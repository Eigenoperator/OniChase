#!/usr/bin/env node

const fs = require('fs');
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

const SAME_NAME_CASES = [
  {
    station: '高松',
    prefecture: '香川県',
    selectByRoutes: ['予讃線', '高徳線'],
    expect: [['サンライズ瀬戸・出雲', 1], ['予讃線', 50]],
    forbid: ['七尾線', '多摩都市モノレール線'],
  },
  {
    station: '高松',
    prefecture: '東京都',
    selectByRoutes: ['多摩都市モノレール線'],
    expect: [['多摩都市モノレール線', 100]],
    forbid: ['サンライズ瀬戸・出雲', '予讃線', '七尾線'],
  },
  {
    station: '高松',
    prefecture: '石川県',
    selectByRoutes: ['七尾線'],
    expect: [['七尾線', 20]],
    forbid: ['サンライズ瀬戸・出雲', '多摩都市モノレール線'],
  },
  {
    station: '小倉',
    prefecture: '福岡県',
    selectByRoutes: ['東海道・山陽新幹線', '日豊線'],
    expect: [['東海道・山陽新幹線', 50], ['日豊線', 50]],
    forbid: ['近畿日本鉄道京都線'],
  },
  {
    station: '小倉',
    prefecture: '京都府',
    selectByRoutes: ['近畿日本鉄道京都線'],
    expect: [['近畿日本鉄道京都線', 100]],
    forbid: ['東海道・山陽新幹線', '日豊線'],
  },
  {
    station: '大宮',
    prefecture: '埼玉県',
    selectByRoutes: ['東北・北海道新幹線', '高崎線'],
    expect: [['東北・北海道新幹線', 50], ['高崎線', 50]],
    forbid: ['阪急電鉄京都線'],
  },
  {
    station: '大宮',
    prefecture: '京都府',
    selectByRoutes: ['阪急電鉄京都線'],
    expect: [['阪急電鉄京都線', 100]],
    forbid: ['東北・北海道新幹線', '高崎線'],
  },
  {
    station: '府中',
    prefecture: '東京都',
    selectByRoutes: ['京王線'],
    expect: [['京王線', 100]],
    forbid: ['福塩線', '徳島線'],
  },
  {
    station: '府中',
    prefecture: '広島県',
    selectByRoutes: ['福塩線'],
    expect: [['福塩線', 10]],
    forbid: ['京王線', '徳島線'],
  },
  {
    station: '郡山',
    prefecture: '福島県',
    selectByRoutes: ['東北・北海道新幹線', '磐越西線'],
    expect: [['東北・北海道新幹線', 50], ['磐越西線', 5]],
    forbid: ['関西線'],
  },
  {
    station: '郡山',
    prefecture: '奈良県',
    selectByRoutes: ['関西線'],
    expect: [['関西線', 50]],
    forbid: ['東北・北海道新幹線', '磐越西線'],
  },
  {
    station: '福井',
    prefecture: '福井県',
    selectByRoutes: ['北陸新幹線', 'ハピラインふくい線'],
    expect: [['北陸新幹線', 20], ['ハピラインふくい線', 20]],
    forbid: ['水島臨海鉄道水島本線'],
  },
  {
    station: '福井',
    prefecture: '岡山県',
    selectByRoutes: ['水島臨海鉄道水島本線'],
    expect: [['水島臨海鉄道水島本線', 20]],
    forbid: ['北陸新幹線', 'ハピラインふくい線'],
  },
  {
    station: '寺田',
    prefecture: '富山県',
    selectByRoutes: ['富山地方鉄道立山線', '富山地方鉄道本線'],
    expect: [['富山地方鉄道立山線', 5], ['富山地方鉄道本線', 5]],
    forbid: ['近畿日本鉄道京都線'],
  },
  {
    station: '寺田',
    prefecture: '京都府',
    selectByRoutes: ['近畿日本鉄道京都線'],
    expect: [['近畿日本鉄道京都線', 100]],
    forbid: ['富山地方鉄道立山線', '富山地方鉄道本線'],
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

async function auditSameNameStations(page) {
  return page.evaluate((sameNameCases) => {
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

    function prefecturesForGroup(stationGroupId) {
      return state.stationGroupById.get(stationGroupId)?.tags?.prefectureNamesJa || [];
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
    const names = new Set(sameNameCases.map((testCase) => testCase.station));

    for (const name of names) {
      const candidateCount = [...state.stationGroupById.keys()].filter((stationGroupId) => groupName(stationGroupId) === name).length;
      if (candidateCount < 2) {
        anomalies.push({
          kind: 'same_name_family_not_ambiguous',
          station: name,
          candidateCount,
        });
      }
    }

    for (const testCase of sameNameCases) {
      const candidateGroups = [...state.stationGroupById.keys()]
        .filter((stationGroupId) => groupName(stationGroupId) === testCase.station)
        .map((stationGroupId) => ({
          stationGroupId,
          prefectures: prefecturesForGroup(stationGroupId),
          exactChoices: routeChoicesForGroup(stationGroupId, false),
        }));

      const selectedGroups = candidateGroups.filter((candidate) => {
        const exactTitles = routeTitleSet(candidate.exactChoices);
        const matchesRoutes = (testCase.selectByRoutes || []).every((routeName) => exactTitles.has(routeName));
        const matchesPrefecture = !testCase.prefecture || candidate.prefectures.includes(testCase.prefecture);
        return matchesRoutes && matchesPrefecture;
      });

      if (selectedGroups.length !== 1) {
        anomalies.push({
          kind: 'same_name_station_disambiguation_failed',
          station: testCase.station,
          prefecture: testCase.prefecture,
          selectByRoutes: testCase.selectByRoutes,
          selectedGroupCount: selectedGroups.length,
          candidates: candidateGroups.map((candidate) => ({
            stationGroupId: candidate.stationGroupId,
            prefectures: candidate.prefectures,
            exactChoices: compactChoiceList(candidate.exactChoices),
          })),
        });
        continue;
      }

      const selectedGroup = selectedGroups[0];
      const choices = routeChoicesForGroup(selectedGroup.stationGroupId, true);
      const choicesByRoute = new Map(choices.map((choice) => [choice.route, choice]));
      const missingOrUnderfilled = (testCase.expect || [])
        .map(([routeName, minimumTrainCount]) => ({
          route: routeName,
          minimumTrainCount,
          actualTrainCount: choicesByRoute.get(routeName)?.trainCount || 0,
        }))
        .filter((item) => item.actualTrainCount < item.minimumTrainCount);
      const forbiddenPresent = (testCase.forbid || []).filter((routeName) => choicesByRoute.has(routeName));

      if (missingOrUnderfilled.length) {
        anomalies.push({
          kind: 'same_name_expected_route_underfilled',
          station: testCase.station,
          prefecture: testCase.prefecture,
          stationGroupId: selectedGroup.stationGroupId,
          missingOrUnderfilled,
          choices: compactChoiceList(choices),
        });
      }
      if (forbiddenPresent.length) {
        anomalies.push({
          kind: 'same_name_remote_route_leak',
          station: testCase.station,
          prefecture: testCase.prefecture,
          stationGroupId: selectedGroup.stationGroupId,
          forbiddenPresent,
          choices: compactChoiceList(choices),
        });
      }

      results.push({
        station: testCase.station,
        prefecture: testCase.prefecture,
        stationGroupId: selectedGroup.stationGroupId,
        candidateCount: candidateGroups.length,
        choiceCount: choices.length,
        expectedRoutes: Object.fromEntries((testCase.expect || []).map(([routeName]) => [
          routeName,
          choicesByRoute.get(routeName)?.trainCount || 0,
        ])),
        forbiddenPresent,
      });
    }

    return {
      checkedAt: new Date().toISOString(),
      sameNameCaseCount: sameNameCases.length,
      checkedCaseCount: results.length,
      ambiguousNameCount: names.size,
      anomalyCount: anomalies.length,
      results,
      anomalies,
    };
  }, SAME_NAME_CASES);
}

(async () => {
  const args = parseArgs(process.argv);
  const { browser, page } = await loadPage(args['page-url']);
  try {
    const result = await auditSameNameStations(page);
    const json = JSON.stringify(result, null, 2);
    console.log(json);
    if (args.output && args.output !== true) fs.writeFileSync(args.output, `${json}\n`);
    if (result.anomalyCount) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
