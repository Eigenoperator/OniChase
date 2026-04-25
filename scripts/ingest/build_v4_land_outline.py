#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_URL = "https://www.geoboundaries.org/api/current/gbOpen/JPN/ADM0/"
DEFAULT_OUTPUT = ROOT / "docs" / "data" / "v4_maplibre" / "japan_land.geojson"
DEFAULT_OVERVIEW_OUTPUT = ROOT / "docs" / "data" / "v4_maplibre" / "japan_land_overview.geojson"


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
        return [[round(point[0], 6), round(point[1], 6)] for point in ring]
    closed = ring[0] == ring[-1]
    body = ring[:-1] if closed else ring
    simplified = body if tolerance <= 0 else simplify_line(body, tolerance)
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


def resolve_source(source_url: str) -> tuple[Any, str, str | None]:
    source = download_json(source_url)
    if isinstance(source, dict) and source.get("type") == "FeatureCollection":
        return source, source_url, None
    if isinstance(source, dict) and source.get("gjDownloadURL"):
        resolved_url = source["gjDownloadURL"]
        return download_json(resolved_url), resolved_url, source_url
    raise ValueError(f"Unsupported land source payload from {source_url}")


def is_japan_feature(feature: dict[str, Any], only_feature: bool) -> bool:
    if only_feature:
        return True
    properties = feature.get("properties", {})
    codes = {
        str(properties.get(key, "")).upper()
        for key in (
            "ADM0_A3",
            "ISO_A3",
            "SOV_A3",
            "boundaryISO",
            "shapeISO",
            "iso_3166_1_alpha_3_codes",
        )
    }
    names = {
        str(properties.get(key, "")).lower()
        for key in ("NAME", "NAME_EN", "ADMIN", "SOVEREIGNT", "boundaryName", "shapeName")
    }
    return "JPN" in codes or "japan" in names or "日本" in names


def count_coordinates(geometry: dict[str, Any]) -> int:
    kind = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if kind == "Polygon":
        return sum(len(ring) for ring in coords)
    if kind == "MultiPolygon":
        return sum(sum(len(ring) for ring in polygon) for polygon in coords)
    return 0


def build_output(
    source: dict[str, Any],
    *,
    source_url: str,
    metadata_url: str | None,
    tolerance: float,
    detail_level: str,
) -> dict[str, Any]:
    source_features = source.get("features", [])
    only_feature = len(source_features) == 1
    features = []
    for feature in source_features:
        if not is_japan_feature(feature, only_feature):
            continue
        geometry = simplify_geometry(feature.get("geometry", {}), tolerance)
        if count_coordinates(geometry) == 0:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "name": "Japan",
                    "name_ja": "日本",
                    "source": "geoboundaries_gbOpen_jpn_adm0",
                    "source_url": source_url,
                    **({"metadata_url": metadata_url} if metadata_url else {}),
                },
            }
        )
    if not features:
        raise ValueError("No Japan boundary features found in source")
    return {
        "type": "FeatureCollection",
        "metadata": {
            "schema": "onichase.v4.japan_land_outline.v2",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "sourceUrl": source_url,
            "metadataUrl": metadata_url,
            "detailLevel": detail_level,
            "tolerance": tolerance,
            "featureCount": len(features),
            "coordinateCount": sum(count_coordinates(feature["geometry"]) for feature in features),
        },
        "features": features,
    }


def write_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    metadata = payload["metadata"]
    print(
        f"Wrote Japan land {metadata['detailLevel']}: "
        f"{metadata['featureCount']} feature(s), {metadata['coordinateCount']} coordinates to {path}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build high-detail and overview Japan land outline layers for v4 MapLibre.")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overview-output", type=Path, default=DEFAULT_OVERVIEW_OUTPUT)
    parser.add_argument("--detail-tolerance", type=float, default=0.0)
    parser.add_argument("--overview-tolerance", type=float, default=0.018)
    args = parser.parse_args()

    source, source_url, metadata_url = resolve_source(args.source_url)
    write_output(
        args.output,
        build_output(
            source,
            source_url=source_url,
            metadata_url=metadata_url,
            tolerance=args.detail_tolerance,
            detail_level="detail",
        ),
    )
    write_output(
        args.overview_output,
        build_output(
            source,
            source_url=source_url,
            metadata_url=metadata_url,
            tolerance=args.overview_tolerance,
            detail_level="overview",
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
