#!/usr/bin/env python3
"""Collect official Nagasaki Airport bus timetable pages."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from collect_v5_keikyu_haneda_bus import TableParser


ROOT = Path(__file__).resolve().parents[2]
SOURCE_URLS = {
    "to_airport": "https://nagasaki-airport.jp/access/bus/timetable/bus_nagasaki_go.php",
    "from_airport": "https://nagasaki-airport.jp/access/bus/timetable/bus_nagasaki.php",
}
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "nagasaki_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_nagasaki_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_nagasaki_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_nagasaki_airport_official_bus_audit.json"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"


def fetch_text(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[str, Path]:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8"), path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", "ignore")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text, path


def parse_time(value: str) -> tuple[str | None, list[str]]:
    raw = str(value or "").strip()
    match = re.search(r"\d{1,2}:\d{2}", raw)
    if not match:
        return None, []
    marks = [char for char in raw[: match.start()] if char and not char.isspace()]
    return match.group(0), marks


def is_time_row(row: list[str]) -> bool:
    return bool(row) and sum(1 for cell in row if parse_time(cell)[0]) >= max(2, len(row) // 2)


def route_code(direction: str, stops: list[str], index: int) -> str:
    if any("新地" in stop or "中央橋" in stop for stop in stops):
        suffix = "shinchi"
    elif any("昭和町" in stop or "平和公園" in stop for stop in stops):
        suffix = "showamachi"
    else:
        suffix = f"section{index}"
    return f"nagasaki_{suffix}_{direction}"


def parse_sections(rows: list[list[str]], direction: str) -> list[dict[str, Any]]:
    sections = []
    current_header: list[str] | None = None
    current_rows: list[list[str]] = []
    section_index = 0
    for row in rows:
        if row and not is_time_row(row):
            if current_header and current_rows:
                section_index += 1
                sections.append((section_index, current_header, current_rows))
            current_header = row
            current_rows = []
        elif current_header and is_time_row(row):
            current_rows.append(row)
    if current_header and current_rows:
        section_index += 1
        sections.append((section_index, current_header, current_rows))
    routes = []
    for index, stops, time_rows in sections:
        trips = []
        for row_index, row in enumerate(time_rows, start=1):
            stop_times = []
            for stop, cell in zip(stops, row):
                time, marks = parse_time(cell)
                if time:
                    stop_times.append({"stopName": stop, "time": time, "raw": cell, "marks": marks})
            if len(stop_times) >= 2:
                code = route_code(direction, stops, index)
                trips.append({"tripId": f"nagasaki_airport:{code}:{row_index:03d}", "direction": direction, "stopTimes": stop_times})
        code = route_code(direction, stops, index)
        routes.append(
            {
                "sourceKind": "official_nagasaki_airport_html_timetable",
                "operatorName": "Nagasaki Airport Bus Operators",
                "airportIata": "NGS",
                "routeCode": code,
                "routeName": f"{stops[0]} ⇔ {stops[-1]}",
                "direction": direction,
                "stops": stops,
                "trips": trips,
                "tripCount": len(trips),
            }
        )
    return routes


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    pages = []
    routes = []
    for direction, url in SOURCE_URLS.items():
        html_text, cache_path = fetch_text(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        parser = TableParser()
        parser.feed(html_text)
        page_routes = parse_sections(parser.rows, direction)
        pages.append({"direction": direction, "sourceUrl": url, "cachePath": str(cache_path.relative_to(ROOT)), "routeCount": len(page_routes), "tripCount": sum(route["tripCount"] for route in page_routes)})
        routes.extend(page_routes)
    source = {
        "schemaVersion": "v5_official_bus_source.nagasaki_airport.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Nagasaki Airport monthly bus timetable HTML pages. Current source URLs are monthly pages and should be refreshed each service month.",
        "pages": pages,
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.nagasaki_airport.v1",
        "generatedAt": generated_at,
        "pageCount": len(pages),
        "routeCount": len(routes),
        "tripCount": sum(route["tripCount"] for route in routes),
        "pages": pages,
        "routes": [{"routeCode": route["routeCode"], "direction": route["direction"], "stopCount": len(route["stops"]), "tripCount": route["tripCount"]} for route in routes],
    }
    return source, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    source, audit = collect(args)
    write_json(args.output, source)
    write_json(args.docs_output, source)
    write_json(args.audit_output, audit)
    print(json.dumps({"routeCount": audit["routeCount"], "tripCount": audit["tripCount"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
