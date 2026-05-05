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

function parseIntegerOption(value, defaultValue = null) {
  if (value === undefined || value === null || value === '') return defaultValue;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : defaultValue;
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

    const anomalies = [];
    const timings = { startedAtMs: performance.now() };
    const allowedVirtualRouteStations = {
      VIRTUAL_JR_EAST_UENO_TOKYO: new Set(['東京', '上野']),
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
      samples: [],
    };
    const duplicateRouteTitleScan = {
      checkedStations: 0,
      duplicateStationTitleCount: 0,
      samples: [],
    };
    const allUenoTokyoChoiceStationSet = new Set();
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
    function routeTraceScanEntries() {
      const entries = [];
      const trips = [...state.tripById.values()];
      const selectedTrips = tripLimit === null ? trips.slice(tripStart) : trips.slice(tripStart, tripStart + tripLimit);
      selectedTrips.forEach((trip, offset) => {
        const stops = (trip.stopTimes || []).filter((stop) => Number.isFinite(stop.sequence));
        for (let index = 0; index < stops.length - 1; index += 1) {
          const stop = stops[index];
          const departureMinute = stopDepartureMinutes(stop);
          if (departureMinute < START_MINUTE) continue;
          const stationGroupId = stop.stationGroupId;
          const group = state.stationGroupById.get(stationGroupId);
          entries.push({
            stationName: group?.names?.ja || group?.primaryName || stationGroupId,
            entry: {
              trip,
              stop,
              boardStop: stop,
              departureMinute,
              routeIds: boardableRouteIdsForStop(trip, stop),
              queryStationGroupId: stationGroupId,
            },
          });
        }
      });
      return {
        entries,
        tripCount: trips.length,
        selectedTripCount: selectedTrips.length,
        tripStart,
        tripLimit,
      };
    }
    const routeTraceScan = routeTraceScanEntries();
    Object.assign(globalChoiceScan, {
      tripStart: routeTraceScan.tripStart,
      tripLimit: routeTraceScan.tripLimit,
      tripCount: routeTraceScan.tripCount,
      selectedTripCount: routeTraceScan.selectedTripCount,
    });
    for (const { stationName, entry } of routeTraceScan.entries) {
        const nextStop = nextStopFor(entry);
        if (!nextStop) continue;
        globalChoiceScan.checkedRows += 1;
        const routeIds = routeChoiceIdsForDeparture(entry);
        globalChoiceScan.checkedChoices += routeIds.length;
        const currentSegmentRouteId = tracedRouteIdForTripSegment(entry.trip, entry.stop, nextStop);
        const futureTraceRouteIds = futureTraceRouteIdsForEntry(entry, currentSegmentRouteId);
        const currentPhysicalRouteIds = currentPhysicalRouteIdsForEntry(entry, currentSegmentRouteId, nextStop);
        routeIds.forEach((routeId) => {
          const label = formatTripLabelForBoarding(entry, routeId);
          globalTrainLabelScan.checkedLabels += 1;
          if (routeTitle(routeId) === '上野東京ライン') {
            allUenoTokyoChoiceStationSet.add(stationName);
          }
          const namedTrainRouteId = namedTrainChoiceRouteId(entry.trip);
          if (namedTrainRouteId && routeId !== namedTrainRouteId) {
            globalTrainLabelScan.namedLimitedExpressNotSeparatedCount += 1;
            addGlobalTrainLabelSample('named_limited_express_not_separated', stationName, entry, routeId, label);
          }
          if (routeTitle(routeId) === '路線') {
            globalChoiceScan.genericRouteLabelCount += 1;
            addGlobalChoiceSample('generic_route_label', stationName, entry, routeId, nextStop);
          }
          const choiceRoute = state.routeById.get(routeId);
          const choiceRouteTitle = routeTitle(routeId);
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
            ['東京メトロ副都心線', '東京メトロ有楽町線', '京急本線'].includes(routeTitle(routeId)) &&
            ['13号線副都心線', '8号線有楽町線'].includes(entry.trip?.serviceName || '')
          ) {
            globalChoiceScan.yokohamaThroughRemoteRouteCount += 1;
            addGlobalChoiceSample('yokohama_through_remote_route', stationName, entry, routeId, nextStop);
          }
          if (/\d+号線/u.test(label)) {
            globalTrainLabelScan.rawNumberedLineLabelCount += 1;
            addGlobalTrainLabelSample('raw_numbered_line_label', stationName, entry, routeId, label);
          }
          const publicNumber = publicTripNumber(entry.trip);
          const shouldDisplayPublicNumber = isShinkansenTrip(entry.trip) ||
            (isLimitedExpressTrip(entry.trip) && looksLikePublicTrainNumber(publicNumber));
          if (
            publicNumber &&
            shouldDisplayPublicNumber &&
            !String(label).includes(publicNumber)
          ) {
            globalTrainLabelScan.limitedOrShinkansenMissingNumberCount += 1;
            addGlobalTrainLabelSample('limited_or_shinkansen_missing_number', stationName, entry, routeId, label);
          }
          if (isLimitedExpressTrip(entry.trip) && !isShinkansenTrip(entry.trip) && /\d{1,4}号/u.test(label)) {
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
          const directionLabel = directionRouteId ? routeTitle(directionRouteId) : '';
          const terminalName = displayNameForGroup((entry.trip?.stopTimes || []).at(-1)?.stationGroupId || '');
          if (
            routeTitle(routeId) === '都営浅草線' &&
            ['天空橋', '羽田空港第１・第２ターミナル', '羽田空港第３ターミナル'].includes(terminalName) &&
            label !== '京急空港線'
          ) {
            globalTrainLabelScan.asakusaKeikyuAirportLabelMismatchCount += 1;
            addGlobalTrainLabelSample('asakusa_keikyu_airport_label_mismatch', stationName, entry, routeId, label);
          }
          const directionTraceRouteCount = new Set((entry.trip?.lineTrace || [])
            .map((trace) => trace?.routeId)
            .filter((candidateRouteId) => candidateRouteId && state.routeById.has(candidateRouteId) && !isThroughServiceTransferAlias(candidateRouteId))).size;
          if (
            directionTraceRouteCount >= 2 &&
            directionLabel &&
            !isShinkansenTrip(entry.trip) &&
            !isLimitedExpressTrip(entry.trip) &&
            !(stationName === '米原' && routeTitle(routeId) === '東海道線' && label === '東海道線') &&
            label !== directionLabel
          ) {
            globalTrainLabelScan.throughDirectionLabelMismatchCount += 1;
            addGlobalTrainLabelSample('through_direction_label_mismatch', stationName, entry, routeId, label);
          }
          if (isMeitetsuTrip(entry.trip)) {
            if (!/^[^（）()]+線$/u.test(label) || /^\d+号線/u.test(label)) {
              globalTrainLabelScan.meitetsuLabelFormatMismatchCount += 1;
              addGlobalTrainLabelSample('meitetsu_label_format_mismatch', stationName, entry, routeId, label);
            }
          }
          const allowedStations = allowedVirtualRouteStations[routeId];
          const routeChoiceMatchesTrace = (
            routeId === entry.trip?.routeId ||
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
            if (isRouteLikeNamedTrainLabel(routeTitle(routeId))) {
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
    });
    for (const [stationGroupId, group] of selectedDuplicateStations) {
      const stationName = group.names?.ja || group.primaryName || stationGroupId;
      duplicateRouteTitleScan.checkedStations += 1;
      const choices = routeChoicesFromDepartures(departuresForStationGroup(stationGroupId, START_MINUTE, { includeTransferEquivalents: true }));
      const titleCounts = new Map();
      choices.forEach((choice) => titleCounts.set(routeTitle(choice.routeId), (titleCounts.get(routeTitle(choice.routeId)) || 0) + 1));
      const duplicateTitles = [...titleCounts.entries()].filter(([, count]) => count > 1);
      if (!duplicateTitles.length) continue;
      duplicateRouteTitleScan.duplicateStationTitleCount += duplicateTitles.length;
      if (duplicateRouteTitleScan.samples.length < 80) {
        duplicateRouteTitleScan.samples.push({
          station: stationName,
          duplicates: duplicateTitles.map(([title, count]) => ({ title, count })),
          choices: choices.map((choice) => ({
            route: routeTitle(choice.routeId),
            subtitle: routeChoiceSubtitle(choice),
            firstDeparture: choice.firstDepartureHhmm,
            trainCount: choice.trainCount,
          })),
        });
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
      globalTrainLabelScan.asakusaKeikyuAirportLabelMismatchCount
    ) {
      anomalies.push({
        kind: 'global_selected_train_label_scan',
        reason: 'Selected-train labels must not expose raw x号線 names, limited express/Shinkansen labels must include public train numbers when available, limited express labels must not append 号 after the train number, ordinary through-running labels including Meitetsu must follow the direction-side line, Meitetsu labels must not use parentheses, and named limited-express/named train services must be separated as their own route choices.',
        ...globalTrainLabelScan,
      });
    }
    const knownStationScanStartedAtMs = performance.now();
    const knownStationChoices = Object.fromEntries(
      [
        '東京', '上野', '品川', '新橋', '大宮', '青梅', '八王子', '米原',
        '敦賀', '京都', '新大阪', '白浜', '新宿', '大船', '成田空港',
        '松本', '大月', '蘇我', '五井', '木更津', '上総一ノ宮', '成田', '佐倉',
      ].map((stationName) => [stationName, choicesAt(stationName)])
    );
    const routeChoiceTitles = Object.fromEntries(
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

    const forbiddenTokyoNorthTrunkChoices = new Set(['東北線', '東北本線', '宇都宮線', '高崎線', '常磐線']);
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
    timings.knownStationScanMs = performance.now() - knownStationScanStartedAtMs;
    const focusedRuleScanStartedAtMs = performance.now();
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

    const coupledUmbrellaSamples = [];
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
    const requiredCoupledUmbrellaLabels = ['成田エクスプレス', '関空快速・紀州路快速'];
    const missingCoupledUmbrellaLabels = requiredCoupledUmbrellaLabels.filter((requiredLabel) =>
      !coupledUmbrellaSamples.some((sample) => sample.label === requiredLabel)
    );
    const coupledEquivalentTripCount = state.coupledEquivalentsByTripId?.size || 0;
    const coupledEquivalentEdgeCount = [...(state.coupledEquivalentsByTripId?.values() || [])]
      .reduce((sum, items) => sum + items.length, 0);
    const shinkansenEquivalentEdgeCount = [...(state.coupledEquivalentsByTripId?.values() || [])]
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
        reason: 'From coupled toward uncoupled direction, non-Shinkansen train choices should expose an umbrella A・B row before portion selection.',
      });
    }
    if (missingCoupledUmbrellaLabels.length) {
      anomalies.push({
        kind: 'reviewed_non_shinkansen_coupled_umbrella_missing',
        reason: 'Non-Shinkansen coupled services such as Narita Express and Kansai/Kishuji rapid must keep the umbrella train row + portion picker rule.',
        missingLabels: missingCoupledUmbrellaLabels,
        samples: coupledUmbrellaSamples,
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

    return {
      checkedAt: new Date().toISOString(),
      auditOptions,
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

(async () => {
  const args = parseArgs(process.argv);
  const auditOptions = {
    tripStart: parseIntegerOption(args['trip-start'], 0),
    tripLimit: parseIntegerOption(args['trip-limit'], null),
    stationStart: parseIntegerOption(args['station-start'], 0),
    stationLimit: parseIntegerOption(args['station-limit'], null),
  };
  const { browser, page, loadTimings } = await loadPage(args['page-url']);
  try {
    const result = await auditRouteChoices(page, auditOptions);
    result.loadTimings = loadTimings;
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    if (result.anomalyCount) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
