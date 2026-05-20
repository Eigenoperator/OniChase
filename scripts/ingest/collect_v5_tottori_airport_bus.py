#!/usr/bin/env python3
"""Collect Tottori Airport official airport-connection bus timetable."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "tottori_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_tottori_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_tottori_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_tottori_airport_official_bus_audit.json"

SOURCE_URL = "https://www.ttj-ap-bld.co.jp/files/access/bus_diagram01.pdf"
SERVICE_START = "20260329"
SERVICE_END = "20260531"

STOPS = {
    "鳥取駅": {"lat": 35.49422, "lon": 134.226085, "coordinateSource": "v4 station group centroid:鳥取"},
    "鳥取空港": {"lat": 35.530058, "lon": 134.165023, "coordinateSource": "OurAirports TTJ coordinate"},
}

TO_AIRPORT = [
    ("06:05", "06:25"),
    ("07:45", "08:05"),
    ("09:50", "10:10"),
    ("14:00", "14:20"),
    ("17:00", "17:20"),
]

FROM_AIRPORT = [
    ("08:25", "08:45"),
    ("10:35", "10:55"),
    ("14:40", "15:00"),
    ("17:50", "18:10"),
    ("20:45", "21:05"),
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
        raise ValueError(f"Tottori airport PDF looks too small: {path}")


def make_trip(direction: str, start_name: str, end_name: str, start: str, end: str, index: int) -> dict[str, Any]:
    return {
        "tripId": f"tottori_airport:{direction}:{index:03d}",
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
        trips.append(make_trip("to_airport", "鳥取駅", "鳥取空港", start, end, index))
    for index, (start, end) in enumerate(FROM_AIRPORT, start=1):
        trips.append(make_trip("from_airport", "鳥取空港", "鳥取駅", start, end, index))

    route = {
        "sourceKind": "official_tottori_airport_pdf",
        "operatorName": "日ノ丸自動車",
        "airportIata": "TTJ",
        "routeCode": "tottori_airport_tottori_station",
        "routeName": "鳥取駅 ⇔ 鳥取空港",
        "sourceUrl": SOURCE_URL,
        "sourceUrls": [SOURCE_URL],
        "cachePath": str(cache_path.relative_to(ROOT)),
        "cachePaths": [str(cache_path.relative_to(ROOT))],
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "adultFareYen": 480,
        "routeStopNames": ["鳥取駅", "鳥取空港"],
        "tripCount": len(trips),
        "stops": [{"stopName": name, **STOPS[name]} for name in ["鳥取駅", "鳥取空港"]],
        "busStops": [{"name": name, **STOPS[name]} for name in ["鳥取駅", "鳥取空港"]],
        "trips": trips,
        "sourceNotes": [
            "Official PDF states Tottori Station to airport buses are boarding-only before the airport and airport to station buses are alighting-only after the airport, so endpoint-playable stop-times are intentional.",
        ],
    }
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_tottori_airport_bus",
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
