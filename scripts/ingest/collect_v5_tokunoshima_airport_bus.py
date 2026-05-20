#!/usr/bin/env python3
"""Collect Tokunoshima Airport official airport-bus timetable."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "tokunoshima_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_tokunoshima_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_tokunoshima_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_tokunoshima_airport_official_bus_audit.json"

SOURCE_URL = "http://www.sogorikuun.com/bus_time/"
SERVICE_START = "20260329"
SERVICE_END = "20270331"

STOPS = {
    "亀津": {"lat": 27.7219991, "lon": 129.0077090, "coordinateSource": "nominatim:place:亀津,徳之島町"},
    "徳之島空港": {"lat": 27.836382, "lon": 128.881356, "coordinateSource": "OurAirports TKN coordinate"},
}

TO_AIRPORT = [
    ("08:00", "08:47", "daily"),
    ("09:00", "09:47", "daily"),
    ("10:00", "10:47", "weekday"),
    ("11:50", "12:37", "daily"),
    ("13:40", "14:27", "daily"),
    ("15:30", "16:17", "weekday"),
    ("16:20", "17:07", "daily"),
    ("17:40", "18:27", "daily"),
]

FROM_AIRPORT = [
    ("07:05", "07:59", "daily"),
    ("08:00", "08:54", "weekday"),
    ("09:15", "10:09", "daily"),
    ("10:10", "11:04", "daily"),
    ("11:20", "12:14", "weekday"),
    ("13:00", "13:54", "daily"),
    ("15:00", "15:54", "daily"),
    ("17:25", "18:19", "daily"),
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


def assert_source(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    required = ["亀津 ～ 平土野 ～ 空港 線", "空港 ～ 平土野～ 亀津 線", "8:47", "17:25"]
    missing = [item for item in required if item not in text]
    if missing:
        raise ValueError(f"Tokunoshima official timetable missing expected markers: {missing}")


def make_trip(direction: str, start_name: str, end_name: str, start: str, end: str, service_days: str, index: int) -> dict[str, Any]:
    return {
        "tripId": f"tokunoshima_airport:{direction}:{index:03d}",
        "direction": direction,
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": service_days,
        "stopTimes": [{"stopName": start_name, "time": start}, {"stopName": end_name, "time": end}],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cache_path = fetch(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    assert_source(cache_path)
    trips = []
    for index, (start, end, service_days) in enumerate(TO_AIRPORT, start=1):
        trips.append(make_trip("to_airport", "亀津", "徳之島空港", start, end, service_days, index))
    for index, (start, end, service_days) in enumerate(FROM_AIRPORT, start=1):
        trips.append(make_trip("from_airport", "徳之島空港", "亀津", start, end, service_days, index))
    route = {
        "sourceKind": "official_tokunoshima_airport_html",
        "operatorName": "徳之島総合陸運",
        "airportIata": "TKN",
        "routeCode": "tokunoshima_airport_kametsu",
        "routeName": "亀津 ⇔ 徳之島空港",
        "sourceUrl": SOURCE_URL,
        "sourceUrls": [SOURCE_URL],
        "cachePath": str(cache_path.relative_to(ROOT)),
        "cachePaths": [str(cache_path.relative_to(ROOT))],
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "routeStopNames": ["亀津", "徳之島空港"],
        "tripCount": len(trips),
        "stops": [{"stopName": name, **STOPS[name]} for name in ["亀津", "徳之島空港"]],
        "busStops": [{"name": name, **STOPS[name]} for name in ["亀津", "徳之島空港"]],
        "trips": trips,
        "sourceNotes": [
            "Endpoint stop-times are from Tokunoshima Sogo Rikuun official route-bus HTML table, revised 2020-03-29 and still published as the current timetable.",
            "Only 亀津 and 徳之島空港 are promoted for gameplay until intermediate island bus-stop coordinates are reviewed.",
            "Blue official rows are encoded as weekday service. Red school-holiday limitation rows without airport stops are intentionally not emitted.",
            "Official fare table is image-only, so no fare is emitted until the current amount is verified without guessing.",
        ],
    }
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_tokunoshima_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source HTML retains copyright.",
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
        "serviceDayCounts": dict(Counter(trip["serviceDays"] for trip in trips)),
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
