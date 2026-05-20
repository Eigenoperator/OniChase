#!/usr/bin/env python3
"""Collect Shonai Airport official limousine-bus timetable."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "shonai_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_shonai_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_shonai_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_shonai_airport_official_bus_audit.json"

TSURUOKA_URL = "https://www.shonaikotsu.jp/limousine/tsuruoka.html"
SAKATA_URL = "https://www.shonaikotsu.jp/limousine/sakata.html"
SERVICE_START = "20260401"
SERVICE_END = "20260531"

STOPS = {
    "鶴岡駅前": {"lat": 38.740095, "lon": 139.83539, "coordinateSource": "v4 station group centroid:鶴岡"},
    "酒田駅前": {"lat": 38.92221, "lon": 139.845915, "coordinateSource": "v4 station group centroid:酒田"},
    "庄内空港": {"lat": 38.812199, "lon": 139.787003, "coordinateSource": "OurAirports SYO coordinate"},
}

ROUTES = [
    {
        "routeCode": "shonai_airport_tsuruoka_station",
        "routeName": "鶴岡駅前 ⇔ 庄内空港",
        "sourceUrl": TSURUOKA_URL,
        "startName": "鶴岡駅前",
        "fare": 1000,
        "times": [("05:57", "06:23"), ("07:29", "07:55"), ("10:44", "11:10"), ("13:54", "14:20"), ("16:14", "16:40")],
    },
    {
        "routeCode": "shonai_airport_sakata_station",
        "routeName": "酒田駅前 ⇔ 庄内空港",
        "sourceUrl": SAKATA_URL,
        "startName": "酒田駅前",
        "fare": 1010,
        "times": [("05:47", "06:20"), ("07:22", "07:55"), ("10:37", "11:10"), ("13:47", "14:20"), ("16:07", "16:40")],
    },
]


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"


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


def assert_source(path: Path, markers: list[str]) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    missing = [item for item in markers if item not in text]
    if missing:
        raise ValueError(f"Shonai airport page missing expected markers: {missing}")


def make_trip(route_code: str, start_name: str, start: str, end: str, index: int) -> dict[str, Any]:
    return {
        "tripId": f"{route_code}:to_airport:{index:03d}",
        "direction": "to_airport",
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "stopTimes": [{"stopName": start_name, "time": start}, {"stopName": "庄内空港", "time": end}],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cache_paths = {
        TSURUOKA_URL: fetch(TSURUOKA_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout),
        SAKATA_URL: fetch(SAKATA_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout),
    }
    assert_source(cache_paths[TSURUOKA_URL], ["2026年4月1日～2026年5月31日", "鶴岡駅前⑤", "庄内空港着", "1,000円"])
    assert_source(cache_paths[SAKATA_URL], ["2026年4月1日～2026年5月31日", "酒田駅前", "庄内空港着", "1,010円"])
    routes = []
    for route_def in ROUTES:
        trips = [
            make_trip(route_def["routeCode"], route_def["startName"], start, end, index)
            for index, (start, end) in enumerate(route_def["times"], start=1)
        ]
        stop_names = [route_def["startName"], "庄内空港"]
        routes.append(
            {
                "sourceKind": "official_shonai_airport_html",
                "operatorName": "庄内交通",
                "airportIata": "SYO",
                "routeCode": route_def["routeCode"],
                "routeName": route_def["routeName"],
                "sourceUrl": route_def["sourceUrl"],
                "sourceUrls": [route_def["sourceUrl"]],
                "cachePath": str(cache_paths[route_def["sourceUrl"]].relative_to(ROOT)),
                "cachePaths": [str(cache_paths[route_def["sourceUrl"]].relative_to(ROOT))],
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": "daily",
                "adultFareYen": route_def["fare"],
                "routeStopNames": stop_names,
                "tripCount": len(trips),
                "stops": [{"stopName": name, **STOPS[name]} for name in stop_names],
                "busStops": [{"name": name, **STOPS[name]} for name in stop_names],
                "trips": trips,
                "sourceNotes": [
                    "City-to-airport fixed stop-times and fares are from Shonai Kotsu official limousine pages for 2026-04-01 through 2026-05-31.",
                    "Airport-to-city trips are arrival-triggered, departing roughly 10 minutes after flight arrival, and are not emitted until the V5 bus model supports arrival-triggered departures.",
                ],
            }
        )
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_shonai_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source HTML retains copyright.",
        "routes": routes,
    }
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "routeCount": len(routes),
        "tripCount": sum(len(route["trips"]) for route in routes),
        "stopCount": len(STOPS),
        "coordinateStopCount": len(STOPS),
        "directionCounts": dict(Counter(trip["direction"] for route in routes for trip in route["trips"])),
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
