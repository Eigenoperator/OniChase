#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_BUNDLE = ROOT / "data" / "v4_gameplay_map_bundle.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v5_walking_edges.json.gz"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_walking_edge_audit.json"
DEFAULT_THRESHOLDS = [500, 1000, 2000, 3000, 5000]
DEFAULT_SPEED_METERS_PER_SECOND = 2.0
EARTH_RADIUS_METERS = 6_371_008.8


def load_json(path: Path) -> dict[str, Any]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        return
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def haversine_meters(left: dict[str, float], right: dict[str, float]) -> float:
    lat1 = math.radians(left["lat"])
    lon1 = math.radians(left["lon"])
    lat2 = math.radians(right["lat"])
    lon2 = math.radians(right["lon"])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_METERS * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def compact_station_group(group: dict[str, Any]) -> dict[str, Any] | None:
    centroid = group.get("centroid") or {}
    lat = centroid.get("lat")
    lon = centroid.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    return {
        "id": group["id"],
        "name": group.get("primaryName") or group.get("names", {}).get("ja") or group["id"],
        "lat": float(lat),
        "lon": float(lon),
        "prefecture": (group.get("tags") or {}).get("prefectureNamesJa", [None])[0],
        "operators": (group.get("tags") or {}).get("operatorNames", []),
        "lines": (group.get("tags") or {}).get("lineNames", []),
    }


def build_grid(nodes: list[dict[str, Any]], cell_degrees: float) -> dict[tuple[int, int], list[int]]:
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, node in enumerate(nodes):
        key = (math.floor(node["lat"] / cell_degrees), math.floor(node["lon"] / cell_degrees))
        grid[key].append(index)
    return grid


def generate_edges(
    nodes: list[dict[str, Any]],
    *,
    max_distance_meters: int,
    speed_meters_per_second: float,
    cell_degrees: float,
) -> list[dict[str, Any]]:
    grid = build_grid(nodes, cell_degrees)
    radius_cells = max(1, math.ceil((max_distance_meters / 111_320) / cell_degrees) + 1)
    edges: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for left_index, left in enumerate(nodes):
        lat_cell = math.floor(left["lat"] / cell_degrees)
        lon_cell = math.floor(left["lon"] / cell_degrees)
        for dlat in range(-radius_cells, radius_cells + 1):
            for dlon in range(-radius_cells, radius_cells + 1):
                for right_index in grid.get((lat_cell + dlat, lon_cell + dlon), []):
                    if right_index <= left_index:
                        continue
                    pair = (left_index, right_index)
                    if pair in seen:
                        continue
                    seen.add(pair)
                    right = nodes[right_index]
                    distance = haversine_meters(left, right)
                    if distance > max_distance_meters:
                        continue
                    distance_meters = int(round(distance))
                    walk_time_sec = int(math.ceil(distance / speed_meters_per_second))
                    edges.append({
                        "fromNodeId": left["id"],
                        "toNodeId": right["id"],
                        "fromName": left["name"],
                        "toName": right["name"],
                        "distanceMeters": distance_meters,
                        "walkTimeSec": walk_time_sec,
                        "speedMetersPerSecond": speed_meters_per_second,
                        "directed": False,
                        "source": "generated_station_group_distance_v1",
                    })
    edges.sort(key=lambda edge: (edge["distanceMeters"], edge["fromName"], edge["toName"]))
    return edges


def layer_summary(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    threshold: int,
) -> dict[str, Any]:
    degree: Counter[str] = Counter()
    layer_edges = [edge for edge in edges if edge["distanceMeters"] <= threshold]
    for edge in layer_edges:
        degree[edge["fromNodeId"]] += 1
        degree[edge["toNodeId"]] += 1
    values = [degree[node["id"]] for node in nodes]
    top_nodes = sorted(
        (
            {
                "stationGroupId": node["id"],
                "name": node["name"],
                "prefecture": node.get("prefecture"),
                "neighborCount": degree[node["id"]],
            }
            for node in nodes
        ),
        key=lambda item: (-item["neighborCount"], item["name"]),
    )[:20]
    return {
        "thresholdMeters": threshold,
        "undirectedEdgeCount": len(layer_edges),
        "directedEdgeCount": len(layer_edges) * 2,
        "averageNeighbors": round(mean(values), 3) if values else 0,
        "medianNeighbors": median(values) if values else 0,
        "maxNeighbors": max(values) if values else 0,
        "isolatedNodeCount": sum(1 for value in values if value == 0),
        "topNeighborStations": top_nodes,
    }


def regional_summary(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], threshold: int) -> list[dict[str, Any]]:
    by_prefecture: dict[str, set[str]] = defaultdict(set)
    id_to_node = {node["id"]: node for node in nodes}
    for edge in edges:
        if edge["distanceMeters"] > threshold:
            continue
        for key in ("fromNodeId", "toNodeId"):
            node = id_to_node.get(edge[key])
            prefecture = node.get("prefecture") if node else None
            by_prefecture[prefecture or "unknown"].add(edge[key])
    return [
        {"prefecture": prefecture, "nodeWithWalkingEdgeCount": len(node_ids)}
        for prefecture, node_ids in sorted(by_prefecture.items(), key=lambda item: (-len(item[1]), item[0]))
    ][:20]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map-bundle", type=Path, default=DEFAULT_MAP_BUNDLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--speed-meters-per-second", type=float, default=DEFAULT_SPEED_METERS_PER_SECOND)
    parser.add_argument("--thresholds", type=int, nargs="+", default=DEFAULT_THRESHOLDS)
    args = parser.parse_args()

    thresholds = sorted(set(args.thresholds))
    if not thresholds or thresholds[0] <= 0:
        raise ValueError("thresholds must be positive")
    if args.speed_meters_per_second <= 0:
        raise ValueError("speed must be positive")

    bundle = load_json(args.map_bundle)
    raw_groups = bundle.get("stationGroups") or []
    nodes = [node for group in raw_groups if (node := compact_station_group(group))]
    max_threshold = max(thresholds)
    edges = generate_edges(
        nodes,
        max_distance_meters=max_threshold,
        speed_meters_per_second=args.speed_meters_per_second,
        cell_degrees=0.05,
    )
    generated_at = datetime.now(UTC).isoformat()
    payload = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "modelVersion": "v5_walking_edges_station_group_distance_v1",
        "sourceMapBundle": str(args.map_bundle.relative_to(ROOT)) if args.map_bundle.is_relative_to(ROOT) else str(args.map_bundle),
        "distanceModel": "haversine_station_group_centroid",
        "thresholdMeters": thresholds,
        "maxDistanceMeters": max_threshold,
        "speedMetersPerSecond": args.speed_meters_per_second,
        "edgeCount": len(edges),
        "directedEdgeCount": len(edges) * 2,
        "edges": edges,
    }
    write_json(args.output, payload)

    audit = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "modelVersion": payload["modelVersion"],
        "sourceMapBundle": payload["sourceMapBundle"],
        "nodeCount": len(raw_groups),
        "eligibleNodeCount": len(nodes),
        "missingCoordinateNodeCount": len(raw_groups) - len(nodes),
        "speedMetersPerSecond": args.speed_meters_per_second,
        "thresholdMeters": thresholds,
        "maxDistanceMeters": max_threshold,
        "edgeCountWithinMaxDistance": len(edges),
        "directedEdgeCountWithinMaxDistance": len(edges) * 2,
        "layers": [layer_summary(nodes, edges, threshold) for threshold in thresholds],
        "regionalTopAtMaxThreshold": regional_summary(nodes, edges, max_threshold),
        "notes": [
            "Walking edges are generated from station-group centroid distance, not from road or pedestrian-network routing.",
            "Edges are stored once as undirected pairs within the maximum threshold. Runtime should filter by distanceMeters for the active walking layer.",
        ],
    }
    write_json(args.audit_output, audit)
    print(json.dumps({
        "output": str(args.output),
        "auditOutput": str(args.audit_output),
        "eligibleNodeCount": len(nodes),
        "edgeCount": len(edges),
        "layers": [
            {
                "thresholdMeters": item["thresholdMeters"],
                "undirectedEdgeCount": item["undirectedEdgeCount"],
                "averageNeighbors": item["averageNeighbors"],
                "maxNeighbors": item["maxNeighbors"],
            }
            for item in audit["layers"]
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
