#!/usr/bin/env node

const fs = require('fs');
const { chromium } = require('playwright');

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
    args[key.slice(2)] = argv[index + 1];
    index += 1;
  }
  if (!args['page-url']) throw new Error('Missing --page-url');
  return args;
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
  await page.goto(pageUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForFunction(() => typeof state !== 'undefined' && Boolean(state.bundle), null, { timeout: 90000 });
  await page.evaluate(() => ensureTimetableLoaded());
  await page.waitForFunction(() => state.timetableStatus === 'ready', null, { timeout: 90000 });
  return { browser, page, consoleMessages };
}

async function auditPlannerInteractions(page) {
  return page.evaluate(async () => {
    const failures = [];
    const steps = [];
    const root = () => document.querySelector('#train-outlook');
    const activeRows = (selector) => [...root().querySelectorAll(`${selector}:not(.planner-row-exit)`)];
    const stepIndex = () => root().querySelector('.planner-step-index')?.textContent.trim() || '';
    const rowMetas = (selector) => activeRows(selector)
      .map((row) => row.querySelector('.row-meta')?.textContent.trim() || '')
      .filter(Boolean);
    const toMinute = (hhmm) => hhmmToMinutes(hhmm);
    const minMetaMinute = (selector) => {
      const minutes = rowMetas(selector).map(toMinute).filter(Number.isFinite);
      return minutes.length ? Math.min(...minutes) : null;
    };
    const click = (node) => {
      if (!node) throw new Error('Cannot click missing planner node');
      node.click();
    };
    const check = (condition, message, details = {}) => {
      if (!condition) failures.push({ message, details });
    };

    function stationGroupIdByName(stationName) {
      return [...state.stationGroupById.entries()]
        .find(([, group]) => (group.names?.ja || group.primaryName) === stationName)?.[0] || null;
    }

    function resetRunnerAt(stationName, currentHhmm) {
      const stationGroupId = stationGroupIdByName(stationName);
      if (!stationGroupId) throw new Error(`Station not found: ${stationName}`);
      state.phase = 'LIVE';
      state.clockRunning = false;
      state.latestResult = null;
      state.activeMode = 'runner';
      state.currentGameMinute = hhmmToMinutes(currentHhmm);
      state.players.runner = { start_station_id: stationGroupId, input_mode: 'plan', steps: [] };
      state.pendingTripIds = { runner: null, hunter: null };
      state.planningRouteIds = { runner: null, hunter: null };
      state.pendingCoupledChoices = { runner: null, hunter: null };
      state.selectedRouteId = null;
      state.selectedTripId = null;
      state.selectedTripStopIds = [];
      state.trainOutlookHtml = '';
      renderGame();
      return stationGroupId;
    }

    resetRunnerAt('東京', '06:30');
    check(stepIndex() === '1/3', 'Planner should start on 1/3 line selection at a station', { stepIndex: stepIndex() });
    const routeRows = activeRows('.route-row[data-action="choose-route"]');
    check(routeRows.length > 0, '1/3 should show route rows at 東京', { routeRows: routeRows.length });
    const earliestRouteMinute = minMetaMinute('.route-row');
    check(earliestRouteMinute !== null && earliestRouteMinute >= hhmmToMinutes('06:30'), '1/3 should not show pre-06:30 route departures', {
      earliest: earliestRouteMinute === null ? null : minutesToHhmm(earliestRouteMinute),
    });

    const routeOrderAt = (hhmm) => {
      resetRunnerAt('東京', hhmm);
      return activeRows('.route-row[data-action="choose-route"]').map((row) => ({
        routeId: row.dataset.routeId || '',
        title: row.querySelector('.row-title')?.textContent.trim() || '',
        category: routeChoiceSortCategory(row.dataset.routeId || ''),
      }));
    };
    const order0630 = routeOrderAt('06:30');
    const order1000 = routeOrderAt('10:00');
    const common0630 = order0630.map((row) => row.title).filter((title) => order1000.some((row) => row.title === title));
    const common1000 = order1000.map((row) => row.title).filter((title) => order0630.some((row) => row.title === title));
    check(common0630.join('|') === common1000.join('|'), '1/3 route order should stay stable as time advances', {
      order0630: common0630,
      order1000: common1000,
    });
    [order0630, order1000].forEach((order, index) => {
      const badCategoryIndex = order.findIndex((row, rowIndex) => rowIndex > 0 && row.category < order[rowIndex - 1].category);
      check(badCategoryIndex < 0, '1/3 route order should group Shinkansen, JR/private, then named limited expresses', {
        sample: index === 0 ? '06:30' : '10:00',
        order: order.slice(0, 24),
        badCategoryIndex,
      });
    });

    resetRunnerAt('東京', '06:30');
    const refreshedRouteRows = activeRows('.route-row[data-action="choose-route"]');
    const routeNode = refreshedRouteRows.find((row) => row.querySelector('.row-title')?.textContent.includes('山手線')) || refreshedRouteRows[0];
    const routeKey = routeNode.dataset.rowKey;
    renderGame();
    renderGame();
    check(root().querySelector(`[data-row-key="${CSS.escape(routeKey)}"]`) === routeNode, 'Same-content renders should retain the selected route row DOM node', { routeKey });
    click(routeNode);
    check(stepIndex() === '2/3', 'Clicking a route should move planner to 2/3 train selection', { stepIndex: stepIndex() });
    const selectedRouteId = state.planningRouteIds.runner;
    check(Boolean(selectedRouteId), 'Route click should set runner planning route exactly once');
    const trainRows = activeRows('.outlook-row[data-action="choose-trip"], .outlook-row[data-action="choose-coupled"]');
    check(trainRows.length > 0, '2/3 should show train rows after route selection', { trainRows: trainRows.length });
    const earliestTrainMinute = minMetaMinute('.outlook-row');
    check(earliestTrainMinute !== null && earliestTrainMinute >= hhmmToMinutes('06:30'), '2/3 should not show pre-06:30 trains', {
      earliest: earliestTrainMinute === null ? null : minutesToHhmm(earliestTrainMinute),
    });

    const trainNode = trainRows[0];
    const trainKey = trainNode.dataset.rowKey;
    renderGame();
    check(root().querySelector(`[data-row-key="${CSS.escape(trainKey)}"]`) === trainNode, 'Same-minute 2/3 render should retain the train row DOM node', { trainKey });
    state.currentGameMinute = hhmmToMinutes('06:31');
    renderGame();
    const retainedTrainNode = root().querySelector(`[data-row-key="${CSS.escape(trainKey)}"]`);
    const earliestTrainAfterMinute = minMetaMinute('.outlook-row');
    check(earliestTrainAfterMinute !== null && earliestTrainAfterMinute >= hhmmToMinutes('06:31'), '2/3 should refresh away trains before 06:31', {
      earliest: earliestTrainAfterMinute === null ? null : minutesToHhmm(earliestTrainAfterMinute),
    });
    if (retainedTrainNode) {
      check(retainedTrainNode === trainNode, 'Minute refresh should patch retained train rows in place', { trainKey });
    }

    const refreshedTrainRows = activeRows('.outlook-row[data-action="choose-trip"], .outlook-row[data-action="choose-coupled"]');
    const trainToClick = refreshedTrainRows[0];
    if (!trainToClick) {
      failures.push({
        message: '2/3 should still have a clickable train after minute refresh',
        details: {
          selectedRoute: selectedRouteId ? routeTitle(selectedRouteId) : null,
          currentTime: minutesToHhmm(state.currentGameMinute),
          trainRowsAfterRefresh: refreshedTrainRows.length,
        },
      });
      return { ok: false, failureCount: failures.length, failures, steps };
    }
    click(trainToClick);
    if (stepIndex() === '3/3' && root().querySelector('[data-action="choose-trip"]')) {
      const portionTrip = root().querySelector('[data-action="choose-trip"]');
      if (portionTrip) click(portionTrip);
    }
    check(stepIndex() === '3/3', 'Choosing a train should move planner to 3/3 destination selection', { stepIndex: stepIndex() });
    const destinationRows = activeRows('.destination-row[data-action="ride-here"]');
    check(destinationRows.length > 0, '3/3 should show downstream destination rows', { destinationRows: destinationRows.length });
    const destinationIndex = Math.min(5, Math.max(0, destinationRows.length - 1));
    const destinationNode = destinationRows[destinationIndex];
    const destinationKey = destinationNode?.dataset.rowKey || null;
    const destinationStationId = destinationNode?.dataset.stationGroupId || null;
    const selectedTripId = state.selectedTripId;
    const selectedTrip = state.tripById.get(selectedTripId);
    const boardStop = selectedTrip ? findBoardingStop(selectedTrip, state.players.runner.start_station_id, effectiveDepartureMinute('runner', state.currentGameMinute)) : null;
    const alightStop = selectedTrip && destinationStationId ? findAlightStop(selectedTrip, boardStop?.sequence ?? -1, destinationStationId) : null;
    const boardMinute = boardStop ? stopDepartureMinutes(boardStop) : null;
    const alightMinute = alightStop ? stopArrivalMinutes(alightStop) : null;
    check(Boolean(boardStop && alightStop), 'Selected train should have a board stop and chosen downstream alight stop', {
      trip: selectedTripId,
      board: boardStop ? displayNameForGroup(boardStop.stationGroupId) : null,
      alight: destinationStationId ? displayNameForGroup(destinationStationId) : null,
    });

    renderGame();
    renderGame();
    check(
      destinationKey ? root().querySelector(`[data-row-key="${CSS.escape(destinationKey)}"]`) === destinationNode : false,
      'Repeated 3/3 renders should retain destination row DOM node before click',
      { destinationKey },
    );
    const beforePlanLength = state.players.runner.steps.length;
    click(destinationNode);
    const afterPlanLength = state.players.runner.steps.length;
    check(afterPlanLength - beforePlanLength === 2, 'Clicking one destination should add exactly BOARD_TRAIN + RIDE_TO_STATION once', {
      beforePlanLength,
      afterPlanLength,
      addedSteps: state.players.runner.steps.slice(beforePlanLength),
    });
    check(state.players.runner.steps.at(-1)?.station_id === destinationStationId, 'Destination click should add the clicked alighting station');

    if (Number.isFinite(boardMinute) && Number.isFinite(alightMinute) && alightMinute > boardMinute + 1) {
      state.currentGameMinute = boardMinute + 1;
      state.trainOutlookHtml = '';
      renderGame();
      const preview = previewPlayer('runner', state.currentGameMinute);
      check(preview.currentState.kind === 'TRAIN', 'At board+1 minute the runner should be onboard for the future-planning check', {
        time: minutesToHhmm(state.currentGameMinute),
        currentState: preview.currentState,
      });
      check(stepIndex() === '1/3', 'Onboard player with a planned future alight should be able to plan onward from 1/3', {
        stepIndex: stepIndex(),
        alight: destinationStationId ? displayNameForGroup(destinationStationId) : null,
      });
      check(activeRows('.route-row[data-action="choose-route"]').length > 0, 'Onboard future-planning 1/3 should show onward route choices');
    } else {
      failures.push({
        message: 'Chosen ride was too short to verify onboard future planning',
        details: {
          board: boardMinute === null ? null : minutesToHhmm(boardMinute),
          alight: alightMinute === null ? null : minutesToHhmm(alightMinute),
        },
      });
    }

    steps.push({
      start: '東京',
      selectedRoute: selectedRouteId ? routeTitle(selectedRouteId) : null,
      selectedTrip: selectedTrip ? formatTripLabel(selectedTrip) : null,
      board: boardMinute === null ? null : minutesToHhmm(boardMinute),
      alight: alightMinute === null ? null : minutesToHhmm(alightMinute),
      destination: destinationStationId ? displayNameForGroup(destinationStationId) : null,
      planLength: state.players.runner.steps.length,
    });

    return {
      ok: failures.length === 0,
      failureCount: failures.length,
      failures,
      steps,
    };
  });
}

async function main() {
  const args = parseArgs(process.argv);
  const { browser, page, consoleMessages } = await loadPage(args['page-url']);
  try {
    const result = await auditPlannerInteractions(page);
    result.consoleMessages = consoleMessages;
    const json = JSON.stringify(result, null, 2);
    if (args.output && args.output !== true) fs.writeFileSync(args.output, `${json}\n`);
    console.log(json);
    if (!result.ok || consoleMessages.some((message) => message.startsWith('pageerror:'))) process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
