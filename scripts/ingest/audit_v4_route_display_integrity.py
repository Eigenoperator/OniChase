#!/usr/bin/env python3
"""Audit v4 train route display identity.

This catches cases where the same train can surface under multiple route
categories at one station, and cases where trip-level route identity disagrees
with the segment-level line trace that should drive through-service display.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_BUNDLE = ROOT / "data" / "v4_gameplay_map_bundle.json.gz"
DEFAULT_TIMETABLE = ROOT / "data" / "v4_gameplay_timetable_bundle.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_route_display_integrity_audit.json"
SAMPLE_LIMIT = 60


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def route_title(route: dict[str, Any] | None, route_id: str = "") -> str:
    return str((route or {}).get("shortName") or (route or {}).get("longName") or route_id or "")


def station_title(group: dict[str, Any] | None, station_group_id: str = "") -> str:
    names = (group or {}).get("names") or {}
    return str(names.get("ja") or (group or {}).get("primaryName") or (group or {}).get("nameJa") or station_group_id)


def seconds_to_hhmm(value: int | None) -> str:
    if not isinstance(value, int):
        return ""
    minutes = value // 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def add_sample(samples: list[dict[str, Any]], sample: dict[str, Any], limit: int = SAMPLE_LIMIT) -> None:
    if len(samples) < limit:
        samples.append(sample)


def segment_trace_matches(trip: dict[str, Any], current_stop: dict[str, Any], next_stop: dict[str, Any]) -> list[dict[str, Any]]:
    current_sequence = int(current_stop.get("sequence") or 0)
    next_sequence = int(next_stop.get("sequence") or 0)
    return [
        trace
        for trace in trip.get("lineTrace") or []
        if trace.get("routeId")
        and current_sequence >= int(trace.get("fromSequence") or 0)
        and next_sequence <= int(trace.get("toSequence") or 0)
    ]


def segment_route_id(trip: dict[str, Any], current_stop: dict[str, Any], next_stop: dict[str, Any]) -> str:
    exact = segment_trace_matches(trip, current_stop, next_stop)
    if len(exact) == 1:
        return str(exact[0].get("routeId") or "")
    current_sequence = int(current_stop.get("sequence") or 0)
    boundary = [
        trace
        for trace in trip.get("lineTrace") or []
        if trace.get("routeId")
        and current_sequence >= int(trace.get("fromSequence") or 0)
        and current_sequence < int(trace.get("toSequence") or 0)
    ]
    return str(boundary[0].get("routeId") or "") if len(boundary) == 1 else ""


def train_source(trip: dict[str, Any]) -> str:
    return str(trip.get("sourceFeedKey") or trip.get("sourceTripId") or "unknown").split(":")[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-bundle", type=Path, default=DEFAULT_MAP_BUNDLE)
    parser.add_argument("--timetable", type=Path, default=DEFAULT_TIMETABLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    map_bundle = load_json(args.map_bundle)
    timetable = load_json(args.timetable)
    station_groups = {group["id"]: group for group in map_bundle.get("stationGroups", [])}
    routes = {route["id"]: route for route in map_bundle.get("serviceRoutes", [])}
    trips = list(timetable.get("tripInstances") or [])

    missing_trace_segment_count = 0
    ambiguous_trace_segment_count = 0
    route_not_in_trace_count = 0
    primary_segment_conflict_count = 0
    duplicate_train_station_count = 0
    duplicate_train_station_route_count = 0
    repeated_station_stop_count = 0
    missing_line_sequence_count = 0
    line_sequence_mismatch_count = 0
    through_boundary_station_count = 0

    missing_trace_by_source: Counter[str] = Counter()
    ambiguous_trace_by_source: Counter[str] = Counter()
    route_not_in_trace_by_source: Counter[str] = Counter()
    primary_segment_conflict_by_source: Counter[str] = Counter()
    duplicate_station_by_source: Counter[str] = Counter()
    missing_line_sequence_by_source: Counter[str] = Counter()
    line_sequence_mismatch_by_source: Counter[str] = Counter()

    primary_trace_pair_counts: Counter[str] = Counter()
    station_duplicate_pair_counts: Counter[str] = Counter()
    through_boundary_pair_counts: Counter[str] = Counter()

    missing_trace_samples: list[dict[str, Any]] = []
    ambiguous_trace_samples: list[dict[str, Any]] = []
    route_not_in_trace_samples: list[dict[str, Any]] = []
    primary_segment_conflict_samples: list[dict[str, Any]] = []
    duplicate_train_station_samples: list[dict[str, Any]] = []
    line_sequence_mismatch_samples: list[dict[str, Any]] = []
    through_boundary_station_samples: list[dict[str, Any]] = []

    for trip in trips:
        source = train_source(trip)
        trip_route_id = str(trip.get("routeId") or "")
        trip_route = routes.get(trip_route_id)
        trip_route_name = route_title(trip_route, trip_route_id)
        stops = list(trip.get("stopTimes") or [])
        line_trace_route_ids = {str(trace.get("routeId") or "") for trace in trip.get("lineTrace") or [] if trace.get("routeId")}
        expected_line_sequence: list[str] = []
        for trace in trip.get("lineTrace") or []:
            route_id = str(trace.get("routeId") or "")
            if route_id and route_id not in expected_line_sequence:
                expected_line_sequence.append(route_id)
        actual_line_sequence = [str(item.get("routeId") or "") for item in trip.get("lineSequence") or [] if item.get("routeId")]
        if expected_line_sequence and not actual_line_sequence:
            missing_line_sequence_count += 1
            missing_line_sequence_by_source[source] += 1
        elif expected_line_sequence != actual_line_sequence:
            line_sequence_mismatch_count += 1
            line_sequence_mismatch_by_source[source] += 1
            add_sample(
                line_sequence_mismatch_samples,
                {
                    "tripId": trip.get("id"),
                    "sourceFeedKey": trip.get("sourceFeedKey"),
                    "tripRoute": trip_route_name,
                    "expectedLineSequence": [route_title(routes.get(route_id), route_id) for route_id in expected_line_sequence],
                    "actualLineSequence": [route_title(routes.get(route_id), route_id) for route_id in actual_line_sequence],
                },
            )
        if trip_route_id and line_trace_route_ids and trip_route_id not in line_trace_route_ids:
            route_not_in_trace_count += 1
            route_not_in_trace_by_source[source] += 1
            trace_names = [route_title(routes.get(route_id), route_id) for route_id in sorted(line_trace_route_ids)]
            for trace_name in trace_names:
                primary_trace_pair_counts[f"{trip_route_name} -> {trace_name}"] += 1
            add_sample(
                route_not_in_trace_samples,
                {
                    "tripId": trip.get("id"),
                    "sourceFeedKey": trip.get("sourceFeedKey"),
                    "tripRoute": trip_route_name,
                    "traceRoutes": trace_names,
                    "firstStation": station_title(station_groups.get(stops[0].get("stationGroupId")), stops[0].get("stationGroupId", "")) if stops else "",
                    "lastStation": station_title(station_groups.get(stops[-1].get("stationGroupId")), stops[-1].get("stationGroupId", "")) if stops else "",
                },
            )

        station_route_ids: dict[str, set[str]] = defaultdict(set)
        station_sequences: dict[str, list[int]] = defaultdict(list)
        outgoing_route_by_sequence: dict[int, str] = {}
        for index, stop in enumerate(stops[:-1]):
            next_stop = stops[index + 1]
            station_group_id = str(stop.get("stationGroupId") or "")
            sequence = int(stop.get("sequence") or index + 1)
            station_sequences[station_group_id].append(sequence)
            matches = segment_trace_matches(trip, stop, next_stop)
            if not matches:
                missing_trace_segment_count += 1
                missing_trace_by_source[source] += 1
                add_sample(
                    missing_trace_samples,
                    {
                        "tripId": trip.get("id"),
                        "sourceFeedKey": trip.get("sourceFeedKey"),
                        "tripRoute": trip_route_name,
                        "fromStation": station_title(station_groups.get(station_group_id), station_group_id),
                        "toStation": station_title(station_groups.get(next_stop.get("stationGroupId")), str(next_stop.get("stationGroupId") or "")),
                        "sequence": stop.get("sequence"),
                    },
                )
                route_id = trip_route_id
            elif len(matches) > 1:
                ambiguous_trace_segment_count += 1
                ambiguous_trace_by_source[source] += 1
                add_sample(
                    ambiguous_trace_samples,
                    {
                        "tripId": trip.get("id"),
                        "sourceFeedKey": trip.get("sourceFeedKey"),
                        "tripRoute": trip_route_name,
                        "fromStation": station_title(station_groups.get(station_group_id), station_group_id),
                        "toStation": station_title(station_groups.get(next_stop.get("stationGroupId")), str(next_stop.get("stationGroupId") or "")),
                        "sequence": stop.get("sequence"),
                        "matchedRoutes": [route_title(routes.get(str(trace.get("routeId") or "")), str(trace.get("routeId") or "")) for trace in matches],
                    },
                )
                route_id = str(matches[0].get("routeId") or trip_route_id)
            else:
                route_id = str(matches[0].get("routeId") or trip_route_id)

            outgoing_route_by_sequence[sequence] = route_id
            if route_id:
                station_route_ids[station_group_id].add(route_id)
            if trip_route_id and route_id and trip_route_id != route_id:
                primary_segment_conflict_count += 1
                primary_segment_conflict_by_source[source] += 1
                pair = f"{trip_route_name} -> {route_title(routes.get(route_id), route_id)}"
                primary_trace_pair_counts[pair] += 1
                add_sample(
                    primary_segment_conflict_samples,
                    {
                        "tripId": trip.get("id"),
                        "sourceFeedKey": trip.get("sourceFeedKey"),
                        "station": station_title(station_groups.get(station_group_id), station_group_id),
                        "departure": seconds_to_hhmm(stop.get("departureTimeSec")),
                        "tripRoute": trip_route_name,
                        "segmentRoute": route_title(routes.get(route_id), route_id),
                        "sequence": stop.get("sequence"),
                    },
                )

        if stops:
            last_group_id = str(stops[-1].get("stationGroupId") or "")
            station_sequences[last_group_id].append(int(stops[-1].get("sequence") or len(stops)))

        for index in range(1, len(stops) - 1):
            stop = stops[index]
            sequence = int(stop.get("sequence") or index + 1)
            incoming_sequence = int(stops[index - 1].get("sequence") or index)
            incoming_route_id = outgoing_route_by_sequence.get(incoming_sequence) or ""
            outgoing_route_id = outgoing_route_by_sequence.get(sequence) or ""
            if not incoming_route_id or not outgoing_route_id or incoming_route_id == outgoing_route_id:
                continue
            station_group_id = str(stop.get("stationGroupId") or "")
            station_name = station_title(station_groups.get(station_group_id), station_group_id)
            incoming_name = route_title(routes.get(incoming_route_id), incoming_route_id)
            outgoing_name = route_title(routes.get(outgoing_route_id), outgoing_route_id)
            through_boundary_station_count += 1
            through_boundary_pair_counts[f"{station_name}: {incoming_name} -> {outgoing_name}"] += 1
            add_sample(
                through_boundary_station_samples,
                {
                    "tripId": trip.get("id"),
                    "sourceFeedKey": trip.get("sourceFeedKey"),
                    "station": station_name,
                    "sequence": sequence,
                    "incomingRoute": incoming_name,
                    "outgoingDisplayRoute": outgoing_name,
                    "rule": "boarding display route must use the outgoing segment after this station",
                },
            )

        for station_group_id, route_ids in station_route_ids.items():
            sequence_count = len(station_sequences.get(station_group_id) or [])
            if sequence_count > 1:
                repeated_station_stop_count += 1
            if len(route_ids) > 1:
                duplicate_train_station_count += 1
                duplicate_train_station_route_count += len(route_ids)
                duplicate_station_by_source[source] += 1
                route_names = sorted(route_title(routes.get(route_id), route_id) for route_id in route_ids)
                station_name = station_title(station_groups.get(station_group_id), station_group_id)
                station_duplicate_pair_counts[f"{station_name}: {' + '.join(route_names)}"] += 1
                add_sample(
                    duplicate_train_station_samples,
                    {
                        "tripId": trip.get("id"),
                        "sourceFeedKey": trip.get("sourceFeedKey"),
                        "station": station_name,
                        "tripRoute": trip_route_name,
                        "segmentRoutesAtStation": route_names,
                        "sequences": station_sequences.get(station_group_id) or [],
                    },
                )

    audit = {
        "schema": "onichase.v4.route_display_integrity_audit.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "inputs": {
            "mapBundle": rel(args.map_bundle),
            "timetable": rel(args.timetable),
        },
        "counts": {
            "tripCount": len(trips),
            "missingLineTraceSegmentCount": missing_trace_segment_count,
            "ambiguousLineTraceSegmentCount": ambiguous_trace_segment_count,
            "tripRouteNotInLineTraceCount": route_not_in_trace_count,
            "primaryRouteSegmentConflictCount": primary_segment_conflict_count,
            "duplicateTrainStationCount": duplicate_train_station_count,
            "duplicateTrainStationRouteMembershipCount": duplicate_train_station_route_count,
            "repeatedStationStopCount": repeated_station_stop_count,
            "missingLineSequenceTripCount": missing_line_sequence_count,
            "lineSequenceMismatchTripCount": line_sequence_mismatch_count,
            "throughBoundaryStationDecisionCount": through_boundary_station_count,
        },
        "bySource": {
            "missingLineTraceSegments": dict(sorted(missing_trace_by_source.items())),
            "ambiguousLineTraceSegments": dict(sorted(ambiguous_trace_by_source.items())),
            "tripRouteNotInLineTrace": dict(sorted(route_not_in_trace_by_source.items())),
            "primaryRouteSegmentConflicts": dict(sorted(primary_segment_conflict_by_source.items())),
            "duplicateTrainStations": dict(sorted(duplicate_station_by_source.items())),
            "missingLineSequence": dict(sorted(missing_line_sequence_by_source.items())),
            "lineSequenceMismatch": dict(sorted(line_sequence_mismatch_by_source.items())),
        },
        "topPrimaryTracePairs": dict(primary_trace_pair_counts.most_common(80)),
        "topDuplicateTrainStationRoutePairs": dict(station_duplicate_pair_counts.most_common(80)),
        "topThroughBoundaryRouteDecisions": dict(through_boundary_pair_counts.most_common(80)),
        "samples": {
            "missingLineTraceSegments": missing_trace_samples,
            "ambiguousLineTraceSegments": ambiguous_trace_samples,
            "tripRouteNotInLineTrace": route_not_in_trace_samples,
            "primaryRouteSegmentConflicts": primary_segment_conflict_samples,
            "duplicateTrainStations": duplicate_train_station_samples,
            "lineSequenceMismatches": line_sequence_mismatch_samples,
            "throughBoundaryRouteDecisions": through_boundary_station_samples,
        },
    }
    write_json(args.output, audit)
    print(
        "route display integrity audit: "
        f"{len(trips)} trips, "
        f"{missing_trace_segment_count} missing trace segments, "
        f"{ambiguous_trace_segment_count} ambiguous trace segments, "
        f"{route_not_in_trace_count} trip route/trace mismatches, "
        f"{duplicate_train_station_count} duplicate train-station route memberships"
    )
    print(f"wrote {rel(args.output)}")
    return 1 if duplicate_train_station_count or missing_trace_segment_count or ambiguous_trace_segment_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
