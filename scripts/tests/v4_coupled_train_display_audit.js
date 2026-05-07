#!/usr/bin/env node

const { chromium } = require('playwright');

function parseArgs(argv) {
  const args = {};
  for (let index = 2; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith('--')) continue;
    const next = argv[index + 1];
    args[key.slice(2)] = next && !next.startsWith('--') ? next : true;
    if (args[key.slice(2)] !== true) index += 1;
  }
  if (!args['page-url']) throw new Error('Missing --page-url');
  return args;
}

(async () => {
  const args = parseArgs(process.argv);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const consoleMessages = [];
  page.on('console', (message) => {
    const text = message.text();
    if (!text.includes('GPU stall')) consoleMessages.push(`${message.type()}: ${text}`);
  });
  page.on('pageerror', (error) => consoleMessages.push(`pageerror: ${error.message}`));

  try {
    await page.goto(args['page-url'], { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForFunction(() => typeof state !== 'undefined' && Boolean(state.bundle), null, { timeout: 90000 });
    await page.evaluate(() => ensureTimetableLoaded());
    await page.waitForFunction(() => state.timetableStatus === 'ready', null, { timeout: 90000 });

    const result = await page.evaluate(() => {
      const failures = [];
      const stationNames = ['東京', '大阪', '京都', '岡山', '日根野', '宇多津', '多度津', '博多', '早岐'];
      const stationGroupIdByName = (stationName) => [...state.stationGroupById.entries()]
        .find(([, group]) => (group.names?.ja || group.primaryName) === stationName)?.[0] || null;

      state.phase = 'PLANNING';
      state.clockRunning = false;
      state.activeMode = 'runner';
      state.currentGameMinute = hhmmToMinutes('05:30');

      let found = null;
      for (const stationName of stationNames) {
        const stationGroupId = stationGroupIdByName(stationName);
        if (!stationGroupId) continue;
        state.players.runner = { start_station_id: stationGroupId, input_mode: 'plan', steps: [] };
        state.pendingTripIds = { runner: null, hunter: null };
        state.pendingCoupledChoices = { runner: null, hunter: null };
        state.planningRouteIds = { runner: null, hunter: null };
        state.selectedTripId = null;
        state.selectedRouteId = null;
        state.trainOutlookHtml = '';
        renderGame();
        const routeButtons = [...document.querySelectorAll('#train-outlook .route-row[data-action="choose-route"]')];
        for (const routeButton of routeButtons) {
          choosePlanningRoute(routeButton.dataset.routeId);
          const coupledButton = document.querySelector('#train-outlook .outlook-row[data-action="choose-coupled"]');
          if (coupledButton) {
            found = {
              stationName,
              routeId: routeButton.dataset.routeId,
              routeTitle: routeTitle(routeButton.dataset.routeId),
              coupledKey: coupledButton.dataset.coupledKey,
              rowTitle: coupledButton.querySelector('.row-title')?.textContent.trim() || '',
              rowSub: coupledButton.querySelector('.row-sub')?.textContent.trim() || '',
            };
            break;
          }
          backToPlanningRoutes();
        }
        if (found) break;
      }

      if (!found) {
        failures.push({ message: 'No coupled umbrella row found in sampled stations' });
        return { ok: false, failureCount: failures.length, failures, found: null };
      }

      chooseCoupledTrain(found.coupledKey);
      const stepIndex = document.querySelector('#train-outlook .planner-step-index')?.textContent.trim() || '';
      const title = document.querySelector('#train-outlook .planner-step-title')?.textContent.trim() || '';
      const portionRows = document.querySelectorAll('#train-outlook [data-row-key^="portion:"]').length;
      const destinationRows = document.querySelectorAll('#train-outlook .destination-row[data-action="ride-here"]').length;
      const pendingTrip = pendingTripId('runner');
      const pendingChoice = pendingCoupledChoice('runner');

      if (stepIndex !== '3/3') failures.push({ message: 'Coupled train should go directly to 3/3', stepIndex, title, found });
      if (portionRows <= 0 && destinationRows <= 0) failures.push({ message: 'Coupled train should expose either direction rows or alighting destination rows', portionRows, destinationRows, found });
      if (portionRows <= 0 && !pendingTrip) failures.push({ message: 'Coupled train should select a representative physical trip when no future split remains', found });
      if (!pendingChoice) failures.push({ message: 'Coupled train should retain coupled context for union destination rows', found });

      const tokyoStationGroupId = stationGroupIdByName('東京');
      if (tokyoStationGroupId) {
        prepareLocalSession('runner', { startStationId: tokyoStationGroupId, startTime: '20:00', endTime: '36:00' });
        state.currentGameMinute = hhmmToMinutes('20:00');
        state.phase = 'PLANNING';
        state.activeMode = 'runner';
        state.pendingTripIds = { runner: null, hunter: null };
        state.pendingCoupledChoices = { runner: null, hunter: null };
        state.planningRouteIds = { runner: null, hunter: null };
        state.selectedTripId = null;
        state.selectedRouteId = null;
        state.trainOutlookHtml = '';
        renderGame();
        const sunriseChoice = routeChoicesFromDepartures(availableDepartures(planCursorPreview('runner')))
          .find((choice) => routeTitle(choice.routeId) === 'サンライズ瀬戸・出雲');
        if (!sunriseChoice) {
          failures.push({ message: 'Tokyo should expose Sunrise Seto/Izumo route choice' });
        } else {
          choosePlanningRoute(sunriseChoice.routeId);
          const sunriseRow = [...document.querySelectorAll('#train-outlook .outlook-row[data-action="choose-coupled"]')]
            .find((row) => row.querySelector('.row-title')?.textContent.trim() === 'サンライズ瀬戸・出雲');
          if (!sunriseRow) {
            failures.push({ message: 'Tokyo Sunrise should render one coupled umbrella row' });
          } else {
            chooseCoupledTrain(sunriseRow.dataset.coupledKey);
            const portionRows = [...document.querySelectorAll('#train-outlook [data-row-key^="portion:"]')];
            const portionLabels = portionRows.map((row) => row.querySelector('.row-title')?.textContent.trim() || '');
            if (!portionLabels.includes('サンライズ瀬戸') || !portionLabels.includes('サンライズ出雲')) {
              failures.push({
                message: 'Tokyo Sunrise toward a future split must ask which portion/direction to ride before alighting stops',
                portionLabels,
              });
            }
            const setoRow = portionRows.find((row) => row.querySelector('.row-title')?.textContent.trim() === 'サンライズ瀬戸');
            if (setoRow) chooseTrip(setoRow.dataset.tripId);
            const pendingSunrise = pendingDepartureContext(planCursorPreview('runner'));
            const destinationLabels = new Set((pendingSunrise?.destinations || []).map((item) => item.label));
            const takamatsuDestination = (pendingSunrise?.destinations || []).find((item) => item.label === '高松');
            const izumoDestination = (pendingSunrise?.destinations || []).find((item) => item.label === '出雲市');
            if (!destinationLabels.has('高松')) {
              failures.push({
                message: 'Tokyo Sunrise Seto portion must expose Takamatsu after the portion is selected',
                destinationLabels: [...destinationLabels],
              });
            }
            if (destinationLabels.has('出雲市')) {
              failures.push({
                message: 'Tokyo Sunrise Seto portion must not expose the Izumo branch destination after choosing Seto',
                destinationLabels: [...destinationLabels],
              });
            }
            if (takamatsuDestination && !/瀬戸/u.test(formatTripLabel(state.tripById.get(takamatsuDestination.tripId)))) {
              failures.push({ message: 'Takamatsu destination should board the Seto portion', tripId: takamatsuDestination.tripId });
            }
          }
        }
      }

      const tokyoNexStationGroupId = stationGroupIdByName('東京');
      const shinjukuStationGroupId = stationGroupIdByName('新宿');
      if (tokyoNexStationGroupId && shinjukuStationGroupId) {
        prepareLocalSession('runner', { startStationId: tokyoNexStationGroupId, startTime: '06:00', endTime: '36:00' });
        state.currentGameMinute = hhmmToMinutes('06:00');
        state.phase = 'PLANNING';
        state.activeMode = 'runner';
        state.pendingTripIds = { runner: null, hunter: null };
        state.pendingCoupledChoices = { runner: null, hunter: null };
        state.planningRouteIds = { runner: null, hunter: null };
        state.selectedTripId = null;
        state.selectedRouteId = null;
        state.trainOutlookHtml = '';
        renderGame();
        const nexChoice = routeChoicesFromDepartures(availableDepartures(planCursorPreview('runner')))
          .find((choice) => routeTitle(choice.routeId) === '成田エクスプレス');
        if (!nexChoice) {
          failures.push({ message: 'Tokyo should expose Narita Express route choice' });
        } else {
          choosePlanningRoute(nexChoice.routeId);
          const nexToShinjukuRow = [...document.querySelectorAll('#train-outlook .outlook-row[data-action="choose-trip"], #train-outlook .outlook-row[data-action="choose-coupled"]')]
            .find((row) => /終点\s*新宿/u.test(row.textContent || ''));
          if (!nexToShinjukuRow) {
            failures.push({ message: 'Tokyo Narita Express should expose Shinjuku-bound rows after broad coupled alias filtering' });
          } else {
            if (nexToShinjukuRow.dataset.action === 'choose-coupled') {
              failures.push({
                message: 'A single Shinjuku-bound Narita Express row must not become a fake coupled umbrella from shared aliases',
                rowText: nexToShinjukuRow.textContent.trim(),
              });
            }
            chooseTrip(nexToShinjukuRow.dataset.tripId);
            const shinjukuDestination = [...document.querySelectorAll('#train-outlook .destination-row[data-action="ride-here"]')]
              .find((row) => row.dataset.stationGroupId === shinjukuStationGroupId || /新宿/u.test(row.textContent || ''));
            if (!shinjukuDestination) {
              failures.push({
                message: 'Selecting a Shinjuku-bound Narita Express at Tokyo must keep Shinjuku as an alighting destination',
                rowText: nexToShinjukuRow.textContent.trim(),
              });
            }
          }
        }
      }

      return {
        ok: failures.length === 0,
        failureCount: failures.length,
        failures,
        found,
        afterClick: { stepIndex, title, portionRows, destinationRows, pendingTrip, pendingChoice: Boolean(pendingChoice) },
      };
    });

    const relevantConsoleMessages = consoleMessages.filter((message) => !message.includes('Failed to load resource'));
    if (relevantConsoleMessages.length) {
      result.ok = false;
      result.failures.push({ message: 'Console/page errors appeared', consoleMessages: relevantConsoleMessages.slice(0, 20) });
      result.failureCount = result.failures.length;
    }
    console.log(JSON.stringify(result, null, 2));
    if (!result.ok) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
