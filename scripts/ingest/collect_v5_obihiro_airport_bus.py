#!/usr/bin/env python3
"""Collect Tokachi-Obihiro Airport official airport-bus timetable."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "obihiro_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_obihiro_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_obihiro_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_obihiro_airport_official_bus_audit.json"

SOURCE_URL = "https://www.tokachibus.jp/bus/wp-content/uploads/KUKOUPDF/KUKOU8_03-2.pdf"
SERVICE_START = "20260330"
SERVICE_END = "20261024"

STOPS = {
    "帯広駅バスターミナル": {"lat": 42.91807, "lon": 143.202105, "coordinateSource": "v4 station group centroid:帯広"},
    "とかち帯広空港": {"lat": 42.7332992554, "lon": 143.216995239, "coordinateSource": "OurAirports OBO coordinate"},
}

TO_AIRPORT = [
    ("07:30", "08:08"),
    ("08:15", "08:53"),
    ("11:35", "12:13"),
    ("12:30", "13:08"),
    ("14:35", "15:13"),
    ("17:35", "18:13"),
    ("18:20", "18:58"),
]

FROM_AIRPORT = [
    ("08:40", "09:18"),
    ("09:30", "10:08"),
    ("12:50", "13:28"),
    ("13:35", "14:13"),
    ("15:40", "16:18"),
    ("18:55", "19:33"),
    ("19:30", "20:08"),
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


def assert_source(path: Path) -> None:
    if path.stat().st_size < 10_000:
        raise ValueError(f"Tokachi-Obihiro airport PDF looks too small: {path}")


def make_trip(direction: str, start_name: str, end_name: str, start: str, end: str, index: int) -> dict[str, Any]:
    return {
        "tripId": f"obihiro_airport:{direction}:{index:03d}",
        "direction": direction,
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
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
    for index, (start, end) in enumerate(TO_AIRPORT, start=1):
        trips.append(make_trip("to_airport", "帯広駅バスターミナル", "とかち帯広空港", start, end, index))
    for index, (start, end) in enumerate(FROM_AIRPORT, start=1):
        trips.append(make_trip("from_airport", "とかち帯広空港", "帯広駅バスターミナル", start, end, index))
    route = {
        "sourceKind": "official_obihiro_airport_pdf",
        "operatorName": "十勝バス",
        "airportIata": "OBO",
        "routeCode": "obihiro_airport_obihiro_station",
        "routeName": "帯広駅バスターミナル ⇔ とかち帯広空港",
        "sourceUrl": SOURCE_URL,
        "sourceUrls": [SOURCE_URL],
        "cachePath": str(cache_path.relative_to(ROOT)),
        "cachePaths": [str(cache_path.relative_to(ROOT))],
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "adultFareYen": 1000,
        "routeStopNames": ["帯広駅バスターミナル", "とかち帯広空港"],
        "tripCount": len(trips),
        "stops": [{"stopName": name, **STOPS[name]} for name in ["帯広駅バスターミナル", "とかち帯広空港"]],
        "busStops": [{"name": name, **STOPS[name]} for name in ["帯広駅バスターミナル", "とかち帯広空港"]],
        "trips": trips,
        "sourceNotes": [
            "Endpoint stop-times are from Tokachi Bus official airport PDF for 2026-03-30 through 2026-10-24.",
        ],
    }
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_obihiro_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source PDF retains copyright.",
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
