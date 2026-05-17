#!/usr/bin/env python3
"""Collect official Miyazaki Airport bus timetable source data."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from collect_v5_keikyu_haneda_bus import TableParser


ROOT = Path(__file__).resolve().parents[2]
SOURCE_URL = "https://www.miyazaki-airport.co.jp/access/bus"
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "miyazaki_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_miyazaki_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_miyazaki_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_miyazaki_airport_official_bus_audit.json"

AIRPORT_STOP_NAME = "宮崎空港"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.html"


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


def clean_text(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_timed_tokens(value: str) -> list[dict[str, Any]]:
    output = []
    for match in re.finditer(r"([^\s\d:]*)(\d{1,2}:\d{2})", value):
        marks = [char for char in match.group(1) if char and not char.isspace()]
        output.append({"time": match.group(2), "marks": marks, "raw": match.group(0)})
    return output


def route_code(name: str) -> str:
    mapping = {
        "宮崎駅": "miyazaki_station",
        "飫肥（日南）": "obi_nichinan",
        "西都城": "nishi_miyakonojo",
        "シーガイア": "seagaia",
    }
    return mapping.get(name, re.sub(r"[^A-Za-z0-9]+", "_", name) or "route")


def parse_routes(rows: list[list[str]]) -> list[dict[str, Any]]:
    routes = []
    row_index = 0
    while row_index + 1 < len(rows):
        header = rows[row_index]
        times = rows[row_index + 1]
        row_index += 2
        if len(header) < 2 or len(times) < 2:
            continue
        origin_label = clean_text(header[0])
        airport_label = clean_text(header[1])
        if not origin_label.endswith("発") or airport_label != "空港発":
            continue
        terminal = origin_label[:-1]
        code = route_code(terminal)
        to_airport_cells = times[:2] if len(times) >= 4 else times[:1]
        from_airport_cells = times[2:4] if len(times) >= 4 else times[1:2]
        directions = []
        for direction_name, cells, stops in [
            ("to_airport", to_airport_cells, [terminal, AIRPORT_STOP_NAME]),
            ("from_airport", from_airport_cells, [AIRPORT_STOP_NAME, terminal]),
        ]:
            trips = []
            tokens = []
            for cell in cells:
                tokens.extend(parse_timed_tokens(cell))
            for index, token in enumerate(tokens, start=1):
                trips.append(
                    {
                        "tripId": f"miyazaki_airport:{code}:{direction_name}:{index:03d}",
                        "direction": direction_name,
                        "marks": token["marks"],
                        "stopTimes": [
                            {"stopName": stops[0], "time": token["time"], "raw": token["raw"]},
                            {"stopName": stops[1], "time": None, "raw": "arrival_time_not_published_on_summary_page"},
                        ],
                    }
                )
            directions.append({"direction": direction_name, "stops": stops, "trips": trips})
        routes.append(
            {
                "sourceKind": "official_miyazaki_airport_summary_timetable",
                "operatorName": "Miyazaki Kotsu",
                "airportIata": "KMI",
                "routeCode": code,
                "routeName": f"{terminal} ⇔ {AIRPORT_STOP_NAME}",
                "sourceUrl": SOURCE_URL,
                "directions": directions,
                "tripCount": sum(len(direction["trips"]) for direction in directions),
            }
        )
    return routes


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    html_text, cache_path = fetch_text(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    parser = TableParser()
    parser.feed(html_text)
    routes = parse_routes(parser.rows)
    source = {
        "schemaVersion": "v5_official_bus_source.miyazaki_airport.v1",
        "generatedAt": generated_at,
        "sourceUrl": SOURCE_URL,
        "sourceCachePath": str(cache_path.relative_to(ROOT)),
        "sourcePolicy": "Official Miyazaki Airport bus summary table. Departure times are real; arrival times and intermediate stop order are not invented when absent from the source page.",
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.miyazaki_airport.v1",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "tripCount": sum(route["tripCount"] for route in routes),
        "routes": [
            {
                "routeCode": route["routeCode"],
                "routeName": route["routeName"],
                "tripCount": route["tripCount"],
                "directionCounts": {direction["direction"]: len(direction["trips"]) for direction in route["directions"]},
                "status": "summary_departure_times_only",
            }
            for route in routes
        ],
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
