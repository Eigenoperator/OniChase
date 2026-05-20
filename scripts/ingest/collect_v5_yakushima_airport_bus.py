#!/usr/bin/env python3
"""Collect Yakushima Airport official route-bus timetable."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "yakushima_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_yakushima_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_yakushima_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_yakushima_airport_official_bus_audit.json"

MATSUBANDA_URL = "https://yakushima.co.jp/route_bus/"
YAKUSHIMA_KOTSU_PDF_URL = "https://yakukan.jp/wp-content/uploads/2026/02/6de96096aa9bc3268bf65e5bd4fecea0.pdf"
SERVICE_START = "20260301"
SERVICE_END = "20261130"

STOPS = {
    "宮之浦港": {"lat": 30.4326809, "lon": 130.5713756, "coordinateSource": "Nominatim OSM bus_stop:宮之浦港"},
    "屋久島空港": {"lat": 30.385599, "lon": 130.658997, "coordinateSource": "OurAirports KUM coordinate"},
    "安房港": {"lat": 30.3173093, "lon": 130.6596175, "coordinateSource": "Nominatim OSM bus_stop:安房港"},
    "屋久杉自然館": {"lat": 30.3090547, "lon": 130.6328709, "coordinateSource": "Nominatim OSM attraction:屋久杉自然館"},
}

MAIN_TRIP = [
    ("宮之浦港", "04:00"),
    ("屋久島空港", "04:24"),
    ("安房港", "04:40"),
    ("屋久杉自然館", "04:48"),
]


def cache_path_for(cache_dir: Path, url: str) -> Path:
    suffix = ".pdf" if url.lower().endswith(".pdf") else ".html"
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}{suffix}"


def fetch(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> Path:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def assert_source(path: Path) -> None:
    html = path.read_text(encoding="utf-8", errors="ignore")
    markers = ["期間：2026/3/1-2026/11/30", "宮之浦港", "空港", "安房港", "屋久杉自然館", "4:24", "¥590"]
    missing = [marker for marker in markers if marker not in html]
    if missing:
        raise ValueError(f"Yakushima bus page is missing expected markers: {missing}")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    html_path = fetch(MATSUBANDA_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    pdf_path = fetch(YAKUSHIMA_KOTSU_PDF_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    assert_source(html_path)
    trip = {
        "tripId": "yakushima_airport:miyanoura_yakusugi:001",
        "direction": "to_yakusugi",
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "stopTimes": [{"stopName": name, "time": time} for name, time in MAIN_TRIP],
    }
    route = {
        "sourceKind": "official_yakushima_airport_html",
        "operatorName": "まつばんだ交通",
        "airportIata": "KUM",
        "routeCode": "yakushima_airport_miyanoura_yakusugi",
        "routeName": "宮之浦港 ⇔ 屋久島空港 ⇔ 安房港 ⇔ 屋久杉自然館",
        "sourceUrl": MATSUBANDA_URL,
        "sourceUrls": [MATSUBANDA_URL, YAKUSHIMA_KOTSU_PDF_URL],
        "cachePath": str(html_path.relative_to(ROOT)),
        "cachePaths": [str(path.relative_to(ROOT)) for path in [html_path, pdf_path]],
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "adultFareYen": 1020,
        "routeStopNames": [name for name, _ in MAIN_TRIP],
        "tripCount": 1,
        "stops": [{"stopName": name, **STOPS[name]} for name in [name for name, _ in MAIN_TRIP]],
        "busStops": [{"name": name, **STOPS[name]} for name in [name for name, _ in MAIN_TRIP]],
        "trips": [trip],
        "sourceNotes": [
            "The fixed-clock Matsubanda route is emitted from the official 2026-03-01 through 2026-11-30 HTML timetable.",
            "Yakushima Kotsu's 2026 PDF is cached as a reviewed future parser source, but its dense multi-column table is not emitted by this endpoint-safe collector yet.",
        ],
    }
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_yakushima_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source pages/PDFs retain copyright.",
        "routes": [route],
    }
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "routeCount": 1,
        "tripCount": 1,
        "stopCount": len(STOPS),
        "coordinateStopCount": len(STOPS),
        "directionCounts": dict(Counter([trip["direction"]])),
        "sourceLimitation": "Only one fixed-clock Matsubanda trip is emitted; Yakushima Kotsu dense timetable requires a dedicated parser.",
    }
    return payload, audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--refresh-cache", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload, audit = collect(args)
    write_json(args.output, payload)
    write_json(args.docs_output, payload)
    write_json(args.audit_output, audit)
    if args.docs_output != args.output:
        args.docs_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.output, args.docs_output)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
