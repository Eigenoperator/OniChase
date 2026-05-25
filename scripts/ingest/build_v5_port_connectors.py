#!/usr/bin/env python3
"""Build V5 ferry-port walking connectors to rail, bus, and airport nodes."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUS_BUNDLE = ROOT / "data" / "v5_bus_gtfs_current_bundle.json.gz"
DEFAULT_MAP_BUNDLE = ROOT / "data" / "v4_gameplay_map_bundle.json.gz"
DEFAULT_AIRPORT_MAP = ROOT / "docs" / "data" / "v5_flight_map.geojson"
DEFAULT_SHIP_MAP = ROOT / "docs" / "data" / "v5_ship_map.geojson"
DEFAULT_OUTPUT = ROOT / "data" / "v5_port_connectors.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_port_connectors.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_port_connector_audit.json"
DEFAULT_DOCS_AUDIT_OUTPUT = ROOT / "docs" / "data" / "v5_port_connector_audit.json"
EARTH_RADIUS_METERS = 6_371_008.8


def read_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_if_needed(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dst.resolve():
        shutil.copyfile(src, dst)


def haversine_meters(left: dict[str, float], right: dict[str, float]) -> float:
    lat1 = math.radians(left["lat"])
    lon1 = math.radians(left["lon"])
    lat2 = math.radians(right["lat"])
    lon2 = math.radians(right["lon"])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_METERS * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def build_grid(nodes: list[dict[str, Any]], cell_degrees: float) -> dict[tuple[int, int], list[int]]:
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, node in enumerate(nodes):
        grid[(math.floor(node["lat"] / cell_degrees), math.floor(node["lon"] / cell_degrees))].append(index)
    return grid


def nearby_nodes(
    node: dict[str, Any],
    candidates: list[dict[str, Any]],
    grid: dict[tuple[int, int], list[int]],
    *,
    max_distance_meters: int,
    cell_degrees: float,
) -> list[dict[str, Any]]:
    radius_cells = max(1, math.ceil((max_distance_meters / 111_320) / cell_degrees) + 1)
    lat_cell = math.floor(node["lat"] / cell_degrees)
    lon_cell = math.floor(node["lon"] / cell_degrees)
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for dlat in range(-radius_cells, radius_cells + 1):
        for dlon in range(-radius_cells, radius_cells + 1):
            for index in grid.get((lat_cell + dlat, lon_cell + dlon), []):
                candidate = candidates[index]
                candidate_id = str(candidate["id"])
                if candidate_id in seen:
                    continue
                seen.add(candidate_id)
                distance = haversine_meters(node, candidate)
                if distance <= max_distance_meters:
                    matches.append(candidate | {"distanceMeters": int(round(distance))})
    return sorted(matches, key=lambda item: (item["distanceMeters"], item["name"], item["id"]))


def station_nodes(map_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = []
    for group in map_bundle.get("stationGroups") or []:
        centroid = group.get("centroid") or {}
        lat = centroid.get("lat")
        lon = centroid.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        nodes.append({
            "id": group["id"],
            "mode": "rail_station_group",
            "name": group.get("primaryName") or (group.get("names") or {}).get("ja") or group["id"],
            "lat": float(lat),
            "lon": float(lon),
        })
    return nodes


def bus_stop_nodes(bus_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = []
    for stop in bus_bundle.get("stops") or []:
        lat = stop.get("lat")
        lon = stop.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        if stop.get("locationType") not in (0, None):
            continue
        nodes.append({
            "id": stop["busStopId"],
            "mode": "bus_stop",
            "name": stop.get("name") or stop["busStopId"],
            "lat": float(lat),
            "lon": float(lon),
        })
    return nodes


def airport_nodes(airport_map: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = []
    for feature in airport_map.get("features") or []:
        props = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        if props.get("kind") != "airport" or len(coords) < 2:
            continue
        iata = props.get("iata")
        if not iata:
            continue
        nodes.append({
            "id": f"airport:{iata}",
            "iata": iata,
            "mode": "airport",
            "name": f"{iata} · {props.get('municipality') or props.get('name') or iata}",
            "lat": float(coords[1]),
            "lon": float(coords[0]),
        })
    return nodes


def port_nodes(ship_map: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = []
    for feature in ship_map.get("features") or []:
        props = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        if props.get("kind") != "port" or len(coords) < 2:
            continue
        name = props.get("name")
        if not name:
            continue
        nodes.append({
            "id": f"port:{name}",
            "mode": "port",
            "name": name,
            "lat": float(coords[1]),
            "lon": float(coords[0]),
            "coordinateSource": props.get("coordinateSource") or "",
        })
    return nodes


def compact_access(match: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "nodeId": match["id"],
        "mode": match["mode"],
        "name": match["name"],
        "coordinate": {"lat": match["lat"], "lon": match["lon"]},
        "distanceMeters": match["distanceMeters"],
    }
    if match.get("iata"):
        payload["iata"] = match["iata"]
    return payload


def build_port_access(
    ports: list[dict[str, Any]],
    *,
    rail_nodes: list[dict[str, Any]],
    bus_nodes: list[dict[str, Any]],
    airport_nodes_: list[dict[str, Any]],
    max_distance_meters: int,
    max_rail_per_port: int,
    max_bus_per_port: int,
    max_airport_per_port: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    rail_grid = build_grid(rail_nodes, 0.05)
    bus_grid = build_grid(bus_nodes, 0.05)
    airport_grid = build_grid(airport_nodes_, 0.05)
    by_port: dict[str, Any] = {}
    bus_to_port_connectors: list[dict[str, Any]] = []
    coverage = Counter()
    for port in ports:
        rail_matches = nearby_nodes(port, rail_nodes, rail_grid, max_distance_meters=max_distance_meters, cell_degrees=0.05)[:max_rail_per_port]
        bus_matches = nearby_nodes(port, bus_nodes, bus_grid, max_distance_meters=max_distance_meters, cell_degrees=0.05)[:max_bus_per_port]
        airport_matches = nearby_nodes(port, airport_nodes_, airport_grid, max_distance_meters=max_distance_meters, cell_degrees=0.05)[:max_airport_per_port]
        if rail_matches:
            coverage["portsWithRailAccess"] += 1
        if bus_matches:
            coverage["portsWithBusAccess"] += 1
        if airport_matches:
            coverage["portsWithAirportAccess"] += 1
        if rail_matches or bus_matches or airport_matches:
            coverage["portsWithAnyAccess"] += 1
        by_port[port["name"]] = {
            "portName": port["name"],
            "portNodeId": port["id"],
            "coordinate": {"lat": port["lat"], "lon": port["lon"]},
            "rail": [compact_access(item) for item in rail_matches],
            "busStops": [compact_access(item) for item in bus_matches],
            "airports": [compact_access(item) for item in airport_matches],
        }
        for match in bus_matches:
            bus_to_port_connectors.append({
                "fromNodeId": match["id"],
                "fromMode": "bus_stop",
                "fromName": match["name"],
                "toNodeId": port["id"],
                "toMode": "port",
                "toName": port["name"],
                "distanceMeters": match["distanceMeters"],
                "source": "generated_haversine_bus_stop_port_connector_v1",
            })
    return by_port, bus_to_port_connectors, dict(coverage)


def merge_bus_connectors(bus_bundle: dict[str, Any], new_connectors: list[dict[str, Any]]) -> tuple[int, int]:
    existing = [
        item
        for item in list(bus_bundle.get("walkingConnectors") or [])
        if not (item.get("toMode") == "port" and str(item.get("source") or "").startswith("generated_haversine_bus_stop_port_connector"))
    ]
    by_key = {
        (item.get("fromNodeId"), item.get("toMode"), item.get("toNodeId")): item
        for item in existing
        if item.get("fromNodeId") and item.get("toNodeId")
    }
    replaced = 0
    added = 0
    for connector in new_connectors:
        key = (connector["fromNodeId"], connector["toMode"], connector["toNodeId"])
        previous = by_key.get(key)
        if previous is None:
            by_key[key] = connector
            added += 1
        elif int(connector["distanceMeters"]) < int(previous.get("distanceMeters") or 10**9):
            by_key[key] = connector
            replaced += 1
    bus_bundle["walkingConnectors"] = sorted(
        by_key.values(),
        key=lambda item: (item.get("fromNodeId") or "", item.get("toMode") or "", item.get("distanceMeters") or 0, item.get("toNodeId") or ""),
    )
    return added, replaced


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bus-bundle", type=Path, default=DEFAULT_BUS_BUNDLE)
    parser.add_argument("--docs-bus-bundle", type=Path, default=ROOT / "docs" / "data" / "v5_bus_gtfs_current_bundle.json.gz")
    parser.add_argument("--map-bundle", type=Path, default=DEFAULT_MAP_BUNDLE)
    parser.add_argument("--airport-map", type=Path, default=DEFAULT_AIRPORT_MAP)
    parser.add_argument("--ship-map", type=Path, default=DEFAULT_SHIP_MAP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--docs-audit-output", type=Path, default=DEFAULT_DOCS_AUDIT_OUTPUT)
    parser.add_argument("--max-connector-meters", type=int, default=2000)
    parser.add_argument("--max-rail-connectors-per-port", type=int, default=8)
    parser.add_argument("--max-bus-connectors-per-port", type=int, default=16)
    parser.add_argument("--max-airport-connectors-per-port", type=int, default=4)
    args = parser.parse_args()

    bus_bundle = read_json(args.bus_bundle)
    map_bundle = read_json(args.map_bundle)
    ship_map = read_json(args.ship_map)
    airport_map = read_json(args.airport_map)
    rails = station_nodes(map_bundle)
    buses = bus_stop_nodes(bus_bundle)
    airports = airport_nodes(airport_map)
    ports = port_nodes(ship_map)
    by_port, bus_port_connectors, coverage = build_port_access(
        ports,
        rail_nodes=rails,
        bus_nodes=buses,
        airport_nodes_=airports,
        max_distance_meters=args.max_connector_meters,
        max_rail_per_port=args.max_rail_connectors_per_port,
        max_bus_per_port=args.max_bus_connectors_per_port,
        max_airport_per_port=args.max_airport_connectors_per_port,
    )
    added, replaced = merge_bus_connectors(bus_bundle, bus_port_connectors)
    generated_at = datetime.now(UTC).isoformat()
    payload = {
        "schemaVersion": "v5_port_connectors_v1",
        "generatedAt": generated_at,
        "modelVersion": "v5_port_rail_bus_airport_haversine_connectors_v1",
        "maxConnectorMeters": args.max_connector_meters,
        "portCount": len(ports),
        "ports": by_port,
    }
    audit = {
        "schemaVersion": "v5_port_connector_audit_v1",
        "generatedAt": generated_at,
        "modelVersion": payload["modelVersion"],
        "summary": {
            "portCount": len(ports),
            "railNodeCount": len(rails),
            "busStopNodeCount": len(buses),
            "airportNodeCount": len(airports),
            "maxConnectorMeters": args.max_connector_meters,
            "busStopPortConnectorCandidates": len(bus_port_connectors),
            "busStopPortConnectorsAdded": added,
            "busStopPortConnectorsReplaced": replaced,
            **coverage,
            "portsWithoutAnyAccess": len(ports) - coverage.get("portsWithAnyAccess", 0),
        },
        "portsWithoutAnyAccess": [
            {"portName": name, "coordinate": item["coordinate"]}
            for name, item in sorted(by_port.items(), key=lambda kv: kv[0])
            if not item["rail"] and not item["busStops"] and not item["airports"]
        ],
        "samplePortAccess": [
            by_port[name]
            for name in sorted(by_port)[:20]
        ],
    }
    write_json(args.output, payload)
    write_json(args.docs_output, payload)
    write_json(args.audit_output, audit)
    write_json(args.docs_audit_output, audit)
    write_json(args.bus_bundle, bus_bundle)
    copy_if_needed(args.bus_bundle, args.docs_bus_bundle)
    print(json.dumps(audit["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
