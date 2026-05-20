#!/usr/bin/env python3
"""Build the V5 ship-map GeoJSON from promoted official ship source files."""

from __future__ import annotations

import json
from pathlib import Path


SOURCE_FILES = [
    Path("data/v5_ship_seikan_ferry_official.json"),
    Path("data/v5_ship_priority_batch_official.json"),
    Path("data/v5_ship_long_distance_batch_official.json"),
    Path("data/v5_ship_expansion_to_70_official.json"),
    Path("data/v5_ship_expansion_150_map_batch1_official.json"),
]
OUT = Path("docs/data/v5_ship_map.geojson")
PORT_COORDINATE_OVERRIDES = Path("data/v5_ship_port_coordinates.json")


def line_for(origin: dict, destination: dict) -> list[list[float]]:
    return [
        [origin["lon"], origin["lat"]],
        [destination["lon"], destination["lat"]],
    ]


def load_port_overrides() -> dict[str, dict]:
    if not PORT_COORDINATE_OVERRIDES.exists():
        return {}
    payload = json.loads(PORT_COORDINATE_OVERRIDES.read_text(encoding="utf-8"))
    return payload.get("ports") or {}


def coordinate_summary(features: list[dict]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for feature in features:
        props = feature.get("properties") or {}
        if props.get("kind") != "port":
            continue
        status = props.get("coordinateStatus") or "source_seed"
        summary[status] = summary.get(status, 0) + 1
    return summary


def port_with_override(name: str, port: dict, overrides: dict[str, dict]) -> dict:
    override = overrides.get(name)
    if not override:
        return port
    merged = dict(port)
    merged["lat"] = override.get("lat", port.get("lat"))
    merged["lon"] = override.get("lon", port.get("lon"))
    merged["coordinateSource"] = override.get("source", port.get("coordinateSource"))
    merged["coordinateStatus"] = override.get("status")
    merged["coordinateQuery"] = override.get("query")
    merged["coordinateDisplayName"] = (override.get("osm") or {}).get("displayName")
    return merged


def main() -> None:
    features = []
    port_seen = set()
    route_count = 0
    route_group_count = 0
    trip_count = 0
    sources = []
    port_overrides = load_port_overrides()
    for path in SOURCE_FILES:
        if not path.exists():
            continue
        source = json.loads(path.read_text(encoding="utf-8"))
        sources.append(str(path))
        route_group_count += int(source.get("summary", {}).get("routeGroupCount") or 1)
        ports = {
            name: port_with_override(name, port, port_overrides)
            for name, port in (source.get("ports", {}) or {}).items()
        }
        for name, port in ports.items():
            if name in port_seen:
                continue
            port_seen.add(name)
            features.append(
                {
                    "type": "Feature",
                    "id": f"port:{name}",
                    "properties": {
                        "kind": "port",
                        "name": name,
                        "city": port.get("city"),
                        "coordinateSource": port.get("coordinateSource"),
                        "coordinateStatus": port.get("coordinateStatus"),
                        "coordinateQuery": port.get("coordinateQuery"),
                        "coordinateDisplayName": port.get("coordinateDisplayName"),
                    },
                    "geometry": {"type": "Point", "coordinates": [port["lon"], port["lat"]]},
                }
            )
        trips_by_route = {}
        for trip in source.get("trips", []):
            trips_by_route.setdefault(trip["routeId"], []).append(trip)
        for route in source.get("routes", []):
            origin = ports[route["origin"]]
            destination = ports[route["destination"]]
            route_trips = trips_by_route.get(route["routeId"], [])
            service_patterns = route.get("servicePatterns") or []
            fare = route.get("fare") or {}
            adult_fare = fare.get("adultPassengerFare") or {}
            trip_count += len(route_trips)
            route_count += 1
            features.append(
                {
                    "type": "Feature",
                    "id": f"ship-route:{route['routeId']}",
                    "properties": {
                        "kind": "ship-route",
                        "routeId": route["routeId"],
                        "routeName": route["routeName"],
                        "operator": route["operator"],
                        "routeGroupId": route.get("routeGroupId"),
                        "origin": route["origin"],
                        "destination": route["destination"],
                        "distanceKm": route.get("distanceKm"),
                        "tripCount": len(route_trips),
                        "servicePatternCount": len(service_patterns),
                        "dailyDirectionalTripCount": max((pattern.get("dailyDirectionalTripCount", 0) for pattern in service_patterns), default=None),
                        "firstDepartureMinute": min((trip["departureMinute"] for trip in route_trips), default=None),
                        "fareAdultJpy": adult_fare.get("amount"),
                        "fareNormalAdultJpy": adult_fare.get("normalSeason", {}).get("amount"),
                        "farePeakAdultJpy": adult_fare.get("peakSeason", {}).get("amount"),
                        "playableStatus": route.get("playablePromotionStatus") or source.get("summary", {}).get("playablePromotionStatus"),
                    },
                    "geometry": {"type": "LineString", "coordinates": line_for(origin, destination)},
                }
            )
    payload = {
        "type": "FeatureCollection",
        "metadata": {
            "schema": "onichase.v5.ship_map.1",
            "source": "official_ship_sources",
            "sourceFiles": sources,
            "portCount": len(port_seen),
            "routeGroupCount": route_group_count,
            "routeCount": route_count,
            "tripCount": trip_count,
            "coordinateSummary": coordinate_summary(features),
            "note": "Ship map contains official promoted source data. Boarding remains disabled until gameplay connector integration is implemented.",
        },
        "features": features,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ports={len(port_seen)} routes={route_count} trips={trip_count}")


if __name__ == "__main__":
    main()
