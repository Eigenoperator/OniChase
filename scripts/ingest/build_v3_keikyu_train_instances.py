#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

import requests


ROOT = Path(__file__).resolve().parents[2]
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_keikyu_weekday_train_instances.json"
CACHE_DIR = ROOT / "data" / "v3_external" / "keikyu"
TIMEOUT = 30
MAX_FETCH_RETRIES = 5
SERVICE_DAY = "2026-04-15"

OFFICIAL_INDEX_PAGE = "https://www.keikyu.co.jp/ride/kakueki/"
OFFICIAL_BASE = "https://www.keikyu.co.jp"
TRANSIT_BASE = "https://norikae.keikyu.co.jp/transit/norikae/"
ROUTE_COLOR = "00A0E9"


def cache_path(url: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"


def fetch_text(url: str) -> str:
    path = cache_path(url)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    last_error: Exception | None = None
    for attempt in range(1, MAX_FETCH_RETRIES + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "shift_jis"
            path.write_text(response.text, encoding="utf-8")
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_FETCH_RETRIES:
                break
            time.sleep(min(2 * attempt, 10))
    assert last_error is not None
    raise last_error


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
    out: dict[str, dict] = {}
    for feature in geojson["features"]:
        props = feature["properties"]
        if props.get("N02_004") != "京浜急行電鉄":
            continue
        name = props.get("N02_005")
        if not name or name in out:
            continue
        lon, lat = centroid(feature["geometry"]["coordinates"])
        out[name] = {
            "station_id": f"KEIKYU_{name}",
            "name_ja": name,
            "operator": "京浜急行電鉄",
            "line_id": props.get("N02_003", ""),
            "lat": round(lat, 8),
            "lon": round(lon, 8),
            "n02_station_code": props.get("N02_005c"),
            "n02_group_code": props.get("N02_005g"),
        }
    return sorted(out.values(), key=lambda item: item["name_ja"])


def discover_station_pages() -> list[str]:
    text = fetch_text(OFFICIAL_INDEX_PAGE)
    matches = sorted(set(re.findall(r'/ride/kakueki/[A-Z]{2}\d+\.html', text)))
    return [urljoin(OFFICIAL_BASE, match) for match in matches if match.startswith("/ride/kakueki/KK")]


def discover_t5_pages(station_page_url: str) -> list[str]:
    text = fetch_text(station_page_url)
    matches = re.findall(r'(https?://norikae\.keikyu\.co\.jp/transit/norikae/T5\?[^"\']+)', text)
    deduped = []
    seen: set[str] = set()
    for match in matches:
        url = html.unescape(match).replace("http://", "https://")
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def discover_t7_pages(t5_url: str) -> list[str]:
    text = fetch_text(t5_url)
    matches = re.findall(r'href="(T7\?[^"]+)"', text)
    deduped = []
    seen: set[str] = set()
    for match in matches:
        url = urljoin(TRANSIT_BASE, html.unescape(match))
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def normalize_station_name(name: str) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(name))
    text = " ".join(text.replace("\u3000", " ").split())
    if text not in {"", "停車駅"}:
        parts = text.split()
        if len(parts) > 1:
            text = parts[-1]
    return text


def normalize_hhmm(value: str) -> str:
    text = html.unescape(value).replace("：", ":").strip()
    if text in {"—", "-", "―", "‐", "&mdash;"}:
        return ""
    return text


def parse_t7_page(t7_url: str, station_lookup: dict[str, dict]) -> dict | None:
    text = fetch_text(t7_url)

    title_match = re.search(
        r'<td id="title" colspan="3">(.*?)<br>\s*平日(?:のダイヤ)?</td>',
        text,
        re.S,
    )
    title_text = normalize_station_name(re.sub(r"<.*?>", " ", title_match.group(1))) if title_match else ""
    if not title_text:
        return None
    title_parts = title_text.split()
    train_type = title_parts[0] if title_parts else "京急"
    headsign = title_parts[-1] if len(title_parts) > 1 else ""

    stop_times = []
    rows = re.findall(
        r"<tr>\s*<td[^>]*>\s*(.*?)</td>\s*<td[^>]*>\s*(.*?)</td>\s*<td[^>]*>\s*(.*?)</td>\s*</tr>",
        text,
        re.S,
    )
    for sequence, (raw_name, raw_arrival, raw_departure) in enumerate(rows, start=1):
        station_name = normalize_station_name(re.sub(r"<.*?>", " ", raw_name))
        if station_name == "停車駅" or not station_name:
            continue
        station = station_lookup.get(station_name)
        if station is None:
            continue
        arrival = normalize_hhmm(re.sub(r"<.*?>", " ", raw_arrival))
        departure = normalize_hhmm(re.sub(r"<.*?>", " ", raw_departure))
        if arrival in {"—", "-", ""}:
            arrival = departure
        if departure in {"—", "-", ""}:
            departure = arrival
        stop_times.append(
            {
                "sequence": len(stop_times) + 1,
                "station_name_raw": station_name,
                "station_id": station["station_id"],
                "line_id": station.get("line_id"),
                "arrival_hhmm": arrival,
                "departure_hhmm": departure,
                "platform": None,
            }
        )

    if len(stop_times) < 2:
        return None

    tx_match = re.search(r"[?&]tx=([^&]+)", t7_url)
    tm_match = re.search(r"[?&]tm=([^&]+)", t7_url)
    date_match = re.search(r"[?&]date=([^&]*)", t7_url)
    train_number = tx_match.group(1) if tx_match else hashlib.sha1(t7_url.encode("utf-8")).hexdigest()[:12]
    departure_seed = tm_match.group(1) if tm_match else stop_times[0]["departure_hhmm"].replace(":", "")
    date_value = date_match.group(1) if date_match else ""
    if date_value and date_value != SERVICE_DAY:
        return None

    return {
        "service_instance_id": f"{train_number}_{SERVICE_DAY}",
        "train_number": train_number,
        "service_name": "Keikyu",
        "headsign": headsign,
        "train_type": train_type,
        "route_color": ROUTE_COLOR,
        "stop_times": stop_times,
        "source_url": t7_url,
    }


def write_output(station_seed: list[dict], source_reports: list[dict], train_instances: list[dict]) -> None:
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

    payload = {
        "id": "v3_tokyo_keikyu_weekday_train_instances_v0_1",
        "label": "v3 Tokyo Keikyu weekday train instances",
        "version": "0.1.0",
        "service_day": SERVICE_DAY,
        "station_seed": station_seed,
        "source_reports": source_reports,
        "train_instances": sorted(
            deduped.values(),
            key=lambda item: (
                item["stop_times"][0]["departure_hhmm"],
                item["train_number"],
            ),
        ),
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    station_seed = load_station_seed()
    station_lookup: dict[str, dict] = {}
    for entry in station_seed:
        station_lookup[entry["name_ja"]] = entry
        station_lookup[normalize_station_name(entry["name_ja"])] = entry
    station_pages = discover_station_pages()

    if OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        source_reports = existing.get("source_reports", [])
        train_instances: list[dict] = existing.get("train_instances", [])
    else:
        source_reports = []
        train_instances = []

    completed_station_pages = {report["station_page"] for report in source_reports}
    seen_t7: set[str] = set()
    seen_instances: set[str] = {item["service_instance_id"] for item in train_instances}

    for station_index, station_page in enumerate(station_pages, start=1):
        if station_page in completed_station_pages:
            continue
        t5_pages = discover_t5_pages(station_page)
        t7_count = 0
        for t5_url in t5_pages:
            t7_pages = discover_t7_pages(t5_url)
            t7_count += len(t7_pages)
            for t7_url in t7_pages:
                if t7_url in seen_t7:
                    continue
                seen_t7.add(t7_url)
                train = parse_t7_page(t7_url, station_lookup)
                if train is None:
                    continue
                if train["service_instance_id"] in seen_instances:
                    continue
                seen_instances.add(train["service_instance_id"])
                train_instances.append(train)
                if len(train_instances) % 500 == 0:
                    write_output(station_seed, source_reports, train_instances)
                    print(f"[keikyu] checkpoint trains={len(train_instances)} stations={station_index}/{len(station_pages)}")
        source_reports.append(
            {
                "station_page": station_page,
                "t5_pages": len(t5_pages),
                "t7_pages": t7_count,
            }
        )
        write_output(station_seed, source_reports, train_instances)
        print(
            f"[keikyu] station {station_index}/{len(station_pages)} "
            f"reports={len(source_reports)} trains={len(train_instances)}"
        )

    write_output(station_seed, source_reports, train_instances)
    print(f"Station pages: {len(station_pages)}")
    print(f"Train instances: {len(train_instances)}")
    print(f"Wrote: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
