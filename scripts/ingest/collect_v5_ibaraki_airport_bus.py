#!/usr/bin/env python3
"""Collect Ibaraki Airport official access-bus timetables."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "ibaraki_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_ibaraki_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_ibaraki_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_ibaraki_airport_official_bus_audit.json"

SOURCES = {
    "mito": "https://www.ibaraki-airport.net/access/bus/mito/",
    "ishioka": "https://www.ibaraki-airport.net/access/bus/ishioka/",
}

STOPS = {
    "水戸駅": {"lat": 36.3709295, "lon": 140.4772005, "coordinateSource": "OniChase rail station group centroid: 水戸"},
    "石岡駅": {"lat": 36.1912, "lon": 140.2799625, "coordinateSource": "OniChase rail station group centroid: 石岡"},
    "茨城空港": {"lat": 36.181456, "lon": 140.414434, "coordinateSource": "OpenFlights / V5 flight airport map"},
}

ROUTE_META = {
    "mito_highway": {
        "routeCode": "ibaraki_airport_mito_highway",
        "routeName": "茨城空港アクセスバス 水戸駅高速線",
        "cityStopName": "水戸駅",
        "adultFareYen": 1500,
        "serviceStart": "20260329",
        "serviceEnd": "20261024",
    },
    "mito_local": {
        "routeCode": "ibaraki_airport_mito_local",
        "routeName": "茨城空港アクセスバス 水戸駅一般道線",
        "cityStopName": "水戸駅",
        "adultFareYen": 1190,
        "serviceStart": "20260401",
        "serviceEnd": "20261024",
    },
    "ishioka": {
        "routeCode": "ibaraki_airport_ishioka",
        "routeName": "茨城空港アクセスバス 石岡駅線",
        "cityStopName": "石岡駅",
        "adultFareYen": 680,
        "serviceStart": "20260501",
        "serviceEnd": "20261024",
    },
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


def service_days_for(value: str) -> str | list[str]:
    if "土日祝運休" in value or "Except Sat" in value:
        return ["monday", "tuesday", "wednesday", "thursday", "friday"]
    if "土日祝のみ" in value or "Sat, Sun" in value:
        return ["saturday", "sunday"]
    return "daily"


def route_key_for_mito(label: str) -> str:
    return "mito_highway" if "高速" in label or "Express" in label else "mito_local"


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


def parse_rows(html_text: str) -> list[list[str]]:
    parser = TableParser()
    parser.feed(html_text)
    return parser.rows


def build_mito_trips(rows: list[list[str]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    header2_index = next(index for index, row in enumerate(rows) if row and "茨城空港 発" in row[1])
    for index, row in enumerate(rows[1:header2_index], start=1):
        if len(row) < 3:
            continue
        route_key = route_key_for_mito(row[0])
        city_time = parse_time(row[1])
        airport_time = parse_time(row[2])
        if not city_time or not airport_time:
            continue
        meta = ROUTE_META[route_key]
        grouped[route_key].append(
            {
                "tripId": f"{meta['routeCode']}:to_airport:{index:03d}",
                "direction": "to_airport",
                "serviceStart": meta["serviceStart"],
                "serviceEnd": meta["serviceEnd"],
                "serviceDays": service_days_for(row[0]),
                "stopTimes": [{"stopName": "水戸駅", "time": city_time}, {"stopName": "茨城空港", "time": airport_time}],
            }
        )
    for index, row in enumerate(rows[header2_index + 1 :], start=1):
        if len(row) < 3:
            continue
        route_key = route_key_for_mito(row[0])
        airport_time = parse_time(row[1])
        city_time = parse_time(row[2])
        if not city_time or not airport_time:
            continue
        meta = ROUTE_META[route_key]
        grouped[route_key].append(
            {
                "tripId": f"{meta['routeCode']}:from_airport:{index:03d}",
                "direction": "from_airport",
                "serviceStart": meta["serviceStart"],
                "serviceEnd": meta["serviceEnd"],
                "serviceDays": service_days_for(row[0]),
                "stopTimes": [{"stopName": "茨城空港", "time": airport_time}, {"stopName": "水戸駅", "time": city_time}],
            }
        )
    return grouped


def build_ishioka_trips(rows: list[list[str]]) -> list[dict[str, Any]]:
    trips = []
    header2_index = next(index for index, row in enumerate(rows) if row and "茨城空港 発" in row[0])
    meta = ROUTE_META["ishioka"]
    for index, row in enumerate(rows[1:header2_index], start=1):
        city_time = parse_time(row[0])
        airport_time = parse_time(row[1] if len(row) > 1 else "")
        if city_time and airport_time:
            trips.append(
                {
                    "tripId": f"{meta['routeCode']}:to_airport:{index:03d}",
                    "direction": "to_airport",
                    "serviceStart": meta["serviceStart"],
                    "serviceEnd": meta["serviceEnd"],
                    "serviceDays": service_days_for(row[0]),
                    "stopTimes": [{"stopName": "石岡駅", "time": city_time}, {"stopName": "茨城空港", "time": airport_time}],
                }
            )
    for index, row in enumerate(rows[header2_index + 1 :], start=1):
        airport_time = parse_time(row[0])
        city_time = parse_time(row[1] if len(row) > 1 else "")
        if city_time and airport_time:
            trips.append(
                {
                    "tripId": f"{meta['routeCode']}:from_airport:{index:03d}",
                    "direction": "from_airport",
                    "serviceStart": meta["serviceStart"],
                    "serviceEnd": meta["serviceEnd"],
                    "serviceDays": service_days_for(row[0]),
                    "stopTimes": [{"stopName": "茨城空港", "time": airport_time}, {"stopName": "石岡駅", "time": city_time}],
                }
            )
    return trips


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def route_from_trips(route_key: str, trips: list[dict[str, Any]], source_url: str, cache_path: Path) -> dict[str, Any]:
    meta = ROUTE_META[route_key]
    city_stop = meta["cityStopName"]
    return {
        "sourceKind": "official_ibaraki_airport_html",
        "operatorName": "茨城空港アクセスバス",
        "airportIata": "IBR",
        "routeCode": meta["routeCode"],
        "routeName": meta["routeName"],
        "sourceUrl": source_url,
        "cachePath": str(cache_path.relative_to(ROOT)),
        "serviceStart": meta["serviceStart"],
        "serviceEnd": meta["serviceEnd"],
        "serviceDays": "mixed_by_trip",
        "adultFareYen": meta["adultFareYen"],
        "routeStopNames": [city_stop, "茨城空港"],
        "busStops": [{"name": city_stop, **STOPS[city_stop]}, {"name": "茨城空港", **STOPS["茨城空港"]}],
        "trips": trips,
        "tripCount": len(trips),
        "notes": ["Endpoint playable promotion from official Ibaraki Airport access-bus timetable. Route is split by fare/service family."],
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    mito_html, mito_cache = fetch_html(SOURCES["mito"], args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    ishioka_html, ishioka_cache = fetch_html(SOURCES["ishioka"], args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    grouped = build_mito_trips(parse_rows(mito_html))
    grouped["ishioka"] = build_ishioka_trips(parse_rows(ishioka_html))
    routes = [
        route_from_trips("mito_highway", grouped["mito_highway"], SOURCES["mito"], mito_cache),
        route_from_trips("mito_local", grouped["mito_local"], SOURCES["mito"], mito_cache),
        route_from_trips("ishioka", grouped["ishioka"], SOURCES["ishioka"], ishioka_cache),
    ]
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.ibaraki_airport.v1",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "tripCount": sum(len(route["trips"]) for route in routes),
        "stopCount": len({stop["name"] for route in routes for stop in route["busStops"]}),
        "coordinateStopCount": len({stop["name"] for route in routes for stop in route["busStops"] if "lat" in stop and "lon" in stop}),
        "missingCoordinateStops": [],
        "directionCounts": dict(Counter(trip["direction"] for route in routes for trip in route["trips"])),
        "serviceDayCounts": dict(Counter(str(trip["serviceDays"]) for route in routes for trip in route["trips"])),
        "routeTripCounts": {route["routeCode"]: len(route["trips"]) for route in routes},
    }
    source = {
        "schemaVersion": "v5_official_bus_source.ibaraki_airport.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Ibaraki Airport access-bus timetables. Mito service covers 2026-03-29/04-01 through 2026-10-24; Ishioka service covers 2026-05-01 through 2026-10-24.",
        "routes": routes,
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
