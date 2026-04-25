#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import math
import re
import unicodedata
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v3_station_identity import build_station_alias_index, normalize_key, resolve_station_key
from v3_route_identity import canonical_route_line


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

BUNDLE_PATH = DATA_DIR / "v3_tokyo_bundle.json.gz"
MAP_PATH = DATA_DIR / "v3_tokyo_phase1_service_views.json"
UNIFIED_TRAINS_PATH = DATA_DIR / "v3_trains_unified.json.gz"
REPORT_PATH = DATA_DIR / "v3_tokyo_bundle_audit.json"

CENTRAL_STATION_NAMES = [
    "東京",
    "新宿",
    "渋谷",
    "池袋",
    "上野",
    "品川",
    "横浜",
    "大手町",
    "日本橋",
    "銀座",
    "新橋",
    "秋葉原",
    "北千住",
]


def load_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def route_id_for(line: Any, operator_id: str) -> str:
    import hashlib

    base = str(line or operator_id or "unknown")
    digest = hashlib.sha1(f"{operator_id}|{base}".encode("utf-8")).hexdigest()[:8].upper()
    return f"R_{digest}"


def distance_m(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    radius = 6_371_000
    phi_a = math.radians(lat_a)
    phi_b = math.radians(lat_b)
    d_phi = math.radians(lat_b - lat_a)
    d_lambda = math.radians(lon_b - lon_a)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi_a) * math.cos(phi_b) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def clock(sec: int | None) -> str | None:
    if sec is None:
        return None
    minutes = sec // 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def station_name(group: dict[str, Any] | None) -> str:
    if not group:
        return "Unknown"
    names = group.get("names", {})
    return names.get("ja") or names.get("en") or group.get("primaryName") or group.get("id") or "Unknown"


def top_items(counter: Counter[str], labels: dict[str, str], limit: int = 30) -> list[dict[str, Any]]:
    return [
        {"id": key, "name": labels.get(key, key), "count": count}
        for key, count in counter.most_common(limit)
    ]


def build_audit() -> dict[str, Any]:
    bundle = load_json(BUNDLE_PATH)
    map_payload = load_json(MAP_PATH)
    train_payload = load_json(UNIFIED_TRAINS_PATH)
    trains = train_payload.get("trains", [])
    station_alias_index = build_station_alias_index(map_payload.get("visibleStations", []))

    groups_by_id = {item["id"]: item for item in bundle.get("stationGroups", [])}
    station_key_to_group: dict[str, str] = {}
    for station in bundle.get("physicalStations", []):
        for source_id in station.get("sourceStopIds", []):
            station_key_to_group[source_id] = station["stationGroupId"]
    for source_key, target_key in station_alias_index.items():
        if target_key in station_key_to_group:
            station_key_to_group[source_key] = station_key_to_group[target_key]

    label_by_group = {group_id: station_name(group) for group_id, group in groups_by_id.items()}
    route_by_id = {route["id"]: route for route in bundle.get("serviceRoutes", [])}

    train_stop_keys: Counter[str] = Counter()
    train_stop_display: dict[str, str] = {}
    train_departures_by_key: Counter[str] = Counter()
    trains_with_unmapped_stops = []
    route_ids_from_unified: Counter[str] = Counter()
    route_source_lines: dict[str, Counter[str]] = defaultdict(Counter)
    route_source_operators: dict[str, Counter[str]] = defaultdict(Counter)

    for train in trains:
        line = canonical_route_line(train)
        route_id = route_id_for(line, train.get("operator_id", "tokyo"))
        route_ids_from_unified[route_id] += 1
        route_source_lines[route_id][str(line or "")] += 1
        route_source_operators[route_id][str(train.get("operator_id") or "")] += 1
        unmapped = []
        for stop in train.get("stops", []):
            key = resolve_station_key(stop.get("station_key") or stop.get("station_name"), station_alias_index)
            if not key:
                continue
            train_stop_keys[key] += 1
            train_stop_display.setdefault(key, stop.get("station_name") or key)
            if stop.get("departure"):
                train_departures_by_key[key] += 1
            if key not in station_key_to_group:
                unmapped.append({
                    "station_key": key,
                    "station_name": stop.get("station_name"),
                    "sequence": stop.get("sequence"),
                })
        if unmapped:
            trains_with_unmapped_stops.append({
                "train_id": train.get("id"),
                "operator": train.get("operator"),
                "line": train.get("line"),
                "train_number": train.get("train_number"),
                "unmapped_stop_count": len(unmapped),
                "sample_unmapped_stops": unmapped[:8],
            })

    bundle_departures_by_group: Counter[str] = Counter()
    bundle_trip_stops_by_group: Counter[str] = Counter()
    route_station_sets: dict[str, set[str]] = defaultdict(set)
    route_stop_counts: dict[str, list[int]] = defaultdict(list)
    route_first_departures: dict[str, list[int]] = defaultdict(list)
    for trip in bundle.get("tripInstances", []):
        route_id = trip.get("routeId")
        stops = trip.get("stopTimes", [])
        route_stop_counts[route_id].append(len(stops))
        for stop in stops:
            group_id = stop.get("stationGroupId")
            if not group_id:
                continue
            route_station_sets[route_id].add(group_id)
            bundle_trip_stops_by_group[group_id] += 1
            if stop.get("departureTimeSec") is not None:
                bundle_departures_by_group[group_id] += 1
        if stops and stops[0].get("departureTimeSec") is not None:
            route_first_departures[route_id].append(stops[0]["departureTimeSec"])

    map_station_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for station in map_payload.get("visibleStations", []):
        key = resolve_station_key(station.get("name_ja") or station.get("name_en"), station_alias_index)
        if not key:
            continue
        map_station_groups[key].append(station)

    duplicate_map_names = []
    collapsed_duplicate_map_names = []
    for key, stations in map_station_groups.items():
        coords = [
            (item.get("lat"), item.get("lon"))
            for item in stations
            if isinstance(item.get("lat"), (int, float)) and isinstance(item.get("lon"), (int, float))
        ]
        if len(coords) <= 1:
            continue
        max_distance = 0.0
        for index, (lat_a, lon_a) in enumerate(coords):
            for lat_b, lon_b in coords[index + 1:]:
                max_distance = max(max_distance, distance_m(lat_a, lon_a, lat_b, lon_b))
        if max_distance < 50:
            continue
        group_id = station_key_to_group.get(key)
        physical_station_count = len(groups_by_id.get(group_id, {}).get("physicalStationIds", [])) if group_id else 0
        is_collapsed = physical_station_count < len(coords)
        duplicate_map_names.append({
            "station_key": key,
            "display_name": stations[0].get("name_ja") or stations[0].get("name_en") or key,
            "map_point_count": len(coords),
            "bundle_physical_station_count": physical_station_count,
            "physical_points_preserved": not is_collapsed,
            "max_distance_m": round(max_distance, 1),
            "train_stop_count": train_stop_keys.get(key, 0),
            "bundle_station_group_id": group_id,
            "sample_points": [
                {
                    "name_ja": item.get("name_ja"),
                    "name_en": item.get("name_en"),
                    "lat": item.get("lat"),
                    "lon": item.get("lon"),
                    "is_priority": bool(item.get("is_priority")),
                }
                for item in stations[:8]
            ],
        })
        if is_collapsed:
            collapsed_duplicate_map_names.append(duplicate_map_names[-1])
    duplicate_map_names.sort(key=lambda item: (-item["train_stop_count"], -item["max_distance_m"], item["station_key"]))
    collapsed_duplicate_map_names.sort(key=lambda item: (-item["train_stop_count"], -item["max_distance_m"], item["station_key"]))

    map_stations_without_trains = [
        {
            "station_key": key,
            "display_name": stations[0].get("name_ja") or stations[0].get("name_en") or key,
            "map_point_count": len(stations),
        }
        for key, stations in map_station_groups.items()
        if key not in train_stop_keys
    ]
    map_stations_without_trains.sort(key=lambda item: (item["display_name"], item["station_key"]))

    train_stations_without_map = [
        {
            "station_key": key,
            "display_name": train_stop_display.get(key, key),
            "train_stop_count": count,
            "departure_count": train_departures_by_key.get(key, 0),
        }
        for key, count in train_stop_keys.items()
        if key not in station_key_to_group
    ]
    train_stations_without_map.sort(key=lambda item: (-item["train_stop_count"], item["station_key"]))

    route_stats = []
    for route_id, route in route_by_id.items():
        trip_count = route_ids_from_unified.get(route_id, 0)
        stop_lengths = route_stop_counts.get(route_id, [])
        station_count = len(route_station_sets.get(route_id, set()))
        route_stats.append({
            "route_id": route_id,
            "short_name": route.get("shortName"),
            "operator_id": route.get("operatorId"),
            "mode": route.get("mode"),
            "trip_count": trip_count,
            "station_count": station_count,
            "min_stop_count": min(stop_lengths) if stop_lengths else 0,
            "max_stop_count": max(stop_lengths) if stop_lengths else 0,
            "avg_stop_count": round(sum(stop_lengths) / len(stop_lengths), 2) if stop_lengths else 0,
            "first_departure": clock(min(route_first_departures[route_id])) if route_first_departures.get(route_id) else None,
            "last_departure": clock(max(route_first_departures[route_id])) if route_first_departures.get(route_id) else None,
            "source_lines": route_source_lines.get(route_id, Counter()).most_common(5),
            "source_operators": route_source_operators.get(route_id, Counter()).most_common(5),
        })

    route_stats_by_trip = sorted(route_stats, key=lambda item: (-item["trip_count"], item["short_name"] or ""))
    tiny_routes = [
        item for item in route_stats
        if item["station_count"] <= 1
        or item["max_stop_count"] <= 1
        or (item["trip_count"] <= 3 and item["station_count"] <= 8)
    ]
    tiny_routes.sort(key=lambda item: (item["trip_count"], item["station_count"], item["short_name"] or ""))
    huge_routes = [
        item for item in route_stats
        if item["station_count"] >= 80 or item["trip_count"] >= 1000 or item["max_stop_count"] >= 80
    ]
    huge_routes.sort(key=lambda item: (-item["station_count"], -item["trip_count"], item["short_name"] or ""))

    operator_route_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for item in route_stats:
        operator_route_counts[str(item.get("operator_id") or "unknown")]["routes"] += 1
        operator_route_counts[str(item.get("operator_id") or "unknown")]["trips"] += item["trip_count"]
        if item in tiny_routes:
            operator_route_counts[str(item.get("operator_id") or "unknown")]["tiny_routes"] += 1
    operator_quality = [
        {
            "operator_id": operator_id,
            "route_count": counts["routes"],
            "trip_count": counts["trips"],
            "tiny_route_count": counts["tiny_routes"],
        }
        for operator_id, counts in operator_route_counts.items()
    ]
    operator_quality.sort(key=lambda item: (-item["route_count"], item["operator_id"]))

    central_station_checks = []
    for name in CENTRAL_STATION_NAMES:
        key = normalize_key(name)
        group_id = station_key_to_group.get(key)
        central_station_checks.append({
            "station_key": key,
            "display_name": name,
            "has_map_point": key in map_station_groups,
            "map_point_count": len(map_station_groups.get(key, [])),
            "bundle_station_group_id": group_id,
            "bundle_name": label_by_group.get(group_id) if group_id else None,
            "source_departure_count": train_departures_by_key.get(key, 0),
            "bundle_departure_count": bundle_departures_by_group.get(group_id, 0) if group_id else 0,
        })

    priority_findings = []
    if train_stations_without_map:
        priority_findings.append({
            "severity": "high",
            "code": "train_stations_without_map",
            "count": len(train_stations_without_map),
            "summary": "Some real timetable station keys do not map into the v3 visible station/group layer.",
            "sample": train_stations_without_map[:10],
        })
    if collapsed_duplicate_map_names:
        priority_findings.append({
            "severity": "high",
            "code": "duplicate_map_names_collapsed_by_key",
            "count": len(collapsed_duplicate_map_names),
            "summary": "Some same-name map points are physically distinct but are not preserved as separate physical stations in the bundle.",
            "sample": collapsed_duplicate_map_names[:10],
        })
    if tiny_routes:
        priority_findings.append({
            "severity": "medium",
            "code": "tiny_or_empty_routes",
            "count": len(tiny_routes),
            "summary": "Some route cards have very few trips or no usable station set and may be map-only fragments or route-id mismatches.",
            "sample": tiny_routes[:10],
        })
    if huge_routes:
        priority_findings.append({
            "severity": "medium",
            "code": "huge_routes",
            "count": len(huge_routes),
            "summary": "Some routes are very broad and should be checked for over-merging or through-service scope.",
            "sample": huge_routes[:10],
        })

    return {
        "id": "v3_tokyo_bundle_audit_v0_1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "inputs": {
            "bundle": str(BUNDLE_PATH.relative_to(ROOT)),
            "map": str(MAP_PATH.relative_to(ROOT)),
            "unified_trains": str(UNIFIED_TRAINS_PATH.relative_to(ROOT)),
        },
        "summary": {
            "bundle_station_group_count": len(bundle.get("stationGroups", [])),
            "bundle_physical_station_count": len(bundle.get("physicalStations", [])),
            "bundle_route_count": len(bundle.get("serviceRoutes", [])),
            "bundle_trip_count": len(bundle.get("tripInstances", [])),
            "unified_train_count": len(trains),
            "map_visible_station_key_count": len(map_station_groups),
            "map_visible_station_point_count": len(map_payload.get("visibleStations", [])),
            "train_station_key_count": len(train_stop_keys),
            "train_stations_without_map_count": len(train_stations_without_map),
            "map_stations_without_trains_count": len(map_stations_without_trains),
            "duplicate_map_name_count": len(duplicate_map_names),
            "collapsed_duplicate_map_name_count": len(collapsed_duplicate_map_names),
            "tiny_route_count": len(tiny_routes),
            "huge_route_count": len(huge_routes),
            "trains_with_unmapped_stops_count": len(trains_with_unmapped_stops),
        },
        "priority_findings": priority_findings,
        "station_quality": {
            "top_departure_station_groups": top_items(bundle_departures_by_group, label_by_group, 40),
            "central_station_checks": central_station_checks,
            "train_stations_without_map": train_stations_without_map[:200],
            "map_stations_without_trains": map_stations_without_trains[:200],
            "duplicate_map_names": duplicate_map_names[:200],
            "collapsed_duplicate_map_names": collapsed_duplicate_map_names[:200],
            "trains_with_unmapped_stops": trains_with_unmapped_stops[:100],
        },
        "route_quality": {
            "top_routes_by_trip_count": route_stats_by_trip[:80],
            "tiny_or_empty_routes": tiny_routes[:200],
            "huge_routes": huge_routes[:80],
        },
        "operator_quality": operator_quality,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit generated v3 Tokyo bundle station/route integrity.")
    parser.add_argument("--output", type=Path, default=REPORT_PATH, help="Path for the component JSON report.")
    args = parser.parse_args()

    report = build_audit()
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    write_json(output_path, report)
    print(json.dumps({
        "report": str(output_path.relative_to(ROOT)) if output_path.is_relative_to(ROOT) else str(output_path),
        **report["summary"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
