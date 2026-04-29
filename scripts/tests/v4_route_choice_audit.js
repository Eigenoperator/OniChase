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
    };
    const globalChoiceScan = {
      checkedRows: 0,
      checkedChoices: 0,
      segmentMismatchCount: 0,
      virtualOutsideAllowedStationCount: 0,
      genericRouteLabelCount: 0,
      yokohamaThroughRemoteRouteCount: 0,
      samples: [],
    };
    const globalTrainLabelScan = {
      checkedLabels: 0,
      rawNumberedLineLabelCount: 0,
      limitedOrShinkansenMissingNumberCount: 0,
      throughDirectionLabelMismatchCount: 0,
      meitetsuLabelFormatMismatchCount: 0,
      yokohamaThroughRemoteLabelCount: 0,
      samples: [],
    };
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
    for (const [stationGroupId, group] of state.stationGroupById.entries()) {
      const stationName = group.names?.ja || group.primaryName || stationGroupId;
      for (const entry of departuresForStationGroup(stationGroupId, START_MINUTE)) {
        const nextStop = nextStopFor(entry);
        if (!nextStop) continue;
        globalChoiceScan.checkedRows += 1;
        const routeIds = routeChoiceIdsForDeparture(entry);
        globalChoiceScan.checkedChoices += routeIds.length;
        routeIds.forEach((routeId) => {
          const label = formatTripLabelForBoarding(entry, routeId);
          globalTrainLabelScan.checkedLabels += 1;
          if (routeTitle(routeId) === '路線') {
            globalChoiceScan.genericRouteLabelCount += 1;
            addGlobalChoiceSample('generic_route_label', stationName, entry, routeId, nextStop);
          }
          if (
            stationName === '横浜' &&
            ['東京メトロ副都心線', '東京メトロ有楽町線', '京急本線'].includes(routeTitle(routeId)) &&
            ['13号線副都心線', '8号線有楽町線'].includes(entry.trip?.serviceName || '')
          ) {
            globalChoiceScan.yokohamaThroughRemoteRouteCount += 1;
            addGlobalChoiceSample('yokohama_through_remote_route', stationName, entry, routeId, nextStop);
          }
          if (
            stationName === '横浜' &&
            ['13号線副都心線', '8号線有楽町線'].includes(entry.trip?.serviceName || '') &&
            ['東急東横線', 'みなとみらい線'].includes(routeTitle(routeId)) &&
            label !== routeTitle(routeId)
          ) {
            globalTrainLabelScan.yokohamaThroughRemoteLabelCount += 1;
            addGlobalTrainLabelSample('yokohama_through_remote_label', stationName, entry, routeId, label);
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
          const selectedJrRouteId = selectedJrNorthernTrunkLabelRouteId(entry, routeId);
          const adjacentDirectionRouteId = adjacentDirectionRouteIdForChoice(entry);
          const directionRouteId = selectedJrRouteId ||
            (adjacentDirectionRouteId === routeId && !isJrRoute(state.routeById.get(routeId))
            ? adjacentDirectionRouteId
            : directionTerminalRouteIdForTrainLabel(entry, routeId));
          const directionLabel = directionRouteId ? routeTitle(directionRouteId) : '';
          const directionTraceRouteCount = new Set((entry.trip?.lineTrace || [])
            .map((trace) => trace?.routeId)
            .filter((candidateRouteId) => candidateRouteId && state.routeById.has(candidateRouteId) && !isThroughServiceTransferAlias(candidateRouteId))).size;
          if (
            directionTraceRouteCount >= 2 &&
            directionLabel &&
            !isShinkansenTrip(entry.trip) &&
            !isLimitedExpressTrip(entry.trip) &&
            !isMeitetsuTrip(entry.trip) &&
            label !== directionLabel
          ) {
            globalTrainLabelScan.throughDirectionLabelMismatchCount += 1;
            addGlobalTrainLabelSample('through_direction_label_mismatch', stationName, entry, routeId, label);
          }
          if (isMeitetsuTrip(entry.trip)) {
            const tripLabel = routeTitle(entry.trip.routeId);
            if (!/^名鉄（.+線）$/u.test(label) || label !== tripLabel) {
              globalTrainLabelScan.meitetsuLabelFormatMismatchCount += 1;
              addGlobalTrainLabelSample('meitetsu_label_format_mismatch', stationName, entry, routeId, label);
            }
          }
          if (isShinkansenCorridorRoute(routeId)) return;
          const allowedStations = allowedVirtualRouteStations[routeId];
          if (allowedStations) {
            if (!allowedStations.has(stationName)) {
              globalChoiceScan.virtualOutsideAllowedStationCount += 1;
              addGlobalChoiceSample('virtual_outside_allowed_station', stationName, entry, routeId, nextStop);
            }
            return;
          }
          if (!routeMatchesTripAdjacentSegment(routeId, entry.trip, entry.stop, nextStop)) {
            globalChoiceScan.segmentMismatchCount += 1;
            addGlobalChoiceSample('choice_not_current_next_segment', stationName, entry, routeId, nextStop);
          }
        });
      }
    }
    if (
      globalChoiceScan.segmentMismatchCount ||
      globalChoiceScan.virtualOutsideAllowedStationCount ||
      globalChoiceScan.genericRouteLabelCount ||
      globalChoiceScan.yokohamaThroughRemoteRouteCount
    ) {
      anomalies.push({
        kind: 'global_route_choice_segment_scan',
        reason: 'Every player-facing route choice must either be an allowed virtual corridor at that station or serve the current boarding stop -> next stop segment, must not expose a generic route label, and must not expose remote through-service routes at Yokohama.',
        ...globalChoiceScan,
      });
    }
    if (
      globalTrainLabelScan.rawNumberedLineLabelCount ||
      globalTrainLabelScan.limitedOrShinkansenMissingNumberCount ||
      globalTrainLabelScan.throughDirectionLabelMismatchCount ||
      globalTrainLabelScan.meitetsuLabelFormatMismatchCount ||
      globalTrainLabelScan.yokohamaThroughRemoteLabelCount
    ) {
      anomalies.push({
        kind: 'global_selected_train_label_scan',
        reason: 'Selected-train labels must not expose raw x号線 names, limited express/Shinkansen labels must include public train numbers when available, ordinary through-running labels must follow the direction-side line, Meitetsu train labels must stay on their own Meitetsu line, and Yokohama through-running labels must not expose remote lines.',
        ...globalTrainLabelScan,
      });
    }
    const knownStationChoices = Object.fromEntries(
      ['東京', '上野', '品川', '新橋', '大宮', '青梅', '八王子'].map((stationName) => [stationName, choicesAt(stationName)])
    );
    const routeChoiceTitles = Object.fromEntries(
      Object.entries(knownStationChoices).map(([stationName, choices]) => [
        stationName,
        new Set(choices.map((choice) => choice.route)),
      ])
    );

    const allUenoTokyoChoiceStations = [];
    for (const [stationGroupId, group] of state.stationGroupById.entries()) {
      const choices = routeChoicesFromDepartures(departuresForStationGroup(stationGroupId, START_MINUTE));
      if (choices.some((choice) => routeTitle(choice.routeId) === '上野東京ライン')) {
        allUenoTokyoChoiceStations.push(group.names?.ja || group.primaryName || stationGroupId);
      }
    }
    const unexpectedUenoTokyoStations = [...new Set(allUenoTokyoChoiceStations)]
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
      東京: ['東海道・山陽新幹線', '東北・北海道新幹線', '上越新幹線', '北陸新幹線'],
      品川: ['東海道・山陽新幹線'],
      大宮: ['東北・北海道新幹線', '上越新幹線', '北陸新幹線'],
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

    return {
      checkedAt: new Date().toISOString(),
      stationCount: state.stationGroupById.size,
      tripCount: state.tripById?.size || 0,
      knownStationChoices,
      globalChoiceScan,
      globalTrainLabelScan,
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
