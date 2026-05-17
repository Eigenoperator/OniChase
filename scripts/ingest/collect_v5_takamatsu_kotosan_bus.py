#!/usr/bin/env python3
"""Collect Kotosan Bus official Takamatsu Airport limousine timetable."""

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
SOURCE_URL = "https://www.kotosan.co.jp/limousine/"
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "takamatsu_kotosan"
DEFAULT_OUTPUT = ROOT / "data" / "v5_takamatsu_kotosan_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_takamatsu_kotosan_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_takamatsu_kotosan_official_bus_audit.json"


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
    marks = []
    if "運休" in raw:
        marks.append("運休")
    for marker in ["☆", "◎"]:
        if marker in raw:
            marks.append(marker)
    return match.group(0), marks


def is_header(row: list[str]) -> bool:
    return "高松空港" in row and sum(1 for cell in row if parse_time(cell)[0]) == 0 and len(row) >= 5


def parse_sections(rows: list[list[str]]) -> list[dict[str, Any]]:
    sections = []
    current_header: list[str] | None = None
    current_rows: list[list[str]] = []

    def flush() -> None:
        nonlocal current_header, current_rows
        if not current_header:
            return
        stops = [stop for stop in current_header if stop != "航空便・航空会社"]
        direction = "to_airport" if stops[-1] == "高松空港" else "from_airport"
        trips = []
        for row_index, row in enumerate(current_rows, start=1):
            stop_times = []
            suspended = False
            offset = 0 if current_header[0] != "航空便・航空会社" else 1
            for stop, cell in zip(stops, row[offset:]):
                time, marks = parse_time(cell)
                if "運休" in marks:
                    suspended = True
                if time:
                    stop_times.append({"stopName": stop, "time": time, "raw": cell, "marks": marks})
            if len(stop_times) >= 2 and not suspended:
                trips.append({"tripId": f"tak_kotosan:{len(sections) + 1:02d}:{direction}:{row_index:03d}", "direction": direction, "stopTimes": stop_times})
        if trips:
            sections.append({"direction": direction, "stops": stops, "tripCount": len(trips), "trips": trips})
        current_header = None
        current_rows = []

    for row in rows:
        if is_header(row):
            flush()
            current_header = row
            current_rows = []
        elif current_header and sum(1 for cell in row if parse_time(cell)[0]) >= 2:
            current_rows.append(row)
        elif current_header and row and row[0] == "":
            flush()
    flush()
    return sections


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    html_text, cache_path = fetch_text(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    parser = TableParser()
    parser.feed(html_text)
    sections = parse_sections(parser.rows)
    routes = [
        {
            "sourceKind": "official_kotosan_html_timetable",
            "operatorName": "琴参バス",
            "airportIata": "TAK",
            "routeCode": f"tak_kotosan_{index:02d}",
            "routeName": f"{section['stops'][0]} ⇔ {section['stops'][-1]}",
            "sourceUrl": SOURCE_URL,
            "cachePath": str(cache_path.relative_to(ROOT)),
            "directions": [section],
            "routeStopNames": section["stops"],
            "tripCount": section["tripCount"],
        }
        for index, section in enumerate(sections, start=1)
    ]
    source = {
        "schemaVersion": "v5_official_bus_source.takamatsu_kotosan.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Kotosan Bus Takamatsu Airport limousine HTML timetable. Rows marked 運休 are preserved in cache but skipped from active trips.",
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.takamatsu_kotosan.v1",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "tripCount": sum(route["tripCount"] for route in routes),
        "routes": [{"routeCode": route["routeCode"], "routeName": route["routeName"], "tripCount": route["tripCount"], "stopCount": len(route["routeStopNames"])} for route in routes],
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
