#!/usr/bin/env python3
"""Audit airport bus access from the V5 GTFS bus bundle.

This audit does not decide gameplay availability by itself.  It answers a
source-data question: for each domestic airport node, do the real bus feeds
currently provide nearby bus stops and airport-class bus routes?
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUS_BUNDLE = ROOT / "data" / "v5_bus_gtfs_current_bundle.json.gz"
DEFAULT_AIRPORT_MAP = ROOT / "docs" / "data" / "v5_flight_map.geojson"
DEFAULT_OUTPUT = ROOT / "data" / "v5_airport_bus_access_audit.json"
DEFAULT_DOCUMENTED_NO_PUBLIC_BUS = ROOT / "data" / "v5_remaining_airport_official_bus_source.json"
EARTH_RADIUS_METERS = 6_371_008.8


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


def airport_nodes(path: Path) -> list[dict[str, Any]]:
    collection = read_json(path)
    nodes = []
    for feature in collection.get("features") or []:
        if feature.get("geometry", {}).get("type") != "Point":
            continue
        coords = feature.get("geometry", {}).get("coordinates") or []
        props = feature.get("properties") or {}
        iata = props.get("iata")
        if len(coords) < 2 or not iata:
            continue
        nodes.append(
            {
                "iata": iata,
                "name": props.get("name") or iata,
                "municipality": props.get("municipality") or "",
                "flightCount": props.get("flightCount") or 0,
                "lat": float(coords[1]),
                "lon": float(coords[0]),
            }
        )
    nodes.sort(key=lambda item: item["iata"])
    return nodes


def grid_key(node: dict[str, Any], cell_degrees: float) -> tuple[int, int]:
    return (math.floor(node["lat"] / cell_degrees), math.floor(node["lon"] / cell_degrees))


def build_grid(nodes: list[dict[str, Any]], cell_degrees: float) -> dict[tuple[int, int], list[int]]:
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, node in enumerate(nodes):
        grid[grid_key(node, cell_degrees)].append(index)
    return grid


def nearby_stops(
    airport: dict[str, Any],
    stops: list[dict[str, Any]],
    grid: dict[tuple[int, int], list[int]],
    *,
    max_distance_meters: int,
    cell_degrees: float,
) -> list[dict[str, Any]]:
    lat_cell, lon_cell = grid_key(airport, cell_degrees)
    radius_cells = max(1, math.ceil((max_distance_meters / 111_320) / cell_degrees) + 1)
    matches = []
    for dlat in range(-radius_cells, radius_cells + 1):
        for dlon in range(-radius_cells, radius_cells + 1):
            for index in grid.get((lat_cell + dlat, lon_cell + dlon), []):
                stop = stops[index]
                distance = haversine_meters(airport, stop)
                if distance <= max_distance_meters:
                    matches.append(stop | {"distanceMeters": int(round(distance))})
    matches.sort(key=lambda item: (item["distanceMeters"], item["name"], item["busStopId"]))
    return matches


def route_label(route: dict[str, Any]) -> str:
    return route.get("routeLongName") or route.get("routeShortName") or route.get("routeDesc") or route.get("busRouteId") or ""


def documented_no_public_bus(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = read_json(path)
    result = {}
    for item in payload.get("documentedNoPublicBus") or []:
        iata = item.get("airportIata")
        if iata:
            result[iata] = item
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bus-bundle", type=Path, default=DEFAULT_BUS_BUNDLE)
    parser.add_argument("--airport-map", type=Path, default=DEFAULT_AIRPORT_MAP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--documented-no-public-bus", type=Path, default=DEFAULT_DOCUMENTED_NO_PUBLIC_BUS)
    parser.add_argument("--nearby-meters", type=int, default=2000)
    parser.add_argument("--search-meters", type=int, default=5000)
    parser.add_argument("--top-stops", type=int, default=12)
    args = parser.parse_args()

    if args.nearby_meters <= 0 or args.search_meters <= 0:
        raise ValueError("distance thresholds must be positive")
    if args.nearby_meters > args.search_meters:
        raise ValueError("--nearby-meters must be <= --search-meters")

    bundle = read_json(args.bus_bundle)
    airports = airport_nodes(args.airport_map)
    no_public_bus = documented_no_public_bus(args.documented_no_public_bus)
    stops = [
        {
            "busStopId": stop["busStopId"],
            "name": stop.get("name") or stop["busStopId"],
            "lat": stop["lat"],
            "lon": stop["lon"],
        }
        for stop in bundle.get("stops") or []
        if isinstance(stop.get("lat"), (int, float)) and isinstance(stop.get("lon"), (int, float)) and (stop.get("locationType") in (0, None))
    ]
    routes_by_id = {route["busRouteId"]: route for route in bundle.get("routes") or []}
    trip_route: dict[str, str] = {}
    for trip in bundle.get("trips") or []:
        if trip.get("busTripId") and trip.get("busRouteId"):
            trip_route[trip["busTripId"]] = trip["busRouteId"]

    stop_routes: dict[str, set[str]] = defaultdict(set)
    for stop_time in bundle.get("stopTimes") or []:
        route_id = trip_route.get(stop_time.get("busTripId") or "")
        stop_id = stop_time.get("busStopId")
        if route_id and stop_id:
            stop_routes[stop_id].add(route_id)

    grid = build_grid(stops, 0.05)
    airport_results = []
    status_counts: Counter[str] = Counter()
    for airport in airports:
        matches = nearby_stops(airport, stops, grid, max_distance_meters=args.search_meters, cell_degrees=0.05)
        nearby = [item for item in matches if item["distanceMeters"] <= args.nearby_meters]
        route_ids = sorted({route_id for stop in nearby for route_id in stop_routes.get(stop["busStopId"], set())})
        routes = [routes_by_id[route_id] for route_id in route_ids if route_id in routes_by_id]
        class_counts = Counter(route.get("serviceClass") or "unknown" for route in routes)
        agency_counts = Counter(route.get("agencyName") or "unknown" for route in routes)
        airport_class_routes = [route for route in routes if route.get("serviceClass") == "bus_airport"]
        if airport["iata"] in no_public_bus and not nearby and not matches:
            status = "documented_no_public_bus"
        elif airport_class_routes:
            status = "covered_by_gtfs_airport_bus"
        elif nearby:
            status = "nearby_gtfs_bus_stop_no_airport_class_route"
        elif matches:
            status = "gtfs_bus_stop_within_search_radius_only"
        else:
            status = "no_gtfs_bus_stop_within_search_radius"
        status_counts[status] += 1
        airport_results.append(
            {
                "iata": airport["iata"],
                "name": airport["name"],
                "municipality": airport["municipality"],
                "flightCount": airport["flightCount"],
                "status": status,
                "nearbyMeters": args.nearby_meters,
                "nearbyStopCount": len(nearby),
                "searchMeters": args.search_meters,
                "searchStopCount": len(matches),
                "routeCountFromNearbyStops": len(routes),
                "airportClassRouteCount": len(airport_class_routes),
                "serviceClassCounts": dict(sorted(class_counts.items())),
                "topAgencyCounts": dict(agency_counts.most_common(12)),
                "nearestStops": [
                    {
                        "busStopId": stop["busStopId"],
                        "name": stop["name"],
                        "distanceMeters": stop["distanceMeters"],
                        "routeCount": len(stop_routes.get(stop["busStopId"], set())),
                    }
                    for stop in matches[: args.top_stops]
                ],
                "airportClassRoutes": [
                    {
                        "busRouteId": route["busRouteId"],
                        "agencyName": route.get("agencyName") or "",
                        "label": route_label(route),
                    }
                    for route in airport_class_routes[:25]
                ],
                "documentedNoPublicBus": no_public_bus.get(airport["iata"]),
            }
        )

    airport_results.sort(key=lambda item: (item["status"], -item["flightCount"], item["iata"]))
    output = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "modelVersion": "v5_airport_bus_access_audit_v1",
        "sourceBusBundle": str(args.bus_bundle.relative_to(ROOT)) if args.bus_bundle.is_relative_to(ROOT) else str(args.bus_bundle),
        "sourceAirportMap": str(args.airport_map.relative_to(ROOT)) if args.airport_map.is_relative_to(ROOT) else str(args.airport_map),
        "summary": {
            "airportCount": len(airports),
            "eligibleBusStopCount": len(stops),
            "nearbyMeters": args.nearby_meters,
            "searchMeters": args.search_meters,
            "statusCounts": dict(sorted(status_counts.items())),
            "airportClassCoveredCount": status_counts["covered_by_gtfs_airport_bus"],
            "nearbyStopWithoutAirportClassCount": status_counts["nearby_gtfs_bus_stop_no_airport_class_route"],
            "noNearbyStopCount": status_counts["gtfs_bus_stop_within_search_radius_only"] + status_counts["no_gtfs_bus_stop_within_search_radius"],
            "documentedNoPublicBusCount": status_counts["documented_no_public_bus"],
            "undocumentedNoNearbyStopCount": status_counts["gtfs_bus_stop_within_search_radius_only"] + status_counts["no_gtfs_bus_stop_within_search_radius"],
        },
        "airports": airport_results,
        "notes": [
            "This audit uses GTFS bus feeds already present in the V5 bus bundle; missing coverage means missing from this source layer, not necessarily no real-world bus.",
            "Airport bus classification is a first-pass route text heuristic from the bus bundle. Airports with nearby local stops should be checked against official airport/operator pages.",
            "Search radius is wider than the default walking connector radius so remote-but-nearby stops can be reviewed before deciding source/parser work.",
        ],
    }
    write_json(args.output, output)
    print(json.dumps(output["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
