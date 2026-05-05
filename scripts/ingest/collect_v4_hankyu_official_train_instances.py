#!/usr/bin/env python3
"""Collect v4 weekday train instances from Hankyu official station timetables."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collect_v4_gtfs_train_instances import V4StationMatcher, load_json, normalize_name_variants, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_LINE_INVENTORY = ROOT / "data" / "v4_nationwide_line_inventory.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_hankyu_official_cache"
DEFAULT_OUTPUT = ROOT / "data" / "v4_hankyu_official_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_hankyu_official_train_instances_audit.json"
DEFAULT_SERVICE_DATE = "2026-04-27"

BASE = "https://www.hankyu.co.jp"
STATION_INDEX_URL = f"{BASE}/station/index.html"
OPERATOR_NAME = "阪急電鉄"
SOURCE_FEED_KEY = "hankyu_official_station_timetable"

THROUGH_HINTS = [
    ("大阪市高速電気軌道", "6号線(堺筋線)"),
    ("阪神電気鉄道", "神戸高速線"),
    ("神戸電鉄", "神戸高速線"),
    ("山陽電気鉄道", "本線"),
    ("山陽電気鉄道", "網干線"),
    ("能勢電鉄", "妙見線"),
    ("能勢電鉄", "日生線"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cache_path(cache_dir: Path, namespace: str, key: str, suffix: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return cache_dir / namespace / f"{digest}{suffix}"


def ascii_url(url: str) -> str:
    return urllib.parse.quote(url, safe=":/?&=%#,+")


def fetch_text_cached(url: str, cache_dir: Path, namespace: str, refresh: bool, timeout: int = 90) -> str:
    url = ascii_url(url)
    path = cache_path(cache_dir, namespace, url, ".html")
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8", errors="replace")
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,*/*",
            "User-Agent": "Mozilla/5.0 (compatible; OniChase-v4-hankyu-official-collector/0.1)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    text = raw.decode(charset, errors="replace")
    path.write_text(text, encoding="utf-8")
    return text


def strip_tags(value: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", value or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_station_name(value: str) -> str:
    text = strip_tags(value)
    text = re.sub(r"駅$", "", text)
    text = re.sub(r"\(阪急\)$", "", text)
    text = re.sub(r"（阪急）$", "", text)
    return text.strip()


def minutes(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    hour_text, minute_text = value.split(":", 1)
    total = int(hour_text) * 60 + int(minute_text)
    if total < 3 * 60:
        total += 24 * 60
    return total


def load_physical_map(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


class HankyuPhysicalIndex:
    def __init__(self, physical_map: dict[str, Any], line_inventory: dict[str, Any]) -> None:
        self.matcher = V4StationMatcher(physical_map)
        self.station_by_id = {station["id"]: station for station in physical_map["physicalStations"]}
        self.line_id_by_operator_line: dict[tuple[str, str], str] = {}
        self.line_color_by_operator_line: dict[tuple[str, str], str] = {}
        self.hankyu_lines: set[str] = set()
        self.hankyu_station_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for line in line_inventory.get("lines", []):
            operator_name = str(line.get("operatorName") or "")
            line_name = str(line.get("lineName") or "")
            self.line_id_by_operator_line[(operator_name, line_name)] = str(line.get("id") or line_name)
            self.line_color_by_operator_line[(operator_name, line_name)] = str(
                line.get("lineColor") or line.get("operatorColor") or "#6B352A"
            ).lstrip("#")
            if operator_name == OPERATOR_NAME:
                self.hankyu_lines.add(line_name)
        for station in physical_map.get("physicalStations", []):
            if station.get("operatorName") != OPERATOR_NAME:
                continue
            for key in normalize_name_variants(station.get("nameJa") or ""):
                self.hankyu_station_by_name[key].append(station)

    def line_id(self, operator_name: str, line_name: str) -> str:
        return self.line_id_by_operator_line.get((operator_name, line_name)) or line_name

    def route_color(self, operator_name: str, line_name: str) -> str:
        return self.line_color_by_operator_line.get((operator_name, line_name), "#6B352A").lstrip("#")

    def station_for_match(self, match: dict[str, Any]) -> dict[str, Any] | None:
        station_id = match.get("physicalStationId")
        if not station_id:
            return None
        return self.station_by_id.get(str(station_id))

    def hankyu_candidates(self, station_name: str) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for key in normalize_name_variants(station_name):
            for station in self.hankyu_station_by_name.get(key, []):
                station_id = str(station.get("id") or "")
                if station_id in seen:
                    continue
                seen.add(station_id)
                output.append(station)
        return output

    def match_stop(self, station_name: str, source_line_name: str | None, previous_line_name: str | None) -> dict[str, Any]:
        cleaned = clean_station_name(station_name)
        candidates = self.hankyu_candidates(cleaned)
        if candidates:
            ranked = sorted(
                candidates,
                key=lambda station: (
                    0 if source_line_name and station.get("lineName") == source_line_name else 1,
                    0 if previous_line_name and station.get("lineName") == previous_line_name else 1,
                    str(station.get("lineName") or ""),
                    str(station.get("stationGroupId") or ""),
                ),
            )
            best = ranked[0]
            return {
                "matched": True,
                "method": "hankyu_name_context",
                "stationGroupId": best["stationGroupId"],
                "physicalStationId": best["id"],
                "candidateCount": len(candidates),
            }
        for operator_name, line_name in THROUGH_HINTS:
            match = self.matcher.match(
                operator_name=operator_name,
                line_name=line_name,
                stop_name=cleaned,
                stop_lat=None,
                stop_lon=None,
            )
            if match.get("matched"):
                match["method"] = f"through_{operator_name}_{line_name}_{match['method']}"
                return match
        return self.matcher.match(
            operator_name=OPERATOR_NAME,
            line_name=source_line_name,
            stop_name=cleaned,
            stop_lat=None,
            stop_lon=None,
        )


def extract_station_page_links(index_html: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"""href\s*=\s*["'](/station/[^"']+\.html)["']""", index_html, flags=re.IGNORECASE):
        href = html.unescape(match.group(1))
        if href in {"/station/index.html", "/station/info.html"}:
            continue
        if "/station/html/" in href or href.endswith("_map.html"):
            continue
        url = urllib.parse.urljoin(BASE, href)
        if url not in seen:
            seen.add(url)
            links.append(url)
    return links


def extract_weekday_timetable_links(station_html: str, station_url: str) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", station_html, flags=re.IGNORECASE | re.DOTALL)
    page_station = clean_station_name(h1_match.group(1).split("|")[0] if h1_match else "")
    pattern = re.compile(
        r"""<div\s+class=["']timetable_cnt["'][^>]*>\s*<h4>(?P<line>.*?)</h4>(?P<body>.*?)(?=<div\s+class=["']timetable_cnt["']|</div>\s*</div>\s*</div>)""",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for block in pattern.finditer(station_html):
        line_name = strip_tags(block.group("line"))
        body = block.group("body")
        for href_match in re.finditer(r"""href\s*=\s*["'](?P<href>/station/html/[^"']+_w\.html)["']""", body, flags=re.IGNORECASE):
            href = html.unescape(href_match.group("href"))
            url = urllib.parse.urljoin(BASE, href)
            if "/station/html/20250222/" in url:
                continue
            if url in seen:
                continue
            seen.add(url)
            output.append({"url": url, "stationName": page_station, "lineName": line_name})
    if not output:
        for href_match in re.finditer(r"""href\s*=\s*["'](?P<href>/station/html/[^"']+_w\.html)["']""", station_html, flags=re.IGNORECASE):
            href = html.unescape(href_match.group("href"))
            url = urllib.parse.urljoin(BASE, href)
            if "/station/html/20250222/" in url:
                continue
            if url in seen:
                continue
            seen.add(url)
            output.append({"url": url, "stationName": page_station, "lineName": ""})
    return output


def parse_timetable_page(page_html: str, page_url: str, fallback_line_name: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    title = strip_tags(re.search(r"<title>(.*?)</title>", page_html, flags=re.IGNORECASE | re.DOTALL).group(1)) if re.search(r"<title>(.*?)</title>", page_html, flags=re.IGNORECASE | re.DOTALL) else ""
    h1 = strip_tags(re.search(r"<h1[^>]*>(.*?)</h1>", page_html, flags=re.IGNORECASE | re.DOTALL).group(1)) if re.search(r"<h1[^>]*>(.*?)</h1>", page_html, flags=re.IGNORECASE | re.DOTALL) else title
    line_match = re.search(r"駅\s+(.+?)\s+.+?〈平日〉", h1)
    line_name = line_match.group(1).strip() if line_match else fallback_line_name
    station_match = re.search(r"^(.+?)駅\s+", h1)
    station_name = clean_station_name(station_match.group(1) if station_match else "")
    direction_match = re.search(r"線\s+(.+?)方面", h1)
    direction_label = direction_match.group(1).strip() if direction_match else ""
    departures: list[dict[str, Any]] = []
    link_pattern = re.compile(
        r"""<a\s+href=["'](?P<href>/station/timetable\.php\?[^"']+)["'][^>]*>(?P<body>.*?)</a>""",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in link_pattern.finditer(page_html):
        href = html.unescape(match.group("href"))
        body = match.group("body")
        params = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        tx = (params.get("TX") or [""])[0]
        dw = (params.get("DW") or [""])[0]
        tm = (params.get("TM") or [""])[0]
        if not tx:
            continue
        minute_match = re.search(r"""class=["']timetable_min["'][^>]*>.*?<span[^>]*>(\d{1,2})</span>""", body, flags=re.IGNORECASE | re.DOTALL)
        train_type_match = re.search(r"""class=["']timetable_train_type["'][^>]*>(.*?)</p>""", body, flags=re.IGNORECASE | re.DOTALL)
        headsign_match = re.search(r"""class=["']timetable_station_name["'][^>]*>(.*?)</p>""", body, flags=re.IGNORECASE | re.DOTALL)
        departures.append(
            {
                "detailUrl": urllib.parse.urljoin(BASE, href),
                "canonicalKey": f"{tx}|{dw}",
                "tx": tx,
                "dw": dw,
                "tm": tm,
                "stationName": station_name,
                "lineName": line_name,
                "directionLabel": direction_label,
                "minute": minute_match.group(1) if minute_match else None,
                "trainType": strip_tags(train_type_match.group(1)).strip("［］[]") if train_type_match else None,
                "headsign": clean_station_name(headsign_match.group(1)) if headsign_match else None,
                "sourceTimetableUrl": page_url,
            }
        )
    return departures, {"stationName": station_name, "lineName": line_name, "directionLabel": direction_label, "title": h1}


def parse_detail_page(page_html: str) -> dict[str, Any] | None:
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", page_html, flags=re.IGNORECASE | re.DOTALL)
    title = strip_tags(title_match.group(1)) if title_match else ""
    header_match = re.search(r"^\[(?P<type>[^\]]+)\]\s*(?P<origin>.+?)発\s+(?P<headsign>.+?)行き", title)
    train_type = header_match.group("type") if header_match else None
    origin = clean_station_name(header_match.group("origin")) if header_match else None
    headsign = clean_station_name(header_match.group("headsign")) if header_match else None
    rows: list[dict[str, Any]] = []
    row_pattern = re.compile(r"""<tr[^>]*class=["'][^"']*t_bd[^"']*["'][^>]*>(?P<body>.*?)</tr>""", flags=re.IGNORECASE | re.DOTALL)
    for index, row in enumerate(row_pattern.finditer(page_html), start=1):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row.group("body"), flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 2:
            continue
        station_name = clean_station_name(cells[0])
        time_text = strip_tags(cells[1])
        events = re.findall(r"(到着|出発)、\s*(\d{1,2}:\d{2})", time_text)
        arrival = next((time for kind, time in events if kind == "到着"), None)
        departure = next((time for kind, time in events if kind == "出発"), None)
        if not events:
            bare = re.search(r"(\d{1,2}:\d{2})", time_text)
            if bare:
                if index == 1:
                    departure = bare.group(1)
                else:
                    arrival = bare.group(1)
        if not station_name:
            continue
        rows.append(
            {
                "sequence": len(rows) + 1,
                "stationName": station_name,
                "arrival": arrival,
                "departure": departure,
            }
        )
    if len(rows) < 2:
        return None
    return {
        "title": title,
        "trainType": train_type,
        "origin": origin or rows[0]["stationName"],
        "headsign": headsign or rows[-1]["stationName"],
        "rows": rows,
    }


def build_train(
    key: str,
    departure: dict[str, Any],
    detail: dict[str, Any],
    physical_index: HankyuPhysicalIndex,
) -> tuple[dict[str, Any] | None, Counter[str], list[dict[str, Any]]]:
    match_methods: Counter[str] = Counter()
    unmatched: list[dict[str, Any]] = []
    stop_times: list[dict[str, Any]] = []
    previous_line_name: str | None = departure.get("lineName") or None
    for row in detail["rows"]:
        match = physical_index.match_stop(row["stationName"], departure.get("lineName"), previous_line_name)
        station = physical_index.station_for_match(match)
        if match.get("matched"):
            match_methods[str(match["method"])] += 1
        else:
            match_methods[str(match.get("method") or "unmatched")] += 1
            if len(unmatched) < 25:
                unmatched.append({"stationName": row["stationName"], "sourceLineName": departure.get("lineName"), "key": key})
        operator_name = str(station.get("operatorName") if station else OPERATOR_NAME)
        line_name = str(station.get("lineName") if station else departure.get("lineName") or "")
        previous_line_name = line_name or previous_line_name
        stop_times.append(
            {
                "sequence": row["sequence"],
                "station_name_raw": row["stationName"],
                "station_id": match.get("stationGroupId"),
                "station_group_id": match.get("stationGroupId"),
                "physical_station_id": match.get("physicalStationId"),
                "operator_name": operator_name,
                "line_id": physical_index.line_id(operator_name, line_name),
                "line_name": line_name,
                "arrival_hhmm": row.get("arrival"),
                "departure_hhmm": row.get("departure"),
                "match_method": match.get("method"),
            }
        )
    if len(stop_times) < 2:
        return None, match_methods, unmatched
    tx = departure["tx"]
    train_number = tx.split("-")[-1] if "-" in tx else tx
    source_line = str(departure.get("lineName") or "")
    primary_line = source_line if source_line in physical_index.hankyu_lines else ""
    if not primary_line:
        primary_line = next(
            (
                str(stop.get("line_name") or "")
                for stop in stop_times
                if stop.get("operator_name") == OPERATOR_NAME and stop.get("line_name") in physical_index.hankyu_lines
            ),
            source_line or str(stop_times[0].get("line_name") or ""),
        )
    first_time = stop_times[0].get("departure_hhmm") or stop_times[0].get("arrival_hhmm") or "0000"
    service_name = detail.get("trainType") or departure.get("trainType") or "普通"
    train = {
        "train_number": train_number,
        "service_instance_id": f"hankyu:{departure['dw']}:{tx}",
        "source_trip_id": f"hankyu:{departure['dw']}:{tx}",
        "operator_id": "阪急電鉄",
        "operator_name": OPERATOR_NAME,
        "service_name": service_name,
        "service_number": train_number,
        "headsign": detail.get("headsign") or departure.get("headsign"),
        "train_type": service_name,
        "route_color": physical_index.route_color(OPERATOR_NAME, primary_line),
        "line_id": physical_index.line_id(OPERATOR_NAME, primary_line),
        "line_name": primary_line,
        "source_feed_key": SOURCE_FEED_KEY,
        "origin": detail.get("origin") or stop_times[0]["station_name_raw"],
        "destination": detail.get("headsign") or stop_times[-1]["station_name_raw"],
        "source_timetable_url": departure.get("sourceTimetableUrl"),
        "source_detail_url": departure.get("detailUrl"),
        "first_departure_hhmm": first_time,
        "stop_times": stop_times,
    }
    return train, match_methods, unmatched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--line-inventory", type=Path, default=DEFAULT_LINE_INVENTORY)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--service-date", default=DEFAULT_SERVICE_DATE)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()

    physical_map = load_physical_map(args.physical_map)
    line_inventory = load_json(args.line_inventory)
    physical_index = HankyuPhysicalIndex(physical_map, line_inventory)

    index_html = fetch_text_cached(STATION_INDEX_URL, args.cache_dir, "station_pages", args.refresh)
    station_page_urls = extract_station_page_links(index_html)
    timetable_links_by_url: dict[str, dict[str, str]] = {}
    station_page_errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_text_cached, url, args.cache_dir, "station_pages", args.refresh): url
            for url in station_page_urls
        }
        for future in as_completed(futures):
            url = futures[future]
            try:
                page_html = future.result()
            except Exception as exc:
                station_page_errors.append({"url": url, "error": str(exc)})
                continue
            for link in extract_weekday_timetable_links(page_html, url):
                timetable_links_by_url.setdefault(link["url"], link)

    departures_by_key: dict[str, dict[str, Any]] = {}
    timetable_page_errors: list[dict[str, str]] = []
    timetable_page_meta: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_text_cached, link["url"], args.cache_dir, "timetable_pages", args.refresh): link
            for link in timetable_links_by_url.values()
        }
        for future in as_completed(futures):
            link = futures[future]
            try:
                page_html = future.result()
            except Exception as exc:
                timetable_page_errors.append({"url": link["url"], "error": str(exc)})
                continue
            if "お探しのページは存在しません" in page_html:
                timetable_page_errors.append({"url": link["url"], "error": "404"})
                continue
            departures, meta = parse_timetable_page(page_html, link["url"], link.get("lineName") or "")
            timetable_page_meta.append({"url": link["url"], **meta, "departureCount": str(len(departures))})
            for departure in departures:
                # The same real train appears on every downstream station page.
                departures_by_key.setdefault(departure["canonicalKey"], departure)

    detail_pages: dict[str, dict[str, Any]] = {}
    detail_page_errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_text_cached, dep["detailUrl"], args.cache_dir, "detail_pages", args.refresh): (key, dep)
            for key, dep in departures_by_key.items()
        }
        for future in as_completed(futures):
            key, dep = futures[future]
            try:
                page_html = future.result()
                detail = parse_detail_page(page_html)
            except Exception as exc:
                detail_page_errors.append({"key": key, "url": dep["detailUrl"], "error": str(exc)})
                continue
            if not detail:
                detail_page_errors.append({"key": key, "url": dep["detailUrl"], "error": "no_detail_rows"})
                continue
            detail_pages[key] = detail

    trains: list[dict[str, Any]] = []
    match_methods: Counter[str] = Counter()
    unmatched_samples: list[dict[str, Any]] = []
    line_counts: Counter[str] = Counter()
    stop_count_distribution: Counter[str] = Counter()
    for key, detail in sorted(detail_pages.items()):
        train, train_methods, unmatched = build_train(key, departures_by_key[key], detail, physical_index)
        match_methods.update(train_methods)
        if unmatched and len(unmatched_samples) < 50:
            unmatched_samples.extend(unmatched[: 50 - len(unmatched_samples)])
        if not train:
            continue
        trains.append(train)
        line_counts[str(train.get("line_name") or "")] += 1
        stop_count_distribution[str(len(train.get("stop_times") or []))] += 1

    output = {
        "id": "v4_hankyu_official_weekday_train_instances_v0_1",
        "label": "V4 Hankyu official weekday train instances",
        "version": "0.1.0",
        "generatedAt": now_iso(),
        "service_date": args.service_date,
        "source": {
            "stationIndexUrl": STATION_INDEX_URL,
            "operatorName": OPERATOR_NAME,
            "sourceFeedKey": SOURCE_FEED_KEY,
        },
        "train_instances": sorted(trains, key=lambda item: item["service_instance_id"]),
    }
    audit = {
        "schema": "onichase.v4.hankyu_official_train_instances_audit.v1",
        "generatedAt": now_iso(),
        "serviceDate": args.service_date,
        "operatorName": OPERATOR_NAME,
        "stationPageCount": len(station_page_urls),
        "timetablePageCount": len(timetable_links_by_url),
        "rawDepartureTrainKeyCount": len(departures_by_key),
        "detailPageCount": len(detail_pages),
        "trainInstanceCount": len(trains),
        "stopTimeCount": sum(len(train.get("stop_times") or []) for train in trains),
        "lineTrainCounts": dict(sorted(line_counts.items())),
        "stopCountDistribution": dict(sorted(stop_count_distribution.items(), key=lambda item: int(item[0]))),
        "stationMatchMethods": dict(sorted(match_methods.items())),
        "unmatchedStopSample": unmatched_samples,
        "stationPageErrors": station_page_errors[:30],
        "timetablePageErrors": timetable_page_errors[:50],
        "detailPageErrors": detail_page_errors[:50],
        "timetablePageSample": timetable_page_meta[:20],
    }
    write_json(args.output, output)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(trains)} trains")
    print(
        f"Wrote {args.audit_output}: timetable_pages={len(timetable_links_by_url)} "
        f"details={len(detail_pages)} unmatched_samples={len(unmatched_samples)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
