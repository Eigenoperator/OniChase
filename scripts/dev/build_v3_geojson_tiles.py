#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


JAPAN_BOUNDS = {
    "min_lon": 128.0,
    "max_lon": 146.5,
    "min_lat": 30.0,
    "max_lat": 46.5,
}


def feature_bbox(feature: dict) -> tuple[float, float, float, float]:
    if "bbox" in feature:
        min_lon, min_lat, max_lon, max_lat = feature["bbox"]
        return min_lon, min_lat, max_lon, max_lat
    coords = feature["geometry"]["coordinates"]
    if feature["geometry"]["type"] == "Point":
        lon, lat = coords
        return lon, lat, lon, lat
    lons = [point[0] for point in coords]
    lats = [point[1] for point in coords]
    return min(lons), min(lats), max(lons), max(lats)


def tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    cols = 2 ** z
    rows = 2 ** z
    lon_span = JAPAN_BOUNDS["max_lon"] - JAPAN_BOUNDS["min_lon"]
    lat_span = JAPAN_BOUNDS["max_lat"] - JAPAN_BOUNDS["min_lat"]
    min_lon = JAPAN_BOUNDS["min_lon"] + lon_span * (x / cols)
    max_lon = JAPAN_BOUNDS["min_lon"] + lon_span * ((x + 1) / cols)
    max_lat = JAPAN_BOUNDS["max_lat"] - lat_span * (y / rows)
    min_lat = JAPAN_BOUNDS["max_lat"] - lat_span * ((y + 1) / rows)
    return min_lon, min_lat, max_lon, max_lat


def intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--min-zoom", type=int, default=3)
    parser.add_argument("--max-zoom", type=int, default=6)
    args = parser.parse_args()

    manifest: dict[str, dict] = {"version": 1, "layers": {}}
    layers = ["stations", "track_centerlines", "service_paths"]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for layer_name in layers:
        source_path = args.source_dir / f"{layer_name}.geojson"
        fc = json.loads(source_path.read_text(encoding="utf-8"))
        features = fc["features"]
        manifest["layers"][layer_name] = {"zooms": {}}
        layer_dir = args.output_dir / layer_name
        layer_dir.mkdir(parents=True, exist_ok=True)

        feature_boxes = [(feature, feature_bbox(feature)) for feature in features]

        for z in range(args.min_zoom, args.max_zoom + 1):
            cols = rows = 2 ** z
            count = 0
            for x in range(cols):
                for y in range(rows):
                    bounds = tile_bounds(z, x, y)
                    included = [feature for feature, bbox in feature_boxes if intersects(bbox, bounds)]
                    if not included:
                        continue
                    tile_dir = layer_dir / str(z) / str(x)
                    tile_dir.mkdir(parents=True, exist_ok=True)
                    tile_path = tile_dir / f"{y}.geojson"
                    tile_path.write_text(json.dumps({"type": "FeatureCollection", "features": included}, ensure_ascii=False), encoding="utf-8")
                    count += 1
            manifest["layers"][layer_name]["zooms"][str(z)] = {"tileCount": count}

    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote tile-ready GeoJSON pyramid to {args.output_dir}")


if __name__ == "__main__":
    main()
