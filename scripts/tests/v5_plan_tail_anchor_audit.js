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

function writeJson(filePath, payload) {
  if (!filePath) return;
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

async function main() {
  const args = parseArgs(process.argv);
  const outputPath = args.output || path.resolve(__dirname, '../../data/v5_plan_tail_anchor_audit.json');
  const docsOutputPath = args['docs-output'] || path.resolve(__dirname, '../../docs/data/v5_plan_tail_anchor_audit.json');
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
  await page.waitForFunction(
    () => state.timetableStatus === 'ready' && state.shipSailingById?.size && state.flightById?.size && state.map?.getSource?.('player-markers'),
    null,
    { timeout: 120000 },
  );

  const result = await page.evaluate(async () => {
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const textFromRows = (rows) => rows.map((html) => html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim());
    const rowHasDistance = (text) =>
      /\d+(?:\.\d+)?\s*km/.test(text) ||
      /\d+\s*m/.test(text) ||
      /current bus stop/.test(text);
    const markerSample = (name, preview, minute = null) => {
      if (Number.isFinite(minute)) state.currentGameMinute = minute;
      updatePlayerMarkers();
      const markerFeatures = state.map.getSource('player-markers')._data.features || [];
      const runnerFeature = markerFeatures.find((feature) => feature.properties?.role === 'RUNNER') || null;
      return {
        name,
        time: preview?.currentTime || null,
        kind: preview?.currentState?.kind || null,
        label: playerMarkerLabel(preview),
        hasPreviewCoordinate: validCoordinate(preview?.mapPosition),
        hasLayerCoordinate: validCoordinate(runnerFeature?.geometry?.coordinates),
      };
    };

    state.phase = 'PLANNING';
    state.latestResult = null;
    state.activeMode = 'runner';
    state.currentGameMinute = hhmmToMinutes(state.startTime);
    const player = activePlayer();
    player.steps = [];
    player.flight_ticket = null;
    player.start_station_id = nearestStationGroupForPort('高松港')?.stationGroupId || player.start_station_id;

    const teshimaFirst = [...state.shipSailingById.values()]
      .find((item) => item.originPort === '高松港' && item.destinationPort === '家浦');
    state.shipPlanning.runner = { origin: '高松港', destination: '家浦' };
    state.planningModes.runner = 'ship';
    addShipStep(teshimaFirst?.sailingId);
    const teshimaTail = previewPlayer('runner', null);
    const teshimaReturn = [...state.shipSailingById.values()]
      .filter((item) => item.originPort === '家浦' && item.destinationPort === '高松港')
      .filter((item) => Number(item.departureMinute) >= Number(teshimaTail.currentMinute || 0))
      .sort((a, b) => Number(a.departureMinute) - Number(b.departureMinute))[0] || null;
    state.shipPlanning.runner = { origin: '家浦', destination: '高松港' };
    addShipStep(teshimaReturn?.sailingId);
    const roundTripTail = previewPlayer('runner', null);

    const takFlight = [...state.flightById.values()]
      .find((item) => item.originAirport === 'TAK' && item.destinationAirport === 'HND' && item.departureTimeLocal === '09:45')
      || [...state.flightById.values()].find((item) => item.originAirport === 'TAK' && item.destinationAirport === 'HND')
      || null;
    if (takFlight) {
      player.flight_ticket = {
        flight_id: takFlight.physicalFlightId,
        flight_number: flightOperatingNumber(takFlight),
        origin_airport: takFlight.originAirport,
        destination_airport: takFlight.destinationAirport,
        purchase_hhmm: state.startTime,
        departure_hhmm: takFlight.departureTimeLocal,
        arrival_hhmm: takFlight.arrivalTimeLocal,
        fare: resolveFlightFare(takFlight),
      };
      planFlightBusAccess(takFlight.physicalFlightId);
      await sleep(1400);
      if (state.busPlannerLoadStatus === 'ready') await refreshBusPlannerVisibleData();
    }
    const takBusPreview = planCursorPreview('runner');
    const takBusRows = busStopRowsHtml(takBusPreview, busPlanningState('runner').targetAirportIata);

    state.planningModes.runner = 'ship';
    state.shipPlanning.runner = { origin: null, destination: null };
    const shipPortRowTexts = textFromRows(shipPortRowsFromPreview(roundTripTail).slice(0, 12));

    state.planningModes.runner = 'flight';
    state.flightPlanning.runner = { origin: null, destination: null };
    const flightRowTexts = textFromRows(flightAirportRowsFromPreview(roundTripTail).slice(0, 16));

    const shodoSailing = [...state.shipSailingById.values()]
      .find((item) => item.sailingId === 'shodoshima_takamatsu_tonosho_064_out_001');
    player.steps = [];
    player.flight_ticket = null;
    player.start_station_id = nearestStationGroupForPort('高松港')?.stationGroupId || player.start_station_id;
    state.currentGameMinute = hhmmToMinutes(state.startTime);
    state.shipPlanning.runner = { origin: shodoSailing?.originPort, destination: shodoSailing?.destinationPort };
    state.planningModes.runner = 'ship';
    addShipStep(shodoSailing?.sailingId);
    const portWaitPreview = previewPlayer('runner', Number(shodoSailing.departureMinute) - 1);
    const shipPreview = previewPlayer('runner', Math.floor((Number(shodoSailing.departureMinute) + Number(shodoSailing.arrivalMinute)) / 2));
    const busStopPreview = previewPlayer('runner', null);

    const markers = [
      markerSample('portWait', portWaitPreview, Number(shodoSailing.departureMinute) - 1),
      markerSample('ship', shipPreview, Math.floor((Number(shodoSailing.departureMinute) + Number(shodoSailing.arrivalMinute)) / 2)),
      markerSample('shipArrivalBusStop', busStopPreview, busStopPreview.currentMinute),
    ];

    const hndFlight = [...state.flightById.values()]
      .find((item) => item.originAirport === 'HND' && item.destinationAirport && flightOperatesForGameDay(item));
    if (hndFlight) {
      const hndStop = [...state.busPlannerStopsById.values()].find((stop) => busStopAirportIata(stop.id) === 'HND');
      if (hndStop) {
        player.steps = [{
          type: 'WALK_TO_BUS_STOP',
          station_id: nearestStationGroupForAirport('HND')?.stationGroupId,
          bus_stop_id: hndStop.id,
          distance_meters: 0,
          walk_time_sec: 0,
          walking_speed_mps: activeWalkingSpeedMetersPerSecond(),
        }];
        player.flight_ticket = null;
        state.currentGameMinute = hhmmToMinutes(state.startTime);
        const airportPreview = previewPlayer('runner', null);
        markers.push(markerSample('airportBusStop', airportPreview, airportPreview.currentMinute));
      }
    }

    return {
      teshima: {
        firstSailingId: teshimaFirst?.sailingId || null,
        returnSailingId: teshimaReturn?.sailingId || null,
        roundTripTailTime: roundTripTail.currentTime,
        roundTripTailKind: roundTripTail.currentState?.kind || null,
        roundTripTailPort: roundTripTail.currentState?.portName || null,
        takBusAccessTime: takBusPreview.currentTime,
        takBusAccessKind: takBusPreview.currentState?.kind || null,
        takBusAccessPort: takBusPreview.currentState?.portName || null,
        takBusRows: textFromRows(takBusRows),
      },
      distanceRows: {
        shipPortRowsChecked: shipPortRowTexts.length,
        shipPortRowsMissingDistance: shipPortRowTexts.filter((text) => !rowHasDistance(text)),
        flightRowsChecked: flightRowTexts.length,
        flightRowsMissingDistance: flightRowTexts.filter((text) => !rowHasDistance(text)),
        busRowsChecked: takBusRows.length,
        busRowsMissingDistance: textFromRows(takBusRows).filter((text) => !rowHasDistance(text)),
      },
      markers,
    };
  });

  const failures = [];
  const toMinutes = (text) => {
    const [hour, minute] = String(text || '00:00').split(':').map((value) => Number(value));
    return (Number.isFinite(hour) ? hour : 0) * 60 + (Number.isFinite(minute) ? minute : 0);
  };
  if (!result.teshima.firstSailingId) failures.push('missing_teshima_first_sailing');
  if (!result.teshima.returnSailingId) failures.push('missing_teshima_return_sailing');
  if (result.teshima.roundTripTailPort === '家浦') failures.push('round_trip_tail_stuck_at_ieura');
  if (toMinutes(result.teshima.takBusAccessTime) < toMinutes('08:55')) failures.push(`tak_bus_access_not_from_plan_end_${result.teshima.takBusAccessTime}`);
  if (result.teshima.takBusAccessPort === '家浦') failures.push('tak_bus_access_stuck_at_ieura');
  if (!result.teshima.takBusRows.length) failures.push('missing_tak_bus_access_rows');
  if (result.distanceRows.shipPortRowsMissingDistance.length) failures.push('ship_port_distance_missing');
  if (result.distanceRows.flightRowsMissingDistance.length) failures.push('flight_airport_distance_missing');
  if (result.distanceRows.busRowsMissingDistance.length) failures.push('bus_stop_distance_missing');
  for (const marker of result.markers) {
    if (!marker.hasPreviewCoordinate || !marker.hasLayerCoordinate) failures.push(`missing_marker_coordinate_${marker.name}_${marker.kind}`);
  }
  if (consoleMessages.length) failures.push(`console_messages_${consoleMessages.length}`);

  const output = {
    schemaVersion: 'v5_plan_tail_anchor_audit_v1',
    summary: {
      failureCount: failures.length,
      markerCount: result.markers.length,
      shipPortRowsChecked: result.distanceRows.shipPortRowsChecked,
      flightRowsChecked: result.distanceRows.flightRowsChecked,
      busRowsChecked: result.distanceRows.busRowsChecked,
      takBusAccessTime: result.teshima.takBusAccessTime,
      takBusAccessKind: result.teshima.takBusAccessKind,
    },
    failures,
    result,
    consoleMessages,
  };
  writeJson(outputPath, output);
  writeJson(docsOutputPath, output);
  await browser.close();
  if (failures.length) {
    console.error(`FAIL v5 plan tail anchors: failures=${failures.length}`);
    process.exit(1);
  }
  console.log(
    `OK v5 plan tail anchors: markers=${output.summary.markerCount} ` +
    `shipRows=${output.summary.shipPortRowsChecked} ` +
    `flightRows=${output.summary.flightRowsChecked} ` +
    `busRows=${output.summary.busRowsChecked} ` +
    `takBus=${output.summary.takBusAccessTime}`
  );
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
