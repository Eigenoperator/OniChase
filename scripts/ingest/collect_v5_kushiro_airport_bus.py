#!/usr/bin/env python3
"""Collect Kushiro Airport official access-bus timetable."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "kushiro_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_kushiro_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_kushiro_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_kushiro_airport_official_bus_audit.json"

ACCESS_URL = "https://www.akanbus.co.jp/airport/"
TIMETABLE_SCRIPT_URL = "https://www.akanbus.co.jp/airport/time-table.cgi"
TIMETABLE_URL = "https://www.akanbus.co.jp/airport/data/80_01.pdf"
SERVICE_START = "20260424"
SERVICE_END = "20260531"

STOPS = {
    "釧路駅前": {"lat": 42.99057, "lon": 144.38204, "coordinateSource": "OniChase N02 rail station centroid: 釧路"},
    "たんちょう釧路空港": {"lat": 43.0410003662, "lon": 144.192993164, "coordinateSource": "KUH airport coordinate"},
}

TO_AIRPORT_ROWS = [
    ("07:25", "08:10", "daily", "ANA4872"),
    ("07:45", "08:30", "daily", "JAL2762"),
    ("08:25", "09:10", "daily", "ADO72/NH4772"),
    ("08:30", "09:15", "daily", "JAL540"),
    ("11:25", "12:10", "date_limited", "JAL2764", "20260427", "20260528"),
    ("12:05", "12:50", "daily", "ANA742"),
    ("13:05", "13:50", "daily", "ANA4874"),
    ("13:15", "14:00", "daily", "JAL542"),
    ("13:55", "14:40", "daily", "JAL2766"),
    ("15:40", "16:25", "daily", "ANA4876"),
    ("16:30", "17:15", "daily", "JAL2768"),
    ("17:00", "17:45", "daily", "ADO74/NH4774"),
    ("18:15", "19:00", "daily", "JAL544"),
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


def assert_source_contains(access_cache: Path, script_cache: Path, timetable_cache: Path) -> None:
    access = access_cache.read_text(encoding="utf-8", errors="ignore")
    script = script_cache.read_text(encoding="utf-8", errors="ignore")
    if "1,200円" not in access or "釧路駅前" not in access:
        raise ValueError("Kushiro airport access page no longer has expected fare/stop markers")
    if "80_01.pdf" not in script:
        raise ValueError("Kushiro timetable script no longer points to the expected current PDF")
    if timetable_cache.stat().st_size < 50_000:
        raise ValueError("Kushiro timetable PDF cache is unexpectedly small")


def build_routes(access_cache: Path, script_cache: Path, timetable_cache: Path) -> list[dict[str, Any]]:
    trips = []
    for index, row in enumerate(TO_AIRPORT_ROWS, start=1):
        start, end, service, flight = row[:4]
        service_start = row[4] if len(row) > 4 else SERVICE_START
        service_end = row[5] if len(row) > 5 else SERVICE_END
        trips.append(
            {
                "tripId": f"kushiro_airport_kushiro_station:to_airport:{index:03d}",
                "direction": "to_airport",
                "serviceStart": service_start,
                "serviceEnd": service_end,
                "serviceDays": "daily",
                "notes": f"Connects outbound flight {flight}; official timetable marker={service}",
                "stopTimes": [{"stopName": "釧路駅前", "time": start}, {"stopName": "たんちょう釧路空港", "time": end}],
            }
        )
    return [
        {
            "sourceKind": "official_kushiro_airport_pdf",
            "operatorName": "阿寒バス",
            "airportIata": "KUH",
            "routeCode": "kushiro_airport_kushiro_station",
            "routeName": "釧路空港連絡バス 釧路駅前 ⇔ たんちょう釧路空港",
            "sourceUrl": TIMETABLE_URL,
            "sourceUrls": [ACCESS_URL, TIMETABLE_SCRIPT_URL, TIMETABLE_URL],
            "cachePath": str(timetable_cache.relative_to(ROOT)),
            "cachePaths": [
                str(access_cache.relative_to(ROOT)),
                str(script_cache.relative_to(ROOT)),
                str(timetable_cache.relative_to(ROOT)),
            ],
            "serviceStart": SERVICE_START,
            "serviceEnd": SERVICE_END,
            "serviceDays": "mixed_by_trip",
            "adultFareYen": 1200,
            "routeStopNames": ["釧路駅前", "たんちょう釧路空港"],
            "tripCount": len(trips),
            "stops": [{"stopName": name, **STOPS[name]} for name in ["釧路駅前", "たんちょう釧路空港"]],
            "busStops": [{"name": name, **STOPS[name]} for name in ["釧路駅前", "たんちょう釧路空港"]],
            "trips": trips,
            "sourceNotes": [
                "Official Akan Bus PDF covers 2026-04-24 through 2026-05-31.",
                "Airport-to-city buses are arrival-connected and officially depart about 10 to 25 minutes after each plane arrives, so they are documented but not emitted as fixed-clock trips until the bus model supports flexible arrival-connected departures.",
            ],
        }
    ]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    access_cache = fetch(ACCESS_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    script_cache = fetch(TIMETABLE_SCRIPT_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    timetable_cache = fetch(TIMETABLE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    assert_source_contains(access_cache, script_cache, timetable_cache)
    routes = build_routes(access_cache, script_cache, timetable_cache)
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_kushiro_airport_bus",
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
        "flexDirectionLimitations": {
            "from_airport": "Official source says city-bound bus departs about 10-25 minutes after each plane arrival; not emitted as fixed-clock trips.",
        },
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
