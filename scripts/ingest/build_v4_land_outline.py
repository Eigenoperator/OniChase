#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries_jpn.geojson"
DEFAULT_OUTPUT = ROOT / "docs" / "data" / "v4_maplibre" / "japan_land.geojson"


def perpendicular_distance(point: list[float], start: list[float], end: list[float]) -> float:
    x, y = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    return abs(dy * x - dx * y + x2 * y1 - y2 * x1) / ((dx * dx + dy * dy) ** 0.5)


def simplify_line(points: list[list[float]], tolerance: float) -> list[list[float]]:
    if len(points) <= 2:
        return points
    max_distance = -1.0
    split_index = 0
    start = points[0]
    end = points[-1]
    for index in range(1, len(points) - 1):
        distance = perpendicular_distance(points[index], start, end)
        if distance > max_distance:
            max_distance = distance
            split_index = index
    if max_distance <= tolerance:
        return [start, end]
    left = simplify_line(points[: split_index + 1], tolerance)
    right = simplify_line(points[split_index:], tolerance)
    return left[:-1] + right


def simplify_ring(ring: list[list[float]], tolerance: float) -> list[list[float]]:
    if len(ring) <= 4:
        return ring
    closed = ring[0] == ring[-1]
    body = ring[:-1] if closed else ring
    simplified = simplify_line(body, tolerance)
    if len(simplified) < 3:
        simplified = body[:3]
    if simplified[0] != simplified[-1]:
        simplified.append(simplified[0])
    return [[round(point[0], 6), round(point[1], 6)] for point in simplified]


def simplify_geometry(geometry: dict[str, Any], tolerance: float) -> dict[str, Any]:
    kind = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if kind == "Polygon":
        return {
            "type": "Polygon",
            "coordinates": [
                simplified
                for ring in coords
                if len(simplified := simplify_ring(ring, tolerance)) >= 4
            ],
        }
    if kind == "MultiPolygon":
        polygons = []
        for polygon in coords:
            rings = [
                simplified
                for ring in polygon
                if len(simplified := simplify_ring(ring, tolerance)) >= 4
            ]
            if rings:
                polygons.append(rings)
        return {"type": "MultiPolygon", "coordinates": polygons}
    raise ValueError(f"Unsupported land geometry type: {kind}")


def download_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a lightweight Japan land outline layer for v4 MapLibre.")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--tolerance", type=float, default=0.006)
    args = parser.parse_args()

    source = download_json(args.source_url)
    features = []
    for feature in source.get("features", []):
        geometry = simplify_geometry(feature.get("geometry", {}), args.tolerance)
        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "name": "Japan",
                    "name_ja": "日本",
                    "source": "natural_earth_10m_admin_0_countries_jpn",
                    "source_url": args.source_url,
                },
            }
        )

    output = {
        "type": "FeatureCollection",
        "metadata": {
            "schema": "onichase.v4.japan_land_outline.v1",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "sourceUrl": args.source_url,
            "tolerance": args.tolerance,
        },
        "features": features,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote Japan land outline: {len(features)} feature(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
