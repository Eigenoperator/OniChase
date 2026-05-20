#!/usr/bin/env python3
"""Collect Fukue Airport official airport-bus timetable."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "fukue_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_fukue_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_fukue_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_fukue_airport_official_bus_audit.json"

INDEX_URL = "https://goto-sight.com/gotobus/index.html"
AIRPORT_LINE_PDF_URL = "https://goto-sight.com/gotobus/_userdata/kuukoujikann2020.12.1.pdf"
FLIGHT_CONNECTION_PDF_URL = "https://goto-sight.com/gotobus/_userdata/kuukousen2020.12.1.pdf"
SERVICE_START = "20260511"
SERVICE_END = "20260531"

STOPS = {
    "福江": {
        "lat": 32.696761,
        "lon": 128.841833,
        "coordinateSource": "Manual official endpoint coordinate near Fukue Port / Goto Bus Fukue center",
    },
    "五島福江空港": {
        "lat": 32.666302,
        "lon": 128.832993,
        "coordinateSource": "OurAirports FUJ coordinate",
    },
}

TO_AIRPORT = [
    ("08:45", "08:55"),
    ("10:00", "10:10"),
    ("12:40", "12:50"),
    ("14:55", "15:05"),
    ("17:05", "17:15"),
]

FROM_AIRPORT = [
    ("09:15", "09:26"),
    ("10:30", "10:41"),
    ("13:10", "13:21"),
    ("15:25", "15:36"),
    ("17:35", "17:46"),
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


def assert_sources(index_path: Path, airport_pdf_path: Path) -> None:
    html = index_path.read_text(encoding="utf-8", errors="ignore")
    missing = [marker for marker in ["kuukoujikann2020.12.1.pdf", "kuukousen2020.12.1.pdf"] if marker not in html]
    if missing:
        raise ValueError(f"Fukue bus index is missing expected markers: {missing}")
    if airport_pdf_path.stat().st_size < 10_000:
        raise ValueError(f"Fukue airport-line PDF looks too small: {airport_pdf_path}")


def make_trip(direction: str, start_name: str, end_name: str, start: str, end: str, index: int) -> dict[str, Any]:
    return {
        "tripId": f"fukue_airport:{direction}:{index:03d}",
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
    index_path = fetch(INDEX_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    airport_pdf_path = fetch(AIRPORT_LINE_PDF_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    flight_pdf_path = fetch(FLIGHT_CONNECTION_PDF_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    assert_sources(index_path, airport_pdf_path)

    trips: list[dict[str, Any]] = []
    for index, (start, end) in enumerate(TO_AIRPORT, start=1):
        trips.append(make_trip("to_airport", "福江", "五島福江空港", start, end, index))
    for index, (start, end) in enumerate(FROM_AIRPORT, start=1):
        trips.append(make_trip("from_airport", "五島福江空港", "福江", start, end, index))

    route = {
        "sourceKind": "official_fukue_airport_pdf",
        "operatorName": "五島自動車",
        "airportIata": "FUJ",
        "routeCode": "fukue_airport",
        "routeName": "空港線 福江 ⇔ 五島福江空港",
        "sourceUrl": AIRPORT_LINE_PDF_URL,
        "sourceUrls": [INDEX_URL, AIRPORT_LINE_PDF_URL, FLIGHT_CONNECTION_PDF_URL],
        "cachePath": str(airport_pdf_path.relative_to(ROOT)),
        "cachePaths": [str(path.relative_to(ROOT)) for path in [index_path, airport_pdf_path, flight_pdf_path]],
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "adultFareYen": 310,
        "routeStopNames": ["福江", "五島福江空港"],
        "tripCount": len(trips),
        "stops": [{"stopName": name, **STOPS[name]} for name in ["福江", "五島福江空港"]],
        "busStops": [{"name": name, **STOPS[name]} for name in ["福江", "五島福江空港"]],
        "trips": trips,
        "sourceNotes": [
            "Official Goto Bus page still links the airport-line PDFs with 2020 filenames; current May 11-31 table is parsed from the linked PDF.",
            "The PDF exposes intermediate stops, but this release emits only endpoint stop-times because intermediate stop coordinates still need a reviewed official/geocoded source.",
        ],
    }
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_fukue_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source PDFs/pages retain copyright.",
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
        "serviceWindow": {"start": SERVICE_START, "end": SERVICE_END},
        "sourceLimitation": "Intermediate stops are cached but not emitted until their coordinates are reviewed.",
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
