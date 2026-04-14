#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests


ROOT = Path(__file__).resolve().parents[2]
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_rinkai_weekday_train_instances.json"
CACHE_DIR = ROOT / "data" / "v3_tokyo_rinkai_cache"
SERVICE_DAY = "2026-04-13"
BASE_URL = "https://www.twr.co.jp"
TIMEOUT = 30

RINKAI_STATIONS = [
    "新木場",
    "東雲",
    "国際展示場",
    "東京テレポート",
    "天王洲アイル",
    "品川シーサイド",
    "大井町",
    "大崎",
]

SOURCE_PAGES = [
    {
        "id": "shinkiba_to_osaki",
        "url": "https://www.twr.co.jp/route/tabid/107/Default.aspx?TabModule1376=0",
        "headsign": "大崎",
    },
    {
        "id": "osaki_to_shinkiba",
        "url": "https://www.twr.co.jp/route/tabid/121/Default.aspx?TabModule1376=0",
        "headsign": "新木場",
    },
]


def fetch_text(url: str) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_name = re.sub(r"[^A-Za-z0-9]+", "_", url).strip("_") + ".html"
    cache_path = CACHE_DIR / cache_name
    if cache_path.exists():
        return cache_path.read_text()
    response = requests.get(url, timeout=TIMEOUT)
    response.encoding = response.apparent_encoding or "utf-8"
    cache_path.write_text(response.text)
    return response.text


def load_station_seed() -> list[dict]:
    geojson = json.loads(N02_STATION_PATH.read_text())
    lookup: dict[str, dict] = {}
    for feature in geojson["features"]:
        props = feature["properties"]
        if props.get("N02_004") != "東京臨海高速鉄道":
            continue
        if props.get("N02_003") != "臨海副都心線":
            continue
        name = props.get("N02_005")
        if name not in RINKAI_STATIONS:
            continue
        lon, lat = centroid(feature["geometry"]["coordinates"])
        lookup[name] = {
            "station_id": f"RINKAI_{name}",
            "name_ja": name,
            "operator": "東京臨海高速鉄道",
            "line_id": "RINKAI",
            "lat": round(lat, 8),
            "lon": round(lon, 8),
            "n02_station_code": props.get("N02_005c"),
            "n02_group_code": props.get("N02_005g"),
        }
    return [lookup[name] for name in RINKAI_STATIONS]


def centroid(coords: list) -> tuple[float, float]:
    points: list[tuple[float, float]] = []

    def walk(node: list) -> None:
        if not node:
            return
        if isinstance(node[0], (int, float)):
            points.append((float(node[0]), float(node[1])))
            return
        for child in node:
            walk(child)

    walk(coords)
    lon = sum(p[0] for p in points) / len(points)
    lat = sum(p[1] for p in points) / len(points)
    return lon, lat


def discover_detail_links(page_html: str) -> list[str]:
    links = re.findall(r'href="(/Portals/0/resources/route/traindetail2026/traindetail_\d+\.html)"', page_html)
    return [urljoin(BASE_URL, href) for href in links]


def parse_detail(url: str, station_lookup: dict[str, dict], default_headsign: str) -> dict:
    html = fetch_text(url)
    train_type = extract_head_table_value(html, "列車種別")
    train_number = extract_head_table_value(html, "列車番号")
    raw_rows = []
    actual_headsign = default_headsign
    for row in re.findall(r"<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>", html, re.S):
        station_name = clean_html(row[0])
        if station_name == "駅名":
            continue
        raw_rows.append((station_name, clean_html(row[1]).replace(" ", ""), clean_html(row[2]) or None))
    if raw_rows:
        actual_headsign = raw_rows[-1][0]
    stop_times = []
    for station_name, time_text, platform in raw_rows:
        if station_name not in station_lookup:
            continue
        time_match = re.search(r"(\d{2}:\d{2})", time_text)
        if not time_match:
            continue
        hhmm = time_match.group(1)
        station_id = station_lookup[station_name]["station_id"]
        stop_times.append(
            {
                "sequence": len(stop_times) + 1,
                "station_name_raw": station_name,
                "station_id": station_id,
                "line_id": "RINKAI",
                "arrival_hhmm": hhmm,
                "departure_hhmm": hhmm,
                "platform": platform,
            }
        )
    return {
        "train_number": train_number,
        "service_instance_id": train_number,
        "service_name": "Rinkai Line",
        "headsign": actual_headsign,
        "train_type": train_type,
        "route_color": "005BAC",
        "stop_times": stop_times,
    }


def extract_head_table_value(html: str, label: str) -> str:
    match = re.search(rf"<th>\s*{re.escape(label)}\s*</th>\s*<td>(.*?)</td>", html, re.S)
    return clean_html(match.group(1)) if match else ""


def clean_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value)
    value = re.sub(r"<.*?>", "", value)
    return " ".join(value.split())


def main() -> None:
    station_seed = load_station_seed()
    station_lookup = {entry["name_ja"]: entry for entry in station_seed}
    train_instances = []
    source_page_reports = []
    seen: set[str] = set()

    for page in SOURCE_PAGES:
        html = fetch_text(page["url"])
        detail_links = discover_detail_links(html)
        source_page_reports.append(
            {
                "page_id": page["id"],
                "url": page["url"],
                "detail_links": len(detail_links),
            }
        )
        for index, link in enumerate(detail_links, start=1):
            if index % 50 == 0:
                print(f"[{page['id']}] {index}/{len(detail_links)}")
            train = parse_detail(link, station_lookup, page["headsign"])
            key = f"{train['train_number']}|{train['stop_times'][0]['departure_hhmm']}|{page['headsign']}"
            if key in seen:
                continue
            seen.add(key)
            train_instances.append(train)

    output = {
        "id": "v3_tokyo_rinkai_weekday_train_instances",
        "label": "v3 Tokyo Rinkai Weekday Train Instances",
        "version": 1,
        "service_day": SERVICE_DAY,
        "station_seed": station_seed,
        "source_pages": source_page_reports,
        "train_instances": train_instances,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Train instances: {len(train_instances)}")
    print(f"Wrote: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
