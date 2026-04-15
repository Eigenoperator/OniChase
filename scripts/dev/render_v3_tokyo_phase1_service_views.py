#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
N02_RAIL_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_RailroadSection.geojson"
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
JR_FAMILIES_PATH = ROOT / "data" / "v3_jr_tokyo_service_families.json"
NETWORK_SEED_PATH = ROOT / "data" / "v3_tokyo_phase1_network_seed.json"
OUTPUT_DATA_PATH = ROOT / "data" / "v3_tokyo_phase1_service_views.json"
OUTPUT_SVG_PATH = ROOT / "visuals" / "v3_tokyo_phase1_service_views.svg"

PRIVATE_OPERATORS = {
    "東急電鉄": {"label": "Tokyu", "color": "#d9485f"},
    "小田急電鉄": {"label": "Odakyu", "color": "#2b78d0"},
    "京王電鉄": {"label": "Keio", "color": "#f18a00"},
    "京浜急行電鉄": {"label": "Keikyu", "color": "#d63339"},
    "東武鉄道": {"label": "Tobu", "color": "#1f78ff"},
    "西武鉄道": {"label": "Seibu", "color": "#00a15f"},
    "京成電鉄": {"label": "Keisei", "color": "#2457c5"},
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
    ("10号線新宿線", "東京都"): {"label": "Toei / Shinjuku", "color": "#6bbd45"},
    ("12号線大江戸線", "東京都"): {"label": "Toei / Oedo", "color": "#b6007a"},
    ("日暮里・舎人ライナー線", "東京都"): {"label": "Toei / Nippori-Toneri", "color": "#e86f2d"},
    ("荒川線", "東京都"): {"label": "Toden Arakawa", "color": "#8b4c39"},
    ("東京臨海新交通臨海線", "ゆりかもめ"): {"label": "Yurikamome", "color": "#4bbddf"},
    ("東京モノレール羽田線", "東京モノレール"): {"label": "Tokyo Monorail", "color": "#4cc3e6"},
    ("多摩都市モノレール線", "多摩都市モノレール"): {"label": "Tama Monorail", "color": "#54c0d8"},
    ("常磐新線", "首都圏新都市鉄道"): {"label": "Tsukuba Express", "color": "#2bb673"},
    ("臨海副都心線", "東京臨海高速鉄道"): {"label": "Rinkai Line", "color": "#1f5aa6"},
    ("日暮里・舎人ライナー", "東京都"): {"label": "Toei / Nippori-Toneri", "color": "#e86f2d"},
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

SERVICE_FAMILY_COLORS = {
    "JR_YAMANOTE": "#88c840",
    "JR_KEIHIN_TOHOKU_NEGISHI": "#00b2d6",
    "JR_CHUO_RAPID": "#f15a24",
    "JR_CHUO_SOBU_LOCAL": "#f2c94c",
    "JR_SOBU_RAPID": "#2f4ca0",
    "JR_YOKOSUKA": "#2f4ca0",
    "JR_TOKAIDO": "#f28e1c",
    "JR_UENO_TOKYO": "#44a25b",
    "JR_SAIKYO_KAWAGOE": "#00a0d2",
    "JR_SHONAN_SHINJUKU": "#c85032",
    "JR_JOBAN_RAPID": "#22a6b3",
    "JR_JOBAN_LOCAL": "#4fc3d7",
    "JR_KEIYO": "#c62828",
}

PRIORITY_STATIONS = {
    "東京", "品川", "上野", "大宮", "新宿", "渋谷", "池袋", "秋葉原", "横浜", "新横浜",
    "神田", "有楽町", "浜松町", "田町", "大崎", "恵比寿", "代々木", "日暮里", "田端",
    "川崎", "大船", "千葉", "西船橋", "舞浜", "自由が丘", "武蔵小杉", "二子玉川",
    "下北沢", "調布", "京急川崎", "北千住", "所沢", "京成上野",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def midpoint(coords: list[list[float]]) -> tuple[float, float]:
    first = coords[0]
    last = coords[-1]
    return (first[0] + last[0]) / 2.0, (first[1] + last[1]) / 2.0


def in_bounds(lon: float, lat: float, bounds: dict[str, float]) -> bool:
    return bounds["min_lon"] <= lon <= bounds["max_lon"] and bounds["min_lat"] <= lat <= bounds["max_lat"]


def project(lon: float, lat: float, bounds: dict[str, float], width: int, height: int, pad: int) -> tuple[float, float]:
    usable_w = width - pad * 2
    usable_h = height - pad * 2
    x = pad + ((lon - bounds["min_lon"]) / (bounds["max_lon"] - bounds["min_lon"])) * usable_w
    y = pad + ((bounds["max_lat"] - lat) / (bounds["max_lat"] - bounds["min_lat"])) * usable_h
    return x, y


def classify_physical(props: dict) -> tuple[str, str, str] | None:
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


def path_from_coords(coords: list[list[float]], bounds: dict[str, float], width: int, height: int, pad: int, dx: float = 0.0) -> str | None:
    points = [project(lon, lat, bounds, width, height, pad) for lon, lat in coords if in_bounds(lon, lat, bounds)]
    if len(points) < 2:
        return None
    first_x, first_y = points[0]
    rest = " ".join(f"L {x + dx:.2f},{y:.2f}" for x, y in points[1:])
    return f"M {first_x + dx:.2f},{first_y:.2f} {rest}"


def render() -> None:
    rail = load_json(N02_RAIL_PATH)
    stations = load_json(N02_STATION_PATH)
    families = load_json(JR_FAMILIES_PATH)
    network_seed = load_json(NETWORK_SEED_PATH)
    bounds = network_seed["bounds"]

    physical_lines: list[dict] = []
    jr_segments_by_line: dict[str, list[dict]] = {}

    for feature in rail["features"]:
        props = feature["properties"]
        classification = classify_physical(props)
        if not classification:
            continue
        kind, label, color = classification
        coords = feature["geometry"]["coordinates"]
        if not any(in_bounds(lon, lat, bounds) for lon, lat in coords):
            continue
        row = {
            "kind": kind,
            "label": label,
            "color": color,
            "line_name_ja": props.get("N02_003"),
            "operator_ja": props.get("N02_004"),
            "coordinates": coords,
        }
        physical_lines.append(row)
        if kind == "jr":
            jr_segments_by_line.setdefault(props.get("N02_003"), []).append(row)

    visible_stations = []
    seen = set()
    for feature in stations["features"]:
        props = feature["properties"]
        classification = classify_physical(props)
        if not classification:
            continue
        lon, lat = midpoint(feature["geometry"]["coordinates"])
        if not in_bounds(lon, lat, bounds):
            continue
        key = (
            props.get("N02_004"),
            props.get("N02_003"),
            props.get("N02_005"),
            round(lon, 6),
            round(lat, 6),
        )
        if key in seen:
            continue
        seen.add(key)
        visible_stations.append(
            {
                "name_ja": props.get("N02_005"),
                "lon": lon,
                "lat": lat,
                "is_priority": props.get("N02_005") in PRIORITY_STATIONS,
            }
        )

    service_families = []
    for family in families["service_families"]:
        family_lines = []
        for line_name in family["member_physical_lines_ja"]:
            family_lines.extend(jr_segments_by_line.get(line_name, []))
        service_families.append(
            {
                "id": family["id"],
                "display_name_en": family["display_name_en"],
                "display_name_ja": family["display_name_ja"],
                "color": SERVICE_FAMILY_COLORS.get(family["id"], "#4f6d88"),
                "segments": family_lines,
            }
        )

    payload = {
        "id": "v3_tokyo_phase1_service_views_v0_1",
        "scope": "tokyo_jr_private_shinkansen_physical_and_service_views",
        "note": "Dual-view Tokyo map for v3. Left panel is the physical rail network at true positions. Right panel overlays JR rider-facing service families on top of the same real geometry.",
        "bounds": bounds,
        "physicalLines": physical_lines,
        "serviceFamilies": service_families,
        "visibleStations": visible_stations,
    }
    OUTPUT_DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    width = 2600
    height = 1320
    panel_w = 1140
    panel_h = 1100
    pad = 56
    left_x = 40
    right_x = 1420
    top_y = 140

    def render_station_group(dx: float) -> str:
        rows = []
        for station in visible_stations:
            x, y = project(station["lon"], station["lat"], bounds, panel_w, panel_h, pad)
            r = 3.6 if station["is_priority"] else 2.0
            rows.append(f'<circle cx="{x + dx:.2f}" cy="{y + top_y:.2f}" r="{r}" class="station" />')
            if station["is_priority"]:
                rows.append(
                    f'<text x="{x + dx + 7:.2f}" y="{y + top_y - 5:.2f}" class="station-ja">{station["name_ja"]}</text>'
                )
        return "".join(rows)

    physical_paths = []
    for line in physical_lines:
        d = path_from_coords(line["coordinates"], bounds, panel_w, panel_h, pad, left_x)
        if not d:
            continue
        width_px = 3.8 if line["kind"] == "shinkansen" else (2.4 if line["kind"] == "urban" else 2.2)
        opacity = 0.9 if line["kind"] == "shinkansen" else (0.78 if line["kind"] == "urban" else 0.68)
        physical_paths.append(
            f'<path d="{d}" fill="none" stroke="{line["color"]}" stroke-width="{width_px}" stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}" />'
        )

    service_base_paths = []
    for line in physical_lines:
        d = path_from_coords(line["coordinates"], bounds, panel_w, panel_h, pad, right_x)
        if not d:
            continue
        service_base_paths.append(
            f'<path d="{d}" fill="none" stroke="#d8e0ea" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" opacity="0.65" />'
        )

    service_paths = []
    for family in service_families:
        for segment in family["segments"]:
            d = path_from_coords(segment["coordinates"], bounds, panel_w, panel_h, pad, right_x)
            if not d:
                continue
            service_paths.append(
                f'<path d="{d}" fill="none" stroke="{family["color"]}" stroke-width="3.0" stroke-linecap="round" stroke-linejoin="round" opacity="0.84" />'
            )

    family_legend_rows = []
    for idx, family in enumerate(service_families[:8]):
        y = 0 + idx * 24
        family_legend_rows.append(
            f'<g transform="translate(0,{y})"><line x1="0" y1="0" x2="20" y2="0" stroke="{family["color"]}" stroke-width="4" stroke-linecap="round" />'
            f'<text x="30" y="5" class="legend">{family["display_name_en"]}</text></g>'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <style>
    .bg {{ fill: #f5f7fb; }}
    .panel {{ fill: rgba(255,255,255,0.95); stroke: #d2dceb; stroke-width: 1.2; }}
    .title {{ font: 700 28px 'Noto Sans', 'Segoe UI', sans-serif; fill: #162637; }}
    .subtitle {{ font: 500 14px 'Noto Sans', 'Segoe UI', sans-serif; fill: #617286; }}
    .paneltitle {{ font: 700 20px 'Noto Sans', 'Segoe UI', sans-serif; fill: #17324d; }}
    .panelsub {{ font: 500 12px 'Noto Sans', 'Segoe UI', sans-serif; fill: #6a7b8d; }}
    .station {{ fill: #fff; stroke: #17324d; stroke-width: 1.1; }}
    .station-ja {{ font: 700 12px 'Noto Sans JP', 'Segoe UI', sans-serif; fill: #10253b; }}
    .legend {{ font: 600 13px 'Noto Sans', 'Segoe UI', sans-serif; fill: #29445d; }}
  </style>
  <rect class="bg" x="0" y="0" width="{width}" height="{height}" />
  <text x="52" y="62" class="title">V3 Tokyo Phase 1 Physical View / Service View</text>
  <text x="52" y="90" class="subtitle">Both panels keep every station and line at its real position. The left panel shows physical infrastructure; the right panel overlays JR rider-facing service families on the same real geometry.</text>
  <rect class="panel" x="{left_x - 16}" y="{top_y - 48}" width="{panel_w + 32}" height="{panel_h + 90}" rx="24" />
  <rect class="panel" x="{right_x - 16}" y="{top_y - 48}" width="{panel_w + 32}" height="{panel_h + 90}" rx="24" />
  <text x="{left_x}" y="{top_y - 14}" class="paneltitle">Physical View</text>
  <text x="{left_x}" y="{top_y + 8}" class="panelsub">Real Shinkansen, JR physical corridors, and private-rail company networks.</text>
  <text x="{right_x}" y="{top_y - 14}" class="paneltitle">JR Service View</text>
  <text x="{right_x}" y="{top_y + 8}" class="panelsub">JR rider-facing service families mapped onto the same true station and corridor geometry.</text>
  <g transform="translate(0,{top_y})">{"".join(physical_paths)}</g>
  <g>{"".join(service_base_paths)}{"".join(service_paths)}</g>
  <g>{render_station_group(left_x)}{render_station_group(right_x)}</g>
  <g transform="translate({right_x + 770}, {top_y + 54})">
    <text x="0" y="0" class="paneltitle" style="font-size:18px;">JR Service Families</text>
    <g transform="translate(0,22)">{"".join(family_legend_rows)}</g>
  </g>
</svg>
'''
    OUTPUT_SVG_PATH.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT_DATA_PATH}")
    print(f"Wrote {OUTPUT_SVG_PATH}")
    print(f"Physical sections: {len(physical_lines)}")
    print(f"JR service families: {len(service_families)}")


if __name__ == "__main__":
    render()
