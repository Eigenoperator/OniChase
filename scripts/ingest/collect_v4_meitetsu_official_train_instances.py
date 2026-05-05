#!/usr/bin/env python3
"""Collect v4 weekday train instances from Meitetsu's official timetable site."""

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

from collect_v4_gtfs_train_instances import (
    V4StationMatcher,
    haversine_m,
    load_json,
    normalize_name,
    normalize_name_variants,
    write_json,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_LINE_INVENTORY = ROOT / "data" / "v4_nationwide_line_inventory.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_meitetsu_official_cache"
DEFAULT_OUTPUT = ROOT / "data" / "v4_meitetsu_official_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_meitetsu_official_train_instances_audit.json"
DEFAULT_SERVICE_DATE = "2026-04-27"

OPERATOR_ID = "meitetsu"
OPERATOR_NAME = "名古屋鉄道"
BASE = "https://trainbus.meitetsu.co.jp"
SEARCH_STATIONS_URL = BASE + "/meitetsu-transfer/pc/extif/SearchNodeListIF"
ROUTE_LIST_URL = BASE + "/meitetsu-transfer/pc/extif/SearchDiagramFromNtjStopIdIF"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cache_path(cache_dir: Path, namespace: str, key: str, suffix: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return cache_dir / namespace / f"{digest}{suffix}"


def fetch_bytes_cached(url: str, cache_dir: Path, namespace: str, suffix: str, refresh: bool, timeout: int = 60) -> bytes:
    path = cache_path(cache_dir, namespace, url, suffix)
    if path.exists() and not refresh:
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/json,*/*",
            "Referer": "https://www.meitetsu.co.jp/",
            "User-Agent": "Mozilla/5.0 (compatible; OniChase-v4-meitetsu-official-collector/0.1)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    path.write_bytes(raw)
    return raw


def strip_tags(value: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def strip_station_code(value: str) -> str:
    text = strip_tags(value)
    return re.sub(r"\([A-Z]{1,3}\d{1,2}\)$", "", text).strip()


def parse_hhmm(value: str) -> str | None:
    text = strip_tags(value).replace("：", ":")
    match = re.search(r"(\d{1,2})\s*:\s*(\d{2})", text)
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"


def minutes(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    hour_text, minute_text = value.split(":", 1)
    try:
        total = int(hour_text) * 60 + int(minute_text)
    except ValueError:
        return None
    if total < 3 * 60:
        total += 24 * 60
    return total


class OperatorPhysicalIndex:
    def __init__(self, physical_map: dict[str, Any], line_inventory: dict[str, Any]) -> None:
        self.by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.line_ids: dict[str, str] = {}
        self.all_line_ids: dict[tuple[str, str], str] = {}
        self.physical_lines: set[str] = set()
        self.group_reps: dict[str, dict[str, Any]] = {}
        for line in line_inventory.get("lines", []):
            operator_name = str(line.get("operatorName") or "")
            line_name = str(line.get("lineName") or "")
            if operator_name and line_name:
                self.all_line_ids[(operator_name, line_name)] = str(line.get("id") or line_name)
            if line.get("operatorName") != OPERATOR_NAME:
                continue
            if line_name:
                self.line_ids[line_name] = str(line.get("id") or line_name)
                self.physical_lines.add(line_name)
        for station in physical_map.get("physicalStations", []):
            if station.get("operatorName") != OPERATOR_NAME:
                continue
            for key in normalize_name_variants(station.get("nameJa") or ""):
                self.by_name[key].append(station)
            group_id = str(station.get("stationGroupId") or "")
            if group_id and group_id not in self.group_reps:
                self.group_reps[group_id] = {
                    "stationGroupId": group_id,
                    "nameJa": station.get("nameJa"),
                    "lat": station.get("lat"),
                    "lon": station.get("lon"),
                }

    def candidates(self, station_name: str) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for key in normalize_name_variants(strip_station_code(station_name)):
            for station in self.by_name.get(key, []):
                station_id = str(station.get("id") or "")
                if station_id in seen:
                    continue
                seen.add(station_id)
                output.append(station)
        return output

    def line_id(self, line_name: str | None) -> str | None:
        if not line_name:
            return None
        return self.line_ids.get(line_name) or line_name

    def line_id_for(self, operator_name: str | None, line_name: str | None) -> str | None:
        if not line_name:
            return None
        if operator_name:
            return self.all_line_ids.get((operator_name, line_name)) or line_name
        return self.line_id(line_name)


THROUGH_LINE_HINTS = {
    "名古屋市営鶴舞線": ("名古屋市", "3号線(鶴舞線)"),
}


def through_operator_line_hints(source_line_names: list[str]) -> list[tuple[str, str]]:
    # Meitetsu has regular through service with the Nagoya Municipal Tsurumai
    # Line.  Some TrainDiagram pages still label those trains by the Meitetsu
    # side (e.g. 犬山線), so keep this as a standing fallback for otherwise
    # ambiguous subway-only stop names such as 原 and 丸の内.
    hints: list[tuple[str, str]] = [("名古屋市", "3号線(鶴舞線)")]
    for name in source_line_names:
        hint = THROUGH_LINE_HINTS.get(name)
        if hint and hint not in hints:
            hints.append(hint)
    return hints


def score_candidate(
    candidate: dict[str, Any],
    source_lines: set[str],
    previous_choice: dict[str, Any] | None,
    previous_lines: set[str],
    next_lines: set[str],
) -> tuple[int, str, str]:
    line = str(candidate.get("lineName") or "")
    group_id = str(candidate.get("stationGroupId") or "")
    score = 0
    if line in source_lines:
        score += 5
    if line in previous_lines:
        score += 7
    if line in next_lines:
        score += 7
    if previous_choice:
        if line == previous_choice.get("lineName"):
            score += 10
        if group_id == previous_choice.get("stationGroupId"):
            score += 4
    return (score, line, group_id)


def attach_station_matches(
    rows: list[dict[str, Any]],
    matcher: V4StationMatcher,
    physical_index: OperatorPhysicalIndex,
    source_lines: set[str],
    through_hints: list[tuple[str, str]] | None = None,
) -> tuple[list[dict[str, Any]], Counter[str], list[dict[str, Any]]]:
    candidate_lists = [physical_index.candidates(row["station_name_raw"]) for row in rows]
    candidate_line_sets = [{str(candidate.get("lineName") or "") for candidate in candidates} for candidates in candidate_lists]
    matched_rows: list[dict[str, Any]] = []
    match_methods: Counter[str] = Counter()
    unmatched: list[dict[str, Any]] = []
    previous_choice: dict[str, Any] | None = None
    visit_counts: Counter[str] = Counter()

    for index, row in enumerate(rows):
        candidates = candidate_lists[index]
        choice: dict[str, Any] | None = None
        match_method = "unmatched"
        if candidates:
            previous_lines = candidate_line_sets[index - 1] if index > 0 else set()
            next_lines = candidate_line_sets[index + 1] if index + 1 < len(candidate_line_sets) else set()
            choice = max(
                candidates,
                key=lambda candidate: score_candidate(candidate, source_lines, previous_choice, previous_lines, next_lines),
            )
            match_method = "meitetsu_name_context"
        else:
            for hint_operator, hint_line in through_hints or []:
                fallback = matcher.match(
                    operator_name=hint_operator,
                    line_name=hint_line,
                    stop_name=strip_station_code(row["station_name_raw"]),
                    stop_lat=None,
                    stop_lon=None,
                )
                if fallback.get("matched"):
                    choice = {
                        "id": fallback["physicalStationId"],
                        "stationGroupId": fallback["stationGroupId"],
                        "operatorName": hint_operator,
                        "lineName": hint_line,
                    }
                    match_method = fallback["method"]
                    break

        if not choice:
            fallback = matcher.match(
                operator_name=OPERATOR_NAME,
                line_name=None,
                stop_name=strip_station_code(row["station_name_raw"]),
                stop_lat=None,
                stop_lon=None,
            )
            if fallback.get("matched"):
                choice = {
                    "id": fallback["physicalStationId"],
                    "stationGroupId": fallback["stationGroupId"],
                    "operatorName": None,
                    "lineName": None,
                }
                match_method = fallback["method"]

        if choice:
            station_group_id = str(choice.get("stationGroupId") or "")
            visit_counts[station_group_id] += 1
            operator_name = choice.get("operatorName") or OPERATOR_NAME
            line_name = choice.get("lineName")
            matched = {
                **row,
                "station_id": station_group_id,
                "station_group_id": station_group_id,
                "physical_station_id": choice.get("id"),
                "line_id": physical_index.line_id_for(str(operator_name) if operator_name else None, str(line_name) if line_name else None),
                "line_name": line_name,
                "platform": None,
                "loop_pass_index": visit_counts[station_group_id],
                "match_method": match_method,
                "match_distance_m": None,
            }
            previous_choice = choice
        else:
            fallback_id = "MEITETSU_UNMATCHED_" + hashlib.sha1(row["station_name_raw"].encode("utf-8")).hexdigest()[:12]
            matched = {
                **row,
                "station_id": fallback_id,
                "station_group_id": None,
                "physical_station_id": None,
                "line_id": None,
                "line_name": None,
                "platform": None,
                "loop_pass_index": None,
                "match_method": "unmatched",
                "match_distance_m": None,
            }
            unmatched.append({"stationName": row["station_name_raw"], "matchMethod": "unmatched"})
        match_methods[matched["match_method"]] += 1
        matched_rows.append(matched)
    return matched_rows, match_methods, unmatched


def station_search_url(name: str) -> str:
    query = urllib.parse.urlencode({"limit": 20, "offset": 0, "company": "00000149", "word": name})
    return f"{SEARCH_STATIONS_URL}?{query}"


def route_list_url(ntj_stop_id: str) -> str:
    return f"{ROUTE_LIST_URL}?ntjStopId={urllib.parse.quote(ntj_stop_id)}"


def best_station_hit(rep: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any] | None:
    name_key = normalize_name(str(rep.get("nameJa") or ""))
    station_hits = [hit for hit in hits if hit.get("type") == "station"]
    filtered = [
        hit for hit in station_hits
        if normalize_name(strip_station_code(str(hit.get("name") or ""))) == name_key
    ] or [
        hit for hit in station_hits
        if normalize_name(strip_station_code(str(hit.get("name") or ""))).startswith(name_key)
        or name_key.startswith(normalize_name(strip_station_code(str(hit.get("name") or ""))))
    ]
    if not filtered:
        return None
    lat = float(rep["lat"])
    lon = float(rep["lon"])
    return min(
        filtered,
        key=lambda hit: haversine_m(lat, lon, float(hit.get("lat") or 0), float(hit.get("lon") or 0)),
    )


def collect_station_ids(
    physical_index: OperatorPhysicalIndex,
    cache_dir: Path,
    refresh: bool,
    workers: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    reps = sorted(physical_index.group_reps.values(), key=lambda item: (str(item["nameJa"]), str(item["stationGroupId"])))
    station_ids: dict[str, dict[str, Any]] = {}
    audits: list[dict[str, Any]] = []

    def fetch_one(rep: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
        url = station_search_url(str(rep["nameJa"]))
        try:
            raw = fetch_bytes_cached(url, cache_dir, "station_search", ".json", refresh=refresh)
            data = json.loads(raw.decode("utf-8"))
            hit = best_station_hit(rep, data.get("items") or [])
            return rep, hit, None
        except Exception as exc:  # noqa: BLE001
            return rep, None, f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(fetch_one, rep) for rep in reps]
        for index, future in enumerate(as_completed(futures), start=1):
            rep, hit, error = future.result()
            if hit:
                station_ids[str(rep["stationGroupId"])] = {
                    "stationGroupId": rep["stationGroupId"],
                    "stationName": rep["nameJa"],
                    "ntjStopId": hit["id"],
                    "ntjName": hit["name"],
                    "lat": hit.get("lat"),
                    "lon": hit.get("lon"),
                }
            audits.append(
                {
                    "stationGroupId": rep["stationGroupId"],
                    "stationName": rep["nameJa"],
                    "matched": bool(hit),
                    "ntjStopId": hit.get("id") if hit else None,
                    "ntjName": hit.get("name") if hit else None,
                    "error": error,
                }
            )
            if index % 50 == 0 or index == len(futures):
                print(f"  station id search {index}/{len(futures)}; matched={len(station_ids)}", flush=True)
    return station_ids, audits


def extract_direction_links(page_html: str, source_station: dict[str, Any]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for match in re.finditer(r"""<a\s+href=["'](?P<href>[^"']*TrainDiagram\?[^"']+)["'][^>]*>(?P<label>.*?)</a>""", page_html, flags=re.IGNORECASE | re.DOTALL):
        before = page_html[: match.start()]
        li_start = before.rfind("<li")
        context = before[li_start:] if li_start >= 0 else before
        dt_matches = re.findall(r"<dt[^>]*>(.*?)</dt>", context, flags=re.IGNORECASE | re.DOTALL)
        line_name = strip_tags(dt_matches[-1]) if dt_matches else None
        direction_name = strip_tags(match.group("label"))
        url = urllib.parse.urljoin(BASE, html.unescape(match.group("href")))
        links.append(
            {
                "url": url,
                "lineName": line_name,
                "directionName": direction_name,
                "sourceStationGroupId": source_station["stationGroupId"],
                "sourceStationName": source_station["stationName"],
                "ntjStopId": source_station["ntjStopId"],
            }
        )
    return links


def collect_direction_links(
    station_ids: dict[str, dict[str, Any]],
    cache_dir: Path,
    refresh: bool,
    workers: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    directions: dict[str, dict[str, Any]] = {}
    audits: list[dict[str, Any]] = []
    stations = list(station_ids.values())

    def fetch_one(station: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], str | None]:
        url = route_list_url(str(station["ntjStopId"]))
        try:
            raw = fetch_bytes_cached(url, cache_dir, "route_list", ".html", refresh=refresh)
            return station, extract_direction_links(raw.decode("utf-8", errors="replace"), station), None
        except Exception as exc:  # noqa: BLE001
            return station, [], f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(fetch_one, station) for station in stations]
        for index, future in enumerate(as_completed(futures), start=1):
            station, links, error = future.result()
            for link in links:
                directions.setdefault(link["url"], link)
            audits.append(
                {
                    "stationName": station["stationName"],
                    "ntjStopId": station["ntjStopId"],
                    "directionLinkCount": len(links),
                    "error": error,
                }
            )
            if index % 50 == 0 or index == len(futures):
                print(f"  route-list pages {index}/{len(futures)}; unique directions={len(directions)}", flush=True)
    return directions, audits


def canonical_train_link(href: str, base_url: str) -> tuple[str, str] | None:
    absolute = urllib.parse.urljoin(base_url, html.unescape(href))
    parsed = urllib.parse.urlparse(absolute)
    if "TrainRouteTimetable" not in parsed.path:
        return None
    params = urllib.parse.parse_qs(parsed.query)
    operation = (params.get("operation") or [""])[0]
    datetime_value = (params.get("datetime") or [""])[0]
    if not operation or not datetime_value.startswith(DEFAULT_SERVICE_DATE):
        return None
    return f"{operation}|{DEFAULT_SERVICE_DATE}", absolute


def extract_train_links(page_html: str, page_url: str, direction: dict[str, Any]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for match in re.finditer(r"""href=["'](?P<href>[^"']*TrainRouteTimetable\?[^"']+)["']""", page_html, flags=re.IGNORECASE):
        canonical = canonical_train_link(match.group("href"), page_url)
        if not canonical:
            continue
        key, url = canonical
        links.append(
            {
                "key": key,
                "url": url,
                "sourceLineName": direction.get("lineName"),
                "sourceDirectionName": direction.get("directionName"),
                "sourceStationName": direction.get("sourceStationName"),
            }
        )
    return links


def collect_train_links(
    directions: dict[str, dict[str, Any]],
    cache_dir: Path,
    refresh: bool,
    workers: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    trains: dict[str, dict[str, Any]] = {}
    audits: list[dict[str, Any]] = []
    direction_items = list(directions.values())

    def fetch_one(direction: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], str | None]:
        url = str(direction["url"])
        try:
            raw = fetch_bytes_cached(url, cache_dir, "diagram", ".html", refresh=refresh)
            return direction, extract_train_links(raw.decode("utf-8", errors="replace"), url, direction), None
        except Exception as exc:  # noqa: BLE001
            return direction, [], f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(fetch_one, direction) for direction in direction_items]
        for index, future in enumerate(as_completed(futures), start=1):
            direction, links, error = future.result()
            for link in links:
                item = trains.setdefault(
                    link["key"],
                    {
                        "key": link["key"],
                        "url": link["url"],
                        "sourceLineNames": set(),
                        "sourceDirectionNames": set(),
                        "sourceStationNames": set(),
                    },
                )
                if link.get("sourceLineName"):
                    item["sourceLineNames"].add(link["sourceLineName"])
                if link.get("sourceDirectionName"):
                    item["sourceDirectionNames"].add(link["sourceDirectionName"])
                if link.get("sourceStationName"):
                    item["sourceStationNames"].add(link["sourceStationName"])
            audits.append(
                {
                    "url": direction["url"],
                    "lineName": direction.get("lineName"),
                    "directionName": direction.get("directionName"),
                    "trainLinkCount": len(links),
                    "error": error,
                }
            )
            if index % 100 == 0 or index == len(futures):
                print(f"  diagram pages {index}/{len(futures)}; unique train keys={len(trains)}", flush=True)

    normalized: dict[str, dict[str, Any]] = {}
    for key, item in trains.items():
        normalized[key] = {
            **item,
            "sourceLineNames": sorted(item["sourceLineNames"]),
            "sourceDirectionNames": sorted(item["sourceDirectionNames"]),
            "sourceStationNames": sorted(item["sourceStationNames"]),
        }
    return normalized, audits


def parse_train_header(page_html: str) -> dict[str, str | None]:
    subject_match = re.search(r"""<h1[^>]+id=["']subject["'][^>]*>(.*?)</h1>""", page_html, flags=re.IGNORECASE | re.DOTALL)
    subject = strip_tags(subject_match.group(1)) if subject_match else ""
    line_name = None
    train_type = None
    headsign = None
    departure = None
    match = re.search(r"路線時刻表\s+(.+?)\((.+?)\)\s+(.+?)行\s+(\d{1,2}:\d{2})", subject)
    if match:
        line_name = match.group(1).strip()
        train_type = match.group(2).strip()
        headsign = strip_station_code(match.group(3)).strip()
        departure = match.group(4)
    return {
        "subject": subject or None,
        "lineName": line_name,
        "trainType": train_type,
        "headsign": headsign,
        "departure": departure,
    }


def parse_stop_rows(page_html: str) -> list[dict[str, Any]]:
    match = re.search(r"""<div[^>]+id=["']railroad-matrix["'][^>]*>(.*?)</div>\s*</div>""", page_html, flags=re.IGNORECASE | re.DOTALL)
    segment = match.group(1) if match else page_html
    rows: list[dict[str, Any]] = []
    pattern = re.compile(r"<span[^>]*>(?P<time>.*?)</span>\s*<strong[^>]*>(?P<station>.*?)</strong>", flags=re.IGNORECASE | re.DOTALL)
    for index, item in enumerate(pattern.finditer(segment), start=1):
        time_text = strip_tags(item.group("time"))
        station_name = strip_station_code(item.group("station"))
        hhmm = parse_hhmm(time_text)
        if not station_name or not hhmm:
            continue
        is_departure = "発" in time_text or index == 1
        is_arrival = "着" in time_text or not is_departure
        rows.append(
            {
                "sequence": len(rows) + 1,
                "station_name_raw": station_name,
                "arrival_hhmm": hhmm if is_arrival else None,
                "departure_hhmm": hhmm if is_departure else hhmm,
            }
        )
    return rows


def primary_line(stop_times: list[dict[str, Any]]) -> tuple[str | None, str | None, list[str]]:
    counts = Counter(str(stop.get("line_name") or "") for stop in stop_times if stop.get("line_name"))
    if not counts:
        return None, None, []
    line_name, _count = counts.most_common(1)[0]
    line_names = sorted(counts)
    line_id = next((str(stop.get("line_id")) for stop in stop_times if stop.get("line_name") == line_name and stop.get("line_id")), line_name)
    return line_id, line_name, line_names


def parse_train_detail(
    item: dict[str, Any],
    page_html: str,
    matcher: V4StationMatcher,
    physical_index: OperatorPhysicalIndex,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    header = parse_train_header(page_html)
    rows = parse_stop_rows(page_html)
    source_lines = {line for line in item.get("sourceLineNames", []) if line in physical_index.physical_lines}
    through_hints = through_operator_line_hints(item.get("sourceLineNames", []))
    if header.get("lineName") in physical_index.physical_lines:
        source_lines.add(str(header["lineName"]))
    stop_times, match_methods, unmatched = attach_station_matches(rows, matcher, physical_index, source_lines, through_hints)
    primary_line_id, primary_line_name, line_names = primary_line(stop_times)
    if header.get("lineName") in physical_index.physical_lines:
        line_name = str(header["lineName"])
        line_id = physical_index.line_id(line_name)
    elif source_lines:
        line_name = sorted(source_lines)[0]
        line_id = physical_index.line_id(line_name)
    else:
        line_id, line_name = primary_line_id, primary_line_name
    operation, service_date = item["key"].split("|", 1)
    service_instance_id = f"meitetsu_official:{operation}:{service_date}"
    train_type = header.get("trainType")
    headsign = header.get("headsign")
    service_name = " ".join(part for part in [str(train_type or ""), f"{headsign}行き" if headsign else ""] if part).strip()
    if not service_name:
        service_name = line_name or "名鉄列車"
    matched_stop_count = sum(1 for stop in stop_times if stop.get("station_group_id"))
    train = None
    if len(stop_times) >= 2 and matched_stop_count >= 2:
        train = {
            "train_number": service_instance_id,
            "service_instance_id": service_instance_id,
            "source_trip_id": item["key"],
            "operator_id": OPERATOR_ID,
            "operator_name": OPERATOR_NAME,
            "service_name": service_name,
            "display_name": service_name,
            "headsign": headsign or "",
            "train_type": train_type,
            "route_color": None,
            "line_id": line_id,
            "line_name": line_name,
            "physical_line_names": line_names,
            "source_feed_key": "meitetsu_official_2026-04-27",
            "source_url": item["url"],
            "source_line_names": item.get("sourceLineNames", []),
            "stop_times": stop_times,
        }
    audit = {
        "key": item["key"],
        "url": item["url"],
        "parsed": train is not None,
        "stopCount": len(stop_times),
        "matchedStopCount": matched_stop_count,
        "unmatchedStopCount": len(unmatched),
        "unmatchedStops": unmatched[:20],
        "matchMethods": dict(sorted(match_methods.items())),
        "lineNames": line_names,
        "header": header,
        "sourceLineNames": item.get("sourceLineNames", []),
        "sourceStationNamesSample": item.get("sourceStationNames", [])[:8],
    }
    return train, audit


def collect_trains(
    train_links: dict[str, dict[str, Any]],
    cache_dir: Path,
    refresh: bool,
    workers: int,
    max_trains: int,
    matcher: V4StationMatcher,
    physical_index: OperatorPhysicalIndex,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    items = list(sorted(train_links.values(), key=lambda item: item["key"]))
    if max_trains:
        items = items[:max_trains]
    trains: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    fetch_errors: list[dict[str, Any]] = []

    def fetch_one(item: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
        try:
            raw = fetch_bytes_cached(str(item["url"]), cache_dir, "train_detail", ".html", refresh=refresh)
            train, audit = parse_train_detail(item, raw.decode("utf-8", errors="replace"), matcher, physical_index)
            return train, audit, None
        except Exception as exc:  # noqa: BLE001
            return None, None, {"key": item["key"], "url": item["url"], "error": f"{type(exc).__name__}: {exc}"}

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(fetch_one, item) for item in items]
        for index, future in enumerate(as_completed(futures), start=1):
            train, audit, error = future.result()
            if train:
                trains.append(train)
            if audit:
                audits.append(audit)
            if error:
                fetch_errors.append(error)
            if index % 250 == 0 or index == len(futures):
                print(f"  train details {index}/{len(futures)}; parsed trains={len(trains)}", flush=True)
    return sorted(trains, key=lambda item: item["service_instance_id"]), audits, fetch_errors


def add_minutes_hhmm(value: str, delta: int) -> str:
    hour, minute = [int(part) for part in value.split(":", 1)]
    total = hour * 60 + minute + delta
    return f"{(total // 60) % 24:02d}:{total % 60:02d}"


def parse_weekday_diagram_departures(page_html: str) -> list[str]:
    departures: list[str] = []
    row_pattern = re.compile(
        r"""<tr class=["']l2["']>.*?<th class=["']hour["']>\s*(?P<hour>\d{1,2})\s*</th>.*?<td class=["']wkd["']>(?P<td>.*?)</td>""",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for row in row_pattern.finditer(page_html):
        hour = int(row.group("hour"))
        for minute_text in re.findall(r"""<span aria-hidden=["']true["']>\s*(\d{1,2})\s*</span>""", row.group("td")):
            departures.append(f"{hour:02d}:{int(minute_text):02d}")
    return departures


def build_chikko_shuttle_trains(
    directions: dict[str, dict[str, Any]],
    cache_dir: Path,
    refresh: bool,
    matcher: V4StationMatcher,
    physical_index: OperatorPhysicalIndex,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trains: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for direction in directions.values():
        if direction.get("lineName") != "築港線":
            continue
        origin = str(direction.get("sourceStationName") or "")
        destination = str(direction.get("directionName") or "").replace("ゆき", "").replace("方面", "").strip()
        if not origin or not destination:
            continue
        raw = fetch_bytes_cached(str(direction["url"]), cache_dir, "diagram", ".html", refresh=refresh)
        departures = parse_weekday_diagram_departures(raw.decode("utf-8", errors="replace"))
        built = 0
        for departure in departures:
            arrival = add_minutes_hhmm(departure, 3)
            rows = [
                {
                    "sequence": 1,
                    "station_name_raw": origin,
                    "arrival_hhmm": None,
                    "departure_hhmm": departure,
                },
                {
                    "sequence": 2,
                    "station_name_raw": destination,
                    "arrival_hhmm": arrival,
                    "departure_hhmm": arrival,
                },
            ]
            stop_times, match_methods, unmatched = attach_station_matches(
                rows,
                matcher,
                physical_index,
                {"築港線"},
                through_hints=[],
            )
            if unmatched or sum(1 for stop in stop_times if stop.get("station_group_id")) < 2:
                audits.append(
                    {
                        "url": direction["url"],
                        "origin": origin,
                        "destination": destination,
                        "departure": departure,
                        "built": False,
                        "unmatchedStops": unmatched,
                        "matchMethods": dict(sorted(match_methods.items())),
                    }
                )
                continue
            key = f"chikko:{origin}:{destination}:{departure}"
            trains.append(
                {
                    "train_number": f"meitetsu_official:{key}",
                    "service_instance_id": f"meitetsu_official:{key}:2026-04-27",
                    "source_trip_id": key,
                    "operator_id": OPERATOR_ID,
                    "operator_name": OPERATOR_NAME,
                    "service_name": f"普通 {destination}行き",
                    "display_name": f"普通 {destination}行き",
                    "headsign": destination,
                    "train_type": "普通",
                    "route_color": None,
                    "line_id": physical_index.line_id("築港線"),
                    "line_name": "築港線",
                    "physical_line_names": ["築港線"],
                    "source_feed_key": "meitetsu_official_2026-04-27",
                    "source_url": direction["url"],
                    "source_line_names": ["築港線"],
                    "stop_times": stop_times,
                }
            )
            built += 1
        audits.append(
            {
                "url": direction["url"],
                "origin": origin,
                "destination": destination,
                "departureCount": len(departures),
                "builtTrainCount": built,
            }
        )
    return trains, audits


def audit_train_integrity(trains: list[dict[str, Any]]) -> dict[str, Any]:
    duplicate_ids = [train_id for train_id, count in Counter(train["service_instance_id"] for train in trains).items() if count > 1]
    short = [train["service_instance_id"] for train in trains if len(train.get("stop_times") or []) < 2]
    bad_order: list[dict[str, Any]] = []
    unmatched_stops: list[dict[str, Any]] = []
    line_counts: Counter[str] = Counter()
    for train in trains:
        previous = -1
        for stop in train.get("stop_times") or []:
            if stop.get("line_name"):
                line_counts[str(stop["line_name"])] += 1
            if not stop.get("station_group_id"):
                unmatched_stops.append(
                    {
                        "serviceInstanceId": train["service_instance_id"],
                        "stationNameRaw": stop.get("station_name_raw"),
                    }
                )
            current = minutes(stop.get("departure_hhmm") or stop.get("arrival_hhmm"))
            if current is None:
                continue
            if current < previous:
                bad_order.append(
                    {
                        "serviceInstanceId": train["service_instance_id"],
                        "stationNameRaw": stop.get("station_name_raw"),
                        "previousMinutes": previous,
                        "currentMinutes": current,
                    }
                )
            previous = max(previous, current)
    return {
        "duplicateServiceInstanceIdCount": len(duplicate_ids),
        "duplicateServiceInstanceIdsSample": sorted(duplicate_ids)[:20],
        "shortTrainInstanceCount": len(short),
        "shortTrainInstancesSample": sorted(short)[:20],
        "badTimeOrderCount": len(bad_order),
        "badTimeOrderSample": bad_order[:20],
        "unmatchedStopCount": len(unmatched_stops),
        "unmatchedStopsSample": unmatched_stops[:20],
        "lineStopCounts": dict(sorted(line_counts.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--line-inventory", type=Path, default=DEFAULT_LINE_INVENTORY)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--service-date", default=DEFAULT_SERVICE_DATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--max-trains", type=int, default=0)
    args = parser.parse_args()

    if args.service_date != DEFAULT_SERVICE_DATE:
        raise SystemExit("This first Meitetsu collector pass is pinned to 2026-04-27 page links.")

    physical_map = load_json(args.physical_map)
    line_inventory = load_json(args.line_inventory)
    matcher = V4StationMatcher(physical_map)
    physical_index = OperatorPhysicalIndex(physical_map, line_inventory)

    print("Searching Meitetsu station ids...", flush=True)
    station_ids, station_audits = collect_station_ids(physical_index, args.cache_dir, args.refresh_cache, args.workers)
    print("Collecting Meitetsu route direction links...", flush=True)
    directions, direction_audits = collect_direction_links(station_ids, args.cache_dir, args.refresh_cache, args.workers)
    print("Collecting Meitetsu train-detail links from diagrams...", flush=True)
    train_links, diagram_audits = collect_train_links(directions, args.cache_dir, args.refresh_cache, args.workers)
    print(f"  unique train-detail keys={len(train_links)}", flush=True)
    print("Parsing Meitetsu train details...", flush=True)
    trains, train_audits, fetch_errors = collect_trains(
        train_links,
        args.cache_dir,
        args.refresh_cache,
        args.workers,
        args.max_trains,
        matcher,
        physical_index,
    )
    chikko_trains, chikko_audits = build_chikko_shuttle_trains(
        directions,
        args.cache_dir,
        args.refresh_cache,
        matcher,
        physical_index,
    )
    trains = sorted(trains + chikko_trains, key=lambda item: item["service_instance_id"])

    integrity = audit_train_integrity(trains)
    output = {
        "id": "v4_meitetsu_official_weekday_train_instances_v0_1",
        "label": "V4 weekday train instances collected from Meitetsu official TrainDiagram pages",
        "version": "0.1.0",
        "service_day": args.service_date,
        "source": {"kind": "official_meitetsu_navitime_train_diagram"},
        "station_identity": physical_map.get("identityVersion"),
        "train_instances": trains,
    }
    audit = {
        "schema": "onichase.v4.meitetsu_official_train_instances_audit.v1",
        "generatedAt": now_iso(),
        "serviceDay": args.service_date,
        "operatorName": OPERATOR_NAME,
        "stationGroupCount": len(physical_index.group_reps),
        "matchedStationIdCount": len(station_ids),
        "directionLinkCount": len(directions),
        "trainDetailKeyCount": len(train_links),
        "syntheticChikkoTrainCount": len(chikko_trains),
        "parsedTrainDetailCount": len(train_audits),
        "trainInstanceCount": len(trains),
        "stopTimeCount": sum(len(train["stop_times"]) for train in trains),
        "fetchErrorCount": len(fetch_errors),
        "fetchErrorsSample": fetch_errors[:20],
        "integrity": integrity,
        "stationAuditsSample": station_audits[:50],
        "directionAuditsSample": direction_audits[:50],
        "diagramAuditsSample": diagram_audits[:50],
        "chikkoAudits": chikko_audits,
        "trainAuditsSample": train_audits[:50],
    }
    write_json(args.output, output)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(trains)} train instances")
    print(
        f"Wrote {args.audit_output}: station_ids={len(station_ids)}/{len(physical_index.group_reps)} "
        f"unmatched={integrity['unmatchedStopCount']} bad_order={integrity['badTimeOrderCount']} "
        f"fetch_errors={len(fetch_errors)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
