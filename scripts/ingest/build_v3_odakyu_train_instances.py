#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests

from train_instance_merge import index_train_instances, upsert_train_instance


ROOT = Path(__file__).resolve().parents[2]
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_odakyu_weekday_train_instances.json"
CACHE_DIR = ROOT / "data" / "v3_external" / "odakyu"
SERVICE_DAY = "2026-04-15"
TIMEOUT = 30
MAX_FETCH_RETRIES = 5

OFFICIAL_BASE = "https://www.odakyu.jp"
TRANSIT_BASE = "https://transfer.navitime.biz"
SEARCH_PREFIX = "https://transfer.navitime.biz/odakyu-transit/smart/diagram/Search"

SEED_OFFICIAL_PAGES = [
    "https://www.odakyu.jp/station/shinjuku/timetable/down/?startId=00004254&linkId=00000686&direction=down&nodeType=train&initDispWeekdayTab=weekday",
]

TRAIN_TYPES = [
    "快速急行",
    "通勤急行",
    "急行",
    "準急",
    "各停",
    "区間準急",
    "区間急行",
    "特急",
]

ROMANCECAR_NAME_RE = re.compile(r"^(?:メトロ)?(?:はこね|ホームウェイ|モーニングウェイ|えのしま|さがみ|ふじさん)\d+号$")

ROUTE_COLORS = {
    "00000686": "005BAC",  # 小田原線
    "00000687": "0085CA",  # 江ノ島線
    "00000688": "7FBA00",  # 多摩線
    "00000828": "E67800",  # 箱根登山線（小田原-箱根湯本）
}


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


def clean_text(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value)
    value = re.sub(r"<.*?>", " ", value, flags=re.S)
    return " ".join(html.unescape(value).split())


def normalize_station_name(name: str) -> str:
    text = clean_text(str(name or ""))
    text = re.sub(r"[（(].*?[）)]", "", text)
    text = text.replace("ヶ", "ケ")
    return text


def station_name_variants(name: str) -> set[str]:
    text = clean_text(str(name or ""))
    variants = {text}
    variants.add(re.sub(r"[（(].*?[）)]", "", text))
    more = set()
    for variant in variants:
        more.add(variant.replace("ヶ", "ケ"))
        more.add(variant.replace("ケ", "ヶ"))
    return {variant for variant in variants | more if variant}


def cache_path(url: str, suffix: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.{suffix}"


def fetch_text(url: str) -> str:
    path = cache_path(url, "html")
    if path.exists():
        return path.read_text(encoding="utf-8")
    last_error: Exception | None = None
    for attempt in range(1, MAX_FETCH_RETRIES + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            path.write_text(response.text, encoding="utf-8")
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_FETCH_RETRIES:
                break
            time.sleep(min(2 * attempt, 10))
    assert last_error is not None
    raise last_error


def load_station_seed() -> list[dict]:
    geojson = json.loads(N02_STATION_PATH.read_text(encoding="utf-8"))
    entries: dict[str, dict] = {}
    for feature in geojson["features"]:
        props = feature["properties"]
        operator = props.get("N02_004")
        line = props.get("N02_003", "")
        if operator == "小田急電鉄":
            station_id_prefix = "ODAKYU"
        elif operator == "小田急箱根" and line == "鉄道線":
            station_id_prefix = "ODAKYU_HAKONE"
        else:
            continue
        name = props.get("N02_005", "")
        if not name:
            continue
        if name in entries:
            continue
        lon, lat = centroid(feature["geometry"]["coordinates"])
        entries[name] = {
            "station_id": f"{station_id_prefix}_{name}",
            "name_ja": name,
            "operator": operator,
            "line_id": line,
            "lat": round(lat, 8),
            "lon": round(lon, 8),
            "n02_station_code": props.get("N02_005c"),
            "n02_group_code": props.get("N02_005g"),
        }
    return sorted(entries.values(), key=lambda item: item["name_ja"])


def set_query(url: str, **updates: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key, value in updates.items():
        qs[key] = [value]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def official_page_key(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    start_id = qs.get("startId", [""])[0]
    return f"{parsed.path}?startId={start_id}"


def parse_official_station_page(page_url: str) -> dict | None:
    try:
        text = fetch_text(page_url)
    except requests.HTTPError:
        return None
    iframe_match = re.search(
        r'(https://transfer\.navitime\.biz/odakyu-transit/smart/diagram/Search\?[^"]+)',
        text,
    )
    if not iframe_match:
        return None
    search_url = html.unescape(iframe_match.group(1))
    parsed = urlparse(search_url)
    query = parse_qs(parsed.query)
    return {
        "official_page_url": page_url,
        "search_url": search_url,
        "station_code": query.get("startId", [""])[0],
        "link_id": query.get("linkId", [""])[0],
        "direction": query.get("direction", [""])[0],
    }


def discover_stop_list_urls(search_url: str) -> list[str]:
    text = fetch_text(search_url)
    matches = re.findall(r'window\.open\("([^"]*StopListDiagram[^"]+)"', text)
    urls = []
    seen: set[str] = set()
    for match in matches:
        full = urljoin(TRANSIT_BASE, html.unescape(match))
        if full in seen:
            continue
        seen.add(full)
        urls.append(full)
    return urls


def parse_stop_list(stop_list_url: str, station_lookup: dict[str, dict]) -> tuple[dict | None, list[str]]:
    text = fetch_text(stop_list_url)

    railroad_name_match = re.search(r'<div class="railroad-name[^"]*">\s*(.*?)\s*</div>', text, re.S)
    railroad_name = clean_text(railroad_name_match.group(1)) if railroad_name_match else "小田急"
    direction_name_match = re.search(r'<div class="direction-name">\s*(.*?)\s*</div>', text, re.S)
    direction_name = clean_text(direction_name_match.group(1)) if direction_name_match else ""

    departure_match = re.search(r'(\d{2}:\d{2})発\s*(.+?)行', direction_name)
    departure_hhmm = departure_match.group(1) if departure_match else ""
    headsign = departure_match.group(2) if departure_match else direction_name

    train_type = ""
    for candidate in TRAIN_TYPES:
        if railroad_name.endswith(candidate):
            train_type = candidate
            break
    if not train_type:
        train_type = "普通"

    line_name = railroad_name
    if train_type and railroad_name.endswith(train_type):
        line_name = railroad_name[: -len(train_type)] or railroad_name
    if ROMANCECAR_NAME_RE.match(line_name):
        train_type = "特急"

    url_query = parse_qs(urlparse(stop_list_url).query)
    tcode = url_query.get("tCode", [""])[0]
    dt = url_query.get("datetime", [""])[0]
    if dt and not dt.startswith(f"{SERVICE_DAY}T"):
        return None, []
    route_color = ROUTE_COLORS.get(url_query.get("linkId", [""])[0], "005BAC")

    station_page_urls: list[str] = []
    stop_times = []
    seen_station_pages: set[str] = set()

    li_pattern = re.compile(r'<li class="([^"]*\btrain\b[^"]*)"[^>]*>(.*?)</li>', re.S)
    href_pattern = re.compile(r'href="([^"]+/station/[^"]+/timetable/[^"]+)"', re.S)
    name_pattern = re.compile(r'<div class="name">\s*(.*?)\s*</div>', re.S)
    time_pattern = re.compile(r'<div class="time">\s*(\d{2}:\d{2})<span class="landing">\s*([着発])\s*</span>', re.S)

    for _class_name, item_html in li_pattern.findall(text):
        name_match = name_pattern.search(item_html)
        time_match = time_pattern.search(item_html)
        if not name_match or not time_match:
            continue
        href_match = href_pattern.search(item_html)
        if href_match:
            station_page_url = html.unescape(href_match.group(1))
            if station_page_url not in seen_station_pages:
                seen_station_pages.add(station_page_url)
                station_page_urls.append(station_page_url)
        raw_name = name_match.group(1)
        hhmm = time_match.group(1)
        marker = time_match.group(2)
        station_name = normalize_station_name(raw_name)
        station = station_lookup.get(station_name)
        if station is None:
            continue
        stop_times.append(
            {
                "sequence": len(stop_times) + 1,
                "station_name_raw": station_name,
                "station_id": station["station_id"],
                "line_id": line_name,
                "arrival_hhmm": hhmm,
                "departure_hhmm": hhmm,
                "platform": None,
                "stop_kind": marker,
            }
        )

    if len(stop_times) < 2:
        return None, station_page_urls

    train_instance = {
        "service_instance_id": f"{tcode}_{SERVICE_DAY}",
        "train_number": tcode,
        "service_name": line_name,
        "headsign": headsign,
        "train_type": train_type,
        "route_color": route_color,
        "stop_times": stop_times,
        "source_url": stop_list_url,
    }
    return train_instance, station_page_urls


def load_existing_output() -> dict:
    if not OUTPUT_PATH.exists():
        return {}
    return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))


def main() -> int:
    station_seed = load_station_seed()
    station_lookup = {}
    for entry in station_seed:
        for variant in station_name_variants(entry["name_ja"]):
            station_lookup[variant] = entry

    existing_output = load_existing_output()
    rebuild = os.environ.get("REBUILD") == "1"
    if existing_output and not rebuild:
        train_instances, instance_index = index_train_instances(existing_output.get("train_instances", []))
        source_reports = list(existing_output.get("source_reports") or existing_output.get("source_pages", []))
    else:
        train_instances = []
        instance_index = {}
        source_reports = []
    seen_official_pages: set[str] = {
        official_page_key(report["official_page_url"])
        for report in source_reports
        if report.get("official_page_url")
    }
    seen_search_urls: set[str] = {
        report["search_url"] for report in source_reports if report.get("search_url")
    }
    seen_stop_urls: set[str] = {item.get("source_url", "") for item in train_instances if item.get("source_url")}

    queue_candidates = list(SEED_OFFICIAL_PAGES)
    for item in train_instances:
        for stop in item.get("stop_times", []):
            station_name = stop.get("station_name_raw")
            if not station_name:
                continue
            station_entry = station_lookup.get(station_name)
            if not station_entry:
                continue
            official_page = station_entry.get("official_page_url")
            if official_page:
                queue_candidates.append(official_page)
    queue: deque[str] = deque(queue_candidates)

    while queue:
        official_page = queue.popleft()
        page_key = official_page_key(official_page)
        if page_key in seen_official_pages:
            continue
        seen_official_pages.add(page_key)

        page_info = parse_official_station_page(official_page)
        if page_info is None:
            continue

        search_urls = [page_info["search_url"]]
        opposite = "up" if page_info["direction"] == "down" else "down"
        search_urls.append(set_query(page_info["search_url"], direction=opposite))

        for search_url in search_urls:
            if search_url in seen_search_urls:
                continue
            seen_search_urls.add(search_url)
            stop_urls = discover_stop_list_urls(search_url)
            source_reports.append(
                {
                    "official_page_url": official_page,
                    "search_url": search_url,
                    "stop_list_pages": len(stop_urls),
                }
            )
            for index, stop_url in enumerate(stop_urls, start=1):
                if stop_url in seen_stop_urls:
                    continue
                seen_stop_urls.add(stop_url)
                if index % 200 == 0:
                    print(f"[odakyu] stop pages {index}/{len(stop_urls)} from {search_url}")
                train, station_pages = parse_stop_list(stop_url, station_lookup)
                for station_page in station_pages:
                    if station_page not in seen_official_pages:
                        queue.append(station_page)
                if train is None:
                    continue
                upsert_train_instance(train_instances, instance_index, train)
                if len(train_instances) % 500 == 0:
                    OUTPUT_PATH.write_text(
                        json.dumps(
                            {
                                "id": "v3_tokyo_odakyu_weekday_train_instances_v0_1",
                                "label": "v3 Tokyo Odakyu Weekday Train Instances",
                                "version": 1,
                                "service_day": SERVICE_DAY,
                                "station_seed": station_seed,
                                "source_pages": source_reports,
                                "train_instances": train_instances,
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    print(
                        f"[odakyu] checkpoint trains={len(train_instances)} "
                        f"stations={len(seen_official_pages)} stop_pages={len(seen_stop_urls)}"
                    )

    train_instances, _ = index_train_instances(train_instances)

    output = {
        "id": "v3_tokyo_odakyu_weekday_train_instances_v0_1",
        "label": "v3 Tokyo Odakyu Weekday Train Instances",
        "version": 1,
        "service_day": SERVICE_DAY,
        "station_seed": station_seed,
        "source_pages": source_reports,
        "train_instances": train_instances,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Official pages: {len(seen_official_pages)}")
    print(f"Search pages: {len(seen_search_urls)}")
    print(f"Stop pages: {len(seen_stop_urls)}")
    print(f"Train instances: {len(train_instances)}")
    print(f"Wrote: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
