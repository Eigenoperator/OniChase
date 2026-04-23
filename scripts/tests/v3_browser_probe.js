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
  if (!args.probe) throw new Error('Missing --probe');
  return args;
}

async function loadV3Page(pageUrl) {
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

async function runInPage(page, probeName) {
  return page.evaluate((name) => {
    function stationIdByName(stationName) {
      return [...state.stationGroupById.entries()].find(([, group]) =>
        (group.names?.ja || group.primaryName) === stationName
      )?.[0] || null;
    }

    function stationIdsByName(stationName) {
      return new Set([...state.stationGroupById.entries()]
        .filter(([, group]) => (group.names?.ja || group.primaryName) === stationName)
        .map(([stationGroupId]) => stationGroupId));
    }

    function routeIdByTitle(title) {
      return [...state.routeById.entries()].find(([, route]) => routeJapaneseName(route) === title)?.[0] || null;
    }

    function selectedPathByRoute() {
      const features = state.map.getSource('selected-trip-path').data.features || [];
      const byRoute = {};
      features.forEach((feature) => {
        const title = routeTitle(feature.properties.route_id);
        byRoute[title] = (byRoute[title] || 0) + 1;
      });
      return { count: features.length, byRoute };
    }

    function resetRunnerAt(stationName, startTime) {
      state.activeMode = 'runner';
      state.players.runner.start_station_id = stationIdByName(stationName);
      state.players.runner.steps = [];
      state.startTime = startTime;
      state.currentGameMinute = hhmmToMinutes(startTime);
      clearPendingTrip('runner');
    }

    function findConsecutiveStationPair(trip, fromName, toName) {
      const fromIds = stationIdsByName(fromName);
      const toIds = stationIdsByName(toName);
      const stops = trip.stopTimes || [];
      for (let index = 0; index < stops.length - 1; index += 1) {
        if (fromIds.has(stops[index].stationGroupId) && toIds.has(stops[index + 1].stationGroupId)) {
          return [stops[index], stops[index + 1]];
        }
      }
      return null;
    }

    function routeTitlesForRows(rows) {
      return rows.map((row) => ({
        departure: minutesToHhmm(row.departureMinute),
        label: formatTripLabelForBoarding({ trip: row.trip, routeIds: row.routeIds }, row.routeIds?.[0] || row.trip.routeId),
        routeIds: (row.routeIds || []).map(routeTitle),
        tripRoute: routeTitle(row.trip.routeId),
      }));
    }

    function selectedTrainHighlightProbe() {
      const fukutoshinRoute = routeIdByTitle('副都心線');
      resetRunnerAt('池袋', '16:55');
      const fukutoshinRows = departuresForStationGroup(stationIdByName('池袋'), hhmmToMinutes('16:55'), { routeId: fukutoshinRoute });
      const fukutoshinTarget = fukutoshinRows.find((row) =>
        minutesToHhmm(row.departureMinute) === '17:01' &&
        formatTripLabelForBoarding({ trip: row.trip, routeIds: row.routeIds }, fukutoshinRoute).includes('みなとみらい')
      );
      if (!fukutoshinTarget) throw new Error('Missing golden 池袋 17:01 副都心線 through-service');
      setSelectedTrip(fukutoshinTarget.trip.id, fukutoshinRoute);
      const fukutoshin = {
        departure: minutesToHhmm(fukutoshinTarget.departureMinute),
        label: formatTripLabelForBoarding({ trip: fukutoshinTarget.trip, routeIds: fukutoshinTarget.routeIds }, fukutoshinRoute),
        startSequence: selectedTripStartSequence(fukutoshinTarget.trip),
        selectedStopCount: state.selectedTripStopIds.length,
        path: selectedPathByRoute(),
        broadRouteHidden: state.map.getSource('selected-route-path').data.features.length === 0,
        routeStopHaloHidden: JSON.stringify(state.map.filters['route-stop-halo']) === JSON.stringify(NONE_STATION_FILTER),
        badDepartureRows: routeTitlesForRows(fukutoshinRows).filter((row) => /埼京|川越/.test(row.label)),
      };

      const yamanoteRoute = routeIdByTitle('山手線');
      resetRunnerAt('東京', '06:25');
      const yamanoteTarget = departuresForStationGroup(stationIdByName('東京'), hhmmToMinutes('06:25'), { routeId: yamanoteRoute })[0];
      if (!yamanoteTarget) throw new Error('Missing golden 東京 山手線 departure');
      const beforeSet = performance.now();
      setSelectedTrip(yamanoteTarget.trip.id, yamanoteRoute);
      const setSelectedTripMs = performance.now() - beforeSet;
      const beforePath = performance.now();
      const yamanoteSegments = tripPathSegments(yamanoteTarget.trip);
      const tripPathMs = performance.now() - beforePath;
      const yamanote = {
        departure: minutesToHhmm(yamanoteTarget.departureMinute),
        startSequence: selectedTripStartSequence(yamanoteTarget.trip),
        selectedStopCount: state.selectedTripStopIds.length,
        featureCount: state.map.getSource('selected-trip-path').data.features.length,
        segmentCount: yamanoteSegments.length,
        uniqueRoutes: [...new Set(yamanoteSegments.map((segment) => routeTitle(segment.routeId)))],
        setSelectedTripMs: Math.round(setSelectedTripMs),
        tripPathMs: Math.round(tripPathMs),
        builtGlobalGraph: Boolean(state.allTrackGraph),
      };
      return { fukutoshin, yamanote };
    }

    function physicalThroughRunningProbe() {
      const fukutoshinRoute = routeIdByTitle('副都心線');
      const ikebukuroRows = departuresForStationGroup(stationIdByName('池袋'), hhmmToMinutes('06:00'), { routeId: fukutoshinRoute });
      const fukutoshinBadRows = routeTitlesForRows(ikebukuroRows)
        .filter((row) => /埼京|川越/.test(row.label) || row.routeIds.some((title) => /埼京|川越/.test(title)));

      const tokyo = stationIdByName('東京');
      const tokyoRouteChoices = routeChoicesFromDepartures(departuresForStationGroup(tokyo, hhmmToMinutes('06:00')));
      function rowsForTokyoRoute(routeTitleText) {
        const choice = tokyoRouteChoices.find((item) => routeTitle(item.routeId) === routeTitleText);
        const routeId = choice?.routeId || routeIdByTitle(routeTitleText);
        const minute = choice?.firstDepartureMinute || hhmmToMinutes('06:00');
        return departuresForStationGroup(tokyo, minute, { routeId }).slice(0, 20);
      }
      const tohokuShinkansen = routeIdByTitle('東北・北海道新幹線');
      const ordinaryRows = rowsForTokyoRoute('東海道線');
      const shinkansenRows = rowsForTokyoRoute('東海道・山陽新幹線');
      const ordinaryWithShinkansen = routeTitlesForRows(ordinaryRows).filter((row) =>
        row.routeIds.includes('東海道・山陽新幹線') || /新幹線/.test(row.label)
      );
      const shinkansenWithOrdinary = routeTitlesForRows(shinkansenRows).filter((row) =>
        row.routeIds.includes('東海道線') || row.routeIds.includes('横須賀線') || row.routeIds.includes('京浜東北線・根岸線')
      );
      const tokaidoWithOtherShinkansen = routeTitlesForRows(shinkansenRows).filter((row) =>
        row.routeIds.includes('東北・北海道新幹線') || row.routeIds.some((title) => title !== '東海道・山陽新幹線' && /新幹線/.test(title))
      );

      const yamanoteRows = departuresForStationGroup(tokyo, hhmmToMinutes('06:00'), { routeId: routeIdByTitle('山手線') }).slice(0, 20);
      const yamanoteWithParallelOrdinary = routeTitlesForRows(yamanoteRows).filter((row) =>
        row.routeIds.some((title) => ['京浜東北線・根岸線', '東海道線', '横須賀線'].includes(title))
      );

      state.selectedRouteId = null;
      state.selectedTripId = null;
      state.pendingTripIds.runner = null;
      const boundaryExpectations = [
        ['泉岳寺', '品川', '京急本線'],
        ['品川', '泉岳寺', '京急本線'],
        ['押上', '青砥', '京成押上線'],
        ['青砥', '押上', '京成押上線'],
        ['京急蒲田', '羽田空港第3ターミナル', '京急空港線'],
        ['横浜', 'みなとみらい', '横浜高速鉄道みなとみらい21線'],
        ['池袋', '小竹向原', '副都心線'],
      ];
      const boundarySegments = boundaryExpectations.map(([fromName, toName, expectedRoute]) => {
        const matches = [];
        for (const trip of state.tripById.values()) {
          const pair = findConsecutiveStationPair(trip, fromName, toName);
          if (!pair) continue;
          matches.push({
            tripRoute: routeTitle(trip.routeId),
            departure: secToClock(pair[0].departureTimeSec),
            chosenRoute: routeTitle(routeIdForTripSegment(trip, pair[0], pair[1])),
          });
          if (matches.length >= 3) break;
        }
        return { fromName, toName, expectedRoute, matches };
      });

      let equivalentPair = null;
      for (const [transferKey, groupIds] of state.stationGroupIdsByTransferKey.entries()) {
        const ids = [...groupIds];
        if (ids.length < 2) continue;
        equivalentPair = { transferKey, left: ids[0], right: ids[1] };
        break;
      }
      const equivalentStationCapture = equivalentPair
        ? detectCaptureAfterEvent(
          { type: 'SCENARIO_START' },
          {
            runner: { kind: 'NODE', stationGroupId: equivalentPair.left },
            hunter: { kind: 'NODE', stationGroupId: equivalentPair.right },
          },
          [],
        )
        : null;
      const sameTrainCapture = detectCaptureAfterEvent(
        { type: 'BOARD_TRAIN' },
        {
          runner: { kind: 'TRAIN', tripId: 'trip-a' },
          hunter: { kind: 'TRAIN', tripId: 'trip-b' },
        },
        [],
      );

      return {
        fukutoshinBadRows,
        shinkansen: {
          ordinaryRowCount: ordinaryRows.length,
          shinkansenRowCount: shinkansenRows.length,
          hasTohokuShinkansenRoute: Boolean(tohokuShinkansen),
          ordinaryWithShinkansen,
          shinkansenWithOrdinary,
          tokaidoWithOtherShinkansen,
        },
        yamanoteWithParallelOrdinary,
        boundarySegments,
        equivalentStationPair: equivalentPair,
        equivalentStationCapture,
        sameTrainCapture,
      };
    }

    function axiomsProbe() {
      const tokyo = stationIdByName('東京');
      const routeChoices = routeChoicesFromDepartures(departuresForStationGroup(tokyo, hhmmToMinutes('06:00')))
        .map((choice) => routeTitle(choice.routeId));
      const metroNumberedTitles = [...state.routeById.keys()]
        .map((routeId) => routeTitle(routeId))
        .filter((title) => /^\\d+号線/u.test(title));
      return {
        tokyoRouteChoices: [...new Set(routeChoices)].sort(),
        metroNumberedTitles,
        routeCount: state.routeById.size,
        stationGroupCount: state.stationGroupById.size,
        tripCount: state.tripById.size,
      };
    }

    function replayCoreProbe() {
      const tokyo = stationIdByName('東京');
      state.phase = 'PLANNING';
      state.startTime = '06:00';
      state.endTime = '18:00';
      state.currentGameMinute = hhmmToMinutes('06:00');
      state.players.runner = { start_station_id: tokyo, input_mode: 'plan', steps: [] };
      state.players.hunter = { start_station_id: tokyo, input_mode: 'plan', steps: [] };
      state.latestResult = null;
      state.liveCapture = null;
      state.replayShareStatus = '';

      runSimulation();
      const record = buildCanonicalReplayRecord();
      const encoded = encodeReplaySharePayload(record);
      const decoded = decodeReplaySharePayload(`${REPLAY_HASH_PREFIX}${encoded}`);
      applyReplayRecord(decoded);

      return {
        resultSectionHidden: document.getElementById('result-card').closest('section').hidden,
        toolbarReplayHidden: document.getElementById('simulate-button').hidden,
        schemaVersion: record.schema_version,
        datasetName: record.dataset_name,
        gameRulesVersion: record.game_rules_version,
        sourceKind: record.source.kind,
        captureType: record.result.capture?.type || 'none',
        captureCheckType: record.capture_checks.at(-1)?.capture_type || 'none',
        eventCount: record.events.length,
        phaseEventCount: record.phase_events.length,
        replayRowCount: document.querySelectorAll('#replay-list .replay-row').length,
        selectedEventType: currentReplayEvent()?.type || null,
        decodedCaptureType: decoded.result.capture?.type || 'none',
        summaryText: document.getElementById('replay-summary').innerText,
        resultText: document.getElementById('result-card').innerText,
        sharePayloadPrefix: encoded.slice(0, 3),
      };
    }

    async function entryModesProbe() {
      function waitUntil(predicate, timeoutMs = 5000) {
        return new Promise((resolve, reject) => {
          const start = performance.now();
          function tick() {
            try {
              if (predicate()) {
                resolve();
                return;
              }
            } catch (_error) {
              // Keep waiting until timeout.
            }
            if (performance.now() - start > timeoutMs) {
              reject(new Error('Timed out waiting for entry mode state'));
              return;
            }
            setTimeout(tick, 20);
          }
          tick();
        });
      }

      const advancedPanel = document.getElementById('advanced-setup-panel');
      const advancedButton = document.getElementById('advanced-setup-button');
      const initial = {
        quickText: document.getElementById('quick-play-button').innerText,
        tutorialText: document.getElementById('tutorial-button').innerText,
        advancedText: advancedButton.innerText,
        advancedHidden: advancedPanel.classList.contains('hidden'),
        singleRunnerHidden: !document.getElementById('single-runner-button').offsetParent,
      };

      advancedButton.click();
      await waitUntil(() => !advancedPanel.classList.contains('hidden'));
      const advanced = {
        hidden: advancedPanel.classList.contains('hidden'),
        expanded: advancedButton.getAttribute('aria-expanded'),
        singleRunnerText: document.getElementById('single-runner-button').innerText,
        createRoomText: document.getElementById('create-room-button').innerText,
      };

      document.getElementById('tutorial-button').click();
      await waitUntil(() => !state.tutorialMode || entryOverlayEl.classList.contains('hidden'));
      await waitUntil(() => state.tutorialMode && !document.getElementById('tutorial-guide-section').hidden);
      const tutorial = {
        entryHidden: entryOverlayEl.classList.contains('hidden'),
        guideHidden: document.getElementById('tutorial-guide-section').hidden,
        activeMode: state.activeMode,
        startTime: state.startTime,
        endTime: state.endTime,
        guideText: document.getElementById('tutorial-guide').innerText,
      };

      openEntry();
      document.getElementById('quick-play-button').click();
      await waitUntil(() => entryOverlayEl.classList.contains('hidden') && state.clockRunning);
      const quick = {
        entryHidden: entryOverlayEl.classList.contains('hidden'),
        activeMode: state.activeMode,
        startTime: state.startTime,
        endTime: state.endTime,
        clockRunning: state.clockRunning,
        planningSecondsRemaining: state.planningSecondsRemaining,
        runnerStepCount: state.players.runner.steps.length,
        hunterStepCount: state.players.hunter.steps.length,
        runnerStart: displayNameForGroup(state.players.runner.start_station_id),
        hunterStart: displayNameForGroup(state.players.hunter.start_station_id),
        planText: document.getElementById('plan-board').innerText,
      };

      return { initial, advanced, tutorial, quick };
    }

    const probes = {
      axioms: axiomsProbe,
      'physical-through-running': physicalThroughRunningProbe,
      'selected-train-highlight': selectedTrainHighlightProbe,
      'replay-core': replayCoreProbe,
      'entry-modes': entryModesProbe,
    };
    if (!probes[name]) throw new Error(`Unknown probe: ${name}`);
    return probes[name]();
  }, probeName);
}

async function main() {
  const args = parseArgs(process.argv);
  const { browser, page } = await loadV3Page(args['page-url']);
  try {
    const result = await runInPage(page, args.probe);
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
