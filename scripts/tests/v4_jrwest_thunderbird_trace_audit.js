#!/usr/bin/env node

const fs = require('fs');
const zlib = require('zlib');

function parseArgs(argv) {
  const args = {
    timetable: 'docs/data/v4_gameplay_timetable_compact.json.gz',
    map: 'docs/data/v4_gameplay_map_bundle.json.gz',
  };
  for (let index = 2; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith('--')) continue;
    args[key.slice(2)] = argv[index + 1];
    index += 1;
  }
  return args;
}

function readJsonMaybeGz(path) {
  const buffer = fs.readFileSync(path);
  const text = path.endsWith('.gz') ? zlib.gunzipSync(buffer).toString('utf8') : buffer.toString('utf8');
  return JSON.parse(text);
}

function main() {
  const args = parseArgs(process.argv);
  const timetable = readJsonMaybeGz(args.timetable);
  const mapBundle = readJsonMaybeGz(args.map);
  const stationNameById = new Map((mapBundle.stationGroups || [])
    .map((group) => [group.id, group.names?.ja || group.primaryName || group.id]));
  const routeNameById = new Map((mapBundle.serviceRoutes || [])
    .map((route) => [route.id, route.shortName || route.longName || route.id]));
  const stationGroupIds = timetable.stationGroupIds || [];
  const routeIds = timetable.routeIds || [];
  const serviceNames = timetable.serviceNames || [];
  const failures = [];
  const samples = [];

  const stationName = (index) => stationNameById.get(stationGroupIds[index]) || stationGroupIds[index] || '';
  const routeName = (index) => routeNameById.get(routeIds[index]) || routeIds[index] || '';
  const thunderbirdRows = (timetable.trips || [])
    .filter((row) => serviceNames[row[2]] === 'サンダーバード');

  for (const row of thunderbirdRows) {
    const stops = (row[4] || []).map((stop) => stationName(stop[0]));
    const traceRoutes = [...new Set((row[5] || []).map((trace) => routeName(trace[2])).filter(Boolean))];
    const trip = {
      id: row[0],
      number: row[3],
      stops,
      traceRoutes,
    };
    if (stops.includes('京都') && stops.includes('敦賀') && !traceRoutes.includes('湖西線')) {
      failures.push({
        type: 'missing_kosei_between_kyoto_and_tsuruga',
        ...trip,
      });
    }
    if (stops.includes('大阪') && stops.includes('京都') && !traceRoutes.includes('東海道線')) {
      failures.push({
        type: 'missing_tokaido_between_osaka_and_kyoto',
        ...trip,
      });
    }
    if (samples.length < 12) samples.push(trip);
  }

  const output = {
    thunderbirdTripCount: thunderbirdRows.length,
    failureCount: failures.length,
    failures,
    samples,
  };
  console.log(JSON.stringify(output, null, 2));
  if (failures.length) process.exit(1);
}

main();
