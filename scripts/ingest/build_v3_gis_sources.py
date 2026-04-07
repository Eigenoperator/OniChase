#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def line_bbox(polyline: list[dict]) -> list[float]:
    lons = [point["lon"] for point in polyline]
    lats = [point["lat"] for point in polyline]
    return [min(lons), min(lats), max(lons), max(lats)]


def build_sources(bundle: dict) -> dict[str, dict]:
    label_map = {entry["stationGroupId"]: entry for entry in bundle["labelRepresentations"]}

    stations = []
    for station in bundle["physicalStations"]:
        label = label_map.get(station["stationGroupId"], {})
        stations.append(
            {
                "type": "Feature",
                "id": station["id"],
                "geometry": {
                    "type": "Point",
                    "coordinates": [station["lon"], station["lat"]],
                },
                "properties": {
                    "id": station["id"],
                    "station_group_id": station["stationGroupId"],
                    "name_en": label.get("displayNameEn", station["name"]),
                    "name_ja": label.get("displayNameJa", station["name"]),
                    "label_rank": label.get("labelRank", 50),
                    "tags": station.get("tags", []),
                },
            }
        )

    track_centerlines = []
    for line in bundle["trackCenterlines"]:
        track_centerlines.append(
            {
                "type": "Feature",
                "id": line["id"],
                "bbox": line_bbox(line["polyline"]),
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[point["lon"], point["lat"]] for point in line["polyline"]],
                },
                "properties": {
                    "id": line["id"],
                    "line_name": line["lineName"],
                    "station_group_ids": line["stationGroupIds"],
                    "mode": line["mode"],
                    "operator_id": line["operatorId"],
                    "tags": line.get("tags", []),
                },
            }
        )

    route_map = {route["id"]: route for route in bundle["serviceRoutes"]}
    service_paths = []
    for geometry in bundle["serviceGeometry"]:
        route = route_map[geometry["routeId"]]
        service_paths.append(
            {
                "type": "Feature",
                "id": geometry["id"],
                "bbox": line_bbox(geometry["polyline"]),
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[point["lon"], point["lat"]] for point in geometry["polyline"]],
                },
                "properties": {
                    "id": geometry["id"],
                    "route_id": geometry["routeId"],
                    "route_name": route["shortName"],
                    "route_color": route["color"],
                    "route_text_color": route["textColor"],
                    "representation": geometry["representation"],
                    "min_zoom": geometry["minZoom"],
                    "max_zoom": geometry["maxZoom"],
                    "offset_rank": geometry.get("offsetRank", 0),
                },
            }
        )

    return {
        "stations": feature_collection(stations),
        "track_centerlines": feature_collection(track_centerlines),
        "service_paths": feature_collection(service_paths),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    sources = build_sources(bundle)
    for name, fc in sources.items():
      (output_dir / f"{name}.geojson").write_text(json.dumps(fc, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "version": 1,
        "bundleGeneratedAt": bundle["generatedAt"],
        "layers": {
            name: {
                "path": f"{name}.geojson",
                "featureCount": len(fc["features"]),
                "geometryType": fc["features"][0]["geometry"]["type"] if fc["features"] else None,
            }
            for name, fc in sources.items()
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote GIS sources to {output_dir}")


if __name__ == "__main__":
    main()
