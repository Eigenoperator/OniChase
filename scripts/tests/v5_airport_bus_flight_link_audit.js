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

function auditAirportAccessRows(repoRoot, sampleIatas) {
  const failures = [];
  const airportAudit = readJson(path.join(repoRoot, 'docs/data/v5_airport_bus_access_audit.json'));
  const byIata = new Map((airportAudit.airports || []).map((airport) => [airport.iata, airport]));
  for (const iata of sampleIatas) {
    const row = byIata.get(iata);
    if (!row) {
      failures.push({ message: `Missing airport access row for ${iata}` });
      continue;
    }
    if (row.status !== 'covered_by_gtfs_airport_bus') {
      failures.push({ message: `Airport ${iata} should have playable airport-bus coverage`, details: row });
    }
    if (!Number(row.airportClassRouteCount || 0)) {
      failures.push({ message: `Airport ${iata} should expose airport-class bus routes`, details: row });
    }
    if (!(row.nearestStops || []).some((stop) => Number(stop.distanceMeters) <= 2000)) {
      failures.push({ message: `Airport ${iata} should have a nearby airport bus stop within 2km`, details: row.nearestStops });
    }
  }
  return { failures, summary: airportAudit.summary };
}

async function main() {
  const args = parseArgs(process.argv);
  const repoRoot = path.resolve(__dirname, '../..');
  const sampleIatas = (args.samples || 'HND,NRT,KIX,FUK,CTS,TAK,NKM,KMQ')
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
  const dataAudit = auditAirportAccessRows(repoRoot, sampleIatas);

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

  const interaction = await page.evaluate(async ({ sampleIatas }) => {
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    await loadBusPlanner();

    async function loadPlannerTilesNearCoordinate(coordinate, radiusMeters = 5000) {
      const entries = busPlannerTileEntriesNear(coordinate, radiusMeters);
      const tiles = await Promise.all(entries.map(loadBusPlannerTile));
      mergeBusPlannerTiles(tiles.filter(Boolean));
      return entries.length;
    }

    const results = [];
    for (const iata of sampleIatas) {
      const airport = state.airportByIata.get(iata);
      const coordinate = airportCoordinate(iata);
      const station = nearestStationGroupForAirport(iata);
      const tileCount = await loadPlannerTilesNearCoordinate(coordinate, 6000);
      const airportStops = [...state.busPlannerStopsById.values()]
        .map((stop) => ({
          stop,
          accessible: accessibleAirportFromBusStop(stop.id),
          distanceMeters: coordinateDistanceMeters(coordinate, [stop.lon, stop.lat]),
        }))
        .filter((item) => item.accessible?.iata === iata)
        .sort((a, b) =>
          a.distanceMeters - b.distanceMeters ||
          String(a.stop.name || '').localeCompare(String(b.stop.name || ''), 'ja')
        );
      const airportStop = airportStops[0]?.stop || null;
      const fromStationCoordinate = stationLonLat(station?.stationGroupId);
      const stopCoordinate = airportStop ? busStopCoordinate(airportStop.id) : null;
      const walkDistance = coordinateDistanceMeters(fromStationCoordinate, stopCoordinate);
      const walkTimeSec = walkingTimeSecForDistance(walkDistance || 0);

      activePlayer().start_station_id = station?.stationGroupId || activePlayer().start_station_id;
      activePlayer().steps = airportStop ? [{
        type: 'WALK_TO_BUS_STOP',
        station_id: station?.stationGroupId,
        bus_stop_id: airportStop.id,
        distance_meters: Math.round(walkDistance || 0),
        walk_time_sec: walkTimeSec,
        walking_speed_mps: activeWalkingSpeedMetersPerSecond(),
      }] : [];
      activePlayer().flight_ticket = null;
      clearBusPlanning();
      state.planningModes[state.activeMode] = 'flight';
      state.flightPlanning[state.activeMode] = { origin: iata, destination: null };
      invalidateSimulation();
      renderGame();
      await sleep(80);

      const previewAtBusStop = planCursorPreview(state.activeMode);
      const accessibleFromPreview = accessibleAirportFromPreview(previewAtBusStop);
      const airportListAnchor = coordinateForFlightAirportListAnchor(previewAtBusStop);
      const airportRowsAllHaveDistance = [...state.airportByIata.values()]
        .filter((feature) => state.flightsByOriginAirport.has(feature.properties?.iata))
        .slice(0, 16)
        .every((feature) => Number.isFinite(coordinateDistanceMeters(airportListAnchor, feature.geometry?.coordinates)));
      const flight = (state.flightsByOriginAirport.get(iata) || [])
        .filter((candidate) => flightOperatesForGameDay(candidate))
        .find((candidate) => flightCatchability(candidate, previewAtBusStop).ok);
      let afterFlightPreview = null;
      let addedFlightStep = false;
      if (flight) {
        state.flightPlanning[state.activeMode] = { origin: iata, destination: flight.destinationAirport };
        buyFlightTicket(flight.physicalFlightId);
        addFlightStep(flight.physicalFlightId);
        await sleep(80);
        addedFlightStep = activePlayer().steps.some((step) =>
          step.type === 'TAKE_FLIGHT' && step.flight_id === flight.physicalFlightId
        );
        afterFlightPreview = planCursorPreview(state.activeMode);
      }

      results.push({
        iata,
        airportName: airportName(iata),
        airportLoaded: Boolean(airport),
        nearestStation: station ? {
          stationGroupId: station.stationGroupId,
          label: displayNameForGroup(station.stationGroupId),
          distanceMeters: Math.round(station.distanceMeters),
        } : null,
        tileCount,
        airportStop: airportStop ? {
          stopId: airportStop.id,
          name: airportStop.name,
          distanceMeters: Math.round(airportStops[0].distanceMeters),
        } : null,
        previewAtBusStop: {
          kind: previewAtBusStop?.currentState?.kind || null,
          busStopId: previewAtBusStop?.currentState?.busStopId || null,
          currentMinute: previewAtBusStop?.currentMinute || null,
        },
        accessibleFromPreview,
        airportListAnchor,
        airportRowsAllHaveDistance,
        flight: flight ? {
          flightId: flight.physicalFlightId,
          label: flightDisplayLabel(flight),
          destinationAirport: flight.destinationAirport,
          departureTimeLocal: flight.departureTimeLocal,
        } : null,
        addedFlightStep,
        afterFlightPreview: afterFlightPreview ? {
          kind: afterFlightPreview.currentState?.kind,
          stationGroupId: afterFlightPreview.currentState?.stationGroupId || null,
          currentMinute: afterFlightPreview.currentMinute,
        } : null,
      });
    }
    return results;
  }, { sampleIatas });

  const failures = [...dataAudit.failures];
  for (const result of interaction) {
    if (!result.airportLoaded) failures.push({ message: `Airport ${result.iata} did not load in web airport map`, details: result });
    if (!result.airportStop) failures.push({ message: `No loaded airport bus stop near ${result.iata}`, details: result });
    if (result.previewAtBusStop.kind !== 'BUS_STOP') failures.push({ message: `Airport bus access did not leave player at BUS_STOP for ${result.iata}`, details: result });
    if (result.accessibleFromPreview?.iata !== result.iata) failures.push({ message: `BUS_STOP preview should be recognized as airport ${result.iata}`, details: result });
    if (!result.airportRowsAllHaveDistance) failures.push({ message: `Departure airport list should have distance labels from BUS_STOP at ${result.iata}`, details: result });
    if (!result.flight) failures.push({ message: `No catchable outbound flight from airport bus stop at ${result.iata}`, details: result });
    if (!result.addedFlightStep) failures.push({ message: `Could not add TAKE_FLIGHT from airport bus stop at ${result.iata}`, details: result });
  }

  const output = {
    failureCount: failures.length,
    failures,
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
