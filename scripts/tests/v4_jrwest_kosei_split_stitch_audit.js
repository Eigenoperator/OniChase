#!/usr/bin/env node

const fs = require('fs');
const zlib = require('zlib');

function parseArgs(argv) {
  const args = {
    timetable: 'docs/data/v4_gameplay_timetable_compact.json.gz',
    map: 'docs/data/v4_gameplay_map_bundle.json.gz',
    jrwestAudit: 'data/v4_jrwest_official_train_instances_audit.json',
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

function decodeCompactTimetable(payload) {
  const stationGroupIds = payload.stationGroupIds || [];
  const routeIds = payload.routeIds || [];
  const serviceNames = payload.serviceNames || [];
  const displayNames = payload.displayNames || [];
  const headsigns = payload.headsigns || [];
  const routeNames = payload.routeNames || [];
  const routeIdAt = (index) => Number.isInteger(index) ? routeIds[index] || '' : '';
  return (payload.trips || []).map((row) => ({
    id: row[0],
    routeId: routeIdAt(row[1]),
    serviceName: serviceNames[row[2]] || '',
    serviceNumber: row[3] || '',
    displayName: displayNames[row[6]] || '',
    headsign: headsigns[row[7]] || '',
    routeName: routeNames[row[8]] || '',
    stopTimes: (row[4] || []).map((stop, index) => ({
      sequence: index + 1,
      stationGroupId: stationGroupIds[stop[0]] || '',
      arrivalTimeSec: stop[1],
      departureTimeSec: stop[2],
      displayRouteId: routeIdAt(stop[3]),
      outgoingRouteId: routeIdAt(stop[4]),
      incomingRouteId: routeIdAt(stop[5]),
    })),
    lineTrace: (row[5] || []).map((trace) => ({
      fromSequence: trace[0],
      toSequence: trace[1],
      routeId: routeIdAt(trace[2]),
    })).filter((trace) => trace.routeId),
  }));
}

function formatHhmm(seconds) {
  if (!Number.isFinite(seconds)) return '';
  const minutes = Math.floor(seconds / 60);
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

function main() {
  const args = parseArgs(process.argv);
  const timetable = decodeCompactTimetable(readJsonMaybeGz(args.timetable));
  const mapBundle = readJsonMaybeGz(args.map);
  const jrwestAudit = readJsonMaybeGz(args.jrwestAudit);
  const stationNameById = new Map((mapBundle.stationGroups || [])
    .map((group) => [group.id, group.names?.ja || group.primaryName || group.id]));
  const routeNameById = new Map((mapBundle.serviceRoutes || [])
    .map((route) => [route.id, route.shortName || route.longName || route.id]));
  const failures = [];
  const samples = [];

  const expectedChains = [
    {
      serviceNumber: '3891M+3811M+3411M',
      origin: '敦賀',
      terminal: '姫路',
      traceRoutes: ['湖西線', '東海道線', '山陽線'],
      minStops: 25,
    },
    {
      serviceNumber: '3143M+3443M',
      origin: '敦賀',
      terminal: '姫路',
      traceRoutes: ['湖西線', '東海道線', '山陽線'],
      minStops: 25,
    },
    {
      serviceNumber: '3438M+3138M',
      origin: '姫路',
      terminal: '敦賀',
      traceRoutes: ['山陽線', '東海道線', '湖西線'],
      minStops: 25,
    },
    {
      serviceNumber: '4841M+128M',
      origin: '近江今津',
      terminal: '米原',
      traceRoutes: ['湖西線', '北陸線'],
      minStops: 10,
    },
    {
      serviceNumber: '143M+4848M',
      origin: '長浜',
      terminal: '近江今津',
      traceRoutes: ['北陸線', '湖西線'],
      minStops: 8,
    },
  ];

  for (const expected of expectedChains) {
    const matches = timetable.filter((trip) => trip.serviceNumber === expected.serviceNumber);
    if (matches.length !== 1) {
      failures.push({
        type: 'missing_or_duplicate_stitched_trip',
        expected,
        actualCount: matches.length,
      });
      continue;
    }
    const trip = matches[0];
    const stops = trip.stopTimes || [];
    const origin = stationNameById.get(stops[0]?.stationGroupId) || '';
    const terminal = stationNameById.get(stops.at(-1)?.stationGroupId) || '';
    const traceRoutes = [...new Set((trip.lineTrace || []).map((trace) => routeNameById.get(trace.routeId) || trace.routeId))];
    const missingTraceRoutes = expected.traceRoutes.filter((routeName) => !traceRoutes.includes(routeName));
    if (origin !== expected.origin || terminal !== expected.terminal || stops.length < expected.minStops || missingTraceRoutes.length) {
      failures.push({
        type: 'stitched_trip_shape_mismatch',
        expected,
        actual: {
          id: trip.id,
          origin,
          terminal,
          stopCount: stops.length,
          traceRoutes,
        },
      });
      continue;
    }
    samples.push({
      serviceNumber: trip.serviceNumber,
      id: trip.id,
      origin,
      terminal,
      firstDeparture: formatHhmm(stops[0]?.departureTimeSec),
      stopCount: stops.length,
      traceRoutes,
    });
  }

  const output = {
    checkedExpectedChains: expectedChains.length,
    reviewedSplitColumnStitchCount: jrwestAudit.reviewedSplitColumnStitchCount || 0,
    reviewedSplitColumnSourceRowCount: jrwestAudit.reviewedSplitColumnSourceRowCount || 0,
    failureCount: failures.length,
    failures,
    samples,
  };
  console.log(JSON.stringify(output, null, 2));
  if (failures.length) process.exit(1);
}

main();
