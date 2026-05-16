#!/usr/bin/env python3
"""Build a lightweight V5 bus map layer from the real GTFS bus bundle."""

from __future__ import annotations

import argparse
import gzip
import json
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
    parser.add_argument("--max-shape-points", type=int, default=180)
    parser.add_argument("--max-fallback-points", type=int, default=80)
    args = parser.parse_args()

    bundle = read_json(args.bus_bundle)
    feature_collection, audit = build_map(bundle, args.max_shape_points, args.max_fallback_points)
    write_json(args.output, feature_collection)
    if args.docs_output:
        write_json(args.docs_output, feature_collection)
    write_json(args.audit_output, audit)
    if args.docs_audit_output:
        write_json(args.docs_audit_output, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
