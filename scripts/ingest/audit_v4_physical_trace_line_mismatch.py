#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from build_v4_gameplay_bundle import (
    PHYSICAL_TRACE_WINS_LINE_NAMES,
    canonical_line_name,
    is_synthetic_line_name,
    operator_maps,
    physical_route_key_for_stop,
    route_id_for,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_CURRENT = ROOT / "data" / "v4_current_weekday_train_instances.json.gz"
DEFAULT_TIMETABLE = ROOT / "docs" / "data" / "v4_gameplay_timetable_compact.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_physical_trace_line_mismatch_audit.json"


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def route_title(routes: dict[str, dict[str, Any]], route_id: str) -> str:
    route = routes.get(route_id) or {}
    return str(route.get("shortName") or route.get("tags", {}).get("lineName") or route_id)


def station_group_name(station_groups: dict[str, dict[str, Any]], station_group_id: str) -> str:
    group = station_groups.get(station_group_id) or {}
    return str((group.get("names") or {}).get("ja") or group.get("primaryName") or station_group_id)


def physical_lines_by_group(physical_map: dict[str, Any]) -> dict[str, set[tuple[str, str]]]:
    result: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for station in physical_map.get("physicalStations", []):
        group_id = station.get("stationGroupId")
        operator_id = station.get("operatorId")
        line_name = station.get("lineName")
        if group_id and operator_id and line_name:
            result[group_id].add((operator_id, line_name))
    return result


def audit_raw_source_mismatches(
    current: dict[str, Any],
    physical_map: dict[str, Any],
    reviewed_line_names: set[str],
) -> tuple[Counter[tuple[str, str, str]], list[dict[str, Any]]]:
    physical_station_by_id = {station["id"]: station for station in physical_map.get("physicalStations", []) if station.get("id")}
    id_to_name, name_to_id = operator_maps(physical_map)
    counts: Counter[tuple[str, str, str]] = Counter()
    samples: list[dict[str, Any]] = []
    for train in current.get("train_instances", []):
        raw_train_line = train.get("line_name")
        if not (is_synthetic_line_name(raw_train_line) or str(raw_train_line or "") in reviewed_line_names):
            continue
        for stop in train.get("stop_times") or []:
            raw_line = canonical_line_name(stop.get("line_name") or raw_train_line)
            if raw_line not in reviewed_line_names:
                continue
            physical_key = physical_route_key_for_stop(stop, train, physical_station_by_id, name_to_id, id_to_name)
            if not physical_key:
                continue
            physical_operator_id, physical_line = physical_key
            if physical_line not in reviewed_line_names or physical_line == raw_line:
                continue
            key = (str(train.get("operator_id") or physical_operator_id), raw_line, physical_line)
            counts[key] += 1
            if len(samples) < 80:
                samples.append(
                    {
                        "kind": "raw_source_line_disagrees_with_physical_station",
                        "trainId": train.get("service_instance_id") or train.get("source_trip_id"),
                        "sourceLine": raw_line,
                        "physicalLine": physical_line,
                        "station": stop.get("station_name_raw") or stop.get("station_name") or stop.get("station_group_id"),
                        "sequence": stop.get("sequence"),
                    }
                )
    return counts, samples


def decode_compact_timetable(payload: dict[str, Any]) -> list[dict[str, Any]]:
    station_group_ids = payload.get("stationGroupIds") or []
    route_ids = payload.get("routeIds") or []
    trips = []
    for row in payload.get("trips") or []:
        trips.append(
            {
                "id": row[0],
                "routeId": route_ids[row[1]] if isinstance(row[1], int) and row[1] < len(route_ids) else "",
                "stopTimes": [
                    {
                        "sequence": index + 1,
                        "stationGroupId": station_group_ids[stop[0]] if stop and stop[0] < len(station_group_ids) else "",
                    }
                    for index, stop in enumerate(row[4] or [])
                ],
                "lineTrace": [
                    {
                        "fromSequence": trace[0],
                        "toSequence": trace[1],
                        "routeId": route_ids[trace[2]] if trace and trace[2] < len(route_ids) else "",
                    }
                    for trace in (row[5] if len(row) > 5 else []) or []
                ],
            }
        )
    return trips


def audit_gameplay_trace_mismatches(
    timetable: dict[str, Any],
    physical_map: dict[str, Any],
    reviewed_line_names: set[str],
) -> tuple[Counter[tuple[str, str]], list[dict[str, Any]]]:
    routes = {route["id"]: route for route in physical_map.get("serviceRoutes", []) if route.get("id")}
    if not routes:
        routes = {
            route_id_for(route["operatorId"], route["shortName"]): route
            for route in physical_map.get("serviceRoutes", [])
            if route.get("operatorId") and route.get("shortName")
        }
    for line_name in reviewed_line_names:
        routes.setdefault(
            route_id_for("jr_east", line_name),
            {"id": route_id_for("jr_east", line_name), "shortName": line_name, "operatorId": "jr_east"},
        )
    station_groups = {group["id"]: group for group in physical_map.get("stationGroups", []) if group.get("id")}
    lines_by_group = physical_lines_by_group(physical_map)
    counts: Counter[tuple[str, str]] = Counter()
    samples: list[dict[str, Any]] = []
    for trip in decode_compact_timetable(timetable):
        stops = trip.get("stopTimes") or []
        if len(stops) < 2:
            continue
        stops_by_sequence = {stop["sequence"]: stop for stop in stops}
        for trace in trip.get("lineTrace") or []:
            trace_line = route_title(routes, trace.get("routeId") or "")
            if trace_line not in reviewed_line_names:
                continue
            for sequence in range(int(trace.get("fromSequence") or 0), int(trace.get("toSequence") or 0)):
                left = stops_by_sequence.get(sequence)
                right = stops_by_sequence.get(sequence + 1)
                if not left or not right:
                    continue
                left_lines = lines_by_group.get(left["stationGroupId"], set())
                right_lines = lines_by_group.get(right["stationGroupId"], set())
                shared_reviewed_lines = {
                    line
                    for operator_id, line in left_lines & right_lines
                    if line in reviewed_line_names and operator_id == "jr_east"
                }
                if not shared_reviewed_lines or trace_line in shared_reviewed_lines:
                    continue
                expected = sorted(shared_reviewed_lines)[0]
                counts[(trace_line, expected)] += 1
                if len(samples) < 80:
                    samples.append(
                        {
                            "kind": "gameplay_trace_line_disagrees_with_physical_adjacent_segment",
                            "tripId": trip["id"],
                            "traceLine": trace_line,
                            "expectedPhysicalLine": expected,
                            "fromStation": station_group_name(station_groups, left["stationGroupId"]),
                            "toStation": station_group_name(station_groups, right["stationGroupId"]),
                            "fromSequence": sequence,
                        }
                    )
    return counts, samples


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit reviewed physical-line corridors where source service labels can disagree with the actual adjacent track line.")
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--current-trains", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--timetable", type=Path, default=DEFAULT_TIMETABLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    physical_map = load_json(args.physical_map)
    current = load_json(args.current_trains)
    timetable = load_json(args.timetable)
    reviewed_line_names = set(PHYSICAL_TRACE_WINS_LINE_NAMES)
    raw_counts, raw_samples = audit_raw_source_mismatches(current, physical_map, reviewed_line_names)
    gameplay_counts, gameplay_samples = audit_gameplay_trace_mismatches(timetable, physical_map, reviewed_line_names)
    payload = {
        "schema": "onichase.v4.physical_trace_line_mismatch_audit.v1",
        "inputs": {
            "physicalMap": str(args.physical_map.relative_to(ROOT)),
            "currentTrains": str(args.current_trains.relative_to(ROOT)),
            "timetable": str(args.timetable.relative_to(ROOT)),
        },
        "reviewedLineNames": sorted(reviewed_line_names),
        "rawSourceMismatchStopCount": sum(raw_counts.values()),
        "rawSourceMismatchGroups": [
            {"operatorId": operator_id, "sourceLine": source, "physicalLine": physical, "stopCount": count}
            for (operator_id, source, physical), count in raw_counts.most_common()
        ],
        "gameplayTraceMismatchSegmentCount": sum(gameplay_counts.values()),
        "gameplayTraceMismatchGroups": [
            {"traceLine": trace, "expectedPhysicalLine": expected, "segmentCount": count}
            for (trace, expected), count in gameplay_counts.most_common()
        ],
        "samples": [*gameplay_samples, *raw_samples][:160],
    }
    write_json(args.output, payload)
    print(
        f"Wrote {args.output}: raw_source_mismatch_stops={payload['rawSourceMismatchStopCount']} "
        f"gameplay_trace_mismatch_segments={payload['gameplayTraceMismatchSegmentCount']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
