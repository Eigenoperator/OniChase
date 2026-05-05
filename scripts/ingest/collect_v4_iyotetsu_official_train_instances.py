#!/usr/bin/env python3
"""Collect v4 weekday train instances from Iyotetsu official timetable search.

Iyotetsu publishes PDF timetables, but the PDF layout abbreviates daytime
high-frequency intervals.  The website route search expands those intervals
into concrete weekday departures, so this collector reconstructs stop_times
from the official station-pair search tables instead.
"""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_iyotetsu_official_cache"
DEFAULT_OUTPUT = ROOT / "data" / "v4_iyotetsu_official_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_iyotetsu_official_train_instances_audit.json"
DEFAULT_SERVICE_DATE = "2026-04-27"

BASE = "https://www.iyotetsu.co.jp"
HOMEN_URL = f"{BASE}/rosen/iyotetsu/homen/"
SEARCH_URL = f"{BASE}/rosen/iyotetsu/search/"
OPERATOR_NAME = "伊予鉄道"
SOURCE_FEED_KEY = "iyotetsu_official_route_search_reconstructed"

ROUTE_DEFS: dict[str, dict[str, str]] = {
    "10012": {"display": "環状線", "primaryLine": "城北線"},
    "10013": {"display": "松山市駅線", "primaryLine": "城南線"},
    "10015": {"display": "ＪＲ松山駅前線", "primaryLine": "城南線"},
    "10016": {"display": "本町線", "primaryLine": "本町線"},
    "10021": {"display": "高浜・横河原線", "primaryLine": "高浜線"},
    "10022": {"display": "郡中線", "primaryLine": "郡中線"},
}

STATION_ALIASES = {
    "ＪＲ松山駅前": ["JR松山駅前"],
    "本町6丁目": ["本町六丁目"],
    "本町5丁目": ["本町五丁目"],
    "本町4丁目": ["本町四丁目"],
    "本町3丁目": ["本町三丁目"],
    "本町1丁目": ["本町一丁目"],
    "大手町": ["大手町駅前"],
    "大手町駅前": ["大手町"],
    "松山市": ["松山市駅"],
    "松山市駅": ["松山市"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cache_path(cache_dir: Path, namespace: str, key: str, suffix: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return cache_dir / namespace / f"{digest}{suffix}"


def fetch_post_cached(
    url: str,
    params: dict[str, str],
    cache_dir: Path,
    namespace: str,
    refresh: bool,
    timeout: int = 90,
) -> str:
    key = url + "?" + urllib.parse.urlencode(sorted(params.items()))
    path = cache_path(cache_dir, namespace, key, ".html")
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8", errors="replace")
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(params).encode("utf-8"),
        headers={
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (compatible; OniChase-v4-iyotetsu-official-collector/0.1)",
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
    text = re.sub(r"<ruby>.*?<rt>.*?</rt>.*?</ruby>", lambda m: re.sub(r"<rt>.*?</rt>", "", m.group(0), flags=re.DOTALL), text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_station_name(value: str) -> str:
    text = strip_tags(value)
    text = text.replace("ＪＲ", "JR")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"駅$", "", text)
    return text.strip()


def parse_hhmm(value: str | None) -> str | None:
    if not value:
        return None
    text = strip_tags(value).replace("：", ":")
    match = re.search(r"(\d{1,2})\s*:\s*(\d{2})", text)
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"


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


class IyotetsuPhysicalIndex:
    def __init__(self, physical_map: dict[str, Any], line_inventory: dict[str, Any]) -> None:
        self.matcher = V4StationMatcher(physical_map)
        self.station_by_id = {station["id"]: station for station in physical_map["physicalStations"]}
        self.line_id_by_operator_line: dict[tuple[str, str], str] = {}
        self.line_color_by_operator_line: dict[tuple[str, str], str] = {}
        self.station_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for line in line_inventory.get("lines", []):
            operator_name = str(line.get("operatorName") or "")
            line_name = str(line.get("lineName") or "")
            self.line_id_by_operator_line[(operator_name, line_name)] = str(line.get("id") or line_name)
            self.line_color_by_operator_line[(operator_name, line_name)] = str(
                line.get("lineColor") or line.get("operatorColor") or "#32BDBB"
            ).lstrip("#")
        for station in physical_map.get("physicalStations", []):
            if station.get("operatorName") != OPERATOR_NAME:
                continue
            for key in normalize_name_variants(station.get("nameJa") or ""):
                self.station_by_name[key].append(station)

    def line_id(self, line_name: str) -> str:
        return self.line_id_by_operator_line.get((OPERATOR_NAME, line_name)) or line_name

    def route_color(self, line_name: str) -> str:
        return self.line_color_by_operator_line.get((OPERATOR_NAME, line_name), "#32BDBB").lstrip("#")

    def station_for_match(self, match: dict[str, Any]) -> dict[str, Any] | None:
        station_id = match.get("physicalStationId")
        if not station_id:
            return None
        return self.station_by_id.get(str(station_id))

    def candidates(self, station_name: str) -> list[dict[str, Any]]:
        aliases = [station_name, *STATION_ALIASES.get(station_name, [])]
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for alias in aliases:
            for key in normalize_name_variants(alias):
                for station in self.station_by_name.get(key, []):
                    station_id = str(station.get("id") or "")
                    if station_id in seen:
                        continue
                    seen.add(station_id)
                    output.append(station)
        return output

    def match_stop(self, station_name: str, preferred_lines: list[str]) -> dict[str, Any]:
        cleaned = clean_station_name(station_name)
        candidates = self.candidates(cleaned)
        if candidates:
            ranked = sorted(
                candidates,
                key=lambda station: (
                    min((preferred_lines.index(station.get("lineName")) for _ in [0] if station.get("lineName") in preferred_lines), default=99),
                    str(station.get("lineName") or ""),
                    str(station.get("stationGroupId") or ""),
                ),
            )
            best = ranked[0]
            return {
                "matched": True,
                "method": "iyotetsu_name_context",
                "stationGroupId": best["stationGroupId"],
                "physicalStationId": best["id"],
                "candidateCount": len(candidates),
            }
        for line_name in preferred_lines:
            match = self.matcher.match(
                operator_name=OPERATOR_NAME,
                line_name=line_name,
                stop_name=cleaned,
                stop_lat=None,
                stop_lon=None,
            )
            if match.get("matched"):
                match["method"] = f"fallback_{line_name}_{match['method']}"
                return match
        return self.matcher.match(OPERATOR_NAME, preferred_lines[0] if preferred_lines else None, cleaned, None, None)


def extract_route_stations(route_id: str, page_html: str) -> list[dict[str, str]]:
    match = re.search(r"""<select\s+name=["']josha["'][^>]*>(?P<body>.*?)</select>""", page_html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for option in re.finditer(r"""<option\s+value=["'](?P<id>\d+)["'][^>]*>(?P<name>.*?)</option>""", match.group("body"), flags=re.IGNORECASE | re.DOTALL):
        station_id = option.group("id")
        name = clean_station_name(option.group("name"))
        if station_id in seen or not name:
            continue
        seen.add(station_id)
        output.append({"siteStationId": station_id, "stationName": name})
    return output


def parse_search_rows(page_html: str, expected_route_name: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    table_match = re.search(
        r"""<table\s+id=["']jikokutable_[^"']+["'][^>]*>(?P<table>.*?)</table>""",
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not table_match:
        return rows
    for row_match in re.finditer(r"<tr[^>]*>(?P<body>.*?)</tr>", table_match.group("table"), flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_match.group("body"), flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 5:
            continue
        departure = parse_hhmm(cells[0])
        arrival = parse_hhmm(cells[1])
        line_name = strip_tags(cells[3])
        headsign = clean_station_name(cells[4])
        if not departure or not arrival:
            continue
        if expected_route_name and expected_route_name not in line_name:
            continue
        rows.append(
            {
                "departure": departure,
                "arrival": arrival,
                "lineName": line_name,
                "headsign": headsign,
            }
        )
    return rows


def fetch_route_stations(route_id: str, cache_dir: Path, refresh: bool) -> list[dict[str, str]]:
    page = fetch_post_cached(
        HOMEN_URL,
        {"rosen1": route_id, "rosen2": route_id},
        cache_dir,
        "route_station_pages",
        refresh,
    )
    return extract_route_stations(route_id, page)


def query_rows(
    origin: dict[str, str],
    destination: dict[str, str],
    expected_route_name: str,
    cache_dir: Path,
    refresh: bool,
) -> list[dict[str, str]]:
    page = fetch_post_cached(
        SEARCH_URL,
        {
            "josha": origin["siteStationId"],
            "kosha": destination["siteStationId"],
            "youbi": "1",
            "hour": "",
            "min": "00",
            "limit": "1200",
        },
        cache_dir,
        "route_search_pages",
        refresh,
    )
    return parse_search_rows(page, expected_route_name)


def directional_patterns(route_id: str, stations: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_name = {station["stationName"]: index for index, station in enumerate(stations)}

    def linear(name: str, seq: list[dict[str, str]], origin_indices: list[int]) -> list[dict[str, Any]]:
        return [{"name": name, "sequence": seq, "originIndices": origin_indices}]

    if route_id == "10021":
        matsuyama = by_name.get("松山市", 9)
        return [
            *linear("takahama_to_yokogawara", stations, [0, matsuyama]),
            *linear("yokogawara_to_takahama", list(reversed(stations)), [0, len(stations) - 1 - matsuyama]),
        ]
    if route_id in {"10013", "10015", "10016", "10022"}:
        return [
            *linear("forward", stations, [0]),
            *linear("reverse", list(reversed(stations)), [0]),
        ]
    if route_id == "10012":
        # The official circular route starts at Mats山市駅.  Keep both loop
        # directions as separate pseudo-linear sequences for reconstruction.
        return [
            *linear("loop_1", stations, [0]),
            *linear("loop_2", [stations[0], stations[1], *list(reversed(stations[2:]))], [0]),
        ]
    return [*linear("forward", stations, [0]), *linear("reverse", list(reversed(stations)), [0])]


def line_preferences(route_id: str, route_display: str, stop_name: str) -> list[str]:
    if route_id == "10021":
        if stop_name in {"高浜", "梅津寺", "港山", "三津", "山西", "西衣山", "衣山", "古町", "大手町"}:
            return ["高浜線", "横河原線", "大手町線"]
        return ["横河原線", "高浜線"]
    if route_id == "10022":
        return ["郡中線"]
    if route_id == "10016":
        if stop_name in {"松山市駅", "松山市"}:
            return ["花園線", "本町線"]
        if stop_name == "南堀端":
            return ["花園線", "城南線", "本町線"]
        return ["本町線", "城南線"]
    if route_id == "10013":
        if stop_name in {"松山市駅", "松山市", "南堀端"}:
            return ["花園線", "城南線"]
        return ["城南線", "連絡線"]
    if route_id == "10015":
        if stop_name in {"JR松山駅前", "大手町駅前", "西堀端"}:
            return ["大手町線", "城南線"]
        return ["城南線", "大手町線", "連絡線"]
    if route_id == "10012":
        if stop_name in {"JR松山駅前", "大手町駅前", "宮田町"}:
            return ["大手町線", "城北線", "城南線"]
        if stop_name in {"古町", "萱町六丁目", "本町六丁目", "木屋町", "高砂町", "清水町", "鉄砲町", "赤十字病院前", "平和通一丁目"}:
            return ["城北線", "連絡線", "城南線"]
        if stop_name in {"上一万"}:
            return ["連絡線", "城南線", "城北線"]
        if stop_name in {"松山市駅", "松山市"}:
            return ["花園線", "城南線"]
        return ["城南線", "城北線"]
    return [ROUTE_DEFS.get(route_id, {}).get("primaryLine", route_display)]


def reconstruct_pattern(
    route_id: str,
    route_display: str,
    pattern: dict[str, Any],
    query_results: dict[tuple[str, str, str], list[dict[str, str]]],
) -> list[dict[str, Any]]:
    sequence: list[dict[str, str]] = pattern["sequence"]
    output: list[dict[str, Any]] = []
    origin_indices: list[int] = pattern["originIndices"]
    for origin_index in origin_indices:
        origin = sequence[origin_index]
        trains_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
        for target_index in range(origin_index + 1, len(sequence)):
            target = sequence[target_index]
            rows = query_results.get((route_id, origin["siteStationId"], target["siteStationId"]), [])
            for row in rows:
                if not row_matches_pattern(route_id, str(pattern["name"]), row):
                    continue
                key = (origin["siteStationId"], row["departure"], row["headsign"])
                train = trains_by_key.setdefault(
                    key,
                    {
                        "routeId": route_id,
                        "routeDisplay": route_display,
                        "patternName": pattern["name"],
                        "originIndex": origin_index,
                        "headsign": row["headsign"],
                        "sourceLineName": row["lineName"],
                        "stops": {
                            origin_index: {
                                "station": origin,
                                "arrival": None,
                                "departure": row["departure"],
                            }
                        },
                    },
                )
                existing = train["stops"].get(target_index)
                if existing is None or (minutes(row["arrival"]) or 0) < (minutes(existing.get("arrival")) or 99999):
                    train["stops"][target_index] = {
                        "station": target,
                        "arrival": row["arrival"],
                        "departure": row["arrival"],
                    }
        output.extend(trains_by_key.values())
    return output


def row_matches_pattern(route_id: str, pattern_name: str, row: dict[str, str]) -> bool:
    """Keep Iyotetsu circular directions from contaminating each other.

    The official search endpoint returns route rows by origin/destination pair.
    For the Matsuyama city loop, both directions can reach many of the same
    downstream stops, so the line label has to be used as the direction guard.
    """
    if route_id != "10012":
        return True
    line_name = str(row.get("lineName") or "")
    if pattern_name == "loop_1":
        return "①番" in line_name or "JR松山駅前" in line_name or "ＪＲ松山駅前" in line_name
    if pattern_name == "loop_2":
        return "②番" in line_name or "大街道" in line_name
    return True


def stop_sort_key(stop: dict[str, Any]) -> int:
    return int(stop["index"])


def merge_continuation_duplicates(raw_trains: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trains = [dict(train) for train in raw_trains]
    for train in trains:
        train["stops"] = dict(train["stops"])
    consumed: set[int] = set()
    ordered = sorted(range(len(trains)), key=lambda i: (trains[i]["routeId"], trains[i]["patternName"], trains[i]["originIndex"]))
    for short_i in ordered:
        if short_i in consumed:
            continue
        short = trains[short_i]
        if short.get("originIndex", 0) == 0:
            continue
        short_stops = short["stops"]
        if len(short_stops) < 2:
            continue
        short_last_index = max(short_stops)
        short_last = short_stops[short_last_index]
        short_origin = short_stops[min(short_stops)]
        best_i: int | None = None
        for long_i in ordered:
            if long_i == short_i or long_i in consumed:
                continue
            long = trains[long_i]
            if long["routeId"] != short["routeId"] or long["patternName"] != short["patternName"]:
                continue
            if long.get("originIndex", 0) >= short.get("originIndex", 0):
                continue
            long_stops = long["stops"]
            long_origin_stop = long_stops.get(short["originIndex"])
            long_last_stop = long_stops.get(short_last_index)
            if not long_origin_stop or not long_last_stop:
                continue
            if long_last_stop.get("arrival") != short_last.get("arrival"):
                continue
            long_origin_minutes = minutes(long_origin_stop.get("arrival") or long_origin_stop.get("departure"))
            short_origin_minutes = minutes(short_origin.get("departure") or short_origin.get("arrival"))
            if long_origin_minutes is None or short_origin_minutes is None:
                continue
            if 0 <= short_origin_minutes - long_origin_minutes <= 8:
                best_i = long_i
                break
        if best_i is None:
            continue
        trains[best_i]["stops"].update(short_stops)
        consumed.add(short_i)
    return [train for index, train in enumerate(trains) if index not in consumed]


def build_train(
    raw_train: dict[str, Any],
    physical_index: IyotetsuPhysicalIndex,
) -> tuple[dict[str, Any] | None, Counter[str], list[dict[str, Any]]]:
    route_id = raw_train["routeId"]
    route_display = raw_train["routeDisplay"]
    primary_line = ROUTE_DEFS[route_id]["primaryLine"]
    match_methods: Counter[str] = Counter()
    unmatched: list[dict[str, Any]] = []
    stop_times: list[dict[str, Any]] = []
    for sequence, (_, raw_stop) in enumerate(sorted(raw_train["stops"].items()), start=1):
        station_name = raw_stop["station"]["stationName"]
        preferred_lines = line_preferences(route_id, route_display, station_name)
        match = physical_index.match_stop(station_name, preferred_lines)
        station = physical_index.station_for_match(match)
        if match.get("matched"):
            match_methods[str(match["method"])] += 1
        else:
            match_methods[str(match.get("method") or "unmatched")] += 1
            if len(unmatched) < 25:
                unmatched.append({"stationName": station_name, "routeId": route_id, "routeDisplay": route_display})
        line_name = str(station.get("lineName") if station else preferred_lines[0])
        stop_times.append(
            {
                "sequence": sequence,
                "station_name_raw": station_name,
                "station_id": match.get("stationGroupId"),
                "station_group_id": match.get("stationGroupId"),
                "physical_station_id": match.get("physicalStationId"),
                "operator_name": OPERATOR_NAME,
                "line_id": physical_index.line_id(line_name),
                "line_name": line_name,
                "arrival_hhmm": raw_stop.get("arrival"),
                "departure_hhmm": raw_stop.get("departure"),
                "match_method": match.get("method"),
            }
        )
    if len(stop_times) < 2:
        return None, match_methods, unmatched
    first_time = stop_times[0].get("departure_hhmm") or stop_times[0].get("arrival_hhmm") or "00:00"
    headsign = raw_train.get("headsign") or stop_times[-1]["station_name_raw"]
    safe_time = first_time.replace(":", "")
    safe_headsign = re.sub(r"[^0-9A-Za-zぁ-んァ-ン一-龥]+", "", headsign)
    service_instance_id = f"iyotetsu:{route_id}:{raw_train['patternName']}:{stop_times[0]['station_name_raw']}:{safe_time}:{safe_headsign}"
    train = {
        "train_number": f"{route_display}{safe_time}",
        "service_instance_id": service_instance_id,
        "source_trip_id": service_instance_id,
        "operator_id": OPERATOR_NAME,
        "operator_name": OPERATOR_NAME,
        "service_name": route_display,
        "service_number": safe_time,
        "headsign": headsign,
        "train_type": "普通",
        "route_color": physical_index.route_color(primary_line),
        "line_id": physical_index.line_id(primary_line),
        "line_name": route_display,
        "source_feed_key": SOURCE_FEED_KEY,
        "origin": stop_times[0]["station_name_raw"],
        "destination": headsign,
        "source_timetable_url": SEARCH_URL,
        "first_departure_hhmm": first_time,
        "reconstruction_method": "official_route_search_station_pair_stitch",
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
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    physical_index = IyotetsuPhysicalIndex(load_physical_map(args.physical_map), load_json(args.line_inventory))
    route_stations: dict[str, list[dict[str, str]]] = {}
    station_errors: list[dict[str, str]] = []
    for route_id in ROUTE_DEFS:
        try:
            route_stations[route_id] = fetch_route_stations(route_id, args.cache_dir, args.refresh)
        except Exception as exc:
            station_errors.append({"routeId": route_id, "error": str(exc)})

    query_tasks: dict[tuple[str, str, str], tuple[dict[str, str], dict[str, str], str]] = {}
    for route_id, stations in route_stations.items():
        route_display = ROUTE_DEFS[route_id]["display"]
        for pattern in directional_patterns(route_id, stations):
            sequence: list[dict[str, str]] = pattern["sequence"]
            for origin_index in pattern["originIndices"]:
                origin = sequence[origin_index]
                for target_index in range(origin_index + 1, len(sequence)):
                    target = sequence[target_index]
                    if origin["siteStationId"] == target["siteStationId"]:
                        continue
                    query_tasks[(route_id, origin["siteStationId"], target["siteStationId"])] = (origin, target, route_display)

    query_results: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    query_errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(query_rows, origin, target, route_display, args.cache_dir, args.refresh): key
            for key, (origin, target, route_display) in query_tasks.items()
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                query_results[key] = future.result()
            except Exception as exc:
                query_errors.append({"routeId": key[0], "origin": key[1], "destination": key[2], "error": str(exc)})

    raw_trains: list[dict[str, Any]] = []
    for route_id, stations in route_stations.items():
        route_display = ROUTE_DEFS[route_id]["display"]
        for pattern in directional_patterns(route_id, stations):
            raw_trains.extend(reconstruct_pattern(route_id, route_display, pattern, query_results))
    merged_raw_trains = merge_continuation_duplicates(raw_trains)

    trains: list[dict[str, Any]] = []
    match_methods: Counter[str] = Counter()
    unmatched_samples: list[dict[str, Any]] = []
    for raw_train in merged_raw_trains:
        train, methods, unmatched = build_train(raw_train, physical_index)
        match_methods.update(methods)
        unmatched_samples.extend(unmatched)
        if train:
            trains.append(train)

    duplicate_ids = [item for item, count in Counter(train["service_instance_id"] for train in trains).items() if count > 1]
    line_counts = Counter(train["line_name"] for train in trains)
    stop_count_distribution = Counter(str(len(train["stop_times"])) for train in trains)
    audit = {
        "schema": "onichase.v4.iyotetsu_official_train_instances_audit.v1",
        "generatedAt": now_iso(),
        "serviceDate": args.service_date,
        "source": {
            "homenUrl": HOMEN_URL,
            "searchUrl": SEARCH_URL,
            "sourceFeedKey": SOURCE_FEED_KEY,
        },
        "counts": {
            "routeCount": len(route_stations),
            "queryTaskCount": len(query_tasks),
            "queryErrorCount": len(query_errors),
            "rawTrainCount": len(raw_trains),
            "mergedRawTrainCount": len(merged_raw_trains),
            "trainInstanceCount": len(trains),
            "stopTimeCount": sum(len(train.get("stop_times") or []) for train in trains),
            "unmatchedSampleCount": len(unmatched_samples),
            "duplicateIdCount": len(duplicate_ids),
        },
        "routeStationCounts": {route_id: len(stations) for route_id, stations in route_stations.items()},
        "lineTrainCounts": dict(sorted(line_counts.items())),
        "stopCountDistribution": dict(sorted(stop_count_distribution.items(), key=lambda item: int(item[0]))),
        "matchMethods": dict(sorted(match_methods.items())),
        "duplicateIdSample": duplicate_ids[:20],
        "unmatchedSamples": unmatched_samples[:100],
        "stationErrors": station_errors,
        "queryErrors": query_errors[:100],
    }
    payload = {
        "schema": "onichase.v4.train_instances.v1",
        "id": "v4_iyotetsu_official_weekday_train_instances_v0_1",
        "label": "V4 weekday train instances reconstructed from Iyotetsu official route search",
        "generatedAt": now_iso(),
        "serviceDate": args.service_date,
        "sourceFeedKey": SOURCE_FEED_KEY,
        "train_instances": sorted(trains, key=lambda item: item["service_instance_id"]),
    }
    write_json(args.output, payload)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(trains)} trains, {audit['counts']['stopTimeCount']} stop_times")
    print(f"Wrote {args.audit_output}: unmatched={len(unmatched_samples)} duplicate_ids={len(duplicate_ids)} query_errors={len(query_errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
