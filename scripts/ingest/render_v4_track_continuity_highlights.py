#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUNDLE = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_track_continuity_audit.json"
DEFAULT_LAND = ROOT / "docs" / "data" / "v4_maplibre" / "japan_land.geojson"
DEFAULT_OVERVIEW = ROOT / "docs" / "data" / "v4_maplibre" / "track_overview.geojson"
DEFAULT_HIGHLIGHT_GEOJSON = ROOT / "docs" / "data" / "v4_maplibre" / "track_continuity_highlights.geojson"
DEFAULT_SVG = ROOT / "docs" / "data" / "v4_track_continuity_highlights.svg"

COLORS = [
    "#E63946",
    "#F97316",
    "#EAB308",
    "#22C55E",
    "#14B8A6",
    "#06B6D4",
    "#3B82F6",
    "#6366F1",
    "#8B5CF6",
    "#D946EF",
    "#EC4899",
    "#A16207",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_bundle(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def simplify_points(points: list[list[float]], step: int) -> list[list[float]]:
    if len(points) <= 2 or step <= 1:
        return points
    reduced = points[::step]
    if reduced[-1] != points[-1]:
        reduced.append(points[-1])
    return reduced


def bbox_for_segments(segments: list[list[list[float]]]) -> list[float]:
    lons = [point[0] for segment in segments for point in segment]
    lats = [point[1] for segment in segments for point in segment]
    return [min(lons), min(lats), max(lons), max(lats)]


def build_highlight_features(bundle: dict[str, Any], audit: dict[str, Any]) -> list[dict[str, Any]]:
    tracks_by_line: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for track in bundle.get("trackCenterlines", []):
        tracks_by_line.setdefault((track["operatorId"], track["lineName"]), []).append(track)

    features = []
    for index, item in enumerate(audit.get("multiComponentLineSamples", []), start=1):
        tracks = tracks_by_line.get((item["operatorId"], item["lineName"]), [])
        segments = [track["points"] for track in tracks if len(track.get("points", [])) >= 2]
        if not segments:
            continue
        bbox = bbox_for_segments(segments)
        color = COLORS[(index - 1) % len(COLORS)]
        features.append(
            {
                "type": "Feature",
                "id": f"CONTINUITY_{index:02d}",
                "geometry": {"type": "MultiLineString", "coordinates": segments},
                "properties": {
                    "index": index,
                    "operator_id": item["operatorId"],
                    "operator_name": item["operatorName"],
                    "line_name": item["lineName"],
                    "component_count": item["componentCount"],
                    "track_centerline_count": item["trackCenterlineCount"],
                    "color": color,
                    "bbox": bbox,
                    "label": f"{index}. {item['operatorName']} / {item['lineName']}",
                },
            }
        )
    return features


def write_highlight_geojson(path: Path, features: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "type": "FeatureCollection",
        "features": features,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def projected_bounds(features: list[dict[str, Any]]) -> list[float]:
    boxes = [feature["properties"]["bbox"] for feature in features]
    min_lon = min(box[0] for box in boxes)
    min_lat = min(box[1] for box in boxes)
    max_lon = max(box[2] for box in boxes)
    max_lat = max(box[3] for box in boxes)
    return [min_lon - 0.8, min_lat - 0.7, max_lon + 0.8, max_lat + 0.7]


def path_for_line(points: list[list[float]], project) -> str:
    if not points:
        return ""
    commands = []
    for index, point in enumerate(points):
        x, y = project(point)
        commands.append(("M" if index == 0 else "L") + f"{x:.1f},{y:.1f}")
    return " ".join(commands)


def iter_lines_from_geometry(geometry: dict[str, Any]) -> list[list[list[float]]]:
    kind = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if kind == "LineString":
        return [coords]
    if kind == "MultiLineString":
        return coords
    if kind == "Polygon":
        return coords
    if kind == "MultiPolygon":
        return [ring for polygon in coords for ring in polygon]
    return []


def render_svg(
    path: Path,
    land: dict[str, Any],
    overview: dict[str, Any],
    highlights: list[dict[str, Any]],
) -> None:
    width = 1800
    height = 1280
    map_width = 1300
    margin = 44
    legend_x = 1340
    legend_y = 132
    bounds = projected_bounds(highlights)
    min_lon, min_lat, max_lon, max_lat = bounds
    lon_span = max_lon - min_lon
    lat_span = max_lat - min_lat

    def project(point: list[float]) -> tuple[float, float]:
        lon, lat = point
        x = margin + (lon - min_lon) / lon_span * (map_width - margin * 2)
        y = margin + (max_lat - lat) / lat_span * (height - margin * 2)
        return x, y

    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        '<clipPath id="mapClip"><rect x="0" y="0" width="1300" height="1280" rx="0"/></clipPath>',
        '<style><![CDATA[text{font-family:"Avenir Next","Yu Gothic",sans-serif}.label{font-size:20px;font-weight:800;fill:#172333}.small{font-size:14px;fill:#64748b}.legend-title{font-size:24px;font-weight:900;fill:#172333}.legend-line{font-size:15px;font-weight:800;fill:#172333}.legend-meta{font-size:12px;font-weight:700;fill:#64748b}]]></style>',
        "</defs>",
        '<rect width="1800" height="1280" fill="#f4f8fa"/>',
        '<rect x="0" y="0" width="1300" height="1280" fill="#eef4f6"/>',
    ]

    svg.append('<g clip-path="url(#mapClip)">')
    svg.append('<g fill="none" stroke="#b8c8cf" stroke-width="1.1" stroke-opacity="0.72">')
    for feature in land.get("features", []):
        for ring in iter_lines_from_geometry(feature.get("geometry", {})):
            d = path_for_line(simplify_points(ring, 6), project)
            if d:
                svg.append(f'<path d="{d}" />')
    svg.append("</g>")

    svg.append('<g fill="none" stroke="#9baab7" stroke-width="0.55" stroke-opacity="0.18">')
    for feature in overview.get("features", []):
        for segment in iter_lines_from_geometry(feature.get("geometry", {})):
            d = path_for_line(simplify_points(segment, 2), project)
            if d:
                svg.append(f'<path d="{d}" />')
    svg.append("</g>")

    for feature in highlights:
        color = feature["properties"]["color"]
        svg.append(f'<g fill="none" stroke="{color}" stroke-linecap="round" stroke-linejoin="round">')
        for segment in feature["geometry"]["coordinates"]:
            d = path_for_line(simplify_points(segment, 2), project)
            if d:
                svg.append(f'<path d="{d}" stroke="#ffffff" stroke-width="6.8" stroke-opacity="0.86"/>')
                svg.append(f'<path d="{d}" stroke="{color}" stroke-width="3.3" stroke-opacity="0.98"/>')
        svg.append("</g>")

    for feature in highlights:
        index = feature["properties"]["index"]
        color = feature["properties"]["color"]
        box = feature["properties"]["bbox"]
        x, y = project([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="15" fill="{color}" stroke="#ffffff" stroke-width="4"/>')
        svg.append(f'<text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" font-size="15" font-weight="900" fill="#ffffff">{index}</text>')
    svg.append("</g>")

    svg.extend(
        [
            '<rect x="1300" y="0" width="500" height="1280" fill="#ffffff"/>',
            '<text x="1340" y="58" class="legend-title">V4 Track Continuity Audit</text>',
            '<text x="1340" y="86" class="small">12 multi-component operator-line pairs highlighted</text>',
            '<text x="1340" y="108" class="small">Gray: all nationwide railway overview</text>',
        ]
    )

    for offset, feature in enumerate(highlights):
        y = legend_y + offset * 88
        props = feature["properties"]
        color = props["color"]
        label = f"{props['index']}. {props['operator_name']} / {props['line_name']}"
        meta = f"{props['component_count']} components · {props['track_centerline_count']} track segments"
        svg.append(f'<circle cx="{legend_x + 12}" cy="{y - 5}" r="10" fill="{color}"/>')
        svg.append(f'<text x="{legend_x + 32}" y="{y}" class="legend-line">{html.escape(label)}</text>')
        svg.append(f'<text x="{legend_x + 32}" y="{y + 22}" class="legend-meta">{html.escape(meta)}</text>')
    svg.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render v4 track continuity highlights as GeoJSON and SVG.")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--land", type=Path, default=DEFAULT_LAND)
    parser.add_argument("--overview", type=Path, default=DEFAULT_OVERVIEW)
    parser.add_argument("--geojson-output", type=Path, default=DEFAULT_HIGHLIGHT_GEOJSON)
    parser.add_argument("--svg-output", type=Path, default=DEFAULT_SVG)
    args = parser.parse_args()

    bundle = load_bundle(args.bundle)
    audit = load_json(args.audit)
    land = load_json(args.land)
    overview = load_json(args.overview)
    highlights = build_highlight_features(bundle, audit)
    write_highlight_geojson(args.geojson_output, highlights)
    render_svg(args.svg_output, land, overview, highlights)
    print(f"Wrote {len(highlights)} continuity highlight features to {args.geojson_output}")
    print(f"Wrote continuity highlight SVG to {args.svg_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
