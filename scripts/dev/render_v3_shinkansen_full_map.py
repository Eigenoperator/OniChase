#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = ROOT / "data" / "v3_shinkansen_bundle.json"
OUTPUT_PATH = ROOT / "visuals" / "v3_shinkansen_real_geometry_full_map.svg"

LINE_COLORS = {
    "Tokaido": "#1f78ff",
    "Sanyo": "#1263d6",
    "Kyushu": "#de4b39",
    "Nishi-Kyushu": "#7c4dff",
    "Tohoku": "#2d9c5b",
    "Hokkaido": "#3f8bd8",
    "Joetsu": "#e65045",
    "Hokuriku": "#2c62c9",
    "Yamagata": "#f09b20",
    "Akita": "#d54a96",
    "GALA Yuzawa": "#98a1ad",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def project(lon: float, lat: float, bounds: tuple[float, float, float, float], width: int, height: int, pad: int) -> tuple[float, float]:
    min_lon, min_lat, max_lon, max_lat = bounds
    usable_w = width - pad * 2
    usable_h = height - pad * 2
    x = pad + ((lon - min_lon) / (max_lon - min_lon)) * usable_w
    y = pad + ((max_lat - lat) / (max_lat - min_lat)) * usable_h
    return x, y


def render() -> None:
    bundle = load_json(BUNDLE_PATH)
    station_groups = {entry["id"]: entry for entry in bundle["stationGroups"]}

    all_points = []
    for line in bundle["trackCenterlines"]:
        for point in line["polyline"]:
            all_points.append((point["lon"], point["lat"]))

    min_lon = min(lon for lon, _ in all_points) - 0.5
    max_lon = max(lon for lon, _ in all_points) + 0.5
    min_lat = min(lat for _, lat in all_points) - 0.35
    max_lat = max(lat for _, lat in all_points) + 0.35
    bounds = (min_lon, min_lat, max_lon, max_lat)

    width = 1800
    height = 1240
    pad = 72

    route_paths: list[str] = []
    legend_rows: list[str] = []
    for idx, line in enumerate(bundle["trackCenterlines"]):
        points = [project(point["lon"], point["lat"], bounds, width, height, pad) for point in line["polyline"]]
        first_x, first_y = points[0]
        rest = " ".join(f"L {x:.2f},{y:.2f}" for x, y in points[1:])
        path_d = f"M {first_x:.2f},{first_y:.2f} {rest}"
        color = LINE_COLORS.get(line["lineName"], "#526173")
        line_width = 3.8 if line["lineName"] != "GALA Yuzawa" else 2.2
        opacity = 0.97 if line["lineName"] != "GALA Yuzawa" else 0.78
        route_paths.append(
            f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="{line_width}" stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}" />'
        )
        legend_rows.append(
            f'''
            <g transform="translate(0,{idx * 24})">
              <line x1="0" y1="0" x2="20" y2="0" stroke="{color}" stroke-width="{line_width}" stroke-linecap="round" />
              <text x="30" y="5" class="legend">{line["lineName"]}</text>
            </g>
            '''
        )

    station_rows: list[str] = []
    for group in bundle["stationGroups"]:
        lat = group["centroid"]["lat"]
        lon = group["centroid"]["lon"]
        if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
            continue
        x, y = project(lon, lat, bounds, width, height, pad)
        rank = group.get("labelRank", 50)
        category = group.get("category", "normal")
        if category == "hub" or rank >= 100:
            radius = 4.8
            ja_size = 13
            en_size = 10
        else:
            radius = 3.4
            ja_size = 11
            en_size = 9
        ja_name = group["names"].get("ja", group["primaryName"])
        en_name = group["names"].get("en", group["primaryName"])
        station_rows.append(
            f'''
            <g>
              <circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" class="station" />
              <text x="{x + 8:.2f}" y="{y - 7:.2f}" class="station-ja" style="font-size:{ja_size}px;">{ja_name}</text>
              <text x="{x + 8:.2f}" y="{y + 7:.2f}" class="station-en" style="font-size:{en_size}px;">{en_name}</text>
            </g>
            '''
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#93a4bf" flood-opacity="0.16" />
    </filter>
  </defs>
  <style>
    .bg {{ fill: #f6f8fb; }}
    .panel {{ fill: rgba(255,255,255,0.92); stroke: #d5deea; stroke-width: 1.2; }}
    .title {{ font: 700 28px 'Noto Sans', 'Segoe UI', sans-serif; fill: #182534; }}
    .subtitle {{ font: 500 14px 'Noto Sans', 'Segoe UI', sans-serif; fill: #5c6c80; }}
    .station {{ fill: #ffffff; stroke: #17324d; stroke-width: 1.4; }}
    .station-ja {{ font: 700 12px 'Noto Sans JP', 'Segoe UI', sans-serif; fill: #13283f; }}
    .station-en {{ font: 500 9px 'Noto Sans', 'Segoe UI', sans-serif; fill: #56677d; }}
    .legend {{ font: 600 13px 'Noto Sans', 'Segoe UI', sans-serif; fill: #274058; }}
  </style>
  <rect class="bg" x="0" y="0" width="{width}" height="{height}" />
  <rect class="panel" x="28" y="24" width="{width - 56}" height="{height - 48}" rx="24" filter="url(#shadow)" />
  <text x="64" y="74" class="title">V3 Shinkansen Real Geometry Full Map</text>
  <text x="64" y="99" class="subtitle">Nationwide Shinkansen geometry rendered from MLIT N02-24 based route extraction. Station positions and line geometry are real.</text>
  <g>{"".join(route_paths)}</g>
  <g>{"".join(station_rows)}</g>
  <g transform="translate({width - 270}, 90)">
    <text x="0" y="0" class="title" style="font-size:20px;">Lines</text>
    <g transform="translate(0,28)">
      {"".join(legend_rows)}
    </g>
  </g>
</svg>
'''
    OUTPUT_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    render()
