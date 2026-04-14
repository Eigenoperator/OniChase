#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests


ROOT = Path(__file__).resolve().parents[2]
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_tokyo_monorail_weekday_train_instances.json"
CACHE_DIR = ROOT / "data" / "v3_external" / "tokyo_monorail"
SERVICE_DAY = "2026-04-15"
BASE_URL = "https://train-cloud.navitime.biz"
API_BASE_URL = "https://train-cloud.navitime.biz/apiv1/tokyo-monorail"
TIMEOUT = 30

LINE_ID = "TOKYO_MONORAIL_HANEDA"
SERVICE_NAME = "Tokyo Monorail"
ROUTE_COLOR = "005176"

STATION_SEQUENCE = [
    "モノレール浜松町",
    "天王洲アイル",
    "大井競馬場前",
    "流通センター",
    "昭和島",
    "整備場",
    "天空橋",
    "新整備場",
    "羽田空港第3ターミナル",
    "羽田空港第1ターミナル",
    "羽田空港第2ターミナル",
]

FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

TERMINAL_ROUTE_PAGES = [
    "https://train-cloud.navitime.biz/tokyo-monorail/railroads?station=00007843",
    "https://train-cloud.navitime.biz/tokyo-monorail/railroads?station=00009397",
]


def fetch_text(url: str) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_name = re.sub(r"[^A-Za-z0-9]+", "_", url).strip("_") + ".html"
    cache_path = CACHE_DIR / cache_name
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    cache_path.write_text(response.text, encoding="utf-8")
    return response.text


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


def load_station_seed() -> list[dict]:
    geojson = json.loads(N02_STATION_PATH.read_text(encoding="utf-8"))
    lookup: dict[str, dict] = {}
    for feature in geojson["features"]:
        props = feature["properties"]
        if props.get("N02_004") != "東京モノレール":
            continue
        if props.get("N02_003") != "東京モノレール羽田線":
            continue
        name = normalize_station_name(props.get("N02_005", ""))
        if name not in STATION_SEQUENCE:
            continue
        lon, lat = centroid(feature["geometry"]["coordinates"])
        lookup[name] = {
            "station_id": f"TOKYO_MONORAIL_{name}",
            "name_ja": name,
            "operator": "東京モノレール",
            "line_id": LINE_ID,
            "lat": round(lat, 8),
            "lon": round(lon, 8),
            "n02_station_code": props.get("N02_005c"),
            "n02_group_code": props.get("N02_005g"),
        }
    return [lookup[name] for name in STATION_SEQUENCE]


def discover_timetable_pages(route_page_url: str) -> list[str]:
    html_text = fetch_text(route_page_url)
    hrefs = re.findall(r'(/tokyo-monorail/railroads/timetables\?station=\d+&amp;directional-railroad=[^"]+)', html_text)
    return [urljoin(BASE_URL, html.unescape(href)) for href in hrefs]


def discover_stop_pages(timetable_url: str) -> list[str]:
    html_text = fetch_text(timetable_url)
    hrefs = re.findall(r'(/tokyo-monorail/railroads/timetables/stops\?[^"]+)', html_text)
    deduped = []
    seen: set[str] = set()
    for href in hrefs:
        full = urljoin(BASE_URL, html.unescape(href))
        if full in seen:
            continue
        seen.add(full)
        deduped.append(full)
    return deduped


def clean_text(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<.*?>", " ", value)).split())


def normalize_station_name(value: str) -> str:
    return clean_text(value).translate(FULLWIDTH_DIGITS)


def fetch_json(url: str, *, params: dict | None = None) -> dict:
    response = requests.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def parse_stop_page(url: str, station_lookup: dict[str, dict]) -> dict:
    query = parse_qs(urlparse(url).query)
    train_id = query.get("train-id", [""])[0]
    dt = query.get("datetime", [""])[0]
    station_id = query.get("station", [""])[0]
    api_url = f"{API_BASE_URL}/trains/sections"
    payload = fetch_json(
        api_url,
        params={
            "station-id": station_id,
            "train-id": train_id,
            "datetime": dt,
            "passed": "true",
            "language": "ja",
        },
    )
    destination = payload.get("destination", "")
    sections = payload.get("sections", [])
    first_departure = next((section.get("departure", {}) for section in sections if section.get("departure")), {})
    service_name = first_departure.get("trainName") or SERVICE_NAME
    train_type = first_departure.get("trainType") or "Local"
    stop_times = []
    for index, section in enumerate(sections, start=1):
        station_info = section.get("station") or {}
        station_name = normalize_station_name(station_info.get("name", ""))
        station = station_lookup.get(station_name)
        if station is None:
            continue
        arrival = section.get("arrival") or {}
        departure = section.get("departure") or {}
        arrival_hhmm = arrival.get("time", "")[11:16] or departure.get("time", "")[11:16]
        departure_hhmm = departure.get("time", "")[11:16] or arrival.get("time", "")[11:16]
        stop_times.append(
            {
                "sequence": index,
                "station_name_raw": station_name,
                "station_id": station["station_id"],
                "line_id": LINE_ID,
                "arrival_hhmm": arrival_hhmm or departure_hhmm,
                "departure_hhmm": departure_hhmm or arrival_hhmm,
                "platform": arrival.get("track") or departure.get("track"),
            }
        )

    return {
        "train_number": train_id,
        "service_instance_id": f"{train_id}_{dt}",
        "service_name": service_name,
        "headsign": destination,
        "train_type": train_type,
        "route_color": ROUTE_COLOR,
        "stop_times": stop_times,
        "source_url": f"{api_url}?station-id={station_id}&train-id={train_id}&datetime={dt}&passed=true&language=ja",
    }


def main() -> int:
    station_seed = load_station_seed()
    station_lookup = {entry["name_ja"]: entry for entry in station_seed}
    train_instances = []
    seen: set[str] = set()
    reports = []

    for route_page_url in TERMINAL_ROUTE_PAGES:
        timetable_pages = discover_timetable_pages(route_page_url)
        route_report = {
            "route_page": route_page_url,
            "timetable_pages": len(timetable_pages),
            "stop_pages": 0,
        }
        for timetable_url in timetable_pages:
            stop_pages = discover_stop_pages(timetable_url)
            route_report["stop_pages"] += len(stop_pages)
            for stop_page in stop_pages:
                train = parse_stop_page(stop_page, station_lookup)
                if len(train["stop_times"]) < 2:
                    continue
                key = train["service_instance_id"]
                if key in seen:
                    continue
                seen.add(key)
                train_instances.append(train)
        reports.append(route_report)

    output = {
        "id": "v3_tokyo_tokyo_monorail_weekday_train_instances_v0_1",
        "label": "V3 Tokyo Monorail weekday train instances from official train detail pages",
        "version": "0.1.0",
        "service_day": SERVICE_DAY,
        "station_seed": station_seed,
        "source_reports": reports,
        "train_instances": sorted(
            train_instances,
            key=lambda item: (
                item["stop_times"][0]["departure_hhmm"],
                item["train_number"],
            ),
        ),
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Train instances: {len(output['train_instances'])}")
    print(f"Wrote: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
