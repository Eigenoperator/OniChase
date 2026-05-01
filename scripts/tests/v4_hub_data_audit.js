#!/usr/bin/env node

const { chromium } = require('playwright');

const MAPLIBRE_STUB = `
class FakeMap {
  constructor() {
    this.sources = new Map();
    this.layers = new Map();
    this.filters = {};
    this.canvas = { style: {} };
  }
  addControl() {}
  on(event, layerOrHandler, maybeHandler) {
    const handler = typeof layerOrHandler === 'function' ? layerOrHandler : maybeHandler;
    if (handler && event === 'load') setTimeout(handler, 0);
    return this;
  }
  addSource(id, source) {
    this.sources.set(id, {
      ...source,
      data: source.data,
      setData(data) { this.data = data; },
    });
  }
  getSource(id) { return this.sources.get(id) || null; }
  addLayer(layer) { this.layers.set(layer.id, layer); }
  getLayer(id) { return this.layers.get(id) || null; }
  setFilter(id, filter) { this.filters[id] = filter; }
  setLayoutProperty(id, key, value) {
    const layer = this.layers.get(id) || {};
    layer.layout = { ...(layer.layout || {}), [key]: value };
    this.layers.set(id, layer);
  }
  setPaintProperty(id, key, value) {
    const layer = this.layers.get(id) || {};
    layer.paint = { ...(layer.paint || {}), [key]: value };
    this.layers.set(id, layer);
  }
  getCanvas() { return this.canvas; }
  getZoom() { return 9; }
  fitBounds() {}
  queryRenderedFeatures() { return []; }
}
window.maplibregl = {
  Map: FakeMap,
  NavigationControl: class {},
  AttributionControl: class {},
};
`;

const HUB_CASES = [
  {
    station: '東京',
    selectByRoutes: ['東海道・山陽新幹線', '東北・北海道新幹線'],
    expect: [['東海道・山陽新幹線', 250], ['東北・北海道新幹線', 100], ['中央線快速', 500], ['成田エクスプレス', 50]],
  },
  {
    station: '新宿',
    selectByRoutes: ['山手線', '中央線快速'],
    expect: [['山手線', 1500], ['中央線快速', 800], ['あずさ', 20], ['かいじ', 18], ['成田エクスプレス', 10]],
  },
  {
    station: '横浜',
    selectByRoutes: ['東海道線', '京急本線'],
    expect: [['東海道線', 900], ['京急本線', 600], ['成田エクスプレス', 30], ['踊り子', 15]],
  },
  {
    station: '名古屋',
    selectByRoutes: ['東海道・山陽新幹線', '東海道線'],
    expect: [['東海道・山陽新幹線', 400], ['東海道線', 500], ['中央線', 120], ['名鉄（名古屋本線）', 800], ['近畿日本鉄道名古屋線', 150]],
  },
  {
    station: '京都',
    selectByRoutes: ['東海道・山陽新幹線', '東海道線'],
    expect: [['東海道・山陽新幹線', 400], ['東海道線', 350], ['奈良線', 90], ['サンダーバード', 30], ['はるか', 30]],
  },
  {
    station: '新大阪',
    selectByRoutes: ['東海道・山陽新幹線', '東海道線'],
    expect: [['東海道・山陽新幹線', 280], ['東海道線', 600], ['大阪市高速電気軌道御堂筋線', 400], ['はるか', 55], ['くろしお', 18]],
  },
  {
    station: '大阪',
    selectByRoutes: ['大阪環状線', '東海道線'],
    expect: [['大阪環状線', 300], ['東海道線', 650], ['くろしお', 30], ['こうのとり', 25]],
  },
  {
    station: '岡山',
    selectByRoutes: ['東海道・山陽新幹線', 'マリンライナー'],
    expect: [['東海道・山陽新幹線', 170], ['マリンライナー', 30], ['やくも', 14], ['しおかぜ', 14], ['南風', 14]],
  },
  {
    station: '広島',
    selectByRoutes: ['東海道・山陽新幹線', '山陽線'],
    expect: [['東海道・山陽新幹線', 130], ['山陽線', 250], ['広島電鉄本線', 300]],
  },
  {
    station: '小倉',
    selectByRoutes: ['東海道・山陽新幹線', '鹿児島線'],
    expect: [['東海道・山陽新幹線', 110], ['鹿児島線', 300], ['日豊線', 100], ['ソニック', 60]],
    forbid: ['近畿日本鉄道京都線', '奈良線'],
  },
  {
    station: '博多',
    selectByRoutes: ['東海道・山陽新幹線', '鹿児島線'],
    expect: [['東海道・山陽新幹線', 35], ['山陽・九州新幹線', 55], ['鹿児島線', 450], ['福岡市空港線', 500], ['ソニック', 30]],
  },
  {
    station: '熊本',
    selectByRoutes: ['山陽・九州新幹線', '鹿児島線'],
    expect: [['山陽・九州新幹線', 50], ['九州新幹線', 20], ['鹿児島線', 100], ['豊肥線', 50]],
  },
  {
    station: '鹿児島中央',
    selectByRoutes: ['九州新幹線', '鹿児島線'],
    expect: [['九州新幹線', 14], ['山陽・九州新幹線', 25], ['鹿児島線', 100], ['指宿枕崎線', 40], ['きりしま', 8]],
  },
  {
    station: '高松',
    selectByRoutes: ['マリンライナー', '予讃線'],
    expect: [['マリンライナー', 30], ['予讃線', 45], ['高徳線', 25], ['うずしお', 15], ['いしづち', 15]],
    forbid: ['七尾線', '多摩都市モノレール線'],
  },
  {
    station: '金沢',
    selectByRoutes: ['北陸新幹線', 'IRいしかわ鉄道線'],
    expect: [['北陸新幹線', 60], ['IRいしかわ鉄道線', 120], ['つるぎ', 30]],
  },
  {
    station: '仙台',
    selectByRoutes: ['東北・北海道新幹線', '東北本線'],
    expect: [['東北・北海道新幹線', 130], ['東北本線', 150], ['仙石線', 180], ['仙台市南北線', 300]],
  },
  {
    station: '新青森',
    selectByRoutes: ['東北・北海道新幹線', '奥羽線'],
    expect: [['東北・北海道新幹線', 40], ['奥羽線', 60], ['つがる', 4]],
  },
  {
    station: '新函館北斗',
    selectByRoutes: ['東北・北海道新幹線', '函館線'],
    expect: [['東北・北海道新幹線', 10], ['函館線', 60], ['はこだてライナー', 15]],
  },
  {
    station: '札幌',
    selectByRoutes: ['函館線'],
    expect: [['函館線', 500], ['宗谷', 2]],
  },
  {
    station: '那覇空港',
    selectByRoutes: ['沖縄都市モノレール線'],
    expect: [['沖縄都市モノレール線', 150]],
  },
  {
    station: '県庁前',
    selectByRoutes: ['沖縄都市モノレール線'],
    expect: [['沖縄都市モノレール線', 300]],
    forbid: ['富山地方鉄道支線', '千葉都市モノレール1号', '神戸市山手線'],
  },
];

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

async function loadPage(pageUrl) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.route('https://unpkg.com/**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/javascript',
    body: MAPLIBRE_STUB,
  }));
  await page.route('**/assets/vendor/maplibre-gl-*/maplibre-gl.js', (route) => route.fulfill({
    status: 200,
    contentType: 'application/javascript',
    body: MAPLIBRE_STUB,
  }));
  await page.route('**/assets/vendor/maplibre-gl-*/maplibre-gl.css', (route) => route.fulfill({
    status: 200,
    contentType: 'text/css',
    body: '',
  }));
  await page.goto(pageUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForFunction(() => typeof state !== 'undefined' && Boolean(state.bundle), null, { timeout: 90000 });
  await page.evaluate(() => ensureTimetableLoaded());
  await page.waitForFunction(() => state.timetableStatus === 'ready', null, { timeout: 90000 });
  return { browser, page };
}

async function auditHubData(page) {
  return page.evaluate((hubCases) => {
    const START_MINUTE = hhmmToMinutes('06:00');

    function groupName(stationGroupId) {
      return displayNameForGroup(stationGroupId);
    }

    function routeChoicesForGroup(stationGroupId, includeTransferEquivalents) {
      return routeChoicesFromDepartures(departuresForStationGroup(stationGroupId, START_MINUTE, { includeTransferEquivalents }))
        .map((choice) => ({
          route: routeTitle(choice.routeId),
          firstDeparture: choice.firstDepartureHhmm,
          trainCount: choice.trainCount,
        }));
    }

    function routeTitleSet(choices) {
      return new Set(choices.map((choice) => choice.route));
    }

    function groupIdsByDisplayName(name) {
      return [...state.stationGroupById.keys()].filter((stationGroupId) => groupName(stationGroupId) === name);
    }

    function compactChoiceList(choices) {
      return choices
        .slice()
        .sort((left, right) => left.route.localeCompare(right.route, 'ja'))
        .map((choice) => ({
          route: choice.route,
          trainCount: choice.trainCount,
          firstDeparture: choice.firstDeparture,
        }));
    }

    const anomalies = [];
    const results = [];

    hubCases.forEach((hubCase) => {
      const candidateGroups = groupIdsByDisplayName(hubCase.station)
        .map((stationGroupId) => ({
          stationGroupId,
          exactChoices: routeChoicesForGroup(stationGroupId, false),
        }));
      const selectedGroups = candidateGroups.filter((candidate) => {
        const exactTitles = routeTitleSet(candidate.exactChoices);
        return (hubCase.selectByRoutes || []).every((routeName) => exactTitles.has(routeName));
      });
      if (selectedGroups.length !== 1) {
        anomalies.push({
          kind: 'hub_station_disambiguation_failed',
          station: hubCase.station,
          selectByRoutes: hubCase.selectByRoutes,
          selectedGroupCount: selectedGroups.length,
          candidates: candidateGroups.map((candidate) => ({
            stationGroupId: candidate.stationGroupId,
            exactChoices: compactChoiceList(candidate.exactChoices),
          })),
        });
        return;
      }

      const selectedGroup = selectedGroups[0];
      const choices = routeChoicesForGroup(selectedGroup.stationGroupId, true);
      const choicesByRoute = new Map(choices.map((choice) => [choice.route, choice]));
      const missingOrUnderfilled = (hubCase.expect || [])
        .map(([routeName, minimumTrainCount]) => ({
          route: routeName,
          minimumTrainCount,
          actualTrainCount: choicesByRoute.get(routeName)?.trainCount || 0,
        }))
        .filter((item) => item.actualTrainCount < item.minimumTrainCount);
      const forbiddenPresent = (hubCase.forbid || [])
        .filter((routeName) => choicesByRoute.has(routeName));

      if (missingOrUnderfilled.length) {
        anomalies.push({
          kind: 'hub_expected_route_underfilled',
          station: hubCase.station,
          stationGroupId: selectedGroup.stationGroupId,
          missingOrUnderfilled,
          choices: compactChoiceList(choices),
        });
      }
      if (forbiddenPresent.length) {
        anomalies.push({
          kind: 'hub_forbidden_remote_route_present',
          station: hubCase.station,
          stationGroupId: selectedGroup.stationGroupId,
          forbiddenPresent,
          choices: compactChoiceList(choices),
        });
      }

      results.push({
        station: hubCase.station,
        stationGroupId: selectedGroup.stationGroupId,
        checkedRouteCount: (hubCase.expect || []).length,
        choiceCount: choices.length,
        expectedRoutes: Object.fromEntries((hubCase.expect || []).map(([routeName]) => [
          routeName,
          choicesByRoute.get(routeName)?.trainCount || 0,
        ])),
        forbiddenPresent,
      });
    });

    return {
      checkedAt: new Date().toISOString(),
      hubCaseCount: hubCases.length,
      checkedHubCount: results.length,
      anomalyCount: anomalies.length,
      results,
      anomalies,
    };
  }, HUB_CASES);
}

(async () => {
  const args = parseArgs(process.argv);
  const { browser, page } = await loadPage(args['page-url']);
  try {
    const result = await auditHubData(page);
    console.log(JSON.stringify(result, null, 2));
    if (result.anomalyCount) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
