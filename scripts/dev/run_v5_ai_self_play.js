#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

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

function numberArg(args, key, fallback) {
  const value = Number(args[key]);
  return Number.isFinite(value) ? value : fallback;
}

function boolArg(args, key, fallback = false) {
  if (!(key in args)) return fallback;
  if (args[key] === true) return true;
  return !['0', 'false', 'no', 'off'].includes(String(args[key]).toLowerCase());
}

function writeJson(filePath, payload) {
  if (!filePath) return;
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

function safeFileName(value) {
  return String(value || '')
    .replace(/[^a-zA-Z0-9_.-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 160) || 'game';
}

function clearReplayJsonFiles(replayDir) {
  if (!replayDir || !fs.existsSync(replayDir)) return;
  fs.readdirSync(replayDir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.json'))
    .forEach((entry) => fs.unlinkSync(path.join(replayDir, entry.name)));
}

function writeReplayFiles(report, replayDir) {
  if (!replayDir || !Array.isArray(report.games)) return [];
  const replayIndex = [];
  report.games.forEach((game) => {
    if (!game.replayRecord) return;
    const paddedIndex = String(game.index ?? replayIndex.length + 1).padStart(4, '0');
    const fileName = safeFileName(`${paddedIndex}-${game.runnerStrategy}-vs-${game.hunterStrategy}-${game.winner}.json`);
    const filePath = path.join(replayDir, fileName);
    writeJson(filePath, game.replayRecord);
    delete game.replayRecord;
    game.replayPath = filePath;
    replayIndex.push({
      gameId: game.gameId,
      index: game.index,
      path: filePath,
      winner: game.winner,
      capture: game.capture || null,
      runnerStrategy: game.runnerStrategy,
      hunterStrategy: game.hunterStrategy,
    });
  });
  return replayIndex;
}

async function main() {
  const args = parseArgs(process.argv);
  const outputPath = args.output || path.resolve(__dirname, '../../reports/v5_ai_self_play_report.json');
  const replayDir = args['replay-dir'] || path.resolve(__dirname, '../../reports/v5_ai_self_play_replays');
  const includeReplays = boolArg(args, 'write-replays', true);
  const config = {
    loadBus: boolArg(args, 'load-bus', false),
    games: numberArg(args, 'games', 0),
    seed: String(args.seed || 'v5-ai-self-play'),
    includeReplayRecords: includeReplays,
    progressEvery: numberArg(args, 'progress-every', 0),
    startIndex: numberArg(args, 'start-index', 1),
    endIndex: numberArg(args, 'end-index', 0),
  };

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const consoleMessages = [];

  page.on('console', (message) => {
    const text = message.text();
    if (!text.includes('GPU stall') && !text.includes('Failed to load resource')) {
      consoleMessages.push(`${message.type()}: ${text}`);
      if (text.startsWith('[v5-self-play]')) console.error(text);
    }
  });
  page.on('pageerror', (error) => consoleMessages.push(`pageerror: ${error.message}`));

  try {
    await page.goto(args['page-url'], { waitUntil: 'load', timeout: 60000 });
    await page.waitForFunction(() => typeof enterSinglePlayer === 'function', null, { timeout: 30000 });
    await page.evaluate(() => enterSinglePlayer('runner'));
    await page.waitForFunction(
      () => state.timetableStatus === 'ready' && state.shipSailingById?.size && state.flightById?.size,
      null,
      { timeout: 120000 },
    );

    const report = await page.evaluate(async (config) => {
      const runnerStrategies = [
        {
          id: 'runner_multimodal_beam',
          label: 'Runner multimodal beam',
          notes: 'Searches rail, walking, flights, ships, and any loaded buses for a long escape plan.',
        },
        {
          id: 'runner_wait10_multimodal',
          label: 'Runner wait 10 then multimodal',
          notes: 'Waits until 06:10, then runs the multimodal escape search.',
        },
        {
          id: 'runner_wait20_multimodal',
          label: 'Runner wait 20 then multimodal',
          notes: 'Gives Hunter less early signal by holding Tokyo until 06:20 before escaping.',
        },
        {
          id: 'runner_rail_one_leg',
          label: 'Runner rail one leg',
          notes: 'Takes the best single rail escape leg from Tokyo.',
        },
        {
          id: 'runner_rail_three_leg',
          label: 'Runner rail three legs',
          notes: 'Extends the rail escape by repeatedly planning from each tail station.',
        },
        {
          id: 'runner_rail_five_leg',
          label: 'Runner rail five legs',
          notes: 'Stress-tests deeper rail-only long-range chaining.',
        },
      ];
      const hunterStrategies = [
        {
          id: 'hunter_rail_one_leg',
          label: 'Hunter rail one leg',
          knowledge: 'belief',
          notes: 'Releases at 06:30 and plans one rail intercept leg against a phantom Runner generated from public information.',
        },
        {
          id: 'hunter_rail_two_leg',
          label: 'Hunter rail two legs',
          knowledge: 'belief',
          notes: 'Releases at 06:30 and chains two rail intercept plans against a phantom Runner generated from public information.',
        },
        {
          id: 'hunter_rail_three_leg',
          label: 'Hunter rail three legs',
          knowledge: 'belief',
          notes: 'Releases at 06:30 and chains three rail intercept plans against a phantom Runner generated from public information.',
        },
        {
          id: 'hunter_multimodal_static',
          label: 'Hunter multimodal static',
          knowledge: 'belief',
          notes: 'Releases at 06:30 and runs one multimodal intercept beam search against a phantom Runner generated from public information.',
        },
        {
          id: 'hunter_multimodal_replan',
          label: 'Hunter multimodal replan',
          knowledge: 'belief',
          notes: 'Releases at 06:30, runs multimodal intercept search, then replans hourly from observations without reading Runner future steps.',
          replan: true,
        },
        {
          id: 'hunter_belief_static',
          label: 'Hunter belief static',
          knowledge: 'belief',
          notes: 'Plans against a phantom Runner generated from public start information, not the real future plan.',
        },
        {
          id: 'hunter_belief_replan',
          label: 'Hunter belief replan',
          knowledge: 'belief',
          notes: 'Holds Tokyo until the first 07:00 observation, then replans hourly from observed Runner state without reading future steps.',
          replan: true,
        },
        {
          id: 'hunter_hold_tokyo',
          label: 'Hunter hold Tokyo',
          knowledge: 'control',
          notes: 'Releases at 06:30 but holds Tokyo as a control baseline.',
        },
      ];
      const unfairHunterStrategies = hunterStrategies.filter((strategy) => strategy.knowledge === 'omniscient');
      if (unfairHunterStrategies.length) {
        throw new Error(`Fair self-play cannot include omniscient Hunter strategies: ${unfairHunterStrategies.map((strategy) => strategy.id).join(', ')}`);
      }
      const targetProfiles = [
        { id: 'balanced', label: 'Balanced', vector: [0, 0], projectionWeight: 0, radialWeight: 20 },
        { id: 'north', label: 'North', vector: [0, 1], projectionWeight: 72, radialWeight: 8 },
        { id: 'south', label: 'South', vector: [0, -1], projectionWeight: 72, radialWeight: 8 },
        { id: 'west', label: 'West', vector: [-1, 0], projectionWeight: 68, radialWeight: 8 },
        { id: 'southwest', label: 'Southwest', vector: [-0.7, -0.7], projectionWeight: 74, radialWeight: 8 },
        { id: 'east', label: 'East', vector: [1, 0], projectionWeight: 60, radialWeight: 8 },
      ];
      const modeProfiles = [
        { id: 'all_modes', label: 'Rail + walk + flight + ship + bus', modes: ['rail', 'walk', 'flight', 'ship', 'bus'] },
        { id: 'rail_air', label: 'Rail + walk + flight', modes: ['rail', 'walk', 'flight'] },
        { id: 'surface', label: 'Rail + walk + ship + bus', modes: ['rail', 'walk', 'ship', 'bus'] },
        { id: 'rail_walk', label: 'Rail + walk', modes: ['rail', 'walk'] },
      ];

      const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const releaseMinute = hhmmToMinutes('06:30');
      const tokyoStationId = stationGroupIdByDisplayName('東京');
      const tokyoCoordinate = stationLonLat(tokyoStationId);
      if (!tokyoStationId || !tokyoCoordinate) throw new Error('Cannot resolve Tokyo station group');

      function clone(value, fallback = null) {
        if (value === undefined) return fallback;
        return JSON.parse(JSON.stringify(value));
      }

      function makeRng(seedText) {
        let hash = 2166136261;
        for (let index = 0; index < seedText.length; index += 1) {
          hash ^= seedText.charCodeAt(index);
          hash = Math.imul(hash, 16777619);
        }
        return () => {
          hash += 0x6D2B79F5;
          let value = hash;
          value = Math.imul(value ^ (value >>> 15), value | 1);
          value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
          return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
        };
      }

      const rng = makeRng(String(config.seed || 'v5-ai-self-play'));
      const choice = (items) => items[Math.floor(rng() * items.length)] || items[0];

      if (config.loadBus && typeof ensureBusPlannerLoaded === 'function') {
        state.activeMode = 'runner';
        state.players.runner.start_station_id = tokyoStationId;
        state.busMapActive = true;
        await ensureBusPlannerLoaded();
        await sleep(800);
        if (state.busPlannerLoadStatus === 'ready' && typeof refreshBusPlannerVisibleData === 'function') {
          await refreshBusPlannerVisibleData();
        }
      }

      function resetSeat(seat) {
        const player = state.players[seat];
        player.start_station_id = tokyoStationId;
        player.steps = [];
        player.flight_ticket = null;
        state.planningModes[seat] = 'rail';
        state.planningRouteIds[seat] = null;
        state.pendingTripIds[seat] = null;
        state.flightPlanning[seat] = { origin: null, destination: null };
        state.shipPlanning[seat] = { origin: null, destination: null };
        state.busPlanning[seat] = { stopId: null, routeKey: null, tripId: null, targetAirportIata: null };
      }

      function resetGame() {
        state.startTime = '06:00';
        state.endTime = '18:00';
        state.currentGameMinute = hhmmToMinutes(state.startTime);
        state.phase = 'PLANNING';
        state.latestResult = null;
        state.activeMode = 'runner';
        state.localAi.enabled = false;
        state.localAi.status = '';
        state.localAi.lastPlanSeat = null;
        state.localAi.lastPlanMinute = null;
        resetSeat('runner');
        resetSeat('hunter');
        state.players.hunter.steps = [{ type: 'WAIT_UNTIL', until_hhmm: '06:30' }];
        invalidateSimulation();
      }

      function withHunterReleaseDeparture(fn) {
        const original = effectiveDepartureMinute;
        effectiveDepartureMinute = (playerId, previewMinute) => {
          const cursorMinute = Number.isFinite(previewMinute) ? previewMinute : hhmmToMinutes(state.startTime);
          const minute = Math.max(cursorMinute, state.currentGameMinute);
          return playerId === 'hunter' ? Math.max(minute, releaseMinute) : minute;
        };
        try {
          return fn();
        } finally {
          effectiveDepartureMinute = original;
        }
      }

      function withCaptureRelease(fn) {
        const original = detectCaptureAfterEvent;
        detectCaptureAfterEvent = (event, carrierState, minuteEvents) => {
          if (Number(event?.time_minute) < releaseMinute) return null;
          return original(event, carrierState, minuteEvents);
        };
        try {
          return fn();
        } finally {
          detectCaptureAfterEvent = original;
        }
      }

      function withAiModeProfile(profile, fn) {
        const allowed = new Set((profile?.modes || modeProfiles[0].modes).map(String));
        const originals = {
          flight: localAiFlightActions,
          ship: localAiShipActions,
          bus: localAiBusActions,
          rail: localAiRailActions,
          walk: localAiWalkActions,
        };
        localAiFlightActions = (...innerArgs) => allowed.has('flight') ? originals.flight(...innerArgs) : [];
        localAiShipActions = (...innerArgs) => allowed.has('ship') ? originals.ship(...innerArgs) : [];
        localAiBusActions = (...innerArgs) => allowed.has('bus') ? originals.bus(...innerArgs) : [];
        localAiRailActions = (...innerArgs) => allowed.has('rail') ? originals.rail(...innerArgs) : [];
        localAiWalkActions = (...innerArgs) => allowed.has('walk') ? originals.walk(...innerArgs) : [];
        try {
          return fn();
        } finally {
          localAiFlightActions = originals.flight;
          localAiShipActions = originals.ship;
          localAiBusActions = originals.bus;
          localAiRailActions = originals.rail;
          localAiWalkActions = originals.walk;
        }
      }

      function runnerTargetBias(preview, profile) {
        if (!profile || profile.id === 'balanced') return 0;
        const coordinate = localAiPreviewCoordinate(preview);
        if (!coordinate || !tokyoCoordinate) return 0;
        const avgLatRadians = ((coordinate[1] + tokyoCoordinate[1]) / 2) * Math.PI / 180;
        const dxKm = (coordinate[0] - tokyoCoordinate[0]) * Math.cos(avgLatRadians) * 111.32;
        const dyKm = (coordinate[1] - tokyoCoordinate[1]) * 110.57;
        const distanceKm = Math.sqrt(dxKm * dxKm + dyKm * dyKm);
        const projectionKm = dxKm * Number(profile.vector?.[0] || 0) + dyKm * Number(profile.vector?.[1] || 0);
        return projectionKm * Number(profile.projectionWeight || 0) + distanceKm * Number(profile.radialWeight || 0);
      }

      function withRunnerTargetBias(profile, fn) {
        const original = localAiScoreNode;
        localAiScoreNode = (node, aiSeat, startMinute) => {
          const base = original(node, aiSeat, startMinute);
          return aiSeat === 'runner' ? base + runnerTargetBias(node.preview, profile) : base;
        };
        try {
          return fn();
        } finally {
          localAiScoreNode = original;
        }
      }

      function seatPlanError(seat) {
        const scenario = buildScenario();
        try {
          expandPlayerPlan(seat, scenario.players[seat], scenario);
          return null;
        } catch (error) {
          return error?.message || String(error);
        }
      }

      function trimSeatPlanTail(seat, minSteps = 0) {
        const steps = state.players[seat].steps;
        if (!steps.length || steps.length <= minSteps) return false;
        const last = steps[steps.length - 1];
        if (last?.type === 'RIDE_TO_STATION' && steps[steps.length - 2]?.type === 'BOARD_TRAIN' && steps.length - 2 >= minSteps) {
          steps.splice(steps.length - 2, 2);
          return true;
        }
        if (last?.type === 'RIDE_TO_BUS_STOP' && steps[steps.length - 2]?.type === 'BOARD_BUS') {
          const walkIndex = steps[steps.length - 3]?.type === 'WALK_TO_BUS_STOP' ? steps.length - 3 : steps.length - 2;
          if (walkIndex >= minSteps) {
            steps.splice(walkIndex, steps.length - walkIndex);
            return true;
          }
        }
        steps.pop();
        return true;
      }

      function sanitizeSeatPlan(seat, minSteps = 0) {
        const removedErrors = [];
        for (let attempt = 0; attempt < 12; attempt += 1) {
          const error = seatPlanError(seat);
          if (!error) return { ok: true, removedErrors };
          removedErrors.push(error);
          if (!trimSeatPlanTail(seat, minSteps)) return { ok: false, removedErrors };
        }
        return { ok: !seatPlanError(seat), removedErrors };
      }

      function generateRailChain(seat, count) {
        let planned = 0;
        for (let index = 0; index < count; index += 1) {
          const before = state.players[seat].steps.map(localAiCloneStep);
          if (!generateLocalAiRailPlan(seat)) break;
          const error = seatPlanError(seat);
          if (error) {
            state.players[seat].steps = before;
            break;
          }
          planned += 1;
        }
        return planned;
      }

      function planRunner(strategyId, context) {
        state.activeMode = 'runner';
        state.localAi.aiSeat = 'runner';
        state.localAi.humanSeat = 'hunter';
        const modeProfile = context.runnerModeProfile;
        const targetProfile = context.runnerTarget;
        return withAiModeProfile(modeProfile, () => withRunnerTargetBias(targetProfile, () => {
          if (strategyId === 'runner_multimodal_beam') return generateLocalAiRunnerPlan();
          if (strategyId === 'runner_rail_one_leg') return generateRailChain('runner', 1) > 0;
          if (strategyId === 'runner_rail_three_leg') return generateRailChain('runner', 3) > 0;
          if (strategyId === 'runner_rail_five_leg') return generateRailChain('runner', 5) > 0;
          if (strategyId === 'runner_wait10_multimodal') {
            state.players.runner.steps.push({ type: 'WAIT_UNTIL', until_hhmm: '06:10' });
            return generateLocalAiRunnerPlan();
          }
          if (strategyId === 'runner_wait20_multimodal') {
            state.players.runner.steps.push({ type: 'WAIT_UNTIL', until_hhmm: '06:20' });
            return generateLocalAiRunnerPlan();
          }
          throw new Error(`Unknown runner strategy ${strategyId}`);
        }));
      }

      function snapshotRunner() {
        return {
          startStationId: state.players.runner.start_station_id,
          steps: clone(state.players.runner.steps, []),
          flightTicket: clone(state.players.runner.flight_ticket, null),
        };
      }

      function restoreRunner(snapshot) {
        state.players.runner.start_station_id = snapshot.startStationId;
        state.players.runner.steps = clone(snapshot.steps, []);
        state.players.runner.flight_ticket = clone(snapshot.flightTicket, null);
      }

      function visibleObservationAt(minute) {
        const preview = previewPlayer('runner', minute);
        const currentState = preview?.currentState || {};
        const base = {
          minute,
          time: minutesToHhmm(minute),
          stateKind: currentState.kind || 'unknown',
          label: formatState(preview),
          resolvedStepCount: preview?.resolvedSteps?.length || 0,
        };
        if (currentState.kind === 'NODE') base.stationGroupId = currentState.stationGroupId;
        if (currentState.kind === 'BUS_STOP') base.busStopId = currentState.busStopId;
        if (currentState.kind === 'TRAIN') base.tripId = currentState.tripId;
        if (currentState.kind === 'BUS') base.tripId = currentState.tripId;
        if (currentState.airportIata) base.airportIata = currentState.airportIata;
        if (currentState.kind === 'PORT_WAIT') base.portName = currentState.portName;
        if (currentState.kind === 'SHIP') base.sailingId = currentState.sailingId;
        return { preview, summary: base };
      }

      function stationDirectionalScore(stationGroupId, profile) {
        const coordinate = stationLonLat(stationGroupId);
        if (!coordinate) return Number.NEGATIVE_INFINITY;
        const preview = {
          currentState: { kind: 'NODE', stationGroupId },
          mapPosition: coordinate,
        };
        return runnerTargetBias(preview, profile) + localAiStationHubScore(stationGroupId) * 260;
      }

      function predictedRailAlightForObservation(tripId, minute, profile) {
        const trip = state.tripById.get(tripId);
        if (!trip) return null;
        const candidates = (trip.stopTimes || [])
          .filter((stop) => stop.stationGroupId && stopArrivalMinutes(stop) >= minute + 5)
          .map((stop) => ({
            stop,
            score: stationDirectionalScore(stop.stationGroupId, profile) +
              Math.min(9000, Math.max(0, stopArrivalMinutes(stop) - minute) * 90),
          }))
          .sort((left, right) => right.score - left.score);
        return candidates[0]?.stop || null;
      }

      function predictedBusAlightForObservation(tripId, minute, profile) {
        const trip = state.busPlannerTripsById.get(tripId);
        if (!trip) return null;
        const candidates = (trip.stops || [])
          .filter((stop) => stop.stopId && Number(stop.arr ?? stop.dep) >= minute + 3)
          .map((stop) => {
            const airportBonus = busStopRecordAirportIata(stop) ? 1800 : 0;
            const railChoices = busRailAccessChoices({ currentState: { kind: 'BUS_STOP', busStopId: stop.stopId }, currentMinute: Number(stop.arr ?? stop.dep) });
            const railBonus = Math.min(1600, railChoices.length * 160);
            const coordinate = busStopCoordinate(stop.stopId);
            const directional = coordinate && tokyoCoordinate
              ? runnerTargetBias({ currentState: { kind: 'BUS_STOP', busStopId: stop.stopId }, mapPosition: coordinate }, profile)
              : 0;
            return {
              stop,
              score: directional + airportBonus + railBonus + Math.min(4200, Math.max(0, Number(stop.arr ?? stop.dep) - minute) * 55),
            };
          })
          .sort((left, right) => right.score - left.score);
        return candidates[0]?.stop || null;
      }

      function buildPhantomRunnerPlan(minute, context, observeActual) {
        const actual = snapshotRunner();
        const saved = {
          currentGameMinute: state.currentGameMinute,
          activeMode: state.activeMode,
          localAi: clone(state.localAi, {}),
        };
        let observation = {
          minute,
          time: minutesToHhmm(minute),
          stateKind: 'prior',
          label: `public prior from 東京 at ${minutesToHhmm(minute)}`,
          resolvedStepCount: 0,
        };

        if (observeActual) {
          const observed = visibleObservationAt(minute);
          observation = observed.summary;
          const currentState = observed.preview?.currentState || {};
          if (currentState.kind === 'NODE' && currentState.stationGroupId) {
            state.players.runner.start_station_id = currentState.stationGroupId;
            state.players.runner.steps = [{ type: 'WAIT_UNTIL', until_hhmm: minutesToHhmm(minute) }];
            state.players.runner.flight_ticket = null;
          } else if (currentState.kind === 'TRAIN' && currentState.tripId) {
            const targetProfile = context.hunterBeliefTarget || context.runnerTarget || targetProfiles[0];
            const prefix = actual.steps.slice(0, observed.summary.resolvedStepCount);
            const alightStop = predictedRailAlightForObservation(currentState.tripId, minute, targetProfile);
            state.players.runner.start_station_id = actual.startStationId;
            state.players.runner.steps = clone(prefix, []);
            if (alightStop?.stationGroupId) {
              state.players.runner.steps.push({ type: 'RIDE_TO_STATION', station_id: alightStop.stationGroupId });
              observation.predictedAlightStationId = alightStop.stationGroupId;
              observation.predictedAlightLabel = displayNameForGroup(alightStop.stationGroupId);
              observation.predictedAlightTime = minutesToHhmm(stopArrivalMinutes(alightStop));
            }
            state.players.runner.flight_ticket = null;
          } else if (currentState.kind === 'BUS' && currentState.tripId) {
            const targetProfile = context.hunterBeliefTarget || context.runnerTarget || targetProfiles[0];
            const prefix = actual.steps.slice(0, observed.summary.resolvedStepCount);
            const alightStop = predictedBusAlightForObservation(currentState.tripId, minute, targetProfile);
            state.players.runner.start_station_id = actual.startStationId;
            state.players.runner.steps = clone(prefix, []);
            if (alightStop?.stopId) {
              state.players.runner.steps.push({ type: 'RIDE_TO_BUS_STOP', bus_stop_id: alightStop.stopId });
              observation.predictedAlightBusStopId = alightStop.stopId;
              observation.predictedAlightLabel = busStopName(alightStop.stopId);
              observation.predictedAlightTime = minutesToHhmm(Number(alightStop.arr ?? alightStop.dep));
            }
            state.players.runner.flight_ticket = null;
          } else {
            state.players.runner.start_station_id = actual.startStationId;
            state.players.runner.steps = actual.steps.slice(0, observed.summary.resolvedStepCount);
            if (observed.preview?.currentMinute < minute) {
              state.players.runner.steps.push({ type: 'WAIT_UNTIL', until_hhmm: minutesToHhmm(minute) });
            }
            state.players.runner.flight_ticket = null;
          }
        } else {
          state.players.runner.start_station_id = tokyoStationId;
          state.players.runner.steps = [];
          state.players.runner.flight_ticket = null;
        }

        state.phase = 'PLANNING';
        state.currentGameMinute = observeActual ? minute : hhmmToMinutes(state.startTime);
        state.activeMode = 'runner';
        state.localAi.aiSeat = 'runner';
        state.localAi.humanSeat = 'hunter';
        state.localAi.lastPlanSeat = null;
        state.localAi.lastPlanMinute = null;

        const protectedSteps = state.players.runner.steps.length;
        const targetProfile = context.hunterBeliefTarget || context.runnerTarget || targetProfiles[0];
        const modeProfile = context.hunterBeliefModeProfile || context.runnerModeProfile || modeProfiles[0];
        const planned = withAiModeProfile(modeProfile, () => withRunnerTargetBias(targetProfile, () => generateLocalAiRunnerPlan()));
        const sanitize = sanitizeSeatPlan('runner', protectedSteps);
        const phantom = {
          startStationId: state.players.runner.start_station_id,
          steps: clone(state.players.runner.steps, []),
          planned,
          sanitize,
          observation,
          targetProfileId: targetProfile.id,
          modeProfileId: modeProfile.id,
        };

        restoreRunner(actual);
        state.currentGameMinute = saved.currentGameMinute;
        state.activeMode = saved.activeMode;
        state.localAi = saved.localAi;
        return phantom;
      }

      function withTemporaryRunnerPlan(phantom, fn) {
        const actual = snapshotRunner();
        state.players.runner.start_station_id = phantom.startStationId;
        state.players.runner.steps = clone(phantom.steps, []);
        state.players.runner.flight_ticket = null;
        try {
          return fn();
        } finally {
          restoreRunner(actual);
        }
      }

      function planHunterRail(strategyId) {
        if (strategyId === 'hunter_rail_one_leg') return generateRailChain('hunter', 1) > 0;
        if (strategyId === 'hunter_rail_two_leg') return generateRailChain('hunter', 2) > 0;
        if (strategyId === 'hunter_rail_three_leg') return generateRailChain('hunter', 3) > 0;
        return false;
      }

      function planHunter(strategy, context) {
        state.activeMode = 'hunter';
        state.localAi.aiSeat = 'hunter';
        state.localAi.humanSeat = 'runner';
        if (strategy.id === 'hunter_hold_tokyo') return true;
        if (strategy.id === 'hunter_belief_replan') {
          state.players.hunter.steps.push({ type: 'WAIT_UNTIL', until_hhmm: '07:00' });
          context.phantomPlans.push({
            phase: 'initial_hold',
            startStationId: tokyoStationId,
            steps: clone(state.players.hunter.steps, []),
            planned: true,
            sanitize: { ok: true, removedErrors: [] },
            observation: {
              minute: releaseMinute,
              time: minutesToHhmm(releaseMinute),
              stateKind: 'prior',
              label: 'belief replan waits at 東京 for first 07:00 observation',
              resolvedStepCount: 0,
            },
            targetProfileId: context.hunterBeliefTarget.id,
            modeProfileId: context.hunterBeliefModeProfile.id,
          });
          return true;
        }
        const runPlanner = () => {
          if (strategy.id.startsWith('hunter_rail_')) return planHunterRail(strategy.id);
          return generateLocalAiHunterPlan();
        };
        const planAgainstCurrentRunner = () => withAiModeProfile(context.hunterModeProfile, () => withHunterReleaseDeparture(runPlanner));
        if (strategy.knowledge !== 'belief') return planAgainstCurrentRunner();

        const phantom = buildPhantomRunnerPlan(releaseMinute, context, false);
        context.phantomPlans.push({ phase: 'initial', ...phantom });
        return withTemporaryRunnerPlan(phantom, () => planAgainstCurrentRunner());
      }

      function captureMinute(capture) {
        return capture?.time_hhmm ? hhmmToMinutes(capture.time_hhmm) : Number.POSITIVE_INFINITY;
      }

      function replanMinutes() {
        const minutes = [];
        const endMinute = hhmmToMinutes(state.endTime);
        for (let minute = hhmmToMinutes('07:00'); minute < endMinute; minute += 60) minutes.push(minute);
        return minutes;
      }

      function replanHunterAt(minute, strategy, context) {
        state.phase = 'PLANNING';
        state.currentGameMinute = minute;
        state.activeMode = 'hunter';
        state.localAi.aiSeat = 'hunter';
        state.localAi.humanSeat = 'runner';
        const beforeStepCount = state.players.hunter.steps.length;
        const protectedSteps = previewPlayer('hunter', minute)?.resolvedSteps?.length || 1;
        const runReplan = () => withAiModeProfile(context.hunterModeProfile, () =>
          withHunterReleaseDeparture(() => localAiTryReplanFromCurrent('hunter'))
        );
        let planned;
        if (strategy.knowledge === 'belief') {
          const phantom = buildPhantomRunnerPlan(minute, context, true);
          context.phantomPlans.push({ phase: 'replan', ...phantom });
          planned = withTemporaryRunnerPlan(phantom, runReplan);
        } else {
          planned = runReplan();
        }
        const sanitize = sanitizeSeatPlan('hunter', protectedSteps);
        return {
          time: minutesToHhmm(minute),
          planned,
          beforeStepCount,
          afterStepCount: state.players.hunter.steps.length,
          protectedSteps,
          sanitize,
        };
      }

      function stateLabel(carrier) {
        return carrierReplayLabel(carrier);
      }

      function legDecisionTrace(player) {
        return (player.legs || []).map((leg) => ({
          legIndex: leg.leg_index,
          mode: leg.mode || 'rail',
          from: leg.from_label || leg.origin_airport || leg.origin_port || leg.from_station_id || leg.from_bus_stop_id || null,
          to: leg.to_label || leg.destination_airport || leg.destination_port || leg.to_station_id || leg.to_bus_stop_id || null,
          depart: leg.depart_hhmm || leg.board_hhmm || leg.purchase_hhmm || leg.origin_access_arrive_hhmm || null,
          arrive: leg.arrive_hhmm || leg.alight_hhmm || leg.destination_access_arrive_hhmm || leg.cooldown_end_hhmm || null,
          tripId: leg.trip_id || leg.flight_id || leg.sailing_id || null,
          fareYen: leg.fare?.total_yen ?? null,
        }));
      }

      function coordinateForCarrierState(carrier, minute) {
        if (!carrier) return null;
        if (carrier.kind === 'NODE') return stationLonLat(carrier.stationGroupId);
        if (carrier.kind === 'BUS_STOP') return busStopCoordinate(carrier.busStopId);
        if (carrier.kind === 'TRAIN') return tripLocationOnMap(carrier.tripId, minute)?.position || null;
        if (carrier.kind === 'BUS') return busTripLocationOnMap(carrier.tripId, minute);
        if (carrier.kind === 'AIRPORT_WAIT' || carrier.kind === 'BOARDING' || carrier.kind === 'ARRIVAL_COOLDOWN') return airportCoordinate(carrier.airportIata);
        if (carrier.kind === 'FLIGHT') {
          const flight = state.flightById.get(carrier.flightId);
          const times = flight ? flightRuleTimes(flight) : null;
          const origin = airportCoordinate(flight?.originAirport);
          const destination = airportCoordinate(flight?.destinationAirport);
          const ratio = times ? clamp((minute - times.departureMinute) / Math.max(1, times.arrivalMinute - times.departureMinute), 0, 1) : 0;
          return origin && destination
            ? [origin[0] + (destination[0] - origin[0]) * ratio, origin[1] + (destination[1] - origin[1]) * ratio]
            : origin || destination || null;
        }
        if (carrier.kind === 'PORT_WAIT') return portCoordinate(carrier.portName);
        if (carrier.kind === 'SHIP') {
          const sailing = state.shipSailingById.get(carrier.sailingId);
          const origin = portCoordinate(sailing?.originPort);
          const destination = portCoordinate(sailing?.destinationPort);
          const ratio = sailing ? clamp((minute - Number(sailing.departureMinute)) / Math.max(1, Number(sailing.arrivalMinute) - Number(sailing.departureMinute)), 0, 1) : 0;
          return origin && destination
            ? [origin[0] + (destination[0] - origin[0]) * ratio, origin[1] + (destination[1] - origin[1]) * ratio]
            : origin || destination || null;
        }
        return null;
      }

      function finalSeparationMeters(result) {
        const event = [...(result.match_event_log || [])].reverse().find((item) => item.state_after?.runner && item.state_after?.hunter);
        const runnerCoordinate = coordinateForCarrierState(event?.state_after?.runner, event?.time_minute);
        const hunterCoordinate = coordinateForCarrierState(event?.state_after?.hunter, event?.time_minute);
        const distance = coordinateDistanceMeters(runnerCoordinate, hunterCoordinate);
        return Number.isFinite(distance) ? Math.round(distance) : null;
      }

      function playerSummary(result, seat) {
        const player = result.players[seat];
        const lastEvent = [...(result.match_event_log || [])]
          .reverse()
          .find((event) => event.player_id === seat && event.state_after);
        const finalState = lastEvent?.state_after?.[seat] || { kind: 'NODE', stationGroupId: player.start_station_id };
        const modes = [...new Set((player.legs || []).map((leg) => leg.mode || 'rail'))];
        return {
          startStation: displayNameForGroup(player.start_station_id),
          stepCount: state.players[seat].steps.length,
          resolvedActionCount: player.resolved_actions?.length || 0,
          modes,
          finalTime: lastEvent?.time_hhmm || state.startTime,
          finalLabel: stateLabel(finalState),
          fareYen: player.fare_summary?.total_yen ?? null,
          planSteps: clone(state.players[seat].steps, []),
          decisionTrace: legDecisionTrace(player),
        };
      }

      function makeReplayRecord(result, context) {
        if (!config.includeReplayRecords) return null;
        state.latestResult = result;
        const record = buildCanonicalReplayRecord(result);
        record.record_id = context.gameId;
        record.scenario.id = context.gameId;
        record.scenario.name = `V5 AI self-play ${context.gameId}`;
        record.source.kind = 'v5_ai_self_play_harness';
        record.self_play = {
          runnerStrategy: context.runnerStrategy.id,
          hunterStrategy: context.hunterStrategy.id,
          runnerTarget: context.runnerTarget.id,
          hunterBeliefTarget: context.hunterBeliefTarget.id,
          runnerModeProfile: context.runnerModeProfile.id,
          hunterModeProfile: context.hunterModeProfile.id,
          hunterKnowledge: context.hunterStrategy.knowledge,
          phantomPlans: clone(context.phantomPlans, []),
        };
        state.latestResult = null;
        return record;
      }

      function runGame(context) {
        resetGame();
        context.phantomPlans = [];
        const runnerPlanned = planRunner(context.runnerStrategy.id, context);
        const runnerMinSteps = context.runnerStrategy.id === 'runner_wait10_multimodal' || context.runnerStrategy.id === 'runner_wait20_multimodal' ? 1 : 0;
        const runnerSanitize = sanitizeSeatPlan('runner', runnerMinSteps);
        const hunterPlanned = planHunter(context.hunterStrategy, context);
        const hunterSanitize = sanitizeSeatPlan('hunter', 1);
        const replans = [];
        let result = withCaptureRelease(() => buildResult());
        result.scenario_id = context.gameId;
        if (context.hunterStrategy.replan) {
          for (const minute of replanMinutes()) {
            if (captureMinute(result.capture) <= minute) break;
            replans.push(replanHunterAt(minute, context.hunterStrategy, context));
            result = withCaptureRelease(() => buildResult());
            result.scenario_id = context.gameId;
          }
        }
        const hunterWon = Boolean(result.capture);
        const game = {
          gameId: context.gameId,
          index: context.index,
          runnerStrategy: context.runnerStrategy.id,
          hunterStrategy: context.hunterStrategy.id,
          hunterKnowledge: context.hunterStrategy.knowledge,
          runnerTarget: context.runnerTarget.id,
          hunterBeliefTarget: context.hunterBeliefTarget.id,
          runnerModeProfile: context.runnerModeProfile.id,
          hunterModeProfile: context.hunterModeProfile.id,
          runnerPlanned,
          hunterPlanned,
          runnerSanitize,
          hunterSanitize,
          phantomPlans: clone(context.phantomPlans, []),
          replans,
          winner: hunterWon ? 'hunter' : 'runner',
          capture: result.capture,
          finalSeparationMeters: finalSeparationMeters(result),
          runner: playerSummary(result, 'runner'),
          hunter: playerSummary(result, 'hunter'),
        };
        game.replayRecord = makeReplayRecord(result, context);
        return game;
      }

      function makeContext(index, runnerStrategy, hunterStrategy) {
        const runnerTarget = choice(targetProfiles);
        const hunterBeliefTarget = choice(targetProfiles);
        return {
          index,
          gameId: `v5-ai-self-play-${String(index).padStart(4, '0')}`,
          runnerStrategy,
          hunterStrategy,
          runnerTarget,
          hunterBeliefTarget,
          runnerModeProfile: choice(modeProfiles),
          hunterModeProfile: choice(modeProfiles),
          hunterBeliefModeProfile: choice(modeProfiles),
          phantomPlans: [],
        };
      }

      function buildSchedule() {
        const totalGames = Math.max(0, Math.floor(Number(config.games || 0)));
        const contexts = [];
        let index = 1;
        runnerStrategies.forEach((runnerStrategy) => {
          hunterStrategies.forEach((hunterStrategy) => {
            contexts.push(makeContext(index, runnerStrategy, hunterStrategy));
            index += 1;
          });
        });
        if (totalGames <= 0) return contexts;
        while (contexts.length < totalGames) {
          contexts.push(makeContext(index, choice(runnerStrategies), choice(hunterStrategies)));
          index += 1;
        }
        const fullSchedule = contexts.slice(0, totalGames).map((context, offset) => ({
          ...context,
          index: offset + 1,
          gameId: `v5-ai-self-play-${String(offset + 1).padStart(4, '0')}`,
        }));
        const startIndex = Math.max(1, Math.floor(Number(config.startIndex || 1)));
        const endIndex = Math.floor(Number(config.endIndex || 0));
        return fullSchedule.filter((context) =>
          context.index >= startIndex &&
          (endIndex <= 0 || context.index <= endIndex)
        );
      }

      const schedule = buildSchedule();
      const games = [];
      schedule.forEach((context) => {
        if (Number(config.progressEvery) === 1) {
          console.log(`[v5-self-play] starting ${games.length + 1}/${schedule.length} game ${context.index} ${context.runnerStrategy.id} vs ${context.hunterStrategy.id}`);
        }
        games.push(runGame(context));
        if (Number(config.progressEvery) > 0 && games.length % Number(config.progressEvery) === 0) {
          console.log(`[v5-self-play] completed ${games.length}/${schedule.length}`);
        }
      });
      if (Number(config.progressEvery) > 0 && games.length % Number(config.progressEvery) !== 0) {
        console.log(`[v5-self-play] completed ${games.length}/${schedule.length}`);
      }

      function average(values) {
        const finite = values.filter(Number.isFinite);
        if (!finite.length) return null;
        return Number((finite.reduce((sum, value) => sum + value, 0) / finite.length).toFixed(2));
      }

      function winRate(wins, total = games.length) {
        return Number((wins / Math.max(1, total)).toFixed(4));
      }

      function groupSummary(keyName, values, winnerSeat) {
        return values.map((value) => {
          const id = typeof value === 'string' ? value : value.id;
          const subset = games.filter((game) => game[keyName] === id);
          const wins = subset.filter((game) => game.winner === winnerSeat).length;
          const captureMinutes = subset
            .map((game) => game.capture?.time_hhmm ? hhmmToMinutes(game.capture.time_hhmm) : null)
            .filter(Number.isFinite);
          return {
            id,
            games: subset.length,
            [`${winnerSeat}Wins`]: wins,
            [`${winnerSeat}WinRate`]: winRate(wins, subset.length),
            averageCaptureMinute: average(captureMinutes),
            averageFinalSeparationMeters: average(subset.map((game) => game.finalSeparationMeters).filter(Number.isFinite)),
          };
        });
      }

      function groupByField(keyName, winnerSeat) {
        const ids = [...new Set(games.map((game) => game[keyName]))].sort();
        return groupSummary(keyName, ids, winnerSeat);
      }

      function modeUsage(seat) {
        const counts = {};
        games.forEach((game) => {
          const modes = game[seat]?.modes || [];
          modes.forEach((mode) => {
            counts[mode] = (counts[mode] || 0) + 1;
          });
        });
        return Object.fromEntries(Object.entries(counts)
          .sort(([left], [right]) => left.localeCompare(right))
          .map(([mode, count]) => [mode, { games: count, rate: winRate(count, games.length) }]));
      }

      const hunterWins = games.filter((game) => game.winner === 'hunter').length;
      const runnerWins = games.length - hunterWins;
      const captures = games.filter((game) => game.capture);
      const fairHunterOnly = games.every((game) => game.hunterKnowledge !== 'omniscient');
      const sanitizeIssueGames = games.filter((game) =>
        !game.runnerSanitize?.ok ||
        !game.hunterSanitize?.ok ||
        (game.runnerSanitize?.removedErrors || []).length ||
        (game.hunterSanitize?.removedErrors || []).length
      );
      const planningFailureGames = games.filter((game) => !game.runnerPlanned || !game.hunterPlanned);

      return {
        generatedAt: new Date().toISOString(),
        configuration: {
          seed: config.seed,
          requestedGames: Math.max(0, Math.floor(Number(config.games || 0))),
          replayRecordsIncluded: Boolean(config.includeReplayRecords),
          progressEvery: Number(config.progressEvery) || 0,
          startIndex: Math.max(1, Math.floor(Number(config.startIndex || 1))),
          endIndex: Math.floor(Number(config.endIndex || 0)) || null,
          fairHunterOnly,
        },
        fairness: {
          runnerStart: '東京 06:00',
          hunterStart: '東京 06:30',
          captureBeforeHunterRelease: 'ignored in self-play harness',
          hunterDepartureClamp: '06:30 in self-play harness',
          hunterKnowledgePolicy: 'Default self-play rejects omniscient Hunter strategies. Hunter planning uses public priors, scheduled observations, and generated phantom Runner plans.',
          hunterKnowledgeModels: {
            belief: 'Hunter scores against a generated phantom Runner prior/replan observation and never reads the real future steps during planning.',
            control: 'Hunter does not move.',
          },
        },
        datasetId: state.bundle.metadata?.datasetId || null,
        busPlannerStatus: state.busPlannerLoadStatus || null,
        strategies: { runner: runnerStrategies, hunter: hunterStrategies },
        targetProfiles,
        modeProfiles,
        summary: {
          games: games.length,
          runnerWins,
          hunterWins,
          runnerWinRate: winRate(runnerWins),
          hunterWinRate: winRate(hunterWins),
          captures: captures.length,
          averageCaptureMinute: average(captures.map((game) => hhmmToMinutes(game.capture.time_hhmm))),
          averageFinalSeparationMeters: average(games.map((game) => game.finalSeparationMeters).filter(Number.isFinite)),
          planningFailureGames: planningFailureGames.length,
          sanitizeIssueGames: sanitizeIssueGames.length,
        },
        byRunner: groupSummary('runnerStrategy', runnerStrategies, 'runner'),
        byHunter: groupSummary('hunterStrategy', hunterStrategies, 'hunter'),
        byHunterKnowledge: groupByField('hunterKnowledge', 'hunter'),
        byRunnerTarget: groupByField('runnerTarget', 'runner'),
        byRunnerModeProfile: groupByField('runnerModeProfile', 'runner'),
        byHunterModeProfile: groupByField('hunterModeProfile', 'hunter'),
        modeUsage: {
          runner: modeUsage('runner'),
          hunter: modeUsage('hunter'),
        },
        planningFailures: planningFailureGames.map((game) => ({
          gameId: game.gameId,
          runnerStrategy: game.runnerStrategy,
          hunterStrategy: game.hunterStrategy,
          runnerPlanned: game.runnerPlanned,
          hunterPlanned: game.hunterPlanned,
        })),
        sanitizeIssues: sanitizeIssueGames.map((game) => ({
          gameId: game.gameId,
          runnerStrategy: game.runnerStrategy,
          hunterStrategy: game.hunterStrategy,
          runnerErrors: game.runnerSanitize?.removedErrors || [],
          hunterErrors: game.hunterSanitize?.removedErrors || [],
        })),
        games,
      };
    }, config);

    report.consoleMessages = consoleMessages;
    if (includeReplays) {
      clearReplayJsonFiles(replayDir);
      report.replayDir = replayDir;
      report.replays = writeReplayFiles(report, replayDir);
    }
    writeJson(outputPath, report);
    console.log(JSON.stringify({
      outputPath,
      replayDir: includeReplays ? replayDir : null,
      summary: report.summary,
      byHunterKnowledge: report.byHunterKnowledge,
      byRunner: report.byRunner,
      byHunter: report.byHunter,
    }, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
