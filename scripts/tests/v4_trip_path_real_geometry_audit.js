#!/usr/bin/env node

const { chromium } = require('playwright');

const MAPLIBRE_STUB = `
class FakeMap {
  constructor() {
    this.sources = new Map();
    this.layers = new Map();
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
  setFilter() {}
  setLayoutProperty() {}
  setPaintProperty() {}
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
    if (!next || next.startsWith('--')) args[key.slice(2)] = true;
    else {
      args[key.slice(2)] = next;
      index += 1;
    }
  }
  if (!args['page-url']) throw new Error('Missing --page-url');
  return args;
}

async function loadPage(pageUrl) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
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
  return { browser, page };
}

async function audit(page) {
  return page.evaluate(() => {
    const failures = [];
    const samples = [];
    let checkedAdjacentSegments = 0;
    let checkedLimitedExpressSegments = 0;
    let strictMissingRealPathCount = 0;
    let reviewedHintSegmentCount = 0;

    function sameCoordinate(left, right) {
      return Boolean(left && right && coordinateDistanceSquared(left, right) < 1e-14);
    }

    function tripLooksHighRisk(trip) {
      const label = formatTripLabel(trip);
      return isLimitedExpressTrip(trip) ||
        /エクスプレス|はるか|ひたち|ときわ|あずさ|しなの|サンダーバード|成田エクスプレス/u.test(label);
    }

    function segmentSummary(trip, routeId, currentStop, nextStop, reason) {
      return {
        reason,
        tripId: trip.id,
        label: formatTripLabel(trip),
        route: routeTitle(routeId),
        from: displayNameForGroup(currentStop.stationGroupId),
        to: displayNameForGroup(nextStop.stationGroupId),
      };
    }

    for (const trip of state.tripById.values()) {
      if (!tripLooksHighRisk(trip)) continue;
      const stops = (trip.stopTimes || [])
        .filter((stop) => Number.isFinite(stop.sequence))
        .sort((a, b) => a.sequence - b.sequence);
      for (let index = 0; index < stops.length - 1; index += 1) {
        const currentStop = stops[index];
        const nextStop = stops[index + 1];
        const reviewedSegments = reviewedTripPathSegmentsForStopPair(trip, currentStop, nextStop);
        if (reviewedSegments?.length) {
          reviewedHintSegmentCount += 1;
          continue;
        }
        const tracedRouteId = tracedRouteIdForTripSegment(trip, currentStop, nextStop) || trip.routeId;
        const routeId = physicalRouteIdForTraceStopPair(trip, tracedRouteId, currentStop, nextStop);
        const route = state.routeById.get(routeId);
        const coordinates = coordinatesForTripSegment(routeId, currentStop, nextStop, {
          allowPhysicalGraphFallback: false,
          allowStationPairFallback: false,
        });
        checkedAdjacentSegments += 1;
        checkedLimitedExpressSegments += 1;
        if (!coordinates.length) {
          strictMissingRealPathCount += 1;
          if (samples.length < 12) {
            samples.push(segmentSummary(trip, routeId, currentStop, nextStop, 'strict geometry missing; no synthetic line is drawn'));
          }
          continue;
        }
        if (!isShinkansenTrip(trip) && (route?.mode === 'shinkansen' || route?.operatorId === 'shinkansen')) {
          failures.push(segmentSummary(trip, routeId, currentStop, nextStop, 'conventional or limited express train must not borrow Shinkansen geometry'));
          continue;
        }
        const from = stationLonLat(currentStop.stationGroupId);
        const to = stationLonLat(nextStop.stationGroupId);
        const stationPairLength = coordinatePathLength([from, to].filter(Boolean));
        const isSyntheticStationPair = coordinates.length === 2 &&
          sameCoordinate(coordinates[0], from) &&
          sameCoordinate(coordinates[1], to);
        if (isSyntheticStationPair && stationPairLength > 0.006) {
          failures.push({
            ...segmentSummary(trip, routeId, currentStop, nextStop, 'long train segment must not use station-to-station synthetic geometry'),
            stationPairLength,
          });
        }
      }
    }

    const nexTrip = [...state.tripById.values()]
      .find((trip) => formatTripLabel(trip).includes('成田エクスプレス28') &&
        (trip.stopTimes || []).some((stop) => displayNameForGroup(stop.stationGroupId) === '空港第2ビル') &&
        (trip.stopTimes || []).some((stop) => displayNameForGroup(stop.stationGroupId) === '東京'));
    if (nexTrip) {
      const segments = tripPathSegmentsFromSequence(nexTrip, Math.min(...nexTrip.stopTimes.map((stop) => stop.sequence)));
      const routeTitles = segments.map((segment) => routeTitle(segment.routeId));
      const hasRequiredRoutes = ['成田線', '総武線', '東海道線'].every((routeName) => routeTitles.includes(routeName));
      const hasForbiddenRoutes = routeTitles.some((routeName) => /新幹線|成田空港線/u.test(routeName));
      if (!hasRequiredRoutes || hasForbiddenRoutes) {
        failures.push({
          reason: 'Narita Express airport-to-Tokyo/Shinagawa path must stay on reviewed JR physical routes',
          tripId: nexTrip.id,
          label: formatTripLabel(nexTrip),
          routeTitles,
        });
      }
    } else {
      failures.push({ reason: 'Narita Express sample trip not found' });
    }

    return {
      checkedAdjacentSegments,
      checkedLimitedExpressSegments,
      reviewedHintSegmentCount,
      strictMissingRealPathCount,
      failureCount: failures.length,
      failures,
      samples,
    };
  });
}

async function main() {
  const args = parseArgs(process.argv);
  const { browser, page } = await loadPage(args['page-url']);
  try {
    const result = await audit(page);
    console.log(JSON.stringify(result, null, 2));
    if (result.failureCount) process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
