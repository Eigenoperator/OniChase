#!/usr/bin/env node

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

async function main() {
  const args = parseArgs(process.argv);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
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
    () => state.timetableStatus === 'ready' && state.shipSailingById?.size && state.map?.getSource?.('player-markers'),
    null,
    { timeout: 120000 },
  );

  const result = await page.evaluate(() => {
    state.phase = 'PLANNING';
    state.latestResult = null;
    state.activeMode = 'runner';
    state.currentGameMinute = hhmmToMinutes(state.startTime);

    const sailing = [...state.shipSailingById.values()]
      .find((item) => item.sailingId === 'shodoshima_takamatsu_tonosho_064_out_001');
    if (!sailing) return { ok: false, reason: 'missing_takamatsu_tonosho_sailing' };

    const player = activePlayer();
    player.steps = [];
    player.flight_ticket = null;
    player.start_station_id = nearestStationGroupForPort('高松港')?.stationGroupId || player.start_station_id;
    state.shipPlanning.runner = { origin: sailing.originPort, destination: sailing.destinationPort };
    state.planningModes.runner = 'ship';
    addShipStep(sailing.sailingId);

    const sampleMinutes = {
      portWait: Math.max(hhmmToMinutes(state.startTime), Number(sailing.departureMinute) - 1),
      shipMid: Math.floor((Number(sailing.departureMinute) + Number(sailing.arrivalMinute)) / 2),
      arrival: Number(sailing.arrivalMinute),
    };
    const markerSamples = Object.entries(sampleMinutes).map(([name, minute]) => {
      const preview = previewPlayer('runner', minute);
      state.currentGameMinute = minute;
      updatePlayerMarkers();
      const markerFeatures = state.map.getSource('player-markers')._data.features || [];
      const runnerFeature = markerFeatures.find((feature) => feature.properties?.role === 'RUNNER') || null;
      return {
        name,
        time: minutesToHhmm(minute),
        kind: preview.currentState?.kind || null,
        hasPreviewCoordinate: validCoordinate(preview.mapPosition),
        hasLayerCoordinate: validCoordinate(runnerFeature?.geometry?.coordinates),
        label: playerMarkerLabel(preview),
      };
    });

    const tailPreview = previewPlayer('runner', null);
    state.planningModes.runner = 'ship';
    state.shipPlanning.runner = { origin: null, destination: null };
    const firstPorts = shipPortRowsFromPreview(tailPreview).slice(0, 5)
      .map((html) => (html.match(/data-port-name="([^"]+)/) || [])[1])
      .filter(Boolean);
    state.shipPlanning.runner = { origin: '土庄港', destination: null };
    const onwardDestinations = shipDestinationRowsFromPreview(tailPreview)
      .map((html) => (html.match(/data-port-name="([^"]+)/) || [])[1])
      .filter(Boolean);

    state.currentGameMinute = hhmmToMinutes(state.startTime);
    player.steps = [];
    player.flight_ticket = null;
    player.start_station_id = nearestStationGroupForPort('高松港')?.stationGroupId || player.start_station_id;
    state.planningModes.runner = 'ship';
    state.shipPlanning.runner = { origin: '高松港', destination: null };
    const takamatsuDestinations = shipDestinationRowsFromPreview(previewPlayer('runner', null))
      .map((html) => (html.match(/data-port-name="([^"]+)/) || [])[1])
      .filter(Boolean);
    state.shipPlanning.runner = { origin: '女木港', destination: null };
    const megijimaDestinations = shipDestinationRowsFromPreview(previewPlayer('runner', null))
      .map((html) => (html.match(/data-port-name="([^"]+)/) || [])[1])
      .filter(Boolean);
    const meonCounts = {};
    state.shipSailingById.forEach((item) => {
      if (item.operator !== '雌雄島海運') return;
      const key = `${item.originPort}->${item.destinationPort}`;
      meonCounts[key] = (meonCounts[key] || 0) + 1;
    });
    const meonFirst = [...state.shipSailingById.values()]
      .find((item) => item.operator === '雌雄島海運' && item.originPort === '高松港' && item.destinationPort === '女木港');
    state.currentGameMinute = hhmmToMinutes(state.startTime);
    player.steps = [];
    player.flight_ticket = null;
    player.start_station_id = nearestStationGroupForPort('高松港')?.stationGroupId || player.start_station_id;
    state.shipPlanning.runner = { origin: '高松港', destination: '女木港' };
    state.planningModes.runner = 'ship';
    if (meonFirst) addShipStep(meonFirst.sailingId);
    const meonTail = previewPlayer('runner', null);
    state.shipPlanning.runner = { origin: '女木港', destination: '男木' };
    const megijimaToOgijimaRows = shipRowsFromPreview(meonTail);

    return {
      ok: true,
      sailingId: sailing.sailingId,
      markerSamples,
      tailKind: tailPreview.currentState?.kind || null,
      tailLabel: playerMarkerLabel(tailPreview),
      firstPorts,
      onwardDestinations,
      takamatsuDestinations,
      megijimaDestinations,
      meonCounts,
      meonFirstSailingId: meonFirst?.sailingId || null,
      meonTailKind: meonTail.currentState?.kind || null,
      meonTailLabel: playerMarkerLabel(meonTail),
      megijimaToOgijimaRowCount: megijimaToOgijimaRows.length,
      shipMapActive: state.shipMapActive,
    };
  });

  await browser.close();

  const failures = [];
  if (!result.ok) failures.push(result.reason || 'audit_failed');
  for (const sample of result.markerSamples || []) {
    if (!sample.hasPreviewCoordinate || !sample.hasLayerCoordinate) failures.push(`missing_marker_${sample.name}_${sample.kind}`);
  }
  if (result.tailKind !== 'BUS_STOP') failures.push(`unexpected_tail_${result.tailKind}`);
  if (result.firstPorts?.[0] !== '土庄港') failures.push(`first_ship_port_${result.firstPorts?.[0] || 'missing'}`);
  if (!result.onwardDestinations?.includes('高松港')) failures.push('missing_tonosho_to_takamatsu');
  if (!result.takamatsuDestinations?.includes('女木港')) failures.push('missing_takamatsu_to_megijima');
  if (!result.megijimaDestinations?.includes('男木')) failures.push('missing_megijima_to_ogijima');
  for (const direction of ['高松港->女木港', '女木港->男木', '男木->女木港', '女木港->高松港']) {
    if (result.meonCounts?.[direction] !== 6) failures.push(`bad_meon_count_${direction}_${result.meonCounts?.[direction] || 0}`);
  }
  if (!result.meonFirstSailingId) failures.push('missing_meon_first_sailing');
  if (result.meonTailKind !== 'PORT_WAIT') failures.push(`bad_meon_tail_${result.meonTailKind}`);
  if (!result.megijimaToOgijimaRowCount) failures.push('missing_enabled_megijima_to_ogijima_rows');
  if (consoleMessages.length) failures.push(`console_messages_${consoleMessages.length}`);

  if (failures.length) {
    console.error(JSON.stringify({ ok: false, failures, result, consoleMessages }, null, 2));
    process.exit(1);
  }
  console.log(`OK v5 ship interaction: markers=${result.markerSamples.length}, firstPort=${result.firstPorts[0]}, onward=${result.onwardDestinations.length}, meon=${Object.keys(result.meonCounts).length}`);
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
