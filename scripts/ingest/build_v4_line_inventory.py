#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_v4_japan_physical_map import DEFAULT_OUTPUT, stable_id, write_json, load_json
from v4_visual_identity import color_for_operator, color_for_operator_line, color_source_for_operator_line


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY_OUTPUT = ROOT / "data" / "v4_nationwide_line_inventory.json"


def extend_bbox(bbox: list[float] | None, lon: float, lat: float) -> list[float]:
    if bbox is None:
        return [lon, lat, lon, lat]
    return [min(bbox[0], lon), min(bbox[1], lat), max(bbox[2], lon), max(bbox[3], lat)]


def build_line_inventory(bundle: dict[str, Any]) -> dict[str, Any]:
    lines: dict[tuple[str, str], dict[str, Any]] = {}

    def entry_for(operator_id: str, operator_name: str, line_name: str) -> dict[str, Any]:
        key = (operator_id, line_name)
        operator_color = color_for_operator(operator_id)
        line_color = color_for_operator_line(operator_id, line_name)
        return lines.setdefault(
            key,
            {
                "id": stable_id("LINE", operator_id, line_name),
                "operatorId": operator_id,
                "operatorName": operator_name,
                "operatorColor": operator_color,
                "lineColor": line_color,
                "lineColorSource": color_source_for_operator_line(operator_id, line_name),
                "lineName": line_name,
                "physicalStationCount": 0,
                "stationGroupIds": set(),
                "trackCenterlineCount": 0,
                "railwayClasses": set(),
                "railwayTypes": set(),
                "sampleStationNames": [],
                "_stationNamesSeen": set(),
                "_bbox": None,
            },
        )

    for station in bundle.get("physicalStations", []):
        operator_id = station.get("operatorId") or "unknown_operator"
        operator_name = station.get("operatorName") or operator_id
        line_name = station.get("lineName") or "unknown_line"
        entry = entry_for(operator_id, operator_name, line_name)
        entry["physicalStationCount"] += 1
        if station.get("stationGroupId"):
            entry["stationGroupIds"].add(station["stationGroupId"])
        name = station.get("nameJa")
        if name and name not in entry["_stationNamesSeen"] and len(entry["sampleStationNames"]) < 10:
            entry["_stationNamesSeen"].add(name)
            entry["sampleStationNames"].append(name)
        if isinstance(station.get("lon"), (int, float)) and isinstance(station.get("lat"), (int, float)):
            entry["_bbox"] = extend_bbox(entry["_bbox"], float(station["lon"]), float(station["lat"]))

    for track in bundle.get("trackCenterlines", []):
        operator_id = track.get("operatorId") or "unknown_operator"
        operator_name = track.get("operatorName") or operator_id
        line_name = track.get("lineName") or "unknown_line"
        entry = entry_for(operator_id, operator_name, line_name)
        entry["trackCenterlineCount"] += 1
        if track.get("railwayClass"):
            entry["railwayClasses"].add(str(track["railwayClass"]))
        if track.get("railwayType"):
            entry["railwayTypes"].add(str(track["railwayType"]))
        for lon, lat in track.get("points", []):
            entry["_bbox"] = extend_bbox(entry["_bbox"], float(lon), float(lat))

    line_entries = []
    for entry in lines.values():
        line_entries.append(
            {
                "id": entry["id"],
                "operatorId": entry["operatorId"],
                "operatorName": entry["operatorName"],
                "operatorColor": entry["operatorColor"],
                "lineColor": entry["lineColor"],
                "lineColorSource": entry["lineColorSource"],
                "lineName": entry["lineName"],
                "physicalStationCount": entry["physicalStationCount"],
                "stationGroupCount": len(entry["stationGroupIds"]),
                "trackCenterlineCount": entry["trackCenterlineCount"],
                "railwayClasses": sorted(entry["railwayClasses"]),
                "railwayTypes": sorted(entry["railwayTypes"]),
                "bbox": [round(value, 7) for value in entry["_bbox"]] if entry["_bbox"] else None,
                "sampleStationNames": entry["sampleStationNames"],
            }
        )
    line_entries.sort(key=lambda item: (item["operatorName"], item["lineName"]))

    operator_counts: dict[str, dict[str, Any]] = {}
    for line in line_entries:
        operator_id = line["operatorId"]
        operator = operator_counts.setdefault(
            operator_id,
            {
                "operatorId": operator_id,
                "operatorName": line["operatorName"],
                "operatorColor": line["operatorColor"],
                "lineCount": 0,
                "physicalStationCount": 0,
                "trackCenterlineCount": 0,
            },
        )
        operator["lineCount"] += 1
        operator["physicalStationCount"] += line["physicalStationCount"]
        operator["trackCenterlineCount"] += line["trackCenterlineCount"]

    return {
        "schema": "onichase.v4.nationwide_line_inventory.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceBundleSchema": bundle.get("schema"),
        "sourceGeneratedAt": bundle.get("generatedAt"),
        "counts": {
            "operatorLinePairs": len(line_entries),
            "uniqueLineNames": len({line["lineName"] for line in line_entries}),
            "operators": len(operator_counts),
            "linesWithoutStations": sum(1 for line in line_entries if line["physicalStationCount"] == 0),
            "linesWithoutTracks": sum(1 for line in line_entries if line["trackCenterlineCount"] == 0),
        },
        "operators": sorted(operator_counts.values(), key=lambda item: item["operatorName"]),
        "lines": line_entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a nationwide operated-line inventory from the v4 physical bundle.")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_INVENTORY_OUTPUT)
    args = parser.parse_args()

    bundle = load_json(args.bundle)
    inventory = build_line_inventory(bundle)
    write_json(args.output, inventory)
    counts = inventory["counts"]
    print(
        "Built v4 nationwide line inventory:",
        f"{counts['operatorLinePairs']} operator-line pairs,",
        f"{counts['uniqueLineNames']} unique line names,",
        f"{counts['operators']} operators,",
        f"{counts['linesWithoutStations']} stationless,",
        f"{counts['linesWithoutTracks']} trackless.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
