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

async function auditTransferChips(page) {
  return page.evaluate(() => {
    const failures = [];
    let checkedTrips = 0;
    let checkedStops = 0;
    const trips = [...state.tripById.values()];
    for (const trip of trips) {
      const traceRouteIds = new Set((trip.lineTrace || []).map((trace) => trace.routeId).filter(Boolean));
      if (traceRouteIds.size < 2 && !trip.throughStitched) continue;
      checkedTrips += 1;
      for (const stop of trip.stopTimes || []) {
        const ownRouteIds = tripRouteIdsAtStop(trip, stop);
        if (!ownRouteIds.length || tripStopIsRouteBoundary(trip, stop)) continue;
        checkedStops += 1;
        const contextRouteId = transferContextRouteIdForTripStop(trip, stop);
        const chipRouteIds = transferRouteIdsForStation(stop.stationGroupId, contextRouteId, { trip, stop });
        const leakedRouteIds = chipRouteIds.filter((routeId) => ownRouteIds.includes(routeId));
        if (!leakedRouteIds.length) continue;
        failures.push({
          tripId: trip.id,
          tripLabel: formatTripLabel(trip),
          station: displayNameForGroup(stop.stationGroupId),
          ownRoutes: ownRouteIds.map(routeTitle),
          leakedRoutes: leakedRouteIds.map(routeTitle),
          contextRoute: routeTitle(contextRouteId),
        });
        if (failures.length >= 50) break;
      }
      if (failures.length >= 50) break;
    }
    return {
      ok: failures.length === 0,
      totalTrips: trips.length,
      checkedTrips,
      checkedStops,
      failureCount: failures.length,
      failures,
    };
  });
}

(async () => {
  const args = parseArgs(process.argv);
  const { browser, page, consoleMessages } = await loadPage(args['page-url']);
  try {
    const result = await auditTransferChips(page);
    result.consoleMessages = consoleMessages;
    console.log(JSON.stringify(result, null, 2));
    if (!result.ok) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
