#!/usr/bin/env python3
"""Collect Saga Airport official access-bus timetable."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import ssl
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "saga_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_saga_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_saga_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_saga_airport_official_bus_audit.json"
SOURCE_URL = "https://www.bus.saga.saga.jp/rosenkukoR8.3.29.html"
SERVICE_START = "20260329"
SERVICE_END = "20260531"

DAYS = {
    "月": "monday",
    "火": "tuesday",
    "水": "wednesday",
    "木": "thursday",
    "金": "friday",
    "土": "saturday",
    "日": "sunday",
}
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]

STOPS = {
    "佐賀駅バスセンター": {"lat": 33.264125, "lon": 130.29737, "coordinateSource": "OniChase rail station group centroid: 佐賀"},
    "佐賀空港": {"lat": 33.1497, "lon": 130.302002, "coordinateSource": "OpenFlights / V5 flight airport map"},
}


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_row = False
        self.in_cell = False
        self.cell: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.in_row = True
            self.row = []
        elif tag in {"td", "th"} and self.in_row:
            self.in_cell = True
            self.cell = []
        elif tag == "br" and self.in_cell:
            self.cell.append(" ")

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.in_cell:
            self.row.append(clean_text("".join(self.cell)))
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.row:
                self.rows.append(self.row)
            self.in_row = False


def clean_text(value: str) -> str:
    text = html.unescape(value).replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_time(value: str) -> str | None:
    match = re.search(r"\d{1,2}:\d{2}", str(value or ""))
    return match.group(0) if match else None


def service_days_for(label: str) -> str | list[str]:
    if "平日のみ" in label:
        return WEEKDAYS
    if "月・水・金・日" in label:
        return ["monday", "wednesday", "friday", "sunday"]
    if "火・木・日" in label:
        return ["tuesday", "thursday", "sunday"]
    return "daily"


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"


def fetch_html(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[str, Path]:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8"), path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        data = response.read().decode("utf-8", "ignore")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    return data, path


def parse_rows(html_text: str) -> list[list[str]]:
    parser = TableParser()
    parser.feed(html_text)
    return parser.rows


def strip_marker(value: str) -> str:
    return str(value or "").replace("●", "").replace("〇", "").replace("○", "").strip()


def build_trips(rows: list[list[str]]) -> list[dict[str, Any]]:
    trips: list[dict[str, Any]] = []
    domestic_out_header = rows[1]
    domestic_in_header = rows[10]
    intl_out_header = rows[18]
    intl_in_header = rows[22]

    out_origin_idx = next(i for i, name in enumerate(domestic_out_header) if "佐賀駅" in name)
    out_airport_idx = next(i for i, name in enumerate(domestic_out_header) if "佐賀空港" in name)
    for index, row in enumerate(rows[2:9], start=1):
        origin = parse_time(row[out_origin_idx])
        airport = parse_time(row[out_airport_idx])
        if not origin or not airport:
            continue
        trips.append(
            {
                "tripId": f"saga_airport_domestic:to_airport:{index:03d}",
                "direction": "to_airport",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": service_days_for(row[0]),
                "stopTimes": [{"stopName": "佐賀駅バスセンター", "time": strip_marker(origin)}, {"stopName": "佐賀空港", "time": strip_marker(airport)}],
            }
        )

    in_airport_idx = next(i for i, name in enumerate(domestic_in_header) if "佐賀空港" in name)
    in_station_idx = next(i for i, name in enumerate(domestic_in_header) if "佐賀駅" in name)
    for index, row in enumerate(rows[11:17], start=1):
        airport = parse_time(row[in_airport_idx])
        station = parse_time(row[in_station_idx])
        if not airport or not station:
            continue
        trips.append(
            {
                "tripId": f"saga_airport_domestic:from_airport:{index:03d}",
                "direction": "from_airport",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": service_days_for(row[0]),
                "stopTimes": [{"stopName": "佐賀空港", "time": strip_marker(airport)}, {"stopName": "佐賀駅バスセンター", "time": strip_marker(station)}],
            }
        )

    intl_origin_idx = next(i for i, name in enumerate(intl_out_header) if "佐賀駅" in name)
    intl_service_idx = next(i for i, name in enumerate(intl_out_header) if "運行日" in name)
    intl_airport_idx = next(i for i, name in enumerate(intl_out_header) if "佐賀空港" in name)
    for index, row in enumerate(rows[19:21], start=1):
        trips.append(
            {
                "tripId": f"saga_airport_international:to_airport:{index:03d}",
                "direction": "to_airport",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": service_days_for(row[intl_service_idx]),
                "stopTimes": [{"stopName": "佐賀駅バスセンター", "time": row[intl_origin_idx]}, {"stopName": "佐賀空港", "time": row[intl_airport_idx]}],
            }
        )

    intl_in_airport_idx = next(i for i, name in enumerate(intl_in_header) if "佐賀空港" in name)
    intl_in_service_idx = next(i for i, name in enumerate(intl_in_header) if "運行日" in name)
    intl_in_station_idx = next(i for i, name in enumerate(intl_in_header) if "佐賀駅" in name)
    for index, row in enumerate(rows[23:25], start=1):
        trips.append(
            {
                "tripId": f"saga_airport_international:from_airport:{index:03d}",
                "direction": "from_airport",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": service_days_for(row[intl_in_service_idx]),
                "stopTimes": [{"stopName": "佐賀空港", "time": row[intl_in_airport_idx]}, {"stopName": "佐賀駅バスセンター", "time": row[intl_in_station_idx]}],
            }
        )
    return trips


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    html_text, cache_path = fetch_html(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    rows = parse_rows(html_text)
    trips = build_trips(rows)
    route = {
        "sourceKind": "official_saga_airport_html",
        "operatorName": "佐賀市営バス",
        "airportIata": "HSG",
        "routeCode": "saga_airport_saga_station",
        "routeName": "佐賀空港接続バス 佐賀駅バスセンター ⇔ 佐賀空港",
        "sourceUrl": SOURCE_URL,
        "cachePath": str(cache_path.relative_to(ROOT)),
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "mixed_by_trip",
        "adultFareYen": 600,
        "routeStopNames": ["佐賀駅バスセンター", "佐賀空港"],
        "busStops": [{"name": name, **coords} for name, coords in STOPS.items()],
        "trips": trips,
        "tripCount": len(trips),
        "notes": ["Endpoint playable promotion from official Saga City Bus airport connection timetable. Intermediate published stops remain source evidence but are not promoted until coordinates are normalized."],
    }
    source = {
        "schemaVersion": "v5_official_bus_source.saga_airport.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Saga City Bus airport-connection timetable, effective 2026-03-29 through 2026-05-31.",
        "routes": [route],
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.saga_airport.v1",
        "generatedAt": generated_at,
        "routeCount": 1,
        "tripCount": len(trips),
        "stopCount": 2,
        "coordinateStopCount": 2,
        "missingCoordinateStops": [],
        "directionCounts": dict(Counter(trip["direction"] for trip in trips)),
        "serviceDayCounts": dict(Counter(str(trip["serviceDays"]) for trip in trips)),
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
