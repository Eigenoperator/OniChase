#!/usr/bin/env python3
"""Collect current Hakodate Airport bus departures from Hakodate Bus."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "hakodate_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_hakodate_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_hakodate_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_hakodate_airport_official_bus_audit.json"

GENERATION_URL = "https://www.primeapps.jp/primetgm-webapp/webresources/thp/generation"
WEEK_URL = "https://www.primeapps.jp/primetgm-webapp/webresources/thp/generationcode={generation_code}"
ROUTE_URL = "https://www.primeapps.jp/primetgm-webapp/webresources/thp/busstopcode={bus_stop_code}/generationcode={generation_code}"
TIMETABLE_URL = "https://map.hakobus.co.jp/sec/timetable/{generation_code}/{bus_stop_code}_{signpole_no:02d}_{week_div:02d}.html"

HAKODATE_AIRPORT_STOP_CODE = "19406"
SOURCE_ACCESS_URL = "https://hakobus.co.jp/visitors/hub/hakodate-airport/"
DEFAULT_SERVICE_END = "20270331"

STOP_COORDS = {
    "函館空港": {
        "lat": 41.77,
        "lon": 140.822006,
        "coordinateSource": "OpenFlights / V5 flight airport map",
    },
    "函館駅前": {
        "lat": 41.7740033,
        "lon": 140.7264067,
        "coordinateSource": "OniChase rail station group centroid: 函館",
    },
}

PLAYABLE_COLUMNS = {
    "5 5A|函館駅前": {
        "routeCode": "hakobus_hkd_5_5a_hakodate_station",
        "routeName": "函館バス 5・5A系統 函館空港 → 函館駅前",
        "arrivalStop": "函館駅前",
        "durationMinutes": 41,
        "sourceNote": "Hakodate Bus access page lists 5/5A to 函館駅前 at about 41 minutes.",
    },
    "【快速】8|函館駅前": {
        "routeCode": "hakobus_hkd_rapid8_hakodate_station",
        "routeName": "函館バス 快速8系統 函館空港 → 函館駅前",
        "arrivalStop": "函館駅前",
        "durationMinutes": 25,
        "sourceNote": "Hakodate Bus access page lists rapid 8 to 函館駅前 at about 25 minutes.",
    },
    "96|函館駅前": {
        "routeCode": "hakobus_hkd_96_hakodate_station",
        "routeName": "函館バス 96系統 函館空港 → 函館駅前",
        "arrivalStop": "函館駅前",
        "durationMinutes": 32,
        "sourceNote": "Hakodate Bus access page lists route 96 to 函館駅前 at about 32 minutes.",
    },
}

WEEK_DIV_TO_DAYS = {
    1: ["monday", "tuesday", "wednesday", "thursday", "friday"],
    2: ["saturday", "sunday"],
}


class TopTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.in_row = False
        self.in_cell = False
        self.current_cell = []
        self.current_colspan = 1
        self.current_row: list[tuple[str, int]] = []
        self.rows: list[list[tuple[str, int]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = {key.lower(): value for key, value in attrs}
        if tag == "table":
            self.depth += 1
        if tag == "tr" and self.depth == 1:
            self.in_row = True
            self.current_row = []
        elif tag in {"td", "th"} and self.in_row and self.depth == 1:
            self.in_cell = True
            self.current_cell = []
            self.current_colspan = int(attr.get("colspan") or 1)
        elif tag == "br" and self.in_cell:
            self.current_cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self.in_row and self.depth == 1 and self.in_cell:
            self.current_row.append((clean_text("".join(self.current_cell)), self.current_colspan))
            self.in_cell = False
            self.current_cell = []
            self.current_colspan = 1
        elif tag == "tr" and self.depth == 1 and self.in_row:
            if self.current_row:
                self.rows.append(self.current_row)
            self.in_row = False
        elif tag == "table":
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)


def clean_text(value: str) -> str:
    text = html.unescape(value).replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, key: str, suffix: str) -> Path:
    return cache_dir / f"{hashlib.sha1(key.encode('utf-8')).hexdigest()}.{suffix}"


def fetch_json(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[Any, Path]:
    path = cache_path_for(cache_dir, url, "json")
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8")), path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return json.loads(data.decode("utf-8")), path


def fetch_html(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[str, Path]:
    path = cache_path_for(cache_dir, url, "html")
    if path.exists() and not refresh:
        return path.read_text(encoding="cp932", errors="ignore"), path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data.decode("cp932", "ignore"), path


def expand_row(row: list[tuple[str, int]]) -> list[str]:
    cells: list[str] = []
    for value, colspan in row:
        for _ in range(max(1, colspan)):
            cells.append(value)
    return cells


def current_generation(generation_payload: dict[str, Any]) -> str:
    for row in generation_payload.get("generationData") or []:
        if row.get("isCurrentGeneration") == 1:
            return str(row["generationCode"])
    rows = generation_payload.get("generationData") or []
    if not rows:
        raise ValueError("Hakodate Bus generation API returned no generation rows")
    return str(rows[-1]["generationCode"])


def parse_timetable(
    html_text: str,
    *,
    week_div: int,
    service_start: str,
) -> list[dict[str, Any]]:
    parser = TopTableParser()
    parser.feed(html_text)
    expanded = [expand_row(row) for row in parser.rows]
    number_row = next((row for row in expanded if row and row[0] == "番号"), [])
    destination_row = next((row for row in expanded if row and row[0] == "行先"), [])
    if len(number_row) < 2 or len(destination_row) < 2:
        return []
    columns = []
    for index, route_number in enumerate(number_row[1:], start=1):
        destination = destination_row[index] if index < len(destination_row) else ""
        key = f"{route_number}|{destination}"
        config = PLAYABLE_COLUMNS.get(key)
        if config:
            columns.append((index, route_number, destination, config))
    trips: list[dict[str, Any]] = []
    days = WEEK_DIV_TO_DAYS.get(week_div, ["monday", "tuesday", "wednesday", "thursday", "friday"])
    for row in expanded:
        if not row or not re.fullmatch(r"\d{1,2}", row[0]):
            continue
        hour = int(row[0])
        for index, route_number, destination, config in columns:
            value = row[index] if index < len(row) else ""
            for minute_text in re.findall(r"\d{2}", value):
                departure = f"{hour:02d}:{int(minute_text):02d}"
                arrival_minutes = hour * 60 + int(minute_text) + int(config["durationMinutes"])
                arrival = f"{arrival_minutes // 60:02d}:{arrival_minutes % 60:02d}"
                trips.append(
                    {
                        "tripId": f"{config['routeCode']}:{week_div}:{hour:02d}{minute_text}",
                        "direction": "from_airport",
                        "routeNumber": route_number,
                        "destination": destination,
                        "serviceStart": service_start,
                        "serviceEnd": DEFAULT_SERVICE_END,
                        "serviceDays": days,
                        "stopTimes": [
                            {"stopName": "函館空港", "time": departure},
                            {"stopName": str(config["arrivalStop"]), "time": arrival, "estimatedFromOfficialRuntime": True},
                        ],
                    }
                )
    return trips


def build_routes(trips: list[dict[str, Any]], source_url: str, cache_paths: list[Path], service_start: str) -> list[dict[str, Any]]:
    by_route: dict[str, list[dict[str, Any]]] = {str(config["routeCode"]): [] for config in PLAYABLE_COLUMNS.values()}
    for trip in trips:
        for config in PLAYABLE_COLUMNS.values():
            if str(trip["tripId"]).startswith(str(config["routeCode"])):
                by_route[str(config["routeCode"])].append(trip)
                break
    bus_stops = [
        {"name": name, **coords}
        for name, coords in STOP_COORDS.items()
    ]
    routes = []
    for config in PLAYABLE_COLUMNS.values():
        route_trips = by_route[str(config["routeCode"])]
        if not route_trips:
            continue
        routes.append(
            {
                "sourceKind": "official_hakodate_bus_current_api_timetable",
                "operatorName": "函館バス",
                "airportIata": "HKD",
                "routeCode": config["routeCode"],
                "routeName": config["routeName"],
                "sourceUrl": source_url,
                "sourceAccessUrl": SOURCE_ACCESS_URL,
                "cachePaths": [str(path.relative_to(ROOT)) for path in cache_paths],
                "serviceStart": service_start,
                "serviceEnd": DEFAULT_SERVICE_END,
                "serviceDays": "mixed_by_trip",
                "routeStopNames": ["函館空港", str(config["arrivalStop"])],
                "busStops": bus_stops,
                "trips": route_trips,
                "tripCount": len(route_trips),
                "notes": [str(config["sourceNote"]), "Airport departure times are from Hakodate Bus current timetable API; arrival times use the official runtime estimate."],
            }
        )
    return routes


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    generation_payload, generation_cache = fetch_json(GENERATION_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    generation_code = args.generation_code or current_generation(generation_payload)
    week_payload, week_cache = fetch_json(WEEK_URL.format(generation_code=generation_code), args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    route_payload, route_cache = fetch_json(
        ROUTE_URL.format(bus_stop_code=HAKODATE_AIRPORT_STOP_CODE, generation_code=generation_code),
        args.cache_dir,
        refresh=args.refresh_cache,
        timeout=args.timeout,
    )
    service_start = args.service_start or str(generation_code)
    all_trips: list[dict[str, Any]] = []
    timetable_caches = []
    for week in week_payload.get("weekDivData") or []:
        week_div = int(week["weekDivCode"])
        html_text, cache_path = fetch_html(
            TIMETABLE_URL.format(
                generation_code=generation_code,
                bus_stop_code=HAKODATE_AIRPORT_STOP_CODE,
                signpole_no=2,
                week_div=week_div,
            ),
            args.cache_dir,
            refresh=args.refresh_cache,
            timeout=args.timeout,
        )
        timetable_caches.append(cache_path)
        all_trips.extend(parse_timetable(html_text, week_div=week_div, service_start=service_start))
    cache_paths = [generation_cache, week_cache, route_cache, *timetable_caches]
    routes = build_routes(all_trips, ROUTE_URL.format(bus_stop_code=HAKODATE_AIRPORT_STOP_CODE, generation_code=generation_code), cache_paths, service_start)
    source = {
        "schemaVersion": "v5_official_bus_source.hakodate_airport.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Hakodate Bus current timetable API is the departure-time source of truth. Official airport/access pages provide route context and runtime estimates.",
        "generationCode": generation_code,
        "generationName": next((row.get("generationName") for row in generation_payload.get("generationData") or [] if str(row.get("generationCode")) == str(generation_code)), ""),
        "airportBusStopCode": HAKODATE_AIRPORT_STOP_CODE,
        "routeSourceRows": route_payload.get("routeData") or [],
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.hakodate_airport.v1",
        "generatedAt": generated_at,
        "generationCode": generation_code,
        "routeCount": len(routes),
        "tripCount": sum(route["tripCount"] for route in routes),
        "stopCount": len({name for route in routes for name in route["routeStopNames"]}),
        "coordinateStopCount": len({stop["name"] for route in routes for stop in route["busStops"]}),
        "missingCoordinateStops": sorted({name for route in routes for name in route["routeStopNames"] if name not in STOP_COORDS}),
        "directionCounts": dict(Counter(trip["direction"] for route in routes for trip in route["trips"])),
        "routeTripCounts": {route["routeCode"]: route["tripCount"] for route in routes},
        "nonPromotedCurrentSourceNote": "Hakodate Teisan airport shuttle current public page was not available for the May 2026 planner date; do not promote its old February 2026 PDF as current service.",
    }
    return source, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--generation-code", default="")
    parser.add_argument("--service-start", default="")
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
