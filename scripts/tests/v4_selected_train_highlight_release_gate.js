#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

function parseArgs(argv) {
  const args = {};
  for (let index = 2; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith('--')) continue;
    const next = argv[index + 1];
    if (next === undefined || next.startsWith('--')) {
      args[key.slice(2)] = true;
      continue;
    }
    args[key.slice(2)] = next;
    index += 1;
  }
  if (!args['page-url']) throw new Error('Missing --page-url');
  return args;
}

function integerArg(args, key, defaultValue, { min = 1 } = {}) {
  if (args[key] === undefined || args[key] === true || args[key] === '') return defaultValue;
  const value = Number(args[key]);
  if (!Number.isInteger(value) || value < min) {
    throw new Error(`Invalid --${key}: expected integer >= ${min}`);
  }
  return value;
}

function runShard({ pageUrl, shardIndex, shardCount, maxFailures, progressEvery, timeoutMs, maxRetries }) {
  const outputPath = path.join('/tmp', `v4_selected_train_highlight_release_shard_${process.pid}_${shardIndex}.json`);
  const args = [
    'scripts/tests/v4_selected_train_highlight_audit.js',
    '--page-url', pageUrl,
    '--shard-count', String(shardCount),
    '--shard-index', String(shardIndex),
    '--max-failures', String(maxFailures),
    '--output', outputPath,
  ];
  if (progressEvery) args.push('--progress-every', String(progressEvery));
  let run = null;
  for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
    fs.rmSync(outputPath, { force: true });
    run = spawnSync(process.execPath, args, {
      cwd: process.cwd(),
      encoding: 'utf8',
      maxBuffer: 128 * 1024 * 1024,
      timeout: timeoutMs,
    });
    process.stderr.write(`[v4_selected_train_highlight_release] shard=${shardIndex}/${shardCount} attempt=${attempt + 1}/${maxRetries + 1} exit=${run.status} signal=${run.signal || ''}\n`);
    if (run.stderr) process.stderr.write(run.stderr);
    if (!run.error && fs.existsSync(outputPath)) break;
    if (attempt === maxRetries) break;
  }
  if (run?.error && run.error.code !== 'ETIMEDOUT') throw run.error;
  if (!fs.existsSync(outputPath)) {
    throw new Error(`Shard ${shardIndex} did not write ${outputPath}. status=${run?.status} signal=${run?.signal || ''} error=${run?.error?.message || ''}\nstdout:\n${run?.stdout || ''}\nstderr:\n${run?.stderr || ''}`);
  }
  const result = JSON.parse(fs.readFileSync(outputPath, 'utf8'));
  fs.rmSync(outputPath, { force: true });
  return {
    status: run.status,
    result,
    stdoutTail: run.stdout.split('\n').slice(-20).join('\n'),
  };
}

function mergeResults(shards) {
  const totals = {
    eligibleTripCount: 0,
    selectedTripCount: 0,
    checkedTrips: 0,
    multiTraceTrips: 0,
    primaryCoverTrips: 0,
    primaryCoverStartCases: 0,
    checkedPrimaryGeometryCases: 0,
    checkedSelectedPathCoverageCases: 0,
    checkedFutureStopCoverageCases: 0,
    checkedOsakaAirportLoopCases: 0,
    checkedContinuousPathCases: 0,
    checkedMiniShinkansenSharedCases: 0,
    checkedMiniShinkansenIndependentTraceCases: 0,
  };
  const failures = [];
  const samples = [];
  const routeStats = new Map();
  for (const shard of shards) {
    const result = shard.result;
    Object.keys(totals).forEach((key) => {
      totals[key] += Number(result[key] || 0);
    });
    failures.push(...(result.failures || []));
    samples.push(...(result.samples || []).slice(0, 5));
    for (const item of result.topPrimaryCoverRoutes || []) {
      routeStats.set(item.route, (routeStats.get(item.route) || 0) + item.count);
    }
  }
  return {
    checkedAt: new Date().toISOString(),
    auditOptions: {
      shardCount: shards.length,
      releaseGate: true,
    },
    ...totals,
    failureCount: failures.length,
    failures,
    topPrimaryCoverRoutes: [...routeStats.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'ja'))
      .slice(0, 20)
      .map(([route, count]) => ({ route, count })),
    samples: samples.slice(0, 20),
    shardSummaries: shards.map((shard, index) => ({
      shardIndex: index,
      exitStatus: shard.status,
      checkedTrips: shard.result.checkedTrips,
      failureCount: shard.result.failureCount,
    })),
  };
}

function main() {
  const args = parseArgs(process.argv);
  const shardCount = integerArg(args, 'shard-count', 8, { min: 1 });
  const maxFailures = integerArg(args, 'max-failures', 25, { min: 1 });
  const progressEvery = integerArg(args, 'progress-every', 0, { min: 0 });
  const timeoutMs = integerArg(args, 'shard-timeout-ms', 300000, { min: 10000 });
  const maxRetries = integerArg(args, 'max-retries', 1, { min: 0 });
  const shards = [];
  for (let shardIndex = 0; shardIndex < shardCount; shardIndex += 1) {
    shards.push(runShard({
      pageUrl: args['page-url'],
      shardIndex,
      shardCount,
      maxFailures,
      progressEvery,
      timeoutMs,
      maxRetries,
    }));
  }
  const merged = mergeResults(shards);
  const json = JSON.stringify(merged, null, 2);
  if (args.output && args.output !== true) fs.writeFileSync(args.output, `${json}\n`);
  console.log(json);
  if (merged.failureCount || shards.some((shard) => shard.status !== 0)) process.exitCode = 1;
}

try {
  main();
} catch (error) {
  console.error(error);
  process.exit(1);
}
