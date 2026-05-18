#!/usr/bin/env python3
"""Collect official Oita Airport Airliner bus timetables."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "oita_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_oita_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_oita_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_oita_airport_official_bus_audit.json"

BASE_URL = "https://www.oitakotsu.co.jp/bus/airport/disp.php"
PERIOD_URL = "https://www.oitakotsu.co.jp/bus/airport/periods.php?area=44201&rosens=01"
DEFAULT_PERIOD = "20260601_20260630"

NAVITIME_LINE_URL = "https://www.navitime.co.jp/airportbus/line/detail?line=00050252"
NAVITIME_STOP_CODES = {
    "新川": ("00081932", 33.245705, 131.605735, "大分新川"),
    "荷揚町": ("00081930", 33.240509, 131.607269, "荷揚町"),
    "大分駅前": ("00253763", 33.233854, 131.606644, "大分駅前"),
    "生石": ("00253772", 33.245157, 131.586214, "生石(大分県)"),
    "別府駅前": ("00083459", 33.279282, 131.501719, "別府駅前(大分県)"),
    "別府北浜": ("00082765", 33.28005, 131.506093, "別府北浜"),
    "餅ヶ浜": ("00253718", 33.292964, 131.502764, "餅ヶ浜"),
    "観光港": ("00255180", 33.299412, 131.502396, "観光港"),
    "六勝園": ("00253723", 33.31261, 131.50096, "六勝園"),
    "亀川駅前": ("00253730", 33.330927, 131.493576, "亀川駅前"),
    "亀川古市": ("00255105", 33.338009, 131.494316, "古市(別府市)"),
    "グランドメルキュール別府湾前": ("00255170", 33.355932, 131.497583, "グランドメルキュール別府湾前"),
    "日出": ("00082450", 33.373136, 131.534831, "日出"),
    "杵築インター": ("00255169", 33.425925, 131.598064, "杵築IC"),
    "大分空港": ("00254006", 33.47579, 131.732234, "大分空港"),
}

DAY_MARKS = {
    "月": "monday",
    "火": "tuesday",
    "水": "wednesday",
    "木": "thursday",
    "金": "friday",
    "土": "saturday",
    "日": "sunday",
}


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []
        self.tables: list[list[list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "table" and attr.get("id") == "timetable":
            self.in_table = True
            self.rows = []
        if not self.in_table:
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
        if not self.in_table:
            return
        if tag in {"td", "th"} and self.in_cell:
            text = normalize_cell("".join(self.current_cell))
            self.current_row.append(text)
            self.in_cell = False
            self.current_cell = []
        elif tag == "tr" and self.in_row:
            if self.current_row:
                self.rows.append(self.current_row)
            self.in_row = False
        elif tag == "table":
            self.tables.append(self.rows)
            self.in_table = False

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)


def normalize_cell(value: str) -> str:
    text = html.unescape(value).replace("\xa0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.html"


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


def source_url(shubetu: int, period: str) -> str:
    query = urllib.parse.urlencode({"rosen": "01", "shubetu": str(shubetu), "period": period})
    return f"{BASE_URL}?{query}"


def parse_service_days(note: str) -> list[str] | None:
    if "のみ運行" not in note:
        return None
    days = []
    for char, day in DAY_MARKS.items():
        if char in note:
            days.append(day)
    return days or None


def parse_route_table(rows: list[list[str]], *, direction: str, route_code: str, period: str) -> tuple[list[str], list[dict[str, Any]]]:
    stop_names: list[str] = []
    trips: list[dict[str, Any]] = []
    pending_trip: dict[str, Any] | None = None
    route_no_counts: Counter[str] = Counter()
    for row in rows:
        if not row:
            continue
        first = row[0]
        if first == "系統番号" and len(row) > 2 and not stop_names:
            stop_names = [clean_stop_name(cell) for cell in row[1:]]
            continue
        if first == "Route No." or first == "系統番号":
            continue
        if first.startswith("※"):
            if pending_trip:
                pending_trip.setdefault("notes", []).append(first)
                service_days = parse_service_days(first)
                if service_days:
                    pending_trip["serviceDays"] = service_days
            continue
        if not stop_names or len(row) < 2 or not re.fullmatch(r"[A-Z]+", first):
            continue
        route_no = first
        route_no_counts[route_no] += 1
        stop_times = []
        for stop_name, raw in zip(stop_names, row[1:]):
            raw = raw.strip()
            if not raw or raw == "→→":
                continue
            if not re.fullmatch(r"\d{1,2}:\d{2}", raw):
                continue
            stop_times.append({"stopName": stop_name, "time": raw, "raw": raw})
        if len(stop_times) < 2:
            pending_trip = None
            continue
        trip = {
            "tripId": f"{route_code}:{direction}:{route_no.lower()}:{route_no_counts[route_no]:03d}",
            "direction": direction,
            "routePattern": route_no,
            "serviceStart": period.split("_", 1)[0],
            "serviceEnd": period.split("_", 1)[1],
            "stopTimes": stop_times,
        }
        trips.append(trip)
        pending_trip = trip
    return stop_names, trips


def clean_stop_name(value: str) -> str:
    text = re.sub(r"[➊➋➌➍➎➏➐➑➒➓]", "", value)
    text = re.sub(r"\s+", "", text)
    text = text.replace("杵築インター", "杵築インター")
    return text.strip()


def parse_page(html_text: str, *, direction: str, route_code: str, period: str) -> tuple[list[str], list[dict[str, Any]]]:
    parser = TableParser()
    parser.feed(html_text)
    if not parser.tables:
        return [], []
    return parse_route_table(parser.tables[0], direction=direction, route_code=route_code, period=period)


def build_bus_stops(stop_names: list[str]) -> list[dict[str, Any]]:
    stops = []
    for name in stop_names:
        if name not in NAVITIME_STOP_CODES:
            continue
        code, lat, lon, navitime_name = NAVITIME_STOP_CODES[name]
        stops.append(
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
    return stops


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    period_html, period_cache = fetch_text(PERIOD_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    period = args.period
    if not args.period:
        periods = sorted(set(re.findall(r"\b20\d{6}_20\d{6}\b", period_html)))
        period = periods[-1] if periods else DEFAULT_PERIOD

    pages = []
    all_stop_names: list[str] = []
    all_trips: list[dict[str, Any]] = []
    route_code = "oit_oita_beppu_airliner"
    for shubetu, direction in [(1, "to_airport"), (2, "from_airport")]:
        url = source_url(shubetu, period)
        text, cache_path = fetch_text(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        stop_names, trips = parse_page(text, direction=direction, route_code=route_code, period=period)
        for name in stop_names:
            if name not in all_stop_names:
                all_stop_names.append(name)
        all_trips.extend(trips)
        pages.append(
            {
                "direction": direction,
                "sourceUrl": url,
                "cachePath": str(cache_path.relative_to(ROOT)),
                "stopCount": len(stop_names),
                "tripCount": len(trips),
            }
        )

    route = {
        "sourceKind": "official_oita_kotsu_airport_html_timetable",
        "operatorName": "大分交通",
        "airportIata": "OIT",
        "routeCode": route_code,
        "routeName": "エアライナー 大分・別府 ⇔ 大分空港",
        "sourceUrl": source_url(1, period),
        "cachePath": pages[0]["cachePath"] if pages else "",
        "coordinateReferenceUrl": NAVITIME_LINE_URL,
        "serviceStart": period.split("_", 1)[0],
        "serviceEnd": period.split("_", 1)[1],
        "serviceDays": "daily",
        "routeStopNames": all_stop_names,
        "busStops": build_bus_stops(all_stop_names),
        "trips": all_trips,
        "tripCount": len(all_trips),
    }
    source = {
        "schemaVersion": "v5_official_bus_source.oita_airport.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Oita Kotsu airport-bus HTML timetable for the selected service period; NAVITIME stop pages are used only as coordinate references.",
        "period": period,
        "periodSourceUrl": PERIOD_URL,
        "periodCachePath": str(period_cache.relative_to(ROOT)),
        "pages": pages,
        "routes": [route],
    }
    service_day_counts = Counter(",".join(trip.get("serviceDays") or ["daily"]) for trip in all_trips)
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.oita_airport.v1",
        "generatedAt": generated_at,
        "period": period,
        "pageCount": len(pages),
        "routeCount": 1,
        "tripCount": len(all_trips),
        "stopCount": len(all_stop_names),
        "coordinateStopCount": len(route["busStops"]),
        "missingCoordinateStops": [name for name in all_stop_names if name not in NAVITIME_STOP_CODES],
        "serviceDayTripCounts": dict(service_day_counts),
        "routePatternCounts": dict(Counter(trip.get("routePattern") for trip in all_trips)),
    }
    return source, audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--period", default=DEFAULT_PERIOD)
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
