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
  args['max-failures'] = Number.parseInt(args['max-failures'] || '0', 10);
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
      const samples = [];
      const normalize = (value) => String(value || '').trim().toLowerCase();
      const stations = ['東京', '新宿', '大阪', '京都', '名古屋', '金沢', '博多'];
      const stationGroupIdByName = (stationName) => [...state.stationGroupById.entries()]
        .find(([, group]) => (group.names?.ja || group.primaryName) === stationName)?.[0] || null;
      const expectedMapColor = (routeId) => {
        const geometryColor = (state.serviceGeometryByRouteId.get(routeId) || [])
          .map((geometry) => geometry?.color)
          .find(Boolean);
        if (geometryColor) return geometryColor;
        const trackColor = routeTrackGeometries(routeId)
          .map((track) => track?.color)
          .find(Boolean);
        if (trackColor) return trackColor;
        return state.routeById.get(routeId)?.color || '#667487';
      };

      state.phase = 'PLANNING';
      state.clockRunning = false;
      state.activeMode = 'runner';
      state.currentGameMinute = hhmmToMinutes('06:00');
      state.pendingTripIds = { runner: null, hunter: null };
      state.planningRouteIds = { runner: null, hunter: null };
      state.pendingCoupledChoices = { runner: null, hunter: null };
      state.selectedRouteId = null;
      state.selectedTripId = null;

      stations.forEach((stationName) => {
        const stationGroupId = stationGroupIdByName(stationName);
        if (!stationGroupId) return;
        state.players.runner = { start_station_id: stationGroupId, input_mode: 'plan', steps: [] };
        state.trainOutlookHtml = '';
        renderGame();
        [...document.querySelectorAll('#train-outlook .route-row[data-action="choose-route"]')].slice(0, 20).forEach((row) => {
          const routeId = row.dataset.routeId;
          if (!routeId || isNamedTrainChoiceRouteId(routeId)) return;
          const plannerColor = row.querySelector('.route-swatch')?.style.background || '';
          const functionColor = routeColor(routeId);
          const mapColor = expectedMapColor(routeId);
          const sample = {
            stationName,
            routeId,
            routeTitle: routeTitle(routeId),
            plannerColor,
            functionColor,
            mapColor,
          };
          samples.push(sample);
          if (normalize(functionColor) !== normalize(mapColor)) failures.push(sample);
        });
      });

      return {
        checkedStations: stations,
        sampleCount: samples.length,
        samples: samples.slice(0, 30),
        failureCount: failures.length,
        failures,
      };
    });

    const relevantConsoleMessages = consoleMessages.filter((message) => !message.includes('Failed to load resource'));
    if (relevantConsoleMessages.length) {
      result.failures.push({ consoleMessages: relevantConsoleMessages.slice(0, 20) });
      result.failureCount = result.failures.length;
    }
    result.ok = result.failureCount <= args['max-failures'];
    console.log(JSON.stringify(result, null, 2));
    if (!result.ok) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
