#!/usr/bin/env python3
"""Collect Izumo Enmusubi Airport official airport-bus timetables."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "izumo_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_izumo_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_izumo_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_izumo_airport_official_bus_audit.json"

IZUMO_PAGE_URL = "https://t-izumo.ichibata.co.jp/airport-bus-izumo/"
MATSUE_PAGE_URL = "https://t-matsue.ichibata.co.jp/airport-bus-izumo/"
IZUMO_PDF_URL = "https://t-izumo.ichibata.co.jp/wp-content/media/3.29%EF%BD%9E5.31%E5%87%BA%E9%9B%B2%E7%B7%9A.pdf"
MATSUE_PDF_URL = "https://t-matsue.ichibata.co.jp/wp-content/media/%E5%87%BA%E9%9B%B2%E7%A9%BA%E6%B8%AF%E9%80%A3%E7%B5%A1%E3%83%90%E3%82%B9%E6%99%82%E5%88%BB%E8%A1%A8%E6%96%B0%EF%BC%892026.3.29-5.31.pdf"
SERVICE_START = "20260329"
SERVICE_END = "20260531"

STOPS = {
    "出雲市駅": {"lat": 35.360595, "lon": 132.7555817, "coordinateSource": "v4 station group centroid:出雲市"},
    "松江しんじ湖温泉駅": {"lat": 35.46708, "lon": 133.045395, "coordinateSource": "v4 station group centroid:松江しんじ湖温泉"},
    "JR松江駅": {"lat": 35.46409, "lon": 133.063965, "coordinateSource": "v4 station group centroid:松江"},
    "出雲空港": {"lat": 35.413601, "lon": 132.889999, "coordinateSource": "OurAirports IZO coordinate"},
}

IZUMO_TO_AIRPORT = [
    ("06:20", "06:50"),
    ("06:45", "07:15"),
    ("07:00", "07:30"),
    ("09:40", "10:10"),
    ("10:05", "10:35"),
    ("10:25", "10:55"),
    ("14:20", "14:50"),
    ("15:20", "15:50"),
    ("16:50", "17:20"),
    ("17:15", "17:45"),
    ("17:50", "18:20"),
]

IZUMO_FROM_AIRPORT = [
    ("08:10", "08:40"),
    ("08:30", "09:00"),
    ("08:45", "09:15"),
    ("10:40", "11:10"),
    ("11:15", "11:45"),
    ("11:25", "11:55"),
    ("15:30", "16:00"),
    ("16:30", "17:00"),
    ("18:15", "18:45"),
    ("18:35", "19:05"),
    ("19:05", "19:35"),
    ("19:55", "20:25"),
]

MATSUE_TO_AIRPORT = [
    ("06:00", "06:10", "06:45"),
    ("06:40", "06:50", "07:25"),
    ("07:00", "07:10", "07:45"),
    ("07:25", "07:40", "08:15"),
    ("09:10", "09:20", "09:55"),
    ("09:50", "10:00", "10:35"),
    ("10:10", "10:20", "10:55"),
    ("14:10", "14:20", "14:55"),
    ("15:25", "15:40", "16:15"),
    ("16:50", "17:00", "17:35"),
    ("17:15", "17:30", "18:05"),
    ("17:25", "17:40", "18:15"),
]

MATSUE_FROM_AIRPORT = [
    ("08:10", "08:45", "08:51"),
    ("08:30", "09:05", "09:11"),
    ("08:45", "09:20", "09:26"),
    ("10:40", "11:15", "11:21"),
    ("11:15", "11:50", "11:56"),
    ("11:25", "12:00", "12:06"),
    ("15:30", "16:05", "16:11"),
    ("16:30", "17:05", "17:11"),
    ("18:15", "18:50", "18:56"),
    ("18:35", "19:10", "19:16"),
    ("19:05", "19:40", "19:46"),
    ("19:55", "20:30", "20:36"),
]


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


def assert_source(path: Path) -> None:
    if path.stat().st_size < 10_000:
        raise ValueError(f"Izumo airport official source looks too small: {path}")


def make_trip(trip_id: str, direction: str, stops: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "tripId": trip_id,
        "direction": direction,
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "stopTimes": [{"stopName": stop_name, "time": time} for stop_name, time in stops],
    }


def build_izumo_route(cache_paths: list[Path]) -> dict[str, Any]:
    trips = []
    for index, (start, end) in enumerate(IZUMO_TO_AIRPORT, start=1):
        trips.append(make_trip(f"izumo_airport:izumo_to_airport:{index:03d}", "to_airport", [("出雲市駅", start), ("出雲空港", end)]))
    for index, (start, end) in enumerate(IZUMO_FROM_AIRPORT, start=1):
        trips.append(make_trip(f"izumo_airport:izumo_from_airport:{index:03d}", "from_airport", [("出雲空港", start), ("出雲市駅", end)]))
    stop_names = ["出雲市駅", "出雲空港"]
    return {
        "sourceKind": "official_izumo_airport_pdf",
        "operatorName": "出雲一畑交通",
        "airportIata": "IZO",
        "routeCode": "izumo_airport_izumoshi_station",
        "routeName": "出雲市駅 ⇔ 出雲空港",
        "sourceUrl": IZUMO_PDF_URL,
        "sourceUrls": [IZUMO_PAGE_URL, IZUMO_PDF_URL],
        "cachePath": str(cache_paths[1].relative_to(ROOT)),
        "cachePaths": [str(path.relative_to(ROOT)) for path in cache_paths],
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "adultFareYen": 850,
        "routeStopNames": stop_names,
        "tripCount": len(trips),
        "stops": [{"stopName": name, **STOPS[name]} for name in stop_names],
        "busStops": [{"name": name, **STOPS[name]} for name in stop_names],
        "trips": trips,
        "sourceNotes": [
            "Endpoint stop-times are from the official 2026-03-29 through 2026-05-31 PDF.",
            "Temporary 4/29-5/10 and 4/29-5/11 trips are not emitted because the V5 planner service date is after those windows.",
        ],
    }


def build_matsue_route(cache_paths: list[Path]) -> dict[str, Any]:
    trips = []
    for index, (onsen, matsue, airport) in enumerate(MATSUE_TO_AIRPORT, start=1):
        trips.append(
            make_trip(
                f"izumo_airport:matsue_to_airport:{index:03d}",
                "to_airport",
                [("松江しんじ湖温泉駅", onsen), ("JR松江駅", matsue), ("出雲空港", airport)],
            )
        )
    for index, (airport, matsue, onsen) in enumerate(MATSUE_FROM_AIRPORT, start=1):
        trips.append(
            make_trip(
                f"izumo_airport:matsue_from_airport:{index:03d}",
                "from_airport",
                [("出雲空港", airport), ("JR松江駅", matsue), ("松江しんじ湖温泉駅", onsen)],
            )
        )
    stop_names = ["松江しんじ湖温泉駅", "JR松江駅", "出雲空港"]
    return {
        "sourceKind": "official_izumo_airport_matsue_pdf",
        "operatorName": "松江一畑交通",
        "airportIata": "IZO",
        "routeCode": "izumo_airport_matsue_station",
        "routeName": "松江しんじ湖温泉駅・JR松江駅 ⇔ 出雲空港",
        "sourceUrl": MATSUE_PDF_URL,
        "sourceUrls": [MATSUE_PAGE_URL, MATSUE_PDF_URL],
        "cachePath": str(cache_paths[1].relative_to(ROOT)),
        "cachePaths": [str(path.relative_to(ROOT)) for path in cache_paths],
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "adultFareYen": 1400,
        "routeStopNames": stop_names,
        "tripCount": len(trips),
        "stops": [{"stopName": name, **STOPS[name]} for name in stop_names],
        "busStops": [{"name": name, **STOPS[name]} for name in stop_names],
        "trips": trips,
        "sourceNotes": [
            "Stop-times are from the official 2026-03-29 through 2026-05-31 Matsue-line PDF.",
            "Temporary 4/29-5/10 and 4/29-5/11 trips are not emitted because the V5 planner service date is after those windows.",
        ],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    izumo_cache_paths = [
        fetch(IZUMO_PAGE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout),
        fetch(IZUMO_PDF_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout),
    ]
    matsue_cache_paths = [
        fetch(MATSUE_PAGE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout),
        fetch(MATSUE_PDF_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout),
    ]
    for path in izumo_cache_paths + matsue_cache_paths:
        assert_source(path)
    routes = [build_izumo_route(izumo_cache_paths), build_matsue_route(matsue_cache_paths)]
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_izumo_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source pages/PDFs retain copyright.",
        "routes": routes,
    }
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "routeCount": len(routes),
        "tripCount": sum(len(route["trips"]) for route in routes),
        "stopCount": len({stop["name"] for route in routes for stop in route["busStops"]}),
        "coordinateStopCount": len({stop["name"] for route in routes for stop in route["busStops"]}),
        "directionCounts": dict(Counter(trip["direction"] for route in routes for trip in route["trips"])),
        "sourceUrls": [IZUMO_PAGE_URL, IZUMO_PDF_URL, MATSUE_PAGE_URL, MATSUE_PDF_URL],
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
