#!/usr/bin/env python3
"""Audit non-JR operator-line timetable coverage for the v4 nationwide scope.

The audit works from station identity rather than only comparing line-name text:
if a train has at least two matched stops on a physical operator-line, that line
is treated as timetable-covered.  This handles legacy v3 route ids, through
services, and GTFS feeds whose route names are broader than physical line names.
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
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_INVENTORY = ROOT / "data" / "v4_nationwide_line_inventory.json"
DEFAULT_TRAINS = ROOT / "data" / "v4_current_weekday_train_instances.json.gz"
DEFAULT_SOURCE_REGISTRY = ROOT / "data" / "v4_timetable_source_registry.json"
DEFAULT_NO_WEEKDAY_SERVICE = ROOT / "data" / "v4_verified_no_weekday_service_lines.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_non_jr_timetable_coverage_audit.json"

JR_OPERATOR_NAMES = {
    "北海道旅客鉄道",
    "東日本旅客鉄道",
    "東海旅客鉄道",
    "西日本旅客鉄道",
    "四国旅客鉄道",
    "九州旅客鉄道",
    "JR Shinkansen",
}


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def station_refs(stop: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("physical_station_id", "station_id", "stationId", "station_group_id", "stationGroupId"):
        value = stop.get(key)
        if value and value not in refs:
            refs.append(str(value))
    return refs


def build_physical_line_lookup(physical_map: dict[str, Any]) -> dict[str, set[tuple[str, str, str]]]:
    """Map physical station/group ids to (operator, line, station-group) triples."""

    refs: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    for station in physical_map.get("physicalStations", []):
        operator = str(station.get("operatorName") or "")
        line = str(station.get("lineName") or "")
        group_id = str(station.get("stationGroupId") or station.get("id") or "")
        physical_id = str(station.get("id") or "")
        if not operator or not line or not group_id:
            continue
        triple = (operator, line, group_id)
        refs[group_id].add(triple)
        if physical_id:
            refs[physical_id].add(triple)
    return refs


def build_source_status_lookup(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    registry = load_json(path)
    return {
        item["operatorName"]: {
            "sourceStatus": item.get("sourceStatus"),
            "knownTrainInstanceCount": item.get("knownTrainInstanceCount"),
            "leadCount": len(item.get("sourceLeads") or []),
        }
        for item in registry.get("operators", [])
        if item.get("operatorName")
    }


def build_no_weekday_service_lookup(path: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    if not path or not path.exists():
        return {}
    payload = load_json(path)
    return {
        (str(item.get("operatorName") or ""), str(item.get("lineName") or "")): item
        for item in payload.get("lines", [])
        if item.get("operatorName") and item.get("lineName")
    }


def audit(
    physical_map: dict[str, Any],
    inventory: dict[str, Any],
    train_collection: dict[str, Any],
    source_status: dict[str, dict[str, Any]],
    no_weekday_service: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    non_jr_lines = [
        line for line in inventory.get("lines", [])
        if line.get("operatorName") not in JR_OPERATOR_NAMES
    ]
    lines_by_operator: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in non_jr_lines:
        lines_by_operator[line["operatorName"]].append(line)

    line_lookup = {
        (line["operatorName"], line["lineName"]): line
        for line in non_jr_lines
    }
    line_station_groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for station in physical_map.get("physicalStations", []):
        key = (str(station.get("operatorName") or ""), str(station.get("lineName") or ""))
        if key in line_lookup:
            group_id = str(station.get("stationGroupId") or station.get("id") or "")
            if group_id:
                line_station_groups[key].add(group_id)
    line_train_counts: Counter[tuple[str, str]] = Counter()
    line_stop_group_counts: dict[tuple[str, str], set[str]] = defaultdict(set)
    line_samples: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    operator_train_counts: Counter[str] = Counter()
    station_line_lookup = build_physical_line_lookup(physical_map)

    for train in train_collection.get("train_instances", []):
        operator = str(train.get("operator_name") or "")
        if not operator or operator in JR_OPERATOR_NAMES:
            continue
        operator_train_counts[operator] += 1
        train_line_groups: dict[tuple[str, str], set[str]] = defaultdict(set)
        for stop in train.get("stop_times") or []:
            for ref in station_refs(stop):
                for ref_operator, line_name, group_id in station_line_lookup.get(ref, set()):
                    if ref_operator == operator and (ref_operator, line_name) in line_lookup:
                        train_line_groups[(ref_operator, line_name)].add(group_id)

        for key, group_ids in train_line_groups.items():
            required_group_count = min(2, max(1, len(line_station_groups.get(key, set()))))
            if len(group_ids) < required_group_count:
                continue
            line_train_counts[key] += 1
            line_stop_group_counts[key].update(group_ids)
            if len(line_samples[key]) < 5:
                line_samples[key].append(
                    {
                        "serviceInstanceId": train.get("service_instance_id"),
                        "trainNumber": train.get("train_number"),
                        "lineName": train.get("line_name"),
                        "sourceCollection": train.get("source_collection"),
                        "matchedStopGroupCountOnLine": len(group_ids),
                    }
                )

    operator_entries: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    covered_line_count = 0
    resolved_line_count = 0
    missing_line_count = 0
    for operator_name, lines in sorted(lines_by_operator.items()):
        line_entries: list[dict[str, Any]] = []
        covered = 0
        resolved = 0
        for line in sorted(lines, key=lambda item: item["lineName"]):
            key = (operator_name, line["lineName"])
            train_count = line_train_counts[key]
            is_covered = train_count > 0
            no_weekday = no_weekday_service.get(key)
            if is_covered:
                covered += 1
                covered_line_count += 1
                resolved += 1
                resolved_line_count += 1
            elif no_weekday:
                resolved += 1
                resolved_line_count += 1
            else:
                missing_line_count += 1
            line_entries.append(
                {
                    "lineName": line["lineName"],
                    "physicalStationCount": line.get("physicalStationCount"),
                    "trackCenterlineCount": line.get("trackCenterlineCount"),
                    "coverageStatus": "covered" if is_covered else ("no_weekday_service" if no_weekday else "missing_timetable"),
                    "noWeekdayService": no_weekday,
                    "trainCount": train_count,
                    "coveredStationGroupCount": len(line_stop_group_counts[key]),
                    "sampleTrains": line_samples.get(key, []),
                }
            )
        if resolved == len(lines):
            status = "complete"
        elif covered:
            status = "partial"
        elif operator_train_counts[operator_name]:
            status = "trains_present_no_line_coverage"
        else:
            status = "missing"
        status_counts[status] += 1
        operator_entries.append(
            {
                "operatorName": operator_name,
                "operatorId": lines[0].get("operatorId"),
                "lineCount": len(lines),
                "coveredLineCount": covered,
                "resolvedLineCount": resolved,
                "missingLineCount": len(lines) - resolved,
                "operatorTrainCount": operator_train_counts[operator_name],
                "coverageStatus": status,
                **source_status.get(operator_name, {}),
                "lines": line_entries,
            }
        )

    operator_entries.sort(key=lambda item: (-item["missingLineCount"], -item["lineCount"], item["operatorName"]))
    return {
        "schema": "onichase.v4.non_jr_timetable_coverage_audit.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "counts": {
            "operatorCount": len(operator_entries),
            "operatorLineCount": len(non_jr_lines),
            "coveredLineCount": covered_line_count,
            "resolvedLineCount": resolved_line_count,
            "missingLineCount": missing_line_count,
            "coverageStatusCounts": dict(sorted(status_counts.items())),
        },
        "operators": operator_entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--trains", type=Path, default=DEFAULT_TRAINS)
    parser.add_argument("--source-registry", type=Path, default=DEFAULT_SOURCE_REGISTRY)
    parser.add_argument("--no-weekday-service", type=Path, default=DEFAULT_NO_WEEKDAY_SERVICE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = audit(
        load_json(args.physical_map),
        load_json(args.inventory),
        load_json(args.trains),
        build_source_status_lookup(args.source_registry),
        build_no_weekday_service_lookup(args.no_weekday_service),
    )
    result["inputs"] = {
        "physicalMap": relative(args.physical_map),
        "inventory": relative(args.inventory),
        "trains": relative(args.trains),
        "sourceRegistry": relative(args.source_registry),
        "noWeekdayService": relative(args.no_weekday_service),
    }
    write_json(args.output, result)
    counts = result["counts"]
    print(
        f"Wrote {args.output}: "
        f"{counts['coveredLineCount']}/{counts['operatorLineCount']} non-JR operator-lines covered; "
        f"{counts['resolvedLineCount']}/{counts['operatorLineCount']} resolved; "
        f"{counts['coverageStatusCounts']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
