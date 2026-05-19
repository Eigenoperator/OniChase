#!/usr/bin/env python3
"""Collect Okayama Momotaro Airport official access-bus timetables."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "okayama_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_okayama_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_okayama_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_okayama_airport_official_bus_audit.json"
SOURCE_URL = "https://www.okayama-airport.org/access/bus"
SERVICE_START = "20260329"
SERVICE_END = "20260630"

WEEKDAYS_EXCEPT_TUE_SAT = ["monday", "wednesday", "thursday", "friday", "sunday"]

STOPS = {
    "岡山駅西口": {"lat": 34.6663, "lon": 133.9178, "coordinateSource": "OniChase N02 rail station centroid: 岡山"},
    "岡山桃太郎空港": {"lat": 34.7569, "lon": 133.8553, "coordinateSource": "OpenFlights / V5 flight airport map"},
    "倉敷駅北口": {"lat": 34.6017, "lon": 133.7655, "coordinateSource": "OniChase N02 rail station centroid: 倉敷"},
}

ROUTES = [
    {
        "routeCode": "okayama_airport_okayama_station",
        "routeName": "岡山空港リムジンバス 岡山駅西口 ⇔ 岡山桃太郎空港",
        "adultFareYen": 1000,
        "stops": ["岡山駅西口", "岡山桃太郎空港"],
        "rows": [
            ("to_airport", "06:00", "06:30", "daily", None),
            ("to_airport", "06:10", "06:40", "daily", None),
            ("to_airport", "06:40", "07:10", "daily", None),
            ("to_airport", "07:20", "07:50", "daily", None),
            ("to_airport", "08:30", "09:00", "daily", None),
            ("to_airport", "08:55", "09:25", "daily", None),
            ("to_airport", "10:40", "11:10", "daily", None),
            ("to_airport", "10:50", "11:20", "daily", None),
            ("to_airport", "12:55", "13:25", "daily", None),
            ("to_airport", "14:50", "15:20", WEEKDAYS_EXCEPT_TUE_SAT, "Official <★>: Monday/Wednesday/Thursday/Friday/Sunday only"),
            ("to_airport", "15:55", "16:25", "daily", None),
            ("to_airport", "16:05", "16:35", "daily", None),
            ("to_airport", "18:00", "18:30", "daily", None),
            ("to_airport", "18:25", "18:55", "daily", None),
            ("from_airport", "07:10", "07:40", "daily", None),
            ("from_airport", "09:15", "09:45", "daily", None),
            ("from_airport", "09:30", "10:00", "daily", "Official <1>: 2026-06-01 through 2026-06-30", "20260601", "20260630"),
            ("from_airport", "09:45", "10:15", "daily", "Official <2>: 2026-03-29 through 2026-05-31", "20260329", "20260531"),
            ("from_airport", "11:40", "12:10", "daily", None),
            ("from_airport", "11:50", "12:20", "daily", None),
            ("from_airport", "13:45", "14:15", "daily", None),
            ("from_airport", "15:55", "16:25", "daily", "Official <3>: current/future part 2026-05-07 through 2026-06-30", "20260507", "20260630"),
            ("from_airport", "16:55", "17:25", "daily", None),
            ("from_airport", "18:55", "19:25", "daily", None),
            ("from_airport", "19:20", "19:50", "daily", "Official <6>: current May segment", "20260501", "20260531"),
            ("from_airport", "20:30", "21:00", "daily", "Official <8>: 2026-04-24 through 2026-06-30", "20260424", "20260630"),
            ("from_airport", "21:10", "21:40", "daily", None),
            ("from_airport", "21:25", "21:55", "daily", "Official <6>: current May segment", "20260501", "20260531"),
        ],
    },
    {
        "routeCode": "okayama_airport_kurashiki_station",
        "routeName": "岡山空港リムジンバス 倉敷駅北口 ⇔ 岡山桃太郎空港",
        "adultFareYen": 1400,
        "stops": ["倉敷駅北口", "岡山桃太郎空港"],
        "rows": [
            ("to_airport", "06:00", "06:35", "daily", None),
            ("to_airport", "08:05", "08:40", "daily", None),
            ("to_airport", "10:45", "11:20", "daily", None),
            ("to_airport", "12:15", "12:50", "daily", None),
            ("to_airport", "15:35", "16:10", "daily", None),
            ("to_airport", "15:45", "16:20", "daily", None),
            ("to_airport", "17:45", "18:20", "daily", None),
            ("to_airport", "18:05", "18:40", "daily", None),
            ("from_airport", "09:15", "09:50", "daily", None),
            ("from_airport", "09:30", "10:05", "daily", "Official <1>: 2026-06-01 through 2026-06-30", "20260601", "20260630"),
            ("from_airport", "09:45", "10:20", "daily", "Official <2>: 2026-03-29 through 2026-05-31", "20260329", "20260531"),
            ("from_airport", "11:50", "12:25", "daily", None),
            ("from_airport", "12:05", "12:40", "daily", None),
            ("from_airport", "13:45", "14:20", "daily", None),
            ("from_airport", "15:55", "16:30", "daily", "Official <3>: current/future part 2026-05-07 through 2026-06-30", "20260507", "20260630"),
            ("from_airport", "18:55", "19:30", "daily", None),
            ("from_airport", "19:20", "19:55", "daily", None),
        ],
    },
]


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"


def fetch_html(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> Path:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def assert_source_contains(cache_path: Path) -> None:
    text = cache_path.read_text(encoding="utf-8", errors="ignore")
    required = ["岡山駅西口", "倉敷駅北口", "2026年03月29日～2026年06月30日", "1,000円", "1,400円"]
    missing = [item for item in required if item not in text]
    if missing:
        raise ValueError(f"official source no longer contains expected markers: {missing}")


def row_service(row: tuple[Any, ...], default_start: str, default_end: str) -> tuple[str | list[str], str, str, str | None]:
    service_days = row[3]
    note = row[4]
    start = row[5] if len(row) > 5 else default_start
    end = row[6] if len(row) > 6 else default_end
    return service_days, start, end, note


def build_trip(route: dict[str, Any], row: tuple[Any, ...], index: int) -> dict[str, Any]:
    direction, first, second = row[:3]
    service_days, start, end, note = row_service(row, SERVICE_START, SERVICE_END)
    stop_names = route["stops"] if direction == "to_airport" else list(reversed(route["stops"]))
    return {
        "tripId": f"{route['routeCode']}:{direction}:{index:03d}",
        "direction": direction,
        "serviceStart": start,
        "serviceEnd": end,
        "serviceDays": service_days,
        "notes": note,
        "stopTimes": [{"stopName": stop_names[0], "time": first}, {"stopName": stop_names[1], "time": second}],
    }


def build_routes(cache_path: Path) -> list[dict[str, Any]]:
    payload_routes = []
    for route in ROUTES:
        trips = [build_trip(route, row, index) for index, row in enumerate(route["rows"], start=1)]
        payload_routes.append(
            {
                "sourceKind": "official_okayama_airport_html",
                "operatorName": "岡山空港リムジンバス共同運行",
                "airportIata": "OKJ",
                "routeCode": route["routeCode"],
                "routeName": route["routeName"],
                "sourceUrl": SOURCE_URL,
                "cachePath": str(cache_path.relative_to(ROOT)),
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": "mixed_by_trip",
                "adultFareYen": route["adultFareYen"],
                "routeStopNames": route["stops"],
                "tripCount": len(trips),
                "stops": [{"stopName": name, **STOPS[name]} for name in route["stops"]],
                "busStops": [{"name": name, **STOPS[name]} for name in route["stops"]],
                "trips": trips,
                "sourceNotes": [
                    "Official Okayama Momotaro Airport bus page for 2026-03-29 through 2026-06-30.",
                    "Endpoint-playable normalization keeps station-airport timing; official special markers are preserved with service-date ranges where relevant to current/future V5 play.",
                ],
            }
        )
    return payload_routes


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cache_path = fetch_html(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    assert_source_contains(cache_path)
    routes = build_routes(cache_path)
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_okayama_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source pages retain copyright.",
        "routes": routes,
    }
    all_trips = [trip for route in routes for trip in route["trips"]]
    stop_names = sorted({stop["stopName"] for route in routes for stop in route["stops"]})
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "routeCount": len(routes),
        "tripCount": len(all_trips),
        "stopCount": len(stop_names),
        "coordinateStopCount": len([name for name in stop_names if STOPS[name].get("lat") and STOPS[name].get("lon")]),
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
