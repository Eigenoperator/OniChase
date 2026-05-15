#!/usr/bin/env python3
"""Collect v4 weekday train instances from Nagoya City Subway official JSON.

Nagoya City publishes structured station master and per-station diagram JSON.
Those files are station departure tables rather than per-trip stop sequences, so
this collector reconstructs all-stop subway movements by chronological
adjacency, similar to the Osaka Metro collector.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import re
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collect_v4_gtfs_train_instances import V4StationMatcher, load_json, normalize_name_variants, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_LINE_INVENTORY = ROOT / "data" / "v4_nationwide_line_inventory.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_nagoya_subway_official_cache"
DEFAULT_OUTPUT = ROOT / "data" / "v4_nagoya_subway_official_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_nagoya_subway_official_train_instances_audit.json"
DEFAULT_SERVICE_DATE = "2026-04-27"

BASE = "https://www.kotsu.city.nagoya.jp"
STATION_MASTER_URL = f"{BASE}/station_data/station_subway_infos/station_master.json"
DIAGRAM_URL = f"{BASE}/station_data/station_subway_infos/diagrams/{{station_id}}.json"
OPERATOR_NAME = "名古屋市"
SOURCE_FEED_KEY = "nagoya_subway_official_station_diagram_json"
WEEKDAY_KEY = "平日"

LINE_DEFS = {
    "H": {"official": "東山線", "line": "1号線東山線", "terminal_down": "藤が丘", "terminal_up": "高畑"},
    "M": {"official": "名城線・名港線", "line": "2号線名城線", "terminal_down": "金山", "terminal_up": "金山"},
    "E": {"official": "名城線・名港線", "line": "2号線名港線", "terminal_down": "名古屋港", "terminal_up": "金山"},
    "T": {"official": "鶴舞線", "line": "3号線鶴舞線", "terminal_down": "赤池", "terminal_up": "上小田井"},
    "S": {"official": "桜通線", "line": "6号線桜通線", "terminal_down": "徳重", "terminal_up": "太閤通"},
    "K": {"official": "上飯田線", "line": "上飯田線", "terminal_down": "平安通", "terminal_up": "上飯田"},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cache_path(cache_dir: Path, namespace: str, key: str, suffix: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return cache_dir / namespace / f"{digest}{suffix}"


def fetch_json_cached(url: str, cache_dir: Path, namespace: str, refresh: bool) -> Any:
    path = cache_path(cache_dir, namespace, url, ".json")
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": "Mozilla/5.0 (compatible; OniChase-v4-nagoya-subway-official-collector/0.1)",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        raw = response.read()
    text = raw.decode("utf-8-sig", errors="replace")
    path.write_text(text, encoding="utf-8")
    return json.loads(text)


def load_physical_map(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def clean_station_name(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"駅$", "", text)
    return text


def code_prefix(code: str) -> str:
    match = re.match(r"([A-Z]+)", str(code or ""))
    return match.group(1) if match else ""


def code_number(code: str) -> int:
    match = re.search(r"(\d+)", str(code or ""))
    return int(match.group(1)) if match else -1


def hhmm_to_minutes(value: str) -> int:
    hour_text, minute_text = value.split(":", 1)
    total = int(hour_text) * 60 + int(minute_text)
    if total < 3 * 60:
        total += 24 * 60
    return total


def minutes_to_hhmm(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


def destination_from_railway(railway: str, direction: str, prefix: str) -> str:
    text = re.sub(r"\[.*?\]", "", str(railway or ""))
    text = re.sub(r"方面.*$", "", text)
    parts = [part.strip() for part in re.split(r"[・、/]", text) if part.strip()]
    if parts:
        return clean_station_name(parts[-1])
    line_def = LINE_DEFS.get(prefix, {})
    return str(line_def.get("terminal_down" if direction == "0" else "terminal_up") or "")


def parse_destination_legend(diagram: dict[str, Any], prefix: str, direction: str) -> dict[str, str]:
    line_def = LINE_DEFS.get(prefix, {})
    default = str(line_def.get("terminal_down" if direction == "0" else "terminal_up") or "")
    default = destination_from_railway(str(diagram.get("RAILWAY") or default), direction, prefix) or default
    if prefix == "M" and "名城線" in str(diagram.get("RAILWAY") or ""):
        default = ""
    legend = {"": clean_station_name(default)}
    for note in diagram.get("NOTES", {}).get(WEEKDAY_KEY, []) or []:
        if prefix == "M" and re.search(r"無印…名城線[左右]回り", str(note)):
            legend[""] = ""
        for code, destination in re.findall(r"([^\s　]+?)…([^…\s　]+?)行", str(note)):
            key = "" if code == "無印" else code.strip()
            legend[key] = clean_station_name(destination)
    return legend


def line_name_for_code(code: str) -> str:
    prefix = code_prefix(code)
    if prefix == "M":
        number = code_number(code)
        return "2号線名城線" if 1 <= number <= 12 else "4号線名城線"
    return str(LINE_DEFS.get(prefix, {}).get("line") or "")


class NagoyaSubwayPhysicalIndex:
    def __init__(self, physical_map: dict[str, Any], line_inventory: dict[str, Any]) -> None:
        self.matcher = V4StationMatcher(physical_map)
        self.station_by_id = {station["id"]: station for station in physical_map.get("physicalStations", [])}
        self.station_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.line_id_by_name: dict[str, str] = {}
        self.line_color_by_name: dict[str, str] = {}
        for line in line_inventory.get("lines", []):
            if line.get("operatorName") != OPERATOR_NAME:
                continue
            line_name = str(line.get("lineName") or "")
            self.line_id_by_name[line_name] = str(line.get("id") or line_name)
            self.line_color_by_name[line_name] = str(line.get("lineColor") or line.get("operatorColor") or "#006E54").lstrip("#")
        for station in physical_map.get("physicalStations", []):
            if station.get("operatorName") != OPERATOR_NAME:
                continue
            for key in normalize_name_variants(station.get("nameJa") or ""):
                self.station_by_name[key].append(station)

    def line_id(self, line_name: str) -> str:
        return self.line_id_by_name.get(line_name) or line_name

    def route_color(self, line_name: str) -> str:
        return self.line_color_by_name.get(line_name, "#006E54").lstrip("#")

    def station_for_match(self, match: dict[str, Any]) -> dict[str, Any] | None:
        station_id = match.get("physicalStationId")
        return self.station_by_id.get(str(station_id)) if station_id else None

    def match_stop(self, station_name: str, code: str) -> dict[str, Any]:
        cleaned = clean_station_name(station_name)
        preferred_line = line_name_for_code(code)
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for key in normalize_name_variants(cleaned):
            for station in self.station_by_name.get(key, []):
                station_id = str(station.get("id") or "")
                if station_id in seen:
                    continue
                seen.add(station_id)
                candidates.append(station)
        if candidates:
            ranked = sorted(
                candidates,
                key=lambda station: (
                    0 if station.get("lineName") == preferred_line else 1,
                    str(station.get("lineName") or ""),
                    str(station.get("stationGroupId") or ""),
                ),
            )
            best = ranked[0]
            return {
                "matched": True,
                "method": "nagoya_subway_code_context",
                "stationGroupId": best["stationGroupId"],
                "physicalStationId": best["id"],
                "candidateCount": len(candidates),
            }
        return self.matcher.match(
            operator_name=OPERATOR_NAME,
            line_name=preferred_line,
            stop_name=cleaned,
            stop_lat=None,
            stop_lon=None,
        )


def station_order_by_prefix(station_master: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_prefix: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for station in station_master:
        for code in station.get("codes") or []:
            prefix = code_prefix(code)
            if prefix in LINE_DEFS:
                by_prefix[prefix][code] = {
                    "stationSiteId": str(station["id"]),
                    "stationName": clean_station_name(station["name"]),
                    "code": code,
                    "prefix": prefix,
                    "order": code_number(code),
                }
    return {
        prefix: sorted(rows.values(), key=lambda item: item["order"])
        for prefix, rows in by_prefix.items()
    }


def parse_departures_for_diagram(
    station: dict[str, Any],
    diagram: dict[str, Any],
    official_line_name: str,
) -> list[dict[str, Any]]:
    codes = [str(code) for code in diagram.get("STATION_CODES") or station.get("codes") or []]
    if not codes:
        return []
    direction = str(diagram.get("DIRECTION_ID"))
    output: list[dict[str, Any]] = []
    for code in codes:
        prefix = code_prefix(code)
        if prefix not in LINE_DEFS:
            continue
        if LINE_DEFS[prefix]["official"] != official_line_name:
            continue
        legend = parse_destination_legend(diagram, prefix, direction)
        diagram_times = diagram.get("DIAGRAM", {}).get(WEEKDAY_KEY, {}) or {}
        destinations = diagram.get("DESTINATION", {}).get(WEEKDAY_KEY, {}) or {}
        for hour_text, minute_rows in diagram_times.items():
            if not isinstance(minute_rows, list):
                continue
            dest_rows = destinations.get(hour_text, []) or []
            for index, minute_value in enumerate(minute_rows):
                if minute_value in (None, ""):
                    continue
                try:
                    minute = int(str(minute_value))
                    hour = int(str(hour_text))
                except ValueError:
                    continue
                headsign_code = str(dest_rows[index]).strip() if index < len(dest_rows) else ""
                hhmm = f"{hour:02d}:{minute:02d}"
                output.append(
                    {
                        "stationSiteId": str(station["id"]),
                        "stationName": clean_station_name(station["name"]),
                        "code": code,
                        "prefix": prefix,
                        "direction": direction,
                        "officialLineName": official_line_name,
                        "time": hhmm,
                        "minutes": hhmm_to_minutes(hhmm),
                        "headsignCode": headsign_code,
                        "headsign": legend.get(headsign_code, legend.get("", "")),
                        "railway": str(diagram.get("RAILWAY") or ""),
                        "platform": str(diagram.get("PLATFORM") or ""),
                    }
                )
    return sorted(output, key=lambda item: item["minutes"])


def direction_station_order(prefix: str, direction: str, order: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if prefix == "M":
        return list(reversed(order)) if direction == "0" else list(order)
    if direction == "0":
        return list(order)
    return list(reversed(order))


def compatible_headsign(existing: str, candidate: str) -> bool:
    return not existing or not candidate or existing == candidate


def stitch_trains(
    prefix: str,
    direction: str,
    station_order: list[dict[str, Any]],
    departures_by_station: dict[tuple[str, str], list[dict[str, Any]]],
) -> list[list[dict[str, Any]]]:
    oriented = direction_station_order(prefix, direction, station_order)
    order_index = {station["code"]: index for index, station in enumerate(oriented)}
    station_passes = [(station, True) for station in oriented]
    if prefix == "M":
        station_passes.extend((station, False) for station in oriented)
    active: list[list[dict[str, Any]]] = []
    finished: list[list[dict[str, Any]]] = []
    for station, allow_new_trains in station_passes:
        departures = departures_by_station.get((station["code"], direction), [])
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
                if delta <= 0 or delta > 12:
                    continue
                if not compatible_headsign(str(train[0].get("headsign") or ""), str(dep.get("headsign") or "")):
                    continue
                if best_delta is None or delta < best_delta:
                    best_index = index
                    best_delta = delta
            if best_index is None:
                if allow_new_trains:
                    next_active.append([dep])
            else:
                used_active.add(best_index)
                next_active.append([*active[best_index], dep])
        for index, train in enumerate(active):
            if index not in used_active:
                finished.append(train)
        active = next_active
    finished.extend(active)
    return [
        append_terminal_arrival(train, oriented, order_index)
        for train in finished
        if len(train) >= 1
    ]


def inferred_terminal_offset(train: list[dict[str, Any]]) -> int:
    deltas = [
        current["minutes"] - previous["minutes"]
        for previous, current in zip(train, train[1:])
        if 0 < current["minutes"] - previous["minutes"] <= 12
    ]
    if not deltas:
        return 2
    deltas = sorted(deltas)
    return max(1, min(4, deltas[len(deltas) // 2]))


def append_terminal_arrival(
    train: list[dict[str, Any]],
    oriented: list[dict[str, Any]],
    order_index: dict[str, int],
) -> list[dict[str, Any]]:
    if not train:
        return train
    last = train[-1]
    index = order_index.get(str(last.get("code") or ""))
    if index is None or index + 1 >= len(oriented):
        return train if len(train) >= 2 else []
    terminal = oriented[index + 1]
    headsign = clean_station_name(str(train[0].get("headsign") or ""))
    if headsign and headsign != terminal["stationName"]:
        return train if len(train) >= 2 else []
    terminal_minutes = last["minutes"] + inferred_terminal_offset(train)
    return [
        *train,
        {
            **last,
            "stationSiteId": terminal["stationSiteId"],
            "stationName": terminal["stationName"],
            "code": terminal["code"],
            "prefix": terminal["prefix"],
            "time": minutes_to_hhmm(terminal_minutes),
            "minutes": terminal_minutes,
            "platform": "",
            "syntheticTerminalArrival": True,
        },
    ]


def build_train(
    prefix: str,
    direction: str,
    index: int,
    stitched: list[dict[str, Any]],
    physical_index: NagoyaSubwayPhysicalIndex,
) -> tuple[dict[str, Any] | None, Counter[str], list[dict[str, Any]]]:
    stop_times: list[dict[str, Any]] = []
    methods: Counter[str] = Counter()
    unmatched: list[dict[str, Any]] = []
    for sequence, dep in enumerate(stitched, start=1):
        match = physical_index.match_stop(dep["stationName"], dep["code"])
        station = physical_index.station_for_match(match)
        if match.get("matched"):
            methods[str(match["method"])] += 1
        else:
            methods[str(match.get("method") or "unmatched")] += 1
            if len(unmatched) < 25:
                unmatched.append({"stationName": dep["stationName"], "code": dep["code"], "direction": direction})
        stop_line = str(station.get("lineName") if station else line_name_for_code(dep["code"]))
        hhmm = minutes_to_hhmm(dep["minutes"])
        stop_times.append(
            {
                "sequence": sequence,
                "station_name_raw": dep["stationName"],
                "station_id": match.get("stationGroupId"),
                "station_group_id": match.get("stationGroupId"),
                "physical_station_id": match.get("physicalStationId"),
                "operator_name": OPERATOR_NAME,
                "line_id": physical_index.line_id(stop_line),
                "line_name": stop_line,
                "arrival_hhmm": None if sequence == 1 else hhmm,
                "departure_hhmm": None if sequence == len(stitched) else hhmm,
                "platform": dep.get("platform") or None,
                "match_method": match.get("method"),
                "source_station_code": dep.get("code"),
            }
        )
    if len(stop_times) < 2:
        return None, methods, unmatched
    line_name = line_name_for_code(stitched[0]["code"])
    first_time = stop_times[0].get("departure_hhmm") or stop_times[0].get("arrival_hhmm") or "00:00"
    train_id = f"nagoyasubway:{prefix}:{direction}:{first_time.replace(':', '')}:{index:04d}"
    headsign = str(stitched[0].get("headsign") or stitched[-1]["stationName"])
    train = {
        "train_number": f"NS{prefix}{direction}-{first_time.replace(':', '')}-{index:04d}",
        "service_instance_id": train_id,
        "source_trip_id": train_id,
        "operator_id": OPERATOR_NAME,
        "operator_name": OPERATOR_NAME,
        "service_name": "普通",
        "service_number": f"{prefix}{direction}-{first_time.replace(':', '')}-{index:04d}",
        "headsign": headsign,
        "train_type": "普通",
        "route_color": physical_index.route_color(line_name),
        "line_id": physical_index.line_id(line_name),
        "line_name": line_name,
        "source_feed_key": SOURCE_FEED_KEY,
        "reconstruction_method": "official_station_diagram_json_chronological_stitch",
        "origin": stop_times[0]["station_name_raw"],
        "destination": headsign,
        "source_timetable_url": DIAGRAM_URL.format(station_id=stitched[0]["stationSiteId"]),
        "first_departure_hhmm": first_time,
        "stop_times": stop_times,
    }
    return train, methods, unmatched


def stop_minutes(stop: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = stop.get(key)
        if value:
            return hhmm_to_minutes(str(value))
    return None


def train_first_departure_minutes(train: dict[str, Any]) -> int | None:
    stops = train.get("stop_times") or []
    if not stops:
        return None
    return stop_minutes(stops[0], "departure_hhmm", "arrival_hhmm")


def train_last_arrival_minutes(train: dict[str, Any]) -> int | None:
    stops = train.get("stop_times") or []
    if not stops:
        return None
    return stop_minutes(stops[-1], "arrival_hhmm", "departure_hhmm")


def first_station_name(train: dict[str, Any]) -> str:
    stops = train.get("stop_times") or []
    return str(stops[0].get("station_name_raw") or "") if stops else ""


def last_station_name(train: dict[str, Any]) -> str:
    stops = train.get("stop_times") or []
    return str(stops[-1].get("station_name_raw") or "") if stops else ""


def service_prefix(train: dict[str, Any]) -> str:
    service_number = str(train.get("service_number") or "")
    return service_number.split("-", 1)[0]


def merge_train_segments(
    primary: dict[str, Any],
    secondary: dict[str, Any],
    *,
    destination: str,
    trim_at_station: str | None = None,
) -> dict[str, Any]:
    merged = copy.deepcopy(primary)
    primary_stops = merged.get("stop_times") or []
    secondary_stops = copy.deepcopy(secondary.get("stop_times") or [])
    if not primary_stops or not secondary_stops:
        return merged
    junction_departure = secondary_stops[0].get("departure_hhmm") or secondary_stops[0].get("arrival_hhmm")
    if junction_departure:
        primary_stops[-1]["departure_hhmm"] = junction_departure
    appended: list[dict[str, Any]] = []
    for stop in secondary_stops[1:]:
        appended.append(stop)
        if trim_at_station and stop.get("station_name_raw") == trim_at_station:
            break
    for stop in appended:
        stop["sequence"] = len(primary_stops) + 1
        primary_stops.append(stop)
    merged["stop_times"] = primary_stops
    merged["headsign"] = destination
    merged["destination"] = destination
    merged["service_number"] = f"{primary.get('service_number')}+{secondary.get('service_number')}"
    merged["train_number"] = f"{primary.get('train_number')}+{secondary.get('train_number')}"
    merged["source_trip_id"] = f"{primary.get('source_trip_id')}+{secondary.get('source_trip_id')}"
    merged["reconstruction_method"] = (
        f"{primary.get('reconstruction_method')}_with_meijo_meiko_through_merge"
    )
    return merged


def find_next_train(
    candidates: list[tuple[int, dict[str, Any]]],
    used: set[int],
    after_minutes: int,
    *,
    max_gap_minutes: int,
    destination: str | None = None,
) -> tuple[int, dict[str, Any]] | None:
    best: tuple[int, dict[str, Any]] | None = None
    best_gap: int | None = None
    for index, candidate in candidates:
        if index in used:
            continue
        candidate_departure = train_first_departure_minutes(candidate)
        if candidate_departure is None:
            continue
        gap = candidate_departure - after_minutes
        if gap < 0 or gap > max_gap_minutes:
            continue
        if destination and str(candidate.get("destination") or candidate.get("headsign") or "") != destination:
            continue
        if best_gap is None or gap < best_gap:
            best = (index, candidate)
            best_gap = gap
    return best


def stitch_meijo_meiko_through_services(trains: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter[str]]:
    """Merge Nagoya Meijo/Meiko through services at Kanayama.

    The official station JSON exposes Meijo and Meiko station diagrams
    separately at Kanayama. Without this post-pass, through trains bound for
    Nagoya-ko or coming from Nagoya-ko are split into two candidate trains even
    though passengers remain on the same physical train.
    """

    indexed = list(enumerate(trains))
    e0_candidates = [
        item for item in indexed
        if service_prefix(item[1]) == "E0"
        and first_station_name(item[1]) == "金山"
        and str(item[1].get("destination") or item[1].get("headsign") or "") == "名古屋港"
    ]
    m1_candidates = [
        item for item in indexed
        if service_prefix(item[1]) == "M1"
        and first_station_name(item[1]) == "金山"
    ]
    used: set[int] = set()
    merged_by_primary: dict[int, dict[str, Any]] = {}
    stats: Counter[str] = Counter()

    for index, train in indexed:
        if service_prefix(train) != "M0":
            continue
        if last_station_name(train) != "金山":
            continue
        if str(train.get("destination") or train.get("headsign") or "") != "名古屋港":
            continue
        arrival = train_last_arrival_minutes(train)
        if arrival is None:
            continue
        match = find_next_train(e0_candidates, used, arrival, max_gap_minutes=8, destination="名古屋港")
        if not match:
            continue
        secondary_index, secondary = match
        used.add(secondary_index)
        merged_by_primary[index] = merge_train_segments(train, secondary, destination="名古屋港")
        stats["M0_to_E0"] += 1

    for index, train in indexed:
        if service_prefix(train) != "E1":
            continue
        destination = str(train.get("destination") or train.get("headsign") or "")
        if not destination or destination == "金山":
            continue
        if last_station_name(train) != "金山":
            continue
        arrival = train_last_arrival_minutes(train)
        if arrival is None:
            continue
        match = find_next_train(m1_candidates, used, arrival, max_gap_minutes=8)
        if not match:
            continue
        secondary_index, secondary = match
        used.add(secondary_index)
        merged_by_primary[index] = merge_train_segments(
            train,
            secondary,
            destination=destination,
            trim_at_station=destination,
        )
        stats["E1_to_M1"] += 1

    output: list[dict[str, Any]] = []
    for index, train in indexed:
        if index in used:
            continue
        output.append(merged_by_primary.get(index, train))
    stats["removed_secondary_segments"] = len(used)
    stats["merged_train_count"] = len(merged_by_primary)
    return output, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--line-inventory", type=Path, default=DEFAULT_LINE_INVENTORY)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--service-date", default=DEFAULT_SERVICE_DATE)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    station_master = fetch_json_cached(STATION_MASTER_URL, args.cache_dir, "station_master", args.refresh)
    physical_index = NagoyaSubwayPhysicalIndex(load_physical_map(args.physical_map), load_json(args.line_inventory))
    orders = station_order_by_prefix(station_master)

    diagrams_by_station: dict[str, Any] = {}
    diagram_errors: list[dict[str, str]] = []
    for station in station_master:
        station_id = str(station["id"])
        try:
            diagrams_by_station[station_id] = fetch_json_cached(
                DIAGRAM_URL.format(station_id=station_id),
                args.cache_dir,
                "diagrams",
                args.refresh,
            )
        except Exception as exc:
            diagram_errors.append({"stationId": station_id, "stationName": station.get("name", ""), "error": str(exc)})

    departures_by_prefix_station_direction: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    direction_counts: Counter[str] = Counter()
    for station in station_master:
        station_id = str(station["id"])
        station_diagrams = diagrams_by_station.get(station_id) or {}
        for official_line_name, diagrams in station_diagrams.items():
            for diagram in diagrams or []:
                departures = parse_departures_for_diagram(station, diagram, official_line_name)
                for dep in departures:
                    departures_by_prefix_station_direction[(dep["prefix"], dep["code"], dep["direction"])].append(dep)
                    direction_counts[f"{dep['prefix']}:{dep['direction']}"] += 1

    trains: list[dict[str, Any]] = []
    match_methods: Counter[str] = Counter()
    unmatched_samples: list[dict[str, Any]] = []
    reconstructed_counts: Counter[str] = Counter()
    line_counts: Counter[str] = Counter()
    for prefix, order in sorted(orders.items()):
        directions = sorted({
            direction
            for p, _code, direction in departures_by_prefix_station_direction
            if p == prefix
        })
        for direction in directions:
            by_station = {
                (code, d): deps
                for p, code, d in departures_by_prefix_station_direction
                if p == prefix and d == direction
                for deps in [departures_by_prefix_station_direction[(p, code, d)]]
            }
            stitched = stitch_trains(prefix, direction, order, by_station)
            reconstructed_counts[f"{prefix}:{direction}"] = len(stitched)
            for index, row in enumerate(stitched, start=1):
                train, methods, unmatched = build_train(prefix, direction, index, row, physical_index)
                match_methods.update(methods)
                if unmatched and len(unmatched_samples) < 50:
                    unmatched_samples.extend(unmatched[: 50 - len(unmatched_samples)])
                if not train:
                    continue
                trains.append(train)

    trains, through_merge_counts = stitch_meijo_meiko_through_services(trains)
    for train in trains:
        line_counts[f"{train['operator_name']}::{train['line_name']}"] += 1

    output = {
        "id": "v4_nagoya_subway_official_weekday_train_instances_v0_1",
        "label": "V4 Nagoya City Subway official weekday train instances reconstructed from station diagram JSON",
        "version": "0.1.0",
        "generatedAt": now_iso(),
        "service_date": args.service_date,
        "source": {
            "stationMasterUrl": STATION_MASTER_URL,
            "diagramUrlTemplate": DIAGRAM_URL,
            "operatorName": OPERATOR_NAME,
            "sourceFeedKey": SOURCE_FEED_KEY,
        },
        "train_instances": sorted(trains, key=lambda item: item["service_instance_id"]),
    }
    audit = {
        "schema": "onichase.v4.nagoya_subway_official_train_instances_audit.v1",
        "generatedAt": now_iso(),
        "serviceDate": args.service_date,
        "operatorName": OPERATOR_NAME,
        "stationMasterCount": len(station_master),
        "diagramStationCount": len(diagrams_by_station),
        "diagramErrorCount": len(diagram_errors),
        "diagramErrors": diagram_errors[:30],
        "trainInstanceCount": len(trains),
        "stopTimeCount": sum(len(train.get("stop_times") or []) for train in trains),
        "lineTrainCounts": dict(sorted(line_counts.items())),
        "meijoMeikoThroughMergeCounts": dict(sorted(through_merge_counts.items())),
        "stationOrderCounts": {prefix: len(rows) for prefix, rows in sorted(orders.items())},
        "departureDirectionCounts": dict(sorted(direction_counts.items())),
        "reconstructedDirectionCounts": dict(sorted(reconstructed_counts.items())),
        "stationMatchMethods": dict(sorted(match_methods.items())),
        "unmatchedStopSample": unmatched_samples,
    }
    write_json(args.output, output)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(trains)} trains")
    print(
        f"Wrote {args.audit_output}: diagrams={len(diagrams_by_station)} "
        f"unmatched_samples={len(unmatched_samples)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
