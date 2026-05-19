#!/usr/bin/env python3
"""Collect Yamaguchi Ube Airport official access-bus timetables."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "yamaguchi_ube_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_yamaguchi_ube_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_yamaguchi_ube_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_yamaguchi_ube_airport_official_bus_audit.json"
SERVICE_START = "20260401"
SERVICE_END = "20260531"

SOURCES = [
    {
        "routeCode": "yamaguchi_ube_airport_shin_yamaguchi",
        "routeName": "山口宇部空港アクセスバス 新山口駅線",
        "url": "https://www.yamaguchiube-airport.jp/mapaccess/bus/bus_shin_yamaguchi/",
        "cityStopName": "新山口駅",
        "cityCoord": {"lat": 34.0938085, "lon": 131.3964633, "coordinateSource": "OniChase rail station group centroid: 新山口"},
        "adultFareYen": 910,
    },
    {
        "routeCode": "yamaguchi_ube_airport_ube_shinkawa",
        "routeName": "山口宇部空港アクセスバス 宇部新川駅線",
        "url": "https://www.yamaguchiube-airport.jp/mapaccess/bus/bus_ubeshinkawa/",
        "cityStopName": "宇部新川駅",
        "cityCoord": {"lat": 33.958605, "lon": 131.24233, "coordinateSource": "OniChase rail station group centroid: 宇部新川"},
        "adultFareYen": 310,
    },
]

AIRPORT_STOP = {
    "name": "山口宇部空港",
    "lat": 33.93,
    "lon": 131.279007,
    "coordinateSource": "OpenFlights / V5 flight airport map",
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
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_time(value: str) -> str | None:
    match = re.search(r"\d{1,2}:\d{2}", value)
    return match.group(0) if match else None


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"


def fetch_html(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[str, Path]:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8"), path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read().decode("utf-8", "ignore")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    return data, path


def current_section(html_text: str) -> str:
    if 'id="id_timetable_1"' not in html_text:
        raise ValueError("Could not find current timetable section id_timetable_1")
    section = html_text.split('id="id_timetable_1"', 1)[1]
    if 'id="id_timetable_2"' in section:
        section = section.split('id="id_timetable_2"', 1)[0]
    return section


def parse_current_rows(html_text: str) -> list[list[str]]:
    parser = TableParser()
    parser.feed(current_section(html_text))
    return parser.rows


def split_direction_tables(rows: list[list[str]], city_stop_name: str) -> tuple[list[list[str]], list[list[str]]]:
    first_header = next(index for index, row in enumerate(rows) if "空港発" in row and city_stop_name in row)
    second_header = next(index for index, row in enumerate(rows) if row and row[0] == city_stop_name and "空港着" in row)
    return rows[first_header : second_header], rows[second_header:]


def build_trips(source: dict[str, Any], rows: list[list[str]]) -> list[dict[str, Any]]:
    city_stop_name = source["cityStopName"]
    to_city_rows, to_airport_rows = split_direction_tables(rows, city_stop_name)
    trips: list[dict[str, Any]] = []

    to_city_header = to_city_rows[0]
    airport_depart_index = to_city_header.index("空港発")
    city_arrive_index = to_city_header.index(city_stop_name)
    for index, row in enumerate(to_city_rows[1:], start=1):
        if len(row) <= max(airport_depart_index, city_arrive_index):
            continue
        airport_time = parse_time(row[airport_depart_index])
        city_time = parse_time(row[city_arrive_index])
        if not airport_time or not city_time:
            continue
        trips.append(
            {
                "tripId": f"{source['routeCode']}:from_airport:{index:03d}",
                "direction": "from_airport",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": "daily",
                "stopTimes": [{"stopName": "山口宇部空港", "time": airport_time}, {"stopName": city_stop_name, "time": city_time}],
            }
        )

    to_airport_header = to_airport_rows[0]
    city_depart_index = to_airport_header.index(city_stop_name)
    airport_arrive_index = to_airport_header.index("空港着")
    for index, row in enumerate(to_airport_rows[1:], start=1):
        if len(row) <= max(city_depart_index, airport_arrive_index):
            continue
        city_time = parse_time(row[city_depart_index])
        airport_time = parse_time(row[airport_arrive_index])
        if not city_time or not airport_time:
            continue
        trips.append(
            {
                "tripId": f"{source['routeCode']}:to_airport:{index:03d}",
                "direction": "to_airport",
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": "daily",
                "stopTimes": [{"stopName": city_stop_name, "time": city_time}, {"stopName": "山口宇部空港", "time": airport_time}],
            }
        )
    return trips


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    routes = []
    cache_paths = []
    for source in SOURCES:
        html_text, cache_path = fetch_html(source["url"], args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        cache_paths.append(str(cache_path.relative_to(ROOT)))
        rows = parse_current_rows(html_text)
        trips = build_trips(source, rows)
        city_stop = {"name": source["cityStopName"], **source["cityCoord"]}
        routes.append(
            {
                "sourceKind": "official_yamaguchi_ube_airport_html",
                "operatorName": "山口宇部空港アクセスバス",
                "airportIata": "UBJ",
                "routeCode": source["routeCode"],
                "routeName": source["routeName"],
                "sourceUrl": source["url"],
                "cachePath": str(cache_path.relative_to(ROOT)),
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": "daily",
                "adultFareYen": source["adultFareYen"],
                "routeStopNames": [source["cityStopName"], "山口宇部空港"],
                "busStops": [city_stop, AIRPORT_STOP],
                "trips": trips,
                "tripCount": len(trips),
                "notes": [
                    "Endpoint playable promotion from the official airport HTML timetable current section.",
                    "Official pages publish intermediate stops, but this first gameplay promotion keeps only reliable airport/station endpoints.",
                ],
            }
        )
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.yamaguchi_ube_airport.v1",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "tripCount": sum(len(route["trips"]) for route in routes),
        "stopCount": len({stop["name"] for route in routes for stop in route["busStops"]}),
        "coordinateStopCount": len({stop["name"] for route in routes for stop in route["busStops"] if "lat" in stop and "lon" in stop}),
        "missingCoordinateStops": [],
        "directionCounts": dict(Counter(trip["direction"] for route in routes for trip in route["trips"])),
        "routeTripCounts": {route["routeCode"]: len(route["trips"]) for route in routes},
        "cachePaths": cache_paths,
    }
    source_doc = {
        "schemaVersion": "v5_official_bus_source.yamaguchi_ube_airport.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Yamaguchi Ube Airport HTML timetable current section, effective 2026-04-01 through 2026-05-31.",
        "routes": routes,
    }
    return source_doc, audit


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
