#!/usr/bin/env python3
"""Collect Iwakuni Kintaikyo Airport official access-bus timetables."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "iwakuni_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_iwakuni_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_iwakuni_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_iwakuni_airport_official_bus_audit.json"

ACCESS_URL = "https://www.iwakuni-airport.jp/access/access-bus/"
TIMETABLE_URL = "https://www.iwakuni-airport.jp/cms/wp-content/themes/iwakuni-airport/images/download/timetable_20260329.pdf"
SERVICE_START = "20260329"
SERVICE_END = "20261024"

STOPS = {
    "岩国駅東口": {"lat": 34.17178, "lon": 132.22561, "coordinateSource": "OniChase N02 rail station centroid: 岩国"},
    "シンフォニア": {"lat": 34.15887, "lon": 132.22083, "coordinateSource": "Iwakuni station-area airport-bus stop, geocoded from official map"},
    "岩国錦帯橋空港": {"lat": 34.143902, "lon": 132.23575, "coordinateSource": "OpenFlights / V5 flight airport map"},
    "錦帯橋": {"lat": 34.16768, "lon": 132.1782, "coordinateSource": "Official airport-bus PDF stop; approximate bridge bus-stop centroid"},
    "広島バスセンター": {"lat": 34.396039, "lon": 132.457059, "coordinateSource": "Existing OniChase official Hiroshima airport-bus stop"},
}

ROUTES = [
    {
        "routeCode": "iwakuni_airport_iwakuni_station",
        "routeName": "岩国錦帯橋空港アクセスバス 岩国駅東口 ⇔ 岩国錦帯橋空港",
        "adultFareYen": 200,
        "stops": ["岩国駅東口", "シンフォニア", "岩国錦帯橋空港"],
        "trips": [
            ("to_airport", ["06:48", "06:49", "06:55"], "ANA632"),
            ("to_airport", ["08:03", "08:04", "08:10"], "ANA634"),
            ("to_airport", ["10:48", "10:49", "10:55"], "ANA1267"),
            ("to_airport", ["12:48", "12:49", "12:55"], "ANA636"),
            ("to_airport", ["16:58", "16:59", "17:05"], "ANA638"),
            ("to_airport", ["18:43", "18:44", "18:50"], "ANA640"),
            ("from_airport", ["08:30", "08:32", "08:37"], "ANA631"),
            ("from_airport", ["11:15", "11:17", "11:22"], "ANA633"),
            ("from_airport", ["13:10", "13:12", "13:17"], "ANA635"),
            ("from_airport", ["17:15", "17:17", "17:22"], "ANA1268"),
            ("from_airport", ["18:50", "18:52", "18:57"], "ANA637"),
            ("from_airport", ["21:55", "21:57", "22:02"], "ANA639"),
        ],
    },
    {
        "routeCode": "iwakuni_airport_hiroshima_bus_center",
        "routeName": "岩国錦帯橋空港アクセスバス 広島バスセンター ⇔ 岩国錦帯橋空港",
        "adultFareYen": 1000,
        "stops": ["広島バスセンター", "錦帯橋", "岩国錦帯橋空港"],
        "trips": [
            ("to_airport", ["10:35", "11:28", "11:55"], "ANA636"),
            ("to_airport", ["15:35", "16:28", "16:55"], "ANA638"),
            ("to_airport", ["16:55", "17:48", "18:15"], "ANA640"),
            ("from_airport", ["08:50", "09:15", "10:15"], "ANA631"),
        ],
    },
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


def parse_access_fares(access_html: str) -> dict[str, int]:
    fares: dict[str, int] = {}
    if re.search(r"岩国駅.*?大人200円", access_html, re.S):
        fares["iwakuni_airport_iwakuni_station"] = 200
    # The 2026-03-29 PDF is the current source of truth for Hiroshima fare.
    if "広島バスセンター" in access_html:
        fares["iwakuni_airport_hiroshima_bus_center"] = 1000
    return fares


def trip_stop_times(route: dict[str, Any], direction: str, times: list[str]) -> list[dict[str, str]]:
    names = route["stops"] if direction == "to_airport" else list(reversed(route["stops"]))
    return [{"stopName": name, "time": time} for name, time in zip(names, times, strict=True)]


def build_routes(access_cache: Path, timetable_cache: Path) -> list[dict[str, Any]]:
    html = access_cache.read_text(encoding="utf-8", errors="ignore")
    checked_fares = parse_access_fares(html)
    payload_routes = []
    for route in ROUTES:
        trips = []
        for index, (direction, times, flight_note) in enumerate(route["trips"], start=1):
            trips.append(
                {
                    "tripId": f"{route['routeCode']}:{direction}:{index:03d}",
                    "direction": direction,
                    "serviceStart": SERVICE_START,
                    "serviceEnd": SERVICE_END,
                    "serviceDays": "daily",
                    "notes": f"Official PDF base timetable, connects {flight_note}",
                    "stopTimes": trip_stop_times(route, direction, times),
                }
            )
        payload_routes.append(
            {
                "sourceKind": "official_iwakuni_airport_pdf",
                "operatorName": "いわくにバス",
                "airportIata": "IWK",
                "routeCode": route["routeCode"],
                "routeName": route["routeName"],
                "sourceUrl": TIMETABLE_URL,
                "sourceUrls": [ACCESS_URL, TIMETABLE_URL],
                "cachePath": str(timetable_cache.relative_to(ROOT)),
                "cachePaths": [str(access_cache.relative_to(ROOT)), str(timetable_cache.relative_to(ROOT))],
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": "daily",
                "adultFareYen": checked_fares.get(route["routeCode"], route["adultFareYen"]),
                "routeStopNames": route["stops"],
                "tripCount": len(trips),
                "stops": [{"stopName": name, **STOPS[name]} for name in route["stops"]],
                "busStops": [{"name": name, **STOPS[name]} for name in route["stops"]],
                "trips": trips,
                "sourceNotes": [
                    "Timetable PDF published by Iwakuni Kintaikyo Airport for 2026-03-29 through 2026-10-24.",
                    "The PDF is image-only; values are transcribed from the official timetable image and checked against the airport access HTML for route/fare context.",
                    "Seasonal parenthesized flight-adjusted times are not promoted into May gameplay service; the base timetable is current for the v5 planner date.",
                ],
            }
        )
    return payload_routes


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    access_cache = fetch(ACCESS_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    timetable_cache = fetch(TIMETABLE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    routes = build_routes(access_cache, timetable_cache)
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_iwakuni_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source pages retain copyright.",
        "routes": routes,
    }
    all_trips = [trip for route in routes for trip in route["trips"]]
    stop_names = sorted({stop["stopName"] for route in routes for stop in route["stops"]})
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "routeCount": len(routes),
        "tripCount": len(all_trips),
        "stopCount": len(stop_names),
        "coordinateStopCount": len([name for name in stop_names if STOPS[name].get("lat") and STOPS[name].get("lon")]),
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
