#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SVG_WIDTH = 1800
SVG_HEIGHT = 960
PANEL_WIDTH = 780
PANEL_HEIGHT = 780
PANEL_PADDING_X = 70
PANEL_PADDING_Y = 90


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def project_points(station_groups: list[dict[str, Any]], origin_x: float, origin_y: float) -> dict[str, tuple[float, float]]:
    lats = [item["centroid"]["lat"] for item in station_groups]
    lons = [item["centroid"]["lon"] for item in station_groups]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    width = PANEL_WIDTH
    height = PANEL_HEIGHT
    projected = {}
    for item in station_groups:
        lat = item["centroid"]["lat"]
        lon = item["centroid"]["lon"]
        x = origin_x + ((lon - min_lon) / (max_lon - min_lon)) * width
        y = origin_y + ((max_lat - lat) / (max_lat - min_lat)) * height
        projected[item["id"]] = (x, y)
    return projected


def polyline_points(station_group_ids: list[str], projected: dict[str, tuple[float, float]]) -> str:
    return " ".join(f"{projected[sgid][0]:.1f},{projected[sgid][1]:.1f}" for sgid in station_group_ids if sgid in projected)


def label_rank_sort(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: (-item["labelRank"], item["primaryName"]))


def render(bundle: dict[str, Any]) -> str:
    station_groups = bundle["stationGroups"]
    track_centerlines = bundle["trackCenterlines"]
    service_routes = {route["id"]: route for route in bundle["serviceRoutes"]}
    patterns = {pattern["routeId"]: pattern for pattern in bundle["servicePatterns"]}
    projected_left = project_points(station_groups, 100, 120)
    projected_right = project_points(station_groups, 940, 120)

    top_labels = [item for item in label_rank_sort(station_groups) if item["labelRank"] >= 100]
    medium_labels = [item for item in label_rank_sort(station_groups) if item["labelRank"] >= 50]

    corridor_svg = []
    for line in track_centerlines:
        points = polyline_points(line["stationGroupIds"], projected_left)
        corridor_svg.append(f'<polyline points="{points}" fill="none" stroke="#d9dde5" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>')
        corridor_svg.append(f'<polyline points="{points}" fill="none" stroke="#8f99aa" stroke-width="4.2" stroke-linecap="round" stroke-linejoin="round"/>')

    service_svg = []
    for geom in [geom for geom in bundle["serviceGeometry"] if geom["representation"] == "service_path"]:
        route = service_routes[geom["routeId"]]
        pattern = patterns[geom["routeId"]]
        points = polyline_points(pattern["stationGroupIds"], projected_right)
        service_svg.append(f'<polyline points="{points}" fill="none" stroke="rgba(255,255,255,0.94)" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>')
        service_svg.append(f'<polyline points="{points}" fill="none" stroke="{route["color"]}" stroke-width="4.6" stroke-linecap="round" stroke-linejoin="round"/>')
        label_station_id = pattern["stationGroupIds"][max(1, len(pattern["stationGroupIds"]) // 2)]
        x, y = projected_right[label_station_id]
        service_svg.append(
            f'<g transform="translate({x + 8:.1f},{y - 10:.1f})">'
            f'<rect x="0" y="0" rx="10" ry="10" width="{max(88, len(route["shortName"]) * 9 + 26)}" height="24" fill="{route["color"]}" fill-opacity="0.95"/>'
            f'<text x="12" y="16" font-size="12" font-weight="700" fill="#ffffff">{route["shortName"]}</text>'
            f'</g>'
        )

    station_svg_left = []
    for item in station_groups:
        x, y = projected_left[item["id"]]
        radius = 5.8 if item["category"] != "normal" else 4.0
        station_svg_left.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="#ffffff" stroke="#4f5969" stroke-width="1.6"/>')
    for item in top_labels:
        x, y = projected_left[item["id"]]
        station_svg_left.append(
            f'<text x="{x + 10:.1f}" y="{y - 9:.1f}" font-size="13" font-weight="700" fill="#223040" stroke="rgba(255,255,255,0.92)" stroke-width="3" paint-order="stroke">{item["primaryName"]}</text>'
        )

    station_svg_right = []
    for item in station_groups:
        x, y = projected_right[item["id"]]
        radius = 5.2 if item["category"] != "normal" else 3.5
        station_svg_right.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="#ffffff" stroke="#415063" stroke-width="1.3"/>')
    for item in medium_labels:
        x, y = projected_right[item["id"]]
        font_size = 12 if item["labelRank"] >= 100 else 9
        weight = 700 if item["labelRank"] >= 100 else 500
        station_svg_right.append(
            f'<text x="{x + 9:.1f}" y="{y - 8:.1f}" font-size="{font_size}" font-weight="{weight}" fill="#223040" stroke="rgba(255,255,255,0.92)" stroke-width="2.4" paint-order="stroke">{item["primaryName"]}</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}">
  <rect width="100%" height="100%" fill="#f5f1e8"/>
  <defs>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#243142" flood-opacity="0.10"/>
    </filter>
  </defs>
  <text x="86" y="64" font-size="34" font-weight="800" fill="#1c2733">OniChase V3 Shinkansen Pilot</text>
  <text x="86" y="92" font-size="15" fill="#677383">GIS-first nationwide Shinkansen · one bundle, two map representations</text>

  <g filter="url(#shadow)">
    <rect x="54" y="118" width="810" height="822" rx="26" fill="rgba(255,252,247,0.96)" stroke="#d8cdb9"/>
    <rect x="894" y="118" width="852" height="822" rx="26" fill="rgba(255,252,247,0.96)" stroke="#d8cdb9"/>
  </g>

  <text x="92" y="156" font-size="20" font-weight="700" fill="#1c2733">Corridor View</text>
  <text x="92" y="180" font-size="13" fill="#677383">Low-zoom idea: structural geography, major hubs, calm rail corridors</text>

  <text x="932" y="156" font-size="20" font-weight="700" fill="#1c2733">Service View</text>
  <text x="932" y="180" font-size="13" fill="#677383">Higher-zoom idea: service families, clearer branches, denser labels</text>

  <g>{''.join(corridor_svg)}{''.join(station_svg_left)}</g>
  <g>{''.join(service_svg)}{''.join(station_svg_right)}</g>

  <g transform="translate(934,846)">
    <text x="0" y="0" font-size="13" font-weight="700" fill="#1c2733">Pilot Notes</text>
    <text x="0" y="22" font-size="12" fill="#677383">• Physical station positions use real lat/lon from the national Shinkansen dataset.</text>
    <text x="0" y="42" font-size="12" fill="#677383">• Corridor and service views come from the same V3 bundle, not from separate hand-drawn maps.</text>
    <text x="0" y="62" font-size="12" fill="#677383">• The next step is to connect this bundle to a real interactive client and timetable view.</text>
  </g>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the OniChase v3 Shinkansen pilot map.")
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    bundle = load_json(Path(args.bundle))
    svg = render(bundle)
    output_path = Path(args.output)
    output_path.write_text(svg, encoding="utf-8")
    print(f"Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
