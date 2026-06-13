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

function writeJson(filePath, payload) {
  if (!filePath) return;
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

async function main() {
  const args = parseArgs(process.argv);
  const outputPath = args.output || path.resolve(__dirname, '../../reports/v5_ai_self_play_report.json');
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const consoleMessages = [];

  page.on('console', (message) => {
    const text = message.text();
    if (!text.includes('GPU stall') && !text.includes('Failed to load resource')) {
      consoleMessages.push(`${message.type()}: ${text}`);
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

    const report = await page.evaluate(async ({ loadBus }) => {
      const runnerStrategies = [
        {
          id: 'runner_multimodal_beam',
          label: 'Runner multimodal beam',
          notes: 'Searches rail, walking, flights, ships, and any loaded buses for a long escape plan.',
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
          id: 'runner_wait10_multimodal',
          label: 'Runner wait 10 then multimodal',
          notes: 'Waits until 06:10, then runs the multimodal escape search.',
        },
      ];
      const hunterStrategies = [
        {
          id: 'hunter_rail_one_leg',
          label: 'Hunter rail one leg',
          notes: 'Releases at 06:30 and plans one intercept rail leg.',
        },
        {
          id: 'hunter_rail_two_leg',
          label: 'Hunter rail two legs',
          notes: 'Releases at 06:30 and chains two rail intercept plans.',
        },
        {
          id: 'hunter_rail_three_leg',
          label: 'Hunter rail three legs',
          notes: 'Releases at 06:30 and chains three rail intercept plans.',
        },
        {
          id: 'hunter_multimodal_static',
          label: 'Hunter multimodal static',
          notes: 'Releases at 06:30 and runs one multimodal intercept beam search.',
        },
        {
          id: 'hunter_multimodal_replan',
          label: 'Hunter multimodal replan',
          notes: 'Releases at 06:30, runs multimodal intercept search, then replans at hourly planning windows.',
          replan: true,
        },
        {
          id: 'hunter_hold_tokyo',
          label: 'Hunter hold Tokyo',
          notes: 'Releases at 06:30 but holds Tokyo as a control baseline.',
        },
      ];

      const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const releaseMinute = hhmmToMinutes('06:30');
      const tokyoStationId = stationGroupIdByDisplayName('東京');
      if (!tokyoStationId) throw new Error('Cannot resolve Tokyo station group');

      if (loadBus && typeof ensureBusPlannerLoaded === 'function') {
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

      function planRunner(strategyId) {
        state.activeMode = 'runner';
        state.localAi.aiSeat = 'runner';
        state.localAi.humanSeat = 'hunter';
        if (strategyId === 'runner_multimodal_beam') return generateLocalAiRunnerPlan();
        if (strategyId === 'runner_rail_one_leg') return generateRailChain('runner', 1) > 0;
        if (strategyId === 'runner_rail_three_leg') return generateRailChain('runner', 3) > 0;
        if (strategyId === 'runner_wait10_multimodal') {
          state.players.runner.steps.push({ type: 'WAIT_UNTIL', until_hhmm: '06:10' });
          return generateLocalAiRunnerPlan();
        }
        throw new Error(`Unknown runner strategy ${strategyId}`);
      }

      function planHunter(strategyId) {
        state.activeMode = 'hunter';
        state.localAi.aiSeat = 'hunter';
        state.localAi.humanSeat = 'runner';
        if (strategyId === 'hunter_hold_tokyo') return true;
        if (strategyId === 'hunter_rail_one_leg') return withHunterReleaseDeparture(() => generateRailChain('hunter', 1) > 0);
        if (strategyId === 'hunter_rail_two_leg') return withHunterReleaseDeparture(() => generateRailChain('hunter', 2) > 0);
        if (strategyId === 'hunter_rail_three_leg') return withHunterReleaseDeparture(() => generateRailChain('hunter', 3) > 0);
        if (strategyId === 'hunter_multimodal_static') return withHunterReleaseDeparture(() => generateLocalAiHunterPlan());
        if (strategyId === 'hunter_multimodal_replan') return withHunterReleaseDeparture(() => generateLocalAiHunterPlan());
        throw new Error(`Unknown hunter strategy ${strategyId}`);
      }

      function captureMinute(capture) {
        return capture?.time_hhmm ? hhmmToMinutes(capture.time_hhmm) : Number.POSITIVE_INFINITY;
      }

      function replanMinutes() {
        const minutes = [];
        const endMinute = hhmmToMinutes(state.endTime);
        for (let minute = hhmmToMinutes('07:30'); minute < endMinute; minute += 60) minutes.push(minute);
        return minutes;
      }

      function replanHunterAt(minute) {
        state.phase = 'PLANNING';
        state.currentGameMinute = minute;
        state.activeMode = 'hunter';
        state.localAi.aiSeat = 'hunter';
        state.localAi.humanSeat = 'runner';
        const beforeStepCount = state.players.hunter.steps.length;
        const planned = withHunterReleaseDeparture(() => localAiTryReplanFromCurrent('hunter'));
        const sanitize = sanitizeSeatPlan('hunter', 1);
        return {
          time: minutesToHhmm(minute),
          planned,
          beforeStepCount,
          afterStepCount: state.players.hunter.steps.length,
          sanitize,
        };
      }

      function stateLabel(carrier) {
        return carrierReplayLabel(carrier);
      }

      function playerSummary(result, seat) {
        const player = result.players[seat];
        const lastEvent = [...(result.match_event_log || [])]
          .reverse()
          .find((event) => event.player_id === seat && event.state_after);
        const finalState = lastEvent?.state_after?.[seat] || { kind: 'NODE', stationGroupId: player.start_station_id };
        return {
          startStation: displayNameForGroup(player.start_station_id),
          stepCount: state.players[seat].steps.length,
          resolvedActionCount: player.resolved_actions?.length || 0,
          modes: [...new Set((player.legs || []).map((leg) => leg.mode || 'rail'))],
          finalTime: lastEvent?.time_hhmm || state.startTime,
          finalLabel: stateLabel(finalState),
          fareYen: player.fare_summary?.total_yen ?? null,
          planSteps: cloneJson(state.players[seat].steps, []),
        };
      }

      function runGame(runnerStrategy, hunterStrategy) {
        resetGame();
        const runnerPlanned = planRunner(runnerStrategy.id);
        const runnerSanitize = sanitizeSeatPlan('runner', runnerStrategy.id === 'runner_wait10_multimodal' ? 1 : 0);
        const hunterPlanned = planHunter(hunterStrategy.id);
        const hunterSanitize = sanitizeSeatPlan('hunter', 1);
        const replans = [];
        let result = withCaptureRelease(() => buildResult());
        if (hunterStrategy.replan) {
          for (const minute of replanMinutes()) {
            if (captureMinute(result.capture) <= minute) break;
            replans.push(replanHunterAt(minute));
            result = withCaptureRelease(() => buildResult());
          }
        }
        const hunterWon = Boolean(result.capture);
        return {
          runnerStrategy: runnerStrategy.id,
          hunterStrategy: hunterStrategy.id,
          runnerPlanned,
          hunterPlanned,
          runnerSanitize,
          hunterSanitize,
          replans,
          winner: hunterWon ? 'hunter' : 'runner',
          capture: result.capture,
          runner: playerSummary(result, 'runner'),
          hunter: playerSummary(result, 'hunter'),
        };
      }

      const games = [];
      runnerStrategies.forEach((runnerStrategy) => {
        hunterStrategies.forEach((hunterStrategy) => {
          games.push(runGame(runnerStrategy, hunterStrategy));
        });
      });

      const hunterWins = games.filter((game) => game.winner === 'hunter').length;
      const runnerWins = games.length - hunterWins;
      const winRate = (wins, total = games.length) => Number((wins / Math.max(1, total)).toFixed(4));
      const byRunner = runnerStrategies.map((strategy) => {
        const subset = games.filter((game) => game.runnerStrategy === strategy.id);
        const wins = subset.filter((game) => game.winner === 'runner').length;
        return { id: strategy.id, runnerWins: wins, games: subset.length, runnerWinRate: winRate(wins, subset.length) };
      });
      const byHunter = hunterStrategies.map((strategy) => {
        const subset = games.filter((game) => game.hunterStrategy === strategy.id);
        const wins = subset.filter((game) => game.winner === 'hunter').length;
        return { id: strategy.id, hunterWins: wins, games: subset.length, hunterWinRate: winRate(wins, subset.length) };
      });

      return {
        generatedAt: new Date().toISOString(),
        fairness: {
          runnerStart: '東京 06:00',
          hunterStart: '東京 06:30',
          captureBeforeHunterRelease: 'ignored in self-play harness',
          hunterDepartureClamp: '06:30 in self-play harness',
        },
        datasetId: state.bundle.metadata?.datasetId || null,
        busPlannerStatus: state.busPlannerLoadStatus || null,
        strategies: { runner: runnerStrategies, hunter: hunterStrategies },
        summary: {
          games: games.length,
          runnerWins,
          hunterWins,
          runnerWinRate: winRate(runnerWins),
          hunterWinRate: winRate(hunterWins),
        },
        byRunner,
        byHunter,
        games,
      };
    }, { loadBus: Boolean(args['load-bus']) });

    report.consoleMessages = consoleMessages;
    writeJson(outputPath, report);
    console.log(JSON.stringify({
      outputPath,
      summary: report.summary,
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
