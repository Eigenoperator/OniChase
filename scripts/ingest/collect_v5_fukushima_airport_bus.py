#!/usr/bin/env python3
"""Collect Fukushima Airport official airport-bus timetable."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "fukushima_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_fukushima_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_fukushima_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_fukushima_airport_official_bus_audit.json"

SOURCE_URL = "https://www.fukushima-koutu.co.jp/express/line/06-revision.html"
SERVICE_START = "20260329"
SERVICE_END = "20270331"

STOPS = {
    "郡山駅前": {"lat": 37.3982637, "lon": 140.3888038, "coordinateSource": "v4 station group centroid:郡山:福島県"},
    "福島空港": {"lat": 37.2274017334, "lon": 140.430999756, "coordinateSource": "OurAirports FKS coordinate"},
}

TO_AIRPORT = [
    ("06:00", "06:45", "daily"),
    ("08:00", "08:45", "daily"),
    ("10:55", "11:40", "daily"),
    ("13:05", "13:50", ["tuesday", "friday"]),
    ("15:35", "16:20", "daily"),
    ("16:45", "17:30", "daily"),
]

FROM_AIRPORT = [
    ("09:15", "09:55", "daily"),
    ("12:20", "13:00", "daily"),
    ("15:30", "16:10", ["tuesday", "friday"]),
    ("17:00", "17:40", "daily"),
    ("18:15", "18:55", "daily"),
    ("20:25", "21:05", "daily"),
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
    required = ["2026年3月29日から", "郡山駅前", "中央工業団地", "福島空港", "06:00", "20:25", "1,200"]
    missing = [item for item in required if item not in text]
    if missing:
        raise ValueError(f"Fukushima airport page missing expected markers: {missing}")


def make_trip(direction: str, start_name: str, end_name: str, start: str, end: str, service_days: Any, index: int) -> dict[str, Any]:
    return {
        "tripId": f"fukushima_airport:{direction}:{index:03d}",
        "direction": direction,
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": service_days,
        "stopTimes": [{"stopName": start_name, "time": start}, {"stopName": end_name, "time": end}],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def service_key(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(value)
    return str(value)


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cache_path = fetch(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    assert_source(cache_path)
    trips = []
    for index, (start, end, service_days) in enumerate(TO_AIRPORT, start=1):
        trips.append(make_trip("to_airport", "郡山駅前", "福島空港", start, end, service_days, index))
    for index, (start, end, service_days) in enumerate(FROM_AIRPORT, start=1):
        trips.append(make_trip("from_airport", "福島空港", "郡山駅前", start, end, service_days, index))
    route = {
        "sourceKind": "official_fukushima_airport_html",
        "operatorName": "福島交通",
        "airportIata": "FKS",
        "routeCode": "fukushima_airport_koriyama_station",
        "routeName": "郡山駅前 ⇔ 福島空港",
        "sourceUrl": SOURCE_URL,
        "sourceUrls": [SOURCE_URL],
        "cachePath": str(cache_path.relative_to(ROOT)),
        "cachePaths": [str(cache_path.relative_to(ROOT))],
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "adultFareYen": 1200,
        "routeStopNames": ["郡山駅前", "福島空港"],
        "tripCount": len(trips),
        "stops": [{"stopName": name, **STOPS[name]} for name in ["郡山駅前", "福島空港"]],
        "busStops": [{"name": name, **STOPS[name]} for name in ["郡山駅前", "福島空港"]],
        "trips": trips,
        "sourceNotes": [
            "Endpoint stop-times and fare are from Fukushima Kotsu official airport limousine page for service from 2026-03-29.",
            "Central Industrial Park is not emitted because official restrictions mark it as boarding-only toward the airport and alighting-only toward Koriyama.",
            "Taiwan-flight connection rows are encoded as Tuesday/Friday-only service.",
        ],
    }
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_fukushima_airport_bus",
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
        "serviceDayCounts": dict(Counter(service_key(trip["serviceDays"]) for trip in trips)),
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
