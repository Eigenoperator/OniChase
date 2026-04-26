#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_v4_japan_physical_map import DEFAULT_OUTPUT, write_json, load_json
from build_v4_line_inventory import build_line_inventory
from v4_visual_identity import color_for_operator


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "data" / "v4_maplibre"
LAND_OUTLINE_FILENAME = "japan_land.geojson"
LAND_OVERVIEW_FILENAME = "japan_land_overview.geojson"

MAJOR_STATION_NAMES = {
    "札幌",
    "仙台",
    "大宮",
    "上野",
    "東京",
    "品川",
    "新宿",
    "渋谷",
    "池袋",
    "横浜",
    "名古屋",
    "京都",
    "新大阪",
    "大阪",
    "三ノ宮",
    "岡山",
    "広島",
    "小倉",
    "博多",
    "熊本",
    "鹿児島中央",
}


def feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def perpendicular_distance(point: list[float], start: list[float], end: list[float]) -> float:
    x, y = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    return abs(dy * x - dx * y + x2 * y1 - y2 * x1) / ((dx * dx + dy * dy) ** 0.5)


def simplify_line(points: list[list[float]], tolerance: float) -> list[list[float]]:
    if len(points) <= 2:
        return points
    max_distance = -1.0
    split_index = 0
    start = points[0]
    end = points[-1]
    for index in range(1, len(points) - 1):
        distance = perpendicular_distance(points[index], start, end)
        if distance > max_distance:
            max_distance = distance
            split_index = index
    if max_distance <= tolerance:
        return [start, end]
    left = simplify_line(points[: split_index + 1], tolerance)
    right = simplify_line(points[split_index:], tolerance)
    return left[:-1] + right


def label_rank_for_group(group: dict[str, Any]) -> int:
    name = group.get("nameJa")
    physical_count = int(group.get("physicalStationCount", 0))
    operator_count = len(group.get("operatorIds", []))
    line_count = len(group.get("lineNames", []))
    rank = 30 + physical_count * 24 + operator_count * 16 + line_count * 8
    if name in MAJOR_STATION_NAMES:
        rank += 900
    if physical_count >= 3:
        rank += 120
    if operator_count >= 3:
        rank += 90
    return min(rank, 1200)


def v3_label_rank_for_group(group: dict[str, Any]) -> int:
    rank = label_rank_for_group(group)
    if rank >= 900:
        return 99
    if rank >= 260:
        return 90
    return min(89, max(10, int(round(30 + rank / 4))))


def physical_station_features(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    features = []
    for station in bundle.get("physicalStations", []):
        operator_id = station["operatorId"]
        features.append(
            {
                "type": "Feature",
                "id": station["id"],
                "geometry": {"type": "Point", "coordinates": [station["lon"], station["lat"]]},
                "properties": {
                    "id": station["id"],
                    "station_group_id": station["stationGroupId"],
                    "name_ja": station["nameJa"],
                    "name_key": station["nameKey"],
                    "operator_id": operator_id,
                    "operator_name": station["operatorName"],
                    "operator_color": color_for_operator(operator_id),
                    "line_name": station["lineName"],
                    "source_station_code": station.get("sourceStationCode"),
                    "source_group_code": station.get("sourceGroupCode"),
                    "prefecture_code": station.get("prefectureCode"),
                    "prefecture_name_ja": station.get("prefectureNameJa"),
                    "prefecture_name_en": station.get("prefectureNameEn"),
                    "prefecture_assignment_method": station.get("prefectureAssignmentMethod"),
                    "location_note": station.get("locationNote"),
                },
            }
        )
    return features


def station_group_features(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    features = []
    for group in bundle.get("stationGroups", []):
        centroid = group["centroid"]
        operator_ids = group.get("operatorIds", [])
        primary_operator_id = operator_ids[0] if operator_ids else "unknown_operator"
        features.append(
            {
                "type": "Feature",
                "id": group["id"],
                "geometry": {"type": "Point", "coordinates": [centroid["lon"], centroid["lat"]]},
                "properties": {
                    "id": group["id"],
                    "name_ja": group["nameJa"],
                    "name_keys": ",".join(group.get("nameKeys", [])),
                    "operator_ids": ",".join(operator_ids),
                    "operator_names": ",".join(group.get("operatorNames", [])),
                    "operator_color": color_for_operator(primary_operator_id),
                    "line_names": ",".join(group.get("lineNames", [])),
                    "prefecture_codes": ",".join(group.get("prefectureCodes", [])),
                    "prefecture_names_ja": ",".join(group.get("prefectureNamesJa", [])),
                    "prefecture_names_en": ",".join(group.get("prefectureNamesEn", [])),
                    "location_note": group.get("locationNote"),
                    "physical_station_count": group.get("physicalStationCount", 0),
                    "label_rank": label_rank_for_group(group),
                    "grouping_method": group.get("groupingMethod"),
                    "source_group_codes": ",".join(group.get("sourceGroupCodes", [])),
                },
            }
        )
    return features


def station_label_features(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    features = []
    for group in bundle.get("stationGroups", []):
        centroid = group["centroid"]
        operator_ids = group.get("operatorIds", [])
        label_rank = v3_label_rank_for_group(group)
        features.append(
            {
                "type": "Feature",
                "id": f"label-{group['id']}",
                "geometry": {"type": "Point", "coordinates": [centroid["lon"], centroid["lat"]]},
                "properties": {
                    "id": f"label-{group['id']}",
                    "station_group_id": group["id"],
                    "name_ja": group["nameJa"],
                    "name_en": group["nameJa"],
                    "operator_ids": ",".join(operator_ids),
                    "line_names": ",".join(group.get("lineNames", [])),
                    "prefecture_names_ja": ",".join(group.get("prefectureNamesJa", [])),
                    "location_note": group.get("locationNote"),
                    "physical_station_count": group.get("physicalStationCount", 0),
                    "label_rank": label_rank,
                    "sort_rank": -label_rank,
                },
            }
        )
    return features


def track_centerline_features(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    features = []
    for track in bundle.get("trackCenterlines", []):
        operator_id = track["operatorId"]
        features.append(
            {
                "type": "Feature",
                "id": track["id"],
                "geometry": {"type": "LineString", "coordinates": track["points"]},
                "properties": {
                    "id": track["id"],
                    "operator_id": operator_id,
                    "operator_name": track["operatorName"],
                    "operator_color": color_for_operator(operator_id),
                    "line_name": track["lineName"],
                    "railway_class": track.get("railwayClass"),
                    "railway_type": track.get("railwayType"),
                    "source_feature_index": track.get("source", {}).get("featureIndex"),
                },
            }
        )
    return features


def track_overview_features(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for track in bundle.get("trackCenterlines", []):
        operator_id = track["operatorId"]
        line_name = track["lineName"]
        key = (operator_id, line_name)
        entry = grouped.setdefault(
            key,
            {
                "id": f"OVERVIEW_{track['id']}",
                "operatorId": operator_id,
                "operatorName": track["operatorName"],
                "operatorColor": color_for_operator(operator_id),
                "lineName": line_name,
                "railwayClasses": set(),
                "railwayTypes": set(),
                "segments": [],
                "trackCenterlineCount": 0,
            },
        )
        if track.get("railwayClass"):
            entry["railwayClasses"].add(str(track["railwayClass"]))
        if track.get("railwayType"):
            entry["railwayTypes"].add(str(track["railwayType"]))
        simplified = simplify_line(track["points"], tolerance=0.0045)
        if len(simplified) >= 2:
            entry["segments"].append(simplified)
        entry["trackCenterlineCount"] += 1

    features = []
    for entry in grouped.values():
        if not entry["segments"]:
            continue
        features.append(
            {
                "type": "Feature",
                "id": entry["id"],
                "geometry": {"type": "MultiLineString", "coordinates": entry["segments"]},
                "properties": {
                    "id": entry["id"],
                    "operator_id": entry["operatorId"],
                    "operator_name": entry["operatorName"],
                    "operator_color": entry["operatorColor"],
                    "line_name": entry["lineName"],
                    "track_centerline_count": entry["trackCenterlineCount"],
                    "railway_classes": ",".join(sorted(entry["railwayClasses"])),
                    "railway_types": ",".join(sorted(entry["railwayTypes"])),
                },
            }
        )
    return sorted(features, key=lambda feature: (feature["properties"]["operator_name"], feature["properties"]["line_name"]))


def build_sources(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "track_overview": feature_collection(track_overview_features(bundle)),
        "track_centerlines": feature_collection(track_centerline_features(bundle)),
        "station_groups": feature_collection(station_group_features(bundle)),
        "station_labels": feature_collection(station_label_features(bundle)),
        "physical_stations": feature_collection(physical_station_features(bundle)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export v4 physical bundle into MapLibre-ready GeoJSON sources.")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    bundle = load_json(args.bundle)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sources = build_sources(bundle)
    for name, payload in sources.items():
        write_json(args.output_dir / f"{name}.geojson", payload)
    line_inventory = build_line_inventory(bundle)
    write_json(args.output_dir / "line_inventory.json", line_inventory)

    manifest = {
        "schema": "onichase.v4.maplibre_sources.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceBundleSchema": bundle.get("schema"),
        "sourceGeneratedAt": bundle.get("generatedAt"),
        "layers": {
            name: {
                "path": f"{name}.geojson",
                "featureCount": len(payload["features"]),
                "geometryType": payload["features"][0]["geometry"]["type"] if payload["features"] else None,
            }
            for name, payload in sources.items()
        },
        "supportingFiles": {
            "line_inventory": {
                "path": "line_inventory.json",
                "operatorLinePairs": line_inventory["counts"]["operatorLinePairs"],
                "uniqueLineNames": line_inventory["counts"]["uniqueLineNames"],
                "operators": line_inventory["counts"]["operators"],
            },
        },
    }
    if (args.output_dir / LAND_OUTLINE_FILENAME).exists():
        manifest["supportingFiles"]["land_outline"] = {"path": LAND_OUTLINE_FILENAME}
    if (args.output_dir / LAND_OVERVIEW_FILENAME).exists():
        manifest["supportingFiles"]["land_outline_overview"] = {"path": LAND_OVERVIEW_FILENAME}
    write_json(args.output_dir / "manifest.json", manifest)
    print(
        "Wrote v4 MapLibre sources:",
        ", ".join(f"{name}={layer['featureCount']}" for name, layer in manifest["layers"].items()),
        f"to {args.output_dir}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
