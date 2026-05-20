#!/usr/bin/env python3
"""Collect Monbetsu Airport official free shuttle timetable."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "monbetsu_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_monbetsu_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_monbetsu_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_monbetsu_airport_official_bus_audit.json"

SOURCE_URL = "https://mombetsu.jp/tourism/?content=1766"
SERVICE_START = "20260329"
SERVICE_END = "20260630"

STOPS = {
    "紋別バスターミナル": {"lat": 44.3520820, "lon": 143.3520067, "coordinateSource": "nominatim:紋別バスターミナル"},
    "紋別空港": {"lat": 44.3039016724, "lon": 143.404006958, "coordinateSource": "OurAirports MBE coordinate"},
}


def cache_path_for(cache_dir: Path, url: str) -> Path:
    suffix = Path(url.split("?", 1)[0]).suffix or ".html"
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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_trip(direction: str, start_name: str, end_name: str, start: str, end: str) -> dict[str, Any]:
    return {
        "tripId": f"monbetsu_airport:{direction}:001",
        "direction": direction,
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "stopTimes": [{"stopName": start_name, "time": start}, {"stopName": end_name, "time": end}],
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cache_path = fetch(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    if cache_path.stat().st_size < 10_000:
        raise ValueError(f"Monbetsu airport source looks too small: {cache_path}")
    trips = [
        make_trip("to_airport", "紋別バスターミナル", "紋別空港", "11:40", "12:01"),
        make_trip("from_airport", "紋別空港", "紋別バスターミナル", "12:35", "12:56"),
    ]
    stop_names = ["紋別バスターミナル", "紋別空港"]
    route = {
        "sourceKind": "official_monbetsu_airport_city_html",
        "operatorName": "紋別市空港連絡バス",
        "airportIata": "MBE",
        "routeCode": "monbetsu_airport_city_shuttle",
        "routeName": "紋別バスターミナル ⇔ 紋別空港",
        "sourceUrl": SOURCE_URL,
        "sourceUrls": [SOURCE_URL],
        "cachePath": str(cache_path.relative_to(ROOT)),
        "cachePaths": [str(cache_path.relative_to(ROOT))],
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "adultFareYen": 0,
        "routeStopNames": stop_names,
        "tripCount": len(trips),
        "stops": [{"stopName": name, **STOPS[name]} for name in stop_names],
        "busStops": [{"name": name, **STOPS[name]} for name in stop_names],
        "trips": trips,
        "sourceNotes": [
            "Endpoint stop-times are from the official Monbetsu city airport-access page for 2026-03-29 through 2026-06-30.",
            "Intermediate city stops are visible in the official source but not emitted until coordinates are reviewed.",
            "Engaru-area shuttle is reservation-only three days in advance and is kept as a source limitation for now.",
        ],
    }
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_monbetsu_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source page retains copyright.",
        "routes": [route],
    }
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "routeCount": 1,
        "tripCount": len(trips),
        "stopCount": len(stop_names),
        "coordinateStopCount": len(stop_names),
        "directionCounts": dict(Counter(trip["direction"] for trip in trips)),
        "sourceUrls": [SOURCE_URL],
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
