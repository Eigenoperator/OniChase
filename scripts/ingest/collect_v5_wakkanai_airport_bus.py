#!/usr/bin/env python3
"""Collect Wakkanai Airport official airport-bus timetable."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "wakkanai_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_wakkanai_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_wakkanai_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_wakkanai_airport_official_bus_audit.json"

SOURCE_URL = "http://www.soyabus.co.jp/airport/"
PDF_URL = "http://www.soyabus.co.jp/app-wp/wp-content/themes/Souyabus-child/images/airport/Airport_2026_0329-1024.pdf"
SERVICE_START = "20260329"
SERVICE_END = "20261024"

STOPS = {
    "稚内フェリーターミナル": {"lat": 45.4157347, "lon": 141.6825650, "coordinateSource": "nominatim:ferry_terminal:稚内フェリーターミナル"},
    "稚内駅前ターミナル": {"lat": 45.4161633, "lon": 141.6773, "coordinateSource": "v4 station group centroid:稚内"},
    "空港ターミナル": {"lat": 45.4042015076, "lon": 141.800994873, "coordinateSource": "OurAirports WKJ coordinate"},
}

TO_AIRPORT = [
    ("10:20", "10:25", "10:55", "daily"),
    ("11:55", "12:00", "12:30", "daily"),
    ("14:15", "14:20", "14:50", "summer"),
    ("15:35", "15:40", "16:10", "daily"),
]

FROM_AIRPORT = [
    ("11:15", "11:45", "11:50", "daily"),
    ("12:55", "13:25", "13:30", "daily"),
    ("15:20", "15:50", "15:55", "summer"),
    ("16:30", "17:00", "17:05", "daily"),
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


def assert_source(html_path: Path, pdf_path: Path) -> None:
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    required = ["稚内市内⇔稚内空港連絡バス", "大人８００円", "Airport_2026_0329-1024.pdf"]
    missing = [item for item in required if item not in text]
    if missing:
        raise ValueError(f"Wakkanai airport page missing expected markers: {missing}")
    if pdf_path.stat().st_size < 100_000:
        raise ValueError(f"Wakkanai airport PDF looks too small: {pdf_path}")


def service_window(service: str) -> tuple[str, str]:
    if service == "summer":
        return "20260601", "20260930"
    return SERVICE_START, SERVICE_END


def make_trip(direction: str, stop_times: list[tuple[str, str]], service: str, index: int) -> dict[str, Any]:
    start, end = service_window(service)
    return {
        "tripId": f"wakkanai_airport:{direction}:{index:03d}",
        "direction": direction,
        "serviceStart": start,
        "serviceEnd": end,
        "serviceDays": "daily",
        "stopTimes": [{"stopName": name, "time": time} for name, time in stop_times],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    html_path = fetch(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    pdf_path = fetch(PDF_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    assert_source(html_path, pdf_path)
    trips = []
    for index, (ferry, station, airport, service) in enumerate(TO_AIRPORT, start=1):
        trips.append(
            make_trip(
                "to_airport",
                [("稚内フェリーターミナル", ferry), ("稚内駅前ターミナル", station), ("空港ターミナル", airport)],
                service,
                index,
            )
        )
    for index, (airport, station, ferry, service) in enumerate(FROM_AIRPORT, start=1):
        trips.append(
            make_trip(
                "from_airport",
                [("空港ターミナル", airport), ("稚内駅前ターミナル", station), ("稚内フェリーターミナル", ferry)],
                service,
                index,
            )
        )
    stop_names = ["稚内フェリーターミナル", "稚内駅前ターミナル", "空港ターミナル"]
    route = {
        "sourceKind": "official_wakkanai_airport_pdf",
        "operatorName": "宗谷バス",
        "airportIata": "WKJ",
        "routeCode": "wakkanai_airport_line",
        "routeName": "稚内フェリーターミナル ⇔ 稚内駅前ターミナル ⇔ 空港ターミナル",
        "sourceUrl": SOURCE_URL,
        "sourceUrls": [SOURCE_URL, PDF_URL],
        "cachePath": str(pdf_path.relative_to(ROOT)),
        "cachePaths": [str(html_path.relative_to(ROOT)), str(pdf_path.relative_to(ROOT))],
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "adultFareYen": 800,
        "routeStopNames": stop_names,
        "tripCount": len(trips),
        "stops": [{"stopName": name, **STOPS[name]} for name in stop_names],
        "busStops": [{"name": name, **STOPS[name]} for name in stop_names],
        "trips": trips,
        "sourceNotes": [
            "Stop-times and flat fare are from Soya Bus official airport page and 2026-03-29 through 2026-10-24 PDF.",
            "The third flight-connection pair is emitted only for 2026-06-01 through 2026-09-30, matching the official PDF.",
            "The official page notes airport-origin departures may wait for baggage claim if flights are delayed; scheduled PDF times are still emitted as planned times.",
        ],
    }
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_wakkanai_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source HTML/PDF retains copyright.",
        "routes": [route],
    }
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "routeCount": 1,
        "tripCount": len(trips),
        "stopCount": len(STOPS),
        "coordinateStopCount": len(STOPS),
        "directionCounts": dict(Counter(trip["direction"] for trip in trips)),
        "seasonalTripCount": sum(1 for trip in trips if trip["serviceStart"] == "20260601"),
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
