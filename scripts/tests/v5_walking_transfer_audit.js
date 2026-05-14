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
    if (!text.includes('GPU stall') && !text.includes('12288-12543.pbf')) {
      consoleMessages.push(`${message.type()}: ${text}`);
    }
  });
  page.on('pageerror', (error) => consoleMessages.push(`pageerror: ${error.message}`));

  await page.goto(args['page-url'], { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.click('#advanced-setup-button');
  await page.click('#single-runner-button');
  await page.waitForFunction(() => state.timetableStatus === 'ready', null, { timeout: 120000 });

  const result = await page.evaluate(() => {
    const failures = [];
    const check = (condition, message, details = {}) => {
      if (!condition) failures.push({ message, details });
    };

    const normalTrip = [...state.tripById.values()].find((trip) => !isShinkansenTrip(trip));
    const shinkansenTrip = [...state.tripById.values()].find((trip) => isShinkansenTrip(trip));
    const groupEntry = [...state.physicalStationsByGroupId.entries()]
      .find(([, stations]) => (stations || []).filter((station) => station?.id).length >= 2);
    if (!normalTrip || !shinkansenTrip || !groupEntry) {
      return { failureCount: 1, failures: [{ message: 'Missing test data for v5 walking transfer audit' }] };
    }

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
    check(initialLink.transferMinutes === 0, 'Initial same-station boarding should not gain transfer penalty', initialLink);

    const samePhysicalLink = sameStationGroupTransferLink(stationGroupId, state.activeMode, {
      fromTrip: normalTrip,
      boardTrip: normalTrip,
      boardStop: normalStop,
      fromPhysicalStationId: firstPhysicalId,
      boardPhysicalStationId: firstPhysicalId,
    });
    check(samePhysicalLink.transferMinutes >= 1, 'Ordinary same-station transfer must be at least 1 minute', samePhysicalLink);
    check(samePhysicalLink.reason === 'same_station_group_minimum', 'Ordinary same-station minimum should use explicit reason', samePhysicalLink);

    const shinkansenLink = sameStationGroupTransferLink(stationGroupId, state.activeMode, {
      fromTrip: normalTrip,
      boardTrip: shinkansenTrip,
      boardStop: shinkansenStop,
      fromPhysicalStationId: firstPhysicalId,
      boardPhysicalStationId: secondPhysicalId,
    });
    check(shinkansenLink.transferMinutes >= 5, 'Shinkansen/non-Shinkansen same-station transfer must be at least 5 minutes', shinkansenLink);
    check(shinkansenLink.minimumTransferMinutes === 5, 'Shinkansen minimum metadata should be 5 minutes', shinkansenLink);

    return {
      failureCount: failures.length,
      failures,
      samples: {
        stationGroupId,
        stationName: displayNameForGroup(stationGroupId),
        initialLink,
        samePhysicalLink,
        shinkansenLink,
      },
    };
  });

  await browser.close();
  console.log(JSON.stringify({ ...result, consoleMessages }, null, 2));
  if (result.failureCount) process.exit(1);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
