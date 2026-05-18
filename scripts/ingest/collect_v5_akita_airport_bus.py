#!/usr/bin/env python3
"""Collect official Akita Airport limousine bus timetable."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "akita_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_akita_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_akita_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_akita_airport_official_bus_audit.json"
SOURCE_URL = "https://www.akita-chuoukotsu.co.jp/rimzin.php"
SERVICE_START = "20260501"
SERVICE_END = "20260531"

STOP_COORDS = {
    "秋田空港": {"lat": 39.615601, "lon": 140.218994, "coordinateSource": "OpenFlights / V5 flight airport map"},
    "秋田駅西口": {"lat": 39.7173833, "lon": 140.12958, "coordinateSource": "OniChase rail station group centroid: 秋田"},
}


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_cell = False
        self.in_row = False
        self.cell: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.in_row = True
            self.row = []
        elif tag == "td" and self.in_row:
            self.in_cell = True
            self.cell = []
        elif tag == "br" and self.in_cell:
            self.cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_cell:
            self.row.append(clean_text("".join(self.cell)))
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.row:
                self.rows.append(self.row)
            self.in_row = False

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell.append(data)


def clean_text(value: str) -> str:
    text = html.unescape(value).replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", "", text).strip()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"


def fetch_table(tab: int, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[str, Path]:
    query = urllib.parse.urlencode({"action": "table", "tab": tab, "term": 0, "busstop": 1})
    url = f"{SOURCE_URL}?{query}"
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8"), path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read().decode("utf-8", "ignore")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    return data, path


def parse_table(payload: str, *, direction: str) -> list[dict[str, Any]]:
    text = payload.split(">OK:", 1)[-1]
    parser = TableParser()
    parser.feed(text)
    rows = parser.rows
    if len(rows) <= 1:
        cells = [clean_text(re.sub(r"<[^>]+>", "", cell)) for cell in re.findall(r"<td[^>]*>(.*?)</td>", text, flags=re.I | re.S)]
        header_start = next((index for index, cell in enumerate(cells) if "秋田空港" in cell), 0)
        header = cells[header_start : header_start + 9]
        body = cells[header_start + 9 :]
        rows = [header] + [body[index : index + len(header)] for index in range(0, len(body), len(header))]
    header = next((row for row in rows if "秋田空港" in "".join(row) and "秋田駅西口" in "".join(row)), [])
    if not header:
        return []
    airport_index = next(index for index, name in enumerate(header) if "秋田空港" in name)
    station_index = next(index for index, name in enumerate(header) if "秋田駅西口" in name)
    trips = []
    for index, row in enumerate(rows, start=1):
        if len(row) <= max(airport_index, station_index):
            continue
        airport_time = parse_time(row[airport_index])
        station_time = parse_time(row[station_index])
        if not airport_time or not station_time:
            continue
        if direction == "to_airport":
            stop_times = [{"stopName": "秋田駅西口", "time": station_time}, {"stopName": "秋田空港", "time": airport_time}]
        else:
            stop_times = [{"stopName": "秋田空港", "time": airport_time}, {"stopName": "秋田駅西口", "time": station_time}]
        trips.append(
            {
                "tripId": f"akita_airport_limousine:{direction}:{index:03d}",
                "direction": direction,
                "serviceStart": SERVICE_START,
                "serviceEnd": SERVICE_END,
                "serviceDays": "daily",
                "stopTimes": stop_times,
            }
        )
    return trips


def parse_time(value: str) -> str | None:
    match = re.search(r"\d{1,2}:\d{2}", value)
    return match.group(0) if match else None


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    city_payload, city_cache = fetch_table(0, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    airport_payload, airport_cache = fetch_table(1, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    trips = parse_table(city_payload, direction="to_airport") + parse_table(airport_payload, direction="from_airport")
    route = {
        "sourceKind": "official_akita_chuokotsu_ajax_timetable",
        "operatorName": "秋田中央交通",
        "airportIata": "AXT",
        "routeCode": "akita_airport_limousine_akita_station",
        "routeName": "秋田空港リムジンバス 秋田駅西口 ⇔ 秋田空港",
        "sourceUrl": SOURCE_URL,
        "cachePaths": [str(city_cache.relative_to(ROOT)), str(airport_cache.relative_to(ROOT))],
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "adultFareYen": 1200,
        "routeStopNames": ["秋田駅西口", "秋田空港"],
        "busStops": [{"name": name, **coords} for name, coords in STOP_COORDS.items()],
        "trips": trips,
        "tripCount": len(trips),
        "notes": ["Official source exposes a full stop table; this parser promotes the gameplay-critical Akita Station endpoint pair."],
    }
    source = {
        "schemaVersion": "v5_official_bus_source.akita_airport.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Akita Chuo Kotsu limousine bus AJAX timetable for 2026-05-01 through 2026-05-31.",
        "routes": [route],
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.akita_airport.v1",
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
