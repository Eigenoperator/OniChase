#!/usr/bin/env node

const fs = require('fs');
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
  args.runs = Number.parseInt(args.runs || '1', 10);
  args['max-p95-frame-ms'] = Number.parseFloat(args['max-p95-frame-ms'] || '90');
  args['max-frame-ms'] = Number.parseFloat(args['max-frame-ms'] || '240');
  args['min-frame-count'] = Number.parseInt(args['min-frame-count'] || '20', 10);
  return args;
}

function percentile(values, p) {
  const sorted = values.slice().sort((left, right) => left - right);
  if (!sorted.length) return null;
  const index = Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1);
  return sorted[index];
}

function isBenignBrowserConsoleMessage(message) {
  return message.includes('Failed to load resource') ||
    message.includes('GPU stall') ||
    message.includes('WebGL: CONTEXT_LOST_WEBGL') ||
    message.includes('WebGL: INVALID_OPERATION') ||
    message.includes('GL_INVALID_OPERATION');
}

async function runScenario(page, scenario) {
  return page.evaluate(async (scenario) => {
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const waitForIdle = async () => {
      const map = state.map;
      if (!map) throw new Error('Map is not initialized');
      await Promise.race([
        new Promise((resolve) => map.once('idle', resolve)),
        sleep(2500),
      ]);
    };
    const measureFrames = async (durationMs) => {
      const times = [];
      let previous = performance.now();
      const startedAt = previous;
      return new Promise((resolve) => {
        const tick = (now) => {
          times.push(now - previous);
          previous = now;
          if (now - startedAt >= durationMs) resolve(times.slice(1));
          else requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
    };

    if (typeof setViewMode === 'function') setViewMode('corridor');
    state.map.jumpTo({ center: scenario.center, zoom: scenario.zoom, duration: 0 });
    await waitForIdle();

    const framePromise = measureFrames(scenario.durationMs + 350);
    state.map.easeTo({
      center: scenario.target,
      zoom: scenario.zoom,
      duration: scenario.durationMs,
      easing: (t) => t,
    });
    const frameIntervals = await framePromise;
    await waitForIdle();

    const labelLayers = ['label-hub', 'label-major', 'label-local', 'label-local-dense', 'label-all-dense']
      .map((id) => ({
        id,
        minzoom: state.map.getLayer(id)?.minzoom ?? null,
        maxzoom: state.map.getLayer(id)?.maxzoom ?? null,
        visibility: state.map.getLayoutProperty(id, 'visibility') || 'visible',
      }));

    return {
      name: scenario.name,
      zoom: scenario.zoom,
      frameIntervals,
      labelLayers,
      serviceVisibility: state.map.getLayer('service-lines')
        ? state.map.getLayoutProperty('service-lines', 'visibility')
        : 'not-created',
    };
  }, scenario);
}

(async () => {
  const args = parseArgs(process.argv);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const consoleMessages = [];
  page.on('console', (message) => {
    const text = message.text();
    if (!isBenignBrowserConsoleMessage(text)) consoleMessages.push(`${message.type()}: ${text}`);
  });
  page.on('pageerror', (error) => consoleMessages.push(`pageerror: ${error.message}`));

  const scenarios = [
    {
      name: 'tokyo-dense-labels',
      center: [139.735, 35.693],
      target: [139.795, 35.673],
      zoom: 12.9,
      durationMs: 900,
    },
    {
      name: 'osaka-dense-labels',
      center: [135.500, 34.700],
      target: [135.560, 34.680],
      zoom: 12.9,
      durationMs: 900,
    },
    {
      name: 'regional-dense-labels',
      center: [136.4914, 36.6663],
      target: [136.5550, 36.6460],
      zoom: 12.9,
      durationMs: 900,
    },
  ];

  const failures = [];
  const runs = [];
  try {
    await page.goto(args['page-url'], { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForFunction(
      () => typeof state !== 'undefined' && Boolean(state.bundle) && Boolean(state.map),
      null,
      { timeout: 90000 },
    );
    await page.waitForFunction(() => state.map.loaded(), null, { timeout: 90000 }).catch(() => {});

    for (let runIndex = 0; runIndex < args.runs; runIndex += 1) {
      for (const scenario of scenarios) {
        const sample = await runScenario(page, scenario);
        const p95 = percentile(sample.frameIntervals, 95);
        const maxFrame = Math.max(...sample.frameIntervals, 0);
        const frameCount = sample.frameIntervals.length;
        const summary = {
          run: runIndex + 1,
          name: sample.name,
          zoom: sample.zoom,
          frameCount,
          p95FrameMs: Math.round(p95 * 10) / 10,
          maxFrameMs: Math.round(maxFrame * 10) / 10,
          serviceVisibility: sample.serviceVisibility,
          labelLayers: sample.labelLayers,
        };
        runs.push(summary);
        if (frameCount < args['min-frame-count']) {
          failures.push({ message: 'Pan sample produced too few animation frames', details: summary });
        }
        if (p95 > args['max-p95-frame-ms']) {
          failures.push({ message: 'Pan p95 frame interval exceeded threshold', details: summary });
        }
        if (maxFrame > args['max-frame-ms']) {
          failures.push({ message: 'Pan max frame interval exceeded threshold', details: summary });
        }
        if (sample.serviceVisibility === 'visible') {
          failures.push({ message: 'Service layer should not be visible in default pan gate', details: summary });
        }
      }
    }
  } finally {
    await browser.close();
  }

  const relevantConsoleMessages = consoleMessages.filter((message) => !isBenignBrowserConsoleMessage(message));
  if (relevantConsoleMessages.length) {
    failures.push({
      message: 'Console/page errors appeared during map pan gate',
      details: { consoleMessages: relevantConsoleMessages.slice(0, 20) },
    });
  }

  const result = {
    checkedAt: new Date().toISOString(),
    ok: failures.length === 0,
    failureCount: failures.length,
    thresholds: {
      maxP95FrameMs: args['max-p95-frame-ms'],
      maxFrameMs: args['max-frame-ms'],
      minFrameCount: args['min-frame-count'],
    },
    pageUrl: args['page-url'],
    runs,
    failures,
  };
  const json = JSON.stringify(result, null, 2);
  console.log(json);
  if (args.output && args.output !== true) fs.writeFileSync(args.output, `${json}\n`);
  if (!result.ok) process.exitCode = 1;
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
