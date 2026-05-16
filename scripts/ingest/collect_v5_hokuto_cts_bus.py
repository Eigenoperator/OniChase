#!/usr/bin/env python3
"""Collect official Hokuto Kotsu New Chitose airport-bus timetables."""

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
INDEX_URL = "https://www.hokkaido-airports.com/en/new-chitose/access/bus/"
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "hokuto_cts"
DEFAULT_OUTPUT = ROOT / "data" / "v5_hokuto_cts_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_hokuto_cts_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_hokuto_cts_official_bus_audit.json"


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


def plain(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_index(html_text: str) -> list[dict[str, str]]:
    routes = []
    seen: set[str] = set()
    for match in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", html_text, re.S):
        url = urllib.parse.urljoin(INDEX_URL, html.unescape(match.group(1)))
        if "hokto.co.jp" not in urllib.parse.urlparse(url).netloc or url in seen:
            continue
        label = re.sub("<.*?>", " ", match.group(2))
        label = plain(label)
        if "chitose" not in url:
            continue
        routes.append({"routeName": label or urllib.parse.urlparse(url).path.strip("/"), "sourceUrl": url})
        seen.add(url)
    return routes


def route_title(html_text: str, fallback: str) -> str:
    headings = []
    for match in re.finditer(r"<h[1-4][^>]*>(.*?)</h[1-4]>", html_text, re.S):
        text = plain(re.sub("<.*?>", " ", match.group(1)))
        if "新千歳空港" in text or "Chitose" in text:
            headings.append(text)
    return headings[-1] if headings else fallback


def parse_time(value: str) -> str | None:
    cleaned = re.sub(r"[^\d:]", "", value)
    if re.fullmatch(r"\d{1,2}:\d{2}", cleaned):
        return cleaned
    return None


def is_stop_header(row: list[str]) -> bool:
    return len(row) == 1 and row[0] == "停留所名"


def is_meta_single(row: list[str]) -> bool:
    if len(row) != 1:
        return False
    value = row[0]
    return value in {"運行会社", "便名", "乗", "降", "↓", "-", "–"} or bool(re.fullmatch(r"\d+分", value))


def looks_like_operator_row(row: list[str]) -> bool:
    if len(row) < 2:
        return False
    cells = [cell for cell in row if cell]
    if not cells:
        return False
    short = sum(1 for cell in cells if re.fullmatch(r"[A-Z0-9]+", cell))
    return short >= max(1, len(cells) // 2) and not any(parse_time(cell) for cell in row)


def parse_segments(rows: list[list[str]], route_code: str) -> list[dict[str, Any]]:
    segments = []
    index = 0
    segment_index = 0
    while index < len(rows):
        if not is_stop_header(rows[index]):
            index += 1
            continue
        index += 1
        stops = []
        while index < len(rows) and len(rows[index]) == 1 and not is_meta_single(rows[index]):
            stops.append(rows[index][0])
            index += 1
        while index < len(rows) and len(rows[index]) == 1:
            index += 1
        if not stops or index >= len(rows):
            continue
        operator_row = rows[index] if looks_like_operator_row(rows[index]) else ["" for _ in range(max(len(rows[index]), 1))]
        if looks_like_operator_row(rows[index]):
            index += 1
        time_rows = []
        while index < len(rows) and not is_stop_header(rows[index]):
            row = rows[index]
            if len(row) >= 2 and (any(parse_time(cell) for cell in row) or any(cell in {"↓", "-", "–"} for cell in row)):
                time_rows.append(row)
            index += 1
        if not time_rows:
            continue
        segment_index += 1
        column_count = max(len(operator_row), *(len(row) for row in time_rows))
        trips = []
        for col in range(column_count):
            stop_times = []
            for stop_name, row in zip(stops, time_rows):
                if col >= len(row):
                    continue
                time = parse_time(row[col])
                if not time:
                    continue
                stop_times.append({"stopName": stop_name, "time": time, "raw": row[col]})
            if len(stop_times) >= 2:
                trips.append(
                    {
                        "tripId": f"hokuto_cts:{route_code}:seg{segment_index}:{col + 1:03d}",
                        "operator": operator_row[col] if col < len(operator_row) else "",
                        "stopTimes": stop_times,
                    }
                )
        segments.append({"segmentIndex": segment_index, "stops": stops, "trips": trips})
    return segments


def route_code_for(url: str) -> str:
    path = urllib.parse.urlparse(url).path.strip("/").replace("/", "_")
    return re.sub(r"[^A-Za-z0-9_-]+", "_", path) or "hokuto_cts"


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    index_html, index_cache = fetch_text(INDEX_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    refs = parse_index(index_html)
    routes = []
    for ref in refs:
        html_text, cache_path = fetch_text(ref["sourceUrl"], args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        parser = TableParser()
        parser.feed(html_text)
        route_code = route_code_for(ref["sourceUrl"])
        segments = parse_segments(parser.rows, route_code)
        trip_count = sum(len(segment["trips"]) for segment in segments)
        routes.append(
            {
                "sourceKind": "official_hokuto_cts_static_timetable",
                "operatorName": "Hokuto Kotsu",
                "airportIata": "CTS",
                "routeCode": route_code,
                "routeName": route_title(html_text, ref["routeName"]),
                "sourceUrl": ref["sourceUrl"],
                "cachePath": str(cache_path.relative_to(ROOT)),
                "status": "ok" if trip_count else "no_parseable_trips",
                "segmentCount": len(segments),
                "tripCount": trip_count,
                "segments": segments,
            }
        )
    status_counts = Counter(route["status"] for route in routes)
    source = {
        "schemaVersion": "v5_official_bus_source.hokuto_cts.v1",
        "generatedAt": generated_at,
        "sourceIndexUrl": INDEX_URL,
        "sourceIndexCachePath": str(index_cache.relative_to(ROOT)),
        "sourcePolicy": "Official Hokuto Kotsu New Chitose Airport timetable pages. No estimated timetable rows.",
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.hokuto_cts.v1",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "okRouteCount": status_counts["ok"],
        "tripCount": sum(route["tripCount"] for route in routes),
        "statusCounts": dict(sorted(status_counts.items())),
        "routes": [
            {
                "routeCode": route["routeCode"],
                "routeName": route["routeName"],
                "sourceUrl": route["sourceUrl"],
                "status": route["status"],
                "segmentCount": route["segmentCount"],
                "tripCount": route["tripCount"],
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
