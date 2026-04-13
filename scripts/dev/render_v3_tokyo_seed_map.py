#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATIONS_PATH = ROOT / "data" / "shinkansen_v2_stations.json"
ROUTES_PATH = ROOT / "data" / "shinkansen_v2_routes.json"
OUTPUT_DATA_PATH = ROOT / "data" / "v3_tokyo_phase1_seed.json"
OUTPUT_SVG_PATH = ROOT / "visuals" / "v3_tokyo_phase1_seed_map.svg"

INCLUDED_STATIONS = [
    "TOKYO",
    "UENO",
    "OMIYA",
    "SHINAGAWA",
    "SHIN_YOKOHAMA",
]

INCLUDED_ROUTES = [
    "TOHOKU",
    "HOKKAIDO",
    "YAMAGATA",
    "AKITA",
    "JOETSU",
    "HOKURIKU",
    "TOKAIDO",
]

ROUTE_LABELS = {
    "TOHOKU": "Tohoku / Hokkaido",
    "HOKKAIDO": "Tohoku / Hokkaido",
    "YAMAGATA": "Yamagata",
    "AKITA": "Akita",
    "JOETSU": "Joetsu",
    "HOKURIKU": "Hokuriku",
    "TOKAIDO": "Tokaido",
}


def load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def project(lon: float, lat: float, bounds: tuple[float, float, float, float], width: int, height: int, pad: int) -> tuple[float, float]:
    min_lon, min_lat, max_lon, max_lat = bounds
    usable_w = width - pad * 2
    usable_h = height - pad * 2
    x = pad + ((lon - min_lon) / (max_lon - min_lon)) * usable_w
    # keep north upward
    y = pad + ((max_lat - lat) / (max_lat - min_lat)) * usable_h
    return x, y


def render() -> None:
    stations = {entry["id"]: entry for entry in load_json(STATIONS_PATH)}
    routes = {entry["id"]: entry for entry in load_json(ROUTES_PATH)}

    selected_stations = [stations[station_id] for station_id in INCLUDED_STATIONS]

    min_lon = min(station["lon"] for station in selected_stations) - 0.06
    max_lon = max(station["lon"] for station in selected_stations) + 0.06
    min_lat = min(station["lat"] for station in selected_stations) - 0.05
    max_lat = max(station["lat"] for station in selected_stations) + 0.05
    bounds = (min_lon, min_lat, max_lon, max_lat)

    width = 1400
    height = 900
    pad = 72

    projected = {
        station["id"]: project(station["lon"], station["lat"], bounds, width, height, pad)
        for station in selected_stations
    }

    seed_bundle = {
        "id": "v3_tokyo_phase1_seed_v0_1",
        "scope": "tokyo_shinkansen_core_seed",
        "note": "First v3 Tokyo seed map using real station positions from the proven v2 Shinkansen dataset.",
        "stations": [
            {
                "id": station["id"],
                "name_en": station["names"].get("en", station["name"]),
                "name_ja": station["names"].get("ja", station["name"]),
                "lat": station["lat"],
                "lon": station["lon"],
                "category": station["category"],
            }
            for station in selected_stations
        ],
        "routes": [
            {
                "id": route_id,
                "label": ROUTE_LABELS[route_id],
                "color": routes[route_id]["color"],
                "station_ids": [station_id for station_id in routes[route_id]["station_ids"] if station_id in INCLUDED_STATIONS],
            }
            for route_id in INCLUDED_ROUTES
        ],
        "bounds": {
            "min_lon": min_lon,
            "min_lat": min_lat,
            "max_lon": max_lon,
            "max_lat": max_lat,
        },
    }
    OUTPUT_DATA_PATH.write_text(json.dumps(seed_bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    route_paths = []
    route_legend = []
    for idx, route_id in enumerate(INCLUDED_ROUTES):
        route = routes[route_id]
        station_ids = [station_id for station_id in route["station_ids"] if station_id in INCLUDED_STATIONS]
        if len(station_ids) < 2:
            continue
        points = [projected[station_id] for station_id in station_ids]
        first_x, first_y = points[0]
        rest = " ".join([f"L {x:.2f},{y:.2f}" for x, y in points[1:]])
        path_d = f"M {first_x:.2f},{first_y:.2f} {rest}"
        route_paths.append(
            f'<path d="{path_d}" fill="none" stroke="{route["color"]}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round" opacity="0.92" />'
        )
        route_legend.append(
            f'''
            <g transform="translate(0,{idx * 26})">
              <line x1="0" y1="0" x2="22" y2="0" stroke="{route["color"]}" stroke-width="6" stroke-linecap="round" />
              <text x="32" y="5" class="legend">{ROUTE_LABELS[route_id]}</text>
            </g>
            '''
        )

    station_labels = []
    for station in selected_stations:
        x, y = projected[station["id"]]
        station_labels.append(
            f'''
            <g>
              <circle cx="{x:.2f}" cy="{y:.2f}" r="7" class="station" />
              <text x="{x + 12:.2f}" y="{y - 10:.2f}" class="station-ja">{station["names"].get("ja", station["name"])}</text>
              <text x="{x + 12:.2f}" y="{y + 10:.2f}" class="station-en">{station["names"].get("en", station["name"])}</text>
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
    .panel {{ fill: rgba(255,255,255,0.88); stroke: #d5deea; stroke-width: 1.2; }}
    .title {{ font: 700 28px 'Noto Sans', 'Segoe UI', sans-serif; fill: #182534; }}
    .subtitle {{ font: 500 14px 'Noto Sans', 'Segoe UI', sans-serif; fill: #5c6c80; }}
    .station {{ fill: #ffffff; stroke: #17324d; stroke-width: 2; }}
    .station-ja {{ font: 700 17px 'Noto Sans JP', 'Segoe UI', sans-serif; fill: #13283f; }}
    .station-en {{ font: 500 12px 'Noto Sans', 'Segoe UI', sans-serif; fill: #56677d; }}
    .legend {{ font: 600 14px 'Noto Sans', 'Segoe UI', sans-serif; fill: #274058; }}
  </style>
  <rect class="bg" x="0" y="0" width="{width}" height="{height}" />
  <rect class="panel" x="36" y="28" width="{width - 72}" height="{height - 56}" rx="24" filter="url(#shadow)" />
  <text x="72" y="88" class="title">V3 Tokyo Phase 1 Seed Map</text>
  <text x="72" y="115" class="subtitle">Current Tokyo Shinkansen core seed using real station positions. This is the first step, not the final v3 rail scope.</text>

  <g>
    {"".join(route_paths)}
  </g>
  <g>
    {"".join(station_labels)}
  </g>

  <g transform="translate({width - 310}, 104)">
    <text x="0" y="0" class="title" style="font-size:20px;">Current Routes</text>
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
