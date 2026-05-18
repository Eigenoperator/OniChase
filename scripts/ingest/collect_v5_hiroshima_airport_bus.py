#!/usr/bin/env python3
"""Collect official Hiroshima Airport limousine bus timetables."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "hiroshima_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_hiroshima_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_hiroshima_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_hiroshima_airport_official_bus_audit.json"

BUS_CENTER_URL = "https://www.hij.airport.jp/access/timetable/1.html"
HIROSHIMA_STATION_URL = "https://www.hij.airport.jp/access/timetable/next_2.html"
DEFAULT_SERVICE_START = "20260329"
DEFAULT_SERVICE_END = "20260630"

STOP_COORDS = {
    "広島バスセンター": ("00025552", 34.396039, 132.457059, "広島バスセンター"),
    "中筋駅": ("00025623", 34.450983, 132.477405, "中筋駅"),
    "広島駅新幹線口": ("00025553", 34.398659, 132.475772, "広島駅新幹線口"),
    "広島空港": ("00097030", 34.440557, 132.918751, "広島空港"),
}


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.cell: list[str] = []
        self.row: list[str] = []
        self.current: list[list[str]] = []
        self.tables: list[list[list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.in_table = True
            self.current = []
        if not self.in_table:
            return
        if tag == "tr":
            self.in_row = True
            self.row = []
        elif tag in {"td", "th"} and self.in_row:
            self.in_cell = True
            self.cell = []
        elif tag == "br" and self.in_cell:
            self.cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if not self.in_table:
            return
        if tag in {"td", "th"} and self.in_cell:
            self.row.append(clean_cell("".join(self.cell)))
            self.cell = []
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.row:
                self.current.append(self.row)
            self.row = []
            self.in_row = False
        elif tag == "table":
            self.tables.append(self.current)
            self.current = []
            self.in_table = False

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell.append(data)


def clean_cell(value: str) -> str:
    text = html.unescape(value).replace("\xa0", " ").replace("\u3000", " ")
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\([^)]*\)番ホーム", "", text)
    text = text.replace("広島駅 新幹線口", "広島駅新幹線口")
    text = text.replace("中筋駅", "中筋駅")
    text = re.sub(r"\s+", "", text)
    if text == "バスセンター":
        text = "広島バスセンター"
    return text.strip()


def parse_time(value: str) -> str | None:
    match = re.search(r"\d{1,2}:\d{2}", value)
    return match.group(0) if match else None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"


def fetch_text(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[str, Path]:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8", errors="ignore"), path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data.decode("utf-8", "ignore"), path


def parse_timetable_table(
    rows: list[list[str]],
    *,
    direction: str,
    route_code: str,
    service_start: str,
    service_end: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    if not rows:
        return [], []
    stops = rows[0]
    if len(stops) < 2 or not all(stop in STOP_COORDS for stop in stops):
        return [], []
    trips = []
    for index, row in enumerate(rows[1:], start=1):
        if len(row) < len(stops):
            continue
        stop_times = []
        for stop_name, raw in zip(stops, row[: len(stops)]):
            value = parse_time(raw)
            if value:
                stop_times.append({"stopName": stop_name, "time": value, "raw": raw})
        if len(stop_times) < 2:
            continue
        trips.append(
            {
                "tripId": f"{route_code}:{direction}:{index:03d}",
                "direction": direction,
                "serviceStart": service_start,
                "serviceEnd": service_end,
                "stopTimes": stop_times,
            }
        )
    return stops, trips


def parse_page(url: str, cache_path: Path, *, route_code: str, service_start: str, service_end: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text = cache_path.read_text(encoding="utf-8", errors="ignore")
    parser = TableParser()
    parser.feed(text)
    routes = []
    page_rows = []
    timetable_tables = [table for table in parser.tables if table and table[0] and all(cell in STOP_COORDS for cell in table[0])]
    for table_index, table in enumerate(timetable_tables, start=1):
        first = table[0][0]
        last = table[0][-1]
        direction = "to_airport" if last == "広島空港" else "from_airport"
        stops, trips = parse_timetable_table(
            table,
            direction=direction,
            route_code=route_code,
            service_start=service_start,
            service_end=service_end,
        )
        page_rows.append({"tableIndex": table_index, "direction": direction, "stopCount": len(stops), "tripCount": len(trips)})
        if trips:
            routes.append({"stops": stops, "trips": trips})
    return routes, page_rows


def build_route(route_code: str, route_name: str, source_url: str, cache_path: Path, parsed_parts: list[dict[str, Any]], service_start: str, service_end: str) -> dict[str, Any]:
    stop_names: list[str] = []
    trips: list[dict[str, Any]] = []
    for part in parsed_parts:
        for name in part["stops"]:
            if name not in stop_names:
                stop_names.append(name)
        trips.extend(part["trips"])
    bus_stops = []
    for name in stop_names:
        code, lat, lon, navitime_name = STOP_COORDS[name]
        bus_stops.append(
            {
                "name": name,
                "lat": lat,
                "lon": lon,
                "coordinateSource": "NAVITIME bus stop page",
                "coordinateSourceUrl": f"https://www.navitime.co.jp/poi?node={code}",
                "navitimeStopCode": code,
                "navitimeStopName": navitime_name,
            }
        )
    return {
        "sourceKind": "official_hiroshima_airport_html_timetable",
        "operatorName": "広島空港リムジンバス共同運行",
        "airportIata": "HIJ",
        "routeCode": route_code,
        "routeName": route_name,
        "sourceUrl": source_url,
        "cachePath": str(cache_path.relative_to(ROOT)),
        "serviceStart": service_start,
        "serviceEnd": service_end,
        "serviceDays": "daily",
        "routeStopNames": stop_names,
        "busStops": bus_stops,
        "trips": trips,
        "tripCount": len(trips),
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    routes = []
    pages = []
    for route_code, route_name, url in [
        ("hij_bus_center_airport_limousine", "広島バスセンター・中筋駅 ⇔ 広島空港", args.bus_center_url),
        ("hij_hiroshima_station_airport_limousine", "広島駅新幹線口 ⇔ 広島空港", args.hiroshima_station_url),
    ]:
        _text, cache_path = fetch_text(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        parts, page_rows = parse_page(
            url,
            cache_path,
            route_code=route_code,
            service_start=args.service_start,
            service_end=args.service_end,
        )
        route = build_route(route_code, route_name, url, cache_path, parts, args.service_start, args.service_end)
        routes.append(route)
        pages.append({"sourceUrl": url, "cachePath": str(cache_path.relative_to(ROOT)), "routeCode": route_code, "tables": page_rows, "tripCount": route["tripCount"]})
    source = {
        "schemaVersion": "v5_official_bus_source.hiroshima_airport.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Hiroshima Airport access timetable pages. NAVITIME stop pages are used only as coordinate references.",
        "pages": pages,
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.hiroshima_airport.v1",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "tripCount": sum(route["tripCount"] for route in routes),
        "stopCount": len({name for route in routes for name in route["routeStopNames"]}),
        "coordinateStopCount": len({stop["name"] for route in routes for stop in route["busStops"]}),
        "missingCoordinateStops": sorted({name for route in routes for name in route["routeStopNames"] if name not in STOP_COORDS}),
        "directionCounts": dict(Counter(trip["direction"] for route in routes for trip in route["trips"])),
        "routeTripCounts": {route["routeCode"]: route["tripCount"] for route in routes},
    }
    return source, audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--bus-center-url", default=BUS_CENTER_URL)
    parser.add_argument("--hiroshima-station-url", default=HIROSHIMA_STATION_URL)
    parser.add_argument("--service-start", default=DEFAULT_SERVICE_START)
    parser.add_argument("--service-end", default=DEFAULT_SERVICE_END)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    source, audit = collect(args)
    write_json(args.output, source)
    write_json(args.docs_output, source)
    write_json(args.audit_output, audit)
    print(json.dumps({"output": str(args.output), **audit}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
