#!/usr/bin/env python3
"""Collect JR Bus Tohoku Aomori Airport line endpoint timetable."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "aomori_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_aomori_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_aomori_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_aomori_airport_official_bus_audit.json"
SOURCE_URL = "https://www.jrbustohoku.co.jp/uploads/files/20260301AomoriAirport.pdf"
SERVICE_START = "20260301"
SERVICE_END = "20270331"

STOP_COORDS = {
    "青森駅": {"lat": 40.83032, "lon": 140.73465, "coordinateSource": "OniChase rail station group centroid: 青森"},
    "青森空港": {"lat": 40.733777, "lon": 140.689477, "coordinateSource": "OpenFlights / V5 flight airport map"},
}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.pdf"


def fetch_pdf(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> Path:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def pdf_text(path: Path) -> str:
    if shutil.which("pdftotext") is None:
        raise RuntimeError("pdftotext is required to parse Aomori Airport PDF")
    return subprocess.check_output(["pdftotext", "-layout", str(path), "-"], text=True, encoding="utf-8", errors="ignore")


def parse_section(text: str, start_marker: str, end_marker: str | None) -> list[list[str]]:
    section = text.split(start_marker, 1)[-1]
    if end_marker and end_marker in section:
        section = section.split(end_marker, 1)[0]
    rows: list[list[str]] = []
    for line in section.splitlines():
        times = re.findall(r"\d{1,2}:\d{2}", line)
        if len(times) >= 2:
            rows.append(times)
    return rows


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    pdf_path = fetch_pdf(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    text = pdf_text(pdf_path)
    to_airport_rows = parse_section(text, "青森空港行き", "青森駅前行き")
    from_airport_rows = parse_section(text, "青森駅前行き", "運賃【円】")
    trips = []
    for index, row in enumerate(to_airport_rows, start=1):
        service_days = ["tuesday", "thursday", "saturday"] if row[0] == "13:35" else "daily"
        trips.append(
            {
                "tripId": f"aomori_airport_line:to_airport:{index:03d}",
                "direction": "to_airport",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": service_days,
                "stopTimes": [{"stopName": "青森駅", "time": row[0]}, {"stopName": "青森空港", "time": row[-1]}],
            }
        )
    for index, row in enumerate(from_airport_rows, start=1):
        service_days = ["tuesday", "thursday", "saturday"] if row[0] == "15:30" else "daily"
        trips.append(
            {
                "tripId": f"aomori_airport_line:from_airport:{index:03d}",
                "direction": "from_airport",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": service_days,
                "stopTimes": [{"stopName": "青森空港", "time": row[0]}, {"stopName": "青森駅", "time": row[-1]}],
            }
        )
    route = {
        "sourceKind": "official_jrbus_tohoku_aomori_airport_pdf",
        "operatorName": "JRバス東北",
        "airportIata": "AOJ",
        "routeCode": "aomori_airport_line",
        "routeName": "青森空港線 青森駅 ⇔ 青森空港",
        "sourceUrl": SOURCE_URL,
        "cachePath": str(pdf_path.relative_to(ROOT)),
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "mixed_by_trip",
        "adultFareYen": 690,
        "routeStopNames": ["青森駅", "青森空港"],
        "busStops": [{"name": name, **coords} for name, coords in STOP_COORDS.items()],
        "trips": trips,
        "tripCount": len(trips),
        "notes": ["Endpoint playable only. The official PDF lists intermediate stops, but airport-bound trips are boarding-only and city-bound trips are alighting-only, so endpoint gameplay is the safest first promotion."],
    }
    source = {
        "schemaVersion": "v5_official_bus_source.aomori_airport.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official JR Bus Tohoku PDF timetable effective from 2026-03-01. Endpoint playable promotion uses official first/last stop times.",
        "routes": [route],
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.aomori_airport.v1",
        "generatedAt": generated_at,
        "routeCount": 1,
        "tripCount": len(trips),
        "stopCount": 2,
        "coordinateStopCount": 2,
        "missingCoordinateStops": [],
        "directionCounts": dict(Counter(trip["direction"] for trip in trips)),
        "routeTripCounts": {route["routeCode"]: len(trips)},
    }
    return source, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--refresh-cache", action="store_true")
    args = parser.parse_args()
    source, audit = collect(args)
    write_json(args.output, source)
    write_json(args.docs_output, source)
    write_json(args.audit_output, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
