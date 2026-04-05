#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_bundle(stations: list[dict[str, Any]], routes: list[dict[str, Any]], trains_dataset: dict[str, Any]) -> dict[str, Any]:
    station_map = {station["id"]: station for station in stations}
    route_map = {route["id"]: route for route in routes}

    station_routes: dict[str, list[str]] = defaultdict(list)
    adjacency_map: dict[tuple[str, str], set[str]] = defaultdict(set)
    route_segments: list[dict[str, Any]] = []

    for route in routes:
        route_id = route["id"]
        ids = route["station_ids"]
        for station_id in ids:
            station_routes[station_id].append(route_id)
        for left, right in zip(ids, ids[1:]):
            key = tuple(sorted((left, right)))
            adjacency_map[key].add(route_id)
            route_segments.append(
                {
                    "route_id": route_id,
                    "from_station_id": left,
                    "to_station_id": right,
                }
            )

    bundle_stations: list[dict[str, Any]] = []
    interchange_station_ids: list[str] = []
    for station in stations:
        route_ids = station_routes.get(station["id"], [])
        bundle_station = dict(station)
        bundle_station["route_ids"] = sorted(route_ids)
        bundle_station["is_interchange"] = len(route_ids) > 1
        bundle_stations.append(bundle_station)
        if bundle_station["is_interchange"]:
            interchange_station_ids.append(station["id"])

    adjacency = [
        {
            "station_ids": [left, right],
            "route_ids": sorted(route_ids),
        }
        for (left, right), route_ids in sorted(adjacency_map.items())
    ]

    service_families = sorted(
        {
            train.get("service_name") or train.get("display_name")
            for train in trains_dataset["train_instances"]
            if train.get("service_name") or train.get("display_name")
        }
    )

    train_routes: dict[str, int] = defaultdict(int)
    for train in trains_dataset["train_instances"]:
        first_line_id = train["stop_times"][0]["line_id"]
        train_routes[first_line_id] += 1

    route_summary = []
    for route in routes:
        route_id = route["id"]
        line_id = route.get("line_id", route_id)
        route_summary.append(
            {
                "route_id": route_id,
                "name": route["name"],
                "color": route["color"],
                "station_count": len(route["station_ids"]),
                "train_count": train_routes.get(line_id, 0),
            }
        )

    return {
        "id": "shinkansen_v2_bundle",
        "label": "OniChase v2 Shinkansen map bundle",
        "version": "0.1.0",
        "stations": bundle_stations,
        "routes": routes,
        "route_segments": route_segments,
        "adjacency": adjacency,
        "interchange_station_ids": sorted(interchange_station_ids),
        "service_families": service_families,
        "route_summary": route_summary,
        "train_dataset_id": trains_dataset["id"],
        "train_count": len(trains_dataset["train_instances"]),
        "metadata": {
            "notes": [
                "Bundle for v2 playable client scaffolding.",
                "Coordinates are consumed from station lat/lon when available.",
                "Adjacency is route-based and engine-agnostic.",
            ]
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the OniChase v2 Shinkansen bundle.")
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
    print(f"Stations: {len(bundle['stations'])}")
    print(f"Routes: {len(bundle['routes'])}")
    print(f"Train count: {bundle['train_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
