#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUNDLE = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_track_continuity_audit.json"


def load_bundle(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def haversine_meters(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = a
    lon2, lat2 = b
    radius = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    value = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(value), math.sqrt(1 - value))


class Dsu:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, a: int, b: int) -> None:
        root_a = self.find(a)
        root_b = self.find(b)
        if root_a != root_b:
            self.parent[root_b] = root_a


def cell_for(point: tuple[float, float], cell_size: float) -> tuple[int, int]:
    lon, lat = point
    return math.floor(lon / cell_size), math.floor(lat / cell_size)


def component_summary(tracks: list[dict[str, Any]], tolerance_m: float) -> dict[str, Any]:
    dsu = Dsu(len(tracks))
    cell_size = 0.003
    grid: dict[tuple[int, int], list[tuple[int, tuple[float, float]]]] = defaultdict(list)
    for index, track in enumerate(tracks):
        points = track.get("points", [])
        if len(points) < 2:
            continue
        for point in (tuple(points[0]), tuple(points[-1])):
            cell = cell_for(point, cell_size)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for other_index, other_point in grid.get((cell[0] + dx, cell[1] + dy), []):
                        if haversine_meters(point, other_point) <= tolerance_m:
                            dsu.union(index, other_index)
            grid[cell].append((index, point))

    components: dict[int, dict[str, Any]] = {}
    for index, track in enumerate(tracks):
        root = dsu.find(index)
        entry = components.setdefault(
            root,
            {
                "trackCenterlineCount": 0,
                "pointCount": 0,
                "bbox": None,
                "sampleTrackIds": [],
            },
        )
        entry["trackCenterlineCount"] += 1
        entry["pointCount"] += len(track.get("points", []))
        if len(entry["sampleTrackIds"]) < 5:
            entry["sampleTrackIds"].append(track.get("id"))
        for lon, lat in track.get("points", []):
            bbox = entry["bbox"]
            entry["bbox"] = [lon, lat, lon, lat] if bbox is None else [
                min(bbox[0], lon),
                min(bbox[1], lat),
                max(bbox[2], lon),
                max(bbox[3], lat),
            ]
    return {
        "componentCount": len(components),
        "components": sorted(
            [
                {
                    **value,
                    "bbox": [round(coord, 6) for coord in value["bbox"]] if value["bbox"] else None,
                }
                for value in components.values()
            ],
            key=lambda item: (-item["trackCenterlineCount"], item["bbox"] or []),
        ),
    }


def build_audit(bundle: dict[str, Any], tolerance_m: float) -> dict[str, Any]:
    by_line: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for track in bundle.get("trackCenterlines", []):
        by_line[(track["operatorId"], track["lineName"])].append(track)

    warnings = []
    for (operator_id, line_name), tracks in by_line.items():
        summary = component_summary(tracks, tolerance_m)
        if summary["componentCount"] <= 1:
            continue
        first_track = tracks[0]
        warnings.append(
            {
                "operatorId": operator_id,
                "operatorName": first_track["operatorName"],
                "lineName": line_name,
                "trackCenterlineCount": len(tracks),
                "componentCount": summary["componentCount"],
                "largestComponents": summary["components"][:8],
            }
        )
    warnings.sort(key=lambda item: (-item["componentCount"], item["operatorName"], item["lineName"]))
    return {
        "schema": "onichase.v4.track_continuity_audit.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceBundleSchema": bundle.get("schema"),
        "sourceGeneratedAt": bundle.get("generatedAt"),
        "endpointSnapToleranceMeters": tolerance_m,
        "counts": {
            "operatorLinePairs": len(by_line),
            "multiComponentLineCount": len(warnings),
        },
        "multiComponentLineSamples": warnings[:100],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit physical continuity for v4 track centerlines.")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--tolerance-m", type=float, default=120.0)
    args = parser.parse_args()

    bundle = load_bundle(args.bundle)
    audit = build_audit(bundle, args.tolerance_m)
    args.output.write_text(json.dumps(audit, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(
        "Audited v4 track continuity:",
        f"{audit['counts']['multiComponentLineCount']} multi-component lines",
        f"out of {audit['counts']['operatorLinePairs']} operator-line pairs.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
