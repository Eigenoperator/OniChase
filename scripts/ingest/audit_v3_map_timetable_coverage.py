#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_v3_tokyo_v2_bundle import ROUTE_COLOR_ALIASES, operator_id_for, route_id_for
from v3_station_identity import canonical_group_key, canonical_station_key, normalize_key, resolve_station_key


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

MAP_BUNDLE_PATH = DATA_DIR / "v3_tokyo_map_bundle.json.gz"
TIMETABLE_BUNDLE_PATH = DATA_DIR / "v3_tokyo_timetable_bundle.json.gz"
UNIFIED_TRAINS_PATH = DATA_DIR / "v3_trains_unified.json.gz"
SERVICE_VIEWS_PATH = DATA_DIR / "v3_tokyo_phase1_service_views.json"
OUTPUT_PATH = DATA_DIR / "v3_map_timetable_coverage_audit.json"

NON_REGULAR_ZERO_STATIONS = {
    "偕楽園": "seasonal Joban Line stop with no regular weekday service in the current source timetable",
    "鹿島サッカースタジアム": "seasonal/event stop with no regular weekday service in the current source timetable",
    "鹿島サッカースタジアム（臨）": "seasonal/event stop with no regular weekday service in the current source timetable",
}

EQUIVALENT_TRAIN_LINES = {
    ("jr_central", "東海道新幹線"): {("shinkansen", "SHINKANSEN_TOKAIDO_SANYO")},
    ("jr_west", "山陽新幹線"): {("shinkansen", "SHINKANSEN_TOKAIDO_SANYO")},
    ("jr_east", "上越新幹線"): {("shinkansen", "SHINKANSEN_JOETSU")},
    ("jr_east", "北陸新幹線"): {("shinkansen", "SHINKANSEN_HOKURIKU")},
    ("jr_west", "北陸新幹線"): {("shinkansen", "SHINKANSEN_HOKURIKU")},
    ("jr_east", "東北新幹線"): {("shinkansen", "SHINKANSEN_TOHOKU_HOKKAIDO")},
    ("jr_hokkaido", "北海道新幹線"): {("shinkansen", "SHINKANSEN_TOHOKU_HOKKAIDO")},
    ("jr_kyushu", "九州新幹線"): {("shinkansen", "SHINKANSEN_KYUSHU")},
    ("jr_kyushu", "西九州新幹線"): {("shinkansen", "SHINKANSEN_NISHI_KYUSHU")},
    ("jr_east", "伊東線"): {("jr_east", "JR_EAST_TOKAIDO")},
    ("jr_east", "東金線"): {("jr_east", "JR_SOTOBO"), ("jr_east", "JR_EAST_KEIYO_MUSASHINO")},
    ("jr_east", "武蔵野線"): {("jr_east", "JR_EAST_KEIYO_MUSASHINO")},
    ("jr_east", "赤羽線"): {("jr_east", "JR_EAST_SAIKYO_KAWAGOE")},
    ("jr_east", "高崎線"): {
        ("jr_east", "JR_EAST_TOKAIDO"),
        ("jr_east", "JR_EAST_UENO_TOKYO"),
        ("jr_east", "JR_EAST_SHONAN_SHINJUKU"),
    },
    ("saitama_railway", "埼玉高速鉄道線"): {
        ("tokyo_metro", "7号線南北線"),
        ("saitama_railway", "埼玉高速鉄道線"),
    },
}


def load_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def route_aliases_for(line_name: str, operator_id: str) -> set[str]:
    aliases = {line_name}
    if operator_id == "jr_east":
        aliases.update(
            {
                f"JR_{line_name}",
                f"JR_EAST_{line_name}",
                line_name.replace("線", ""),
            }
        )
    return {alias for alias in aliases if alias}


def build_group_lookup(map_bundle: dict[str, Any]) -> dict[str, set[str]]:
    lookup: dict[str, set[str]] = defaultdict(set)
    for station in map_bundle.get("physicalStations", []):
        group_id = station.get("stationGroupId")
        if not group_id:
            continue
        names = [
            station.get("name"),
            station.get("names", {}).get("ja"),
            station.get("names", {}).get("en"),
            *(station.get("sourceStopIds") or []),
        ]
        for name in names:
            key = normalize_key(name)
            if key:
                lookup[key].add(group_id)
            station_key = canonical_station_key(name)
            if station_key:
                lookup[station_key].add(group_id)
            group_key = canonical_group_key(name)
            if group_key:
                lookup[group_key].add(group_id)
    return lookup


def group_ids_for_station(name: Any, group_lookup: dict[str, set[str]]) -> set[str]:
    raw_key = normalize_key(name)
    keys = {
        raw_key,
        canonical_station_key(name),
        canonical_group_key(name),
        resolve_station_key(name, {key: key for key in group_lookup}),
    }
    result: set[str] = set()
    for key in keys:
        result.update(group_lookup.get(key, set()))
    return result


def collect_timetable_counts(timetable_bundle: dict[str, Any]) -> tuple[Counter[str], Counter[str], Counter[tuple[str, str]]]:
    route_trip_counts: Counter[str] = Counter()
    group_stop_counts: Counter[str] = Counter()
    route_group_stop_counts: Counter[tuple[str, str]] = Counter()
    for trip in timetable_bundle.get("tripInstances", []):
        route_id = str(trip.get("routeId") or "")
        if route_id:
            route_trip_counts[route_id] += 1
        seen_groups_for_trip: set[str] = set()
        for stop in trip.get("stopTimes", []):
            group_id = stop.get("stationGroupId")
            if not group_id:
                continue
            group_stop_counts[group_id] += 1
            if route_id:
                route_group_stop_counts[(route_id, group_id)] += 1
            seen_groups_for_trip.add(group_id)
    return route_trip_counts, group_stop_counts, route_group_stop_counts


def collect_unified_train_counts(unified: dict[str, Any]) -> tuple[Counter[tuple[str, str]], Counter[tuple[str, str, str]]]:
    line_train_counts: Counter[tuple[str, str]] = Counter()
    line_station_counts: Counter[tuple[str, str, str]] = Counter()
    for train in unified.get("trains", []):
        operator_id = str(train.get("operator_id") or "")
        line = str(train.get("line") or "")
        if operator_id and line:
            line_train_counts[(operator_id, line)] += 1
        for stop in train.get("stops", []):
            stop_line = str(stop.get("line") or line or "")
            station_key = str(stop.get("station_key") or "")
            if operator_id and stop_line and station_key:
                line_station_counts[(operator_id, stop_line, station_key)] += 1
    return line_train_counts, line_station_counts


def train_line_keys_for(operator_id: str, line_name: str) -> set[tuple[str, str]]:
    keys = {(operator_id, line_name)}
    for line_id, mapped_name in ROUTE_COLOR_ALIASES.items():
        if mapped_name == line_name:
            keys.add((operator_id, line_id))
    if operator_id == "jr_east":
        keys.add((operator_id, f"JR_{line_name}"))
        keys.add((operator_id, f"JR_EAST_{line_name}"))
    keys.update(EQUIVALENT_TRAIN_LINES.get((operator_id, line_name), set()))
    return {(op, key) for op, key in keys if op and key}


def collect_visible_line_stations(
    service_views: dict[str, Any],
    group_lookup: dict[str, set[str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    lines: dict[tuple[str, str], dict[str, Any]] = {}

    track_counts: Counter[tuple[str, str]] = Counter()
    for line in service_views.get("physicalLines", []):
        operator_id = operator_id_for(line.get("operator_ja"))
        line_name = str(line.get("line_name_ja") or "")
        if not line_name:
            continue
        track_counts[(operator_id, line_name)] += 1
        entry = lines.setdefault(
            (operator_id, line_name),
            {
                "operator_id": operator_id,
                "operator_ja": line.get("operator_ja"),
                "line_name_ja": line_name,
                "physical_segment_count": 0,
                "stations": {},
            },
        )
        entry["physical_segment_count"] = track_counts[(operator_id, line_name)]

    for station in service_views.get("visibleStations", []):
        operator_id = operator_id_for(station.get("operator_ja"))
        line_name = str(station.get("line_name_ja") or "")
        station_name = str(station.get("name_ja") or "")
        if not line_name or not station_name:
            continue
        entry = lines.setdefault(
            (operator_id, line_name),
            {
                "operator_id": operator_id,
                "operator_ja": station.get("operator_ja"),
                "line_name_ja": line_name,
                "physical_segment_count": track_counts[(operator_id, line_name)],
                "stations": {},
            },
        )
        station_key = canonical_station_key(station_name)
        station_entry = entry["stations"].setdefault(
            station_key,
            {
                "name_ja": station_name,
                "station_key": station_key,
                "group_ids": sorted(group_ids_for_station(station_name, group_lookup)),
                "is_priority": bool(station.get("is_priority")),
            },
        )
        if not station_entry.get("group_ids"):
            station_entry["group_ids"] = sorted(group_ids_for_station(station_name, group_lookup))

    return lines


def build_route_lookup(map_bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(route.get("id")): route for route in map_bundle.get("serviceRoutes", [])}


def matching_service_routes(
    operator_id: str,
    line_name: str,
    service_routes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    exact_id = route_id_for(line_name, operator_id)
    matches: list[dict[str, Any]] = []
    if exact_id in service_routes:
        matches.append(service_routes[exact_id])
    aliases = route_aliases_for(line_name, operator_id)
    for route in service_routes.values():
        if route.get("operatorId") != operator_id:
            continue
        short_name = str(route.get("shortName") or "")
        if short_name in aliases or line_name in short_name:
            if route not in matches:
                matches.append(route)
    return matches


def line_report(
    entry: dict[str, Any],
    service_routes: dict[str, dict[str, Any]],
    route_trip_counts: Counter[str],
    group_stop_counts: Counter[str],
    line_train_counts: Counter[tuple[str, str]],
    line_station_counts: Counter[tuple[str, str, str]],
) -> dict[str, Any]:
    operator_id = entry["operator_id"]
    line_name = entry["line_name_ja"]
    stations = list(entry["stations"].values())
    route_matches = matching_service_routes(operator_id, line_name, service_routes)
    exact_route_id = route_id_for(line_name, operator_id)
    route_trip_total = sum(route_trip_counts.get(route["id"], 0) for route in route_matches)
    train_line_keys = train_line_keys_for(operator_id, line_name)
    exact_train_count = sum(line_train_counts.get((line_operator_id, line_key), 0) for line_operator_id, line_key in train_line_keys)
    route_ids = [route["id"] for route in route_matches]

    zero_stations = []
    non_regular_zero_stations = []
    unresolved_stations = []
    station_reports = []
    exact_line_station_stop_count = 0
    for station in sorted(stations, key=lambda item: item["name_ja"]):
        group_ids = station.get("group_ids") or []
        stop_count = sum(group_stop_counts.get(group_id, 0) for group_id in group_ids)
        line_specific_count = sum(
            line_station_counts.get((line_operator_id, line_key, station["station_key"]), 0)
            for line_operator_id, line_key in train_line_keys
        )
        exact_line_station_stop_count += line_specific_count
        station_item = {
            "name_ja": station["name_ja"],
            "station_key": station["station_key"],
            "group_ids": group_ids,
            "timetable_stop_count": stop_count,
            "line_specific_stop_count": line_specific_count,
        }
        non_regular_reason = NON_REGULAR_ZERO_STATIONS.get(station["name_ja"])
        if non_regular_reason:
            station_item["non_regular_service_reason"] = non_regular_reason
        station_reports.append(station_item)
        if not group_ids:
            unresolved_stations.append(station_item)
        if stop_count == 0:
            if non_regular_reason:
                non_regular_zero_stations.append(station_item)
            else:
                zero_stations.append(station_item)

    station_count = len(station_reports)
    zero_count = len(zero_stations)
    unresolved_count = len(unresolved_stations)
    has_rendered_geometry = int(entry.get("physical_segment_count") or 0) > 0
    coverage_ratio = None if station_count == 0 else round((station_count - zero_count) / station_count, 4)

    return {
        "operator_id": operator_id,
        "operator_ja": entry.get("operator_ja"),
        "line_name_ja": line_name,
        "exact_route_id": exact_route_id,
        "matched_route_ids": route_ids,
        "matched_route_trip_count": route_trip_total,
        "exact_line_train_count": exact_train_count,
        "exact_line_station_stop_count": exact_line_station_stop_count,
        "physical_segment_count": int(entry.get("physical_segment_count") or 0),
        "has_rendered_geometry": has_rendered_geometry,
        "station_count": station_count,
        "station_coverage_ratio": coverage_ratio,
        "zero_stop_station_count": zero_count,
        "non_regular_zero_station_count": len(non_regular_zero_stations),
        "unresolved_station_count": unresolved_count,
        "zero_stop_station_samples": zero_stations[:25],
        "non_regular_zero_station_samples": non_regular_zero_stations[:25],
        "unresolved_station_samples": unresolved_stations[:25],
        "stations": station_reports,
    }


def build_audit() -> dict[str, Any]:
    map_bundle = load_json(MAP_BUNDLE_PATH)
    timetable_bundle = load_json(TIMETABLE_BUNDLE_PATH)
    unified = load_json(UNIFIED_TRAINS_PATH)
    service_views = load_json(SERVICE_VIEWS_PATH)

    group_lookup = build_group_lookup(map_bundle)
    route_trip_counts, group_stop_counts, _route_group_stop_counts = collect_timetable_counts(timetable_bundle)
    line_train_counts, line_station_counts = collect_unified_train_counts(unified)
    service_routes = build_route_lookup(map_bundle)
    visible_lines = collect_visible_line_stations(service_views, group_lookup)

    reports = [
        line_report(
            entry,
            service_routes,
            route_trip_counts,
            group_stop_counts,
            line_train_counts,
            line_station_counts,
        )
        for entry in visible_lines.values()
    ]
    reports.sort(
        key=lambda item: (
            -item["zero_stop_station_count"],
            item["operator_id"],
            item["line_name_ja"],
        )
    )

    missing_or_suspicious = [
        report
        for report in reports
        if report["zero_stop_station_count"]
        or report["unresolved_station_count"]
        or (
            report["station_count"]
            and report["matched_route_trip_count"] == 0
            and report["exact_line_train_count"] == 0
            and report["exact_line_station_stop_count"] == 0
        )
    ]

    rendered_station_total = sum(report["station_count"] for report in reports)
    zero_stop_station_total = sum(report["zero_stop_station_count"] for report in reports)
    non_regular_zero_station_total = sum(report["non_regular_zero_station_count"] for report in reports)
    rendered_line_without_trips = [
        {
            "operator_id": report["operator_id"],
            "line_name_ja": report["line_name_ja"],
            "station_count": report["station_count"],
            "physical_segment_count": report["physical_segment_count"],
        }
        for report in reports
        if report["has_rendered_geometry"]
        and report["station_count"]
        and report["matched_route_trip_count"] == 0
        and report["exact_line_train_count"] == 0
        and report["exact_line_station_stop_count"] == 0
    ]

    return {
        "id": "v3_map_timetable_coverage_audit_v0_1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "inputs": {
            "map_bundle": str(MAP_BUNDLE_PATH.relative_to(ROOT)),
            "timetable_bundle": str(TIMETABLE_BUNDLE_PATH.relative_to(ROOT)),
            "unified_trains": str(UNIFIED_TRAINS_PATH.relative_to(ROOT)),
            "service_views": str(SERVICE_VIEWS_PATH.relative_to(ROOT)),
        },
        "summary": {
            "physical_station_count": len(map_bundle.get("physicalStations", [])),
            "station_group_count": len(map_bundle.get("stationGroups", [])),
            "track_centerline_count": len(map_bundle.get("trackCenterlines", [])),
            "rendered_line_count": len(reports),
            "service_route_count": len(service_routes),
            "trip_instance_count": len(timetable_bundle.get("tripInstances", [])),
            "unified_train_count": len(unified.get("trains", [])),
            "rendered_station_membership_count": rendered_station_total,
            "zero_stop_station_membership_count": zero_stop_station_total,
            "non_regular_zero_station_membership_count": non_regular_zero_station_total,
            "rendered_line_without_trip_count": len(rendered_line_without_trips),
        },
        "rendered_lines_without_trips": rendered_line_without_trips,
        "missing_or_suspicious_lines": missing_or_suspicious,
        "line_reports": reports,
    }


def main() -> int:
    audit = build_audit()
    write_json(OUTPUT_PATH, audit)
    print(json.dumps(audit["summary"], ensure_ascii=False, indent=2))
    print(f"Wrote: {OUTPUT_PATH}")
    if audit["rendered_lines_without_trips"]:
        print("Rendered lines without exact timetable trips:")
        for item in audit["rendered_lines_without_trips"][:30]:
            print(f"- {item['operator_id']} / {item['line_name_ja']} ({item['station_count']} stations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
