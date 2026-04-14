#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_keikyu_weekday_train_instances.json"
CACHE_DIR = ROOT / "data" / "v3_external" / "keikyu"
TIMEOUT = 30
SERVICE_DAY = "2026-04-15"

SEED_STATION_PAGES = [
    "https://www.keikyu.co.jp/ride/kakueki/KK01.html",
]


def cache_path(url: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"


def fetch_text(url: str) -> str:
    path = cache_path(url)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "shift_jis"
    path.write_text(response.text, encoding="utf-8")
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


def discover_t5_pages(station_page_url: str) -> list[str]:
    text = fetch_text(station_page_url)
    matches = re.findall(r'(https?://norikae\.keikyu\.co\.jp/transit/norikae/T5\?[^"\']+)', text)
    deduped = []
    seen: set[str] = set()
    for match in matches:
        url = html.unescape(match)
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def discover_t2_pages(t5_url: str) -> list[str]:
    text = fetch_text(t5_url)
    matches = re.findall(r'(/transit/norikae/T2\?[^"\']+)', text)
    deduped = []
    seen: set[str] = set()
    for match in matches:
        url = "https://norikae.keikyu.co.jp" + html.unescape(match)
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def main() -> int:
    station_seed = load_station_seed()
    reports = []
    for station_page in SEED_STATION_PAGES:
        t5_pages = discover_t5_pages(station_page)
        t2_count = 0
        for t5_url in t5_pages:
            t2_pages = discover_t2_pages(t5_url)
            t2_count += len(t2_pages)
        reports.append(
            {
                "station_page": station_page,
                "t5_pages": len(t5_pages),
                "t2_pages": t2_count,
            }
        )

    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "id": "v3_tokyo_keikyu_weekday_train_instances_v0_seed",
                "label": "v3 Tokyo Keikyu weekday train instances seed",
                "version": 0,
                "service_day": SERVICE_DAY,
                "station_seed": station_seed,
                "source_reports": reports,
                "train_instances": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(reports)
    print(f"Wrote: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
