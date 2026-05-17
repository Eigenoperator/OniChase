#!/usr/bin/env python3
"""Collect Hankyu Kanko Bus official Osaka Itami Airport limousine timetables."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from collect_v5_keikyu_haneda_bus import TableParser


ROOT = Path(__file__).resolve().parents[2]
ROUTE_CODES = ["ITM", "S", "U", "N", "A", "E", "Y", "T", "K", "H", "B", "M", "J"]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "itm_hankyu_kanko"
DEFAULT_OUTPUT = ROOT / "data" / "v5_itm_hankyu_kanko_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_itm_hankyu_kanko_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_itm_hankyu_kanko_official_bus_audit.json"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def route_url(code: str) -> str:
    return f"https://www.hankyu-kankobus.co.jp/limousine/timetable/{code}/"


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


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_time(value: str) -> str | None:
    match = re.search(r"\d{1,2}:\d{2}", str(value or ""))
    return match.group(0) if match else None


def parse_fare(row: list[str]) -> dict[str, int] | None:
    text = "".join(row)
    adult = re.search(r"大人\s*(\d+)円", text)
    child = re.search(r"小児\s*(\d+)円", text)
    if adult:
        return {"adultFareYen": int(adult.group(1)), "childFareYen": int(child.group(1)) if child else 0}
    return None


def direction_from_stops(stops: list[str]) -> str:
    if stops and "発大阪（伊丹）空港" in stops[0]:
        return "from_airport"
    if stops and any("着大阪(伊丹)空港" in stop or "着大阪（伊丹）空港" in stop for stop in stops[-2:]):
        return "to_airport"
    return "unknown"


def strip_stop_label(value: str) -> str:
    text = clean(value)
    text = re.sub(r"^[A-Z0-9]+", "", text)
    text = text.replace("のりば", "").replace("おりば", "")
    text = text.replace("発", "").replace("着", "")
    return text


def route_title(html_text: str, fallback: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.S | re.I)
    if not match:
        return fallback
    title = re.sub("<.*?>", " ", match.group(1))
    return clean(title.split("|")[0])


def parse_page(code: str, url: str, html_text: str, cache_path: Path) -> dict[str, Any]:
    parser = TableParser()
    parser.feed(html_text)
    sections: list[dict[str, Any]] = []
    current_header: list[str] | None = None
    current_fare: dict[str, int] | None = None
    current_rows: list[list[str]] = []

    def flush() -> None:
        nonlocal current_header, current_fare, current_rows
        if not current_header:
            return
        stop_headers = current_header[2:]
        stops = [strip_stop_label(stop) for stop in stop_headers]
        direction = direction_from_stops(current_header[2:])
        trips = []
        for row_index, row in enumerate(current_rows, start=1):
            operator = clean(row[0]) if row else ""
            stop_times = []
            for stop, cell in zip(stops, row[2:]):
                time = parse_time(cell)
                if time:
                    stop_times.append({"stopName": stop, "time": time, "raw": cell})
            if len(stop_times) >= 2:
                trips.append(
                    {
                        "tripId": f"itm_hankyu:{code}:{direction}:{len(sections) + 1:02d}:{row_index:03d}",
                        "direction": direction,
                        "operatorCode": operator,
                        "stopTimes": stop_times,
                    }
                )
        if trips:
            sections.append(
                {
                    "direction": direction,
                    "stops": stops,
                    "fare": current_fare or {},
                    "tripCount": len(trips),
                    "trips": trips,
                }
            )
        current_header = None
        current_fare = None
        current_rows = []

    for row in parser.rows:
        if not row:
            continue
        if row[0].startswith("運行") and len(row) >= 4:
            flush()
            current_header = row
            current_rows = []
            current_fare = None
        elif current_header and parse_fare(row):
            current_fare = parse_fare(row)
        elif current_header and sum(1 for cell in row if parse_time(cell)) >= 2:
            current_rows.append(row)
    flush()

    title = route_title(html_text, code)
    return {
        "sourceKind": "official_hankyu_kanko_html_timetable",
        "operatorName": "阪急観光バス",
        "airportIata": "ITM",
        "routeCode": f"itm_hankyu_{code.lower()}",
        "routeName": f"大阪（伊丹）空港 ⇔ {title}",
        "sourceUrl": url,
        "cachePath": str(cache_path.relative_to(ROOT)),
        "directions": sections,
        "routeStopNames": sorted({stop for section in sections for stop in section["stops"]}),
        "tripCount": sum(section["tripCount"] for section in sections),
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    routes = []
    pages = []
    for code in args.route_codes:
        url = route_url(code)
        try:
            html_text, cache_path = fetch_text(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
            route = parse_page(code, url, html_text, cache_path)
            status = "ok" if route["tripCount"] else "no_trips"
            routes.append(route)
            pages.append({"routeCode": route["routeCode"], "sourceUrl": url, "cachePath": str(cache_path.relative_to(ROOT)), "status": status, "tripCount": route["tripCount"]})
        except OSError as exc:
            pages.append({"routeCode": f"itm_hankyu_{code.lower()}", "sourceUrl": url, "status": "fetch_error", "error": f"{type(exc).__name__}: {exc}", "tripCount": 0})
    status_counts = Counter(page["status"] for page in pages)
    source = {
        "schemaVersion": "v5_official_bus_source.itm_hankyu_kanko.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Hankyu Kanko Bus HTML timetable pages for Osaka Itami Airport limousine routes. Parsed rows preserve published stop order and fare text where present.",
        "routes": routes,
        "pages": pages,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.itm_hankyu_kanko.v1",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "tripCount": sum(route["tripCount"] for route in routes),
        "statusCounts": dict(sorted(status_counts.items())),
        "pages": pages,
        "routes": [{"routeCode": route["routeCode"], "directionCount": len(route["directions"]), "tripCount": route["tripCount"], "stopCount": len(route["routeStopNames"])} for route in routes],
    }
    return source, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--route-codes", nargs="*", default=ROUTE_CODES)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    source, audit = collect(args)
    write_json(args.output, source)
    write_json(args.docs_output, source)
    write_json(args.audit_output, audit)
    print(json.dumps({"routeCount": audit["routeCount"], "tripCount": audit["tripCount"], "statusCounts": audit["statusCounts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
