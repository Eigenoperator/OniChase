#!/usr/bin/env python3
"""Collect official Matsuyama Airport limousine bus timetables."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "matsuyama_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_matsuyama_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_matsuyama_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_matsuyama_airport_official_bus_audit.json"

SOURCE_URL = "https://www.iyotetsu.co.jp/bus/limousine/airport/"
NAVITIME_LINE_URL = "https://www.navitime.co.jp/bus/company/00001251/route/00062080/"
DEFAULT_SERVICE_START = "20260501"
DEFAULT_SERVICE_END = "20260531"

FROM_AIRPORT_STOPS = ["松山空港", "JR松山駅前", "愛媛新聞社前", "松山市駅", "大街道", "県民文化会館前", "道後温泉駅前"]
TO_AIRPORT_STOPS = ["道後温泉駅前", "県民文化会館前", "大街道", "松山市駅", "愛媛新聞社前", "JR松山駅前", "松山空港"]

NAVITIME_STOP_COORDS = {
    "道後温泉駅前": ("00042725", 33.850611, 132.784993, "道後温泉駅"),
    "県民文化会館前": ("00301044", 33.847422, 132.779134, "南町県民文化会館前"),
    "大街道": ("00292885", 33.841337, 132.770809, "大街道"),
    "松山市駅": ("00026286", 33.835979, 132.762276, "松山市駅"),
    "愛媛新聞社前": ("00366511", 33.840092, 132.757732, "愛媛新聞社前"),
    "JR松山駅前": ("00025583", 33.840142, 132.751681, "JR松山駅"),
    "松山空港": ("00293240", 33.829405, 132.704106, "松山空港"),
}


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_target_table = False
        self.target_id = ""
        self.in_row = False
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.tables: dict[str, list[list[str]]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "table" and attr.get("id") in {"time_nobori", "time_kudari"}:
            self.in_target_table = True
            self.target_id = attr["id"] or ""
            self.tables[self.target_id] = []
        if not self.in_target_table:
            return
        if tag == "tr":
            self.in_row = True
            self.current_row = []
        elif tag in {"td", "th"} and self.in_row:
            self.in_cell = True
            self.current_cell = []
        elif tag == "br" and self.in_cell:
            self.current_cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if not self.in_target_table:
            return
        if tag in {"td", "th"} and self.in_cell:
            self.current_row.append(normalize_cell("".join(self.current_cell)))
            self.current_cell = []
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.current_row:
                self.tables[self.target_id].append(self.current_row)
            self.current_row = []
            self.in_row = False
        elif tag == "table":
            self.in_target_table = False
            self.target_id = ""

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)


def normalize_cell(value: str) -> str:
    text = html.unescape(value).replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


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


def parse_time(value: str) -> str | None:
    text = value.strip().replace("：", ":")
    if text in {"", "-", "→"}:
        return None
    if re.fullmatch(r"\d{1,2}:\d{2}", text):
        return text
    return None


def parse_rows(rows: list[list[str]], *, stops: list[str], direction: str, route_code: str, service_start: str, service_end: str) -> list[dict[str, Any]]:
    trips = []
    for index, row in enumerate(rows, start=1):
        cells = [cell for cell in row if cell != "　"]
        if not cells or not any(parse_time(cell) for cell in cells):
            continue
        stop_cells = cells[-len(stops) :]
        if len(stop_cells) < len(stops):
            continue
        stop_times = []
        for stop_name, raw in zip(stops, stop_cells):
            value = parse_time(raw)
            if value:
                stop_times.append({"stopName": stop_name, "time": value, "raw": raw})
        if len(stop_times) < 2:
            continue
        trip = {
            "tripId": f"{route_code}:{direction}:{index:03d}",
            "direction": direction,
            "serviceStart": service_start,
            "serviceEnd": service_end,
            "stopTimes": stop_times,
        }
        trips.append(trip)
    return trips


def build_bus_stops() -> list[dict[str, Any]]:
    rows = []
    for name, (code, lat, lon, navitime_name) in NAVITIME_STOP_COORDS.items():
        rows.append(
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
    return rows


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    text, cache_path = fetch_text(args.source_url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    parser = TableParser()
    parser.feed(text)
    route_code = "myj_iyotetsu_airport_limousine"
    from_airport = parse_rows(
        parser.tables.get("time_nobori", []),
        stops=FROM_AIRPORT_STOPS,
        direction="from_airport",
        route_code=route_code,
        service_start=args.service_start,
        service_end=args.service_end,
    )
    to_airport = parse_rows(
        parser.tables.get("time_kudari", []),
        stops=TO_AIRPORT_STOPS,
        direction="to_airport",
        route_code=route_code,
        service_start=args.service_start,
        service_end=args.service_end,
    )
    trips = from_airport + to_airport
    route = {
        "sourceKind": "official_iyotetsu_matsuyama_airport_html_timetable",
        "operatorName": "伊予鉄バス",
        "airportIata": "MYJ",
        "routeCode": route_code,
        "routeName": "松山空港リムジンバス",
        "sourceUrl": args.source_url,
        "cachePath": str(cache_path.relative_to(ROOT)),
        "coordinateReferenceUrl": NAVITIME_LINE_URL,
        "serviceStart": args.service_start,
        "serviceEnd": args.service_end,
        "serviceDays": "daily",
        "routeStopNames": list(dict.fromkeys(FROM_AIRPORT_STOPS + TO_AIRPORT_STOPS)),
        "busStops": build_bus_stops(),
        "trips": trips,
        "tripCount": len(trips),
    }
    source = {
        "schemaVersion": "v5_official_bus_source.matsuyama_airport.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Iyotetsu Matsuyama Airport limousine HTML timetable. NAVITIME stop pages are used only as coordinate references.",
        "pages": [
            {
                "direction": "from_airport",
                "sourceUrl": args.source_url,
                "cachePath": str(cache_path.relative_to(ROOT)),
                "tripCount": len(from_airport),
            },
            {
                "direction": "to_airport",
                "sourceUrl": args.source_url,
                "cachePath": str(cache_path.relative_to(ROOT)),
                "tripCount": len(to_airport),
            },
        ],
        "routes": [route],
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.matsuyama_airport.v1",
        "generatedAt": generated_at,
        "sourceUrl": args.source_url,
        "routeCount": 1,
        "tripCount": len(trips),
        "fromAirportTripCount": len(from_airport),
        "toAirportTripCount": len(to_airport),
        "stopCount": len(route["routeStopNames"]),
        "coordinateStopCount": len(route["busStops"]),
        "missingCoordinateStops": [name for name in route["routeStopNames"] if name not in NAVITIME_STOP_COORDS],
        "directionCounts": dict(Counter(trip["direction"] for trip in trips)),
    }
    return source, audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--source-url", default=SOURCE_URL)
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
