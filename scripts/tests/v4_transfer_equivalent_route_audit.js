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

async function auditTransferEquivalentRoutes(page) {
  return page.evaluate(() => {
    const START_MINUTE = hhmmToMinutes('06:00');
    const MAX_SAMPLES = 80;

    function groupName(stationGroupId) {
      return displayNameForGroup(stationGroupId);
    }

    function routeChoicesForGroup(stationGroupId, includeTransferEquivalents) {
      return routeChoicesFromDepartures(departuresForStationGroup(stationGroupId, START_MINUTE, { includeTransferEquivalents }))
        .map((choice) => choice.routeId)
        .filter((routeId, index, routeIds) => routeId && routeIds.indexOf(routeId) === index);
    }

    function routeTitles(routeIds) {
      return routeIds.map(routeTitle).sort((a, b) => a.localeCompare(b, 'ja'));
    }

    function groupIdsByDisplayName(name) {
      return [...state.stationGroupById.keys()].filter((stationGroupId) => groupName(stationGroupId) === name);
    }

    function canonicalClusterKey(stationGroupId) {
      return equivalentStationGroupIds(stationGroupId).slice().sort().join('|');
    }

    const clusters = new Map();
    for (const stationGroupId of state.stationGroupById.keys()) {
      const equivalentIds = equivalentStationGroupIds(stationGroupId);
      if (equivalentIds.length < 2) continue;
      const key = canonicalClusterKey(stationGroupId);
      if (!clusters.has(key)) clusters.set(key, equivalentIds.slice().sort());
    }

    const samples = [];
    const pendingDestinationSamples = [];
    const stationGroupSummaries = [];
    let checkedClusters = 0;
    let checkedStationGroups = 0;
    let checkedExactRoutes = 0;
    let missingRouteCount = 0;
    let clustersWithMissingRoutes = 0;
    let checkedPendingTrips = 0;
    let missingPendingDestinationCount = 0;

    for (const equivalentIds of clusters.values()) {
      checkedClusters += 1;
      const exactRouteSet = new Set();
      const exactByGroup = equivalentIds.map((stationGroupId) => {
        const routeIds = routeChoicesForGroup(stationGroupId, false);
        routeIds.forEach((routeId) => exactRouteSet.add(routeId));
        checkedExactRoutes += routeIds.length;
        return {
          stationGroupId,
          station: groupName(stationGroupId),
          exactRoutes: routeTitles(routeIds),
        };
      });
      const expectedRouteIds = [...exactRouteSet];
      if (!expectedRouteIds.length) continue;
      let clusterMissing = false;
      for (const stationGroupId of equivalentIds) {
        checkedStationGroups += 1;
        const mergedRouteIds = routeChoicesForGroup(stationGroupId, true);
        const mergedRouteSet = new Set(mergedRouteIds);
        const missingRouteIds = expectedRouteIds.filter((routeId) => !mergedRouteSet.has(routeId));
        if (!missingRouteIds.length) continue;
        clusterMissing = true;
        missingRouteCount += missingRouteIds.length;
        if (samples.length < MAX_SAMPLES) {
          samples.push({
            station: groupName(stationGroupId),
            stationGroupId,
            equivalentStationGroupIds: equivalentIds,
            expectedRoutes: routeTitles(expectedRouteIds),
            mergedRoutes: routeTitles(mergedRouteIds),
            missingRoutes: routeTitles(missingRouteIds),
            exactByGroup,
          });
        }
      }
      if (clusterMissing) clustersWithMissingRoutes += 1;
      if (stationGroupSummaries.length < MAX_SAMPLES) {
        const routeTitleSet = new Set(expectedRouteIds.map(routeTitle));
        if ([...routeTitleSet].some((title) => title.includes('新幹線'))) {
          stationGroupSummaries.push({
            station: groupName(equivalentIds[0]),
            equivalentStationGroupIds: equivalentIds,
            expectedRoutes: [...routeTitleSet].sort((a, b) => a.localeCompare(b, 'ja')),
            exactByGroup,
          });
        }
      }
    }

    const previousActiveMode = state.activeMode;
    const previousRunner = { ...state.players.runner, steps: [...(state.players.runner?.steps || [])] };
    const previousSelectedRouteId = state.selectedRouteId;
    const previousSelectedTripId = state.selectedTripId;
    const previousPendingTripIds = { ...state.pendingTripIds };
    state.activeMode = 'runner';
    for (const equivalentIds of clusters.values()) {
      for (const stationGroupId of equivalentIds) {
        state.players.runner = { start_station_id: stationGroupId, input_mode: 'plan', steps: [] };
        state.pendingTripIds.runner = null;
        const preview = planCursorPreview('runner');
        const mergedRouteIds = routeChoicesForGroup(stationGroupId, true);
        for (const routeId of mergedRouteIds) {
          const rows = availableRouteDepartures(preview, routeId, 1, 'runner');
          if (!rows.length) continue;
          const row = rows[0];
          checkedPendingTrips += 1;
          state.pendingTripIds.runner = row.trip.id;
          const pending = pendingDepartureContext(preview, 'runner');
          if (!pending || !pending.destinations.length) {
            missingPendingDestinationCount += 1;
            if (pendingDestinationSamples.length < MAX_SAMPLES) {
              pendingDestinationSamples.push({
                station: groupName(stationGroupId),
                stationGroupId,
                route: routeTitle(routeId),
                tripId: row.trip.id,
                departureHhmm: row.departureHhmm,
                boardStation: groupName(row.boardStop.stationGroupId),
                exactStationGroupIds: equivalentIds,
              });
            }
          }
          state.pendingTripIds.runner = null;
        }
      }
    }
    state.activeMode = previousActiveMode;
    state.players.runner = previousRunner;
    state.selectedRouteId = previousSelectedRouteId;
    state.selectedTripId = previousSelectedTripId;
    state.pendingTripIds = previousPendingTripIds;

    const anomalies = [];
    if (missingRouteCount) {
      anomalies.push({
        kind: 'transfer_equivalent_route_choice_missing',
        reason: 'Every player-facing route list for a transfer-equivalent station group must include the union of exact route choices from all equivalent groups, so lines do not disappear when the player selects one physical group.',
        missingRouteCount,
        clustersWithMissingRoutes,
        samples,
      });
    }
    if (missingPendingDestinationCount) {
      anomalies.push({
        kind: 'transfer_equivalent_pending_destinations_missing',
        reason: 'A train chosen from a merged transfer-equivalent route list must still resolve to a pending trip with downstream alighting stops.',
        missingPendingDestinationCount,
        samples: pendingDestinationSamples,
      });
    }
    const requiredNagoyaNames = ['名古屋', '名鉄名古屋', '近鉄名古屋'];
    const requiredNagoyaGroupIds = requiredNagoyaNames
      .map((name) => groupIdsByDisplayName(name)[0])
      .filter(Boolean);
    const nagoyaEquivalentIds = requiredNagoyaGroupIds.length
      ? new Set(equivalentStationGroupIds(requiredNagoyaGroupIds[0]))
      : new Set();
    const missingNagoyaNames = requiredNagoyaNames.filter((name) => {
      const groupId = groupIdsByDisplayName(name)[0];
      return !groupId || !nagoyaEquivalentIds.has(groupId);
    });
    const nagoyaTransferMinutes = requiredNagoyaGroupIds.slice(1).map((groupId) => ({
      from: groupName(requiredNagoyaGroupIds[0]),
      to: groupName(groupId),
      minutes: typeof transferMinutesBetweenStationGroups === 'function'
        ? transferMinutesBetweenStationGroups(requiredNagoyaGroupIds[0], groupId)
        : null,
    }));
    if (missingNagoyaNames.length || nagoyaTransferMinutes.some((item) => item.minutes !== 0)) {
      anomalies.push({
        kind: 'required_nagoya_private_jr_interchange_missing',
        reason: 'For this v4 playtest, Nagoya, Meitetsu Nagoya, and Kintetsu Nagoya must be treated as direct transfer-equivalent station groups, with walking time left as a future refinement.',
        requiredNames: requiredNagoyaNames,
        missingNames: missingNagoyaNames,
        transferMinutes: nagoyaTransferMinutes,
        equivalentNames: [...nagoyaEquivalentIds].map(groupName).sort((a, b) => a.localeCompare(b, 'ja')),
      });
    }
    const kamataGroupId = groupIdsByDisplayName('蒲田')[0];
    const keikyuKamataGroupId = groupIdsByDisplayName('京急蒲田')[0];
    if (kamataGroupId && keikyuKamataGroupId && stationGroupsTransferEquivalent(kamataGroupId, keikyuKamataGroupId)) {
      anomalies.push({
        kind: 'forbidden_kamata_keikyu_kamata_interchange',
        reason: '蒲田 and 京急蒲田 are separate stations for this v4 playtest and must not be instant transfer-equivalent.',
        stationGroupIds: [kamataGroupId, keikyuKamataGroupId],
        transferMinutes: typeof transferMinutesBetweenStationGroups === 'function'
          ? transferMinutesBetweenStationGroups(kamataGroupId, keikyuKamataGroupId)
          : null,
      });
    }

    return {
      anomalyCount: anomalies.length,
      checkedClusters,
      checkedStationGroups,
      checkedExactRoutes,
      checkedPendingTrips,
      missingRouteCount,
      clustersWithMissingRoutes,
      missingPendingDestinationCount,
      shinkansenEquivalentStationSamples: stationGroupSummaries,
      anomalies,
    };
  });
}

async function main() {
  const args = parseArgs(process.argv);
  const { browser, page } = await loadPage(args['page-url']);
  try {
    const result = await auditTransferEquivalentRoutes(page);
    console.log(JSON.stringify(result, null, 2));
    if (result.anomalyCount) process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
