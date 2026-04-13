#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = ROOT / "data" / "v3_shinkansen_bundle.json"
OUTPUT_DATA_PATH = ROOT / "data" / "v3_tokyo_phase1_seed.json"
OUTPUT_SVG_PATH = ROOT / "visuals" / "v3_tokyo_phase1_seed_map.svg"

TOKYO_BOUNDS = {
    "min_lon": 139.55,
    "max_lon": 139.92,
    "min_lat": 35.47,
    "max_lat": 35.90,
}

ROUTE_COLORS = {
    "Tokaido": "#1f78ff",
    "Sanyo": "#1263d6",
    "Kyushu": "#de4b39",
    "Nishi-Kyushu": "#7c4dff",
    "Tohoku": "#2d9c5b",
    "Hokkaido": "#2d9c5b",
    "Joetsu": "#e65045",
    "Hokuriku": "#2c62c9",
    "Yamagata": "#f09b20",
    "Akita": "#d54a96",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def project(lon: float, lat: float, bounds: dict[str, float], width: int, height: int, pad: int) -> tuple[float, float]:
    usable_w = width - pad * 2
    usable_h = height - pad * 2
    x = pad + ((lon - bounds["min_lon"]) / (bounds["max_lon"] - bounds["min_lon"])) * usable_w
    y = pad + ((bounds["max_lat"] - lat) / (bounds["max_lat"] - bounds["min_lat"])) * usable_h
    return x, y


def in_bounds(lat: float, lon: float) -> bool:
    return TOKYO_BOUNDS["min_lon"] <= lon <= TOKYO_BOUNDS["max_lon"] and TOKYO_BOUNDS["min_lat"] <= lat <= TOKYO_BOUNDS["max_lat"]


def render() -> None:
    bundle = load_json(BUNDLE_PATH)
    station_groups = {entry["id"]: entry for entry in bundle["stationGroups"]}

    selected_stations = {
        station["id"]: station
        for station in bundle["stationGroups"]
        if in_bounds(station["centroid"]["lat"], station["centroid"]["lon"])
    }

    width = 1500
    height = 980
    pad = 72

    projected = {
        station_id: project(station["centroid"]["lon"], station["centroid"]["lat"], TOKYO_BOUNDS, width, height, pad)
        for station_id, station in selected_stations.items()
    }

    route_entries = []
    for track in bundle["trackCenterlines"]:
        polyline = [
            project(point["lon"], point["lat"], TOKYO_BOUNDS, width, height, pad)
            for point in track["polyline"]
            if in_bounds(point["lat"], point["lon"])
        ]
        if len(polyline) < 2:
            continue
        route_entries.append(
            {
                "id": track["id"],
                "lineName": track["lineName"],
                "color": ROUTE_COLORS.get(track["lineName"], "#526173"),
                "polyline": polyline,
            }
        )

    seed_bundle = {
        "id": "v3_tokyo_phase1_seed_v0_2",
        "scope": "tokyo_shinkansen_core_from_bundle",
        "note": "Current Tokyo map rendered from the v3 Shinkansen bundle and its current real-geometry pipeline state.",
        "bounds": TOKYO_BOUNDS,
        "stations": [
            {
                "id": station_id,
                "name_en": station["names"].get("en", station["primaryName"]),
                "name_ja": station["names"].get("ja", station["primaryName"]),
                "lat": station["centroid"]["lat"],
                "lon": station["centroid"]["lon"],
                "category": station["category"],
            }
            for station_id, station in sorted(selected_stations.items())
        ],
        "routes": [
            {
                "id": route["id"],
                "label": route["lineName"],
                "color": route["color"],
            }
            for route in route_entries
        ],
    }
    OUTPUT_DATA_PATH.write_text(json.dumps(seed_bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    route_paths = []
    route_legend = []
    for idx, route in enumerate(route_entries):
        points = route["polyline"]
        first_x, first_y = points[0]
        rest = " ".join([f"L {x:.2f},{y:.2f}" for x, y in points[1:]])
        path_d = f"M {first_x:.2f},{first_y:.2f} {rest}"
        route_paths.append(
            f'<path d="{path_d}" fill="none" stroke="{route["color"]}" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.96" />'
        )
        route_legend.append(
            f'''
            <g transform="translate(0,{idx * 24})">
              <line x1="0" y1="0" x2="20" y2="0" stroke="{route["color"]}" stroke-width="5" stroke-linecap="round" />
              <text x="30" y="5" class="legend">{route["lineName"]}</text>
            </g>
            '''
        )

    station_labels = []
    for station_id, station in sorted(selected_stations.items()):
        x, y = projected[station_id]
        station_labels.append(
            f'''
            <g>
              <circle cx="{x:.2f}" cy="{y:.2f}" r="5.5" class="station" />
              <text x="{x + 10:.2f}" y="{y - 8:.2f}" class="station-ja">{station["names"].get("ja", station["primaryName"])}</text>
              <text x="{x + 10:.2f}" y="{y + 8:.2f}" class="station-en">{station["names"].get("en", station["primaryName"])}</text>
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
    .panel {{ fill: rgba(255,255,255,0.90); stroke: #d5deea; stroke-width: 1.2; }}
    .title {{ font: 700 28px 'Noto Sans', 'Segoe UI', sans-serif; fill: #182534; }}
    .subtitle {{ font: 500 14px 'Noto Sans', 'Segoe UI', sans-serif; fill: #5c6c80; }}
    .station {{ fill: #ffffff; stroke: #17324d; stroke-width: 1.8; }}
    .station-ja {{ font: 700 14px 'Noto Sans JP', 'Segoe UI', sans-serif; fill: #13283f; }}
    .station-en {{ font: 500 11px 'Noto Sans', 'Segoe UI', sans-serif; fill: #56677d; }}
    .legend {{ font: 600 13px 'Noto Sans', 'Segoe UI', sans-serif; fill: #274058; }}
  </style>
  <rect class="bg" x="0" y="0" width="{width}" height="{height}" />
  <rect class="panel" x="36" y="28" width="{width - 72}" height="{height - 56}" rx="24" filter="url(#shadow)" />
  <text x="72" y="88" class="title">V3 Current Tokyo Map</text>
  <text x="72" y="115" class="subtitle">Current Tokyo-area Shinkansen view rendered from the v3 bundle. Station positions are real; line geometry reflects the current real-geometry pipeline state.</text>

  <g>
    {"".join(route_paths)}
  </g>
  <g>
    {"".join(station_labels)}
  </g>

  <g transform="translate({width - 280}, 104)">
    <text x="0" y="0" class="title" style="font-size:20px;">Current Lines</text>
    <g transform="translate(0,28)">
      {"".join(route_legend)}
    </g>
  </g>
</svg>
'''
    OUTPUT_SVG_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT_DATA_PATH}")
    print(f"Wrote {OUTPUT_SVG_PATH}")


if __name__ == "__main__":
    render()
