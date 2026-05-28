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

function parseIntegerOption(value, defaultValue) {
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

async function auditSparseRouteChoices(page, auditOptions) {
  return page.evaluate((auditOptions) => {
    const startMinute = hhmmToMinutes(auditOptions.startTime || '06:00');
    const maxTrainCount = Math.max(1, Number(auditOptions.maxTrainCount || 2));
    const maxSamples = Math.max(1, Number(auditOptions.maxSamples || 120));
    const stationLimit = auditOptions.stationLimit === null || auditOptions.stationLimit === undefined || auditOptions.stationLimit === ''
      ? null
      : Math.max(0, Number(auditOptions.stationLimit));
    const stationOffset = Math.max(0, Number(auditOptions.stationOffset || 0));
    const REVIEWED_SPARSE_NAVITIME_THROUGH_ALLOW = new Set([
      '中村|土佐くろしお鉄道宿毛線',
      '宿毛|土佐くろしお鉄道宿毛線',
    ]);
    const ROUTE_LIKE_TITLE_RE = /(?:線|本線|支線|鉄道|鐵道|電鉄|電鐵|電車|市電|地下鉄|地下鐵|モノレール|新交通|軌道|系統|ルート|ライン|交通|ケーブル|鋼索)$/u;
    const ORDINARY_ROUTE_TITLE_ALLOW_RE = /(?:号|ライナー|エクスプレス|はるか|くろしお|サンダーバード|しらさぎ|ひたち|ときわ|あずさ|かいじ|踊り子|わかしお|さざなみ|しおさい|こうのとり|きのさき|はしだて|まいづる|ふじさん|はこね|えのしま|ホームウェイ|スペーシア|リバティ|ひだ)$/u;

    function stationNameForGroup(stationGroupId) {
      const group = state.stationGroupById.get(stationGroupId);
      return group?.names?.ja || group?.primaryName || stationGroupId;
    }

    function hasPlayableDownstream(entry) {
      return Boolean(nextStopFor(entry));
    }

    function sourceFamily(entry) {
      const text = String(entry.trip?.id || entry.trip?.sourceFeedKey || '');
      if (text.startsWith('shinkansen:')) return 'curated';
      if (text.includes('_official') || text.includes(':official') || /(?:^|:)jr_[a-z]+_official:/u.test(text)) return 'official';
      if (text.includes('navitime')) return 'navitime';
      return 'other';
    }

    function routeChoiceIdsForEntry(entry) {
      return routeChoiceIdsForDeparture({
        trip: entry.trip,
        boardStop: entry.stop,
        stop: entry.stop,
        routeIds: entry.routeIds || [],
        departureMinute: entry.departureMinute,
        queryStationGroupId: entry.queryStationGroupId,
      });
    }

    function entryMatchesChoice(entry, choice) {
      const choiceTitle = routeTitle(choice.routeId);
      return routeChoiceIdsForEntry(entry).some((routeId) =>
        routeId === choice.routeId || routeTitle(routeId) === choiceTitle
      );
    }

    function nextStopFor(entry) {
      return (entry.trip?.stopTimes || []).find((stop) => stop.sequence > entry.stop.sequence) || null;
    }

    function tripStationNames(trip) {
      return (trip?.stopTimes || []).map((stop) => stationNameForGroup(stop.stationGroupId));
    }

    function currentOperationalKey(entry) {
      const trip = entry.trip;
      const stationNames = tripStationNames(trip);
      return [
        minutesToHhmm(entry.departureMinute),
        stationNames.join('>'),
      ].join('|');
    }

    function reviewedCoupledSplitOperation(groupEntries) {
      if (!groupEntries?.length || !(state.coupledServiceEntries || []).length) return false;
      for (const registryEntry of state.coupledServiceEntries || []) {
        const matchedPortionIndexes = new Set();
        let matchedTripCount = 0;
        for (const entry of groupEntries) {
          const portionIndexes = coupledPortionIndexesForTrip(registryEntry, entry.trip);
          if (!portionIndexes.length) continue;
          matchedTripCount += 1;
          portionIndexes.forEach((index) => matchedPortionIndexes.add(index));
        }
        if (matchedTripCount >= 2 && matchedPortionIndexes.size >= 2) return true;
      }
      return false;
    }

    function routeLikeChoiceTitle(title) {
      if (!title || title === '路線') return false;
      if (ORDINARY_ROUTE_TITLE_ALLOW_RE.test(title)) return false;
      return ROUTE_LIKE_TITLE_RE.test(title);
    }

    function limitedBaseName(trip) {
      return publicLimitedExpressBaseName(trip)?.name || '';
    }

    function summarizeEntry(entry, selectedRouteId) {
      const trip = entry.trip;
      const nextStop = nextStopFor(entry);
      const stationNames = tripStationNames(trip);
      const choiceIds = routeChoiceIdsForEntry(entry);
      return {
        departure: minutesToHhmm(entry.departureMinute),
        label: formatTripLabelForBoarding(entry, selectedRouteId),
        serviceName: trip?.serviceName || '',
        displayName: trip?.displayName || '',
        limitedBaseName: limitedBaseName(trip),
        namedChoiceLabel: namedTrainChoiceLabel(trip),
        serviceNumber: publicTripNumber(trip),
        isLimitedExpress: Boolean(isLimitedExpressTrip(trip)),
        sourceFamily: sourceFamily(entry),
        sourceFeedKey: trip?.sourceFeedKey || '',
        tripRoute: routeTitle(trip?.routeId || ''),
        choices: choiceIds.map(routeTitle),
        traceRoutes: [...new Set((trip?.lineTrace || []).map((trace) => routeTitle(trace.routeId)).filter(Boolean))],
        origin: stationNames[0] || '',
        boardStation: stationNameForGroup(entry.stop.stationGroupId),
        nextStation: nextStop ? stationNameForGroup(nextStop.stationGroupId) : '',
        terminal: stationNames.at(-1) || '',
        stopCount: stationNames.length,
        tripId: trip?.id || '',
      };
    }

    const scan = {
      checkedStations: 0,
      checkedRouteChoices: 0,
      sparseChoiceCount: 0,
      suspiciousChoiceCount: 0,
      routeLikeSparseChoiceCount: 0,
      hiddenNamedTrainChoiceCount: 0,
      overlappingSourceChoiceCount: 0,
      splitOperationalChoiceCount: 0,
      suspiciousSourceSparseChoiceCount: 0,
      samples: [],
    };
    const sparseExamples = [];
    const suspicious = [];
    const stationGroups = [...state.stationGroupById.entries()];
    const selectedStationGroups = stationLimit === null
      ? stationGroups.slice(stationOffset)
      : stationGroups.slice(stationOffset, stationOffset + stationLimit);

    function addSample(target, sample) {
      if (target.length < maxSamples) target.push(sample);
    }

    for (const [stationGroupId, group] of selectedStationGroups) {
      const stationName = group.names?.ja || group.primaryName || stationGroupId;
      scan.checkedStations += 1;
      const departures = departuresForStationGroup(stationGroupId, startMinute, { includeTransferEquivalents: true });
      if (!departures.length) continue;
      const choices = routeChoicesFromDepartures(departures);
      scan.checkedRouteChoices += choices.length;

      const operationalGroups = new Map();
      for (const entry of departures) {
        const key = currentOperationalKey(entry);
        if (!operationalGroups.has(key)) operationalGroups.set(key, []);
        operationalGroups.get(key).push(entry);
      }

      for (const choice of choices) {
        if (choice.trainCount > maxTrainCount) continue;
        scan.sparseChoiceCount += 1;
        const title = routeTitle(choice.routeId);
        const routeLike = routeLikeChoiceTitle(title);
        if (routeLike) scan.routeLikeSparseChoiceCount += 1;
      const entries = departures.filter((entry) => hasPlayableDownstream(entry) && entryMatchesChoice(entry, choice));
        const entrySummaries = entries.map((entry) => summarizeEntry(entry, choice.routeId));
        addSample(sparseExamples, {
          station: stationName,
          route: title,
          trainCount: choice.trainCount,
          firstDeparture: choice.firstDepartureHhmm,
          entries: entrySummaries.slice(0, 4),
        });

        const hiddenNamedEntries = entries.filter((entry) => {
          const label = namedTrainChoiceLabel(entry.trip) || limitedBaseName(entry.trip);
          return routeLike && !isShinkansenTrip(entry.trip) && label && label !== title;
        });
        const splitOperationalEntries = entries.filter((entry) => {
          const groupEntries = (operationalGroups.get(currentOperationalKey(entry)) || []).filter(hasPlayableDownstream);
          if (reviewedCoupledSplitOperation(groupEntries)) return false;
          const choiceTitles = new Set(groupEntries.flatMap((candidate) => routeChoiceIdsForEntry(candidate).map(routeTitle)));
          return choiceTitles.size > 1;
        });
        const overlappingSourceEntries = entries.filter((entry) => {
          const groupEntries = (operationalGroups.get(currentOperationalKey(entry)) || []).filter(hasPlayableDownstream);
          const sourceFamilies = new Set(groupEntries.map(sourceFamily));
          return sourceFamilies.has('official') && sourceFamilies.has('navitime');
        });
        const suspiciousSparseSourceEntries = entries.filter((entry) =>
          routeLike &&
          sourceFamily(entry) === 'navitime' &&
          (entry.trip?.lineTrace || []).length >= 3 &&
          !isLimitedExpressTrip(entry.trip) &&
          !namedTrainChoiceLabel(entry.trip) &&
          !REVIEWED_SPARSE_NAVITIME_THROUGH_ALLOW.has(`${stationName}|${title}`)
        );

        const reasons = [];
        if (hiddenNamedEntries.length) reasons.push('route_like_sparse_choice_hides_named_train');
        if (splitOperationalEntries.length) reasons.push('same_operation_split_across_route_choices');
        if (overlappingSourceEntries.length) reasons.push('official_navitime_overlap_in_sparse_choice');
        if (suspiciousSparseSourceEntries.length) reasons.push('route_like_sparse_navitime_through_candidate');
        if (!reasons.length) continue;

        scan.suspiciousChoiceCount += 1;
        if (hiddenNamedEntries.length) scan.hiddenNamedTrainChoiceCount += 1;
        if (splitOperationalEntries.length) scan.splitOperationalChoiceCount += 1;
        if (overlappingSourceEntries.length) scan.overlappingSourceChoiceCount += 1;
        if (suspiciousSparseSourceEntries.length) scan.suspiciousSourceSparseChoiceCount += 1;
        const sample = {
          station: stationName,
          route: title,
          trainCount: choice.trainCount,
          firstDeparture: choice.firstDepartureHhmm,
          reasons,
          entries: entrySummaries,
          siblingOperations: [...new Set(entries.flatMap((entry) => {
            const groupEntries = (operationalGroups.get(currentOperationalKey(entry)) || []).filter(hasPlayableDownstream);
            return groupEntries.map((candidate) => summarizeEntry(candidate, choice.routeId));
          }).map((summary) => JSON.stringify(summary)))].map((value) => JSON.parse(value)).slice(0, 8),
        };
        suspicious.push(sample);
        addSample(scan.samples, sample);
      }
    }

    return {
      checkedAt: new Date().toISOString(),
      auditOptions: {
        startTime: auditOptions.startTime || '06:00',
        maxTrainCount,
        maxSamples,
        stationLimit,
        stationOffset,
      },
      stationCount: state.stationGroupById.size,
      tripCount: state.tripById?.size || 0,
      scan,
      sparseExamples: sparseExamples.slice(0, maxSamples),
      suspiciousChoices: suspicious.slice(0, maxSamples),
      anomalyCount: suspicious.length,
      anomalies: suspicious.slice(0, maxSamples),
    };
  }, auditOptions);
}

(async () => {
  const args = parseArgs(process.argv);
  const auditOptions = {
    startTime: args['start-time'] || '06:00',
    maxTrainCount: parseIntegerOption(args['max-train-count'], 2),
    maxSamples: parseIntegerOption(args['max-samples'], 120),
    stationLimit: parseIntegerOption(args['station-limit'], null),
    stationOffset: parseIntegerOption(args['station-offset'], 0),
  };
  const { browser, page, loadTimings } = await loadPage(args['page-url']);
  try {
    const result = await auditSparseRouteChoices(page, auditOptions);
    result.loadTimings = loadTimings;
    const json = JSON.stringify(result, null, 2);
    process.stdout.write(`${json}\n`);
    if (args.output && args.output !== true) fs.writeFileSync(args.output, `${json}\n`);
    if (result.anomalyCount) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
