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
  if (args['fixed-count'] !== undefined) {
    args['fixed-count'] = Number.parseInt(args['fixed-count'], 10);
    if (!Number.isFinite(args['fixed-count']) || args['fixed-count'] < 0) {
      throw new Error('Invalid --fixed-count');
    }
  } else {
    args['fixed-count'] = null;
  }
  args['random-count'] = Number.parseInt(args['random-count'] || (args['case-file'] ? '0' : '100'), 10);
  if (!Number.isFinite(args['random-count']) || args['random-count'] < 0) {
    throw new Error('Invalid --random-count');
  }
  args.seed = Number.parseInt(args.seed || '20260501', 10);
  if (!Number.isFinite(args.seed)) throw new Error('Invalid --seed');
  return args;
}

function loadCaseFile(caseFile) {
  const cases = JSON.parse(fs.readFileSync(caseFile, 'utf8'));
  if (!Array.isArray(cases)) throw new Error('--case-file must contain a JSON array');
  for (const [index, testCase] of cases.entries()) {
    if (!testCase?.name || !Array.isArray(testCase.stops) || testCase.stops.length < 2) {
      throw new Error(`Invalid case at index ${index}`);
    }
    for (const [stopIndex, stop] of testCase.stops.entries()) {
      if (!stop?.name || (stop.routes !== undefined && !Array.isArray(stop.routes))) {
        throw new Error(`Invalid stop at case ${index}, stop ${stopIndex}`);
      }
    }
  }
  return cases;
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

async function auditLongDistancePlayability(page, options) {
  return page.evaluate(({ fixedCases: handFixedCases, fixedCount, randomCount, seed, strictExpectedRoutes }) => {
    const START_MINUTE = hhmmToMinutes('06:00');
    const END_MINUTE = hhmmToMinutes('30:00');
    const MIN_TRANSFER_MINUTES = 2;
    const MIN_RANDOM_DISTANCE_METERS = 80_000;
    const fixedGeneratedCount = Math.max(0, fixedCount - handFixedCases.length);
    const MAX_RANDOM_ATTEMPTS = Math.max(100, (fixedGeneratedCount + randomCount) * 70);
    const MAX_CHAIN_LEGS = 4;
    const MAX_RANDOM_DEPARTURES = 140;
    const NOVELTY_CANDIDATES_PER_CASE = 8;

    function seededRandom(initialSeed) {
      let value = initialSeed >>> 0;
      return () => {
        value = (value * 1664525 + 1013904223) >>> 0;
        return value / 0x100000000;
      };
    }

    const random = seededRandom(seed);

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

    function normalizeRouteTitleForChallenge(value) {
      return String(value || '').replace(/[\s　]+/g, '');
    }

    function routeTitleMatchesExpected(actualTitle, expectedTitle) {
      const actual = normalizeRouteTitleForChallenge(actualTitle);
      const expected = normalizeRouteTitleForChallenge(expectedTitle);
      return actual === expected || actual.includes(expected) || expected.includes(actual);
    }

    function selectStationGroup(selector) {
      if (selector.stationGroupId) {
        const group = state.stationGroupById.get(selector.stationGroupId);
        const routes = group ? routeChoicesForGroup(selector.stationGroupId, false) : [];
        return {
          selector,
          candidates: group ? [{ stationGroupId: selector.stationGroupId, routes }] : [],
          selected: group ? { stationGroupId: selector.stationGroupId, routes } : null,
          selectedCount: group ? 1 : 0,
        };
      }
      const candidates = groupIdsByDisplayName(selector.name)
        .map((stationGroupId) => ({
          stationGroupId,
          routes: routeChoicesForGroup(stationGroupId, false),
        }));
      const matching = selector.routes?.length
        ? candidates.filter((candidate) => selector.routes.every((routeName) =>
          candidate.routes.some((candidateRoute) => routeTitleMatchesExpected(candidateRoute, routeName))
        ))
        : candidates;
      const selected = matching.length === 1 ? matching[0] : (candidates.length === 1 ? candidates[0] : null);
      return {
        selector,
        candidates,
        selected,
        selectedCount: selected ? 1 : matching.length,
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

    function groupCoordinate(stationGroupId) {
      return stationGroupCoordinate(stationGroupId);
    }

    function stationHasRawBoardableService(stationGroupId) {
      for (const trip of state.stationTripsByGroupId.get(stationGroupId) || []) {
        for (const stop of trip.stopTimes || []) {
          if (stop.stationGroupId !== stationGroupId) continue;
          const departureMinute = stopDepartureMinutes(stop);
          if (departureMinute >= START_MINUTE && departureMinute <= END_MINUTE && hasDownstreamStop(trip, stop)) {
            return true;
          }
        }
      }
      return false;
    }

    function randomStationPool() {
      return [...state.stationGroupById.keys()]
        .map((stationGroupId) => {
          const coordinate = groupCoordinate(stationGroupId);
          return {
            stationGroupId,
            name: displayNameForGroup(stationGroupId),
            coordinate,
          };
        })
        .filter((item) => item.name && item.coordinate && stationHasRawBoardableService(item.stationGroupId));
    }

    function randomItem(items) {
      return items[Math.floor(random() * items.length)];
    }

    function randomDepartureCandidates(stationGroupId, currentMinute) {
      return departuresForStationGroup(stationGroupId, currentMinute, {
        includeTransferEquivalents: true,
      })
        .slice(0, MAX_RANDOM_DEPARTURES)
        .filter((departure) => routeNamesForEntry(departure).length && hasDownstreamStop(departure.trip, departure.stop));
    }

    function downstreamCandidates(departure) {
      const stops = (departure.trip.stopTimes || [])
        .filter((stop) => stop.sequence > departure.stop.sequence)
        .map((stop) => ({
          stop,
          arrivalMinute: Math.ceil((stop.arrivalTimeSec ?? stop.departureTimeSec ?? 0) / 60),
          coordinate: groupCoordinate(stop.stationGroupId),
        }))
        .filter((item) => Number.isFinite(item.arrivalMinute) && item.arrivalMinute <= END_MINUTE && item.coordinate);
      if (stops.length <= 2) return stops;
      return stops.slice(Math.floor(stops.length * 0.35));
    }

    function planRandomChain(origin, usedStationGroupIds, usedRouteNames) {
      const targetLegCount = 1 + Math.floor(random() * MAX_CHAIN_LEGS);
      let currentStationGroupId = origin.stationGroupId;
      let currentMinute = START_MINUTE;
      const legs = [];
      const visited = new Set([currentStationGroupId]);
      for (let legIndex = 0; legIndex < targetLegCount; legIndex += 1) {
        const departures = randomDepartureCandidates(currentStationGroupId, currentMinute);
        if (!departures.length) break;
        const departure = randomItem(departures);
        const downstream = downstreamCandidates(departure)
          .filter((item) => !visited.has(item.stop.stationGroupId));
        if (!downstream.length) break;
        const chosen = randomItem(downstream);
        const routeNames = routeNamesForEntry(departure);
        legs.push({
          route: routeNames[0],
          train: formatTripLabel(departure.trip),
          tripId: departure.trip.id,
          from: displayNameForGroup(departure.stop.stationGroupId),
          to: displayNameForGroup(chosen.stop.stationGroupId),
          fromStationGroupId: currentStationGroupId,
          boardStationGroupId: departure.stop.stationGroupId,
          toStationGroupId: chosen.stop.stationGroupId,
          depart: minutesToHhmm(departure.departureMinute),
          arrive: minutesToHhmm(chosen.arrivalMinute),
          departureMinute: departure.departureMinute,
          arrivalMinute: chosen.arrivalMinute,
        });
        currentStationGroupId = chosen.stop.stationGroupId;
        currentMinute = chosen.arrivalMinute + MIN_TRANSFER_MINUTES;
        visited.add(currentStationGroupId);
        const distanceMeters = coordinateDistanceMeters(origin.coordinate, chosen.coordinate);
        if (distanceMeters >= MIN_RANDOM_DISTANCE_METERS && legs.length >= 2 && random() < 0.45) break;
      }
      return {
        found: Boolean(legs.length),
        reachedGroupId: currentStationGroupId,
        arrivalMinute: legs.at(-1)?.arrivalMinute || null,
        expansionCount: legs.length,
        noveltyScore: scorePlanNovelty(origin, currentStationGroupId, legs, usedStationGroupIds, usedRouteNames),
        legs,
      };
    }

    function scorePlanNovelty(origin, targetStationGroupId, legs, usedStationGroupIds, usedRouteNames) {
      const stationIds = new Set([origin.stationGroupId, targetStationGroupId]);
      const routeNames = new Set();
      for (const leg of legs) {
        stationIds.add(leg.fromStationGroupId);
        stationIds.add(leg.boardStationGroupId);
        stationIds.add(leg.toStationGroupId);
        if (leg.route) routeNames.add(leg.route);
      }
      const newStationCount = [...stationIds].filter((stationGroupId) => !usedStationGroupIds.has(stationGroupId)).length;
      const newRouteCount = [...routeNames].filter((routeName) => !usedRouteNames.has(routeName)).length;
      return (newRouteCount * 100) + (newStationCount * 12) + (legs.length * 2);
    }

    function addCaseUsage(testCase, usedStationGroupIds, usedRouteNames) {
      for (const stop of testCase.stops || []) {
        if (stop.stationGroupId) usedStationGroupIds.add(stop.stationGroupId);
        for (const routeName of stop.routes || []) usedRouteNames.add(routeName);
      }
      for (const leg of testCase.plannedLegs || []) {
        if (leg.fromStationGroupId) usedStationGroupIds.add(leg.fromStationGroupId);
        if (leg.boardStationGroupId) usedStationGroupIds.add(leg.boardStationGroupId);
        if (leg.toStationGroupId) usedStationGroupIds.add(leg.toStationGroupId);
        if (leg.route) usedRouteNames.add(leg.route);
      }
    }

    function seedUsageFromHandFixedCases(usedStationGroupIds, usedRouteNames) {
      for (const testCase of handFixedCases) {
        for (const stop of testCase.stops || []) {
          for (const stationGroupId of groupIdsByDisplayName(stop.name)) {
            usedStationGroupIds.add(stationGroupId);
          }
          for (const routeName of stop.routes || []) usedRouteNames.add(routeName);
        }
      }
    }

    function caseFromPlan(index, origin, target, plan, prefix, generatedKind) {
      const stops = [];
      for (let legIndex = 0; legIndex < plan.legs.length; legIndex += 1) {
        const leg = plan.legs[legIndex];
        if (legIndex === 0) {
          stops.push({
            name: displayNameForGroup(leg.fromStationGroupId),
            stationGroupId: leg.fromStationGroupId,
            routes: [leg.route],
          });
        }
        const nextLeg = plan.legs[legIndex + 1];
        stops.push({
          name: displayNameForGroup(leg.toStationGroupId),
          stationGroupId: leg.toStationGroupId,
          routes: nextLeg ? [nextLeg.route] : [],
        });
      }
      return {
        name: `${prefix}_${index}_${origin.name}_to_${target.name}`,
        generated: true,
        generatedKind,
        plannedArrival: minutesToHhmm(plan.arrivalMinute),
        plannedLegCount: plan.legs.length,
        planExpansionCount: plan.expansionCount,
        noveltyScore: plan.noveltyScore,
        distanceKm: Math.round(coordinateDistanceMeters(origin.coordinate, target.coordinate) / 1000),
        stops,
        plannedLegs: plan.legs,
      };
    }

    function generateNoveltyCases(count, usedStationGroupIds, usedRouteNames, prefix, generatedKind) {
      if (!count) return [];
      const pool = randomStationPool();
      const cases = [];
      const seenPairs = new Set();
      let attemptCount = 0;
      while (cases.length < count && attemptCount < MAX_RANDOM_ATTEMPTS) {
        attemptCount += 1;
        let bestCandidate = null;
        for (let candidateIndex = 0; candidateIndex < NOVELTY_CANDIDATES_PER_CASE; candidateIndex += 1) {
          const origin = randomItem(pool);
          if (!origin) continue;
          const plan = planRandomChain(origin, usedStationGroupIds, usedRouteNames);
          if (!plan.found || !plan.legs.length || plan.legs.length > MAX_CHAIN_LEGS) continue;
          const targetCoordinate = groupCoordinate(plan.reachedGroupId);
          const target = {
            stationGroupId: plan.reachedGroupId,
            name: displayNameForGroup(plan.reachedGroupId),
            coordinate: targetCoordinate,
          };
          if (!target.coordinate || origin.stationGroupId === target.stationGroupId) continue;
          const pairKey = `${origin.stationGroupId}->${target.stationGroupId}`;
          if (seenPairs.has(pairKey)) continue;
          const distanceMeters = coordinateDistanceMeters(origin.coordinate, target.coordinate);
          if (!Number.isFinite(distanceMeters) || distanceMeters < MIN_RANDOM_DISTANCE_METERS) continue;
          const distanceScore = Math.min(300, Math.round(distanceMeters / 10_000));
          const score = plan.noveltyScore + distanceScore + plan.legs.length;
          if (!bestCandidate || score > bestCandidate.score) {
            bestCandidate = { origin, target, plan, pairKey, score };
          }
        }
        if (!bestCandidate) continue;
        seenPairs.add(bestCandidate.pairKey);
        const testCase = caseFromPlan(
          cases.length + 1,
          bestCandidate.origin,
          bestCandidate.target,
          bestCandidate.plan,
          prefix,
          generatedKind,
        );
        cases.push(testCase);
        addCaseUsage(testCase, usedStationGroupIds, usedRouteNames);
      }
      return cases;
    }

    function auditWaypointSurface(testCase, stopIndex, stationGroupId, selector, currentMinute, nextTargetGroupId) {
      const choices = routeChoiceSummariesForGroup(stationGroupId, true, currentMinute);
      const choiceTitles = choices.map((choice) => choice.route);
      const missingExpectedRoutes = (selector.routes || []).filter((routeName) =>
        !choiceTitles.some((choiceTitle) => routeTitleMatchesExpected(choiceTitle, routeName))
      );
      if (strictExpectedRoutes && nextTargetGroupId && missingExpectedRoutes.length) {
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
      if (nextTargetGroupId && !boardableDepartureCount) {
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
    const usedStationGroupIds = new Set();
    const usedRouteNames = new Set();
    seedUsageFromHandFixedCases(usedStationGroupIds, usedRouteNames);
    const coverageCases = generateNoveltyCases(
      fixedGeneratedCount,
      usedStationGroupIds,
      usedRouteNames,
      'coverage',
      'fixed_coverage',
    );
    const fixedCases = [...handFixedCases, ...coverageCases];
    const randomCases = generateNoveltyCases(
      randomCount,
      usedStationGroupIds,
      usedRouteNames,
      'random',
      'random',
    );
    const cases = [...fixedCases, ...randomCases];
    if (fixedCases.length !== fixedCount || randomCases.length !== randomCount) {
      anomalies.push({
        kind: 'long_distance_generated_case_shortfall',
        requestedFixedCaseCount: fixedCount,
        fixedCaseCount: fixedCases.length,
        requestedRandomCaseCount: randomCount,
        randomCaseCount: randomCases.length,
      });
    }
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
        generated: Boolean(testCase.generated),
        generatedKind: testCase.generatedKind || null,
        from: testCase.stops[0].name,
        to: testCase.stops.at(-1).name,
        via: testCase.stops.slice(1, -1).map((item) => item.name),
        plannedArrival: testCase.plannedArrival || null,
        plannedLegCount: testCase.plannedLegCount || null,
        noveltyScore: testCase.noveltyScore || null,
        distanceKm: testCase.distanceKm || null,
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
      handFixedCaseCount: handFixedCases.length,
      coverageCaseCount: coverageCases.length,
      fixedCaseCount: fixedCases.length,
      requestedFixedCaseCount: fixedCount,
      randomCaseCount: randomCases.length,
      requestedRandomCaseCount: randomCount,
      seed,
      strictExpectedRoutes,
      passedCaseCount: results.filter((item) => item.found).length,
      waypointAuditCount,
      anomalyCount: anomalies.length,
      elapsedMs: Math.round(performance.now() - startedAtMs),
      results,
      anomalies,
    };
  }, {
    fixedCases: options.fixedCases,
    fixedCount: options.fixedCount,
    randomCount: options.randomCount,
    seed: options.seed,
    strictExpectedRoutes: options.strictExpectedRoutes,
  });
}

(async () => {
  const args = parseArgs(process.argv);
  const fixedCases = args['case-file'] ? loadCaseFile(args['case-file']) : LONG_DISTANCE_CASES;
  const fixedCount = args['fixed-count'] ?? (args['case-file'] ? fixedCases.length : 100);
  if (fixedCount < fixedCases.length) {
    throw new Error(`Invalid --fixed-count; must be at least ${fixedCases.length}`);
  }
  const { browser, page } = await loadPage(args['page-url']);
  try {
    const result = await auditLongDistancePlayability(page, {
      fixedCases,
      fixedCount,
      randomCount: args['random-count'],
      seed: args.seed,
      strictExpectedRoutes: !args['case-file'],
    });
    const json = JSON.stringify(result, null, 2);
    console.log(json);
    if (args.output && args.output !== true) fs.writeFileSync(args.output, `${json}\n`);
    if (result.anomalyCount) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
