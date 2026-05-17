#!/usr/bin/env python3
"""Collect Yonkoh official Takamatsu Airport bus timetable."""

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
SOURCE_URL = "https://yonkoh.co.jp/airport-1"
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "takamatsu_yonkoh"
DEFAULT_OUTPUT = ROOT / "data" / "v5_takamatsu_yonkoh_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_takamatsu_yonkoh_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_takamatsu_yonkoh_official_bus_audit.json"


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


def parse_time(value: str) -> str | None:
    match = re.search(r"\d{1,2}[：:]\d{2}", str(value or ""))
    return match.group(0).replace("：", ":") if match else None


def parse_trip_section(header: list[str], stop_rows: list[list[str]], direction: str) -> list[dict[str, Any]]:
    trips = []
    for column in range(1, len(header)):
        stop_times = []
        for row in stop_rows:
            if column >= len(row):
                continue
            time = parse_time(row[column])
            if time:
                stop_times.append({"stopName": row[0], "time": time, "raw": row[column]})
        if len(stop_times) >= 2:
            trips.append({"tripId": f"tak_yonkoh:{direction}:{column:03d}", "direction": direction, "serviceName": header[column], "stopTimes": stop_times})
    return trips


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    html_text, cache_path = fetch_text(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    parser = TableParser()
    parser.feed(html_text)
    rows = parser.rows
    trips = []
    route_sections = []
    for idx, row in enumerate(rows):
        if row and "便" in "".join(row) and idx + 3 < len(rows):
            stop_rows = rows[idx + 1 : idx + 4]
            direction = "to_airport" if stop_rows[-1][0] == "高松空港" else "from_airport"
            section_trips = parse_trip_section(row, stop_rows, direction)
            trips.extend(section_trips)
            route_sections.append({"direction": direction, "stops": [item[0] for item in stop_rows], "tripCount": len(section_trips), "trips": section_trips})
    route = {
        "sourceKind": "official_yonkoh_html_timetable",
        "operatorName": "四国交通",
        "airportIata": "TAK",
        "routeCode": "tak_yonkoh_awaikeda",
        "routeName": "阿波池田バスターミナル ⇔ 高松空港",
        "sourceUrl": SOURCE_URL,
        "cachePath": str(cache_path.relative_to(ROOT)),
        "directions": route_sections,
        "routeStopNames": sorted({stop for section in route_sections for stop in section["stops"]}),
        "tripCount": len(trips),
    }
    source = {
        "schemaVersion": "v5_official_bus_source.takamatsu_yonkoh.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Yonkoh Takamatsu Airport route HTML timetable. The table is parsed into both directions; fare table remains source-captured.",
        "routes": [route],
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.takamatsu_yonkoh.v1",
        "generatedAt": generated_at,
        "routeCount": 1,
        "tripCount": route["tripCount"],
        "routes": [{"routeCode": route["routeCode"], "tripCount": route["tripCount"], "stopCount": len(route["routeStopNames"])}],
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
