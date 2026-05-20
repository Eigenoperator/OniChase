#!/usr/bin/env python3
"""Collect Hachijojima Airport official town-bus timetable."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "hachijojima_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_hachijojima_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_hachijojima_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_hachijojima_airport_official_bus_audit.json"

SOURCE_URL = "https://www.8bus.jp/bus_route/bus_time.pdf"
SERVICE_START = "20260329"
SERVICE_END = "20270331"

STOPS = {
    "町役場": {"lat": 33.1122675, "lon": 139.7894651, "coordinateSource": "nominatim:bus_stop:町役場,八丈町"},
    "八丈島空港": {"lat": 33.1166241, "lon": 139.7823867, "coordinateSource": "nominatim:bus_stop:八丈島空港"},
}

TO_AIRPORT = [
    ("07:40", "07:48"),
    ("10:05", "10:24"),
    ("11:22", "11:30"),
    ("13:30", "13:49"),
    ("14:50", "15:09"),
    ("16:00", "16:08"),
]

FROM_AIRPORT = [
    ("08:05", "08:13"),
    ("10:41", "11:00"),
    ("11:47", "11:55"),
    ("14:06", "14:25"),
    ("15:26", "15:45"),
    ("16:25", "16:33"),
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
        raise ValueError(f"Hachijojima town-bus PDF looks too small: {path}")


def make_trip(direction: str, start_name: str, end_name: str, start: str, end: str, index: int) -> dict[str, Any]:
    return {
        "tripId": f"hachijojima_airport:{direction}:{index:03d}",
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
        trips.append(make_trip("to_airport", "町役場", "八丈島空港", start, end, index))
    for index, (start, end) in enumerate(FROM_AIRPORT, start=1):
        trips.append(make_trip("from_airport", "八丈島空港", "町役場", start, end, index))
    route = {
        "sourceKind": "official_hachijojima_airport_pdf",
        "operatorName": "八丈町営バス",
        "airportIata": "HAC",
        "routeCode": "hachijojima_airport_town_hall",
        "routeName": "町役場 ⇔ 八丈島空港",
        "sourceUrl": SOURCE_URL,
        "sourceUrls": [SOURCE_URL],
        "cachePath": str(cache_path.relative_to(ROOT)),
        "cachePaths": [str(cache_path.relative_to(ROOT))],
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "routeStopNames": ["町役場", "八丈島空港"],
        "tripCount": len(trips),
        "stops": [{"stopName": name, **STOPS[name]} for name in ["町役場", "八丈島空港"]],
        "busStops": [{"name": name, **STOPS[name]} for name in ["町役場", "八丈島空港"]],
        "trips": trips,
        "sourceNotes": [
            "Endpoint stop-times are extracted from the official Hachijo town-bus PDF airport/Yaene route table.",
            "The published table is a loop that can pass 八丈島空港 twice; this source emits player-facing endpoint segments between 町役場 and each airport pass.",
            "Fare is not emitted until the current official fare table is parsed without guessing.",
        ],
    }
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_hachijojima_airport_bus",
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
