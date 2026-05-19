#!/usr/bin/env python3
"""Collect Asahikawa Airport official access-bus timetable."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "asahikawa_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_asahikawa_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_asahikawa_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_asahikawa_airport_official_bus_audit.json"

ACCESS_URL = "https://www.asahikawa-denkikidou.jp/asahikawa-airport/"
TIMETABLE_URL = "https://www.asahikawa-denkikidou.jp/manage/wp-content/uploads/2026/03/airport_timetable.R8.5.01-R8.5.31.pdf"
SERVICE_START = "20260501"
SERVICE_END = "20260531"

STOPS = {
    "旭川駅": {"lat": 43.762865, "lon": 142.35807, "coordinateSource": "OniChase N02 rail station centroid: 旭川"},
    "旭川空港": {"lat": 43.670799, "lon": 142.447006, "coordinateSource": "OurAirports AKJ coordinate"},
}

# Official 2026-05-01 through 2026-05-31 rows.  The public page includes many
# city stops; the gameplay source keeps the safe endpoint pair because airport
# direction rows explicitly disallow mid-route alighting and city direction rows
# disallow mid-route boarding.
TO_AIRPORT = [
    ("06:55", "07:50", "ADO82"),
    ("07:35", "08:30", "JAL552"),
    ("11:25", "12:20", "JAL554"),
    ("11:45", "12:40", "ADO84"),
    ("12:55", "13:50", "GK800"),
    ("14:00", "14:55", "JAL556"),
    ("16:25", "17:20", "GK802"),
    ("17:20", "18:15", "ADO88"),
    ("17:40", "18:35", "JAL558"),
]

FROM_AIRPORT = [
    ("09:05", "09:44", "ADO81"),
    ("09:40", "10:19", "JAL551"),
    ("13:15", "13:54", "JAL553"),
    ("14:20", "14:59", "ADO83"),
    ("14:55", "15:34", "GK801"),
    ("16:05", "16:44", "JAL555"),
    ("18:25", "19:04", "GK803"),
    ("19:20", "19:59", "ADO87"),
    ("19:45", "20:24", "JAL557"),
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


def assert_source_contains(access_cache: Path, timetable_cache: Path) -> None:
    html = access_cache.read_text(encoding="utf-8", errors="ignore")
    markers = [
        "2026年5月1日",
        "2026年5月31日",
        "旭川駅(9)",
        "旭川空港着",
        "旭川空港発",
        "750円",
        "airport_timetable.R8.5.01-R8.5.31.pdf",
    ]
    missing = [marker for marker in markers if marker not in html]
    if missing:
        raise ValueError(f"Asahikawa airport page is missing expected markers: {missing}")
    if timetable_cache.stat().st_size < 50_000:
        raise ValueError(f"Asahikawa PDF cache is unexpectedly small: {timetable_cache}")


def build_routes(access_cache: Path, timetable_cache: Path) -> list[dict[str, Any]]:
    trips = []
    for index, (start, end, flight) in enumerate(TO_AIRPORT, start=1):
        trips.append(
            {
                "tripId": f"asahikawa_airport_asahikawa_station:to_airport:{index:03d}",
                "direction": "to_airport",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": "daily",
                "notes": f"Connects outbound flight {flight}",
                "stopTimes": [{"stopName": "旭川駅", "time": start}, {"stopName": "旭川空港", "time": end}],
            }
        )
    for index, (start, end, flight) in enumerate(FROM_AIRPORT, start=1):
        trips.append(
            {
                "tripId": f"asahikawa_airport_asahikawa_station:from_airport:{index:03d}",
                "direction": "from_airport",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": "daily",
                "notes": f"Connects inbound flight {flight}",
                "stopTimes": [{"stopName": "旭川空港", "time": start}, {"stopName": "旭川駅", "time": end}],
            }
        )
    return [
        {
            "sourceKind": "official_asahikawa_airport_html_pdf",
            "operatorName": "旭川電気軌道",
            "airportIata": "AKJ",
            "routeCode": "asahikawa_airport_asahikawa_station",
            "routeName": "旭川空港線 旭川駅 ⇔ 旭川空港",
            "sourceUrl": ACCESS_URL,
            "sourceUrls": [ACCESS_URL, TIMETABLE_URL],
            "cachePath": str(access_cache.relative_to(ROOT)),
            "cachePaths": [str(access_cache.relative_to(ROOT)), str(timetable_cache.relative_to(ROOT))],
            "serviceStart": SERVICE_START,
            "serviceEnd": SERVICE_END,
            "serviceDays": "daily",
            "adultFareYen": 750,
            "routeStopNames": ["旭川駅", "旭川空港"],
            "tripCount": len(trips),
            "stops": [{"stopName": name, **STOPS[name]} for name in ["旭川駅", "旭川空港"]],
            "busStops": [{"name": name, **STOPS[name]} for name in ["旭川駅", "旭川空港"]],
            "trips": trips,
            "sourceNotes": [
                "Official Asahikawa Denkikidou page and PDF cover 2026-05-01 through 2026-05-31.",
                "Endpoint-playable normalization uses 旭川駅 and 旭川空港. The official airport-bound note says passengers cannot alight before the airport; the city-bound note says passengers cannot board after the airport.",
            ],
        }
    ]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    access_cache = fetch(ACCESS_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    timetable_cache = fetch(TIMETABLE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    assert_source_contains(access_cache, timetable_cache)
    routes = build_routes(access_cache, timetable_cache)
    all_trips = [trip for route in routes for trip in route["trips"]]
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_asahikawa_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source pages retain copyright.",
        "routes": routes,
    }
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "routeCount": len(routes),
        "tripCount": len(all_trips),
        "stopCount": 2,
        "coordinateStopCount": 2,
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
