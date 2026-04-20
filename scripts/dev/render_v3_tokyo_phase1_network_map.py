#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
N02_RAIL_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_RailroadSection.geojson"
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_DATA_PATH = ROOT / "data" / "v3_tokyo_phase1_network_seed.json"
OUTPUT_SVG_PATH = ROOT / "visuals" / "v3_tokyo_phase1_network_map.svg"

BASE_BOUNDS = {
    "min_lon": 138.75,
    "max_lon": 140.55,
    "min_lat": 35.00,
    "max_lat": 36.45,
}

PRIVATE_OPERATORS = {
    "東急電鉄": {"label": "Tokyu", "color": "#d9485f"},
    "小田急電鉄": {"label": "Odakyu", "color": "#2b78d0"},
    "京王電鉄": {"label": "Keio", "color": "#f18a00"},
    "京浜急行電鉄": {"label": "Keikyu", "color": "#d63339"},
    "東武鉄道": {"label": "Tobu", "color": "#1f78ff"},
    "西武鉄道": {"label": "Seibu", "color": "#00a15f"},
    "京成電鉄": {"label": "Keisei", "color": "#2457c5"},
    "埼玉高速鉄道": {"label": "Saitama Railway", "color": "#00a6e9"},
}

TOKYO_URBAN_LINE_REFS = {
    ("3号線銀座線", "東京地下鉄"): {"label": "Tokyo Metro / Ginza", "color": "#f39700"},
    ("4号線丸ノ内線", "東京地下鉄"): {"label": "Tokyo Metro / Marunouchi", "color": "#e60012"},
    ("4号線丸ノ内線分岐線", "東京地下鉄"): {"label": "Tokyo Metro / Marunouchi Branch", "color": "#e60012"},
    ("2号線日比谷線", "東京地下鉄"): {"label": "Tokyo Metro / Hibiya", "color": "#9caeb7"},
    ("5号線東西線", "東京地下鉄"): {"label": "Tokyo Metro / Tozai", "color": "#00a7db"},
    ("9号線千代田線", "東京地下鉄"): {"label": "Tokyo Metro / Chiyoda", "color": "#009944"},
    ("8号線有楽町線", "東京地下鉄"): {"label": "Tokyo Metro / Yurakucho", "color": "#d7c447"},
    ("11号線半蔵門線", "東京地下鉄"): {"label": "Tokyo Metro / Hanzomon", "color": "#9b7cb6"},
    ("7号線南北線", "東京地下鉄"): {"label": "Tokyo Metro / Namboku", "color": "#00ada9"},
    ("13号線副都心線", "東京地下鉄"): {"label": "Tokyo Metro / Fukutoshin", "color": "#bb641d"},
    ("1号線浅草線", "東京都"): {"label": "Toei / Asakusa", "color": "#ec6e65"},
    ("6号線三田線", "東京都"): {"label": "Toei / Mita", "color": "#0079c2"},
    ("10号線新宿線", "東京都"): {"label": "Toei / Shinjuku", "color": "#6cbb5a"},
    ("12号線大江戸線", "東京都"): {"label": "Toei / Oedo", "color": "#b6007a"},
    ("日暮里・舎人ライナー", "東京都"): {"label": "Toei / Nippori-Toneri", "color": "#e45e12"},
    ("荒川線", "東京都"): {"label": "Toei / Toden Arakawa", "color": "#66aa33"},
    ("臨海副都心線", "東京臨海高速鉄道"): {"label": "TWR / Rinkai", "color": "#0068b7"},
    ("東京臨海新交通臨海線", "ゆりかもめ"): {"label": "Yurikamome", "color": "#009ddc"},
    ("東京モノレール羽田線", "東京モノレール"): {"label": "Tokyo Monorail", "color": "#007cc2"},
    ("多摩都市モノレール線", "多摩都市モノレール"): {"label": "Tama Monorail", "color": "#f08200"},
    ("常磐新線", "首都圏新都市鉄道"): {"label": "Tsukuba Express", "color": "#003f8c"},
}

JR_LINE_REFS = {
    ("山手線", "東日本旅客鉄道"): {"label": "JR East / Yamanote", "color": "#88c840"},
    ("中央線", "東日本旅客鉄道"): {"label": "JR East / Chuo", "color": "#f15a24"},
    ("総武線", "東日本旅客鉄道"): {"label": "JR East / Sobu", "color": "#f4c300"},
    ("横須賀線", "東日本旅客鉄道"): {"label": "JR East / Yokosuka", "color": "#2f4ca0"},
    ("東海道線", "東日本旅客鉄道"): {"label": "JR East / Tokaido", "color": "#f28e1c"},
    ("東海道線", "東海旅客鉄道"): {"label": "JR Central / Tokaido", "color": "#f28e1c"},
    ("東北線", "東日本旅客鉄道"): {"label": "JR East / Tohoku", "color": "#3aa76d"},
    ("常磐線", "東日本旅客鉄道"): {"label": "JR East / Joban", "color": "#22a6b3"},
    ("京葉線", "東日本旅客鉄道"): {"label": "JR East / Keiyo", "color": "#c62828"},
    ("赤羽線", "東日本旅客鉄道"): {"label": "JR East / Saikyo", "color": "#0099cc"},
    ("川越線", "東日本旅客鉄道"): {"label": "JR East / Kawagoe", "color": "#0099cc"},
    ("高崎線", "東日本旅客鉄道"): {"label": "JR East / Takasaki", "color": "#f28e1c"},
    ("根岸線", "東日本旅客鉄道"): {"label": "JR East / Negishi", "color": "#00bcd4"},
    ("武蔵野線", "東日本旅客鉄道"): {"label": "JR East / Musashino", "color": "#ff6f00"},
}

SHINKANSEN_REFS = {
    ("東海道新幹線", "東海旅客鉄道"): {"label": "Shinkansen / Tokaido", "color": "#1f78ff"},
    ("東北新幹線", "東日本旅客鉄道"): {"label": "Shinkansen / Tohoku", "color": "#2d9c5b"},
    ("上越新幹線", "東日本旅客鉄道"): {"label": "Shinkansen / Joetsu", "color": "#e65045"},
    ("北陸新幹線", "東日本旅客鉄道"): {"label": "Shinkansen / Hokuriku", "color": "#2c62c9"},
    ("北陸新幹線", "西日本旅客鉄道"): {"label": "Shinkansen / Hokuriku", "color": "#2c62c9"},
    ("山陽新幹線", "西日本旅客鉄道"): {"label": "Shinkansen / Sanyo", "color": "#1263d6"},
    ("山形新幹線", "東日本旅客鉄道"): {"label": "Shinkansen / Yamagata", "color": "#f09b20"},
    ("秋田新幹線", "東日本旅客鉄道"): {"label": "Shinkansen / Akita", "color": "#d54a96"},
    ("北海道新幹線", "北海道旅客鉄道"): {"label": "Shinkansen / Hokkaido", "color": "#3f8bd8"},
    ("九州新幹線", "九州旅客鉄道"): {"label": "Shinkansen / Kyushu", "color": "#de4b39"},
    ("西九州新幹線", "九州旅客鉄道"): {"label": "Shinkansen / Nishi-Kyushu", "color": "#7c4dff"},
}

PRIORITY_STATIONS = {
    "東京", "品川", "上野", "大宮", "新宿", "渋谷", "池袋", "秋葉原", "横浜", "新横浜",
    "神田", "有楽町", "浜松町", "田町", "大崎", "恵比寿", "代々木", "日暮里", "田端",
    "川崎", "大船", "千葉", "西船橋", "舞浜", "自由が丘", "武蔵小杉", "二子玉川",
    "下北沢", "調布", "京急川崎", "北千住", "所沢", "京成上野",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def in_bounds(lon: float, lat: float, bounds: dict[str, float]) -> bool:
    return bounds["min_lon"] <= lon <= bounds["max_lon"] and bounds["min_lat"] <= lat <= bounds["max_lat"]


def midpoint(coords: list[list[float]]) -> tuple[float, float]:
    first = coords[0]
    last = coords[-1]
    return (first[0] + last[0]) / 2.0, (first[1] + last[1]) / 2.0


def project(lon: float, lat: float, bounds: dict[str, float], width: int, height: int, pad: int) -> tuple[float, float]:
    usable_w = width - pad * 2
    usable_h = height - pad * 2
    x = pad + ((lon - bounds["min_lon"]) / (bounds["max_lon"] - bounds["min_lon"])) * usable_w
    y = pad + ((bounds["max_lat"] - lat) / (bounds["max_lat"] - bounds["min_lat"])) * usable_h
    return x, y


def classify_line(props: dict) -> tuple[str, str, str] | None:
    key = (props.get("N02_003"), props.get("N02_004"))
    if key in SHINKANSEN_REFS:
        info = SHINKANSEN_REFS[key]
        return ("shinkansen", info["label"], info["color"])
    if key in JR_LINE_REFS:
        info = JR_LINE_REFS[key]
        return ("jr", info["label"], info["color"])
    if key in TOKYO_URBAN_LINE_REFS:
        info = TOKYO_URBAN_LINE_REFS[key]
        return ("urban", info["label"], info["color"])
    operator = props.get("N02_004")
    if operator in PRIVATE_OPERATORS:
        info = PRIVATE_OPERATORS[operator]
        return ("private", f"{info['label']} / {props.get('N02_003')}", info["color"])
    return None


def render() -> None:
    rail = load_json(N02_RAIL_PATH)
    stations = load_json(N02_STATION_PATH)

    visible_lines = []
    for feature in rail["features"]:
        classification = classify_line(feature["properties"])
        if not classification:
            continue
        kind, label, color = classification
        visible_lines.append(
            {
                "kind": kind,
                "label": label,
                "color": color,
                "line_name_ja": feature["properties"].get("N02_003"),
                "operator_ja": feature["properties"].get("N02_004"),
                "coordinates": feature["geometry"]["coordinates"],
            }
        )

    line_points = [point for line in visible_lines for point in line["coordinates"]]
    if line_points:
        bounds = {
            "min_lon": min(BASE_BOUNDS["min_lon"], min(lon for lon, _ in line_points) - 0.08),
            "max_lon": max(BASE_BOUNDS["max_lon"], max(lon for lon, _ in line_points) + 0.08),
            "min_lat": min(BASE_BOUNDS["min_lat"], min(lat for _, lat in line_points) - 0.08),
            "max_lat": max(BASE_BOUNDS["max_lat"], max(lat for _, lat in line_points) + 0.08),
        }
    else:
        bounds = dict(BASE_BOUNDS)

    visible_stations = []
    seen_station_keys = set()
    for feature in stations["features"]:
        classification = classify_line(feature["properties"])
        if not classification:
            continue
        lon, lat = midpoint(feature["geometry"]["coordinates"])
        if not in_bounds(lon, lat, bounds):
            continue
        name = feature["properties"].get("N02_005")
        station_key = (
            feature["properties"].get("N02_004"),
            feature["properties"].get("N02_003"),
            name,
            round(lon, 6),
            round(lat, 6),
        )
        if station_key in seen_station_keys:
            continue
        seen_station_keys.add(station_key)
        visible_stations.append(
            {
                "name_ja": name,
                "operator_ja": feature["properties"].get("N02_004"),
                "line_name_ja": feature["properties"].get("N02_003"),
                "lon": lon,
                "lat": lat,
                "is_priority": name in PRIORITY_STATIONS,
            }
        )

    payload = {
        "id": "v3_tokyo_phase1_network_seed_v0_1",
        "scope": "tokyo_jr_private_shinkansen_network_seed",
        "note": "Current Tokyo-area real-geometry network seed drawn directly from MLIT N02-24. Station positions and line geometry are real. Bounds expand to fit the currently included whole-line and whole-company scope.",
        "bounds": bounds,
        "visibleLines": visible_lines,
        "visibleStations": visible_stations,
    }
    OUTPUT_DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    width = 1700
    height = 1280
    pad = 64

    line_paths = []
    for line in visible_lines:
        points = [project(lon, lat, bounds, width, height, pad) for lon, lat in line["coordinates"] if in_bounds(lon, lat, bounds)]
        if len(points) < 2:
            continue
        first_x, first_y = points[0]
        rest = " ".join(f"L {x:.2f},{y:.2f}" for x, y in points[1:])
        path_d = f"M {first_x:.2f},{first_y:.2f} {rest}"
        width_px = 3.8 if line["kind"] == "shinkansen" else (2.7 if line["kind"] == "urban" else 2.4)
        opacity = 0.92 if line["kind"] == "shinkansen" else (0.80 if line["kind"] == "urban" else 0.72)
        line_paths.append(
            f'<path d="{path_d}" fill="none" stroke="{line["color"]}" stroke-width="{width_px}" stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}" />'
        )

    station_rows = []
    for station in visible_stations:
        x, y = project(station["lon"], station["lat"], bounds, width, height, pad)
        r = 3.8 if station["is_priority"] else 2.1
        ja_size = 13 if station["is_priority"] else 10
        station_rows.append(
            f'''
            <g>
              <circle cx="{x:.2f}" cy="{y:.2f}" r="{r}" class="station" />
              {'<text x="%.2f" y="%.2f" class="station-ja" style="font-size:%spx;">%s</text>' % (x + 8, y - 6, ja_size, station["name_ja"]) if station["is_priority"] else ''}
            </g>
            '''
        )

    legend_entries = [
        ("Shinkansen", "#1f78ff"),
        ("JR", "#4f7a3f"),
        ("Metro / Urban Rail", "#7a3fc7"),
        ("Private Rail", "#b63b5f"),
    ]
    legend_rows = []
    for idx, (label, color) in enumerate(legend_entries):
        legend_rows.append(
            f'''
            <g transform="translate(0,{idx * 24})">
              <line x1="0" y1="0" x2="20" y2="0" stroke="{color}" stroke-width="4" stroke-linecap="round" />
              <text x="30" y="5" class="legend">{label}</text>
            </g>
            '''
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <style>
    .bg {{ fill: #f6f8fb; }}
    .panel {{ fill: rgba(255,255,255,0.93); stroke: #d5deea; stroke-width: 1.2; }}
    .title {{ font: 700 28px 'Noto Sans', 'Segoe UI', sans-serif; fill: #182534; }}
    .subtitle {{ font: 500 14px 'Noto Sans', 'Segoe UI', sans-serif; fill: #5c6c80; }}
    .station {{ fill: #ffffff; stroke: #17324d; stroke-width: 1.2; }}
    .station-ja {{ font: 700 12px 'Noto Sans JP', 'Segoe UI', sans-serif; fill: #13283f; }}
    .legend {{ font: 600 13px 'Noto Sans', 'Segoe UI', sans-serif; fill: #274058; }}
  </style>
  <rect class="bg" x="0" y="0" width="{width}" height="{height}" />
  <rect class="panel" x="24" y="22" width="{width - 48}" height="{height - 44}" rx="22" />
  <text x="56" y="70" class="title">V3 Tokyo Phase 1 Network Map</text>
  <text x="56" y="96" class="subtitle">Current Tokyo-area real-geometry physical network from MLIT N02-24. This view now includes Shinkansen, core JR lines, Tokyo Metro, Toei, Rinkai, Yurikamome, Tokyo Monorail, Tama Monorail, Tsukuba Express, and the first full private-rail company networks.</text>
  <g>{"".join(line_paths)}</g>
  <g>{"".join(station_rows)}</g>
  <g transform="translate({width - 240}, 82)">
    <text x="0" y="0" class="title" style="font-size:20px;">Layers</text>
    <g transform="translate(0,26)">
      {"".join(legend_rows)}
    </g>
  </g>
</svg>
'''
    svg = "\n".join(line.rstrip() for line in svg.splitlines()) + "\n"
    OUTPUT_SVG_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT_DATA_PATH}")
    print(f"Wrote {OUTPUT_SVG_PATH}")
    print(f"Visible line sections: {len(visible_lines)}")
    print(f"Visible stations: {len(visible_stations)}")


if __name__ == "__main__":
    render()
