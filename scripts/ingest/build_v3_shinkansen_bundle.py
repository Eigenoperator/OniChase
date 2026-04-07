#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SERVICE_ROUTE_DEFS = {
    "SHINKANSEN_TOKAIDO_SANYO": {
        "id": "TOKAIDO_SANYO",
        "short_name": "Tokaido-Sanyo",
        "long_name": "Tokaido-Sanyo Shinkansen Services",
        "color": "#1f78ff",
        "physical_routes": ["TOKAIDO", "SANYO"],
    },
    "SHINKANSEN_TOHOKU_HOKKAIDO": {
        "id": "TOHOKU_HOKKAIDO",
        "short_name": "Tohoku-Hokkaido",
        "long_name": "Tohoku-Hokkaido Shinkansen Services",
        "color": "#2d9c5b",
        "physical_routes": ["TOHOKU", "HOKKAIDO"],
    },
    "SHINKANSEN_HOKURIKU": {
        "id": "HOKURIKU",
        "short_name": "Hokuriku",
        "long_name": "Hokuriku Shinkansen Services",
        "color": "#2c62c9",
        "physical_routes": ["HOKURIKU"],
    },
    "SHINKANSEN_JOETSU": {
        "id": "JOETSU",
        "short_name": "Joetsu",
        "long_name": "Joetsu Shinkansen Services",
        "color": "#e65045",
        "physical_routes": ["JOETSU"],
    },
    "SHINKANSEN_KYUSHU": {
        "id": "KYUSHU",
        "short_name": "Kyushu",
        "long_name": "Kyushu Shinkansen Services",
        "color": "#de4b39",
        "physical_routes": ["KYUSHU"],
    },
    "SHINKANSEN_NISHI_KYUSHU": {
        "id": "NISHI_KYUSHU",
        "short_name": "Nishi-Kyushu",
        "long_name": "Nishi-Kyushu Shinkansen Services",
        "color": "#7c4dff",
        "physical_routes": ["NISHI_KYUSHU"],
    },
    "SHINKANSEN_YAMAGATA": {
        "id": "YAMAGATA",
        "short_name": "Yamagata",
        "long_name": "Yamagata Shinkansen Services",
        "color": "#f09b20",
        "physical_routes": ["YAMAGATA"],
    },
    "SHINKANSEN_AKITA": {
        "id": "AKITA",
        "short_name": "Akita",
        "long_name": "Akita Shinkansen Services",
        "color": "#d54a96",
        "physical_routes": ["AKITA"],
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def station_group_id(station_id: str) -> str:
    return f"SG_{station_id}"


def physical_station_id(station_id: str) -> str:
    return f"PS_{station_id}"


def game_node_id(station_id: str) -> str:
    return f"GN_{station_id}"


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def dedupe_station_sequence(station_ids: list[str]) -> list[str]:
    output: list[str] = []
    for station_id in station_ids:
        if output and output[-1] == station_id:
            continue
        output.append(station_id)
    return output


def combined_route_station_ids(route_map: dict[str, dict[str, Any]], route_ids: list[str]) -> list[str]:
    result: list[str] = []
    for idx, route_id in enumerate(route_ids):
        part = route_map[route_id]["station_ids"]
        if idx and result and part and result[-1] == part[0]:
            result.extend(part[1:])
        else:
            result.extend(part)
    return dedupe_station_sequence(result)


def build_bundle(stations: list[dict[str, Any]], routes: list[dict[str, Any]], trains_dataset: dict[str, Any]) -> dict[str, Any]:
    station_map = {station["id"]: station for station in stations}
    route_map = {route["id"]: route for route in routes}

    physical_stations = []
    station_groups = []
    label_representations = []
    game_nodes = []

    for station in stations:
        sid = station["id"]
        sgid = station_group_id(sid)
        psid = physical_station_id(sid)
        physical_stations.append(
            {
                "id": psid,
                "name": station["name"],
                "names": station.get("names", {}),
                "operatorIds": [],
                "lat": station["lat"],
                "lon": station["lon"],
                "sourceStopIds": [sid],
                "stationGroupId": sgid,
                "tags": [station.get("category", "normal"), "shinkansen"],
            }
        )
        station_groups.append(
            {
                "id": sgid,
                "primaryName": station["name"],
                "names": station.get("names", {}),
                "physicalStationIds": [psid],
                "centroid": {"lat": station["lat"], "lon": station["lon"]},
                "category": "hub" if station.get("category") == "hub" else "normal",
                "labelRank": 100 if station.get("category") == "hub" else 50,
                "tags": ["shinkansen"],
            }
        )
        label_representations.append(
            {
                "stationGroupId": sgid,
                "minZoom": 4 if station.get("category") == "hub" else 6,
                "maxZoom": 24,
                "labelRank": 100 if station.get("category") == "hub" else 50,
                "displayNameJa": station.get("names", {}).get("ja"),
                "displayNameEn": station.get("names", {}).get("en", station["name"]),
                "labelPoint": {"lat": station["lat"], "lon": station["lon"]},
            }
        )
        game_nodes.append(
            {
                "id": game_node_id(sid),
                "stationGroupIds": [sgid],
                "primaryStationGroupId": sgid,
                "category": "hub" if station.get("category") == "hub" else "normal",
                "revealName": station["name"],
                "tags": ["shinkansen"],
            }
        )

    track_centerlines = []
    for route in routes:
        polyline = [{"lat": station_map[sid]["lat"], "lon": station_map[sid]["lon"]} for sid in route["station_ids"]]
        track_centerlines.append(
            {
                "id": f"TRACK_{route['id']}",
                "operatorId": "JAPAN_SHINKANSEN",
                "lineName": route["name"],
                "mode": "shinkansen",
                "polyline": polyline,
                "stationGroupIds": [station_group_id(sid) for sid in route["station_ids"]],
                "tags": ["track_centerline"],
            }
        )

    service_routes = []
    service_patterns = []
    service_geometry = []
    service_route_station_ids: dict[str, list[str]] = {}
    for line_id, cfg in SERVICE_ROUTE_DEFS.items():
        station_ids = combined_route_station_ids(route_map, cfg["physical_routes"])
        service_route_station_ids[cfg["id"]] = station_ids
        service_routes.append(
            {
                "id": cfg["id"],
                "operatorId": "JAPAN_SHINKANSEN",
                "shortName": cfg["short_name"],
                "longName": cfg["long_name"],
                "color": cfg["color"],
                "textColor": "#ffffff",
                "mode": "shinkansen",
            }
        )
        service_patterns.append(
            {
                "id": f"PATTERN_{cfg['id']}",
                "routeId": cfg["id"],
                "label": cfg["short_name"],
                "stationGroupIds": [station_group_id(sid) for sid in station_ids],
                "shapeId": f"GEOM_SERVICE_{cfg['id']}",
                "tags": ["pilot_pattern"],
            }
        )
        polyline = [{"lat": station_map[sid]["lat"], "lon": station_map[sid]["lon"]} for sid in station_ids]
        service_geometry.append(
            {
                "id": f"GEOM_CORRIDOR_{cfg['id']}",
                "routeId": cfg["id"],
                "representation": "corridor",
                "minZoom": 0,
                "maxZoom": 7,
                "polyline": polyline,
                "offsetRank": 0,
            }
        )
        service_geometry.append(
            {
                "id": f"GEOM_SERVICE_{cfg['id']}",
                "routeId": cfg["id"],
                "representation": "service_path",
                "minZoom": 7,
                "maxZoom": 24,
                "polyline": polyline,
                "offsetRank": 0,
            }
        )

    trip_instances = []
    for index, train in enumerate(trains_dataset["train_instances"], start=1):
        line_id = train["stop_times"][0]["line_id"]
        route_cfg = SERVICE_ROUTE_DEFS.get(line_id)
        if not route_cfg:
          continue
        route_id = route_cfg["id"]
        stop_times = []
        cumulative = 0.0
        previous_station = None
        for stop in train["stop_times"]:
            station_id = stop["station_id"]
            station = station_map.get(station_id)
            if not station:
                continue
            if previous_station is not None:
                prev = station_map[previous_station]
                cumulative += haversine_meters(prev["lat"], prev["lon"], station["lat"], station["lon"])
            arrival = stop.get("arrival_hhmm") or stop.get("departure_hhmm")
            departure = stop.get("departure_hhmm") or stop.get("arrival_hhmm")
            hhmm_to_sec = lambda value: int(value[:2]) * 3600 + int(value[3:5]) * 60
            stop_times.append(
                {
                    "sequence": stop["sequence"],
                    "stationGroupId": station_group_id(station_id),
                    "physicalStationId": physical_station_id(station_id),
                    "arrivalTimeSec": hhmm_to_sec(arrival),
                    "departureTimeSec": hhmm_to_sec(departure),
                    "shapeDistTraveled": round(cumulative, 3),
                }
            )
            previous_station = station_id

        trip_instances.append(
            {
                "id": f"TRIP_{index:05d}",
                "routeId": route_id,
                "servicePatternId": f"PATTERN_{route_id}",
                "serviceName": train.get("service_name"),
                "serviceNumber": train.get("service_number"),
                "operatorId": "JAPAN_SHINKANSEN",
                "directionId": train.get("direction_label"),
                "stopTimes": stop_times,
            }
        )

    return {
        "version": "0.1.0",
        "generatedAt": "2026-04-06T00:00:00Z",
        "metadata": {
            "label": "OniChase v3 nationwide Shinkansen pilot bundle",
            "sourceVersion": "v2-shinkansen-upgrade",
            "notes": [
                "First v3 pilot bundle built from existing nationwide Shinkansen data.",
                "Station groups remain one-to-one with physical stations in this pilot.",
                "Service geometry is route-family based and multi-scale ready.",
            ],
        },
        "physicalStations": physical_stations,
        "stationGroups": station_groups,
        "trackCenterlines": track_centerlines,
        "pathways": [],
        "serviceRoutes": service_routes,
        "servicePatterns": service_patterns,
        "tripInstances": trip_instances,
        "serviceGeometry": service_geometry,
        "labelRepresentations": label_representations,
        "gameNodes": game_nodes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the OniChase v3 Shinkansen pilot bundle.")
    parser.add_argument("--stations", required=True)
    parser.add_argument("--routes", required=True)
    parser.add_argument("--trains", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    stations = load_json(Path(args.stations))
    routes = load_json(Path(args.routes))
    trains = load_json(Path(args.trains))

    bundle = build_bundle(stations, routes, trains)
    output_path = Path(args.output)
    output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote: {output_path}")
    print(f"Physical stations: {len(bundle['physicalStations'])}")
    print(f"Service routes: {len(bundle['serviceRoutes'])}")
    print(f"Trip instances: {len(bundle['tripInstances'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
