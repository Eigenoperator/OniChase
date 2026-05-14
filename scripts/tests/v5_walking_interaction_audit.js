#!/usr/bin/env node

const { chromium } = require('playwright');

function parseArgs(argv) {
  const args = { 'walk-radius-km': '2' };
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
  const expectedRadiusMeters = Math.round(Number(args['walk-radius-km']) * 1000);
  if (!Number.isFinite(expectedRadiusMeters) || expectedRadiusMeters <= 0) {
    throw new Error(`Invalid --walk-radius-km: ${args['walk-radius-km']}`);
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const consoleMessages = [];
  page.on('console', (message) => {
    const text = message.text();
    if (!text.includes('GPU stall') && !text.includes('12288-12543.pbf') && !text.includes('Failed to load resource')) {
      consoleMessages.push(`${message.type()}: ${text}`);
    }
  });
  page.on('pageerror', (error) => consoleMessages.push(`pageerror: ${error.message}`));

  await page.goto(args['page-url'], { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.click('#advanced-setup-button');
  await page.click('#single-runner-button');
  await page.waitForFunction(() => state.timetableStatus === 'ready', null, { timeout: 120000 });

  const interaction = await page.evaluate(async () => {
    const modeText = () => document.querySelector('#train-outlook')?.innerText || '';
    const railButton = () => document.querySelector('[data-action="choose-mode"][data-mode="rail"]');
    const walkButton = () => document.querySelector('[data-action="choose-mode"][data-mode="walk"]');
    const activeRows = (selector) => [...document.querySelectorAll(selector)]
      .filter((node) => !node.classList.contains('planner-row-exit'));
    const routeRows = () => activeRows('[data-action="choose-route"]').length;
    const walkRows = () => activeRows('[data-action="walk-to-station"]').length;
    const click = (node) => {
      node.click();
      return new Promise((resolve) => setTimeout(resolve, 260));
    };

    const before = {
      mode: activePlanningMode(),
      routeRows: routeRows(),
      walkRows: walkRows(),
      walkingMapActive: state.walkingMapActive,
      text: modeText(),
    };
    await click(walkButton());
    const afterWalk = {
      mode: activePlanningMode(),
      routeRows: routeRows(),
      walkRows: walkRows(),
      walkingMapActive: state.walkingMapActive,
      text: modeText(),
    };
    await click(railButton());
    const afterRail = {
      mode: activePlanningMode(),
      routeRows: routeRows(),
      walkRows: walkRows(),
      walkingMapActive: state.walkingMapActive,
      text: modeText(),
    };
    return { before, afterWalk, afterRail };
  });

  const result = await page.evaluate(({ expectedRadiusMeters }) => {
    const failures = [];
    const check = (condition, message, details = {}) => {
      if (!condition) failures.push({ message, details });
    };

    check(V5_ACTIVE_WALKING_THRESHOLD_METERS === expectedRadiusMeters, 'Configured walking radius does not match audit argument', {
      expectedRadiusMeters,
      actualRadiusMeters: V5_ACTIVE_WALKING_THRESHOLD_METERS,
    });

    const walkingDistances = [...state.walkingEdgesByFromGroupId.values()].flat().map((edge) => edge.distanceMeters);
    const maxIndexedDistance = Math.max(...walkingDistances);
    check(maxIndexedDistance <= expectedRadiusMeters, 'Walking graph includes edge beyond active radius', { maxIndexedDistance, expectedRadiusMeters });
    const hasNearRadiusEdge = walkingDistances.some((distance) => distance > expectedRadiusMeters * 0.75 && distance <= expectedRadiusMeters);
    check(hasNearRadiusEdge, 'Walking graph should include at least one edge near the configured radius', { expectedRadiusMeters });

    const sameNameWalking = [];
    for (const [fromGroupId, edges] of state.walkingEdgesByFromGroupId.entries()) {
      const fromName = displayNameForGroup(fromGroupId);
      const match = (edges || []).find((edge) =>
        edge.toNodeId !== fromGroupId &&
        displayNameForGroup(edge.toNodeId) === fromName &&
        edge.distanceMeters > 0 &&
        edge.distanceMeters <= expectedRadiusMeters
      );
      if (!match) continue;
      const link = walkingTransferLinkBetween(fromGroupId, match.toNodeId, state.activeMode);
      sameNameWalking.push({ fromGroupId, toGroupId: match.toNodeId, name: fromName, edge: match, link });
      break;
    }
    check(sameNameWalking.length > 0, 'No same-name different-station walking transfer sample found');
    if (sameNameWalking[0]) {
      check(sameNameWalking[0].link?.transferMinutes > 0, 'Same-name different-station transfer must use walking time', sameNameWalking[0]);
      check(sameNameWalking[0].link?.distanceMeters > 0, 'Same-name different-station transfer must carry walking distance', sameNameWalking[0]);
    }

    const normalTrip = [...state.tripById.values()].find((trip) => !isShinkansenTrip(trip));
    const shinkansenTrip = [...state.tripById.values()].find((trip) => isShinkansenTrip(trip));
    const groupEntry = [...state.physicalStationsByGroupId.entries()]
      .find(([, stations]) => (stations || []).filter((station) => station?.id).length >= 2);
    check(Boolean(normalTrip && shinkansenTrip && groupEntry), 'Missing trip or physical-station sample data');
    let transferSamples = null;
    if (normalTrip && shinkansenTrip && groupEntry) {
      const [stationGroupId, stations] = groupEntry;
      const firstPhysicalId = stations[0].id;
      const secondPhysicalId = stations[1].id;
      const normalStop = normalTrip.stopTimes?.[0] || null;
      const shinkansenStop = shinkansenTrip.stopTimes?.[0] || null;
      const initialLink = sameStationGroupTransferLink(stationGroupId, state.activeMode, {
        boardTrip: normalTrip,
        boardStop: normalStop,
        boardPhysicalStationId: firstPhysicalId,
      });
      const samePhysicalLink = sameStationGroupTransferLink(stationGroupId, state.activeMode, {
        fromTrip: normalTrip,
        boardTrip: normalTrip,
        boardStop: normalStop,
        fromPhysicalStationId: firstPhysicalId,
        boardPhysicalStationId: firstPhysicalId,
      });
      const shinkansenLink = sameStationGroupTransferLink(stationGroupId, state.activeMode, {
        fromTrip: normalTrip,
        boardTrip: shinkansenTrip,
        boardStop: shinkansenStop,
        fromPhysicalStationId: firstPhysicalId,
        boardPhysicalStationId: secondPhysicalId,
      });
      transferSamples = {
        stationGroupId,
        stationName: displayNameForGroup(stationGroupId),
        initialLink,
        samePhysicalLink,
        shinkansenLink,
      };
      check(initialLink.transferMinutes === 0, 'Initial same-station boarding should remain 0 minutes', initialLink);
      check(samePhysicalLink.transferMinutes >= 1, 'Post-ride same-station physical transfer must not be 0', samePhysicalLink);
      check(shinkansenLink.transferMinutes >= 5, 'Shinkansen/non-Shinkansen same-station transfer must be at least 5 minutes', shinkansenLink);
      check(shinkansenLink.minimumTransferMinutes === 5, 'Shinkansen/non-Shinkansen minimum metadata should be 5', shinkansenLink);
    }

    return {
      failureCount: failures.length,
      failures,
      samples: {
        maxIndexedDistance,
        sameNameWalking: sameNameWalking[0] || null,
        transferSamples,
      },
    };
  }, { expectedRadiusMeters });

  const modeFailures = [];
  const checkMode = (condition, message, details = {}) => {
    if (!condition) modeFailures.push({ message, details });
  };
  checkMode(interaction.before.mode === 'rail', 'Planner should start in rail mode', interaction.before);
  checkMode(interaction.before.routeRows > 0, 'Rail mode should show route rows before switching', interaction.before);
  checkMode(interaction.afterWalk.mode === 'walk', 'Walk mode button should switch active mode to walk', interaction.afterWalk);
  checkMode(interaction.afterWalk.walkingMapActive, 'Walk mode should activate walking map', interaction.afterWalk);
  checkMode(interaction.afterWalk.walkRows > 0, 'Walk mode should show walking rows', interaction.afterWalk);
  checkMode(interaction.afterWalk.routeRows === 0, 'Walk mode should hide rail route rows', interaction.afterWalk);
  checkMode(interaction.afterRail.mode === 'rail', 'Rail mode button should switch active mode back to rail', interaction.afterRail);
  checkMode(!interaction.afterRail.walkingMapActive, 'Rail mode should deactivate walking map', interaction.afterRail);
  checkMode(interaction.afterRail.routeRows > 0, 'Rail mode should restore route rows', interaction.afterRail);

  const output = {
    interaction,
    ...result,
    failureCount: result.failureCount + modeFailures.length,
    failures: [...modeFailures, ...result.failures],
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
