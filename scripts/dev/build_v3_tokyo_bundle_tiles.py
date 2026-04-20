#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUNDLE = ROOT / "data" / "v3_tokyo_bundle.json.gz"
DEFAULT_SOURCE_DIR = ROOT / "data" / "v3_tokyo_tile_source"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "data" / "v3_tokyo_tiles"


def load_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_geojson(path: Path, features: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def line_feature(feature_id: str, properties: dict[str, Any], polyline: list[dict[str, Any]]) -> dict[str, Any] | None:
    coordinates = [
        [point.get("lon"), point.get("lat")]
        for point in polyline
        if isinstance(point.get("lon"), (int, float)) and isinstance(point.get("lat"), (int, float))
    ]
    if len(coordinates) < 2:
        return None
    lons = [point[0] for point in coordinates]
    lats = [point[1] for point in coordinates]
    return {
        "type": "Feature",
        "bbox": [min(lons), min(lats), max(lons), max(lats)],
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "properties": {"id": feature_id, **properties},
    }


def build_source_geojson(bundle: dict[str, Any], source_dir: Path) -> dict[str, int]:
    if source_dir.exists():
        shutil.rmtree(source_dir)
    source_dir.mkdir(parents=True, exist_ok=True)

    group_by_id = {group["id"]: group for group in bundle.get("stationGroups", [])}
    route_by_id = {route["id"]: route for route in bundle.get("serviceRoutes", [])}

    station_features = []
    for station in bundle.get("physicalStations", []):
        lon = station.get("lon")
        lat = station.get("lat")
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            continue
        group = group_by_id.get(station.get("stationGroupId"), {})
        station_features.append({
            "type": "Feature",
            "bbox": [lon, lat, lon, lat],
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id": station.get("id"),
                "station_group_id": station.get("stationGroupId"),
                "name_en": station.get("names", {}).get("en") or station.get("name"),
                "name_ja": station.get("names", {}).get("ja") or station.get("name"),
                "label_rank": group.get("labelRank", 50),
                "tags": station.get("tags", []),
            },
        })

    track_features = []
    for track in bundle.get("trackCenterlines", []):
        feature = line_feature(track.get("id") or "track", {
            "line_name": track.get("lineName"),
            "station_group_ids": track.get("stationGroupIds", []),
            "mode": track.get("mode"),
            "operator_id": track.get("operatorId"),
            "tags": track.get("tags", []),
        }, track.get("polyline", []))
        if feature:
            track_features.append(feature)

    service_features = []
    for geometry in bundle.get("serviceGeometry", []):
        route = route_by_id.get(geometry.get("routeId"), {})
        feature = line_feature(geometry.get("id") or "service", {
            "route_id": geometry.get("routeId"),
            "route_name": route.get("shortName"),
            "route_color": route.get("color"),
            "route_text_color": route.get("textColor"),
            "representation": geometry.get("representation"),
            "min_zoom": geometry.get("minZoom", 0),
            "max_zoom": geometry.get("maxZoom", 24),
            "offset_rank": geometry.get("offsetRank", 0),
        }, geometry.get("polyline", []))
        if feature:
            service_features.append(feature)

    write_geojson(source_dir / "stations.geojson", station_features)
    write_geojson(source_dir / "track_centerlines.geojson", track_features)
    write_geojson(source_dir / "service_paths.geojson", service_features)
    return {
        "stations": len(station_features),
        "track_centerlines": len(track_features),
        "service_paths": len(service_features),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-zoom", type=int, default=3)
    parser.add_argument("--max-zoom", type=int, default=6)
    args = parser.parse_args()

    bundle = load_json(args.bundle)
    counts = build_source_geojson(bundle, args.source_dir)
    if args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "dev" / "build_v3_geojson_tiles.py"),
        "--source-dir",
        str(args.source_dir),
        "--output-dir",
        str(args.output_dir),
        "--min-zoom",
        str(args.min_zoom),
        "--max-zoom",
        str(args.max_zoom),
    ]
    subprocess.run(cmd, check=True)
    print(json.dumps({
        "bundle": str(args.bundle.relative_to(ROOT)) if args.bundle.is_relative_to(ROOT) else str(args.bundle),
        "source_dir": str(args.source_dir.relative_to(ROOT)) if args.source_dir.is_relative_to(ROOT) else str(args.source_dir),
        "output_dir": str(args.output_dir.relative_to(ROOT)) if args.output_dir.is_relative_to(ROOT) else str(args.output_dir),
        **counts,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
