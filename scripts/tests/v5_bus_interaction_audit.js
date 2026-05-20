#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

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

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function auditPublishedBusAirportAccess(repoRoot) {
  const failures = [];
  const check = (condition, message, details = {}) => {
    if (!condition) failures.push({ message, details });
  };

  const airportAudit = readJson(path.join(repoRoot, 'docs/data/v5_airport_bus_access_audit.json'));
  const flightsBundle = readJson(path.join(repoRoot, 'docs/data/v5_domestic_flights_current_bundle.json'));
  const flightAirports = new Set();
  (flightsBundle.flights || []).forEach((flight) => {
    if (flight.originAirport) flightAirports.add(flight.originAirport);
    if (flight.destinationAirport) flightAirports.add(flight.destinationAirport);
  });

  const summary = airportAudit.summary || {};
  check(summary.undocumentedNoNearbyStopCount === 0, 'Airport bus access has undocumented no-nearby-stop gaps', summary);
  check(summary.nearbyStopWithoutAirportClassCount === 0, 'Airport bus access has nearby stops without airport-class route coverage', summary);
  check(summary.airportClassCoveredCount >= 75, 'Airport bus access coverage dropped below current release threshold', summary);

  const airportsByIata = new Map((airportAudit.airports || []).map((airport) => [airport.iata, airport]));
  ['FUK', 'KMQ', 'KKJ', 'IWJ', 'NRT', 'TJH'].forEach((iata) => {
    const airport = airportsByIata.get(iata);
    check(Boolean(airport), `Missing airport access audit row for ${iata}`);
    check(airport?.status === 'covered_by_gtfs_airport_bus', `Airport ${iata} should be covered by playable airport bus GTFS`, airport);
    check(Number(airport?.airportClassRouteCount || 0) > 0, `Airport ${iata} should expose at least one airport bus route`, airport);
    check(flightAirports.has(iata), `Airport ${iata} should also exist in domestic flight bundle`, airport);
  });

  return {
    failureCount: failures.length,
    failures,
    summary,
  };
}

async function main() {
  const args = parseArgs(process.argv);
  const repoRoot = path.resolve(__dirname, '../..');
  const dataAudit = auditPublishedBusAirportAccess(repoRoot);

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

  await page.goto(args['page-url'], { waitUntil: 'load', timeout: 60000 });
  await page.waitForFunction(() => typeof enterSinglePlayer === 'function', null, { timeout: 30000 });
  await page.evaluate(() => enterSinglePlayer('runner'));
  await page.waitForFunction(() => state.timetableStatus === 'ready', null, { timeout: 120000 });

  const interaction = await page.evaluate(async () => {
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const clickAction = async (selector) => {
      const node = document.querySelector(selector);
      if (!node) return false;
      node.click();
      await sleep(350);
      return true;
    };
    const activeRows = (selector) => [...document.querySelectorAll(selector)]
      .filter((node) => !node.classList.contains('planner-row-exit'));
    const plannerText = () => document.querySelector('#train-outlook')?.innerText || '';

    const before = {
      mode: activePlanningMode(),
      busMapActive: state.busMapActive,
      busPlannerLoadStatus: state.busPlannerLoadStatus,
      steps: activePlayer().steps.length,
    };

    await clickAction('[data-action="choose-mode"][data-mode="bus"]');
    for (let index = 0; index < 80; index += 1) {
      if (
        activePlanningMode() === 'bus' &&
        state.busPlannerLoadStatus === 'ready' &&
        activeRows('[data-action="choose-bus-stop"]').length > 0
      ) break;
      await refreshBusPlannerVisibleData();
      renderGame();
      await sleep(250);
    }

    const stopRows = activeRows('[data-action="choose-bus-stop"]');
    const stopRow = stopRows[0] || null;
    const stopId = stopRow?.dataset.busStopId || null;
    if (stopRow) {
      stopRow.click();
      await sleep(350);
    }

    const routeRows = activeRows('[data-action="choose-bus-route"]');
    const routeRow = routeRows[0] || null;
    const routeKey = routeRow?.dataset.busRouteKey || null;
    if (routeRow) {
      routeRow.click();
      await sleep(350);
    }

    const tripRows = activeRows('[data-action="choose-bus-trip"]');
    const tripRow = tripRows[0] || null;
    const tripId = tripRow?.dataset.busTripId || null;
    const boardPreview = planCursorPreview(state.activeMode);
    const boardReadyMinute = stopId ? busBoardReadyMinute(stopId, boardPreview) : null;
    const boardTrip = tripId ? state.busPlannerTripsById.get(tripId) : null;
    const boardStop = boardTrip ? (boardTrip.stops || []).find((stop) => stop.stopId === stopId) : null;
    const boardDepartureMinute = boardStop ? Number(boardStop.dep ?? boardStop.arr) : null;
    if (tripRow) {
      tripRow.click();
      await sleep(350);
    }

    const destinationRows = activeRows('[data-action="ride-bus-here"]');
    const destinationRow = destinationRows[0] || null;
    const destinationStopId = destinationRow?.dataset.busStopId || null;
    if (destinationRow) {
      destinationRow.click();
      await sleep(500);
    }

    const busSteps = activePlayer().steps.filter((step) =>
      ['WALK_TO_BUS_STOP', 'BOARD_BUS', 'RIDE_TO_BUS_STOP', 'WALK_FROM_BUS_TO_STATION'].includes(step.type)
    );
    const preview = planCursorPreview(state.activeMode);

    return {
      before,
      afterModeSwitch: {
        mode: activePlanningMode(),
        busMapActive: state.busMapActive,
        busPlannerLoadStatus: state.busPlannerLoadStatus,
        busStopRows: stopRows.length,
        text: plannerText().slice(0, 500),
      },
      chosen: {
        stopId,
        stopName: stopId ? busStopName(stopId) : null,
        routeKey,
        routeName: routeKey ? busRouteName(parseBusRouteKey(routeKey).routeId) : null,
        tripId,
        boardReadyMinute,
        boardDepartureMinute,
        destinationStopId,
        destinationStopName: destinationStopId ? busStopName(destinationStopId) : null,
      },
      rowCounts: {
        stops: stopRows.length,
        routes: routeRows.length,
        trips: tripRows.length,
        destinations: destinationRows.length,
      },
      busSteps,
      finalPreview: {
        kind: preview?.currentState?.kind || null,
        stationGroupId: preview?.currentState?.stationGroupId || null,
        busStopId: preview?.currentState?.busStopId || null,
        currentMinute: preview?.currentMinute || null,
      },
    };
  });

  const uiFailures = [];
  const check = (condition, message, details = {}) => {
    if (!condition) uiFailures.push({ message, details });
  };

  check(interaction.before.mode === 'rail', 'Planner should start in rail mode', interaction.before);
  check(interaction.afterModeSwitch.mode === 'bus', 'Bus mode button should switch planner to bus mode', interaction.afterModeSwitch);
  check(interaction.afterModeSwitch.busMapActive, 'Bus mode should activate the bus map', interaction.afterModeSwitch);
  check(interaction.afterModeSwitch.busPlannerLoadStatus === 'ready', 'Bus planner data should load in the web page', interaction.afterModeSwitch);
  check(interaction.rowCounts.stops > 0, 'Bus mode should show reachable bus stops', interaction.rowCounts);
  check(interaction.rowCounts.routes > 0, 'Choosing a bus stop should show bus routes', interaction);
  check(interaction.rowCounts.trips > 0, 'Choosing a bus route should show bus trips', interaction);
  check(interaction.rowCounts.destinations > 0, 'Choosing a bus trip should show downstream stops', interaction);
  check(Number(interaction.chosen.boardDepartureMinute) >= Number(interaction.chosen.boardReadyMinute), 'Chosen bus must depart after walk-to-stop time', interaction.chosen);
  check(interaction.busSteps.some((step) => step.type === 'BOARD_BUS'), 'Selecting a downstream stop should add BOARD_BUS to current plan', interaction.busSteps);
  check(interaction.busSteps.some((step) => step.type === 'RIDE_TO_BUS_STOP'), 'Selecting a downstream stop should add RIDE_TO_BUS_STOP to current plan', interaction.busSteps);
  check(interaction.finalPreview.kind === 'BUS_STOP', 'After a bus ride the planner cursor should be at a bus stop', interaction.finalPreview);

  const output = {
    failureCount: dataAudit.failureCount + uiFailures.length,
    failures: [...dataAudit.failures, ...uiFailures],
    dataAudit: dataAudit.summary,
    interaction,
    consoleMessages,
  };

  await browser.close();
  console.log(JSON.stringify(output, null, 2));
  if (output.failureCount) process.exit(1);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
