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
    Path("data/v5_ship_map_to_193_official.json"),
]
OUT = Path("docs/data/v5_ship_map.geojson")
PORT_COORDINATE_OVERRIDES = Path("data/v5_ship_port_coordinates.json")
PORT_ALIASES = {
    # MLIT/source inventories sometimes use bare city/port names.  Keep the
    # gameplay node at the real ferry terminal name instead of creating a third
    # Takamatsu node beside 高松港 and 高松東港.
    "高松": "高松港",
}

SUPPLEMENTAL_PORTS = {
    "女木港": {
        "name": "女木港",
        "city": "高松市",
        "lat": 34.39041,
        "lon": 134.051989,
        "coordinateSource": "public_coordinate:女木港 latitude/longitude cross-check; official Meon ferry landing page address 香川県高松市女木町15-22",
        "coordinateStatus": "public_verified",
        "coordinateDisplayName": "女木港",
    },
}

SUPPLEMENTAL_ROUTES = [
    {
        "routeId": "meon_map_takamatsu_megijima",
        "routeGroupId": "meon_takamatsu_megijima_ogijima",
        "operator": "雌雄島海運",
        "routeName": "高松港～女木港",
        "origin": "高松港",
        "destination": "女木港",
        "sourceUrl": "https://meon.co.jp/access",
    },
    {
        "routeId": "meon_map_megijima_ogijima",
        "routeGroupId": "meon_takamatsu_megijima_ogijima",
        "operator": "雌雄島海運",
        "routeName": "女木港～男木",
        "origin": "女木港",
        "destination": "男木",
        "sourceUrl": "https://meon.co.jp/access",
    },
]


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


def canonical_port_name(name: str) -> str:
    return PORT_ALIASES.get(name, name)


def canonical_ports(source_ports: dict[str, dict], overrides: dict[str, dict]) -> dict[str, dict]:
    ports: dict[str, dict] = {}
    for raw_name, raw_port in source_ports.items():
        name = canonical_port_name(raw_name)
        port = port_with_override(name, raw_port, overrides)
        if name not in ports:
            ports[name] = port
    return ports


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
        ports = canonical_ports(source.get("ports", {}) or {}, port_overrides)
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
            origin_name = canonical_port_name(route["origin"])
            destination_name = canonical_port_name(route["destination"])
            origin = ports[origin_name]
            destination = ports[destination_name]
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
                        "origin": origin_name,
                        "destination": destination_name,
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
    supplemental_ports = canonical_ports(SUPPLEMENTAL_PORTS, port_overrides)
    for name, port in supplemental_ports.items():
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
    port_lookup = {
        feature["properties"]["name"]: {
            "lon": feature["geometry"]["coordinates"][0],
            "lat": feature["geometry"]["coordinates"][1],
        }
        for feature in features
        if feature.get("properties", {}).get("kind") == "port"
    }
    for route in SUPPLEMENTAL_ROUTES:
        origin_name = canonical_port_name(route["origin"])
        destination_name = canonical_port_name(route["destination"])
        origin = port_lookup.get(origin_name)
        destination = port_lookup.get(destination_name)
        if not origin or not destination:
            continue
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
                    "origin": origin_name,
                    "destination": destination_name,
                    "distanceKm": None,
                    "tripCount": 0,
                    "servicePatternCount": 0,
                    "dailyDirectionalTripCount": None,
                    "firstDepartureMinute": None,
                    "fareAdultJpy": None,
                    "fareNormalAdultJpy": None,
                    "farePeakAdultJpy": None,
                    "playableStatus": "supplemental_official_route_shape",
                    "sourceUrl": route.get("sourceUrl"),
                },
                "geometry": {"type": "LineString", "coordinates": line_for(origin, destination)},
            }
        )
    if SUPPLEMENTAL_ROUTES:
        route_group_count += 1
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
