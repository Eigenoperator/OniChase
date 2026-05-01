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

const LONG_DISTANCE_CASES = [
  { name: 'tokyo_to_hakata', stops: [
    { name: '東京', routes: ['東海道・山陽新幹線'] },
    { name: '博多', routes: ['東海道・山陽新幹線'] },
  ] },
  { name: 'tokyo_to_shin_hakodate', stops: [
    { name: '東京', routes: ['東北・北海道新幹線'] },
    { name: '新函館北斗', routes: ['東北・北海道新幹線'] },
  ] },
  { name: 'tokyo_to_kanazawa', stops: [
    { name: '東京', routes: ['北陸新幹線'] },
    { name: '金沢', routes: ['北陸新幹線'] },
  ] },
  { name: 'tokyo_to_shirahama', stops: [
    { name: '東京', routes: ['東海道・山陽新幹線'] },
    { name: '新大阪', routes: ['東海道・山陽新幹線', 'くろしお'] },
    { name: '白浜', routes: ['くろしお'] },
  ] },
  { name: 'osaka_to_kinosaki_onsen', stops: [
    { name: '大阪', routes: ['こうのとり'] },
    { name: '城崎温泉', routes: ['こうのとり'] },
  ] },
  { name: 'kyoto_to_amanohashidate', stops: [
    { name: '京都', routes: ['はしだて'] },
    { name: '天橋立', routes: ['はしだて'] },
  ] },
  { name: 'nagoya_to_takayama', stops: [
    { name: '名古屋', routes: ['ひだ'] },
    { name: '高山', routes: ['ひだ'] },
  ] },
  { name: 'nagoya_to_shingu', stops: [
    { name: '名古屋', routes: ['南紀'] },
    { name: '新宮', routes: ['南紀'] },
  ] },
  { name: 'okayama_to_izumoshi', stops: [
    { name: '岡山', routes: ['やくも'] },
    { name: '出雲市', routes: ['やくも'] },
  ] },
  { name: 'okayama_to_matsuyama', stops: [
    { name: '岡山', routes: ['しおかぜ'] },
    { name: '松山', routes: ['しおかぜ'] },
  ] },
  { name: 'takamatsu_to_uwajima', stops: [
    { name: '高松', routes: ['予讃線', 'いしづち'] },
    { name: '松山', routes: ['予讃線', 'いしづち'] },
    { name: '宇和島', routes: ['予讃線', '宇和海'] },
  ] },
  { name: 'hakata_to_kagoshima_chuo', stops: [
    { name: '博多', routes: ['九州新幹線'] },
    { name: '鹿児島中央', routes: ['九州新幹線'] },
  ] },
  { name: 'hakata_to_sasebo', stops: [
    { name: '博多', routes: ['みどり'] },
    { name: '佐世保', routes: ['佐世保線'] },
  ] },
  { name: 'hakata_to_nagasaki', stops: [
    { name: '博多', routes: ['リレーかもめ'] },
    { name: '武雄温泉', routes: ['リレーかもめ', '西九州新幹線'] },
    { name: '長崎', routes: ['西九州新幹線'] },
  ] },
  { name: 'kumamoto_to_miyaji', stops: [
    { name: '熊本', routes: ['豊肥線'] },
    { name: '宮地', routes: ['豊肥線'] },
  ] },
  { name: 'kagoshima_chuo_to_makurazaki', stops: [
    { name: '鹿児島中央', routes: ['指宿枕崎線'] },
    { name: '指宿', routes: ['指宿枕崎線'] },
    { name: '枕崎', routes: ['指宿枕崎線'] },
  ] },
  { name: 'sapporo_to_shin_hakodate', stops: [
    { name: '札幌', routes: ['函館線'] },
    { name: '新函館北斗', routes: ['函館線'] },
  ] },
  { name: 'sapporo_to_wakkanai', stops: [
    { name: '札幌', routes: ['宗谷'] },
    { name: '稚内', routes: ['宗谷線'] },
  ] },
  { name: 'sapporo_to_nemuro', stops: [
    { name: '札幌', routes: ['函館線'] },
    { name: '釧路', routes: ['根室線'] },
    { name: '根室', routes: ['根室線'] },
  ] },
  { name: 'shin_aomori_to_ominato', stops: [
    { name: '新青森', routes: ['奥羽線'] },
    { name: '青森', routes: ['奥羽線'] },
    { name: '野辺地', routes: ['青い森鉄道線'] },
    { name: '大湊', routes: ['大湊線'] },
  ] },
  { name: 'sendai_to_onagawa', stops: [
    { name: '仙台', routes: ['仙石線'] },
    { name: '石巻', routes: ['仙石線', '石巻線'] },
    { name: '女川', routes: ['石巻線'] },
  ] },
  { name: 'tokyo_to_choshi', stops: [
    { name: '東京', routes: ['しおさい'] },
    { name: '銚子', routes: ['総武線'] },
  ] },
  { name: 'tokyo_to_okutama', stops: [
    { name: '東京', routes: ['中央線快速'] },
    { name: '青梅', routes: ['青梅線'] },
    { name: '奥多摩', routes: ['青梅線'] },
  ] },
  { name: 'shinjuku_to_kawaguchiko', stops: [
    { name: '新宿', routes: ['富士回遊'] },
    { name: '河口湖', routes: ['富士山麓電気鉄道河口湖線'] },
  ] },
  { name: 'matsumoto_to_minami_otari', stops: [
    { name: '松本', routes: ['大糸線'] },
    { name: '信濃大町', routes: ['大糸線'] },
    { name: '南小谷', routes: ['大糸線'] },
  ] },
  { name: 'tottori_to_hamasaka', stops: [
    { name: '鳥取', routes: ['山陰線'] },
    { name: '浜坂', routes: ['山陰線'] },
  ] },
  { name: 'yonago_to_sakaiminato', stops: [
    { name: '米子', routes: ['境線'] },
    { name: '境港', routes: ['境線'] },
  ] },
  { name: 'kochi_to_nahari', stops: [
    { name: '高知', routes: ['土讃線'] },
    { name: '後免', routes: ['土讃線', '土佐くろしお鉄道阿佐線'] },
    { name: '奈半利', routes: ['土佐くろしお鉄道阿佐線'] },
  ] },
  { name: 'kochi_to_sukumo', stops: [
    { name: '高知', routes: ['土讃線'] },
    { name: '窪川', routes: ['土讃線', '土佐くろしお鉄道中村線'] },
    { name: '宿毛', routes: ['土佐くろしお鉄道宿毛線'] },
  ] },
  { name: 'naha_airport_to_shuri', stops: [
    { name: '那覇空港', routes: ['沖縄都市モノレール線'] },
    { name: '首里', routes: ['沖縄都市モノレール線'] },
  ] },
];

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

async function auditLongDistancePlayability(page) {
  return page.evaluate((cases) => {
    const START_MINUTE = hhmmToMinutes('06:00');
    const END_MINUTE = hhmmToMinutes('30:00');
    const MIN_TRANSFER_MINUTES = 2;

    function routeChoicesForGroup(stationGroupId, includeTransferEquivalents = false, minute = START_MINUTE) {
      return routeChoicesFromDepartures(departuresForStationGroup(stationGroupId, minute, { includeTransferEquivalents }))
        .map((choice) => routeTitle(choice.routeId));
    }

    function routeChoiceSummariesForGroup(stationGroupId, includeTransferEquivalents = false, minute = START_MINUTE) {
      return routeChoicesFromDepartures(departuresForStationGroup(stationGroupId, minute, { includeTransferEquivalents }))
        .map((choice) => ({
          route: routeTitle(choice.routeId),
          firstDeparture: choice.firstDepartureHhmm,
          trainCount: choice.trainCount,
        }));
    }

    function groupIdsByDisplayName(name) {
      return [...state.stationGroupById.keys()].filter((stationGroupId) => displayNameForGroup(stationGroupId) === name);
    }

    function selectStationGroup(selector) {
      const candidates = groupIdsByDisplayName(selector.name)
        .map((stationGroupId) => ({
          stationGroupId,
          routes: routeChoicesForGroup(stationGroupId, false),
        }));
      const matching = selector.routes?.length
        ? candidates.filter((candidate) => selector.routes.every((routeName) => candidate.routes.includes(routeName)))
        : candidates;
      return {
        selector,
        candidates,
        selected: matching.length === 1 ? matching[0] : null,
        selectedCount: matching.length,
      };
    }

    function stationMatchesSelector(stationGroupId, selectedTargetGroupId) {
      return stationGroupId === selectedTargetGroupId || equivalentStationGroupIds(stationGroupId).includes(selectedTargetGroupId);
    }

    function routeNamesForEntry(entry) {
      const routeIds = routeChoiceIdsForDeparture({
        trip: entry.trip,
        boardStop: entry.stop,
        stop: entry.stop,
        routeIds: entry.routeIds || [],
        departureMinute: entry.departureMinute,
        queryStationGroupId: entry.queryStationGroupId,
      });
      return routeIds.map(routeTitle).filter(Boolean);
    }

    function findLeg(originGroupId, targetGroupId, currentMinute) {
      const departures = departuresForStationGroup(originGroupId, currentMinute, { includeTransferEquivalents: true });
      for (const departure of departures) {
        const routeNames = routeNamesForEntry(departure);
        if (!routeNames.length || !hasDownstreamStop(departure.trip, departure.stop)) continue;
        for (const stop of departure.trip.stopTimes || []) {
          if (stop.sequence <= departure.stop.sequence) continue;
          if (!stationMatchesSelector(stop.stationGroupId, targetGroupId)) continue;
          const arrivalMinute = Math.ceil((stop.arrivalTimeSec ?? stop.departureTimeSec ?? 0) / 60);
          if (!Number.isFinite(arrivalMinute) || arrivalMinute > END_MINUTE) return null;
          return {
            route: routeNames[0],
            train: formatTripLabel(departure.trip),
            from: displayNameForGroup(departure.stop.stationGroupId),
            to: displayNameForGroup(stop.stationGroupId),
            depart: minutesToHhmm(departure.departureMinute),
            arrive: minutesToHhmm(arrivalMinute),
            arrivalMinute,
            tripId: departure.trip.id,
          };
        }
      }
      return null;
    }

    function auditWaypointSurface(testCase, stopIndex, stationGroupId, selector, currentMinute, nextTargetGroupId) {
      const choices = routeChoiceSummariesForGroup(stationGroupId, true, currentMinute);
      const choiceTitles = new Set(choices.map((choice) => choice.route));
      const missingExpectedRoutes = (selector.routes || []).filter((routeName) => !choiceTitles.has(routeName));
      if (missingExpectedRoutes.length) {
        anomalies.push({
          kind: 'long_distance_waypoint_expected_route_missing',
          name: testCase.name,
          stopIndex,
          station: selector.name,
          stationGroupId,
          after: minutesToHhmm(currentMinute),
          missingExpectedRoutes,
          choices,
        });
      }

      const departures = departuresForStationGroup(stationGroupId, currentMinute, { includeTransferEquivalents: true });
      let boardableDepartureCount = 0;
      let candidateToNextCount = 0;
      let skippedNonBoardableDepartureCount = 0;
      for (const departure of departures) {
        const routeNames = routeNamesForEntry(departure);
        const downstreamStops = (departure.trip?.stopTimes || []).filter((stop) => stop.sequence > departure.stop.sequence);
        if (routeNames.length && downstreamStops.length) boardableDepartureCount += 1;
        else skippedNonBoardableDepartureCount += 1;
        if (nextTargetGroupId && downstreamStops.some((stop) => stationMatchesSelector(stop.stationGroupId, nextTargetGroupId))) {
          candidateToNextCount += 1;
        }
      }
      if (!boardableDepartureCount) {
        anomalies.push({
          kind: 'long_distance_waypoint_no_boardable_departures',
          name: testCase.name,
          stopIndex,
          station: selector.name,
          stationGroupId,
          after: minutesToHhmm(currentMinute),
          choices,
        });
      }
      if (nextTargetGroupId && !candidateToNextCount) {
        anomalies.push({
          kind: 'long_distance_waypoint_no_candidate_to_next_stop',
          name: testCase.name,
          stopIndex,
          station: selector.name,
          stationGroupId,
          nextStation: testCase.stops[stopIndex + 1]?.name,
          after: minutesToHhmm(currentMinute),
          choices,
        });
      }
      return {
        station: selector.name,
        stationGroupId,
        after: minutesToHhmm(currentMinute),
        choiceCount: choices.length,
        expectedRoutes: selector.routes || [],
        missingExpectedRoutes,
        boardableDepartureCount,
        skippedNonBoardableDepartureCount,
        candidateToNextCount,
        topChoices: choices.slice(0, 12),
      };
    }

    const anomalies = [];
    const results = [];
    const startedAtMs = performance.now();
    for (const testCase of cases) {
      const selectedStops = testCase.stops.map(selectStationGroup);
      const ambiguous = selectedStops
        .map((selection, index) => ({ selection, index }))
        .filter((item) => !item.selection.selected);
      if (ambiguous.length) {
        anomalies.push({
          kind: 'playability_station_disambiguation_failed',
          name: testCase.name,
          ambiguous: ambiguous.map((item) => item.selection),
        });
        results.push({ name: testCase.name, found: false, reason: 'station_disambiguation_failed' });
        continue;
      }

      let currentMinute = START_MINUTE;
      const legs = [];
      const waypointAudits = [];
      for (let index = 0; index < selectedStops.length - 1; index += 1) {
        const origin = selectedStops[index].selected.stationGroupId;
        const target = selectedStops[index + 1].selected.stationGroupId;
        waypointAudits.push(auditWaypointSurface(testCase, index, origin, selectedStops[index].selector, currentMinute, target));
        const leg = findLeg(origin, target, currentMinute);
        if (!leg) {
          anomalies.push({
            kind: 'long_distance_playability_leg_missing',
            name: testCase.name,
            from: selectedStops[index].selector,
            to: selectedStops[index + 1].selector,
            after: minutesToHhmm(currentMinute),
            originStationGroupId: origin,
            targetStationGroupId: target,
            originChoices: routeChoicesForGroup(origin, true),
          });
          break;
        }
        legs.push(leg);
        currentMinute = leg.arrivalMinute + MIN_TRANSFER_MINUTES;
      }

      const found = legs.length === selectedStops.length - 1;
      if (found) {
        const finalIndex = selectedStops.length - 1;
        waypointAudits.push(auditWaypointSurface(
          testCase,
          finalIndex,
          selectedStops[finalIndex].selected.stationGroupId,
          selectedStops[finalIndex].selector,
          legs.at(-1).arrivalMinute,
          null,
        ));
      }
      results.push({
        name: testCase.name,
        from: testCase.stops[0].name,
        to: testCase.stops.at(-1).name,
        via: testCase.stops.slice(1, -1).map((item) => item.name),
        found,
        arrival: found ? legs.at(-1).arrive : null,
        legCount: legs.length,
        transferCount: Math.max(0, legs.length - 1),
        legs,
        waypointAudits,
      });
    }
    const waypointAuditCount = results.reduce((sum, item) => sum + (item.waypointAudits?.length || 0), 0);
    return {
      checkedAt: new Date().toISOString(),
      caseCount: cases.length,
      passedCaseCount: results.filter((item) => item.found).length,
      waypointAuditCount,
      anomalyCount: anomalies.length,
      elapsedMs: Math.round(performance.now() - startedAtMs),
      results,
      anomalies,
    };
  }, LONG_DISTANCE_CASES);
}

(async () => {
  const args = parseArgs(process.argv);
  const { browser, page } = await loadPage(args['page-url']);
  try {
    const result = await auditLongDistancePlayability(page);
    console.log(JSON.stringify(result, null, 2));
    if (result.anomalyCount) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
