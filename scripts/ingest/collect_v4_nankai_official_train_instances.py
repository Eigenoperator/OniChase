#!/usr/bin/env python3
"""Collect v4 weekday train instances from Nankai official station timetables."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_nankai_official_cache"
DEFAULT_OUTPUT = ROOT / "data" / "v4_nankai_official_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_nankai_official_train_instances_audit.json"
DEFAULT_SERVICE_DATE = "2026-04-27"

BASE = "https://www.nankai.co.jp"
KENTSAKU_BASE = "https://kensaku.nankai.co.jp/pc/"
OPERATOR_NAME = "南海電気鉄道"
SOURCE_FEED_KEY = "nankai_official_station_timetable"
JIKOKU_PAGES = [
    f"{BASE}/traffic/jikoku.html",
    f"{BASE}/traffic/jikoku-ka.html",
    f"{BASE}/traffic/jikoku-sa.html",
    f"{BASE}/traffic/jikoku-ta.html",
    f"{BASE}/traffic/jikoku-na.html",
    f"{BASE}/traffic/jikoku-ha.html",
    f"{BASE}/traffic/jikoku-ma.html",
    f"{BASE}/traffic/jikoku-ya.html",
    f"{BASE}/traffic/jikoku-ra.html",
    f"{BASE}/traffic/jikoku-wa.html",
]

SOURCE_LINE_ALIASES = {
    "南海線": ("南海電気鉄道", "南海本線"),
    "高野線": ("南海電気鉄道", "高野線"),
    "高野線（汐見橋～岸里玉出）": ("南海電気鉄道", "高野線"),
    "高野線(汐見橋～岸里玉出)": ("南海電気鉄道", "高野線"),
    "空港線": ("南海電気鉄道", "空港線"),
    "高師浜線": ("南海電気鉄道", "高師浜線"),
    "多奈川線": ("南海電気鉄道", "多奈川線"),
    "加太線": ("南海電気鉄道", "加太線"),
    "和歌山港線": ("南海電気鉄道", "和歌山港線"),
    "高野山ケーブルカー": ("南海電気鉄道", "鋼索線"),
    "泉北線": ("泉北高速鉄道", "泉北高速鉄道線"),
}

THROUGH_HINTS = [
    ("泉北高速鉄道", "泉北高速鉄道線"),
    ("西日本旅客鉄道", "関西空港線"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cache_path(cache_dir: Path, namespace: str, key: str, suffix: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return cache_dir / namespace / f"{digest}{suffix}"


def fetch_text_cached(url: str, cache_dir: Path, namespace: str, refresh: bool, timeout: int = 90) -> str:
    path = cache_path(cache_dir, namespace, url, ".html")
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8", errors="replace")
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,*/*",
            "User-Agent": "Mozilla/5.0 (compatible; OniChase-v4-nankai-official-collector/0.1)",
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


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def clean_station_name(value: str) -> str:
    text = strip_tags(value)
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"駅$", "", text)
    return text.strip()


def clean_source_line(value: str) -> str:
    text = strip_tags(value)
    text = re.sub(r"\s+", "", text)
    return text.strip()


def parse_hhmm(value: str | None) -> str | None:
    if not value:
        return None
    text = strip_tags(value)
    text = text.replace("：", ":").replace("−", "").replace("-", "").strip()
    match = re.search(r"(\d{1,2})\s*:\s*(\d{2})", text)
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"


def load_physical_map(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


class NankaiPhysicalIndex:
    def __init__(self, physical_map: dict[str, Any], line_inventory: dict[str, Any]) -> None:
        self.matcher = V4StationMatcher(physical_map)
        self.station_by_id = {station["id"]: station for station in physical_map["physicalStations"]}
        self.line_id_by_operator_line: dict[tuple[str, str], str] = {}
        self.line_color_by_operator_line: dict[tuple[str, str], str] = {}
        self.nankai_lines: set[str] = set()
        self.target_station_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for line in line_inventory.get("lines", []):
            operator_name = str(line.get("operatorName") or "")
            line_name = str(line.get("lineName") or "")
            self.line_id_by_operator_line[(operator_name, line_name)] = str(line.get("id") or line_name)
            self.line_color_by_operator_line[(operator_name, line_name)] = str(
                line.get("lineColor") or line.get("operatorColor") or "#009A44"
            ).lstrip("#")
            if operator_name == OPERATOR_NAME:
                self.nankai_lines.add(line_name)
        for station in physical_map.get("physicalStations", []):
            if station.get("operatorName") not in {OPERATOR_NAME, "泉北高速鉄道"}:
                continue
            for key in normalize_name_variants(station.get("nameJa") or ""):
                self.target_station_by_name[key].append(station)

    def line_id(self, operator_name: str, line_name: str) -> str:
        return self.line_id_by_operator_line.get((operator_name, line_name)) or line_name

    def route_color(self, operator_name: str, line_name: str) -> str:
        return self.line_color_by_operator_line.get((operator_name, line_name), "#009A44").lstrip("#")

    def station_for_match(self, match: dict[str, Any]) -> dict[str, Any] | None:
        station_id = match.get("physicalStationId")
        if not station_id:
            return None
        return self.station_by_id.get(str(station_id))

    def source_operator_line(self, source_line_name: str | None) -> tuple[str, str]:
        source_key = clean_source_line(source_line_name or "")
        return SOURCE_LINE_ALIASES.get(source_key, (OPERATOR_NAME, source_key))

    def target_candidates(self, station_name: str) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        aliases = [station_name]
        if station_name == "なんば":
            aliases.append("難波")
        for alias in aliases:
            for key in normalize_name_variants(alias):
                for station in self.target_station_by_name.get(key, []):
                    station_id = str(station.get("id") or "")
                    if station_id in seen:
                        continue
                    seen.add(station_id)
                    output.append(station)
        return output

    def match_stop(
        self,
        station_name: str,
        source_line_name: str | None,
        previous_operator_name: str | None,
        previous_line_name: str | None,
    ) -> dict[str, Any]:
        cleaned = clean_station_name(station_name)
        source_operator, source_line = self.source_operator_line(source_line_name)
        candidates = self.target_candidates(cleaned)
        if candidates:
            ranked = sorted(
                candidates,
                key=lambda station: (
                    0 if station.get("operatorName") == previous_operator_name else 1,
                    0 if previous_line_name and station.get("lineName") == previous_line_name else 1,
                    0 if station.get("operatorName") == source_operator else 1,
                    0 if source_line and station.get("lineName") == source_line else 1,
                    str(station.get("operatorName") or ""),
                    str(station.get("lineName") or ""),
                    str(station.get("stationGroupId") or ""),
                ),
            )
            best = ranked[0]
            return {
                "matched": True,
                "method": "nankai_name_context",
                "stationGroupId": best["stationGroupId"],
                "physicalStationId": best["id"],
                "candidateCount": len(candidates),
            }
        for operator_name, line_name in [(source_operator, source_line), *THROUGH_HINTS]:
            match = self.matcher.match(
                operator_name=operator_name,
                line_name=line_name,
                stop_name=cleaned,
                stop_lat=None,
                stop_lon=None,
            )
            if match.get("matched"):
                match["method"] = f"fallback_{operator_name}_{line_name}_{match['method']}"
                return match
        return self.matcher.match(
            operator_name=OPERATOR_NAME,
            line_name=source_line,
            stop_name=cleaned,
            stop_lat=None,
            stop_lon=None,
        )


def extract_weekday_timetable_links(page_html: str, page_url: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    block_pattern = re.compile(
        r"""<div\s+class=["']el-station-list__item["'][^>]*>(?P<body>.*?)(?=<div\s+class=["']el-station-list__item["']|<h2|</main>|$)""",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for block in block_pattern.finditer(page_html):
        body = block.group("body")
        station_match = re.search(r"""el-station-list__heading__inner["'][^>]*>(?P<name>.*?)</span>""", body, flags=re.IGNORECASE | re.DOTALL)
        line_match = re.search(r"""el-station-list__train[^>]*>.*?<span[^>]*>(?P<line>.*?)</span>""", body, flags=re.IGNORECASE | re.DOTALL)
        station_name = clean_station_name(station_match.group("name")) if station_match else ""
        source_line = strip_tags(line_match.group("line")) if line_match else ""
        for href_match in re.finditer(
            r"""href\s*=\s*["'](?P<href>https://kensaku\.nankai\.co\.jp/pc/T5\?[^"']*?dw=0[^"']*)["'][^>]*>(?P<label>.*?)</a>""",
            body,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            url = html.unescape(href_match.group("href")).replace("&amp;", "&")
            if url in seen:
                continue
            seen.add(url)
            links.append(
                {
                    "url": url,
                    "stationName": station_name,
                    "lineName": source_line,
                    "directionLabel": strip_tags(href_match.group("label")),
                    "sourcePageUrl": page_url,
                }
            )
    return links


def parse_timetable_page(page_html: str, link: dict[str, str]) -> list[dict[str, Any]]:
    departures: list[dict[str, Any]] = []
    for href_match in re.finditer(r"""href\s*=\s*["'](?P<href>T7\?[^"']+)["']""", page_html, flags=re.IGNORECASE):
        href = html.unescape(href_match.group("href")).replace("&amp;", "&")
        detail_url = urllib.parse.urljoin(KENTSAKU_BASE, href)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(detail_url).query)
        tx = (params.get("tx") or [""])[0]
        dw = (params.get("dw") or [""])[0]
        tm = (params.get("tm") or [""])[0]
        if not tx:
            continue
        departures.append(
            {
                "detailUrl": detail_url,
                "canonicalKey": f"{tx}|{dw}",
                "tx": tx,
                "dw": dw,
                "tm": tm,
                "stationName": link.get("stationName"),
                "lineName": link.get("lineName"),
                "directionLabel": link.get("directionLabel"),
                "sourceTimetableUrl": link.get("url"),
            }
        )
    return departures


def parse_detail_page(page_html: str) -> dict[str, Any] | None:
    header_match = re.search(r"""<td[^>]*colspan=["']3["'][^>]*>\s*<b>(?P<header>.*?)</b>""", page_html, flags=re.IGNORECASE | re.DOTALL)
    header = strip_tags(header_match.group("header")) if header_match else ""
    train_type = None
    headsign = None
    header_parts = [part for part in re.split(r"\s+", header) if part and part != "平日のダイヤ"]
    if header_parts:
        train_type = header_parts[0]
    if len(header_parts) >= 2:
        headsign = clean_station_name(header_parts[1].removesuffix("行"))
    rows: list[dict[str, Any]] = []
    row_pattern = re.compile(r"""<tr>\s*(?P<body>(?:\s*<td[^>]*>.*?</td>\s*){3})\s*</tr>""", flags=re.IGNORECASE | re.DOTALL)
    for row in row_pattern.finditer(page_html):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row.group("body"), flags=re.IGNORECASE | re.DOTALL)
        if len(cells) != 3:
            continue
        station_name = clean_station_name(cells[0])
        if not station_name or station_name == "停車駅":
            continue
        arrival = parse_hhmm(cells[1])
        departure = parse_hhmm(cells[2])
        if not arrival and not departure:
            # Nankai detail pages list pass-through stations for express trains
            # with blank time cells.  They are geometry context, not boardable
            # stop_times, so keep them out of gameplay stop choices.
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
        "title": header,
        "trainType": train_type,
        "origin": rows[0]["stationName"],
        "headsign": headsign or rows[-1]["stationName"],
        "rows": rows,
    }


def build_train(
    key: str,
    departure: dict[str, Any],
    detail: dict[str, Any],
    physical_index: NankaiPhysicalIndex,
) -> tuple[dict[str, Any] | None, Counter[str], list[dict[str, Any]]]:
    match_methods: Counter[str] = Counter()
    unmatched: list[dict[str, Any]] = []
    stop_times: list[dict[str, Any]] = []
    previous_operator_name: str | None = None
    previous_line_name: str | None = None
    for row in detail["rows"]:
        match = physical_index.match_stop(
            row["stationName"],
            departure.get("lineName"),
            previous_operator_name,
            previous_line_name,
        )
        station = physical_index.station_for_match(match)
        if match.get("matched"):
            match_methods[str(match["method"])] += 1
        else:
            match_methods[str(match.get("method") or "unmatched")] += 1
            if len(unmatched) < 25:
                unmatched.append({"stationName": row["stationName"], "sourceLineName": departure.get("lineName"), "key": key})
        operator_name = str(station.get("operatorName") if station else OPERATOR_NAME)
        line_name = str(station.get("lineName") if station else departure.get("lineName") or "")
        previous_operator_name = operator_name or previous_operator_name
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

    source_operator, source_line = physical_index.source_operator_line(departure.get("lineName"))
    operator_name = OPERATOR_NAME if any(stop.get("operator_name") == OPERATOR_NAME for stop in stop_times) else source_operator
    primary_line = source_line if operator_name == source_operator else ""
    if not primary_line or (operator_name, primary_line) not in physical_index.line_id_by_operator_line:
        primary_line = next(
            (
                str(stop.get("line_name") or "")
                for stop in stop_times
                if stop.get("operator_name") == operator_name
            ),
            str(stop_times[0].get("line_name") or source_line),
        )

    tx = departure["tx"]
    train_number = tx.split("-")[-1] if "-" in tx else tx
    first_time = stop_times[0].get("departure_hhmm") or stop_times[0].get("arrival_hhmm") or "00:00"
    service_name = detail.get("trainType") or "普通"
    headsign = detail.get("headsign") or stop_times[-1]["station_name_raw"]
    train = {
        "train_number": train_number,
        "service_instance_id": f"nankai:{departure['dw']}:{tx}",
        "source_trip_id": f"nankai:{departure['dw']}:{tx}",
        "operator_id": operator_name,
        "operator_name": operator_name,
        "service_name": service_name,
        "service_number": train_number,
        "headsign": headsign,
        "train_type": service_name,
        "route_color": physical_index.route_color(operator_name, primary_line),
        "line_id": physical_index.line_id(operator_name, primary_line),
        "line_name": primary_line,
        "source_feed_key": SOURCE_FEED_KEY,
        "origin": detail.get("origin") or stop_times[0]["station_name_raw"],
        "destination": headsign,
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
    physical_index = NankaiPhysicalIndex(physical_map, line_inventory)

    timetable_links_by_url: dict[str, dict[str, str]] = {}
    station_page_errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_text_cached, url, args.cache_dir, "station_index_pages", args.refresh): url
            for url in JIKOKU_PAGES
        }
        for future in as_completed(futures):
            page_url = futures[future]
            try:
                page_html = future.result()
            except Exception as exc:
                station_page_errors.append({"url": page_url, "error": str(exc)})
                continue
            for link in extract_weekday_timetable_links(page_html, page_url):
                timetable_links_by_url.setdefault(link["url"], link)

    departures_by_key: dict[str, dict[str, Any]] = {}
    timetable_page_errors: list[dict[str, str]] = []
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
            for departure in parse_timetable_page(page_html, link):
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
    operator_counts: Counter[str] = Counter()
    stop_count_distribution: Counter[str] = Counter()
    for key, detail in sorted(detail_pages.items()):
        train, train_methods, unmatched = build_train(key, departures_by_key[key], detail, physical_index)
        match_methods.update(train_methods)
        if unmatched and len(unmatched_samples) < 50:
            unmatched_samples.extend(unmatched[: 50 - len(unmatched_samples)])
        if not train:
            continue
        trains.append(train)
        operator_counts[str(train.get("operator_name") or "")] += 1
        line_counts[f"{train.get('operator_name')}::{train.get('line_name')}"] += 1
        stop_count_distribution[str(len(train.get("stop_times") or []))] += 1

    output = {
        "id": "v4_nankai_official_weekday_train_instances_v0_1",
        "label": "V4 Nankai official weekday train instances",
        "version": "0.1.0",
        "generatedAt": now_iso(),
        "service_date": args.service_date,
        "source": {
            "stationIndexUrls": JIKOKU_PAGES,
            "operatorName": OPERATOR_NAME,
            "sourceFeedKey": SOURCE_FEED_KEY,
        },
        "train_instances": sorted(trains, key=lambda item: item["service_instance_id"]),
    }
    audit = {
        "schema": "onichase.v4.nankai_official_train_instances_audit.v1",
        "generatedAt": now_iso(),
        "serviceDate": args.service_date,
        "operatorName": OPERATOR_NAME,
        "stationIndexPageCount": len(JIKOKU_PAGES),
        "timetablePageCount": len(timetable_links_by_url),
        "rawDepartureTrainKeyCount": len(departures_by_key),
        "detailPageCount": len(detail_pages),
        "trainInstanceCount": len(trains),
        "stopTimeCount": sum(len(train.get("stop_times") or []) for train in trains),
        "operatorTrainCounts": dict(sorted(operator_counts.items())),
        "lineTrainCounts": dict(sorted(line_counts.items())),
        "stopCountDistribution": dict(sorted(stop_count_distribution.items(), key=lambda item: int(item[0]))),
        "stationMatchMethods": dict(sorted(match_methods.items())),
        "unmatchedStopSample": unmatched_samples,
        "stationPageErrors": station_page_errors[:30],
        "timetablePageErrors": timetable_page_errors[:50],
        "detailPageErrors": detail_page_errors[:50],
        "timetablePageSample": list(timetable_links_by_url.values())[:20],
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
