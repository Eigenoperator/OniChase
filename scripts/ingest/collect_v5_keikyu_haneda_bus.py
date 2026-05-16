#!/usr/bin/env python3
"""Collect official Keikyu/Haneda airport-bus timetable source data.

Keikyu publishes airport route metadata in ``/js/airport.js`` and timetable
fragments under ``/include*/timetable/*.html``.  This collector keeps the data
as official source/audit artifacts; conversion into the normalized gameplay bus
bundle is a later, explicit step so source overlap can be audited first.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
import urllib.error
from collections import Counter
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "https://www.keikyu-bus.co.jp"
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "keikyu_haneda"
DEFAULT_OUTPUT = ROOT / "data" / "v5_keikyu_haneda_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_keikyu_haneda_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_keikyu_haneda_official_bus_audit.json"

HANEDA_COORDS = {
    "羽田空港(第1)": (35.549393, 139.785097),
    "羽田空港(第１)": (35.549393, 139.785097),
    "羽田空港第1": (35.549393, 139.785097),
    "羽田空港第１": (35.549393, 139.785097),
    "羽田空港(第2)": (35.553333, 139.787778),
    "羽田空港(第２)": (35.553333, 139.787778),
    "羽田空港第2": (35.553333, 139.787778),
    "羽田空港第２": (35.553333, 139.787778),
    "羽田空港(第3)": (35.544830, 139.768560),
    "羽田空港(第３)": (35.544830, 139.768560),
    "羽田空港第3": (35.544830, 139.768560),
    "羽田空港第３": (35.544830, 139.768560),
}


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell_parts = []
        elif tag == "br" and self._cell_parts is not None:
            self._cell_parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell_parts is not None:
            text = html.unescape("".join(self._cell_parts))
            text = re.sub(r"\s+", " ", text).strip()
            self._row.append(text)
            self._cell_parts = None
        elif tag == "tr" and self._row is not None:
            if any(cell for cell in self._row):
                self.rows.append(self._row)
            self._row = None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    suffix = ".js" if url.endswith(".js") else ".html"
    return cache_dir / f"{digest}{suffix}"


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


def balanced_block(text: str, start_index: int, open_char: str, close_char: str) -> str:
    depth = 0
    quote: str | None = None
    escape = False
    for index in range(start_index, len(text)):
        char = text[index]
        if quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]
    return text[start_index:]


def parse_route_entries(js: str) -> list[dict[str, Any]]:
    entries = []
    seen_keys: set[str] = set()
    for match in re.finditer(r"'([^']+)'\s*:\s*\{", js):
        key = match.group(1)
        if not key.startswith("/airport/h-") or key in seen_keys:
            continue
        seen_keys.add(key)
        body = balanced_block(js, match.end() - 1, "{", "}")
        table_urls = []
        for table_match in re.finditer(r"'table\d+'\s*:\s*'([^']+)'", body):
            table_urls.append(urllib.parse.urljoin(BASE_URL, table_match.group(1)))
        bus_stops = []
        stop_pos = body.find("'bus_stop'")
        if stop_pos >= 0:
            bracket_pos = body.find("[", stop_pos)
            if bracket_pos >= 0:
                raw_array = balanced_block(body, bracket_pos, "[", "]")
                try:
                    parsed = ast.literal_eval(raw_array)
                except (SyntaxError, ValueError):
                    parsed = []
                for row in parsed:
                    if not row:
                        continue
                    lat = lon = None
                    if len(row) >= 3 and isinstance(row[2], str) and "," in row[2]:
                        parts = [part.strip() for part in row[2].split(",", 1)]
                        try:
                            lat = float(parts[0])
                            lon = float(parts[1])
                        except ValueError:
                            lat = lon = None
                    bus_stops.append(
                        {
                            "name": str(row[0]),
                            "mapTemplate": str(row[1]) if len(row) > 1 else "",
                            "lat": lat,
                            "lon": lon,
                            "zoom": str(row[3]) if len(row) > 3 else "",
                        }
                    )
        entries.append(
            {
                "routePath": key,
                "routeCode": key.strip("/").replace("/", "_"),
                "sourceUrl": urllib.parse.urljoin(BASE_URL, key),
                "tableUrls": sorted(set(table_urls)),
                "busStops": bus_stops,
            }
        )
    return entries


def normalize_name(value: str) -> str:
    text = re.sub(r"\s+", "", value)
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("第１", "第1").replace("第２", "第2").replace("第３", "第3")
    text = text.replace("「", "").replace("」", "").replace("®", "")
    return text


def coords_for_header(header: str, bus_stops: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    direct = HANEDA_COORDS.get(header)
    if direct:
        return direct
    normalized_header = normalize_name(header)
    for name, coords in HANEDA_COORDS.items():
        if normalize_name(name) in normalized_header:
            return coords
    for stop in bus_stops:
        lat = stop.get("lat")
        lon = stop.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        normalized_stop = normalize_name(stop["name"])
        if normalized_header in normalized_stop or normalized_stop in normalized_header:
            return float(lat), float(lon)
    return None, None


def parse_time(value: str) -> str | None:
    cleaned = re.sub(r"[^\d:]", "", value)
    if re.fullmatch(r"\d{1,2}:\d{2}", cleaned):
        return cleaned
    return None


def parse_timetable(html_text: str, table_url: str, route: dict[str, Any], table_index: int) -> dict[str, Any]:
    parser = TableParser()
    parser.feed(html_text)
    rows = parser.rows
    header = next((row[1:] for row in rows if len(row) >= 2 and any("羽田空港" in cell for cell in row)), [])
    trip_rows = [row for row in rows if len(row) >= 2 and any(parse_time(cell) for cell in row[1:])]
    stops = []
    for index, name in enumerate(header):
        lat, lon = coords_for_header(name, route["busStops"])
        stops.append({"index": index, "name": name, "lat": lat, "lon": lon})
    trips = []
    for row_index, row in enumerate(trip_rows, start=1):
        operator = row[0]
        stop_times = []
        for stop, cell in zip(stops, row[1:]):
            time = parse_time(cell)
            if not time:
                continue
            stop_times.append(
                {
                    "stopIndex": stop["index"],
                    "stopName": stop["name"],
                    "time": time,
                    "raw": cell,
                }
            )
        if len(stop_times) >= 2:
            trips.append(
                {
                    "tripId": f"keikyu_haneda:{route['routeCode']}:table{table_index}:{row_index:03d}",
                    "operator": operator,
                    "stopTimes": stop_times,
                }
            )
    status = "ok" if trips and len(stops) >= 2 else "no_parseable_trips"
    return {
        "tableUrl": table_url,
        "status": status,
        "stops": stops,
        "trips": trips,
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    js_url = f"{BASE_URL}/js/airport.js"
    js, js_cache = fetch_text(js_url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    route_entries = parse_route_entries(js)
    routes = []
    for route in route_entries:
        timetables = []
        for index, table_url in enumerate(route["tableUrls"], start=1):
            try:
                html_text, cache_path = fetch_text(table_url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
                parsed = parse_timetable(html_text, table_url, route, index)
                parsed["cachePath"] = str(cache_path.relative_to(ROOT))
            except (OSError, urllib.error.URLError) as exc:
                parsed = {
                    "tableUrl": table_url,
                    "status": "fetch_error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "stops": [],
                    "trips": [],
                }
            timetables.append(parsed)
        trip_count = sum(len(table["trips"]) for table in timetables)
        route_stop_names = sorted({stop["name"] for table in timetables for stop in table["stops"]})
        routes.append(
            {
                "sourceKind": "official_keikyu_airport_js_timetable",
                "operatorName": "Keikyu Bus",
                "airportIata": "HND",
                "routePath": route["routePath"],
                "routeCode": route["routeCode"],
                "sourceUrl": route["sourceUrl"],
                "busStops": route["busStops"],
                "timetables": timetables,
                "routeStopNames": route_stop_names,
                "tripCount": trip_count,
            }
        )
    status_counts = Counter()
    for route in routes:
        status_counts["ok" if route["tripCount"] else "no_parseable_trips"] += 1
    source = {
        "schemaVersion": "v5_official_bus_source.keikyu_haneda.v1",
        "generatedAt": generated_at,
        "sourceJsUrl": js_url,
        "sourceJsCachePath": str(js_cache.relative_to(ROOT)),
        "sourcePolicy": "Official Keikyu Bus airport route JavaScript index and official timetable HTML fragments. No estimated timetable rows.",
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.keikyu_haneda.v1",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "okRouteCount": status_counts["ok"],
        "tripCount": sum(route["tripCount"] for route in routes),
        "statusCounts": dict(sorted(status_counts.items())),
        "routes": [
            {
                "routeCode": route["routeCode"],
                "sourceUrl": route["sourceUrl"],
                "tableCount": len(route["timetables"]),
                "tripCount": route["tripCount"],
                "stopNameCount": len(route["routeStopNames"]),
                "status": "ok" if route["tripCount"] else "no_parseable_trips",
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
    print(json.dumps({"routeCount": audit["routeCount"], "okRouteCount": audit["okRouteCount"], "tripCount": audit["tripCount"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
