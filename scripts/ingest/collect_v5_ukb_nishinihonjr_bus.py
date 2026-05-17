#!/usr/bin/env python3
"""Collect Nishinihon JR Bus timetable rows that serve Kobe Airport (UKB)."""

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
from pathlib import Path
from typing import Any

from collect_v5_keikyu_haneda_bus import TableParser


ROOT = Path(__file__).resolve().parents[2]
SOURCE_URLS = [
    "https://timetable.nishinihonjrbus.co.jp/timeline/2-2-D-1Tokushima.html",
    "https://timetable.nishinihonjrbus.co.jp/timeline/2-2-D-2Kobe.html",
]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "ukb_nishinihonjr"
DEFAULT_OUTPUT = ROOT / "data" / "v5_ukb_nishinihonjr_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_ukb_nishinihonjr_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_ukb_nishinihonjr_official_bus_audit.json"


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


def parse_time(value: str) -> str | None:
    value = clean_text(value)
    if value in {"－", "-", "↓", "||", ""}:
        return None
    match = re.search(r"\d{1,2}:\d{2}", value)
    return match.group(0) if match else None


def route_title(html_text: str, fallback: str) -> str:
    title = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.S | re.I)
    if title:
        return clean_text(re.sub("<.*?>", " ", title.group(1)))
    return fallback


def parse_page(url: str, html_text: str, cache_path: Path) -> dict[str, Any]:
    parser = TableParser()
    parser.feed(html_text)
    rows = [row for row in parser.rows if row]
    operator_row = next((row for row in rows if row[0] == "運行会社"), [])
    service_name_row = next((row for row in rows if row[0] == "便名"), [])
    service_number_row = next((row for row in rows if row[0] == "号数"), [])
    stop_rows = [row for row in rows if row[0] not in {"運行会社", "便名", "号数", "運行情報"}]
    column_count = max((len(row) for row in rows), default=1)
    direction = "to_tokushima" if "1Tokushima" in url else "to_kobe"
    trips = []
    for col in range(1, column_count):
        stop_times = []
        for stop_row in stop_rows:
            if col >= len(stop_row):
                continue
            time = parse_time(stop_row[col])
            if time:
                stop_times.append({"stopName": clean_text(stop_row[0]), "time": time, "raw": stop_row[col]})
        if len(stop_times) >= 2 and any("神戸空港" in item["stopName"] or "Kobe Airport" in item["stopName"] for item in stop_times):
            service_number = service_number_row[col] if col < len(service_number_row) else ""
            trips.append(
                {
                    "tripId": f"ukb_nishinihonjr:{direction}:{col:03d}",
                    "direction": direction,
                    "operator": operator_row[col] if col < len(operator_row) else "",
                    "serviceName": service_name_row[col] if col < len(service_name_row) else "",
                    "serviceNumber": service_number,
                    "stopTimes": stop_times,
                }
            )
    return {
        "sourceUrl": url,
        "cachePath": str(cache_path.relative_to(ROOT)),
        "routeName": route_title(html_text, "Kobe Airport highway bus"),
        "direction": direction,
        "status": "ok" if trips else "no_ukb_trips",
        "tripCount": len(trips),
        "stopNames": sorted({item["stopName"] for trip in trips for item in trip["stopTimes"]}),
        "trips": trips,
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    pages = []
    for url in SOURCE_URLS:
        html_text, cache_path = fetch_text(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        pages.append(parse_page(url, html_text, cache_path))
    status_counts = Counter(page["status"] for page in pages)
    routes = [
        {
            "sourceKind": "official_nishinihonjr_html_timetable",
            "operatorName": "Nishinihon JR Bus",
            "airportIata": "UKB",
            "routeCode": "ukb_tokushima",
            "routeName": "神戸空港 ⇔ 徳島",
            "sourceUrls": SOURCE_URLS,
            "directions": [
                {"direction": page["direction"], "sourceUrl": page["sourceUrl"], "stopNames": page["stopNames"], "trips": page["trips"]}
                for page in pages
            ],
            "tripCount": sum(page["tripCount"] for page in pages),
        }
    ]
    source = {
        "schemaVersion": "v5_official_bus_source.ukb_nishinihonjr.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Nishinihon JR Bus HTML timetable rows serving Kobe Airport. Cells without times are not emitted.",
        "pages": pages,
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.ukb_nishinihonjr.v1",
        "generatedAt": generated_at,
        "pageCount": len(pages),
        "statusCounts": dict(sorted(status_counts.items())),
        "routeCount": len(routes),
        "tripCount": sum(route["tripCount"] for route in routes),
        "pages": [{k: page[k] for k in ["sourceUrl", "status", "tripCount", "direction"]} for page in pages],
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
    print(json.dumps({"routeCount": audit["routeCount"], "tripCount": audit["tripCount"], "statusCounts": audit["statusCounts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
