#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import time
from collections import deque
from hashlib import sha1
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

import requests


ROOT = Path(__file__).resolve().parents[2]
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_tokyu_weekday_train_instances.json"
CACHE_DIR = ROOT / "data" / "v3_external" / "tokyu"
SERVICE_DAY = "2026-04-15"
BASE_URL = "https://transfer.navitime.biz"
TIMEOUT = 30
MAX_FETCH_RETRIES = 5

SEED_LINE_PAGES = [
    "https://transfer.navitime.biz/tokyu/pc/diagram/TrainDiagram?stCd=00003544&rrCd=00000790&updown=1",
    "https://transfer.navitime.biz/tokyu/pc/diagram/TrainDiagram?stCd=00003544&rrCd=00000789&updown=1",
]

TOKYU_OPERATOR = "東急電鉄"
ROUTE_COLOR = "D91B5C"


def fetch_text(url: str) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_name = sha1(url.encode("utf-8")).hexdigest() + ".html"
    cache_path = CACHE_DIR / cache_name
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")
    last_error: Exception | None = None
    for attempt in range(1, MAX_FETCH_RETRIES + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            cache_path.write_text(response.text, encoding="utf-8")
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_FETCH_RETRIES:
                break
            time.sleep(min(2 * attempt, 10))
    assert last_error is not None
    raise last_error


def centroid(coords: list) -> tuple[float, float]:
    flat: list[tuple[float, float]] = []

    def walk(node: list) -> None:
        if not node:
            return
        if isinstance(node[0], (int, float)):
            flat.append((float(node[0]), float(node[1])))
            return
        for child in node:
            walk(child)

    walk(coords)
    lon = sum(p[0] for p in flat) / len(flat)
    lat = sum(p[1] for p in flat) / len(flat)
    return lon, lat


def normalize_station_name(name: str) -> str:
    name = name.strip()
    name = name.replace("（東京都）", "")
    name = name.replace("（神奈川県）", "")
    name = name.replace("ケーブル下", "")
    return name


def load_station_seed() -> list[dict]:
    geojson = json.loads(N02_STATION_PATH.read_text(encoding="utf-8"))
    stations: dict[str, dict] = {}
    for feature in geojson["features"]:
        props = feature["properties"]
        if props.get("N02_004") != TOKYU_OPERATOR:
            continue
        name = props.get("N02_005")
        if not name:
            continue
        norm = normalize_station_name(name)
        lon, lat = centroid(feature["geometry"]["coordinates"])
        stations.setdefault(
            norm,
            {
                "station_id": f"TOKYU_{norm}",
                "name_ja": norm,
                "operator": TOKYU_OPERATOR,
                "lat": round(lat, 8),
                "lon": round(lon, 8),
                "n02_station_code": props.get("N02_005c"),
                "n02_group_code": props.get("N02_005g"),
            },
        )
    return sorted(stations.values(), key=lambda item: item["name_ja"])


def canonical_line_page(url: str) -> str:
    query = parse_qs(urlparse(url).query)
    st = query.get("stCd", [""])[0]
    rr = query.get("rrCd", [""])[0]
    up = query.get("updown", [""])[0]
    return f"https://transfer.navitime.biz/tokyu/pc/diagram/TrainDiagram?stCd={st}&rrCd={rr}&updown={up}"


def is_tokyu_line_page(url: str, label: str | None = None) -> bool:
    if "transfer.navitime.biz/tokyu/pc/diagram/TrainDiagram?" not in url:
        return False
    if label is None:
        return True
    return "東急" in label and "東京メトロ" not in label


def extract_line_page_options(html_text: str) -> list[tuple[str, str]]:
    options = []
    for href, label in re.findall(r'<option value="([^"]*TrainDiagram\?[^"]+)">(.*?)</option>', html_text, re.S):
        full = urljoin(BASE_URL, html.unescape(href))
        text = html.unescape(re.sub(r"<.*?>", " ", label)).strip()
        options.append((full, text))
    return options


def extract_train_links(html_text: str) -> list[str]:
    links = []
    seen: set[str] = set()
    for href in re.findall(r'(/tokyu/pc/diagram/TrainRouteTimetable\?[^"\']+)', html_text):
        full = urljoin(BASE_URL, html.unescape(href))
        if full in seen:
            continue
        seen.add(full)
        links.append(full)
    return links


def extract_station_codes_from_stop_page(html_text: str) -> list[str]:
    return re.findall(r'stationimg-(\d+)\.png', html_text)


def extract_tokyu_station_codes_from_stop_page(html_text: str, station_lookup: dict[str, dict]) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()
    for code, raw_name in re.findall(
        r'stationimg-(\d+)\.png.*?<div class="name">(.*?)</div>',
        html_text,
        re.S,
    ):
        station_name = normalize_station_name(html.unescape(re.sub(r"<.*?>", " ", raw_name)).strip())
        if station_name not in station_lookup:
            continue
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def parse_stop_page(url: str, station_lookup: dict[str, dict]) -> dict | None:
    html_text = fetch_text(url)
    title_match = re.search(r"<title>\s*(.*?)\s*</title>", html_text, re.S)
    title = html.unescape(re.sub(r"<.*?>", " ", title_match.group(1))).strip() if title_match else ""

    query = parse_qs(urlparse(url).query)
    train_code = query.get("trCd", [""])[0]
    day = query.get("day", [""])[0]
    month = query.get("month", [""])[0]
    year = query.get("year", [""])[0]
    hour = query.get("hour", [""])[0]
    minute = query.get("minutes", [""])[0]
    if f"{year}-{month}-{day}" != SERVICE_DAY:
        return None
    service_instance_id = f"{train_code}_{SERVICE_DAY}"

    title_clean = title.replace("停車駅 | 東急電鉄", "").strip()
    title_match = re.match(r"\((.+?)\)\s+(\d{2}:\d{2})発\s+(.+?)行き", title_clean)
    if title_match:
        train_type = title_match.group(1)
        headsign = title_match.group(3)
    else:
        train_type = "Tokyu"
        headsign = ""

    blocks = re.findall(r'<li>\s*<div class="station-icon">.*?</li>', html_text, re.S)
    stop_times = []
    for index, block in enumerate(blocks, start=1):
        code_match = re.search(r'stationimg-(\d+)\.png', block)
        name_match = re.search(r'<div class="name">(.*?)</div>', block, re.S)
        time_match = re.search(r'<span aria-hidden="true">(\d{2}:\d{2})</span>', block)
        kind_match = re.search(r'<span class="landing" aria-hidden="true">(発|着)</span>', block)
        if not code_match or not name_match or not time_match:
            continue
        station_name = normalize_station_name(html.unescape(re.sub(r"<.*?>", " ", name_match.group(1))).strip())
        station = station_lookup.get(station_name)
        if station is None:
            continue
        hhmm = time_match.group(1)
        landing = kind_match.group(1) if kind_match else "着"
        arrival_hhmm = hhmm
        departure_hhmm = hhmm
        if index != 1 and landing == "着":
            departure_hhmm = hhmm
        stop_times.append(
            {
                "sequence": index,
                "station_name_raw": station_name,
                "station_id": station["station_id"],
                "line_id": None,
                "arrival_hhmm": arrival_hhmm,
                "departure_hhmm": departure_hhmm,
                "platform": None,
                "source_station_code": code_match.group(1),
            }
        )
    if len(stop_times) < 2:
        return None
    return {
        "train_number": train_code,
        "service_instance_id": service_instance_id,
        "service_name": "Tokyu",
        "headsign": headsign,
        "train_type": train_type,
        "route_color": ROUTE_COLOR,
        "stop_times": stop_times,
        "source_url": url,
    }


def crawl_tokyu_pages(station_lookup: dict[str, dict]) -> tuple[set[str], list[dict]]:
    queue = deque(canonical_line_page(url) for url in SEED_LINE_PAGES)
    seen_pages: set[str] = set()
    train_links: set[str] = set()
    page_reports: list[dict] = []
    while queue:
        page_url = queue.popleft()
        if page_url in seen_pages:
            continue
        seen_pages.add(page_url)
        try:
            html_text = fetch_text(page_url)
        except requests.HTTPError as exc:
            print(f"[tokyu] skip page {page_url}: {exc}")
            page_reports.append(
                {
                    "page_url": page_url,
                    "title": None,
                    "train_links": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        title_match = re.search(r"<title>\s*(.*?)\s*</title>", html_text, re.S)
        title = html.unescape(re.sub(r"<.*?>", " ", title_match.group(1))).strip() if title_match else ""
        route_train_links = extract_train_links(html_text)
        train_links.update(route_train_links)
        for option_url, label in extract_line_page_options(html_text):
            if not is_tokyu_line_page(option_url, label):
                continue
            queue.append(canonical_line_page(option_url))
        for train_url in route_train_links[:40]:
            try:
                stop_html = fetch_text(train_url)
            except requests.HTTPError as exc:
                print(f"[tokyu] skip stop page {train_url}: {exc}")
                continue
            line_query = parse_qs(urlparse(page_url).query)
            rr = line_query.get("rrCd", [""])[0]
            for station_code in extract_tokyu_station_codes_from_stop_page(stop_html, station_lookup):
                queue.append(canonical_line_page(f"https://transfer.navitime.biz/tokyu/pc/diagram/TrainDiagram?stCd={station_code}&rrCd={rr}&updown=0"))
                queue.append(canonical_line_page(f"https://transfer.navitime.biz/tokyu/pc/diagram/TrainDiagram?stCd={station_code}&rrCd={rr}&updown=1"))
        page_reports.append(
            {
                "page_url": page_url,
                "title": title,
                "train_links": len(route_train_links),
            }
        )
    return train_links, page_reports


def load_existing_output() -> dict:
    if not OUTPUT_PATH.exists():
        return {}
    return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))


def main() -> int:
    station_seed = load_station_seed()
    station_lookup = {entry["name_ja"]: entry for entry in station_seed}
    train_links, page_reports = crawl_tokyu_pages(station_lookup)
    existing_output = load_existing_output()
    train_instances = list(existing_output.get("train_instances", []))
    seen_instances: set[str] = {item["service_instance_id"] for item in train_instances}
    for train_url in sorted(train_links):
        train = parse_stop_page(train_url, station_lookup)
        if train is None:
            continue
        if train["service_instance_id"] in seen_instances:
            continue
        seen_instances.add(train["service_instance_id"])
        train_instances.append(train)
        if len(train_instances) % 500 == 0:
            OUTPUT_PATH.write_text(
                json.dumps(
                    {
                        "id": "v3_tokyo_tokyu_weekday_train_instances_v0_1",
                        "label": "V3 Tokyu weekday train instances from official train detail pages",
                        "version": "0.1.0",
                        "service_day": SERVICE_DAY,
                        "station_seed": station_seed,
                        "source_reports": page_reports,
                        "train_instances": sorted(
                            train_instances,
                            key=lambda item: (
                                item["stop_times"][0]["departure_hhmm"],
                                item["train_number"],
                            ),
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"[tokyu] checkpoint trains={len(train_instances)} pages={len(page_reports)} details={len(train_links)}")
    deduped: dict[str, dict] = {}
    for item in train_instances:
        stop_times = item.get("stop_times", [])
        if not stop_times:
            continue
        key = item.get("train_number") or (
            item.get("service_name"),
            item.get("headsign"),
            item.get("train_type"),
            stop_times[0].get("departure_hhmm", ""),
            stop_times[-1].get("arrival_hhmm", ""),
            tuple((s.get("station_id"), s.get("arrival_hhmm"), s.get("departure_hhmm")) for s in stop_times),
        )
        existing = deduped.get(key)
        if existing is None or len(stop_times) > len(existing.get("stop_times", [])):
            deduped[key] = item

    output = {
        "id": "v3_tokyo_tokyu_weekday_train_instances_v0_1",
        "label": "V3 Tokyu weekday train instances from official train detail pages",
        "version": "0.1.0",
        "service_day": SERVICE_DAY,
        "station_seed": station_seed,
        "source_reports": page_reports,
        "train_instances": sorted(
            deduped.values(),
            key=lambda item: (
                item["stop_times"][0]["departure_hhmm"],
                item["train_number"],
            ),
        ),
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Line pages crawled: {len(page_reports)}")
    print(f"Train detail pages: {len(train_links)}")
    print(f"Train instances: {len(output['train_instances'])}")
    print(f"Wrote: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
