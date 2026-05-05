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
    const next = argv[index + 1];
    if (!next || next.startsWith('--')) {
      args[key.slice(2)] = true;
    } else {
      args[key.slice(2)] = next;
      index += 1;
    }
  }
  if (!args['page-url']) throw new Error('Missing --page-url');
  return args;
}

function integerArg(args, key, defaultValue, { min = 0 } = {}) {
  if (args[key] === undefined || args[key] === true || args[key] === '') return defaultValue;
  const value = Number(args[key]);
  if (!Number.isInteger(value) || value < min) {
    throw new Error(`Invalid --${key}: expected integer >= ${min}`);
  }
  return value;
}

function auditOptionsFromArgs(args) {
  const tripLimit = args['trip-limit'] === undefined
    ? null
    : integerArg(args, 'trip-limit', null, { min: 1 });
  const shardCount = integerArg(args, 'shard-count', 1, { min: 1 });
  const shardIndex = integerArg(args, 'shard-index', 0, { min: 0 });
  if (shardIndex >= shardCount) {
    throw new Error('--shard-index must be smaller than --shard-count');
  }
  return {
    tripStart: integerArg(args, 'trip-start', 0, { min: 0 }),
    tripLimit,
    shardIndex,
    shardCount,
    maxFailures: integerArg(args, 'max-failures', 25, { min: 1 }),
    progressEvery: integerArg(args, 'progress-every', 0, { min: 0 }),
    skipOsakaLoop: Boolean(args['skip-osaka-loop']),
  };
}

async function loadPage(pageUrl) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
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
  return { browser, page };
}

async function auditSelectedTrainHighlights(page, options = {}) {
  return page.evaluate((auditOptions) => {
    const tripStart = auditOptions?.tripStart || 0;
    const tripLimit = Number.isFinite(auditOptions?.tripLimit) ? auditOptions.tripLimit : null;
    const tripEnd = tripLimit ? tripStart + tripLimit : Number.POSITIVE_INFINITY;
    const shardIndex = auditOptions?.shardIndex || 0;
    const shardCount = auditOptions?.shardCount || 1;
    const maxFailures = auditOptions?.maxFailures || 25;
    const progressEvery = auditOptions?.progressEvery || 0;
    const skipOsakaLoop = Boolean(auditOptions?.skipOsakaLoop);
    const samples = [];
    const failures = [];
    const routeStats = new Map();
    let eligibleTripCount = 0;
    let selectedTripCount = 0;
    let checkedTrips = 0;
    let multiTraceTrips = 0;
    let primaryCoverTrips = 0;
    let primaryCoverStartCases = 0;
    let checkedPrimaryGeometryCases = 0;
    let checkedSelectedPathCoverageCases = 0;
    let checkedFutureStopCoverageCases = 0;
    let checkedOsakaAirportLoopCases = 0;
    let checkedContinuousPathCases = 0;

    function endpointScore(coordinates, fromStationGroupId, toStationGroupId) {
      const fromLonLat = stationLonLat(fromStationGroupId);
      const toLonLat = stationLonLat(toStationGroupId);
      if (!coordinates?.length || !fromLonLat || !toLonLat) return Number.POSITIVE_INFINITY;
      const squared = (left, right) => {
        const dx = left[0] - right[0];
        const dy = left[1] - right[1];
        return dx * dx + dy * dy;
      };
      return squared(coordinates[0], fromLonLat) + squared(coordinates[coordinates.length - 1], toLonLat);
    }

    function distanceSquaredToSegments(stationGroupId, segments) {
      const lonLat = stationLonLat(stationGroupId);
      if (!lonLat) return Number.POSITIVE_INFINITY;
      let best = Number.POSITIVE_INFINITY;
      segments.forEach((segment) => {
        const coordinates = segment.coordinates || [];
        coordinates.forEach((coordinate, index) => {
          best = Math.min(
            best,
            index
              ? distanceSquaredToCoordinateSegment(lonLat, coordinates[index - 1], coordinate)
              : coordinateDistanceSquared(lonLat, coordinate)
          );
        });
      });
      return best;
    }

    function routeIdByTitleAndOperator(title, operatorId = '') {
      for (const [routeId, route] of state.routeById.entries()) {
        if (routeTitle(routeId) !== title) continue;
        if (operatorId && route.operatorId !== operatorId) continue;
        return routeId;
      }
      return null;
    }

    function namedRouteStationGroupId(routeId, stationName) {
      if (!routeId) return null;
      return stationGroupIdByRouteStationName(routeId, stationName);
    }

    function coordinateDistance(left, right) {
      if (!left || !right) return Number.POSITIVE_INFINITY;
      return Math.hypot(left[0] - right[0], left[1] - right[1]);
    }

    function segmentEndpointGap(leftSegment, rightSegment) {
      const leftEnd = leftSegment?.coordinates?.at(-1);
      const rightStart = rightSegment?.coordinates?.[0];
      return coordinateDistance(leftEnd, rightStart);
    }

    function continuityBreaksForSegments(segments, maxGap = 0.012) {
      const breaks = [];
      for (let index = 1; index < segments.length; index += 1) {
        const gap = segmentEndpointGap(segments[index - 1], segments[index]);
        if (gap > maxGap) {
          breaks.push({
            index,
            gap,
            previousRoute: routeTitle(segments[index - 1].routeId),
            nextRoute: routeTitle(segments[index].routeId),
            previousEnd: segments[index - 1].coordinates.at(-1) || null,
            nextStart: segments[index].coordinates[0] || null,
          });
        }
      }
      return breaks;
    }

    const sampleTrip = (trip, startStop, ranges, reason) => ({
      reason,
      tripId: trip.id,
      label: formatTripLabel(trip),
      primaryRoute: routeTitle(trip.routeId),
      start: displayNameForGroup(startStop.stationGroupId),
      terminal: displayNameForGroup(trip.stopTimes.at(-1)?.stationGroupId || ''),
      traceRoutes: [...new Set((trip.lineTrace || []).map((trace) => trace.routeId).filter(Boolean))]
        .map((routeId) => routeTitle(routeId)),
      ranges: ranges.map((trace) => ({
        route: routeTitle(trace.routeId),
        fromSequence: trace.fromSequence,
        toSequence: trace.toSequence,
      })),
    });

    const eligibleTripEntries = [...state.tripById.values()]
      .map((trip) => ({ trip, stops: (trip.stopTimes || []).filter((stop) => Number.isFinite(stop.sequence)) }))
      .filter(({ trip, stops }) => trip.routeId && state.routeById.has(trip.routeId) && stops.length >= 2)
      .map((entry, eligibleIndex) => ({ ...entry, eligibleIndex }));
    eligibleTripCount = eligibleTripEntries.length;
    const selectedTripEntries = eligibleTripEntries.filter(({ eligibleIndex }) => (
      eligibleIndex >= tripStart &&
      eligibleIndex < tripEnd &&
      (shardCount <= 1 || eligibleIndex % shardCount === shardIndex)
    ));
    selectedTripCount = selectedTripEntries.length;

    function reachedFailureLimit() {
      return failures.length >= maxFailures;
    }

    function reportProgress(entry) {
      if (!progressEvery || checkedTrips % progressEvery !== 0) return;
      console.log(`__V4_SELECTED_TRAIN_AUDIT_PROGRESS__ ${JSON.stringify({
        checkedTrips,
        selectedTripCount,
        eligibleTripIndex: entry?.eligibleIndex ?? null,
        eligibleTripCount,
        failureCount: failures.length,
      })}`);
    }

    for (const entry of selectedTripEntries) {
      const { trip, stops } = entry;
      checkedTrips += 1;
      const uniqueTraceRouteIds = [...new Set((trip.lineTrace || []).map((trace) => trace.routeId).filter(Boolean))];
      if (uniqueTraceRouteIds.length > 1) multiTraceTrips += 1;
      const terminalStop = stops[stops.length - 1];
      const startsToCheck = uniqueTraceRouteIds.length > 1
        ? stops.slice(0, -1)
        : [stops[0]];
      let tripPrimaryCovered = false;
      for (const startStop of startsToCheck) {
        const ranges = futureLineTraceRanges(trip, startStop.sequence);
        let pathSegments = tripPathSegmentsFromSequence(trip, startStop.sequence);
        if (pathSegments.length) {
          checkedFutureStopCoverageCases += 1;
          const futureStops = stops.filter((stop) => stop.sequence >= startStop.sequence);
          const missingStops = futureStops
            .filter((stop) => distanceSquaredToSegments(stop.stationGroupId, pathSegments) > 0.025 * 0.025)
            .map((stop) => ({
              sequence: stop.sequence,
              station: displayNameForGroup(stop.stationGroupId),
            }));
          if (missingStops.length) {
            failures.push({
              ...sampleTrip(trip, startStop, ranges, 'selected train highlight must cover current and downstream stops'),
              missingStops: missingStops.slice(0, 8),
              selectedSegments: pathSegments.map((segment) => ({
                route: routeTitle(segment.routeId),
                pointCount: segment.coordinates.length,
              })),
            });
            if (reachedFailureLimit()) break;
          }
        }
        const primaryCoordinates = routeSliceCoordinates(trip.routeId, startStop.stationGroupId, terminalStop.stationGroupId);
        if (primaryCoordinates.length < 2) continue;
        const primaryCoordinateEndpointScore = endpointScore(primaryCoordinates, startStop.stationGroupId, terminalStop.stationGroupId);
        if (primaryCoordinateEndpointScore > 0.0009) continue;
        tripPrimaryCovered = true;
        primaryCoverStartCases += 1;
        const mustUseRecordedTrace = Boolean(trip.throughStitched && uniqueTraceRouteIds.length > 1);
        if (mustUseRecordedTrace) {
          const expectedTraceRouteIds = new Set((trip.lineTrace || [])
            .filter((trace) => trace.toSequence >= startStop.sequence && trace.fromSequence <= terminalStop.sequence)
            .map((trace) => typeof reviewedTraceRouteIdForRange === 'function' ? reviewedTraceRouteIdForRange(trip, trace) : trace.routeId)
            .filter(Boolean));
          const actualRouteIds = new Set(ranges.map((trace) => trace.routeId));
          const missingTraceRoutes = [...expectedTraceRouteIds].filter((routeId) => !actualRouteIds.has(routeId));
          if (missingTraceRoutes.length) {
            failures.push({
              ...sampleTrip(trip, startStop, ranges, 'stitched through train highlight must keep recorded current and downstream trace routes'),
              missingTraceRoutes: missingTraceRoutes.map((routeId) => routeTitle(routeId)),
            });
            if (reachedFailureLimit()) break;
          }
        } else if (!trip.lineTrace?.length) {
          const expectedOnePrimaryRange = ranges.length === 1 &&
            ranges[0].routeId === trip.routeId &&
            ranges[0].fromSequence === startStop.sequence &&
            ranges[0].toSequence === terminalStop.sequence;
          if (!expectedOnePrimaryRange) {
            failures.push(sampleTrip(trip, startStop, ranges, 'primary route can cover future run but highlight is fragmented'));
            if (reachedFailureLimit()) break;
          }
        }
        if (pathSegments.length) {
          checkedContinuousPathCases += 1;
          const continuityBreaks = continuityBreaksForSegments(pathSegments);
          if (continuityBreaks.length) {
            failures.push({
              ...sampleTrip(trip, startStop, ranges, 'selected train highlight path must be continuous'),
              continuityBreaks: continuityBreaks.slice(0, 6).map((item) => ({
                ...item,
                gap: Number(item.gap.toFixed(6)),
              })),
              selectedSegments: pathSegments.map((segment) => ({
                route: routeTitle(segment.routeId),
                pointCount: segment.coordinates.length,
              })),
            });
            if (reachedFailureLimit()) break;
          }
        }
        const primarySegmentCoordinates = routeSliceCoordinates(trip.routeId, startStop.stationGroupId, terminalStop.stationGroupId);
        const primaryEndpointScore = endpointScore(primarySegmentCoordinates, startStop.stationGroupId, terminalStop.stationGroupId);
        checkedPrimaryGeometryCases += 1;
        if (!primarySegmentCoordinates.length || primaryEndpointScore > 0.0009) {
          failures.push({
            ...sampleTrip(trip, startStop, ranges, 'primary route range exists but geometry endpoints do not match selected future run'),
            primaryEndpointScore,
            primarySegmentPointCount: primarySegmentCoordinates.length,
            primarySegmentStart: primarySegmentCoordinates[0] || null,
            primarySegmentEnd: primarySegmentCoordinates.at(-1) || null,
          });
          if (reachedFailureLimit()) break;
        } else if (samples.length < 12 && uniqueTraceRouteIds.length > 1 && !mustUseRecordedTrace) {
          samples.push(sampleTrip(trip, startStop, ranges, 'multi-trace trip correctly collapsed to primary route'));
        }

        checkedSelectedPathCoverageCases += 1;
      }
      if (tripPrimaryCovered) {
        primaryCoverTrips += 1;
        const routeTitleText = routeTitle(trip.routeId);
        routeStats.set(routeTitleText, (routeStats.get(routeTitleText) || 0) + 1);
      }
      reportProgress(entry);
      if (reachedFailureLimit()) break;
    }

    const osakaStationGroupId = [...state.stationGroupById.entries()]
      .find(([, group]) => (group.names?.ja || group.primaryName) === '大阪')?.[0] || null;
    const kansaiAirportStationGroupId = [...state.stationGroupById.entries()]
      .find(([, group]) => (group.names?.ja || group.primaryName) === '関西空港')?.[0] || null;
    const osakaLoopRouteId = routeIdByTitleAndOperator('大阪環状線', 'jr_west');
    const westStationIds = ['西九条', '弁天町', '大正']
      .map((stationName) => namedRouteStationGroupId(osakaLoopRouteId, stationName))
      .filter(Boolean);
    const eastStationIds = ['京橋', '鶴橋']
      .map((stationName) => namedRouteStationGroupId(osakaLoopRouteId, stationName))
      .filter(Boolean);
    const fullRangeSelected = tripStart === 0 && !tripLimit && shardCount === 1;
    if (!skipOsakaLoop && fullRangeSelected && osakaStationGroupId && kansaiAirportStationGroupId && osakaLoopRouteId && westStationIds.length && eastStationIds.length) {
      for (const trip of state.tripById.values()) {
        const stops = (trip.stopTimes || []).filter((stop) => Number.isFinite(stop.sequence));
        const startStop = stops.find((stop) => stop.stationGroupId === osakaStationGroupId);
        if (!startStop) continue;
        if (!stops.some((stop) => stop.sequence > startStop.sequence && stop.stationGroupId === kansaiAirportStationGroupId)) continue;
        const segments = tripPathSegmentsFromSequence(trip, startStop.sequence);
        const loopSegments = segments.filter((segment) => segment.routeId === osakaLoopRouteId);
        if (!loopSegments.length) continue;
        checkedOsakaAirportLoopCases += 1;
        const westCovered = westStationIds.some((stationGroupId) => distanceSquaredToSegments(stationGroupId, loopSegments) <= 0.006 * 0.006);
        const eastHighlighted = eastStationIds.some((stationGroupId) => distanceSquaredToSegments(stationGroupId, loopSegments) <= 0.006 * 0.006);
        const selectedRouteTitles = [...new Set(segments.map((segment) => routeTitle(segment.routeId)))];
        const isHaruka = formatTripLabel(trip).includes('はるか');
        const harukaHasReviewedAirportPath = !isHaruka || (
          selectedRouteTitles.includes('大阪環状線') &&
          selectedRouteTitles.includes('阪和線') &&
          selectedRouteTitles.includes('関西空港線') &&
          !selectedRouteTitles.includes('東海道線')
        );
        if (!westCovered || eastHighlighted || !harukaHasReviewedAirportPath) {
          failures.push({
            ...sampleTrip(trip, startStop, futureLineTraceRanges(trip, startStop.sequence), 'Osaka airport-bound train should highlight the west side of Osaka Loop'),
            westCovered,
            eastHighlighted,
            selectedRouteTitles,
            harukaHasReviewedAirportPath,
            selectedSegments: loopSegments.map((segment) => ({
              route: routeTitle(segment.routeId),
              pointCount: segment.coordinates.length,
            })),
          });
          if (reachedFailureLimit()) break;
        }
        if (checkedOsakaAirportLoopCases >= 40) break;
      }
    }

    return {
      auditOptions: {
        tripStart,
        tripLimit,
        shardIndex,
        shardCount,
        maxFailures,
        progressEvery,
        skipOsakaLoop,
      },
      eligibleTripCount,
      selectedTripCount,
      checkedTrips,
      multiTraceTrips,
      primaryCoverTrips,
      primaryCoverStartCases,
      checkedPrimaryGeometryCases,
      checkedSelectedPathCoverageCases,
      checkedFutureStopCoverageCases,
      checkedOsakaAirportLoopCases,
      checkedContinuousPathCases,
      failureCount: failures.length,
      failures,
      topPrimaryCoverRoutes: [...routeStats.entries()]
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'ja'))
        .slice(0, 20)
        .map(([route, count]) => ({ route, count })),
      samples,
    };
  }, options);
}

async function main() {
  const args = parseArgs(process.argv);
  const options = auditOptionsFromArgs(args);
  const { browser, page } = await loadPage(args['page-url']);
  if (options.progressEvery) {
    page.on('console', (message) => {
      const text = message.text();
      if (!text.startsWith('__V4_SELECTED_TRAIN_AUDIT_PROGRESS__')) return;
      console.error(text.replace('__V4_SELECTED_TRAIN_AUDIT_PROGRESS__ ', '[progress] '));
    });
  }
  try {
    const result = await auditSelectedTrainHighlights(page, options);
    console.log(JSON.stringify(result, null, 2));
    if (result.failureCount) {
      process.exitCode = 1;
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
