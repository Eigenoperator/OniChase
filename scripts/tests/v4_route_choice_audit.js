#!/usr/bin/env node

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
  await page.route('https://unpkg.com/**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/javascript',
    body: MAPLIBRE_STUB,
  }));
  await page.goto(pageUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForFunction(() => typeof state !== 'undefined' && Boolean(state.bundle), null, { timeout: 90000 });
  await page.evaluate(() => ensureTimetableLoaded());
  await page.waitForFunction(() => state.timetableStatus === 'ready', null, { timeout: 90000 });
  return { browser, page };
}

async function auditRouteChoices(page) {
  return page.evaluate(() => {
    const START_MINUTE = hhmmToMinutes('06:00');
    const OMIYA_BRANCH_NEXT_STATIONS = new Set([
      '土呂', '東大宮', '蓮田', '白岡', '久喜', '栗橋', '古河', '野木', '間々田',
      '小山', '小金井', '自治医大', '石橋', '雀宮', '宇都宮',
      '宮原', '上尾', '桶川', '北本', '鴻巣', '熊谷', '籠原', '深谷', '本庄',
      '新町', '倉賀野', '高崎', '新前橋', '前橋',
    ]);

    function stationIdsByName(stationName) {
      return [...state.stationGroupById.entries()]
        .filter(([, group]) => (group.names?.ja || group.primaryName) === stationName)
        .map(([stationGroupId]) => stationGroupId);
    }

    function firstStationIdByName(stationName) {
      return stationIdsByName(stationName)[0] || null;
    }

    function nextStopFor(entry) {
      return (entry.trip?.stopTimes || []).find((stop) => stop.sequence > entry.stop.sequence) || null;
    }

    function routeTitlesForEntry(entry) {
      return routeChoiceIdsForDeparture({
        trip: entry.trip,
        boardStop: entry.stop,
        stop: entry.stop,
        routeIds: entry.routeIds || [],
        departureMinute: entry.departureMinute,
      }).map(routeTitle);
    }

    function summarizeEntry(stationName, entry) {
      const nextStop = nextStopFor(entry);
      return {
        station: stationName,
        departure: minutesToHhmm(entry.departureMinute),
        serviceName: entry.trip?.serviceName || '',
        serviceNumber: publicTripNumber(entry.trip),
        tripRoute: routeTitle(entry.trip?.routeId || ''),
        choices: routeTitlesForEntry(entry),
        rawRouteIds: (entry.routeIds || []).map(routeTitle),
        boardFaceNames: boardingFaceRouteNamesForStop(entry.trip, entry.stop),
        nextStation: nextStop ? displayNameForGroup(nextStop.stationGroupId) : '',
        terminal: displayNameForGroup((entry.trip?.stopTimes || []).at(-1)?.stationGroupId || ''),
        sourceFeedKey: entry.trip?.sourceFeedKey || '',
        tripId: entry.trip?.id || '',
      };
    }

    function choicesAt(stationName) {
      const stationGroupId = firstStationIdByName(stationName);
      if (!stationGroupId) return [];
      return routeChoicesFromDepartures(departuresForStationGroup(stationGroupId, START_MINUTE))
        .map((choice) => ({
          route: routeTitle(choice.routeId),
          firstDeparture: choice.firstDepartureHhmm,
          trainCount: choice.trainCount,
        }));
    }

    function entriesAt(stationName) {
      const stationGroupId = firstStationIdByName(stationName);
      if (!stationGroupId) return [];
      return departuresForStationGroup(stationGroupId, START_MINUTE);
    }

    const anomalies = [];
    const knownStationChoices = Object.fromEntries(
      ['東京', '品川', '大宮', '青梅'].map((stationName) => [stationName, choicesAt(stationName)])
    );
    const routeChoiceTitles = Object.fromEntries(
      Object.entries(knownStationChoices).map(([stationName, choices]) => [
        stationName,
        new Set(choices.map((choice) => choice.route)),
      ])
    );

    if (routeChoiceTitles['東京']?.has('東北線') || routeChoiceTitles['東京']?.has('東海道線')) {
      anomalies.push({
        kind: 'tokyo_physical_trunk_route_choice',
        station: '東京',
        reason: 'Tokyo route choices should use the reviewed virtual corridors, not expose Tohoku/Tokaido physical source labels.',
        choices: knownStationChoices['東京'],
      });
    }

    if (routeChoiceTitles['青梅']?.has('中央線')) {
      anomalies.push({
        kind: 'ome_terminal_or_through_row_route_choice',
        station: '青梅',
        reason: 'Ome route choices should not be polluted by through-service terminal rows whose next boarding segment does not exist.',
        choices: knownStationChoices['青梅'],
      });
    }

    for (const stationName of ['東京', '品川']) {
      for (const entry of entriesAt(stationName)) {
        const choices = routeTitlesForEntry(entry);
        if (choices.includes('東海道線') || choices.includes('東北線') || choices.includes('高崎線')) {
          anomalies.push({
            kind: 'central_ueno_tokyo_physical_choice',
            reason: `${stationName} should expose the Ueno-Tokyo corridor instead of parallel physical source labels for through-running trains.`,
            ...summarizeEntry(stationName, entry),
          });
        }
      }
    }

    for (const entry of entriesAt('大宮')) {
      const summary = summarizeEntry('大宮', entry);
      if (summary.choices.includes('東海道線')) {
        anomalies.push({
          kind: 'omiya_tokaido_choice',
          reason: 'Tokaido is a south-side source label and must not be a selectable boarding line at Omiya.',
          ...summary,
        });
      }
      if (summary.choices.includes('上野東京ライン') && OMIYA_BRANCH_NEXT_STATIONS.has(summary.nextStation)) {
        anomalies.push({
          kind: 'omiya_branch_hidden_by_ueno_tokyo',
          reason: 'At Omiya, northbound branch movements must show the branch boarding face, not the through-service corridor.',
          ...summary,
        });
      }
    }

    for (const entry of entriesAt('青梅')) {
      const summary = summarizeEntry('青梅', entry);
      if (summary.nextStation && summary.choices.includes('中央線')) {
        anomalies.push({
          kind: 'ome_branch_central_choice',
          reason: 'Ome branch departures should remain on the Ome Line choice even when the service runs through to Chuo.',
          ...summary,
        });
      }
    }

    return {
      checkedAt: new Date().toISOString(),
      stationCount: state.stationGroupById.size,
      tripCount: state.tripById?.size || 0,
      knownStationChoices,
      anomalyCount: anomalies.length,
      anomalies: anomalies.slice(0, 80),
    };
  });
}

(async () => {
  const args = parseArgs(process.argv);
  const { browser, page } = await loadPage(args['page-url']);
  try {
    const result = await auditRouteChoices(page);
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    if (result.anomalyCount) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
