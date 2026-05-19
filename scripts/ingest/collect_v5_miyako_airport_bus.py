#!/usr/bin/env python3
"""Collect Miyako Airport airport-liner endpoint timetable."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "miyako_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_miyako_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_miyako_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_miyako_airport_official_bus_audit.json"
SOURCE_URL = "https://www.miyakojima-style.jp/bus-routes/route-airport/"
SERVICE_START = "20260329"
SERVICE_END = "20261024"

STOP_COORDS = {
    "宮古空港": {"lat": 24.782801, "lon": 125.294998, "coordinateSource": "OpenFlights / V5 flight airport map"},
    "みやこ下地島空港": {"lat": 24.8267, "lon": 125.144997, "coordinateSource": "OpenFlights / V5 flight airport map"},
}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"


def fetch_html(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[str, Path]:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8"), path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", "ignore")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text, path


def line_times(text: str, stop_name: str) -> list[str]:
    match = re.search(rf"<th[^>]*>{re.escape(stop_name)}</th>(.*?)</tr>", text, flags=re.S)
    if not match:
        return []
    return re.findall(r"\d{1,2}:\d{2}", match.group(1))


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    text, cache_path = fetch_html(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    up_start = line_times(text, "宮古空港")
    up_end = line_times(text, "みやこ下地島空港")
    down_start = line_times(text.split("### 下り", 1)[-1], "みやこ下地島空港")
    down_end = line_times(text.split("### 下り", 1)[-1], "宮古空港")
    trips = []
    for index, (departure, arrival) in enumerate(zip(up_start, up_end), start=1):
        trips.append(
            {
                "tripId": f"miyako_shimoji_airport_liner:to_shi:{index:03d}",
                "direction": "to_shimoji",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": "daily",
                "stopTimes": [{"stopName": "宮古空港", "time": departure}, {"stopName": "みやこ下地島空港", "time": arrival}],
            }
        )
    for index, (departure, arrival) in enumerate(zip(down_start, down_end), start=1):
        trips.append(
            {
                "tripId": f"miyako_shimoji_airport_liner:to_mmy:{index:03d}",
                "direction": "to_miyako",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": "daily",
                "stopTimes": [{"stopName": "みやこ下地島空港", "time": departure}, {"stopName": "宮古空港", "time": arrival}],
            }
        )
    route = {
        "sourceKind": "miyakojima_city_style_airport_liner_timetable",
        "operatorName": "中央交通",
        "airportIata": "MMY",
        "routeCode": "miyako_shimoji_airport_liner",
        "routeName": "みやこ下地島エアポートライナー 宮古空港 ⇔ みやこ下地島空港",
        "sourceUrl": SOURCE_URL,
        "cachePath": str(cache_path.relative_to(ROOT)),
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "routeStopNames": ["宮古空港", "みやこ下地島空港"],
        "busStops": [{"name": name, **coords} for name, coords in STOP_COORDS.items()],
        "trips": trips,
        "tripCount": len(trips),
        "notes": ["Endpoint playable only; intermediate stops are visible in source but coordinates are not yet normalized."],
    }
    source = {
        "schemaVersion": "v5_official_bus_source.miyako_airport.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Miyakojima City tourism route page provides the timetable; OpenFlights/V5 airport map provides airport coordinates.",
        "routes": [route],
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.miyako_airport.v1",
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
