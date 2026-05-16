#!/usr/bin/env python3
"""Build a lightweight V5 bus map layer from the real GTFS bus bundle."""

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
DEFAULT_OUTPUT = ROOT / "data" / "v5_bus_map.geojson.gz"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_bus_map.geojson.gz"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_bus_map_audit.json"
DEFAULT_DOCS_AUDIT_OUTPUT = ROOT / "docs" / "data" / "v5_bus_map_audit.json"
DEFAULT_TILE_DIR = ROOT / "data" / "v5_bus_map_tiles"
DEFAULT_DOCS_TILE_DIR = ROOT / "docs" / "data" / "v5_bus_map_tiles"
DEFAULT_TILE_SIZE_DEGREES = 0.25

CLASS_RANK = {
    "bus_airport": 0,
    "bus_long_distance": 1,
    "bus_local": 2,
}


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


def feature_coordinates(feature: dict[str, Any]) -> list[list[float]]:
    geometry = feature.get("geometry") or {}
    if geometry.get("type") == "Point":
        coordinates = geometry.get("coordinates")
        return [coordinates] if valid_coordinate(coordinates) else []
    if geometry.get("type") == "LineString":
        return [coord for coord in geometry.get("coordinates") or [] if valid_coordinate(coord)]
    return []


def valid_coordinate(coordinate: Any) -> bool:
    return (
        isinstance(coordinate, list)
        and len(coordinate) >= 2
        and isinstance(coordinate[0], (int, float))
        and isinstance(coordinate[1], (int, float))
    )


def tile_key(ix: int, iy: int) -> str:
    return f"z0_x{ix}_y{iy}"


def tile_indices_for_coordinate(coordinate: list[float], tile_size_degrees: float) -> tuple[int, int]:
    return math.floor(coordinate[0] / tile_size_degrees), math.floor(coordinate[1] / tile_size_degrees)


def tile_keys_for_feature(feature: dict[str, Any], tile_size_degrees: float) -> set[str]:
    coordinates = feature_coordinates(feature)
    if not coordinates:
        return set()
    xs = [coord[0] for coord in coordinates]
    ys = [coord[1] for coord in coordinates]
    min_ix = math.floor(min(xs) / tile_size_degrees)
    max_ix = math.floor(max(xs) / tile_size_degrees)
    min_iy = math.floor(min(ys) / tile_size_degrees)
    max_iy = math.floor(max(ys) / tile_size_degrees)
    # Long-distance bus routes can cross many cells; keep them discoverable
    # without exploding tile references by indexing only touched vertices plus
    # bbox corners. Dense local routes have many vertices and naturally cover
    # their cells.
    keys = {tile_key(*tile_indices_for_coordinate(coord, tile_size_degrees)) for coord in coordinates}
    keys.add(tile_key(min_ix, min_iy))
    keys.add(tile_key(max_ix, max_iy))
    return keys


def feature_bounds(features: list[dict[str, Any]]) -> list[float] | None:
    coordinates: list[list[float]] = []
    for feature in features:
        coordinates.extend(feature_coordinates(feature))
    if not coordinates:
        return None
    return [
        min(coord[0] for coord in coordinates),
        min(coord[1] for coord in coordinates),
        max(coord[0] for coord in coordinates),
        max(coord[1] for coord in coordinates),
    ]


def write_bus_tiles(
    feature_collection: dict[str, Any],
    *,
    tile_dir: Path,
    tile_size_degrees: float,
    generated_at: str,
) -> dict[str, Any]:
    if tile_dir.exists():
        shutil.rmtree(tile_dir)
    tile_dir.mkdir(parents=True, exist_ok=True)

    by_tile: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_by_tile: dict[str, set[str]] = defaultdict(set)
    for feature in feature_collection.get("features") or []:
        feature_id = str(feature.get("id") or "")
        for key in tile_keys_for_feature(feature, tile_size_degrees):
            if feature_id and feature_id in seen_by_tile[key]:
                continue
            by_tile[key].append(feature)
            if feature_id:
                seen_by_tile[key].add(feature_id)

    manifest_tiles: dict[str, Any] = {}
    feature_count_total = 0
    for key, features in sorted(by_tile.items()):
        tile_payload = {
            "type": "FeatureCollection",
            "metadata": {
                "schemaVersion": "v5_bus_map_tile_geojson_v1",
                "generatedAt": generated_at,
                "tileKey": key,
            },
            "features": features,
        }
        path = tile_dir / f"{key}.geojson.gz"
        write_json(path, tile_payload)
        bounds = feature_bounds(features)
        class_counts = Counter(feature.get("properties", {}).get("serviceClass") or "unknown" for feature in features)
        kind_counts = Counter(feature.get("properties", {}).get("kind") or "unknown" for feature in features)
        manifest_tiles[key] = {
            "url": f"./data/v5_bus_map_tiles/{key}.geojson.gz",
            "featureCount": len(features),
            "bounds": bounds,
            "serviceClassCounts": dict(sorted(class_counts.items())),
            "kindCounts": dict(sorted(kind_counts.items())),
        }
        feature_count_total += len(features)

    return {
        "schemaVersion": "v5_bus_map_tile_manifest_v1",
        "generatedAt": generated_at,
        "tileSizeDegrees": tile_size_degrees,
        "tileCount": len(manifest_tiles),
        "tileFeatureReferenceCount": feature_count_total,
        "sourceFeatureCount": len(feature_collection.get("features") or []),
        "tiles": manifest_tiles,
    }


def color_for_class(service_class: str) -> str:
    if service_class == "bus_airport":
        return "#0f766e"
    if service_class == "bus_long_distance":
        return "#b45309"
    return "#64748b"


def route_name(route: dict[str, Any]) -> str:
    return (
        route.get("routeLongName")
        or route.get("routeShortName")
        or route.get("routeDesc")
        or route.get("sourceRouteId")
        or route.get("busRouteId")
        or "Bus route"
    )


def downsample_coordinates(points: list[dict[str, Any]], max_points: int) -> list[list[float]]:
    coordinates = [
        [float(point["lon"]), float(point["lat"])]
        for point in sorted(points, key=lambda item: item.get("sequence") or 0)
        if isinstance(point.get("lat"), (int, float)) and isinstance(point.get("lon"), (int, float))
    ]
    if len(coordinates) <= max_points:
        return coordinates
    stride = max(1, len(coordinates) // max_points)
    sampled = [coordinates[index] for index in range(0, len(coordinates), stride)]
    if sampled[-1] != coordinates[-1]:
        sampled.append(coordinates[-1])
    return sampled


def stop_sequence_geometry(
    trip_id: str,
    stop_times_by_trip: dict[str, list[dict[str, Any]]],
    stops_by_id: dict[str, dict[str, Any]],
    max_points: int,
) -> list[list[float]]:
    coordinates: list[list[float]] = []
    for stop_time in sorted(stop_times_by_trip.get(trip_id, []), key=lambda item: item.get("stopSequence") or 0):
        stop = stops_by_id.get(stop_time.get("busStopId") or "")
        if not stop:
            continue
        lat = stop.get("lat")
        lon = stop.get("lon")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            coord = [float(lon), float(lat)]
            if not coordinates or coordinates[-1] != coord:
                coordinates.append(coord)
    if len(coordinates) <= max_points:
        return coordinates
    stride = max(1, len(coordinates) // max_points)
    sampled = [coordinates[index] for index in range(0, len(coordinates), stride)]
    if sampled[-1] != coordinates[-1]:
        sampled.append(coordinates[-1])
    return sampled


def representative_route_for_shape(
    shape_id: str,
    trips: list[dict[str, Any]],
    routes_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = [routes_by_id.get(trip.get("busRouteId") or "") for trip in trips if trip.get("busShapeId") == shape_id]
    candidates = [route for route in candidates if route]
    if not candidates:
        return None
    candidates.sort(
        key=lambda route: (
            CLASS_RANK.get(route.get("serviceClass") or "bus_local", 9),
            route.get("agencyName") or "",
            route_name(route),
        )
    )
    return candidates[0]


def build_map(bundle: dict[str, Any], max_shape_points: int, max_fallback_points: int) -> tuple[dict[str, Any], dict[str, Any]]:
    routes_by_id = {route["busRouteId"]: route for route in bundle.get("routes") or [] if route.get("busRouteId")}
    stops_by_id = {stop["busStopId"]: stop for stop in bundle.get("stops") or [] if stop.get("busStopId")}
    trips = [trip for trip in bundle.get("trips") or [] if trip.get("busTripId") and trip.get("busRouteId")]
    trips_by_shape: dict[str, list[dict[str, Any]]] = defaultdict(list)
    trips_by_route: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trip in trips:
        trips_by_route[trip["busRouteId"]].append(trip)
        if trip.get("busShapeId"):
            trips_by_shape[trip["busShapeId"]].append(trip)

    stop_times_by_trip: dict[str, list[dict[str, Any]]] = defaultdict(list)
    route_ids_by_stop: dict[str, set[str]] = defaultdict(set)
    for stop_time in bundle.get("stopTimes") or []:
        trip_id = stop_time.get("busTripId")
        stop_id = stop_time.get("busStopId")
        if not trip_id or not stop_id:
            continue
        stop_times_by_trip[trip_id].append(stop_time)
    trip_route = {trip["busTripId"]: trip["busRouteId"] for trip in trips}
    for trip_id, rows in stop_times_by_trip.items():
        route_id = trip_route.get(trip_id)
        if not route_id:
            continue
        for row in rows:
            route_ids_by_stop[row["busStopId"]].add(route_id)

    features: list[dict[str, Any]] = []
    route_line_count_by_class: Counter[str] = Counter()
    shape_by_id = {shape.get("busShapeId"): shape for shape in bundle.get("shapes") or [] if shape.get("busShapeId")}

    for shape_id, shape in shape_by_id.items():
        route = representative_route_for_shape(shape_id, trips, routes_by_id)
        if not route:
            continue
        coordinates = downsample_coordinates(shape.get("points") or [], max_shape_points)
        if len(coordinates) < 2:
            continue
        service_class = route.get("serviceClass") or "bus_local"
        features.append(
            {
                "type": "Feature",
                "id": f"bus-shape:{shape_id}",
                "geometry": {"type": "LineString", "coordinates": coordinates},
                "properties": {
                    "kind": "bus-route",
                    "busShapeId": shape_id,
                    "busRouteId": route["busRouteId"],
                    "routeName": route_name(route),
                    "agencyName": route.get("agencyName") or "",
                    "serviceClass": service_class,
                    "routeColor": f"#{route.get('routeColor')}" if route.get("routeColor") else color_for_class(service_class),
                    "tripCount": len(trips_by_shape.get(shape_id, [])),
                },
            }
        )
        route_line_count_by_class[service_class] += 1

    route_ids_with_shape = {feature["properties"]["busRouteId"] for feature in features}
    for route_id, route in routes_by_id.items():
        if route_id in route_ids_with_shape:
            continue
        route_trips = trips_by_route.get(route_id) or []
        if not route_trips:
            continue
        representative_trip = max(route_trips, key=lambda trip: len(stop_times_by_trip.get(trip["busTripId"], [])))
        coordinates = stop_sequence_geometry(representative_trip["busTripId"], stop_times_by_trip, stops_by_id, max_fallback_points)
        if len(coordinates) < 2:
            continue
        service_class = route.get("serviceClass") or "bus_local"
        features.append(
            {
                "type": "Feature",
                "id": f"bus-route-fallback:{route_id}",
                "geometry": {"type": "LineString", "coordinates": coordinates},
                "properties": {
                    "kind": "bus-route",
                    "busShapeId": "",
                    "busRouteId": route_id,
                    "routeName": route_name(route),
                    "agencyName": route.get("agencyName") or "",
                    "serviceClass": service_class,
                    "routeColor": f"#{route.get('routeColor')}" if route.get("routeColor") else color_for_class(service_class),
                    "tripCount": len(route_trips),
                    "geometrySource": "stop_sequence_fallback",
                },
            }
        )
        route_line_count_by_class[service_class] += 1

    stop_count_by_class: Counter[str] = Counter()
    for stop_id, stop in stops_by_id.items():
        lat = stop.get("lat")
        lon = stop.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        route_ids = route_ids_by_stop.get(stop_id) or set()
        if route_ids:
            classes = [routes_by_id[route_id].get("serviceClass") or "bus_local" for route_id in route_ids if route_id in routes_by_id]
            service_class = sorted(classes, key=lambda item: CLASS_RANK.get(item, 9))[0] if classes else "bus_local"
        else:
            service_class = "bus_local"
        features.append(
            {
                "type": "Feature",
                "id": f"bus-stop:{stop_id}",
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "properties": {
                    "kind": "bus-stop",
                    "busStopId": stop_id,
                    "name": stop.get("name") or stop_id,
                    "serviceClass": service_class,
                    "routeCount": len(route_ids),
                },
            }
        )
        stop_count_by_class[service_class] += 1

    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    feature_collection = {
        "type": "FeatureCollection",
        "metadata": {
            "schemaVersion": "v5_bus_map_geojson_v1",
            "generatedAt": generated_at,
            "sourceBundle": "data/v5_bus_gtfs_current_bundle.json.gz",
            "shapePointPolicy": {
                "maxShapePoints": max_shape_points,
                "maxFallbackPoints": max_fallback_points,
            },
        },
        "features": features,
    }
    audit = {
        "schemaVersion": "v5_bus_map_audit_v1",
        "generatedAt": generated_at,
        "sourceBundle": "data/v5_bus_gtfs_current_bundle.json.gz",
        "featureCount": len(features),
        "routeLineCount": sum(route_line_count_by_class.values()),
        "routeLineCountByClass": dict(sorted(route_line_count_by_class.items())),
        "busStopCount": sum(stop_count_by_class.values()),
        "busStopCountByClass": dict(sorted(stop_count_by_class.items())),
        "sourceRouteCount": len(routes_by_id),
        "sourceTripCount": len(trips),
        "sourceStopCount": len(stops_by_id),
        "sourceShapeCount": len(shape_by_id),
    }
    return feature_collection, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bus-bundle", type=Path, default=DEFAULT_BUS_BUNDLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--docs-audit-output", type=Path, default=DEFAULT_DOCS_AUDIT_OUTPUT)
    parser.add_argument("--tile-dir", type=Path, default=DEFAULT_TILE_DIR)
    parser.add_argument("--docs-tile-dir", type=Path, default=DEFAULT_DOCS_TILE_DIR)
    parser.add_argument("--tile-size-degrees", type=float, default=DEFAULT_TILE_SIZE_DEGREES)
    parser.add_argument("--max-shape-points", type=int, default=180)
    parser.add_argument("--max-fallback-points", type=int, default=80)
    args = parser.parse_args()

    bundle = read_json(args.bus_bundle)
    feature_collection, audit = build_map(bundle, args.max_shape_points, args.max_fallback_points)
    generated_at = feature_collection["metadata"]["generatedAt"]
    tile_manifest = write_bus_tiles(
        feature_collection,
        tile_dir=args.tile_dir,
        tile_size_degrees=args.tile_size_degrees,
        generated_at=generated_at,
    )
    if args.docs_tile_dir:
        docs_manifest = write_bus_tiles(
            feature_collection,
            tile_dir=args.docs_tile_dir,
            tile_size_degrees=args.tile_size_degrees,
            generated_at=generated_at,
        )
        write_json(args.docs_tile_dir / "manifest.json", docs_manifest)
    write_json(args.tile_dir / "manifest.json", tile_manifest)
    audit["tileManifest"] = {
        "tileSizeDegrees": args.tile_size_degrees,
        "tileCount": tile_manifest["tileCount"],
        "tileFeatureReferenceCount": tile_manifest["tileFeatureReferenceCount"],
    }
    write_json(args.output, feature_collection)
    if args.docs_output:
        write_json(args.docs_output, feature_collection)
    write_json(args.audit_output, audit)
    if args.docs_audit_output:
        write_json(args.docs_audit_output, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
