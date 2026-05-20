#!/usr/bin/env python3
"""Build the V5 ship-map GeoJSON from promoted official ship source files."""

from __future__ import annotations

import json
from pathlib import Path


SOURCE_FILES = [
    Path("data/v5_ship_seikan_ferry_official.json"),
    Path("data/v5_ship_priority_batch_official.json"),
    Path("data/v5_ship_long_distance_batch_official.json"),
]
OUT = Path("docs/data/v5_ship_map.geojson")


def line_for(origin: dict, destination: dict) -> list[list[float]]:
    return [
        [origin["lon"], origin["lat"]],
        [destination["lon"], destination["lat"]],
    ]


def main() -> None:
    features = []
    port_seen = set()
    route_count = 0
    route_group_count = 0
    trip_count = 0
    sources = []
    for path in SOURCE_FILES:
        if not path.exists():
            continue
        source = json.loads(path.read_text(encoding="utf-8"))
        sources.append(str(path))
        route_group_count += int(source.get("summary", {}).get("routeGroupCount") or 1)
        ports = source.get("ports", {})
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
            "note": "Ship map contains official promoted source data. Boarding remains disabled until gameplay connector integration is implemented.",
        },
        "features": features,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ports={len(port_seen)} routes={route_count} trips={trip_count}")


if __name__ == "__main__":
    main()
