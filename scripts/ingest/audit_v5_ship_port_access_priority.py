#!/usr/bin/env python3
"""Prioritize V5 ship ports that lack 2 km rail/bus/airport access."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORT_CONNECTORS = ROOT / "data" / "v5_port_connectors.json"
DEFAULT_PORT_CONNECTOR_AUDIT = ROOT / "data" / "v5_port_connector_audit.json"
DEFAULT_BUS_BUNDLE = ROOT / "data" / "v5_bus_gtfs_current_bundle.json.gz"
DEFAULT_MAP_BUNDLE = ROOT / "data" / "v4_gameplay_map_bundle.json.gz"
DEFAULT_SHIP_MAP = ROOT / "docs" / "data" / "v5_ship_map.geojson"
DEFAULT_SHIP_TIMETABLE = ROOT / "docs" / "data" / "v5_ship_timetable_current_bundle.json"
DEFAULT_OUTPUT = ROOT / "data" / "v5_ship_port_access_priority_audit.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_ship_port_access_priority_audit.json"
EARTH_RADIUS_METERS = 6_371_008.8


MAJOR_LAND_BOUNDS = [
    # These are intentionally broad gameplay triage bounds, not legal island
    # definitions. They catch ports where real public access should usually be
    # collected instead of treating the port as a remote-island exception.
    ("honshu_mainland_band", 33.3, 41.6, 130.5, 142.2),
    ("hokkaido_mainland_band", 41.2, 45.8, 139.2, 146.0),
    ("kyushu_mainland_band", 30.8, 34.0, 129.2, 132.2),
    ("shikoku_mainland_band", 32.6, 34.8, 132.0, 134.9),
    ("okinawa_main_island_band", 26.0, 26.9, 127.5, 128.4),
    ("awaji_band", 34.1, 34.7, 134.6, 135.1),
    ("sado_band", 37.7, 38.4, 138.1, 138.6),
    ("amakusa_band", 32.1, 32.7, 129.8, 130.5),
]


REMOTE_ISLAND_NAME_HINTS = [
    "与路",
    "上五島",
    "下五島",
    "福江",
    "奈留",
    "久賀",
    "小値賀",
    "宇久",
    "中島",
    "睦月",
    "野忽那",
    "怒和",
    "津和地",
    "二神",
    "佐合島",
    "祝島",
    "粟島",
    "青島",
    "似島",
    "高島",
    "伊王島",
    "渡嘉敷",
    "座間味",
    "阿嘉",
    "粟国",
    "久米島",
    "渡名喜",
    "徳之島",
    "奄美",
    "加計呂麻",
    "請島",
    "与論",
    "利尻",
    "礼文",
    "奥尻",
    "隠岐",
    "父島",
    "母島",
    "八丈",
    "神津島",
    "三宅島",
    "新島",
    "式根島",
]
GENERIC_AMBIGUOUS_PORT_NAMES = {
    "大島港",
    "長崎港",
    "戸畑",
    "呼子",
    "佐伯",
    "明石",
    "笠岡",
    "久賀",
    "三津浜港",
    "平戸港",
    "土生",
    "青森港",
    "新潟港",
}
WEAK_COORDINATE_SCORE_MAX = 7


def read_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def haversine_meters(left: dict[str, float], right: dict[str, float]) -> float:
    lat1 = math.radians(left["lat"])
    lon1 = math.radians(left["lon"])
    lat2 = math.radians(right["lat"])
    lon2 = math.radians(right["lon"])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_METERS * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def nearest_node(point: dict[str, float], nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    best = None
    for node in nodes:
        distance = haversine_meters(point, node)
        if best is None or distance < best["distanceMeters"]:
            best = {**node, "distanceMeters": int(round(distance))}
    return best


def station_nodes(map_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for group in map_bundle.get("stationGroups") or []:
        centroid = group.get("centroid") or {}
        if not isinstance(centroid.get("lat"), (int, float)) or not isinstance(centroid.get("lon"), (int, float)):
            continue
        rows.append({
            "nodeId": group["id"],
            "name": group.get("primaryName") or (group.get("names") or {}).get("ja") or group["id"],
            "lat": float(centroid["lat"]),
            "lon": float(centroid["lon"]),
        })
    return rows


def bus_stop_nodes(bus_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for stop in bus_bundle.get("stops") or []:
        if stop.get("locationType") not in (0, None):
            continue
        if not isinstance(stop.get("lat"), (int, float)) or not isinstance(stop.get("lon"), (int, float)):
            continue
        rows.append({
            "nodeId": stop["busStopId"],
            "name": stop.get("name") or stop["busStopId"],
            "lat": float(stop["lat"]),
            "lon": float(stop["lon"]),
        })
    return rows


def land_band_for(point: dict[str, float]) -> str | None:
    lat = point["lat"]
    lon = point["lon"]
    for name, min_lat, max_lat, min_lon, max_lon in MAJOR_LAND_BOUNDS:
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return name
    return None


def has_remote_name_hint(port_name: str) -> bool:
    return any(hint in port_name for hint in REMOTE_ISLAND_NAME_HINTS)


def ship_usage(timetable: dict[str, Any]) -> dict[str, Any]:
    by_port: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sailing in timetable.get("sailings") or []:
        origin = sailing.get("originPort")
        destination = sailing.get("destinationPort")
        if origin:
            by_port[origin]["originSailings"] += 1
        if destination:
            by_port[destination]["destinationSailings"] += 1
        for port in [origin, destination]:
            if not port or len(examples[port]) >= 5:
                continue
            examples[port].append({
                "sailingId": sailing.get("sailingId"),
                "operator": sailing.get("operator"),
                "originPort": origin,
                "destinationPort": destination,
                "departureHhmm": sailing.get("departureHhmm"),
                "arrivalHhmm": sailing.get("arrivalHhmm"),
            })
    return {"counts": by_port, "examples": examples}


def ship_map_port_props(ship_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {}
    for feature in ship_map.get("features") or []:
        props = feature.get("properties") or {}
        if props.get("kind") != "port":
            continue
        name = props.get("name")
        if name:
            rows[str(name)] = props
    return rows


def operator_contexts(timetable: dict[str, Any]) -> dict[str, list[str]]:
    rows: dict[str, set[str]] = defaultdict(set)
    for sailing in timetable.get("sailings") or []:
        operator = str(sailing.get("operator") or "").strip()
        if not operator:
            continue
        for key in ("originPort", "destinationPort"):
            port = str(sailing.get(key) or "").strip()
            if port:
                rows[port].add(operator)
    return {port: sorted(values) for port, values in rows.items()}


def coordinate_identity_review(port_name: str, port_props: dict[str, Any], operators: list[str]) -> tuple[str, list[str]]:
    reasons = []
    source = str(port_props.get("coordinateSource") or "")
    display = str(port_props.get("coordinateDisplayName") or "")
    is_manual_verified = source.startswith("manual_verified:")
    score_match = re.search(r"\bscore=(\d+)\b", source)
    weak_source = (
        "needs_precise_port_review" in source
        and score_match is not None
        and int(score_match.group(1)) <= WEAK_COORDINATE_SCORE_MAX
    )
    if weak_source:
        reasons.append("coordinate source was a weak geocoder match and needs precise port review")
    if display and port_name not in display and not has_identity_token_overlap(port_name, display):
        reasons.append(f"coordinate display name does not contain port name: {display[:80]}")
    if port_name in GENERIC_AMBIGUOUS_PORT_NAMES and not is_manual_verified:
        reasons.append("generic/ambiguous port name; verify route/operator/region before adding connectors")
    if len(operators) >= 4:
        reasons.append(f"multiple operator contexts share this port name: {', '.join(operators[:5])}")
    if reasons:
        return "needs_port_identity_fix", reasons
    return "ok", []


def has_identity_token_overlap(port_name: str, display: str) -> bool:
    """Accept semantic terminal aliases such as 大島岡田港 -> 岡田港入口."""
    if not display:
        return False
    tokens = {port_name}
    for suffix in ("フェリーターミナル", "ターミナル", "港"):
        if port_name.endswith(suffix) and len(port_name) > len(suffix):
            tokens.add(port_name[: -len(suffix)])
    for token in ("青森", "岡田港"):
        if token in port_name:
            tokens.add(token)
    return any(len(token) >= 2 and token in display for token in tokens)


def classify_port(port_name: str, point: dict[str, float], nearest_rail: dict[str, Any] | None, nearest_bus: dict[str, Any] | None, sailings: int) -> tuple[str, list[str]]:
    reasons = []
    band = land_band_for(point)
    if band:
        reasons.append(f"inside {band}")
    if has_remote_name_hint(port_name):
        reasons.append("remote island name hint")
    rail_distance = nearest_rail["distanceMeters"] if nearest_rail else math.inf
    bus_distance = nearest_bus["distanceMeters"] if nearest_bus else math.inf
    if rail_distance <= 20_000:
        reasons.append(f"rail within {rail_distance}m")
    if bus_distance <= 10_000:
        reasons.append(f"bus stop within {bus_distance}m")
    if sailings:
        reasons.append(f"used by {sailings} playable sailings")

    if sailings and (band or rail_distance <= 20_000 or bus_distance <= 10_000):
        return "collect_real_connector_high_priority", reasons
    if band or rail_distance <= 20_000 or bus_distance <= 10_000:
        return "collect_real_connector", reasons
    return "record_remote_or_small_island", reasons


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port-connectors", type=Path, default=DEFAULT_PORT_CONNECTORS)
    parser.add_argument("--port-connector-audit", type=Path, default=DEFAULT_PORT_CONNECTOR_AUDIT)
    parser.add_argument("--bus-bundle", type=Path, default=DEFAULT_BUS_BUNDLE)
    parser.add_argument("--map-bundle", type=Path, default=DEFAULT_MAP_BUNDLE)
    parser.add_argument("--ship-map", type=Path, default=DEFAULT_SHIP_MAP)
    parser.add_argument("--ship-timetable", type=Path, default=DEFAULT_SHIP_TIMETABLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    args = parser.parse_args()

    port_connectors = read_json(args.port_connectors)
    connector_audit = read_json(args.port_connector_audit)
    bus_bundle = read_json(args.bus_bundle)
    map_bundle = read_json(args.map_bundle)
    ship_map = read_json(args.ship_map)
    timetable = read_json(args.ship_timetable)
    rail_nodes = station_nodes(map_bundle)
    bus_nodes = bus_stop_nodes(bus_bundle)
    usage = ship_usage(timetable)
    port_props_by_name = ship_map_port_props(ship_map)
    operators_by_port = operator_contexts(timetable)
    rows = []
    for item in connector_audit.get("portsWithoutAnyAccess") or []:
        port_name = item["portName"]
        coordinate = item["coordinate"]
        point = {"lat": float(coordinate["lat"]), "lon": float(coordinate["lon"])}
        nearest_rail = nearest_node(point, rail_nodes)
        nearest_bus = nearest_node(point, bus_nodes)
        counts = usage["counts"].get(port_name, Counter())
        sailing_count = int(counts.get("originSailings", 0) + counts.get("destinationSailings", 0))
        category, reasons = classify_port(port_name, point, nearest_rail, nearest_bus, sailing_count)
        port_props = port_props_by_name.get(port_name, {})
        operators = operators_by_port.get(port_name, [])
        identity_status, identity_reasons = coordinate_identity_review(port_name, port_props, operators)
        if identity_status == "needs_port_identity_fix" and sailing_count:
            category = "resolve_port_identity_first"
            reasons = identity_reasons + reasons
        rows.append({
            "portName": port_name,
            "coordinate": coordinate,
            "category": category,
            "reasons": reasons,
            "coordinateIdentityStatus": identity_status,
            "coordinateIdentityReasons": identity_reasons,
            "coordinateSource": port_props.get("coordinateSource"),
            "coordinateDisplayName": port_props.get("coordinateDisplayName"),
            "operatorContexts": operators,
            "playableSailingCount": sailing_count,
            "originSailingCount": int(counts.get("originSailings", 0)),
            "destinationSailingCount": int(counts.get("destinationSailings", 0)),
            "nearestRail": None if not nearest_rail else {
                "stationGroupId": nearest_rail["nodeId"],
                "name": nearest_rail["name"],
                "distanceMeters": nearest_rail["distanceMeters"],
            },
            "nearestBusStop": None if not nearest_bus else {
                "busStopId": nearest_bus["nodeId"],
                "name": nearest_bus["name"],
                "distanceMeters": nearest_bus["distanceMeters"],
            },
            "sampleSailings": usage["examples"].get(port_name, []),
            "searchQueries": [
                f"{port_name} 港 アクセス バス 時刻表",
                f"{port_name} フェリーターミナル 最寄り バス停",
                f"{port_name} 連絡バス 公式",
            ],
        })

    priority_order = {
        "resolve_port_identity_first": 0,
        "collect_real_connector_high_priority": 1,
        "collect_real_connector": 2,
        "record_remote_or_small_island": 3,
    }
    rows.sort(key=lambda row: (
        priority_order.get(row["category"], 9),
        -row["playableSailingCount"],
        row["nearestBusStop"]["distanceMeters"] if row["nearestBusStop"] else 10**9,
        row["nearestRail"]["distanceMeters"] if row["nearestRail"] else 10**9,
        row["portName"],
    ))
    counts = Counter(row["category"] for row in rows)
    generated_at = datetime.now(UTC).isoformat()
    payload = {
        "schemaVersion": "v5_ship_port_access_priority_audit_v1",
        "generatedAt": generated_at,
        "inputConnectorModel": port_connectors.get("modelVersion"),
        "inputConnectorMaxMeters": port_connectors.get("maxConnectorMeters"),
        "summary": {
            "portsWithout2kmAccess": len(rows),
            "resolvePortIdentityFirst": counts.get("resolve_port_identity_first", 0),
            "collectRealConnectorHighPriority": counts.get("collect_real_connector_high_priority", 0),
            "collectRealConnector": counts.get("collect_real_connector", 0),
            "recordRemoteOrSmallIsland": counts.get("record_remote_or_small_island", 0),
            "playableAffectedPortCount": sum(1 for row in rows if row["playableSailingCount"] > 0),
        },
        "rules": {
            "portAccessPlayableRadiusMeters": port_connectors.get("maxConnectorMeters"),
            "highPriority": "No 2km connector, used by playable ship sailings, and likely on major land or near rail/bus source coverage.",
            "resolvePortIdentityFirst": "No connector, but current port coordinate is suspicious or the port name is ambiguous. Fix the port identity before collecting access connectors.",
            "collectRealConnector": "No 2km connector but likely mainland/major-island or has rail/bus source coverage nearby; collect official port bus/access data.",
            "recordRemoteOrSmallIsland": "No nearby rail/bus source coverage and remote-island hints; record as island access gap until local island bus data is intentionally collected.",
        },
        "ports": rows,
    }
    write_json(args.output, payload)
    write_json(args.docs_output, payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(json.dumps(rows[:20], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
