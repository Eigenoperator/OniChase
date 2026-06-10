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

const DEFAULT_STAGES = ['global', 'duplicates', 'known', 'mini-shinkansen', 'focused'];

function parseArgs(argv) {
  const args = {};
  for (let index = 2; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith('--')) continue;
    const next = argv[index + 1];
    if (next === undefined || next.startsWith('--')) {
      args[key.slice(2)] = true;
      continue;
    }
    args[key.slice(2)] = next;
    index += 1;
  }
  if (!args['page-url']) throw new Error('Missing --page-url');
  return args;
}

function parseIntegerOption(value, defaultValue = null) {
  if (value === undefined || value === null || value === '') return defaultValue;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : defaultValue;
}

function parseStagesOption(value) {
  if (value === undefined || value === null || value === '' || value === true || value === 'all') {
    return DEFAULT_STAGES;
  }
  if (value === 'none') return [];
  const knownStages = new Set(DEFAULT_STAGES);
  const stages = String(value)
    .split(',')
    .map((stage) => stage.trim())
    .filter(Boolean);
  const unknownStages = stages.filter((stage) => !knownStages.has(stage));
  if (unknownStages.length) throw new Error(`Unknown --stages value(s): ${unknownStages.join(', ')}`);
  return [...new Set(stages)];
}

async function loadPage(pageUrl) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const startedAt = Date.now();
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
  const domContentLoadedAt = Date.now();
  await page.waitForFunction(() => typeof state !== 'undefined' && Boolean(state.bundle), null, { timeout: 90000 });
  const mapBundleReadyAt = Date.now();
  await page.evaluate(() => ensureTimetableLoaded());
  await page.waitForFunction(() => state.timetableStatus === 'ready', null, { timeout: 90000 });
  const timetableReadyAt = Date.now();
  return {
    browser,
    page,
    loadTimings: {
      domContentLoadedMs: domContentLoadedAt - startedAt,
      mapBundleReadyMs: mapBundleReadyAt - startedAt,
      timetableReadyMs: timetableReadyAt - startedAt,
      timetableLoadMs: timetableReadyAt - mapBundleReadyAt,
    },
  };
}

async function auditRouteChoices(page, auditOptions) {
  return page.evaluate((auditOptions) => {
    const START_MINUTE = hhmmToMinutes('06:00');
    const tripStart = Math.max(0, Number(auditOptions.tripStart || 0));
    const hasTripLimit = auditOptions.tripLimit !== null && auditOptions.tripLimit !== undefined;
    const tripLimit = hasTripLimit && Number.isFinite(Number(auditOptions.tripLimit))
      ? Math.max(0, Number(auditOptions.tripLimit))
      : null;
    const stationStart = Math.max(0, Number(auditOptions.stationStart || 0));
    const hasStationLimit = auditOptions.stationLimit !== null && auditOptions.stationLimit !== undefined;
    const stationLimit = hasStationLimit && Number.isFinite(Number(auditOptions.stationLimit))
      ? Math.max(0, Number(auditOptions.stationLimit))
      : null;
    const enabledStages = new Set(Array.isArray(auditOptions.stages) ? auditOptions.stages : ['global', 'duplicates', 'known', 'focused']);
    const stageEnabled = (stageName) => enabledStages.has(stageName);
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

    function stationIdByNameAndPrefecture(stationName, prefectureName) {
      return [...state.stationGroupById.entries()]
        .find(([, group]) =>
          (group.names?.ja || group.primaryName) === stationName &&
          (!prefectureName || (group.tags?.prefectureNamesJa || []).includes(prefectureName))
        )?.[0] || null;
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
        queryStationGroupId: entry.queryStationGroupId,
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
      return routeChoicesFromDepartures(departuresForStationGroup(stationGroupId, START_MINUTE, { includeTransferEquivalents: true }))
        .map((choice) => ({
          route: routeTitle(choice.routeId),
          firstDeparture: choice.firstDepartureHhmm,
          trainCount: choice.trainCount,
        }));
    }

    function entriesAt(stationName) {
      const stationGroupId = firstStationIdByName(stationName);
      if (!stationGroupId) return [];
      return departuresForStationGroup(stationGroupId, START_MINUTE, { includeTransferEquivalents: true });
    }

    function allEntriesAt(stationName) {
      const seen = new Set();
      const entries = [];
      stationIdsByName(stationName).forEach((stationGroupId) => {
        departuresForStationGroup(stationGroupId, START_MINUTE, { includeTransferEquivalents: true }).forEach((entry) => {
          const key = `${entry.trip?.id || ''}|${entry.stop?.sequence || ''}|${entry.departureMinute || ''}`;
          if (seen.has(key)) return;
          seen.add(key);
          entries.push(entry);
        });
      });
      return entries;
    }

    const anomalies = [];
    const timings = { startedAtMs: performance.now() };
    const allTrips = [...state.tripById.values()];
    const selectedTrips = tripLimit === null
      ? allTrips.slice(tripStart)
      : allTrips.slice(tripStart, tripStart + tripLimit);
    const routeTitleCache = new Map();
    function titleForRoute(routeId) {
      const key = routeId || '';
      if (!routeTitleCache.has(key)) routeTitleCache.set(key, routeTitle(routeId));
      return routeTitleCache.get(key);
    }
    const stationNameCache = new Map();
    function stationNameForGroupId(stationGroupId) {
      const key = stationGroupId || '';
      if (!stationNameCache.has(key)) {
        const group = state.stationGroupById.get(stationGroupId);
        stationNameCache.set(key, group?.names?.ja || group?.primaryName || stationGroupId || '');
      }
      return stationNameCache.get(key);
    }
    const directionTraceRouteCountCache = new Map();
    function directionTraceRouteCountForTrip(trip) {
      const key = trip?.id || '';
      if (!directionTraceRouteCountCache.has(key)) {
        directionTraceRouteCountCache.set(key, new Set((trip?.lineTrace || [])
          .map((trace) => trace?.routeId)
          .filter((candidateRouteId) =>
            candidateRouteId &&
            state.routeById.has(candidateRouteId) &&
            !isThroughServiceTransferAlias(candidateRouteId)
          )).size);
      }
      return directionTraceRouteCountCache.get(key);
    }
    function nextStopAfterIndex(stops, index) {
      const currentSequence = stops[index]?.sequence;
      if (!Number.isFinite(currentSequence)) return null;
      for (let nextIndex = index + 1; nextIndex < stops.length; nextIndex += 1) {
        if (stops[nextIndex]?.sequence > currentSequence) return stops[nextIndex];
      }
      return null;
    }
    const allowedVirtualRouteStations = {
      VIRTUAL_JR_EAST_UENO_TOKYO: new Set(['東京', '上野']),
      VIRTUAL_JR_EAST_SHONAN_SHINJUKU: new Set([
        '大宮', '浦和', '赤羽', '池袋', '新宿', '渋谷', '恵比寿', '大崎',
        '西大井', '武蔵小杉', '新川崎', '横浜', '保土ケ谷', '保土ヶ谷',
        '東戸塚', '戸塚', '大船',
      ]),
      VIRTUAL_JR_EAST_YOKOSUKA_SOBU_RAPID: new Set([
        '久里浜', '衣笠', '横須賀', '田浦', '東逗子', '逗子', '鎌倉', '北鎌倉',
        '大船', '戸塚', '東戸塚', '保土ヶ谷', '横浜', '新川崎', '武蔵小杉',
        '西大井', '品川', '新橋', '東京', '新日本橋', '馬喰町', '錦糸町',
        '新小岩', '市川', '船橋', '津田沼', '稲毛', '千葉',
      ]),
      VIRTUAL_JR_EAST_CHUO_RAPID: new Set([
        '東京', '神田', '御茶ノ水', '四ツ谷', '新宿', '中野', '高円寺', '阿佐ケ谷',
        '荻窪', '西荻窪', '吉祥寺', '三鷹', '武蔵境', '東小金井', '武蔵小金井',
        '国分寺', '西国分寺', '国立', '立川', '日野', '豊田', '八王子',
        '西八王子', '高尾', '大月',
      ]),
      VIRTUAL_JR_EAST_CHUO_SOBU_LOCAL: new Set([
        '三鷹', '吉祥寺', '西荻窪', '荻窪', '阿佐ケ谷', '高円寺', '中野',
        '東中野', '大久保', '新宿', '代々木', '千駄ケ谷', '信濃町', '四ツ谷',
        '市ケ谷', '飯田橋', '水道橋', '御茶ノ水', '秋葉原', '浅草橋', '両国',
        '錦糸町', '亀戸', '平井', '新小岩', '小岩', '市川', '本八幡',
        '下総中山', '西船橋', '船橋', '東船橋', '津田沼', '幕張本郷', '幕張',
        '新検見川', '稲毛', '西千葉', '千葉',
      ]),
      VIRTUAL_JR_EAST_KEIHIN_TOHOKU_NEGISHI: new Set([
        '大宮', 'さいたま新都心', '与野', '北浦和', '浦和', '南浦和', '蕨',
        '西川口', '川口', '赤羽', '東十条', '王子', '上中里', '田端',
        '西日暮里', '日暮里', '鶯谷', '上野', '御徒町', '秋葉原', '神田',
        '東京', '有楽町', '新橋', '浜松町', '田町', '高輪ゲートウェイ',
        '品川', '大井町', '大森', '蒲田', '川崎', '鶴見', '新子安',
        '東神奈川', '横浜', '桜木町', '関内', '石川町', '山手', '根岸',
        '磯子', '新杉田', '洋光台', '港南台', '本郷台', '大船',
      ]),
      VIRTUAL_MAIBARA_TOKAIDO_BOUNDARY: new Set(['米原']),
    };
    const globalChoiceScan = {
      checkedRows: 0,
      checkedChoices: 0,
      segmentMismatchCount: 0,
      virtualOutsideAllowedStationCount: 0,
      genericRouteLabelCount: 0,
      yokohamaThroughRemoteRouteCount: 0,
      routeLikeNamedChoiceCount: 0,
      nonKeikyuAirportLineKkSymbolCount: 0,
      choiceTraceMismatchCount: 0,
      currentPhysicalMismatchCount: 0,
      highlightTraceMismatchCount: 0,
      samples: [],
    };
    const globalTrainLabelScan = {
      checkedLabels: 0,
      rawNumberedLineLabelCount: 0,
      limitedOrShinkansenMissingNumberCount: 0,
      throughDirectionLabelMismatchCount: 0,
      meitetsuLabelFormatMismatchCount: 0,
      namedLimitedExpressNotSeparatedCount: 0,
      limitedExpressGoSuffixCount: 0,
      asakusaKeikyuAirportLabelMismatchCount: 0,
      checkedThroughPreviewTexts: 0,
      throughDisplayTextCount: 0,
      samples: [],
    };
    const duplicateRouteTitleScan = {
      checkedStations: 0,
      duplicateStationTitleCount: 0,
      samples: [],
    };
    const miniShinkansenBranchScan = {
      checkedStations: 0,
      checkedShinkansenEntries: 0,
      checkedOrdinaryEntries: 0,
      missingRouteCount: 0,
      ordinaryLineLeakCount: 0,
      nonShinkansenEntryCount: 0,
      specialExpressLabelLeakCount: 0,
      mergedRouteChoiceCount: 0,
      samples: [],
      skipped: !stageEnabled('mini-shinkansen'),
    };
    const allUenoTokyoChoiceStationSet = new Set();
    const forbiddenTokyoNorthTrunkChoices = new Set(['東北線', '東北本線', '宇都宮線', '高崎線', '常磐線']);
    function addGlobalChoiceSample(kind, stationName, entry, routeId, nextStop) {
      if (globalChoiceScan.samples.length >= 80) return;
      globalChoiceScan.samples.push({
        kind,
        station: stationName,
        route: routeTitle(routeId),
        departure: minutesToHhmm(entry.departureMinute),
        nextStation: displayNameForGroup(nextStop.stationGroupId),
        terminal: displayNameForGroup((entry.trip?.stopTimes || []).at(-1)?.stationGroupId || ''),
        tripRoute: routeTitle(entry.trip?.routeId || ''),
        tripId: entry.trip?.id || '',
      });
    }
    function addGlobalTrainLabelSample(kind, stationName, entry, routeId, label) {
      if (globalTrainLabelScan.samples.length >= 80) return;
      globalTrainLabelScan.samples.push({
        kind,
        station: stationName,
        selectedRoute: routeTitle(routeId),
        label,
        departure: minutesToHhmm(entry.departureMinute),
        serviceName: entry.trip?.serviceName || '',
        serviceNumber: publicTripNumber(entry.trip),
        tripRoute: routeTitle(entry.trip?.routeId || ''),
        tripId: entry.trip?.id || '',
      });
    }
    function allowedPassengerRouteOverPhysicalTrace(stationName, entry, routeId, currentSegmentRouteId, nextStop) {
      const route = routeTitle(routeId);
      const segmentRoute = routeTitle(currentSegmentRouteId);
      const nextStation = displayNameForGroup(nextStop?.stationGroupId || '');
      if (
        stationName === '東京' &&
        nextStation === '新橋' &&
        route === '東海道線' &&
        ['東北線', '東北本線'].includes(segmentRoute)
      ) {
        return true;
      }
      if (
        ['成田', '酒々井', '佐倉'].includes(stationName) &&
        ['成田', '酒々井', '佐倉'].includes(nextStation) &&
        route === '成田線' &&
        segmentRoute === '総武線'
      ) {
        return true;
      }
      if (
        ['成田空港', '空港第２ビル', '成田湯川', '印旛日本医大'].includes(stationName) &&
        ['成田空港', '空港第２ビル', '成田湯川', '印旛日本医大'].includes(nextStation) &&
        route === '京成成田空港線' &&
        segmentRoute === '北総鉄道北総線'
      ) {
        return true;
      }
      if (
        ['鳥取', '郡家', '智頭'].includes(stationName) &&
        ['鳥取', '郡家', '智頭'].includes(nextStation) &&
        route === '因美線' &&
        ['智頭急行智頭線', '山陽線'].includes(segmentRoute)
      ) {
        return true;
      }
      if (
        route === '埼京線' &&
        [
          '大崎', '恵比寿', '渋谷', '新宿', '池袋', '板橋', '十条', '赤羽',
          '北赤羽', '浮間舟渡', '戸田公園', '戸田', '北戸田', '武蔵浦和',
          '中浦和', '南与野', '与野本町', '北与野', '大宮', '日進',
          '西大宮', '指扇', '南古谷', '川越',
        ].includes(stationName) &&
        [
          '大崎', '恵比寿', '渋谷', '新宿', '池袋', '板橋', '十条', '赤羽',
          '北赤羽', '浮間舟渡', '戸田公園', '戸田', '北戸田', '武蔵浦和',
          '中浦和', '南与野', '与野本町', '北与野', '大宮', '日進',
          '西大宮', '指扇', '南古谷', '川越',
        ].includes(nextStation) &&
        ['埼京線', '山手線', '赤羽線', '東北線', '東北本線', '川越線', '東海道線', '相鉄本線', '相鉄新横浜線'].includes(segmentRoute)
      ) {
        return true;
      }
      if (
        stationName === '上野' &&
        nextStation === '日暮里' &&
        route === '常磐線'
      ) {
        return true;
      }
      if (
        route.includes('新幹線') &&
        !segmentRoute.includes('新幹線') &&
        routePatternServesPlannerBoardingStation(routeId, entry?.stop?.stationGroupId) &&
        routePatternServesPlannerBoardingStation(routeId, nextStop?.stationGroupId)
      ) {
        return true;
      }
      return stationName === '上野' &&
        nextStation === '日暮里' &&
        route === '常磐線' &&
        ['東北線', '東北本線'].includes(segmentRoute);
    }
    const futureTraceRouteIdCache = new Map();
    const currentPhysicalRouteIdCache = new Map();
    function tripSequenceCacheKey(trip, sequence) {
      return `${trip?.id || ''}::${sequence}`;
    }
    function currentTraceForEntry(entry, nextStop) {
      const currentSequence = entry?.stop?.sequence;
      const nextSequence = nextStop?.sequence;
      if (!Number.isFinite(currentSequence) || !Number.isFinite(nextSequence)) return null;
      const exact = (entry.trip?.lineTrace || []).find((trace) =>
        trace?.routeId &&
        state.routeById.has(trace.routeId) &&
        currentSequence >= trace.fromSequence &&
        nextSequence <= trace.toSequence
      );
      if (exact) return exact;
      return (entry.trip?.lineTrace || []).find((trace) =>
        trace?.routeId &&
        state.routeById.has(trace.routeId) &&
        currentSequence >= trace.fromSequence &&
        currentSequence < trace.toSequence
      ) || null;
    }
    function futureTraceRouteIdsForEntry(entry, currentSegmentRouteId) {
      const key = tripSequenceCacheKey(entry.trip, entry.stop.sequence);
      if (!futureTraceRouteIdCache.has(key)) {
        const routeIds = new Set((entry.trip?.lineTrace || [])
          .filter((trace) => trace?.routeId && state.routeById.has(trace.routeId) && trace.toSequence >= entry.stop.sequence)
          .map((trace) => typeof reviewedTraceRouteIdForRange === 'function' ? reviewedTraceRouteIdForRange(entry.trip, trace) : trace.routeId)
          .filter((candidateRouteId) => candidateRouteId && state.routeById.has(candidateRouteId)));
        if (entry.trip?.routeId) routeIds.add(entry.trip.routeId);
        futureTraceRouteIdCache.set(key, routeIds);
      }
      const routeIds = new Set(futureTraceRouteIdCache.get(key));
      if (currentSegmentRouteId) routeIds.add(currentSegmentRouteId);
      return routeIds;
    }
    function currentPhysicalRouteIdsForEntry(entry, currentSegmentRouteId, nextStop) {
      const key = tripSequenceCacheKey(entry.trip, entry.stop.sequence);
      if (!currentPhysicalRouteIdCache.has(key)) {
        const reviewedSegments = nextStop
          ? reviewedTripPathSegmentsForStopPair(entry.trip, entry.stop, nextStop)
          : [];
        const trace = currentTraceForEntry(entry, nextStop);
        const reviewedTraceRouteId = trace && typeof reviewedTraceRouteIdForRange === 'function'
          ? reviewedTraceRouteIdForRange(entry.trip, trace)
          : currentSegmentRouteId;
        const fallbackRouteId = reviewedTraceRouteId || currentSegmentRouteId;
        const routeIds = reviewedSegments?.length
          ? [reviewedSegments[0].routeId]
          : [fallbackRouteId];
        currentPhysicalRouteIdCache.set(key, new Set(routeIds
          .filter((candidateRouteId) =>
            candidateRouteId &&
            state.routeById.has(candidateRouteId) &&
            !isThroughServiceTransferAlias(candidateRouteId)
          )));
      }
      return currentPhysicalRouteIdCache.get(key);
    }
    function routeIdSetHasRouteOrTitle(routeIds, routeId) {
      if (!routeId) return false;
      if (routeIds.has(routeId)) return true;
      const title = routeTitle(routeId);
      return Boolean(title && [...routeIds].some((candidateRouteId) => routeTitle(candidateRouteId) === title));
    }
    Object.assign(globalChoiceScan, {
      tripStart,
      tripLimit,
      tripCount: allTrips.length,
      selectedTripCount: selectedTrips.length,
      skipped: !stageEnabled('global'),
    });
    Object.assign(globalTrainLabelScan, {
      tripStart,
      tripLimit,
      tripCount: allTrips.length,
      selectedTripCount: selectedTrips.length,
      skipped: !stageEnabled('global'),
    });
    if (stageEnabled('global')) {
      for (const trip of selectedTrips) {
        const stops = trip.stopTimes || [];
        for (let index = 0; index < stops.length - 1; index += 1) {
          const stop = stops[index];
          if (!Number.isFinite(stop?.sequence)) continue;
          const nextStop = nextStopAfterIndex(stops, index);
          if (!nextStop) continue;
          const departureMinute = stopDepartureMinutes(stop);
          if (departureMinute < START_MINUTE) continue;
          const stationGroupId = stop.stationGroupId;
          const stationName = stationNameForGroupId(stationGroupId);
          const entry = {
            trip,
            stop,
            boardStop: stop,
            departureMinute,
            routeIds: boardableRouteIdsForStop(trip, stop),
            queryStationGroupId: stationGroupId,
          };
          globalChoiceScan.checkedRows += 1;
          const routeIds = routeChoiceIdsForDeparture(entry);
          globalChoiceScan.checkedChoices += routeIds.length;
          const currentSegmentRouteId = tracedRouteIdForTripSegment(trip, stop, nextStop);
          const futureTraceRouteIds = futureTraceRouteIdsForEntry(entry, currentSegmentRouteId);
          const currentPhysicalRouteIds = currentPhysicalRouteIdsForEntry(entry, currentSegmentRouteId, nextStop);
          routeIds.forEach((routeId) => {
            const label = formatTripLabelForBoarding(entry, routeId);
            const choiceRouteTitle = titleForRoute(routeId);
            globalTrainLabelScan.checkedLabels += 1;
            if (choiceRouteTitle === '上野東京ライン') {
              allUenoTokyoChoiceStationSet.add(stationName);
            }
            const namedTrainRouteId = namedTrainChoiceRouteId(trip);
            if (namedTrainRouteId && routeId !== namedTrainRouteId) {
              globalTrainLabelScan.namedLimitedExpressNotSeparatedCount += 1;
              addGlobalTrainLabelSample('named_limited_express_not_separated', stationName, entry, routeId, label);
            }
            if (choiceRouteTitle === '路線') {
              globalChoiceScan.genericRouteLabelCount += 1;
              addGlobalChoiceSample('generic_route_label', stationName, entry, routeId, nextStop);
            }
            const choiceRoute = state.routeById.get(routeId);
            const rawChoiceLineName = String(choiceRoute?.shortName || choiceRoute?.tags?.lineName || '');
            if (
              (choiceRouteTitle.includes('空港線') || rawChoiceLineName.includes('空港線')) &&
              choiceRoute?.operatorId !== 'keikyu' &&
              routeSymbolCode(routeId) === 'KK'
            ) {
              globalChoiceScan.nonKeikyuAirportLineKkSymbolCount += 1;
              addGlobalChoiceSample('non_keikyu_airport_line_kk_symbol', stationName, entry, routeId, nextStop);
            }
            if (
              stationName === '横浜' &&
              ['東京メトロ副都心線', '東京メトロ有楽町線', '京急本線'].includes(choiceRouteTitle) &&
              ['13号線副都心線', '8号線有楽町線'].includes(trip?.serviceName || '')
            ) {
              globalChoiceScan.yokohamaThroughRemoteRouteCount += 1;
              addGlobalChoiceSample('yokohama_through_remote_route', stationName, entry, routeId, nextStop);
            }
            if (/\d+号線/u.test(label)) {
              globalTrainLabelScan.rawNumberedLineLabelCount += 1;
              addGlobalTrainLabelSample('raw_numbered_line_label', stationName, entry, routeId, label);
            }
            if (/\s直通$/u.test(label)) {
              globalTrainLabelScan.throughDisplayTextCount += 1;
              addGlobalTrainLabelSample('through_display_text', stationName, entry, routeId, label);
            }
            const publicNumber = publicTripNumber(trip);
            const shouldDisplayPublicNumber = isShinkansenTrip(trip) ||
              (isLimitedExpressTrip(trip) && looksLikePublicTrainNumber(publicNumber));
            if (
              publicNumber &&
              shouldDisplayPublicNumber &&
              !String(label).includes(publicNumber)
            ) {
              globalTrainLabelScan.limitedOrShinkansenMissingNumberCount += 1;
              addGlobalTrainLabelSample('limited_or_shinkansen_missing_number', stationName, entry, routeId, label);
            }
            if (isLimitedExpressTrip(trip) && !isShinkansenTrip(trip) && /\d{1,4}号/u.test(label)) {
              globalTrainLabelScan.limitedExpressGoSuffixCount += 1;
              addGlobalTrainLabelSample('limited_express_go_suffix', stationName, entry, routeId, label);
            }
            const selectedJrRouteId = selectedJrNorthernTrunkLabelRouteId(entry, routeId);
            const adjacentDirectionRouteId = adjacentDirectionRouteIdForChoice(entry);
            const directionRouteId = selectedJrRouteId ||
              directionTerminalRouteIdForTrainLabel(entry, routeId) ||
              (adjacentDirectionRouteId === routeId && !isJrRoute(state.routeById.get(routeId))
                ? adjacentDirectionRouteId
                : null);
            const directionLabel = directionRouteId ? titleForRoute(directionRouteId) : '';
            const terminalName = displayNameForGroup((trip?.stopTimes || []).at(-1)?.stationGroupId || '');
            if (
              choiceRouteTitle === '都営浅草線' &&
              ['天空橋', '羽田空港第１・第２ターミナル', '羽田空港第３ターミナル'].includes(terminalName) &&
              label !== '京急空港線'
            ) {
              globalTrainLabelScan.asakusaKeikyuAirportLabelMismatchCount += 1;
              addGlobalTrainLabelSample('asakusa_keikyu_airport_label_mismatch', stationName, entry, routeId, label);
            }
            const directionTraceRouteCount = directionTraceRouteCountForTrip(trip);
            if (
              directionTraceRouteCount >= 2 &&
              directionLabel &&
              !isShinkansenTrip(trip) &&
              !isLimitedExpressTrip(trip) &&
              !(stationName === '米原' && choiceRouteTitle === '東海道線' && label === '東海道線') &&
              label !== directionLabel
            ) {
              globalTrainLabelScan.throughDirectionLabelMismatchCount += 1;
              addGlobalTrainLabelSample('through_direction_label_mismatch', stationName, entry, routeId, label);
            }
            if (isMeitetsuTrip(trip)) {
              if (!/^[^（）()]+線$/u.test(label) || /^\d+号線/u.test(label)) {
                globalTrainLabelScan.meitetsuLabelFormatMismatchCount += 1;
                addGlobalTrainLabelSample('meitetsu_label_format_mismatch', stationName, entry, routeId, label);
              }
            }
            const allowedStations = allowedVirtualRouteStations[routeId];
            const routeChoiceMatchesTrace = (
              routeId === trip?.routeId ||
              routeId === currentSegmentRouteId ||
              routeIdSetHasRouteOrTitle(currentPhysicalRouteIds, routeId) ||
              futureTraceRouteIds.has(routeId) ||
              Boolean(allowedStations) ||
              isNamedTrainChoiceRouteId(routeId) ||
              isShinkansenCorridorRoute(routeId) ||
              allowedPassengerRouteOverPhysicalTrace(stationName, entry, routeId, currentSegmentRouteId, nextStop)
            );
            if (!routeChoiceMatchesTrace) {
              globalChoiceScan.choiceTraceMismatchCount += 1;
              addGlobalChoiceSample('route_choice_not_in_trip_trace', stationName, entry, routeId, nextStop);
            }
            const routeChoiceMatchesCurrentPhysical = (
              routeIdSetHasRouteOrTitle(currentPhysicalRouteIds, routeId) ||
              Boolean(allowedStations) ||
              isNamedTrainChoiceRouteId(routeId) ||
              isShinkansenCorridorRoute(routeId) ||
              allowedPassengerRouteOverPhysicalTrace(stationName, entry, routeId, currentSegmentRouteId, nextStop)
            );
            if (currentPhysicalRouteIds.size && !routeChoiceMatchesCurrentPhysical) {
              globalChoiceScan.currentPhysicalMismatchCount += 1;
              addGlobalChoiceSample('route_choice_not_current_physical_segment', stationName, entry, routeId, nextStop);
            }
            if (isShinkansenCorridorRoute(routeId)) return;
            if (isNamedTrainChoiceRouteId(routeId)) {
              if (isRouteLikeNamedTrainLabel(choiceRouteTitle)) {
                globalChoiceScan.routeLikeNamedChoiceCount += 1;
                addGlobalChoiceSample('route_like_named_choice', stationName, entry, routeId, nextStop);
              }
              return;
            }
            if (allowedStations) {
              if (!allowedStations.has(stationName)) {
                globalChoiceScan.virtualOutsideAllowedStationCount += 1;
                addGlobalChoiceSample('virtual_outside_allowed_station', stationName, entry, routeId, nextStop);
              }
              return;
            }
            if (
              currentPhysicalRouteIds.size &&
              !routeIdSetHasRouteOrTitle(currentPhysicalRouteIds, routeId) &&
              !allowedPassengerRouteOverPhysicalTrace(stationName, entry, routeId, currentSegmentRouteId, nextStop)
            ) {
              globalChoiceScan.segmentMismatchCount += 1;
              addGlobalChoiceSample('choice_not_current_next_segment', stationName, entry, routeId, nextStop);
            }
          });
        }
      }
      selectedTrips.forEach((trip) => {
        if (!trip?.throughStitched) return;
        const boardStop = (trip.stopTimes || []).find((stop) => stopDepartureMinutes(stop) >= START_MINUTE) ||
          (trip.stopTimes || [])[0];
        if (!boardStop) return;
        globalTrainLabelScan.checkedThroughPreviewTexts += 1;
        const previewText = trainPreviewText(trip, boardStop);
        if (/(^|[\s·,，、])直通\s/u.test(previewText)) {
          globalTrainLabelScan.throughDisplayTextCount += 1;
          addGlobalTrainLabelSample(
            'through_preview_display_text',
            displayNameForGroup(boardStop.stationGroupId),
            {
              trip,
              stop: boardStop,
              departureMinute: stopDepartureMinutes(boardStop),
            },
            trip.routeId,
            formatTripLabel(trip)
          );
        }
      });
    }
    if (
      globalChoiceScan.segmentMismatchCount ||
      globalChoiceScan.virtualOutsideAllowedStationCount ||
      globalChoiceScan.genericRouteLabelCount ||
      globalChoiceScan.yokohamaThroughRemoteRouteCount ||
      globalChoiceScan.routeLikeNamedChoiceCount ||
      globalChoiceScan.nonKeikyuAirportLineKkSymbolCount ||
      globalChoiceScan.choiceTraceMismatchCount ||
      globalChoiceScan.currentPhysicalMismatchCount ||
      globalChoiceScan.highlightTraceMismatchCount
    ) {
      anomalies.push({
        kind: 'global_route_choice_segment_scan',
        reason: 'Every player-facing route choice must either be an allowed virtual corridor/named train or match the reviewed current physical segment and future trace; selected-train ranges must cover the current physical segment and future trace; route symbols must not leak across same-named airport lines.',
        ...globalChoiceScan,
      });
    }
    timings.globalChoiceAndLabelScanMs = performance.now() - timings.startedAtMs;
    if (stageEnabled('global')) {
      state.departureQueryCache = new Map();
      state.routeChoicesByDeparturesCache = new WeakMap();
    }
    const duplicateScanStartedAtMs = performance.now();
    const duplicateStations = [...state.stationGroupById.entries()];
    const selectedDuplicateStations = stationLimit === null
      ? duplicateStations.slice(stationStart)
      : duplicateStations.slice(stationStart, stationStart + stationLimit);
    Object.assign(duplicateRouteTitleScan, {
      stationStart,
      stationLimit,
      stationCount: duplicateStations.length,
      selectedStationCount: selectedDuplicateStations.length,
      skipped: !stageEnabled('duplicates'),
    });
    if (stageEnabled('duplicates')) {
      for (const [stationGroupId, group] of selectedDuplicateStations) {
        const stationName = group.names?.ja || group.primaryName || stationGroupId;
        duplicateRouteTitleScan.checkedStations += 1;
        const choices = routeChoicesFromDepartures(departuresForStationGroup(stationGroupId, START_MINUTE, { includeTransferEquivalents: true }));
        const titleCounts = new Map();
        choices.forEach((choice) => {
          const title = titleForRoute(choice.routeId);
          titleCounts.set(title, (titleCounts.get(title) || 0) + 1);
        });
        const duplicateTitles = [...titleCounts.entries()].filter(([, count]) => count > 1);
        if (!duplicateTitles.length) continue;
        duplicateRouteTitleScan.duplicateStationTitleCount += duplicateTitles.length;
        if (duplicateRouteTitleScan.samples.length < 80) {
          duplicateRouteTitleScan.samples.push({
            station: stationName,
            duplicates: duplicateTitles.map(([title, count]) => ({ title, count })),
            choices: choices.map((choice) => ({
              route: titleForRoute(choice.routeId),
              subtitle: routeChoiceSubtitle(choice),
              firstDeparture: choice.firstDepartureHhmm,
              trainCount: choice.trainCount,
            })),
          });
        }
      }
    }
    if (duplicateRouteTitleScan.duplicateStationTitleCount) {
      anomalies.push({
        kind: 'duplicate_route_choice_title_scan',
        reason: 'Each station route-choice list should show only one row for a player-facing route name; duplicate source route IDs must be merged behind that choice.',
        ...duplicateRouteTitleScan,
      });
    }
    timings.duplicateRouteTitleScanMs = performance.now() - duplicateScanStartedAtMs;
    if (
      globalTrainLabelScan.rawNumberedLineLabelCount ||
      globalTrainLabelScan.limitedOrShinkansenMissingNumberCount ||
      globalTrainLabelScan.throughDirectionLabelMismatchCount ||
      globalTrainLabelScan.meitetsuLabelFormatMismatchCount ||
      globalTrainLabelScan.namedLimitedExpressNotSeparatedCount ||
      globalTrainLabelScan.limitedExpressGoSuffixCount ||
      globalTrainLabelScan.asakusaKeikyuAirportLabelMismatchCount ||
      globalTrainLabelScan.throughDisplayTextCount
    ) {
      anomalies.push({
        kind: 'global_selected_train_label_scan',
        reason: 'Selected-train labels must not expose raw x号線 names, limited express/Shinkansen labels must include public train numbers when available, limited express labels must not append 号 after the train number, ordinary through-running labels including Meitetsu must follow the direction-side line, Meitetsu labels must not use parentheses, named limited-express/named train services must be separated as their own route choices, and synthetic/stitched trips must not show extra 直通 display text.',
        ...globalTrainLabelScan,
      });
    }
    if (stageEnabled('duplicates')) {
      state.departureQueryCache = new Map();
      state.routeChoicesByDeparturesCache = new WeakMap();
    }
    const miniShinkansenScanStartedAtMs = performance.now();
    if (stageEnabled('mini-shinkansen')) {
      const reviewedMiniShinkansenStations = [
        ['福島', '山形新幹線', ['奥羽線'], /つばさ|Tsubasa/u],
        ['米沢', '山形新幹線', ['奥羽線'], /つばさ|Tsubasa/u],
        ['山形', '山形新幹線', ['奥羽線'], /つばさ|Tsubasa/u],
        ['新庄', '山形新幹線', ['奥羽線'], /つばさ|Tsubasa/u],
        ['盛岡', '秋田新幹線', ['田沢湖線'], /こまち|Komachi/u],
        ['田沢湖', '秋田新幹線', ['田沢湖線'], /こまち|Komachi/u],
        ['大曲', '秋田新幹線', ['田沢湖線', '奥羽線'], /こまち|Komachi/u],
        ['秋田', '秋田新幹線', ['奥羽線'], /こまち|Komachi/u],
      ];
      const addMiniSample = (kind, station, detail) => {
        if (miniShinkansenBranchScan.samples.length >= 80) return;
        miniShinkansenBranchScan.samples.push({ kind, station, ...detail });
      };
      reviewedMiniShinkansenStations.forEach(([stationName, shinkansenRoute, ordinaryRoutes, branchServicePattern]) => {
        miniShinkansenBranchScan.checkedStations += 1;
        const choices = choicesAt(stationName);
        const choiceTitles = new Set(choices.map((choice) => choice.route));
        const missingRoutes = [shinkansenRoute, ...ordinaryRoutes]
          .filter((routeName) => !choiceTitles.has(routeName));
        if (missingRoutes.length) {
          miniShinkansenBranchScan.missingRouteCount += missingRoutes.length;
          addMiniSample('missing_mini_shinkansen_or_ordinary_branch_route', stationName, {
            missingRoutes,
            choices,
          });
        }
        const mergedChoices = choices.filter((choice) =>
          choice.route.includes('・') &&
          choice.route.includes('新幹線') &&
          (choice.route.includes('秋田') || choice.route.includes('山形'))
        );
        if (mergedChoices.length) {
          miniShinkansenBranchScan.mergedRouteChoiceCount += mergedChoices.length;
          addMiniSample('merged_mini_shinkansen_route_choice', stationName, {
            mergedChoices,
            choices,
          });
        }
        entriesAt(stationName).forEach((entry) => {
          const routeTitles = routeTitlesForEntry(entry);
          const label = formatTripLabelForBoarding(entry, entry.trip?.routeId || '');
          if (routeTitles.includes(shinkansenRoute)) {
            miniShinkansenBranchScan.checkedShinkansenEntries += 1;
            if (!isShinkansenTrip(entry.trip)) {
              miniShinkansenBranchScan.nonShinkansenEntryCount += 1;
              addMiniSample('mini_shinkansen_choice_has_non_shinkansen_trip', stationName, {
                summary: summarizeEntry(stationName, entry),
                label,
              });
            }
            if (/特急/u.test(label)) {
              miniShinkansenBranchScan.specialExpressLabelLeakCount += 1;
              addMiniSample('mini_shinkansen_label_leaks_limited_express_text', stationName, {
                summary: summarizeEntry(stationName, entry),
                label,
              });
            }
          }
          ordinaryRoutes.forEach((ordinaryRoute) => {
            if (!routeTitles.includes(ordinaryRoute)) return;
            miniShinkansenBranchScan.checkedOrdinaryEntries += 1;
            const text = [
              entry.trip?.serviceName,
              entry.trip?.displayName,
              entry.trip?.routeName,
              label,
            ].filter(Boolean).join(' ');
            if (branchServicePattern.test(text) || isShinkansenTrip(entry.trip)) {
              miniShinkansenBranchScan.ordinaryLineLeakCount += 1;
              addMiniSample('mini_shinkansen_trip_leaks_into_ordinary_branch_route', stationName, {
                ordinaryRoute,
                summary: summarizeEntry(stationName, entry),
                label,
              });
            }
          });
        });
      });
      if (
        miniShinkansenBranchScan.missingRouteCount ||
        miniShinkansenBranchScan.ordinaryLineLeakCount ||
        miniShinkansenBranchScan.nonShinkansenEntryCount ||
        miniShinkansenBranchScan.specialExpressLabelLeakCount ||
        miniShinkansenBranchScan.mergedRouteChoiceCount
      ) {
        anomalies.push({
          kind: 'mini_shinkansen_branch_route_identity_scan',
          reason: 'Mini-Shinkansen branch services must stay visible as Shinkansen route choices and must not leak into ordinary branch-line or limited-express categories.',
          ...miniShinkansenBranchScan,
        });
      }
      state.departureQueryCache = new Map();
      state.routeChoicesByDeparturesCache = new WeakMap();
    }
    timings.miniShinkansenBranchScanMs = performance.now() - miniShinkansenScanStartedAtMs;
    const knownStationScanStartedAtMs = performance.now();
    let knownStationChoices = {};
    let routeChoiceTitles = {};
    if (stageEnabled('known')) {
      knownStationChoices = Object.fromEntries(
        [
          '東京', '上野', '品川', '新橋', '大宮', '福島', '米沢', '山形', '新庄', '盛岡', '田沢湖', '大曲', '秋田', '青梅', '八王子', '米原',
          '敦賀', '京都', '新大阪', '白浜', '新宿', '池袋', '横浜', '大船', '小田原', '逗子', '宇都宮', '高崎', '成田空港',
          '松本', '大月', '蘇我', '五井', '木更津', '上総一ノ宮', '成田', '佐倉',
        ].map((stationName) => [stationName, choicesAt(stationName)])
      );
      routeChoiceTitles = Object.fromEntries(
        Object.entries(knownStationChoices).map(([stationName, choices]) => [
          stationName,
          new Set(choices.map((choice) => choice.route)),
        ])
      );
      for (const stationName of ['大宮', '八王子']) {
      if (!routeChoiceTitles[stationName]?.has('むさしの号')) {
        anomalies.push({
          kind: 'musashino_named_train_choice_missing',
          station: stationName,
          reason: 'The Omiya-Hachioji Musashino service should be a separate named-train choice instead of being buried under a physical line.',
          choices: knownStationChoices[stationName],
        });
      }
    }
    if (!routeChoiceTitles['東京']?.has('秋田新幹線')) {
      anomalies.push({
        kind: 'tokyo_akita_shinkansen_choice_missing',
        station: '東京',
        reason: 'Tokyo must expose the reviewed Komachi branch as its own Akita Shinkansen route choice instead of merging Shinkansen coupled services into one corridor.',
        choices: knownStationChoices['東京'],
      });
    }
    ['新宿', '池袋', '横浜', '大船', '大宮'].forEach((stationName) => {
      if (!routeChoiceTitles[stationName]?.has('湘南新宿ライン')) {
        anomalies.push({
          kind: 'shonan_shinjuku_corridor_choice_missing',
          station: stationName,
          reason: 'Shonan-Shinjuku Line is a real JR East operating corridor and should be selectable in its core Omiya-Shinjuku-Yokohama-Ofuna corridor while selected-train highlight stays on the physical trace.',
          choices: knownStationChoices[stationName],
        });
      }
    });
    ['小田原', '逗子', '宇都宮', '高崎'].forEach((stationName) => {
      if (routeChoiceTitles[stationName]?.has('湘南新宿ライン')) {
        anomalies.push({
          kind: 'shonan_shinjuku_corridor_leaks_to_branch_station',
          station: stationName,
          reason: 'Outside the core Shonan-Shinjuku corridor, branch stations should keep their physical line choices and use through-running train labels after the player selects a train.',
          choices: knownStationChoices[stationName],
        });
      }
    });
    ['東京', '上野', '大宮', '福島', '山形', '新庄'].forEach((stationName) => {
      if (!routeChoiceTitles[stationName]?.has('山形新幹線')) {
        anomalies.push({
          kind: 'yamagata_shinkansen_choice_missing',
          station: stationName,
          reason: 'Reviewed Tsubasa B/M source segments must be paired by train number into a Yamagata Shinkansen choice without frontend-only fabrication.',
          choices: knownStationChoices[stationName],
        });
      }
    });
    const mergedShinkansenChoices = Object.entries(knownStationChoices)
      .flatMap(([station, choices]) => choices
        .filter((choice) => choice.route === '東北・北海道・秋田新幹線')
        .map((choice) => ({ station, ...choice })));
    if (mergedShinkansenChoices.length) {
      anomalies.push({
        kind: 'shinkansen_coupled_route_choice_merged',
        reason: 'Shinkansen coupled services are a display exception: route choices stay on each Shinkansen route, while same_train capture equivalence still applies.',
        samples: mergedShinkansenChoices,
      });
    }
    [
      ['東京', 'ひたち', 30],
      ['東京', 'ときわ', 35],
      ['東京', '成田エクスプレス', 35],
      ['東京', 'あずさ', 5],
      ['東京', 'かいじ', 8],
      ['東京', 'わかしお', 10],
      ['東京', 'さざなみ', 4],
      ['東京', '踊り子', 7],
      ['東京', '秋田新幹線', 18],
      ['東京', '山形新幹線', 14],
      ['上野', '山形新幹線', 26],
      ['大宮', '山形新幹線', 26],
      ['上野', 'ひたち', 30],
      ['上野', 'ときわ', 35],
      ['品川', '成田エクスプレス', 50],
      ['品川', 'ひたち', 15],
      ['品川', 'ときわ', 18],
      ['八王子', 'あずさ', 34],
      ['八王子', 'かいじ', 20],
      ['新宿', '成田エクスプレス', 10],
      ['新宿', 'あずさ', 20],
      ['新宿', 'かいじ', 18],
      ['新宿', '富士回遊', 1],
      ['大船', '成田エクスプレス', 14],
      ['成田空港', '成田エクスプレス', 25],
      ['松本', 'あずさ', 15],
      ['大月', 'あずさ', 8],
      ['大月', 'かいじ', 28],
      ['大月', '富士回遊', 6],
      ['敦賀', 'サンダーバード', 25],
      ['京都', 'サンダーバード', 30],
      ['京都', 'はるか', 30],
      ['新大阪', 'サンダーバード', 30],
      ['新大阪', 'はるか', 55],
      ['新大阪', 'くろしお', 18],
      ['白浜', 'くろしお', 20],
    ].forEach(([stationName, routeName, minimumTrainCount]) => {
      const choice = knownStationChoices[stationName]?.find((item) => item.route === routeName);
      if (!choice || choice.trainCount < minimumTrainCount) {
        anomalies.push({
          kind: 'named_limited_express_choice_underfilled',
          station: stationName,
          route: routeName,
          minimumTrainCount,
          actualTrainCount: choice?.trainCount || 0,
          reason: 'Reviewed named limited express choices should include both directions from the official direct-service source.',
          choices: knownStationChoices[stationName],
        });
      }
    });
    function trainNumbersForChoiceAt(stationName, routeName) {
      return new Set(entriesAt(stationName)
        .filter((entry) => routeTitlesForEntry(entry).includes(routeName))
        .map((entry) => publicTripNumber(entry.trip))
        .filter(Boolean));
    }
    [
      ['敦賀', 'サンダーバード', ['2', '4', '6', '8', '10']],
      ['京都', 'サンダーバード', ['1', '2', '3', '4', '43']],
      ['新大阪', 'サンダーバード', ['1', '2', '3', '4', '43']],
      ['京都', 'はるか', ['3', '5', '7', '9', '11']],
      ['新大阪', 'はるか', ['1', '3', '5', '7', '9']],
      ['新大阪', 'くろしお', ['1', '2', '4', '12', '16']],
      ['白浜', 'くろしお', ['8', '10', '12', '16', '22']],
      ['新宿', '成田エクスプレス', ['9', '13', '17', '21', '25']],
      ['大船', '成田エクスプレス', ['3', '5', '7', '11', '15']],
      ['成田空港', '成田エクスプレス', ['1', '2', '3', '4', '5']],
      ['新宿', 'あずさ', ['1', '3', '5', '9', '83']],
      ['松本', 'あずさ', ['1', '4', '8', '12', '83']],
      ['大月', '富士回遊', ['3', '7', '11', '15', '93']],
      ['大月', 'かいじ', ['70', '2', '6', '10', '99']],
      ['東京', '秋田新幹線', ['1', '3', '7', '9', '23']],
      ['東京', '山形新幹線', ['121', '129', '139', '159', '87', '88']],
    ].forEach(([stationName, routeName, requiredNumbers]) => {
      const actualNumbers = trainNumbersForChoiceAt(stationName, routeName);
      const missingNumbers = requiredNumbers.filter((number) => !actualNumbers.has(number));
      if (missingNumbers.length) {
        anomalies.push({
          kind: 'reviewed_limited_express_train_numbers_missing',
          station: stationName,
          route: routeName,
          requiredNumbers,
          missingNumbers,
          actualNumbers: [...actualNumbers].slice(0, 80),
          reason: 'Reviewed limited express train numbers must remain present in route choices, including boundary-station starts, branch-origin trains, and through-service pass-through trains.',
          choices: knownStationChoices[stationName],
        });
      }
    });
    if (routeChoiceTitles['東京']?.has('サフィール踊り子')) {
      anomalies.push({
        kind: 'saphir_odoriko_named_train_family_split',
        station: '東京',
        reason: 'Saphir Odoriko should be grouped under the Odoriko named-train family choice.',
        choices: knownStationChoices['東京'],
      });
    }
    const maibaraTokaidoChoices = knownStationChoices['米原']?.filter((choice) => choice.route === '東海道線') || [];
    if (maibaraTokaidoChoices.length !== 1) {
      anomalies.push({
        kind: 'maibara_duplicate_tokaido_choice',
        station: '米原',
        reason: 'Maibara is the JR Central/JR West Tokaido boundary, but the player should see one platform-line choice, not separate operator route IDs.',
        choices: knownStationChoices['米原'],
      });
    }
    const maibaraSouthboundProblems = entriesAt('米原')
      .map((entry) => summarizeEntry('米原', entry))
      .filter((summary) => summary.nextStation === '彦根' && summary.choices.includes('北陸線'))
      .slice(0, 20);
    if (maibaraSouthboundProblems.length) {
      anomalies.push({
        kind: 'maibara_southbound_tokaido_missing',
        station: '米原',
        reason: 'Maibara departures toward Hikone/Kyoto/Osaka must be shown under Tokaido Line, not Hokuriku Line.',
        samples: maibaraSouthboundProblems,
        choices: knownStationChoices['米原'],
      });
    }

    const forbiddenRemoteThroughChoicesByStation = {
      蘇我: new Set(['横須賀線', '総武快速線', '横須賀線・総武快速線', '総武線']),
      五井: new Set(['横須賀線', '総武快速線', '横須賀線・総武快速線', '総武線', '京葉線']),
      木更津: new Set(['横須賀線', '総武快速線', '横須賀線・総武快速線', '総武線', '京葉線']),
      上総一ノ宮: new Set(['横須賀線', '総武快速線', '横須賀線・総武快速線', '総武線', '京葉線']),
      成田: new Set(['横須賀線', '総武快速線', '横須賀線・総武快速線', '総武線']),
      佐倉: new Set(['横須賀線', '総武快速線', '横須賀線・総武快速線']),
    };
    for (const [stationName, forbiddenTitles] of Object.entries(forbiddenRemoteThroughChoicesByStation)) {
      const forbiddenChoices = knownStationChoices[stationName]
        .filter((choice) => forbiddenTitles.has(choice.route))
        .map((choice) => choice.route);
      if (forbiddenChoices.length) {
        anomalies.push({
          kind: 'remote_through_line_choice_on_physical_branch',
          station: stationName,
          reason: 'Route choices must show the current physical boarding line; remote through-running identities such as Yokosuka/Sobu Rapid/Keiyo may only appear after selecting a train.',
          forbiddenChoices: [...new Set(forbiddenChoices)].sort((a, b) => a.localeCompare(b, 'ja')),
          choices: knownStationChoices[stationName],
        });
      }
    }

    const unexpectedUenoTokyoStations = [...allUenoTokyoChoiceStationSet]
      .filter((stationName) => !['東京', '上野'].includes(stationName))
      .sort((a, b) => a.localeCompare(b, 'ja'));
    if (unexpectedUenoTokyoStations.length) {
      anomalies.push({
        kind: 'ueno_tokyo_line_outside_core_station_scan',
        reason: 'The weakened Ueno-Tokyo Line display rule only allows 上野東京ライン at Tokyo and Ueno.',
        stations: unexpectedUenoTokyoStations,
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

    const requiredShinkansenChoices = {
      東京: ['東海道・山陽新幹線', '東北・北海道新幹線', '秋田新幹線', '上越新幹線', '北陸新幹線'],
      品川: ['東海道・山陽新幹線'],
      大宮: ['東北・北海道新幹線', '秋田新幹線', '上越新幹線', '北陸新幹線'],
    };
    for (const [stationName, requiredRoutes] of Object.entries(requiredShinkansenChoices)) {
      const choices = routeChoiceTitles[stationName] || new Set();
      const missingRoutes = requiredRoutes.filter((routeName) => !choices.has(routeName));
      if (missingRoutes.length) {
        anomalies.push({
          kind: 'major_station_shinkansen_choice_missing',
          station: stationName,
          reason: 'Major Shinkansen stations must keep Shinkansen route choices visible even when the selected station group is a transfer-equivalent conventional group.',
          missingRoutes,
          choices: knownStationChoices[stationName],
        });
      }
    }

    const forbiddenTokyoNorthChoices = knownStationChoices['東京']
      .filter((choice) => forbiddenTokyoNorthTrunkChoices.has(choice.route))
      .map((choice) => choice.route);
    if (forbiddenTokyoNorthChoices.length) {
      anomalies.push({
        kind: 'tokyo_station_raw_north_trunk_choice',
        station: '東京',
        reason: 'At Tokyo, 東北本線 through-running uses the 上野東京ライン nickname only on the 東京-上野 segment; raw northern trunk choices must not appear.',
        choices: knownStationChoices['東京'],
        forbiddenChoices: [...new Set(forbiddenTokyoNorthChoices)].sort((a, b) => a.localeCompare(b, 'ja')),
      });
    }

    const forbiddenUenoSouthChoices = knownStationChoices['上野']
      .filter((choice) => choice.route === '東海道線')
      .map((choice) => choice.route);
    if (forbiddenUenoSouthChoices.length) {
      anomalies.push({
        kind: 'ueno_station_raw_south_trunk_choice',
        station: '上野',
        reason: 'At Ueno, Tokyo-bound 東北本線 through-running must show the 上野東京ライン nickname; raw southern trunk choices such as 東海道線 must not appear.',
        choices: knownStationChoices['上野'],
        forbiddenChoices: [...new Set(forbiddenUenoSouthChoices)].sort((a, b) => a.localeCompare(b, 'ja')),
      });
    }
    const forbiddenOmiyaTobuTojoChoices = knownStationChoices['大宮']
      .filter((choice) => choice.route === '東武東上本線')
      .map((choice) => choice.route);
    if (forbiddenOmiyaTobuTojoChoices.length) {
      anomalies.push({
        kind: 'omiya_station_forbidden_tobu_tojo_choice',
        station: '大宮',
        reason: 'Saitama Omiya is served by Tobu Noda/Urban Park Line, not Tobu Tojo Line; JR Saikyo/Kawagoe rows must not be imported as Tobu Tojo choices.',
        choices: knownStationChoices['大宮'],
        forbiddenChoices: [...new Set(forbiddenOmiyaTobuTojoChoices)].sort((a, b) => a.localeCompare(b, 'ja')),
      });
    }
    }
    timings.knownStationScanMs = performance.now() - knownStationScanStartedAtMs;
    const focusedRuleScanStartedAtMs = performance.now();
    let coupledUmbrellaSamples = [];
    let coupledEquivalentTripCount = 0;
    let coupledEquivalentEdgeCount = 0;
    let shinkansenEquivalentEdgeCount = 0;
    if (stageEnabled('focused')) {
    const uenoTakasakiBranchStations = new Set([
      '宮原', '上尾', '北上尾', '桶川', '北本', '鴻巣', '北鴻巣', '吹上',
      '行田', '熊谷', '籠原', '深谷', '岡部', '本庄', '神保原',
      '新町', '倉賀野', '高崎', '新前橋', '前橋',
    ]);

    for (const stationName of ['東京']) {
      for (const entry of entriesAt(stationName)) {
        if (!nextStopFor(entry)) continue;
        const choices = routeTitlesForEntry(entry);
        if (choices.includes('東海道線') || [...forbiddenTokyoNorthTrunkChoices].some((route) => choices.includes(route))) {
          const nextStation = summarizeEntry(stationName, entry).nextStation;
          if (nextStation !== '上野' && !choices.some((choice) => forbiddenTokyoNorthTrunkChoices.has(choice))) continue;
          anomalies.push({
            kind: 'central_ueno_tokyo_physical_choice',
          reason: 'Tokyo station through-running should expose the 東京-上野 東北本線 nickname as 上野東京ライン and southbound movements as 東海道線.',
            ...summarizeEntry(stationName, entry),
          });
        }
      }
    }

    for (const entry of entriesAt('上野')) {
      if (!nextStopFor(entry)) continue;
      const summary = summarizeEntry('上野', entry);
      if (summary.choices.includes('東海道線')) {
        anomalies.push({
          kind: 'ueno_tokaido_through_choice',
          reason: 'Ueno is the northern boundary of the 上野東京ライン nickname segment; southbound through movements should use 上野東京ライン, not 東海道線.',
          ...summary,
        });
      }
      const downstreamNames = (entry.trip?.stopTimes || [])
        .filter((stop) => stop.sequence > entry.stop.sequence)
        .map((stop) => displayNameForGroup(stop.stationGroupId));
      if (summary.choices.includes('高崎線')) {
        anomalies.push({
          kind: 'ueno_takasaki_branch_starts_too_early',
          reason: '高崎線 starts as the branch at 大宮; at 上野, Takasaki-bound through movements are still on 東北本線.',
          ...summary,
          downstreamSample: downstreamNames.slice(0, 16),
        });
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
          reason: 'At Omiya, northbound branch movements must show the branch boarding face, not the through-service nickname.',
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

    for (const stationName of ['中野', '新宿', '四ツ谷', '御茶ノ水', '神田']) {
      for (const entry of allEntriesAt(stationName)) {
        const summary = summarizeEntry(stationName, entry);
        if (!summary.choices.includes('中央線快速')) continue;
        const labels = routeChoiceIdsForDeparture(entry).map((routeId) => formatTripLabelForBoarding(entry, routeId));
        const leakedLabels = labels.filter((label) => label === '東北本線' || label === '東北線');
        if (!leakedLabels.length) continue;
        anomalies.push({
          kind: 'chuo_train_label_tohoku_leak',
          reason: 'Chuo rapid trains between Kanda and Tokyo must remain on 中央線; the Kanda-Tokyo endpoint must not be traced or labeled as 東北本線.',
          ...summary,
          labels,
        });
      }
    }

    const kazusaIchinomiyaAwaKamogawaLabels = [];
    for (const entry of entriesAt('上総一ノ宮')) {
      const summary = summarizeEntry('上総一ノ宮', entry);
      if (summary.terminal !== '安房鴨川') continue;
      for (const routeId of routeChoiceIdsForDeparture(entry)) {
        if (routeTitle(routeId) !== '外房線') continue;
        kazusaIchinomiyaAwaKamogawaLabels.push(formatTripLabelForBoarding(entry, routeId));
      }
    }
    if (
      !kazusaIchinomiyaAwaKamogawaLabels.length ||
      kazusaIchinomiyaAwaKamogawaLabels.some((label) => label !== '外房線')
    ) {
      anomalies.push({
        kind: 'sotobo_awa_kamogawa_train_label_mismatch',
        reason: 'Trains from 上総一ノ宮 toward 安房鴨川 run on the Sotobo side and must not be labeled as Uchibo.',
        labels: kazusaIchinomiyaAwaKamogawaLabels.slice(0, 20),
      });
    }

    for (const entry of entriesAt('八王子')) {
      const summary = summarizeEntry('八王子', entry);
      if (summary.terminal === '河口湖' && summary.choices.includes('横浜線')) {
        anomalies.push({
          kind: 'hachioji_yokohama_line_kawaguchiko_pollution',
          reason: 'Fuji/Kawaguchiko through trains at Hachioji use the Chuo-side boarding segment toward Otsuki/Tachikawa and must not appear under Yokohama Line.',
          ...summary,
        });
      }
    }

    coupledUmbrellaSamples = [];
    for (const stationName of ['東京', '上野', '大宮', '仙台', '成田空港', '空港第2ビル', '品川', '新大阪', '大阪', '京都', '博多', '宇多津', '岡山', '綾部']) {
      const rows = buildCoupledTrainRows(entriesAt(stationName), null)
        .filter((row) => row.kind === 'coupled');
      rows.slice(0, 4).forEach((row) => coupledUmbrellaSamples.push({
        station: stationName,
        label: row.label,
        departure: row.departureHhmm,
        portionCount: row.portions.length,
        portions: row.portions.map((item) => item.portion?.label || formatTripLabel(item.row.trip)),
      }));
    }
    const shinkansenUmbrellaSamples = coupledUmbrellaSamples.filter((sample) =>
      [...(sample.portions || []), sample.label].some((label) => /はやぶさ|こまち|やまびこ|つばさ/u.test(String(label || '')))
    );
    const requiredCoupledUmbrellaLabels = ['成田エクスプレス', '関空快速・紀州路快速', 'サンライズ瀬戸・出雲'];
    const missingCoupledUmbrellaLabels = requiredCoupledUmbrellaLabels.filter((requiredLabel) =>
      !coupledUmbrellaSamples.some((sample) => sample.label === requiredLabel)
    );
    coupledEquivalentTripCount = state.coupledEquivalentsByTripId?.size || 0;
    coupledEquivalentEdgeCount = [...(state.coupledEquivalentsByTripId?.values() || [])]
      .reduce((sum, items) => sum + items.length, 0);
    shinkansenEquivalentEdgeCount = [...(state.coupledEquivalentsByTripId?.values() || [])]
      .flat()
      .filter((item) => item.entryId === 'hayabusa_komachi_morioka' || item.entryId === 'yamabiko_tsubasa_fukushima')
      .length;
    if ((state.coupledServiceEntries || []).length < 16) {
      anomalies.push({
        kind: 'coupled_registry_underfilled',
        reason: 'The reviewed coupled-service registry should load regular passenger split/join services for gameplay.',
        entryCount: (state.coupledServiceEntries || []).length,
      });
    }
    if (!coupledEquivalentTripCount || !coupledEquivalentEdgeCount) {
      anomalies.push({
        kind: 'coupled_same_train_equivalence_missing',
        reason: 'Coupled portions must be considered same_train during their shared physical segment.',
        equivalentTripCount: coupledEquivalentTripCount,
        equivalentEdgeCount: coupledEquivalentEdgeCount,
      });
    }
    if (!coupledUmbrellaSamples.length) {
      anomalies.push({
        kind: 'coupled_umbrella_choice_missing',
        reason: 'Reviewed non-Shinkansen coupled trains should expose an umbrella A・B row when the player boards the coupled physical train.',
      });
    }
    if (missingCoupledUmbrellaLabels.length) {
      anomalies.push({
        kind: 'reviewed_non_shinkansen_coupled_umbrella_missing',
        reason: 'Non-Shinkansen coupled services such as Narita Express and Kansai/Kishuji rapid must keep the umbrella train row and must not require a second branch picker after train selection.',
        missingLabels: missingCoupledUmbrellaLabels,
        samples: coupledUmbrellaSamples,
      });
    }
    const tokyoSunriseChoices = choicesAt('東京').filter((choice) => choice.route.includes('サンライズ'));
    const tokyoStationGroupId = firstStationIdByName('東京');
    const tokyoSunriseRouteId = tokyoSunriseChoices.length === 1
      ? routeChoicesFromDepartures(entriesAt('東京')).find((choice) => routeTitle(choice.routeId) === tokyoSunriseChoices[0].route)?.routeId
      : null;
    const tokyoSunrisePlayableRows = tokyoStationGroupId && tokyoSunriseRouteId
      ? buildCoupledTrainRows(availableRouteDepartures({
        currentState: { kind: 'NODE', stationGroupId: tokyoStationGroupId },
        currentMinute: START_MINUTE,
      }, tokyoSunriseRouteId, 20), tokyoSunriseRouteId)
      : [];
    const tokyoSunriseUmbrellas = buildCoupledTrainRows(entriesAt('東京'), null)
      .filter((row) => row.kind === 'coupled' && row.label === 'サンライズ瀬戸・出雲');
    const tokyoSunriseTerminals = new Set(tokyoSunriseUmbrellas.flatMap((row) =>
      row.portions.map((item) => displayNameForGroup(item.row.trip.stopTimes.at(-1)?.stationGroupId || ''))
    ));
    if (
      tokyoSunriseChoices.length !== 1 ||
      tokyoSunriseChoices[0]?.route !== 'サンライズ瀬戸・出雲' ||
      tokyoSunriseChoices[0]?.trainCount !== 1 ||
      tokyoSunriseUmbrellas.length !== 1 ||
      tokyoSunrisePlayableRows.length !== 1 ||
      tokyoSunrisePlayableRows[0]?.kind !== 'coupled' ||
      tokyoSunrisePlayableRows[0]?.label !== 'サンライズ瀬戸・出雲' ||
      !tokyoSunriseTerminals.has('高松') ||
      !tokyoSunriseTerminals.has('出雲市')
    ) {
      anomalies.push({
        kind: 'sunrise_seto_izumo_tokyo_umbrella_regression',
        reason: 'Tokyo should show one Sunrise Seto/Izumo umbrella train; the Seto portion must remain available to Takamatsu and Izumo must remain available to Izumoshi.',
        choices: tokyoSunriseChoices,
        umbrellas: tokyoSunriseUmbrellas.map((row) => ({
          label: row.label,
          departure: row.departureHhmm,
          portions: row.portions.map((item) => ({
            label: item.portion?.label || formatTripLabel(item.row.trip),
            trip: formatTripLabel(item.row.trip),
            terminal: displayNameForGroup(item.row.trip.stopTimes.at(-1)?.stationGroupId || ''),
          })),
        })),
        playableRows: tokyoSunrisePlayableRows.map((row) => ({
          kind: row.kind,
          label: row.label || formatTripLabel(row.entry?.trip),
          departure: row.departureHhmm || row.entry?.departureHhmm,
        })),
      });
    }
    const seasonalSunriseTrips = allTrips
      .filter((trip) => /サンライズ/u.test(formatTripLabel(trip)))
      .filter((trip) => /(?:91|92|9011|9012)/u.test([
        formatTripLabel(trip),
        trip.serviceNumber,
        trip.displayName,
        trip.serviceName,
      ].filter(Boolean).join(' ')));
    if (seasonalSunriseTrips.length) {
      anomalies.push({
        kind: 'sunrise_seasonal_rows_visible_in_regular_gameplay',
        reason: 'Seasonal Sunrise 91/92 rows should not inflate the regular weekday gameplay Sunrise route choices.',
        trips: seasonalSunriseTrips.slice(0, 8).map((trip) => ({
          id: trip.id,
          label: formatTripLabel(trip),
        })),
      });
    }
    function sunrisePlayableRowsAt(stationName, prefectureName = null) {
      const stationGroupId = prefectureName
        ? stationIdByNameAndPrefecture(stationName, prefectureName)
        : firstStationIdByName(stationName);
      if (!stationGroupId) return { stationName, prefectureName, missingStation: true, choices: [], rows: [] };
      const preview = {
        currentState: { kind: 'NODE', stationGroupId },
        currentMinute: START_MINUTE,
      };
      const stationEntries = departuresForStationGroup(stationGroupId, START_MINUTE, { includeTransferEquivalents: true });
      const choices = routeChoicesFromDepartures(stationEntries)
        .filter((choice) => routeTitle(choice.routeId).includes('サンライズ'));
      const rows = choices.flatMap((choice) =>
        buildCoupledTrainRows(availableRouteDepartures(preview, choice.routeId, 20), choice.routeId)
      );
      return {
        stationName,
        prefectureName,
        stationGroupId,
        choices: choices.map((choice) => ({
          route: routeTitle(choice.routeId),
          trainCount: choice.trainCount,
          firstDeparture: choice.firstDepartureHhmm,
        })),
        rows: rows.map((row) => {
          if (row.kind === 'coupled') {
            return {
              kind: 'coupled',
              label: row.label,
              departure: row.departureHhmm,
              terminals: row.portions.map((item) => displayNameForGroup(item.row.trip.stopTimes.at(-1)?.stationGroupId || '')),
              portions: row.portions.map((item) => item.portion?.label || formatTripLabel(item.row.trip)),
            };
          }
          return {
            kind: 'trip',
            label: formatTripLabel(row.entry?.trip),
            departure: row.entry?.departureHhmm,
            terminal: displayNameForGroup(row.entry?.trip?.stopTimes?.at(-1)?.stationGroupId || ''),
          };
        }),
      };
    }
    const sunriseStationCases = [
      {
        name: '東京',
        expectCoupled: true,
        expectTerminals: ['高松', '出雲市'],
        expectOnlyOneRow: true,
      },
      {
        name: '横浜',
        expectCoupled: true,
        expectTerminals: ['高松', '出雲市'],
        expectTokyoBound: true,
      },
      {
        name: '高松',
        prefecture: '香川県',
        expectSingleTripLabel: 'サンライズ瀬戸',
        expectSingleTripTerminal: '東京',
      },
      {
        name: '出雲市',
        expectSingleTripLabel: 'サンライズ出雲',
        expectSingleTripTerminal: '東京',
      },
      {
        name: '岡山',
        expectCoupled: true,
        expectTerminals: ['高松', '出雲市'],
      },
    ];
    const sunriseStationFailures = [];
    for (const testCase of sunriseStationCases) {
      const summary = sunrisePlayableRowsAt(testCase.name, testCase.prefecture || null);
      const coupledRows = summary.rows.filter((row) => row.kind === 'coupled' && row.label === 'サンライズ瀬戸・出雲');
      const tripRows = summary.rows.filter((row) => row.kind === 'trip');
      const terminals = new Set(summary.rows.flatMap((row) => row.kind === 'coupled' ? row.terminals : [row.terminal]));
      const hasExpectedTerminals = (testCase.expectTerminals || []).every((terminal) => terminals.has(terminal));
      const hasExpectedSingleTrip = !testCase.expectSingleTripLabel || (
        tripRows.length === 1 &&
        tripRows[0].label.includes(testCase.expectSingleTripLabel) &&
        tripRows[0].terminal === testCase.expectSingleTripTerminal
      );
      const hasTokyoBound = !testCase.expectTokyoBound || tripRows.some((row) => row.terminal === '東京');
      const rowCountOk = !testCase.expectOnlyOneRow || summary.rows.length === 1;
      if (
        summary.missingStation ||
        !summary.choices.length ||
        (testCase.expectCoupled && !coupledRows.length) ||
        !hasExpectedTerminals ||
        !hasExpectedSingleTrip ||
        !hasTokyoBound ||
        !rowCountOk
      ) {
        sunriseStationFailures.push({
          testCase,
          summary,
        });
      }
    }
    if (sunriseStationFailures.length) {
      anomalies.push({
        kind: 'sunrise_seto_izumo_nationwide_direction_regression',
        reason: 'Sunrise Seto/Izumo must work in both directions and at shared, branch, and split/join stations.',
        failures: sunriseStationFailures,
      });
    }
    if (shinkansenUmbrellaSamples.length) {
      anomalies.push({
        kind: 'shinkansen_coupled_umbrella_visible',
        reason: 'Shinkansen coupled services are the exception: show each portion under its own Shinkansen route, but keep same_train equivalence for capture.',
        samples: shinkansenUmbrellaSamples,
      });
    }
    if (!shinkansenEquivalentEdgeCount) {
      anomalies.push({
        kind: 'shinkansen_coupled_same_train_equivalence_missing',
        reason: 'Even though Shinkansen coupled services do not use the umbrella display rule, their portions must still count as same_train during the shared segment.',
      });
    }
    }

    return {
      checkedAt: new Date().toISOString(),
      auditOptions,
      enabledStages: [...enabledStages],
      timings: {
        ...timings,
        focusedRuleScanMs: performance.now() - focusedRuleScanStartedAtMs,
        totalAuditMs: performance.now() - timings.startedAtMs,
      },
      stationCount: state.stationGroupById.size,
      tripCount: state.tripById?.size || 0,
      knownStationChoices,
      globalChoiceScan,
      globalTrainLabelScan,
      duplicateRouteTitleScan,
      miniShinkansenBranchScan,
      coupledScan: {
        registryEntryCount: (state.coupledServiceEntries || []).length,
        equivalentTripCount: coupledEquivalentTripCount,
        equivalentEdgeCount: coupledEquivalentEdgeCount,
        shinkansenEquivalentEdgeCount,
        umbrellaSamples: coupledUmbrellaSamples.slice(0, 20),
      },
      anomalyCount: anomalies.length,
      anomalies: anomalies.slice(0, 80),
    };
  }, auditOptions);
}

function resultForStage(stageResults, stageName) {
  return stageResults.find((result) => (result.enabledStages || []).includes(stageName)) || null;
}

function mergeStageResults(stageResults, auditOptions) {
  const globalResult = resultForStage(stageResults, 'global') || stageResults[0] || {};
  const duplicateResult = resultForStage(stageResults, 'duplicates') || stageResults[0] || {};
  const knownResult = resultForStage(stageResults, 'known') || stageResults[0] || {};
  const miniShinkansenResult = resultForStage(stageResults, 'mini-shinkansen') || stageResults[0] || {};
  const focusedResult = resultForStage(stageResults, 'focused') || stageResults[0] || {};
  const anomalies = stageResults.flatMap((result) => result.anomalies || []);
  return {
    checkedAt: new Date().toISOString(),
    auditOptions,
    enabledStages: [...auditOptions.stages],
    loadTimings: {
      stageRuns: stageResults.map((result) => ({
        stages: result.enabledStages || [],
        ...(result.loadTimings || {}),
      })),
    },
    timings: {
      globalChoiceAndLabelScanMs: globalResult.timings?.globalChoiceAndLabelScanMs || 0,
      duplicateRouteTitleScanMs: duplicateResult.timings?.duplicateRouteTitleScanMs || 0,
      knownStationScanMs: knownResult.timings?.knownStationScanMs || 0,
      miniShinkansenBranchScanMs: miniShinkansenResult.timings?.miniShinkansenBranchScanMs || 0,
      focusedRuleScanMs: focusedResult.timings?.focusedRuleScanMs || 0,
      totalAuditMs: stageResults.reduce((sum, result) => sum + (result.timings?.totalAuditMs || 0), 0),
    },
    stationCount: Math.max(...stageResults.map((result) => result.stationCount || 0), 0),
    tripCount: Math.max(...stageResults.map((result) => result.tripCount || 0), 0),
    knownStationChoices: knownResult.knownStationChoices || {},
    globalChoiceScan: globalResult.globalChoiceScan || {},
    globalTrainLabelScan: globalResult.globalTrainLabelScan || {},
    duplicateRouteTitleScan: duplicateResult.duplicateRouteTitleScan || {},
    miniShinkansenBranchScan: miniShinkansenResult.miniShinkansenBranchScan || {},
    coupledScan: focusedResult.coupledScan || {},
    anomalyCount: anomalies.length,
    anomalies: anomalies.slice(0, 80),
  };
}

async function runAuditOnFreshPage(pageUrl, auditOptions) {
  const { browser, page, loadTimings } = await loadPage(pageUrl);
  try {
    const result = await auditRouteChoices(page, auditOptions);
    result.loadTimings = loadTimings;
    return result;
  } finally {
    await browser.close();
  }
}

async function runGlobalStageChunkedOnSinglePage(pageUrl, auditOptions) {
  const chunkSize = Math.max(1, Number(auditOptions.tripChunkSize || 20000));
  const { browser, page, loadTimings } = await loadPage(pageUrl);
  const chunkResults = [];
  try {
    let tripStart = Math.max(0, Number(auditOptions.tripStart || 0));
    while (true) {
      process.stderr.write(`[v4_route_choice_audit] global chunk tripStart=${tripStart} tripLimit=${chunkSize}\n`);
      const chunkResult = await auditRouteChoices(page, {
        ...auditOptions,
        stages: ['global'],
        tripStart,
        tripLimit: chunkSize,
      });
      chunkResult.loadTimings = chunkResults.length === 0 ? loadTimings : { reusedPage: true };
      chunkResults.push(chunkResult);
      const selectedTripCount = chunkResult.globalChoiceScan?.selectedTripCount || 0;
      const tripCount = chunkResult.globalChoiceScan?.tripCount || 0;
      if (selectedTripCount < chunkSize || tripStart + selectedTripCount >= tripCount) break;
      tripStart += chunkSize;
    }
  } finally {
    await browser.close();
  }
  return mergeGlobalStageChunkResults(chunkResults, auditOptions);
}

function mergeGlobalStageChunkResults(chunkResults, auditOptions) {
  const first = chunkResults[0] || {};
  const sum = (selector) => chunkResults.reduce((total, result) => total + (selector(result) || 0), 0);
  const mergeSamples = (selector) => chunkResults.flatMap((result) => selector(result) || []).slice(0, 80);
  const globalChoiceScan = {
    ...(first.globalChoiceScan || {}),
    tripStart: auditOptions.tripStart || 0,
    tripLimit: auditOptions.tripLimit,
    tripCount: Math.max(...chunkResults.map((result) => result.globalChoiceScan?.tripCount || 0), 0),
    selectedTripCount: sum((result) => result.globalChoiceScan?.selectedTripCount),
    checkedRows: sum((result) => result.globalChoiceScan?.checkedRows),
    checkedChoices: sum((result) => result.globalChoiceScan?.checkedChoices),
    segmentMismatchCount: sum((result) => result.globalChoiceScan?.segmentMismatchCount),
    virtualOutsideAllowedStationCount: sum((result) => result.globalChoiceScan?.virtualOutsideAllowedStationCount),
    genericRouteLabelCount: sum((result) => result.globalChoiceScan?.genericRouteLabelCount),
    yokohamaThroughRemoteRouteCount: sum((result) => result.globalChoiceScan?.yokohamaThroughRemoteRouteCount),
    routeLikeNamedChoiceCount: sum((result) => result.globalChoiceScan?.routeLikeNamedChoiceCount),
    nonKeikyuAirportLineKkSymbolCount: sum((result) => result.globalChoiceScan?.nonKeikyuAirportLineKkSymbolCount),
    choiceTraceMismatchCount: sum((result) => result.globalChoiceScan?.choiceTraceMismatchCount),
    currentPhysicalMismatchCount: sum((result) => result.globalChoiceScan?.currentPhysicalMismatchCount),
    highlightTraceMismatchCount: sum((result) => result.globalChoiceScan?.highlightTraceMismatchCount),
    samples: mergeSamples((result) => result.globalChoiceScan?.samples),
    skipped: false,
  };
  const globalTrainLabelScan = {
    ...(first.globalTrainLabelScan || {}),
    tripStart: auditOptions.tripStart || 0,
    tripLimit: auditOptions.tripLimit,
    tripCount: globalChoiceScan.tripCount,
    selectedTripCount: globalChoiceScan.selectedTripCount,
    checkedLabels: sum((result) => result.globalTrainLabelScan?.checkedLabels),
    rawNumberedLineLabelCount: sum((result) => result.globalTrainLabelScan?.rawNumberedLineLabelCount),
    limitedOrShinkansenMissingNumberCount: sum((result) => result.globalTrainLabelScan?.limitedOrShinkansenMissingNumberCount),
    throughDirectionLabelMismatchCount: sum((result) => result.globalTrainLabelScan?.throughDirectionLabelMismatchCount),
    meitetsuLabelFormatMismatchCount: sum((result) => result.globalTrainLabelScan?.meitetsuLabelFormatMismatchCount),
    namedLimitedExpressNotSeparatedCount: sum((result) => result.globalTrainLabelScan?.namedLimitedExpressNotSeparatedCount),
    limitedExpressGoSuffixCount: sum((result) => result.globalTrainLabelScan?.limitedExpressGoSuffixCount),
    asakusaKeikyuAirportLabelMismatchCount: sum((result) => result.globalTrainLabelScan?.asakusaKeikyuAirportLabelMismatchCount),
    checkedThroughPreviewTexts: sum((result) => result.globalTrainLabelScan?.checkedThroughPreviewTexts),
    throughDisplayTextCount: sum((result) => result.globalTrainLabelScan?.throughDisplayTextCount),
    samples: mergeSamples((result) => result.globalTrainLabelScan?.samples),
    skipped: false,
  };
  const anomalies = chunkResults.flatMap((result) => result.anomalies || []);
  return {
    checkedAt: new Date().toISOString(),
    auditOptions: { ...auditOptions, stages: ['global'] },
    enabledStages: ['global'],
    loadTimings: {
      chunks: chunkResults.map((result) => ({
        tripStart: result.globalChoiceScan?.tripStart,
        tripLimit: result.globalChoiceScan?.tripLimit,
        ...(result.loadTimings || {}),
      })),
    },
    timings: {
      globalChoiceAndLabelScanMs: sum((result) => result.timings?.globalChoiceAndLabelScanMs),
      duplicateRouteTitleScanMs: 0,
      knownStationScanMs: 0,
      miniShinkansenBranchScanMs: 0,
      focusedRuleScanMs: 0,
      totalAuditMs: sum((result) => result.timings?.totalAuditMs),
    },
    stationCount: Math.max(...chunkResults.map((result) => result.stationCount || 0), 0),
    tripCount: Math.max(...chunkResults.map((result) => result.tripCount || 0), 0),
    knownStationChoices: {},
    globalChoiceScan,
    globalTrainLabelScan,
    duplicateRouteTitleScan: first.duplicateRouteTitleScan || {},
    miniShinkansenBranchScan: first.miniShinkansenBranchScan || {},
    coupledScan: {},
    anomalyCount: anomalies.length,
    anomalies: anomalies.slice(0, 80),
  };
}

async function runStageAudit(pageUrl, auditOptions, stage) {
  process.stderr.write(`[v4_route_choice_audit] stage=${stage} start\n`);
  if (stage !== 'global' || auditOptions.tripLimit !== null) {
    const result = await runAuditOnFreshPage(pageUrl, { ...auditOptions, stages: [stage] });
    process.stderr.write(`[v4_route_choice_audit] stage=${stage} done anomalies=${result.anomalyCount || 0}\n`);
    return result;
  }
  const result = await runGlobalStageChunkedOnSinglePage(pageUrl, auditOptions);
  process.stderr.write(`[v4_route_choice_audit] stage=${stage} done anomalies=${result.anomalyCount || 0}\n`);
  return result;
}

(async () => {
  const args = parseArgs(process.argv);
  const auditOptions = {
    tripStart: parseIntegerOption(args['trip-start'], 0),
    tripLimit: parseIntegerOption(args['trip-limit'], null),
    tripChunkSize: parseIntegerOption(args['trip-chunk-size'], 20000),
    stationStart: parseIntegerOption(args['station-start'], 0),
    stationLimit: parseIntegerOption(args['station-limit'], null),
    stages: parseStagesOption(args.stages),
  };
  const stageResults = [];
  for (const stage of auditOptions.stages) {
    stageResults.push(await runStageAudit(args['page-url'], auditOptions, stage));
  }
  const result = stageResults.length === 1 ? stageResults[0] : mergeStageResults(stageResults, auditOptions);
  const json = JSON.stringify(result, null, 2);
  if (args.output && args.output !== true) fs.writeFileSync(args.output, `${json}\n`);
  process.stdout.write(`${json}\n`);
  if (result.anomalyCount) process.exitCode = 1;
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
