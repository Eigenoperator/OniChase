#!/usr/bin/env python3
"""Reconstruct v4 weekday train instances from Osaka Metro official station timetables.

Osaka Metro publishes station-direction departure tables rather than per-train
stop detail pages.  This collector keeps the official station departure times
and stitches same-direction all-stop movements by chronological adjacency.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import ssl
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
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_osaka_metro_official_cache"
DEFAULT_OUTPUT = ROOT / "data" / "v4_osaka_metro_official_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_osaka_metro_official_train_instances_audit.json"
DEFAULT_SERVICE_DATE = "2026-04-27"

BASE = "https://kensaku.osakametro.co.jp"
RAIL_INDEX_URL = f"{BASE}/timetable/ja/sp/subway/dia/rail"
OPERATOR_NAME = "大阪市高速電気軌道"
SOURCE_FEED_KEY = "osaka_metro_official_station_timetable_reconstructed"

LINE_DEFS = {
    "10": {"railName": "御堂筋・北大阪急行線", "operator": OPERATOR_NAME, "line": "1号線(御堂筋線)"},
    "20": {"railName": "谷町線", "operator": OPERATOR_NAME, "line": "2号線(谷町線)"},
    "30": {"railName": "四つ橋線", "operator": OPERATOR_NAME, "line": "3号線(四つ橋線)"},
    "40": {"railName": "中央線", "operator": OPERATOR_NAME, "line": "4号線(中央線)"},
    "50": {"railName": "千日前線", "operator": OPERATOR_NAME, "line": "5号線(千日前線)"},
    "60": {"railName": "堺筋線", "operator": OPERATOR_NAME, "line": "6号線(堺筋線)"},
    "70": {"railName": "長堀鶴見緑地線", "operator": OPERATOR_NAME, "line": "7号線(長堀鶴見緑地線)"},
    "75": {"railName": "今里筋線", "operator": OPERATOR_NAME, "line": "8号線(今里筋線)"},
    "80": {"railName": "ニュートラム", "operator": OPERATOR_NAME, "line": "南港ポートタウン線"},
    "90": {"railName": "御堂筋・北大阪急行線", "operator": "北大阪急行電鉄", "line": "南北線"},
}


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
            "User-Agent": "Mozilla/5.0 (compatible; OniChase-v4-osaka-metro-official-collector/0.1)",
        },
    )
    # The site is accessible in browsers but the local CA bundle in this runner
    # does not validate its chain reliably.
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
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


def minutes_to_hhmm(total: int) -> str:
    hour = total // 60
    minute = total % 60
    return f"{hour:02d}:{minute:02d}"


def hhmm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    total = int(hour) * 60 + int(minute)
    if total < 3 * 60:
        total += 24 * 60
    return total


def load_physical_map(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


class OsakaMetroPhysicalIndex:
    def __init__(self, physical_map: dict[str, Any], line_inventory: dict[str, Any]) -> None:
        self.matcher = V4StationMatcher(physical_map)
        self.station_by_id = {station["id"]: station for station in physical_map["physicalStations"]}
        self.line_id_by_operator_line: dict[tuple[str, str], str] = {}
        self.line_color_by_operator_line: dict[tuple[str, str], str] = {}
        self.station_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        target_operators = {OPERATOR_NAME, "北大阪急行電鉄"}
        for line in line_inventory.get("lines", []):
            operator_name = str(line.get("operatorName") or "")
            line_name = str(line.get("lineName") or "")
            self.line_id_by_operator_line[(operator_name, line_name)] = str(line.get("id") or line_name)
            self.line_color_by_operator_line[(operator_name, line_name)] = str(
                line.get("lineColor") or line.get("operatorColor") or "#004098"
            ).lstrip("#")
        for station in physical_map.get("physicalStations", []):
            if station.get("operatorName") not in target_operators:
                continue
            for key in normalize_name_variants(station.get("nameJa") or ""):
                self.station_by_name[key].append(station)

    def line_id(self, operator_name: str, line_name: str) -> str:
        return self.line_id_by_operator_line.get((operator_name, line_name)) or line_name

    def route_color(self, operator_name: str, line_name: str) -> str:
        return self.line_color_by_operator_line.get((operator_name, line_name), "#004098").lstrip("#")

    def station_for_match(self, match: dict[str, Any]) -> dict[str, Any] | None:
        station_id = match.get("physicalStationId")
        if not station_id:
            return None
        return self.station_by_id.get(str(station_id))

    def candidates(self, station_name: str) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        aliases = [station_name]
        aliases.extend({
            "なんば": ["難波"],
            "あびこ": ["我孫子"],
            "なかもず": ["中百舌鳥"],
        }.get(station_name, []))
        for alias in aliases:
            for key in normalize_name_variants(alias):
                for station in self.station_by_name.get(key, []):
                    station_id = str(station.get("id") or "")
                    if station_id in seen:
                        continue
                    seen.add(station_id)
                    output.append(station)
        return output

    def match_stop(self, station_name: str, operator_name: str, line_name: str) -> dict[str, Any]:
        cleaned = clean_station_name(station_name)
        candidates = self.candidates(cleaned)
        if candidates:
            ranked = sorted(
                candidates,
                key=lambda station: (
                    0 if station.get("operatorName") == operator_name else 1,
                    0 if station.get("lineName") == line_name else 1,
                    str(station.get("operatorName") or ""),
                    str(station.get("lineName") or ""),
                ),
            )
            best = ranked[0]
            return {
                "matched": True,
                "method": "osaka_metro_name_context",
                "stationGroupId": best["stationGroupId"],
                "physicalStationId": best["id"],
                "candidateCount": len(candidates),
            }
        return self.matcher.match(
            operator_name=operator_name,
            line_name=line_name,
            stop_name=cleaned,
            stop_lat=None,
            stop_lon=None,
        )


def extract_line_links(index_html: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for match in re.finditer(
        r"""href\s*=\s*["'](?P<href>/timetable/ja/sp/subway/dia/rail/(?P<code>\d+))["'][^>]*>(?P<label>.*?)</a>""",
        index_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        code = match.group("code")
        if code not in LINE_DEFS:
            continue
        links.append({"code": code, "url": urllib.parse.urljoin(BASE, match.group("href")), "label": strip_tags(match.group("label"))})
    return links


def extract_station_links(line_html: str, line_code: str) -> list[dict[str, str]]:
    stations: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"""href\s*=\s*["'](?P<href>/timetable/ja/sp/subway/dia/station/(?P<station_id>\d+))["'][^>]*>(?P<label>.*?)</a>""",
        line_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        station_id = match.group("station_id")
        if station_id in seen:
            continue
        seen.add(station_id)
        stations.append(
            {
                "lineCode": line_code,
                "stationSiteId": station_id,
                "stationName": clean_station_name(match.group("label")),
                "stationPageUrl": urllib.parse.urljoin(BASE, match.group("href")),
            }
        )
    return stations


def extract_direction_links(station_html: str, station: dict[str, str], line_code: str) -> list[dict[str, str]]:
    expected = compact(str(LINE_DEFS[line_code]["railName"]))
    output: list[dict[str, str]] = []
    block_pattern = re.compile(
        r"""<li\s+class=["']mark["'][^>]*>(?P<head>.*?)</li>\s*</ul>\s*<ul\s+class=["']btn_full["'][^>]*>(?P<body>.*?)</ul>""",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for block in block_pattern.finditer(station_html):
        rail_match = re.search(r"""class=["']railname["'][^>]*>(?P<name>.*?)</span>""", block.group("head"), flags=re.IGNORECASE | re.DOTALL)
        rail_name = strip_tags(rail_match.group("name")) if rail_match else ""
        if compact(rail_name) != expected:
            continue
        for link_match in re.finditer(
            r"""href\s*=\s*["'](?P<href>/timetable/ja/sp/subway/dia/station/(?P<station_id>\d+)/(?P<route_id>\d+)/(?P<direction>\d+))["'][^>]*>(?P<label>.*?)</a>""",
            block.group("body"),
            flags=re.IGNORECASE | re.DOTALL,
        ):
            output.append(
                {
                    **station,
                    "routeId": link_match.group("route_id"),
                    "direction": link_match.group("direction"),
                    "directionLabel": strip_tags(link_match.group("label")),
                    "timetableUrl": urllib.parse.urljoin(BASE, link_match.group("href")),
                    "railName": rail_name,
                }
            )
    return output


def parse_legend(weekday_html: str, direction_label: str) -> dict[str, str]:
    default = re.sub(r"\s*方面.*$", "", strip_tags(direction_label))
    legend = {"": clean_station_name(default)}
    legend_match = re.search(r"【凡例】(?P<body>.*?)(?:ひとつ前に戻る|</body>)", weekday_html, flags=re.IGNORECASE | re.DOTALL)
    if legend_match:
        text = strip_tags(legend_match.group("body"))
        for code, destination in re.findall(r"(\S+?)…([^…\s]+?)行", text):
            code = code.strip()
            if code == "無印":
                code = ""
            legend[code] = clean_station_name(destination)
    return legend


def parse_departures(timetable_html: str, direction: dict[str, str]) -> list[dict[str, Any]]:
    weekday_match = re.search(r"""<div\s+class=["'][^"']*stt_heijitsu[^"']*["'][^>]*id=["']weekday["'][^>]*>(?P<body>.*?)(?=<div\s+class=["'][^"']*stt_kyujitsu|<div\s+id=["']hanrei|</body>)""", timetable_html, flags=re.IGNORECASE | re.DOTALL)
    if not weekday_match:
        return []
    body = weekday_match.group("body")
    legend = parse_legend(timetable_html, direction.get("directionLabel") or "")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.IGNORECASE | re.DOTALL)
    current_hour: int | None = None
    output: list[dict[str, Any]] = []
    for row in rows:
        if "<th" in row.lower():
            continue
        cells = re.findall(r"<td([^>]*)>(.*?)</td>", row, flags=re.IGNORECASE | re.DOTALL)
        minute_cells: list[tuple[str, str]] = []
        for attrs, cell in cells:
            cell_text = strip_tags(cell)
            if "class=\"time\"" in attrs or "class='time'" in attrs:
                if re.fullmatch(r"\d{1,2}", cell_text):
                    current_hour = int(cell_text)
                continue
            minute_cells.append((attrs, cell))
        if current_hour is None:
            continue
        for _attrs, cell in minute_cells:
            text = strip_tags(cell)
            if not text:
                continue
            minute_match = re.search(r"(\d{2})\s*$", text)
            if not minute_match:
                continue
            minute = int(minute_match.group(1))
            code = text[: minute_match.start()].strip()
            code = code.replace("　", "").strip()
            hhmm = f"{current_hour:02d}:{minute:02d}"
            output.append(
                {
                    "stationSiteId": direction["stationSiteId"],
                    "stationName": direction["stationName"],
                    "lineCode": direction["lineCode"],
                    "routeId": direction["routeId"],
                    "direction": direction["direction"],
                    "time": hhmm,
                    "minutes": hhmm_to_minutes(hhmm),
                    "headsignCode": code,
                    "headsign": legend.get(code, legend.get("", "")),
                    "sourceTimetableUrl": direction["timetableUrl"],
                }
            )
    return sorted(output, key=lambda item: item["minutes"])


def direction_score(station_departures: list[list[dict[str, Any]]]) -> int:
    score = 0
    for current, next_station in zip(station_departures, station_departures[1:]):
        next_times = [item["minutes"] for item in next_station]
        cursor = 0
        for item in current:
            while cursor < len(next_times) and next_times[cursor] <= item["minutes"]:
                cursor += 1
            if cursor < len(next_times) and next_times[cursor] - item["minutes"] <= 12:
                score += 1
    return score


def orient_station_order(
    station_order: list[dict[str, str]],
    departures_by_station_dir: dict[tuple[str, str], list[dict[str, Any]]],
    direction: str,
) -> list[dict[str, str]]:
    forward = [departures_by_station_dir.get((station["stationSiteId"], direction), []) for station in station_order]
    reverse_order = list(reversed(station_order))
    reverse = [departures_by_station_dir.get((station["stationSiteId"], direction), []) for station in reverse_order]
    return station_order if direction_score(forward) >= direction_score(reverse) else reverse_order


def compatible_headsign(existing: str, candidate: str) -> bool:
    return not existing or not candidate or existing == candidate


def stitch_trains(
    line_code: str,
    station_order: list[dict[str, str]],
    departures_by_station_dir: dict[tuple[str, str], list[dict[str, Any]]],
    direction: str,
) -> list[list[dict[str, Any]]]:
    oriented = orient_station_order(station_order, departures_by_station_dir, direction)
    active: list[list[dict[str, Any]]] = []
    finished: list[list[dict[str, Any]]] = []
    for station in oriented:
        departures = departures_by_station_dir.get((station["stationSiteId"], direction), [])
        used_active: set[int] = set()
        next_active: list[list[dict[str, Any]]] = []
        for dep in departures:
            best_index: int | None = None
            best_delta: int | None = None
            for index, train in enumerate(active):
                if index in used_active:
                    continue
                last = train[-1]
                delta = dep["minutes"] - last["minutes"]
                if delta <= 0 or delta > 15:
                    continue
                if not compatible_headsign(str(train[0].get("headsign") or ""), str(dep.get("headsign") or "")):
                    continue
                if best_delta is None or delta < best_delta:
                    best_index = index
                    best_delta = delta
            if best_index is None:
                next_active.append([dep])
            else:
                used_active.add(best_index)
                train = [*active[best_index], dep]
                next_active.append(train)
        for index, train in enumerate(active):
            if index not in used_active:
                finished.append(train)
        active = next_active
    finished.extend(active)
    return [train for train in finished if len(train) >= 2]


def build_train(
    line_code: str,
    direction: str,
    index: int,
    stitched: list[dict[str, Any]],
    physical_index: OsakaMetroPhysicalIndex,
) -> tuple[dict[str, Any] | None, Counter[str], list[dict[str, Any]]]:
    line_def = LINE_DEFS[line_code]
    operator_name = str(line_def["operator"])
    line_name = str(line_def["line"])
    stop_times: list[dict[str, Any]] = []
    methods: Counter[str] = Counter()
    unmatched: list[dict[str, Any]] = []
    for sequence, dep in enumerate(stitched, start=1):
        match = physical_index.match_stop(dep["stationName"], operator_name, line_name)
        station = physical_index.station_for_match(match)
        if match.get("matched"):
            methods[str(match["method"])] += 1
        else:
            methods[str(match.get("method") or "unmatched")] += 1
            if len(unmatched) < 25:
                unmatched.append({"stationName": dep["stationName"], "lineCode": line_code, "direction": direction})
        stop_operator = str(station.get("operatorName") if station else operator_name)
        stop_line = str(station.get("lineName") if station else line_name)
        hhmm = minutes_to_hhmm(dep["minutes"])
        stop_times.append(
            {
                "sequence": sequence,
                "station_name_raw": dep["stationName"],
                "station_id": match.get("stationGroupId"),
                "station_group_id": match.get("stationGroupId"),
                "physical_station_id": match.get("physicalStationId"),
                "operator_name": stop_operator,
                "line_id": physical_index.line_id(stop_operator, stop_line),
                "line_name": stop_line,
                "arrival_hhmm": None if sequence == 1 else hhmm,
                "departure_hhmm": None if sequence == len(stitched) else hhmm,
                "match_method": match.get("method"),
            }
        )
    if len(stop_times) < 2:
        return None, methods, unmatched
    first_time = stop_times[0].get("departure_hhmm") or stop_times[0].get("arrival_hhmm") or "00:00"
    train_id = f"osakametro:{line_code}:{direction}:{first_time.replace(':', '')}:{index:04d}"
    headsign = str(stitched[0].get("headsign") or stitched[-1]["stationName"])
    train = {
        "train_number": f"OM{line_code}{direction}-{first_time.replace(':', '')}-{index:04d}",
        "service_instance_id": train_id,
        "source_trip_id": train_id,
        "operator_id": operator_name,
        "operator_name": operator_name,
        "service_name": "普通",
        "service_number": f"{line_code}{direction}-{first_time.replace(':', '')}-{index:04d}",
        "headsign": headsign,
        "train_type": "普通",
        "route_color": physical_index.route_color(operator_name, line_name),
        "line_id": physical_index.line_id(operator_name, line_name),
        "line_name": line_name,
        "source_feed_key": SOURCE_FEED_KEY,
        "reconstruction_method": "official_station_departures_chronological_stitch",
        "origin": stop_times[0]["station_name_raw"],
        "destination": headsign,
        "source_timetable_url": stitched[0].get("sourceTimetableUrl"),
        "first_departure_hhmm": first_time,
        "stop_times": stop_times,
    }
    return train, methods, unmatched


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

    physical_index = OsakaMetroPhysicalIndex(load_physical_map(args.physical_map), load_json(args.line_inventory))

    index_html = fetch_text_cached(RAIL_INDEX_URL, args.cache_dir, "index", args.refresh)
    line_links = extract_line_links(index_html)
    station_orders: dict[str, list[dict[str, str]]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_text_cached, link["url"], args.cache_dir, "line_pages", args.refresh): link
            for link in line_links
        }
        for future in as_completed(futures):
            link = futures[future]
            station_orders[link["code"]] = extract_station_links(future.result(), link["code"])

    direction_links: dict[str, dict[str, str]] = {}
    station_page_errors: list[dict[str, str]] = []
    station_pages = {
        (station["stationSiteId"], station["lineCode"]): station
        for stations in station_orders.values()
        for station in stations
    }
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_text_cached, station["stationPageUrl"], args.cache_dir, "station_pages", args.refresh): station
            for station in station_pages.values()
        }
        for future in as_completed(futures):
            station = futures[future]
            try:
                station_html = future.result()
            except Exception as exc:
                station_page_errors.append({"url": station["stationPageUrl"], "error": str(exc)})
                continue
            for link in extract_direction_links(station_html, station, station["lineCode"]):
                direction_links.setdefault(link["timetableUrl"], link)

    departures_by_line_direction_station: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    timetable_page_errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_text_cached, link["timetableUrl"], args.cache_dir, "timetable_pages", args.refresh): link
            for link in direction_links.values()
        }
        for future in as_completed(futures):
            link = futures[future]
            try:
                page_html = future.result()
                departures = parse_departures(page_html, link)
            except Exception as exc:
                timetable_page_errors.append({"url": link["timetableUrl"], "error": str(exc)})
                continue
            departures_by_line_direction_station[(link["lineCode"], link["direction"], link["stationSiteId"])].extend(departures)

    trains: list[dict[str, Any]] = []
    match_methods: Counter[str] = Counter()
    unmatched_samples: list[dict[str, Any]] = []
    line_counts: Counter[str] = Counter()
    reconstructed_counts: Counter[str] = Counter()
    for line_code, station_order in sorted(station_orders.items()):
        directions = sorted({
            direction
            for l_code, direction, _station_id in departures_by_line_direction_station
            if l_code == line_code
        })
        for direction in directions:
            by_station = {
                (station_id, direction): deps
                for l_code, d, station_id in departures_by_line_direction_station
                if l_code == line_code and d == direction
                for deps in [departures_by_line_direction_station[(l_code, d, station_id)]]
            }
            stitched_trains = stitch_trains(line_code, station_order, by_station, direction)
            reconstructed_counts[f"{line_code}:{direction}"] = len(stitched_trains)
            for index, stitched in enumerate(stitched_trains, start=1):
                train, methods, unmatched = build_train(line_code, direction, index, stitched, physical_index)
                match_methods.update(methods)
                if unmatched and len(unmatched_samples) < 50:
                    unmatched_samples.extend(unmatched[: 50 - len(unmatched_samples)])
                if not train:
                    continue
                trains.append(train)
                line_counts[f"{train.get('operator_name')}::{train.get('line_name')}"] += 1

    output = {
        "id": "v4_osaka_metro_official_weekday_train_instances_v0_1",
        "label": "V4 Osaka Metro official weekday train instances reconstructed from station timetables",
        "version": "0.1.0",
        "generatedAt": now_iso(),
        "service_date": args.service_date,
        "source": {
            "railIndexUrl": RAIL_INDEX_URL,
            "operatorName": OPERATOR_NAME,
            "sourceFeedKey": SOURCE_FEED_KEY,
        },
        "train_instances": sorted(trains, key=lambda item: item["service_instance_id"]),
    }
    audit = {
        "schema": "onichase.v4.osaka_metro_official_train_instances_audit.v1",
        "generatedAt": now_iso(),
        "serviceDate": args.service_date,
        "operatorName": OPERATOR_NAME,
        "linePageCount": len(line_links),
        "stationPageCount": len(station_pages),
        "directionTimetablePageCount": len(direction_links),
        "trainInstanceCount": len(trains),
        "stopTimeCount": sum(len(train.get("stop_times") or []) for train in trains),
        "lineTrainCounts": dict(sorted(line_counts.items())),
        "reconstructedDirectionCounts": dict(sorted(reconstructed_counts.items())),
        "stationMatchMethods": dict(sorted(match_methods.items())),
        "unmatchedStopSample": unmatched_samples,
        "stationPageErrors": station_page_errors[:30],
        "timetablePageErrors": timetable_page_errors[:50],
        "stationOrderCounts": {code: len(stations) for code, stations in sorted(station_orders.items())},
    }
    write_json(args.output, output)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(trains)} trains")
    print(
        f"Wrote {args.audit_output}: timetable_pages={len(direction_links)} "
        f"unmatched_samples={len(unmatched_samples)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
