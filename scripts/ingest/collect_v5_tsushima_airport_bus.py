#!/usr/bin/env python3
"""Collect Tsushima Airport official local-bus timetable."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "tsushima_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_tsushima_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_tsushima_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_tsushima_airport_official_bus_audit.json"

SOURCE_URL = "https://tsushima-airport.co.jp/transportration"
SERVICE_START = "20260501"
SERVICE_END = "20261024"

STOPS = {
    "厳原": {"lat": 34.2027631, "lon": 129.2875119, "coordinateSource": "Nominatim manual cache: 対馬市役所/厳原中心部"},
    "比田勝": {"lat": 34.655668, "lon": 129.4691822, "coordinateSource": "Nominatim manual cache: 比田勝港"},
    "対馬やまねこ空港": {"lat": 34.2849006653, "lon": 129.330993652, "coordinateSource": "OurAirports TSJ coordinate"},
}

IZUHARA_TO_AIRPORT = [
    ("07:00", "07:24", "daily"),
    ("09:28", "09:52", "daily"),
    ("10:00", "10:29", "daily"),
    ("10:58", "11:22", "daily"),
    ("11:58", "12:57", "daily"),
    ("13:28", "13:52", "daily"),
    ("14:30", "14:54", "weekend"),
    ("15:10", "15:34", "daily"),
    ("15:28", "15:57", "daily"),
    ("15:53", "16:22", "daily"),
    ("17:28", "17:52", "daily"),
    ("18:00", "18:24", "daily"),
    ("18:46", "19:15", "daily"),
    ("19:06", "19:35", "daily"),
    ("19:23", "19:50", "daily"),
]
IZUHARA_FROM_AIRPORT = [
    ("08:16", "08:48", "daily"),
    ("08:35", "09:02", "daily"),
    ("10:20", "10:47", "daily"),
    ("10:40", "11:07", "daily"),
    ("13:10", "13:42", "weekend"),
    ("13:50", "14:17", "daily"),
    ("14:26", "14:58", "daily"),
    ("15:04", "15:31", "daily"),
    ("15:30", "15:57", "weekend"),
    ("16:35", "17:07", "daily"),
    ("18:25", "18:52", "daily"),
    ("18:46", "19:13", "daily"),
    ("19:45", "20:12", "daily"),
]
HITAKATSU_TO_AIRPORT = [
    ("06:35", "08:32", "daily"),
    ("08:40", "10:37", "daily"),
    ("09:00", "11:04", "daily"),
    ("11:49", "13:47", "daily"),
    ("13:00", "14:59", "daily"),
    ("16:45", "18:43", "daily"),
]
HITAKATSU_FROM_AIRPORT = [
    ("11:30", "13:26", "daily"),
    ("14:00", "15:56", "daily"),
    ("15:42", "17:38", "daily"),
    ("18:32", "20:28", "daily"),
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


def assert_source_contains(path: Path) -> None:
    html = path.read_text(encoding="utf-8", errors="ignore")
    markers = ["対馬やまねこ空港着", "対馬やまねこ空港発", "厳原発", "比田勝発", "空港発", "3,070円", "710円"]
    missing = [marker for marker in markers if marker not in html]
    if missing:
        raise ValueError(f"Tsushima airport page is missing expected markers: {missing}")


def make_trip(route_code: str, direction: str, start_name: str, end_name: str, start: str, end: str, service_days: str, index: int) -> dict[str, Any]:
    return {
        "tripId": f"{route_code}:{direction}:{index:03d}",
        "direction": direction,
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": service_days,
        "stopTimes": [{"stopName": start_name, "time": start}, {"stopName": end_name, "time": end}],
    }


def build_route(route_code: str, route_name: str, endpoint: str, fare: int, to_rows: list[tuple[str, str, str]], from_rows: list[tuple[str, str, str]], cache_path: Path) -> dict[str, Any]:
    trips = []
    for index, (start, end, service_days) in enumerate(to_rows, start=1):
        trips.append(make_trip(route_code, "to_airport", endpoint, "対馬やまねこ空港", start, end, service_days, index))
    for index, (start, end, service_days) in enumerate(from_rows, start=1):
        trips.append(make_trip(route_code, "from_airport", "対馬やまねこ空港", endpoint, start, end, service_days, index))
    return {
        "sourceKind": "official_tsushima_airport_html",
        "operatorName": "対馬交通",
        "airportIata": "TSJ",
        "routeCode": route_code,
        "routeName": route_name,
        "sourceUrl": SOURCE_URL,
        "sourceUrls": [SOURCE_URL],
        "cachePath": str(cache_path.relative_to(ROOT)),
        "cachePaths": [str(cache_path.relative_to(ROOT))],
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "mixed_by_trip",
        "adultFareYen": fare,
        "routeStopNames": [endpoint, "対馬やまねこ空港"],
        "tripCount": len(trips),
        "stops": [{"stopName": name, **STOPS[name]} for name in [endpoint, "対馬やまねこ空港"]],
        "busStops": [{"name": name, **STOPS[name]} for name in [endpoint, "対馬やまねこ空港"]],
        "trips": trips,
        "sourceNotes": [
            "Official Tsushima Airport page publishes bus rows without an explicit update date; this source snapshot is retained in cache.",
            "Rows that only expose 仁位 or 赤島 endpoints are left out until those intermediate stop coordinates are reviewed.",
        ],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cache_path = fetch(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    assert_source_contains(cache_path)
    routes = [
        build_route("tsushima_airport_izuhara", "対馬やまねこ空港線 厳原 ⇔ 対馬やまねこ空港", "厳原", 710, IZUHARA_TO_AIRPORT, IZUHARA_FROM_AIRPORT, cache_path),
        build_route("tsushima_airport_hitakatsu", "対馬やまねこ空港線 比田勝 ⇔ 対馬やまねこ空港", "比田勝", 3070, HITAKATSU_TO_AIRPORT, HITAKATSU_FROM_AIRPORT, cache_path),
    ]
    all_trips = [trip for route in routes for trip in route["trips"]]
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_tsushima_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source pages retain copyright.",
        "routes": routes,
    }
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "routeCount": len(routes),
        "tripCount": len(all_trips),
        "stopCount": 3,
        "coordinateStopCount": 3,
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
