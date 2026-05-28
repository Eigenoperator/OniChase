#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { performance } = require('perf_hooks');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '../..');

const MAPLIBRE_STUB = `
class FakeMap {
  constructor() {
    this.sources = new Map();
    this.layers = new Map();
    this.filters = {};
    this.canvas = { style: {} };
  }
  addControl() {}
  on(event, layerOrHandler, maybeHandler) {
    const handler = typeof layerOrHandler === 'function' ? layerOrHandler : maybeHandler;
    if (handler && event === 'load') setTimeout(handler, 0);
    return this;
  }
  addSource(id, source) {
    this.sources.set(id, {
      ...source,
      data: source.data,
      setData(data) { this.data = data; },
    });
  }
  getSource(id) { return this.sources.get(id) || null; }
  addLayer(layer) { this.layers.set(layer.id, layer); }
  getLayer(id) { return this.layers.get(id) || null; }
  setFilter(id, filter) { this.filters[id] = filter; }
  setLayoutProperty(id, key, value) {
    const layer = this.layers.get(id) || {};
    layer.layout = { ...(layer.layout || {}), [key]: value };
    this.layers.set(id, layer);
  }
  setPaintProperty(id, key, value) {
    const layer = this.layers.get(id) || {};
    layer.paint = { ...(layer.paint || {}), [key]: value };
    this.layers.set(id, layer);
  }
  getCanvas() { return this.canvas; }
  getZoom() { return 9; }
  fitBounds() {}
  queryRenderedFeatures() { return []; }
}
window.maplibregl = {
  Map: FakeMap,
  NavigationControl: class {},
  AttributionControl: class {},
};
`;

function parseArgs(argv) {
  const args = {};
  for (let index = 2; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith('--')) continue;
    const next = argv[index + 1];
    args[key.slice(2)] = next && !next.startsWith('--') ? next : true;
    if (args[key.slice(2)] !== true) index += 1;
  }
  if (!args['page-url']) throw new Error('Missing --page-url');
  args.runs = Number.parseInt(args.runs || '3', 10);
  if (!Number.isFinite(args.runs) || args.runs < 1) throw new Error('Invalid --runs');
  args['max-timetable-ready-ms'] = Number.parseInt(args['max-timetable-ready-ms'] || '15000', 10);
  args['max-map-ready-ms'] = Number.parseInt(args['max-map-ready-ms'] || '3000', 10);
  args['max-live-render-ms'] = Number.parseInt(args['max-live-render-ms'] || '120', 10);
  return args;
}

function percentile(values, p) {
  const sorted = values.slice().sort((left, right) => left - right);
  if (!sorted.length) return null;
  const index = Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1);
  return sorted[index];
}

function fileSize(relativePath) {
  const absolutePath = path.join(ROOT, relativePath);
  if (!fs.existsSync(absolutePath)) return null;
  return fs.statSync(absolutePath).size;
}

async function loadPage(pageUrl) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const consoleMessages = [];
  page.on('console', (message) => {
    const text = message.text();
    if (!text.includes('GPU stall')) consoleMessages.push(`${message.type()}: ${text}`);
  });
  page.on('pageerror', (error) => {
    consoleMessages.push(`pageerror: ${error.message}`);
  });
  await page.route('https://unpkg.com/**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/javascript',
    body: MAPLIBRE_STUB,
  }));
  await page.route('**/assets/vendor/maplibre-gl-*/maplibre-gl.js', (route) => route.fulfill({
    status: 200,
    contentType: 'application/javascript',
    body: MAPLIBRE_STUB,
  }));
  await page.route('**/assets/vendor/maplibre-gl-*/maplibre-gl.css', (route) => route.fulfill({
    status: 200,
    contentType: 'text/css',
    body: '',
  }));

  const startedAt = Date.now();
  await page.goto(pageUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  const domContentLoadedAt = Date.now();
  await page.waitForFunction(() => typeof state !== 'undefined' && Boolean(state.bundle), null, { timeout: 90000 });
  const mapBundleReadyAt = Date.now();
  await page.evaluate(() => ensureTimetableLoaded());
  await page.waitForFunction(() => state.timetableStatus === 'ready', null, { timeout: 90000 });
  const timetableReadyAt = Date.now();

  return {
    browser,
    page,
    consoleMessages,
    loadTimings: {
      domContentLoadedMs: domContentLoadedAt - startedAt,
      mapBundleReadyMs: mapBundleReadyAt - startedAt,
      timetableReadyMs: timetableReadyAt - startedAt,
      timetableLoadMs: timetableReadyAt - mapBundleReadyAt,
    },
  };
}

async function auditPlannerLiveFlicker(page, maxLiveRenderMs) {
  return page.evaluate(async (maxLiveRenderMs) => {
    const failures = [];
    const renderDurations = [];
    const root = () => document.querySelector('#train-outlook');
    const activeRows = (selector) => [...root().querySelectorAll(`${selector}:not(.planner-row-exit)`)];
    const stepIndex = () => root().querySelector('.planner-step-index')?.textContent.trim() || '';
    const minuteFromRow = (row) => hhmmToMinutes(row.querySelector('.row-meta')?.textContent.trim() || '');
    const rowSummary = () => activeRows('.outlook-row[data-action="choose-trip"], .outlook-row[data-action="choose-coupled"]')
      .map((row) => ({
        key: row.dataset.rowKey || '',
        title: row.querySelector('.row-title')?.textContent.trim() || '',
        minute: minuteFromRow(row),
      }));
    const check = (condition, message, details = {}) => {
      if (!condition) failures.push({ message, details });
    };
    const stationGroupIdByName = (stationName) => [...state.stationGroupById.entries()]
      .find(([, group]) => (group.names?.ja || group.primaryName) === stationName)?.[0] || null;

    const stationGroupId = stationGroupIdByName('東京');
    if (!stationGroupId) throw new Error('Station not found: 東京');
    state.phase = 'LIVE';
    state.clockRunning = false;
    state.latestResult = null;
    state.activeMode = 'runner';
    state.currentGameMinute = hhmmToMinutes('06:30');
    state.players.runner = { start_station_id: stationGroupId, input_mode: 'plan', steps: [] };
    state.pendingTripIds = { runner: null, hunter: null };
    state.planningRouteIds = { runner: null, hunter: null };
    state.pendingCoupledChoices = { runner: null, hunter: null };
    state.selectedRouteId = null;
    state.selectedTripId = null;
    state.selectedTripStopIds = [];
    state.trainOutlookHtml = '';
    renderGame();

    const yamanoteRoute = activeRows('.route-row[data-action="choose-route"]')
      .find((row) => row.querySelector('.row-title')?.textContent.includes('山手線'));
    check(Boolean(yamanoteRoute), 'Planner should expose 山手線 at 東京 06:30');
    if (!yamanoteRoute) return { failureCount: failures.length, failures };
    yamanoteRoute.click();
    check(stepIndex() === '2/3', 'Planner should stay on 2/3 after route selection', { stepIndex: stepIndex() });

    const initialRows = rowSummary();
    const retainedCandidate = initialRows.find((row) => row.minute >= hhmmToMinutes('06:35')) || initialRows[initialRows.length - 1];
    check(Boolean(retainedCandidate), '2/3 should have at least one train row for live refresh checks', { initialRows });
    if (!retainedCandidate) return { failureCount: failures.length, failures };

    const mutationSamples = [];
    const observer = new MutationObserver(() => {
      const outlook = root();
      mutationSamples.push({
        time: performance.now(),
        hasStack: Boolean(outlook?.querySelector('.planner-stack')),
        stepIndex: stepIndex(),
        activeTrainRows: activeRows('.outlook-row[data-action="choose-trip"], .outlook-row[data-action="choose-coupled"]').length,
        hasEmpty: Boolean(outlook?.querySelector('.empty')),
      });
    });
    observer.observe(root(), { childList: true, subtree: true });

    let retainedWhileFutureCount = 0;
    for (let minute = hhmmToMinutes('06:31'); minute <= Math.min(retainedCandidate.minute - 1, hhmmToMinutes('06:34')); minute += 1) {
      state.currentGameMinute = minute;
      const startedAt = performance.now();
      renderGame();
      renderDurations.push(performance.now() - startedAt);
      await new Promise((resolve) => setTimeout(resolve, 190));
      const retainedNode = root().querySelector(`[data-row-key="${CSS.escape(retainedCandidate.key)}"]:not(.planner-row-exit)`);
      if (retainedNode) retainedWhileFutureCount += 1;
      check(stepIndex() === '2/3', 'Live minute refresh should keep the planner on 2/3', {
        currentTime: minutesToHhmm(minute),
        stepIndex: stepIndex(),
      });
      const earliestMinute = Math.min(...rowSummary().map((row) => row.minute).filter(Number.isFinite));
      check(earliestMinute >= minute, 'Live minute refresh should not show departed train rows', {
        currentTime: minutesToHhmm(minute),
        earliest: Number.isFinite(earliestMinute) ? minutesToHhmm(earliestMinute) : null,
      });
    }

    state.currentGameMinute = retainedCandidate.minute + 1;
    const startedAt = performance.now();
    renderGame();
    renderDurations.push(performance.now() - startedAt);
    await new Promise((resolve) => setTimeout(resolve, 190));
    const rowsAfterDeparture = rowSummary();
    const departedStillVisible = rowsAfterDeparture.some((row) => row.key === retainedCandidate.key);
    check(!departedStillVisible, 'A departed retained test row should disappear after its departure minute', {
      retainedCandidate,
      currentTime: minutesToHhmm(state.currentGameMinute),
    });
    check(stepIndex() === '2/3', 'Removing departed rows should not reset planner page', { stepIndex: stepIndex() });
    check(rowsAfterDeparture.length > 0, 'Removing one departed row should not flash to an empty planner list', { rowsAfterDeparture });

    observer.disconnect();
    const emptyMutationCount = mutationSamples.filter((sample) => !sample.hasStack || sample.hasEmpty).length;
    const maxRenderMs = Math.max(...renderDurations, 0);
    check(emptyMutationCount === 0, 'Planner live refresh should not mutate through empty/blank state', {
      emptyMutationCount,
      mutationSamples: mutationSamples.slice(0, 12),
    });
    check(maxRenderMs <= maxLiveRenderMs, 'Planner live refresh render time should stay below threshold', {
      maxRenderMs,
      maxLiveRenderMs,
      renderDurations,
    });
    check(retainedWhileFutureCount > 0 || retainedCandidate.minute <= hhmmToMinutes('06:31'), 'Future train row should be retained in place while still boardable', {
      retainedCandidate,
      retainedWhileFutureCount,
    });

    return {
      failureCount: failures.length,
      failures,
      retainedCandidate,
      retainedWhileFutureCount,
      mutationCount: mutationSamples.length,
      emptyMutationCount,
      renderDurationsMs: renderDurations.map((value) => Math.round(value * 10) / 10),
      maxRenderMs: Math.round(maxRenderMs * 10) / 10,
      rowCountBefore: initialRows.length,
      rowCountAfterDeparture: rowsAfterDeparture.length,
    };
  }, maxLiveRenderMs);
}

(async () => {
  const args = parseArgs(process.argv);
  const failures = [];
  const loadRuns = [];
  let flicker = null;
  let consoleMessages = [];

  for (let run = 0; run < args.runs; run += 1) {
    const { browser, page, loadTimings, consoleMessages: runConsoleMessages } = await loadPage(args['page-url']);
    try {
      loadRuns.push({ run: run + 1, ...loadTimings });
      consoleMessages = consoleMessages.concat(runConsoleMessages);
      if (run === 0) flicker = await auditPlannerLiveFlicker(page, args['max-live-render-ms']);
    } finally {
      await browser.close();
    }
  }

  const mapReadyP95 = percentile(loadRuns.map((run) => run.mapBundleReadyMs), 95);
  const timetableReadyP95 = percentile(loadRuns.map((run) => run.timetableReadyMs), 95);
  if (mapReadyP95 > args['max-map-ready-ms']) {
    failures.push({
      message: 'Map bundle readiness exceeded threshold',
      details: { mapReadyP95, threshold: args['max-map-ready-ms'] },
    });
  }
  if (timetableReadyP95 > args['max-timetable-ready-ms']) {
    failures.push({
      message: 'Timetable readiness exceeded threshold',
      details: { timetableReadyP95, threshold: args['max-timetable-ready-ms'] },
    });
  }
  if (flicker?.failureCount) failures.push(...flicker.failures);
  const relevantConsoleMessages = consoleMessages.filter((message) => !message.includes('Failed to load resource'));
  if (relevantConsoleMessages.length) {
    failures.push({
      message: 'Console/page errors appeared during performance gate',
      details: { consoleMessages: relevantConsoleMessages.slice(0, 20) },
    });
  }

  const result = {
    checkedAt: new Date().toISOString(),
    ok: failures.length === 0,
    failureCount: failures.length,
    thresholds: {
      maxMapReadyMs: args['max-map-ready-ms'],
      maxTimetableReadyMs: args['max-timetable-ready-ms'],
      maxLiveRenderMs: args['max-live-render-ms'],
    },
    bundleSizes: {
      mapBundleGzipBytes: fileSize('docs/data/v4_gameplay_map_bundle.json.gz'),
      compactTimetableGzipBytes: fileSize('docs/data/v4_gameplay_timetable_compact.json.gz'),
      fullTimetableGzipBytes: fileSize('docs/data/v4_gameplay_timetable_bundle.json.gz'),
    },
    loadRuns,
    summary: {
      mapReadyP95,
      timetableReadyP95,
      timetableLoadP95: percentile(loadRuns.map((run) => run.timetableLoadMs), 95),
    },
    plannerLiveFlicker: flicker,
    consoleMessages: relevantConsoleMessages,
    failures,
  };

  const json = JSON.stringify(result, null, 2);
  console.log(json);
  if (args.output && args.output !== true) fs.writeFileSync(args.output, `${json}\n`);
  if (!result.ok) process.exitCode = 1;
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
