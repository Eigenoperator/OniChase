#!/usr/bin/env python3
"""Collect KIX limousine bus timetables from the official KATE website."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "kate"
DEFAULT_OUTPUT = ROOT / "data" / "v5_kate_official_airport_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_kate_official_airport_bus_source.json"
DEFAULT_AUDIT = ROOT / "data" / "v5_kate_official_airport_bus_audit.json"
DEFAULT_LIST_URL = "https://www.kate.co.jp/en/timetable/"
BASE_URL = "https://www.kate.co.jp"
TIME_RE = re.compile(r"(?:[※◆]?\s*)?(\d{1,2}:\d{2})")
FARE_RE = re.compile(r"([0-9][0-9,]*)\s*Yen", re.IGNORECASE)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_text(url: str, cache_dir: Path, *, refresh: bool = False) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    cache_path = cache_dir / f"{cache_key}.html"
    if cache_path.exists() and not refresh:
        return cache_path.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={"User-Agent": "OniChase-v5-kate-bus-collector/0.1"})
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read()
    text = raw.decode("utf-8", "replace")
    cache_path.write_text(text, encoding="utf-8")
    return text


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[dict[str, Any]] = []
        self.in_table = False
        self.table_depth = 0
        self.current_table: dict[str, Any] | None = None
        self.current_row: list[dict[str, str]] | None = None
        self.current_cell: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        if tag == "table":
            classes = set((attrs_dict.get("class") or "").split())
            if "timetable" in classes:
                self.in_table = True
                self.table_depth = 1
                self.current_table = {"rows": []}
                return
            if self.in_table:
                self.table_depth += 1
        elif self.in_table and tag == "tr":
            self.current_row = []
        elif self.in_table and tag in {"td", "th"}:
            self.current_cell = {"tag": tag, "text": ""}

    def handle_endtag(self, tag: str) -> None:
        if not self.in_table:
            return
        if tag in {"td", "th"} and self.current_cell is not None and self.current_row is not None:
            self.current_cell["text"] = clean_text(self.current_cell["text"])
            self.current_row.append(self.current_cell)
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None and self.current_table is not None:
            if any(cell["text"] for cell in self.current_row):
                self.current_table["rows"].append(self.current_row)
            self.current_row = None
        elif tag == "table":
            self.table_depth -= 1
            if self.table_depth <= 0:
                if self.current_table is not None:
                    self.tables.append(self.current_table)
                self.in_table = False
                self.current_table = None

    def handle_data(self, data: str) -> None:
        if self.in_table and self.current_cell is not None:
            self.current_cell["text"] += data


def extract_detail_links(list_html: str) -> list[dict[str, str]]:
    rows = []
    seen = set()
    for href, code, label in re.findall(r'<a\s+href="(/en/timetable/detail/([A-Za-z0-9]+))"[^>]*>(.*?)</a>', list_html, flags=re.S):
        text = clean_text(re.sub(r"<.*?>", "", label))
        if code in seen:
            continue
        seen.add(code)
        rows.append({"code": code, "label": text or code, "url": BASE_URL + href})
    return rows


def extract_route_title(page_html: str, fallback: str) -> str:
    match = re.search(r"<h2>(.*?)</h2>", page_html, flags=re.S | re.I)
    if not match:
        return fallback
    text = clean_text(re.sub(r"<.*?>", " ", match.group(1)))
    return text or fallback


def parse_header_cell(text: str, index: int) -> dict[str, Any]:
    code_match = re.search(r"\b([A-Z]{2,5}\d{0,2}|KIX|SKYB\d*)\b", text)
    code = code_match.group(1) if code_match else f"STOP{index + 1}"
    label = text
    for token in [code, "Pick up point", "Drop off point"]:
        label = label.replace(token, " ")
    label = clean_text(label)
    return {"code": code, "name": label or code}


def normalize_time_cell(text: str) -> tuple[str | None, dict[str, Any]]:
    text = clean_text(text)
    if not text or "→" in text:
        return None, {"raw": text, "skipped": True}
    match = TIME_RE.search(text)
    if not match:
        return None, {"raw": text, "skipped": True}
    marks = []
    if "※" in text:
        marks.append("note")
    if "◆" in text:
        marks.append("late_night")
    return match.group(1), {"raw": text, "marks": marks}


def parse_timetable_table(table: dict[str, Any], route_code: str, direction_index: int) -> dict[str, Any] | None:
    rows = table.get("rows") or []
    header_row = next((row for row in rows if row and all(cell["tag"] == "th" for cell in row)), None)
    if not header_row:
        return None
    stops = [parse_header_cell(cell["text"], index) for index, cell in enumerate(header_row)]
    trips = []
    trip_index = 1
    for row in rows:
        if not row or not all(cell["tag"] == "td" for cell in row):
            continue
        if len(row) < 2:
            continue
        stop_times = []
        for index, cell in enumerate(row[: len(stops)]):
            time_text, meta = normalize_time_cell(cell["text"])
            if not time_text:
                continue
            stop_times.append({"stopCode": stops[index]["code"], "time": time_text, "raw": meta["raw"], "marks": meta.get("marks", [])})
        if len(stop_times) < 2:
            continue
        trips.append(
            {
                "tripId": f"kate:{route_code}:dir{direction_index}:{trip_index:03d}",
                "directionIndex": direction_index,
                "stopTimes": stop_times,
            }
        )
        trip_index += 1
    return {"directionIndex": direction_index, "stops": stops, "trips": trips}


def extract_fares(page_html: str) -> list[dict[str, Any]]:
    text = clean_text(re.sub(r"<.*?>", " ", page_html))
    if "Fares" not in text:
        return []
    fare_text = text.split("Fares", 1)[-1][:2500]
    values = [int(value.replace(",", "")) for value in FARE_RE.findall(fare_text)]
    unique = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return [{"currency": "JPY", "amountYen": value, "rawContext": "official KATE fare text"} for value in unique[:12]]


def collect_route(link: dict[str, str], cache_dir: Path, refresh: bool) -> dict[str, Any]:
    page_html = fetch_text(link["url"], cache_dir, refresh=refresh)
    parser = TableParser()
    parser.feed(page_html)
    route_code = link["code"]
    directions = []
    for direction_index, table in enumerate(parser.tables[:2]):
        direction = parse_timetable_table(table, route_code, direction_index)
        if direction:
            directions.append(direction)
    route_title = extract_route_title(page_html, link["label"])
    return {
        "sourceKind": "official_kate_static_timetable",
        "operatorName": "Kansai Airport Transportation Enterprise",
        "airportIata": "KIX",
        "routeCode": route_code,
        "routeName": route_title,
        "sourceUrl": link["url"],
        "directions": directions,
        "fares": extract_fares(page_html),
        "status": "ok" if sum(len(direction["trips"]) for direction in directions) > 0 else "no_active_timetable_rows",
        "tripCount": sum(len(direction["trips"]) for direction in directions),
        "stopCount": len({stop["code"] for direction in directions for stop in direction["stops"]}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-url", default=DEFAULT_LIST_URL)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--refresh-cache", action="store_true")
    args = parser.parse_args()

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    list_html = fetch_text(args.list_url, args.cache_dir, refresh=args.refresh_cache)
    links = extract_detail_links(list_html)
    routes = [collect_route(link, args.cache_dir, args.refresh_cache) for link in links]
    payload = {
        "schemaVersion": "v5_official_bus_source.kate.v1",
        "generatedAt": generated_at,
        "source": {
            "name": "Kansai Airport Transportation Enterprise",
            "baseUrl": BASE_URL,
            "listUrl": args.list_url,
            "sourcePolicy": "Official KATE static timetable pages; extracted as source data before merge/dedup with GTFS.",
        },
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.kate.v1",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "okRouteCount": sum(1 for route in routes if route["status"] == "ok"),
        "tripCount": sum(route["tripCount"] for route in routes),
        "routes": [
            {
                "routeCode": route["routeCode"],
                "routeName": route["routeName"],
                "status": route["status"],
                "tripCount": route["tripCount"],
                "stopCount": route["stopCount"],
                "sourceUrl": route["sourceUrl"],
            }
            for route in routes
        ],
    }
    write_json(args.output, payload)
    write_json(args.docs_output, payload)
    write_json(args.audit_output, audit)
    print(json.dumps({k: audit[k] for k in ["routeCount", "okRouteCount", "tripCount"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
