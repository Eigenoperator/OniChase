#!/usr/bin/env python3

from __future__ import annotations

import argparse
import heapq
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
N02_RAIL_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_RailroadSection.geojson"
ROUTES_PATH = ROOT / "data" / "shinkansen_v2_routes.json"
STATIONS_PATH = ROOT / "data" / "shinkansen_v2_stations.json"
OUTPUT_PATH = ROOT / "data" / "v3_real_geometry_routes.json"


ROUTE_SPECS: dict[str, dict[str, Any]] = {
    "TOKAIDO": {
        "refs": [("東海道新幹線", "東海旅客鉄道")],
    },
    "SANYO": {
        "refs": [("山陽新幹線", "西日本旅客鉄道")],
    },
    "KYUSHU": {
        "refs": [("九州新幹線", "九州旅客鉄道")],
    },
    "NISHI_KYUSHU": {
        "refs": [("西九州新幹線", "九州旅客鉄道")],
        "station_ids": ["TAKEO_ONSEN", "URESHINO_ONSEN", "SHIN_OMURA", "ISAHAYA", "NAGASAKI"],
    },
    "TOHOKU": {
        "refs": [("東北新幹線", "東日本旅客鉄道")],
    },
    "HOKKAIDO": {
        "refs": [("北海道新幹線", "北海道旅客鉄道")],
    },
    "JOETSU": {
        "refs": [("東北新幹線", "東日本旅客鉄道"), ("上越新幹線", "東日本旅客鉄道")],
    },
    "HOKURIKU": {
        "refs": [
            ("東北新幹線", "東日本旅客鉄道"),
            ("上越新幹線", "東日本旅客鉄道"),
            ("北陸新幹線", "東日本旅客鉄道"),
            ("北陸新幹線", "西日本旅客鉄道"),
        ],
    },
    "YAMAGATA": {
        "refs": [("東北新幹線", "東日本旅客鉄道"), ("奥羽線", "東日本旅客鉄道")],
    },
    "AKITA": {
        "refs": [("東北新幹線", "東日本旅客鉄道"), ("田沢湖線", "東日本旅客鉄道"), ("奥羽線", "東日本旅客鉄道")],
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def node_key(point: list[float]) -> tuple[float, float]:
    lon, lat = point
    return (round(lon, 6), round(lat, 6))


def build_graph(features: list[dict[str, Any]]) -> tuple[dict[tuple[float, float], list[tuple[tuple[float, float], float]]], dict[tuple[float, float], list[float]]]:
    adjacency: dict[tuple[float, float], list[tuple[tuple[float, float], float]]] = {}
    coords: dict[tuple[float, float], list[float]] = {}
    for feature in features:
        points = feature["geometry"]["coordinates"]
        for start, end in zip(points, points[1:]):
            start_key = node_key(start)
            end_key = node_key(end)
            coords[start_key] = start
            coords[end_key] = end
            distance = haversine_meters(start[1], start[0], end[1], end[0])
            adjacency.setdefault(start_key, []).append((end_key, distance))
            adjacency.setdefault(end_key, []).append((start_key, distance))
    return adjacency, coords


def nearest_graph_node(
    lat: float,
    lon: float,
    nodes: list[tuple[float, float]],
) -> tuple[tuple[float, float], float]:
    best = min(nodes, key=lambda node: haversine_meters(lat, lon, node[1], node[0]))
    return best, haversine_meters(lat, lon, best[1], best[0])


def shortest_path(
    adjacency: dict[tuple[float, float], list[tuple[tuple[float, float], float]]],
    start: tuple[float, float],
    end: tuple[float, float],
) -> list[tuple[float, float]]:
    queue: list[tuple[float, tuple[float, float]]] = [(0.0, start)]
    distance: dict[tuple[float, float], float] = {start: 0.0}
    previous: dict[tuple[float, float], tuple[float, float]] = {}
    while queue:
        current_distance, current = heapq.heappop(queue)
        if current == end:
            break
        if current_distance != distance[current]:
            continue
        for neighbor, weight in adjacency.get(current, []):
            next_distance = current_distance + weight
            if next_distance < distance.get(neighbor, float("inf")):
                distance[neighbor] = next_distance
                previous[neighbor] = current
                heapq.heappush(queue, (next_distance, neighbor))
    if end not in distance:
        raise RuntimeError(f"Could not find path between graph nodes {start} and {end}")
    path = [end]
    while path[-1] != start:
        path.append(previous[path[-1]])
    path.reverse()
    return path


def dedupe_polyline(points: list[list[float]]) -> list[list[float]]:
    deduped: list[list[float]] = []
    for point in points:
        if deduped and point == deduped[-1]:
            continue
        deduped.append(point)
    return deduped


def route_station_ids(route_entry: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    return spec.get("station_ids", route_entry["station_ids"])


def build_route_geometry(
    route_id: str,
    route_entry: dict[str, Any],
    spec: dict[str, Any],
    rail_features: list[dict[str, Any]],
    station_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    refs = set(spec["refs"])
    features = [
        feature
        for feature in rail_features
        if (feature["properties"].get("N02_003"), feature["properties"].get("N02_004")) in refs
    ]
    if not features:
        raise RuntimeError(f"No N02 railroad sections found for {route_id}: {sorted(refs)}")

    adjacency, coords = build_graph(features)
    node_keys = list(coords.keys())
    station_ids = route_station_ids(route_entry, spec)
    snapped: list[dict[str, Any]] = []
    for station_id in station_ids:
        station = station_map[station_id]
        node, snap_distance = nearest_graph_node(station["lat"], station["lon"], node_keys)
        snapped.append(
            {
                "station_id": station_id,
                "node": node,
                "snap_distance_m": round(snap_distance, 3),
            }
        )

    full_polyline: list[list[float]] = []
    max_snap_distance = 0.0
    for current, nxt in zip(snapped, snapped[1:]):
        path = shortest_path(adjacency, current["node"], nxt["node"])
        segment = [coords[node] for node in path]
        if full_polyline and segment and full_polyline[-1] == segment[0]:
            full_polyline.extend(segment[1:])
        else:
            full_polyline.extend(segment)
        max_snap_distance = max(max_snap_distance, current["snap_distance_m"], nxt["snap_distance_m"])

    if not full_polyline:
        first = coords[snapped[0]["node"]]
        full_polyline = [first]

    return {
        "id": route_id,
        "lineName": route_entry["name"],
        "source": "mlit_n02_2024",
        "lineRefs": [{"name_ja": name, "operator_ja": operator} for name, operator in spec["refs"]],
        "station_ids": station_ids,
        "polyline": [{"lat": point[1], "lon": point[0]} for point in dedupe_polyline(full_polyline)],
        "snapDiagnostics": {
            "maxSnapDistanceMeters": round(max_snap_distance, 3),
            "stationNodes": [
                {
                    "station_id": item["station_id"],
                    "node_lon": item["node"][0],
                    "node_lat": item["node"][1],
                    "snap_distance_m": item["snap_distance_m"],
                }
                for item in snapped
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v3 real Shinkansen geometry from MLIT N02 data.")
    parser.add_argument("--n02-rail", default=str(N02_RAIL_PATH))
    parser.add_argument("--routes", default=str(ROUTES_PATH))
    parser.add_argument("--stations", default=str(STATIONS_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()

    rail_features = load_json(Path(args.n02_rail))["features"]
    routes = {entry["id"]: entry for entry in load_json(Path(args.routes))}
    stations = {entry["id"]: entry for entry in load_json(Path(args.stations))}

    route_geometries = []
    for route_id in [
        "TOKAIDO",
        "SANYO",
        "KYUSHU",
        "NISHI_KYUSHU",
        "TOHOKU",
        "HOKKAIDO",
        "JOETSU",
        "HOKURIKU",
        "YAMAGATA",
        "AKITA",
    ]:
        geometry = build_route_geometry(route_id, routes[route_id], ROUTE_SPECS[route_id], rail_features, stations)
        route_geometries.append(geometry)
        print(
            f"{route_id}: {len(geometry['polyline'])} geometry points, max station snap {geometry['snapDiagnostics']['maxSnapDistanceMeters']:.1f}m"
        )

    payload = {
        "id": "v3_real_geometry_routes_v0_2",
        "note": "Shinkansen route geometries extracted from MLIT N02 2024 railroad sections. Station positions remain real; lines follow N02 section geometry.",
        "routes": route_geometries,
    }
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
