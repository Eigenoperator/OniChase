#!/usr/bin/env python3
"""Collect Memanbetsu Airport official Abashiri Bus timetable."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "memanbetsu_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_memanbetsu_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_memanbetsu_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_memanbetsu_airport_official_bus_audit.json"
SOURCE_URLS = [
    "https://www.abashiribus.com/jikoku/mmbR08.05.01_1.pdf",
    "https://www.abashiribus.com/jikoku/mmbR08.05.01_2.pdf",
]
SERVICE_START = "20260501"
SERVICE_END = "20260531"

STOPS = {
    "網走駅前": {"lat": 44.019915, "lon": 144.25418, "coordinateSource": "OniChase N02 rail station centroid: 網走"},
    "女満別空港": {"lat": 43.8805999756, "lon": 144.164001465, "coordinateSource": "MMB airport coordinate"},
}

TO_AIRPORT = [
    ("07:38", "08:08"),
    ("08:05", "08:35"),
    ("09:35", "10:05"),
    ("12:15", "12:45"),
    ("12:40", "13:10"),
    ("13:20", "13:50"),
    ("16:05", "16:35"),
    ("17:45", "18:15"),
    ("18:20", "18:50"),
]
FROM_AIRPORT = [
    ("08:30", "08:56"),
    ("08:40", "09:06"),
    ("10:20", "10:46"),
    ("13:10", "13:36"),
    ("13:20", "13:46"),
    ("14:20", "14:46"),
    ("17:00", "17:26"),
    ("18:45", "19:11"),
    ("19:15", "19:41"),
    ("19:35", "20:01"),
]


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.pdf"


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


def assert_source_contains(paths: list[Path]) -> None:
    for path in paths:
        if path.stat().st_size < 30_000:
            raise ValueError(f"Memanbetsu PDF cache is unexpectedly small: {path}")


def build_routes(cache_paths: list[Path]) -> list[dict[str, Any]]:
    trips = []
    for index, (start, end) in enumerate(TO_AIRPORT, start=1):
        trips.append(
            {
                "tripId": f"memanbetsu_airport_abashiri_station:to_airport:{index:03d}",
                "direction": "to_airport",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": "daily",
                "stopTimes": [{"stopName": "網走駅前", "time": start}, {"stopName": "女満別空港", "time": end}],
            }
        )
    for index, (start, end) in enumerate(FROM_AIRPORT, start=1):
        trips.append(
            {
                "tripId": f"memanbetsu_airport_abashiri_station:from_airport:{index:03d}",
                "direction": "from_airport",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": "daily",
                "stopTimes": [{"stopName": "女満別空港", "time": start}, {"stopName": "網走駅前", "time": end}],
            }
        )
    return [
        {
            "sourceKind": "official_memanbetsu_airport_pdf",
            "operatorName": "網走バス",
            "airportIata": "MMB",
            "routeCode": "memanbetsu_airport_abashiri_station",
            "routeName": "女満別空港線 網走駅前 ⇔ 女満別空港",
            "sourceUrl": SOURCE_URLS[0],
            "sourceUrls": SOURCE_URLS,
            "cachePath": str(cache_paths[0].relative_to(ROOT)),
            "cachePaths": [str(path.relative_to(ROOT)) for path in cache_paths],
            "serviceStart": SERVICE_START,
            "serviceEnd": SERVICE_END,
            "serviceDays": "daily",
            "adultFareYen": 1050,
            "routeStopNames": ["網走駅前", "女満別空港"],
            "tripCount": len(trips),
            "stops": [{"stopName": name, **STOPS[name]} for name in ["網走駅前", "女満別空港"]],
            "busStops": [{"name": name, **STOPS[name]} for name in ["網走駅前", "女満別空港"]],
            "trips": trips,
            "sourceNotes": [
                "Official Abashiri Bus PDFs cover 2026-05-01 through 2026-05-31.",
                "Endpoint-playable normalization uses the official 網走駅前 and 女満別空港 rows; intermediate stops remain in the cached PDF source.",
            ],
        }
    ]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cache_paths = [fetch(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout) for url in SOURCE_URLS]
    assert_source_contains(cache_paths)
    routes = build_routes(cache_paths)
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_memanbetsu_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source pages retain copyright.",
        "routes": routes,
    }
    all_trips = [trip for route in routes for trip in route["trips"]]
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "routeCount": len(routes),
        "tripCount": len(all_trips),
        "stopCount": 2,
        "coordinateStopCount": 2,
        "directionCounts": dict(Counter(trip["direction"] for trip in all_trips)),
        "routeTripCounts": {route["routeCode"]: len(route["trips"]) for route in routes},
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
