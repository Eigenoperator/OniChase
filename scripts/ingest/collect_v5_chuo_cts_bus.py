#!/usr/bin/env python3
"""Collect official Hokkaido Chuo Bus New Chitose airport-bus timetables."""

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
INDEX_URL = "https://www.chuo-bus.co.jp/airport.en/"
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "chuo_cts"
DEFAULT_OUTPUT = ROOT / "data" / "v5_chuo_cts_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_chuo_cts_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_chuo_cts_official_bus_audit.json"


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


def parse_index(html_text: str) -> list[dict[str, str]]:
    routes = []
    seen: set[str] = set()
    for match in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", html_text, re.S):
        href = html.unescape(match.group(1))
        if "timetable" not in href:
            continue
        label = re.sub("<.*?>", " ", match.group(2))
        label = re.sub(r"\s+", " ", html.unescape(label)).strip()
        url = urllib.parse.urljoin(INDEX_URL, href)
        if url in seen:
            continue
        seen.add(url)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        routes.append(
            {
                "routeName": label,
                "direction": "to_cts" if query.get("o", [""])[0] == "1" else "from_cts",
                "routeNumber": query.get("n", [""])[0],
                "sourceUrl": url,
            }
        )
    return routes


def parse_time(value: str) -> str | None:
    cleaned = re.sub(r"[^\d:]", "", value)
    if re.fullmatch(r"\d{1,2}:\d{2}", cleaned):
        return cleaned
    return None


def clean_stop_name(value: str) -> str:
    text = re.sub(r"\[MAP\]", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_timetable(html_text: str, route: dict[str, str], cache_path: Path) -> dict[str, Any]:
    parser = TableParser()
    parser.feed(html_text)
    rows = [row for row in parser.rows if len(row) >= 3]
    header = next((row for row in rows if row[0] == "Cat." or "Operator" in row[1]), [])
    stop_rows = [row for row in rows if row and row[0] != "Cat." and any(parse_time(cell) for cell in row[2:])]
    trip_count = max((len(row) for row in rows), default=0) - 2
    trips = []
    for col in range(2, max(2, trip_count + 2)):
        stop_times = []
        operator = header[col] if col < len(header) else ""
        for row in stop_rows:
            if col >= len(row):
                continue
            time = parse_time(row[col])
            if not time:
                continue
            stop_times.append(
                {
                    "stopName": clean_stop_name(row[1]),
                    "category": row[0],
                    "time": time,
                    "raw": row[col],
                }
            )
        if len(stop_times) >= 2:
            trips.append(
                {
                    "tripId": f"chuo_cts:{route['routeNumber']}:{route['direction']}:{col - 1:03d}",
                    "operator": operator,
                    "stopTimes": stop_times,
                }
            )
    status = "ok" if trips else "no_parseable_trips"
    return {
        "sourceUrl": route["sourceUrl"],
        "cachePath": str(cache_path.relative_to(ROOT)),
        "status": status,
        "routeName": route["routeName"],
        "direction": route["direction"],
        "routeNumber": route["routeNumber"],
        "tripCount": len(trips),
        "stopNames": sorted({item["stopName"] for trip in trips for item in trip["stopTimes"]}),
        "trips": trips,
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    index_html, index_cache = fetch_text(INDEX_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    route_refs = parse_index(index_html)
    routes = []
    for route in route_refs:
        html_text, cache_path = fetch_text(route["sourceUrl"], args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        routes.append(parse_timetable(html_text, route, cache_path))
    status_counts = Counter(route["status"] for route in routes)
    source = {
        "schemaVersion": "v5_official_bus_source.chuo_cts.v1",
        "generatedAt": generated_at,
        "sourceIndexUrl": INDEX_URL,
        "sourceIndexCachePath": str(index_cache.relative_to(ROOT)),
        "sourcePolicy": "Official Hokkaido Chuo Bus New Chitose Airport timetable pages. No estimated timetable rows.",
        "operatorName": "Hokkaido Chuo Bus",
        "airportIata": "CTS",
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.chuo_cts.v1",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "okRouteCount": status_counts["ok"],
        "tripCount": sum(route["tripCount"] for route in routes),
        "statusCounts": dict(sorted(status_counts.items())),
        "routes": [
            {
                "routeName": route["routeName"],
                "direction": route["direction"],
                "sourceUrl": route["sourceUrl"],
                "status": route["status"],
                "tripCount": route["tripCount"],
                "stopNameCount": len(route["stopNames"]),
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
