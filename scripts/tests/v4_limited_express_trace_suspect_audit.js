#!/usr/bin/env node

const fs = require('fs');
const zlib = require('zlib');

const LONG_PAIR_KM = 45;
const VERY_LONG_PAIR_KM = 90;
const LONG_TRIP_KM = 160;
const MAX_REPORTED_SUSPECTS = 600;

const NAMED_SERVICE_PATTERNS = [
  /サンダーバード/, /しらさぎ/, /くろしお/, /はるか/, /こうのとり/, /きのさき/, /はしだて/,
  /まいづる/, /スーパーはくと/, /ひだ/, /南紀/, /しなの/, /あずさ/, /かいじ/, /富士回遊/,
  /成田エクスプレス/, /踊り子/, /湘南/, /ひたち/, /ときわ/, /わかしお/, /さざなみ/,
  /しおさい/, /草津/, /四万/, /あかぎ/, /いなほ/, /つがる/, /北斗/, /すずらん/,
  /おおぞら/, /とかち/, /カムイ/, /ライラック/, /ソニック/, /にちりん/, /きりしま/,
  /かもめ/, /みどり/, /ハウステンボス/, /ゆふ/, /ゆふいんの森/, /指宿のたまて箱/,
  /しまんと/, /しおかぜ/, /いしづち/, /南風/, /うずしお/, /剣山/, /むろと/,
  /はまかぜ/, /らくラク/, /びわこエクスプレス/, /伊勢志摩ライナー/, /ビスタカー/,
  /アーバンライナー/, /しまかぜ/, /ひのとり/, /りょうもう/, /スペーシア/, /リバティ/,
  /ロマンスカー/, /はこね/, /さがみ/, /ふじさん/, /えのしま/, /ラピート/, /サザン/,
  /Nozomi/i, /Hikari/i, /Kodama/i, /Mizuho/i, /Sakura/i, /Tsubame/i, /Tsurugi/i,
  /Asama/i, /Kagayaki/i, /Hakutaka/i, /Toki/i, /Tanigawa/i, /Yamabiko/i, /Nasuno/i,
  /Hayabusa/i, /Hayate/i, /Komachi/i, /Tsubasa/i,
];

const REVIEWED_SEGMENT_EXCEPTIONS = new Set([
  reviewedSegmentKey('京都', '敦賀', '湖西線'),
  reviewedSegmentKey('京都', '近江今津', '湖西線'),
  reviewedSegmentKey('京都', '堅田', '湖西線'),
  reviewedSegmentKey('敦賀', '近江今津', '湖西線'),
  reviewedSegmentKey('敦賀', '堅田', '湖西線'),
  reviewedSegmentKey('上野', '土浦', '常磐線'),
  reviewedSegmentKey('上野', '水戸', '常磐線'),
  reviewedSegmentKey('仙台', '相馬', '常磐線'),
]);

function reviewedSegmentKey(fromName, toName, routeName) {
  return [fromName, toName].sort().join('\u0000') + `\u0000${routeName}`;
}

function parseArgs(argv) {
  const args = {
    timetable: 'docs/data/v4_gameplay_timetable_compact.json.gz',
    map: 'docs/data/v4_gameplay_map_bundle.json.gz',
    'json-out': '',
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

function haversineKm(left, right) {
  if (!left || !right) return 0;
  const radiusKm = 6371.0088;
  const toRad = (value) => value * Math.PI / 180;
  const dLat = toRad(right.lat - left.lat);
  const dLon = toRad(right.lon - left.lon);
  const lat1 = toRad(left.lat);
  const lat2 = toRad(right.lat);
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return radiusKm * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function uniq(values) {
  return [...new Set(values.filter(Boolean))];
}

function textAt(array, index) {
  return Number.isInteger(index) ? array[index] || '' : '';
}

function routeTitle(route) {
  return route?.shortName || route?.longName || route?.id || '';
}

function cleanFamilyName(value) {
  return String(value || '')
    .replace(/\s+/g, '')
    .replace(/[0-9０-９]+号.*/, '')
    .replace(/（.*?）/g, '')
    .replace(/\(.*?\)/g, '') || 'UNKNOWN';
}

function isNamedLongDistanceTrip(fields) {
  if (fields.route?.mode === 'shinkansen') return true;
  const text = [
    fields.serviceName,
    fields.displayName,
    fields.routeName,
    fields.headsign,
    fields.id,
  ].filter(Boolean).join(' ');
  if (NAMED_SERVICE_PATTERNS.some((pattern) => pattern.test(text))) return true;
  return fields.serviceName === '特急' && Boolean(fields.displayName || fields.routeName);
}

function isVirtualCorridorRoute(route) {
  const name = routeTitle(route);
  return /^SHINKANSEN_/.test(name) || /^SHINKANSEN_/.test(route?.id || '');
}

function isShinkansenLikeRoute(route) {
  return route?.mode === 'shinkansen' || isVirtualCorridorRoute(route);
}

function severityFor(reasons, distanceKm, isMostlyShinkansen = false) {
  if (reasons.includes('reviewed_long_physical_segment') &&
      !reasons.includes('long_pair_trace_route_absent_from_both_endpoint_lines')) {
    return 34 + Math.min(10, distanceKm / 40);
  }
  if (isMostlyShinkansen && reasons.every((reason) =>
    reason === 'long_adjacent_stop_pair' ||
    reason === 'very_long_adjacent_stop_pair' ||
    reason === 'virtual_shinkansen_corridor_pair' ||
    reason === 'normal_shinkansen_express_skip_candidate'
  )) {
    return 36 + Math.min(12, distanceKm / 40);
  }
  if (reasons.includes('very_long_adjacent_stop_pair')) return 90;
  if (reasons.includes('long_pair_trace_route_absent_from_both_endpoint_lines')) return 82;
  if (reasons.includes('long_trip_single_trace_with_line_context_mismatch')) return 72;
  if (reasons.includes('long_adjacent_stop_pair')) return 60 + Math.min(20, distanceKm / 10);
  return 30;
}

function main() {
  const args = parseArgs(process.argv);
  const timetable = readJsonMaybeGz(args.timetable);
  const mapBundle = readJsonMaybeGz(args.map);

  const routeById = new Map((mapBundle.serviceRoutes || []).map((route) => [route.id, route]));
  const stationById = new Map((mapBundle.stationGroups || []).map((station) => [station.id, station]));
  const stationGroupIds = timetable.stationGroupIds || [];
  const routeIds = timetable.routeIds || [];
  const serviceNames = timetable.serviceNames || [];
  const displayNames = timetable.displayNames || [];
  const headsigns = timetable.headsigns || [];
  const routeNames = timetable.routeNames || [];

  const stationForIndex = (index) => stationById.get(stationGroupIds[index]) || null;
  const stationName = (station) => station?.names?.ja || station?.primaryName || station?.id || '';
  const routeForIndex = (index) => routeById.get(routeIds[index]) || null;
  const stationLineSet = (station) => new Set(station?.tags?.lineNames || []);
  const stationOperatorSet = (station) => new Set(station?.tags?.operatorIds || []);

  const suspects = [];
  const familyCounts = new Map();
  let checkedTrips = 0;
  let candidateTripCount = 0;
  let checkedAdjacentPairs = 0;

  for (const row of timetable.trips || []) {
    checkedTrips += 1;
    const route = routeForIndex(row[1]);
    const fields = {
      id: row[0],
      route,
      serviceName: textAt(serviceNames, row[2]),
      displayName: textAt(displayNames, row[6]),
      headsign: textAt(headsigns, row[7]),
      routeName: textAt(routeNames, row[8]),
    };
    if (!isNamedLongDistanceTrip(fields)) continue;
    const stops = (row[4] || []).map((stop, index) => ({
      sequence: index + 1,
      station: stationForIndex(stop[0]),
      route: routeForIndex(stop[3]),
    })).filter((stop) => stop.station);
    if (stops.length < 2) continue;

    candidateTripCount += 1;
    const family = cleanFamilyName(fields.displayName || fields.serviceName || fields.routeName);
    familyCounts.set(family, (familyCounts.get(family) || 0) + 1);
    const traces = (row[5] || []).map((trace) => ({
      fromSequence: trace[0],
      toSequence: trace[1],
      route: routeForIndex(trace[2]),
    })).filter((trace) => trace.route);
    const traceRouteNames = uniq(traces.map((trace) => routeTitle(trace.route)));
    const origin = stops[0];
    const terminal = stops[stops.length - 1];
    const tripDistanceKm = haversineKm(origin.station.centroid, terminal.station.centroid);
    const tripOperators = uniq(stops.flatMap((stop) => [...stationOperatorSet(stop.station)]));
    const traceOperatorNames = uniq(traces.map((trace) => trace.route.operatorId));

    if (tripDistanceKm >= LONG_TRIP_KM && traceRouteNames.length === 1) {
      const traceName = traceRouteNames[0];
      const offLineStops = stops.filter((stop) => !stationLineSet(stop.station).has(traceName));
      if (offLineStops.length >= 2 || tripOperators.length > 1 || traceOperatorNames.length > 1) {
        const mostlyShinkansen = traces.length > 0 && traces.every((trace) => isShinkansenLikeRoute(trace.route));
        suspects.push({
          severity: severityFor(['long_trip_single_trace_with_line_context_mismatch'], tripDistanceKm, mostlyShinkansen),
          reasons: ['long_trip_single_trace_with_line_context_mismatch'],
          tripId: fields.id,
          family,
          serviceName: fields.serviceName,
          displayName: fields.displayName,
          trainNumber: row[3] || '',
          origin: stationName(origin.station),
          terminal: stationName(terminal.station),
          tripDistanceKm: Number(tripDistanceKm.toFixed(1)),
          traceRoutes: traceRouteNames,
          offTraceLineStops: offLineStops.slice(0, 8).map((stop) => stationName(stop.station)),
          operatorIdsSeenAtStops: tripOperators,
        });
      }
    }

    for (let index = 0; index < stops.length - 1; index += 1) {
      checkedAdjacentPairs += 1;
      const from = stops[index];
      const to = stops[index + 1];
      const pairDistanceKm = haversineKm(from.station.centroid, to.station.centroid);
      if (pairDistanceKm < LONG_PAIR_KM) continue;

      const coveringTraces = traces.filter((trace) =>
        trace.fromSequence <= from.sequence && to.sequence <= trace.toSequence
      );
      const coveringRouteNames = uniq(coveringTraces.map((trace) => routeTitle(trace.route)));
      const reasons = ['long_adjacent_stop_pair'];
      if (pairDistanceKm >= VERY_LONG_PAIR_KM) reasons.push('very_long_adjacent_stop_pair');
      const fromLines = stationLineSet(from.station);
      const toLines = stationLineSet(to.station);
      const mostlyShinkansen = coveringTraces.length > 0 && coveringTraces.every((trace) =>
        isShinkansenLikeRoute(trace.route)
      );
      if (coveringTraces.some((trace) => isVirtualCorridorRoute(trace.route))) {
        reasons.push('virtual_shinkansen_corridor_pair');
      }
      const absentCoveringRoutes = coveringTraces.filter((trace) =>
        !isShinkansenLikeRoute(trace.route) &&
        routeTitle(trace.route) &&
        !REVIEWED_SEGMENT_EXCEPTIONS.has(reviewedSegmentKey(
          stationName(from.station),
          stationName(to.station),
          routeTitle(trace.route)
        )) &&
        !fromLines.has(routeTitle(trace.route)) &&
        !toLines.has(routeTitle(trace.route))
      ).map((trace) => routeTitle(trace.route));
      if (coveringTraces.some((trace) => REVIEWED_SEGMENT_EXCEPTIONS.has(reviewedSegmentKey(
        stationName(from.station),
        stationName(to.station),
        routeTitle(trace.route)
      )))) {
        reasons.push('reviewed_long_physical_segment');
      }
      if (absentCoveringRoutes.length) {
        reasons.push('long_pair_trace_route_absent_from_both_endpoint_lines');
      }
      if (mostlyShinkansen && reasons.every((reason) =>
        reason === 'long_adjacent_stop_pair' ||
        reason === 'very_long_adjacent_stop_pair' ||
        reason === 'virtual_shinkansen_corridor_pair'
      )) {
        reasons.push('normal_shinkansen_express_skip_candidate');
      }
      const uniqueReasons = uniq(reasons);
      suspects.push({
        severity: severityFor(uniqueReasons, pairDistanceKm, mostlyShinkansen),
        reasons: uniqueReasons,
        tripId: fields.id,
        family,
        serviceName: fields.serviceName,
        displayName: fields.displayName,
        trainNumber: row[3] || '',
        origin: stationName(origin.station),
        terminal: stationName(terminal.station),
        from: stationName(from.station),
        to: stationName(to.station),
        distanceKm: Number(pairDistanceKm.toFixed(1)),
        coveringTraceRoutes: coveringRouteNames,
        allTraceRoutes: traceRouteNames,
        fromStationLines: [...fromLines].sort(),
        toStationLines: [...toLines].sort(),
      });
    }
  }

  suspects.sort((left, right) =>
    right.severity - left.severity ||
    (right.distanceKm || right.tripDistanceKm || 0) - (left.distanceKm || left.tripDistanceKm || 0) ||
    String(left.tripId).localeCompare(String(right.tripId))
  );
  const reasonCounts = {};
  for (const suspect of suspects) {
    for (const reason of suspect.reasons || []) reasonCounts[reason] = (reasonCounts[reason] || 0) + 1;
  }
  const output = {
    generatedAt: new Date().toISOString(),
    inputs: {
      timetable: args.timetable,
      map: args.map,
    },
    thresholds: {
      longPairKm: LONG_PAIR_KM,
      veryLongPairKm: VERY_LONG_PAIR_KM,
      longTripKm: LONG_TRIP_KM,
    },
    checkedTrips,
    candidateTripCount,
    checkedAdjacentPairs,
    suspectCount: suspects.length,
    reasonCounts,
    topFamilies: [...familyCounts.entries()]
      .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
      .slice(0, 50)
      .map(([family, count]) => ({ family, count })),
    suspects: suspects.slice(0, MAX_REPORTED_SUSPECTS),
  };

  const json = JSON.stringify(output, null, 2);
  if (args['json-out']) fs.writeFileSync(args['json-out'], `${json}\n`);
  console.log(JSON.stringify({
    checkedTrips,
    candidateTripCount,
    checkedAdjacentPairs,
    suspectCount: suspects.length,
    reasonCounts,
    written: args['json-out'] || null,
    topSuspects: suspects.slice(0, 12).map((suspect) => ({
      reasons: suspect.reasons,
      family: suspect.family,
      trainNumber: suspect.trainNumber,
      from: suspect.from || suspect.origin,
      to: suspect.to || suspect.terminal,
      distanceKm: suspect.distanceKm || suspect.tripDistanceKm,
      traceRoutes: suspect.coveringTraceRoutes || suspect.traceRoutes,
    })),
  }, null, 2));
}

main();
