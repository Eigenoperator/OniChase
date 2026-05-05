#!/usr/bin/env python3
"""Collect v4 weekday train instances from Kobe City Subway official CSV open data."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collect_v4_gtfs_train_instances import V4StationMatcher, load_json, normalize_name_variants, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_LINE_INVENTORY = ROOT / "data" / "v4_nationwide_line_inventory.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_kobe_subway_official_cache"
DEFAULT_OUTPUT = ROOT / "data" / "v4_kobe_subway_official_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_kobe_subway_official_train_instances_audit.json"
DEFAULT_SERVICE_DATE = "2026-04-27"

OPERATOR_NAME = "神戸市"
SOURCE_FEED_KEY = "kobe_subway_official_csv_open_data"

CSV_SOURCES = [
    {
        "key": "seishin_yamate_hokushin_east_weekday",
        "url": "https://kotsu.city.kobe.lg.jp/wp-content/uploads/04_/5lyb5qwt5qac6kab/44kq44o844ox44oz44oh44o844k/open_seishin_w_east_r070315.csv",
        "label": "西神・山手線、北神線 時刻表（平日ダイヤ）東行",
        "primaryLine": "山手線",
        "fallbackLines": ["北神線", "西神線", "西神延伸線"],
    },
    {
        "key": "seishin_yamate_hokushin_west_weekday",
        "url": "https://kotsu.city.kobe.lg.jp/wp-content/uploads/04_/5lyb5qwt5qac6kab/44kq44o844ox44oz44oh44o844k/open_seishin_w_west_r070315.csv",
        "label": "西神・山手線、北神線 時刻表（平日ダイヤ）西行",
        "primaryLine": "山手線",
        "fallbackLines": ["北神線", "西神線", "西神延伸線"],
    },
    {
        "key": "kaigan_east_weekday",
        "url": "https://kotsu.city.kobe.lg.jp/wp-content/uploads/open_kaigan_w_east_r080314.csv",
        "label": "海岸線 時刻表（平日ダイヤ）東行",
        "primaryLine": "海岸線",
        "fallbackLines": [],
    },
    {
        "key": "kaigan_west_weekday",
        "url": "https://kotsu.city.kobe.lg.jp/wp-content/uploads/open_kaigan_w_west_r080314.csv",
        "label": "海岸線 時刻表（平日ダイヤ）西行",
        "primaryLine": "海岸線",
        "fallbackLines": [],
    },
]

HOKUSHIN = {"谷上", "新神戸"}
YAMATE = {"新神戸", "三宮", "県庁前", "大倉山", "湊川公園", "上沢", "長田", "新長田"}
SEISHIN = {"新長田", "板宿", "妙法寺", "名谷"}
SEISHIN_EXTENSION = {"名谷", "総合運動公園", "学園都市", "伊川谷", "西神南", "西神中央"}
KAIGAN = {
    "三宮・花時計前",
    "旧居留地・大丸前",
    "みなと元町",
    "ハーバーランド",
    "中央市場前",
    "和田岬",
    "御崎公園",
    "苅藻",
    "駒ヶ林",
    "新長田",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").strip()


def parse_hhmm(value: str) -> str | None:
    text = clean_text(value)
    if not re.fullmatch(r"\d{1,2}:\d{2}", text):
        return None
    hour, minute = text.split(":")
    return f"{int(hour):02d}:{int(minute):02d}"


def minutes(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    hour_text, minute_text = value.split(":", 1)
    total = int(hour_text) * 60 + int(minute_text)
    if total < 3 * 60:
        total += 24 * 60
    return total


def fetch_text_cached(url: str, cache_dir: Path, refresh: bool) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    path = cache_dir / "csv" / f"{digest}.csv"
    if path.exists() and not refresh:
        data = path.read_bytes()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OniChase-v4-kobe-subway-official-collector/0.1)"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read()
        path.write_bytes(data)
    for encoding in ("utf-8-sig", "cp932", "shift_jis"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def load_physical_map(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


class KobeSubwayPhysicalIndex:
    def __init__(self, physical_map: dict[str, Any], line_inventory: dict[str, Any]) -> None:
        self.matcher = V4StationMatcher(physical_map)
        self.station_by_id = {station["id"]: station for station in physical_map["physicalStations"]}
        self.station_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.line_id_by_operator_line: dict[tuple[str, str], str] = {}
        self.line_color_by_operator_line: dict[tuple[str, str], str] = {}
        for line in line_inventory.get("lines", []):
            operator_name = str(line.get("operatorName") or "")
            line_name = str(line.get("lineName") or "")
            self.line_id_by_operator_line[(operator_name, line_name)] = str(line.get("id") or line_name)
            self.line_color_by_operator_line[(operator_name, line_name)] = str(
                line.get("lineColor") or line.get("operatorColor") or "#00AE8F"
            ).lstrip("#")
        for station in physical_map.get("physicalStations", []):
            if station.get("operatorName") != OPERATOR_NAME:
                continue
            for key in normalize_name_variants(station.get("nameJa") or ""):
                self.station_by_name[key].append(station)

    def line_id(self, line_name: str) -> str:
        return self.line_id_by_operator_line.get((OPERATOR_NAME, line_name)) or line_name

    def route_color(self, line_name: str) -> str:
        return self.line_color_by_operator_line.get((OPERATOR_NAME, line_name), "#00AE8F").lstrip("#")

    def station_for_match(self, match: dict[str, Any]) -> dict[str, Any] | None:
        station_id = match.get("physicalStationId")
        if not station_id:
            return None
        return self.station_by_id.get(str(station_id))

    def candidates(self, station_name: str) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for key in normalize_name_variants(station_name):
            for station in self.station_by_name.get(key, []):
                station_id = str(station.get("id") or "")
                if station_id in seen:
                    continue
                seen.add(station_id)
                output.append(station)
        return output

    def match_stop(self, station_name: str, preferred_lines: list[str]) -> dict[str, Any]:
        candidates = self.candidates(station_name)
        if candidates:
            ranked = sorted(
                candidates,
                key=lambda station: (
                    min(
                        (
                            preferred_lines.index(station.get("lineName"))
                            for _ in [0]
                            if station.get("lineName") in preferred_lines
                        ),
                        default=99,
                    ),
                    str(station.get("lineName") or ""),
                    str(station.get("stationGroupId") or ""),
                ),
            )
            best = ranked[0]
            return {
                "matched": True,
                "method": "kobe_subway_name_context",
                "stationGroupId": best["stationGroupId"],
                "physicalStationId": best["id"],
                "candidateCount": len(candidates),
            }
        for line_name in preferred_lines:
            match = self.matcher.match(OPERATOR_NAME, line_name, station_name, None, None)
            if match.get("matched"):
                match["method"] = f"fallback_{line_name}_{match['method']}"
                return match
        return self.matcher.match(OPERATOR_NAME, preferred_lines[0] if preferred_lines else None, station_name, None, None)


def preferred_lines_for_station(station_name: str, source: dict[str, Any]) -> list[str]:
    name = clean_text(station_name)
    primary_line = str(source["primaryLine"])
    fallback_lines = list(source.get("fallbackLines") or [])
    if primary_line == "海岸線":
        return ["海岸線"]
    if name in HOKUSHIN:
        return ["北神線", "山手線", *fallback_lines]
    if name in YAMATE:
        return ["山手線", "西神線", "北神線", *fallback_lines]
    if name in SEISHIN_EXTENSION:
        return ["西神延伸線", "西神線", "山手線", *fallback_lines]
    if name in SEISHIN:
        return ["西神線", "山手線", "西神延伸線", *fallback_lines]
    return [primary_line, *fallback_lines]


def parse_csv_table(text: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [[clean_text(cell) for cell in row] for row in csv.reader(text.splitlines()) if any(clean_text(cell) for cell in row)]
    if len(rows) < 3:
        return []
    origin_row = rows[0]
    destination_row = rows[1]
    stop_rows = rows[2:]
    max_columns = max(len(row) for row in rows)
    raw_trains: list[dict[str, Any]] = []
    for column in range(1, max_columns):
        stops: list[dict[str, Any]] = []
        for row in stop_rows:
            if not row:
                continue
            station_name = clean_text(row[0])
            if not station_name:
                continue
            value = row[column] if column < len(row) else ""
            hhmm = parse_hhmm(value)
            if not hhmm:
                continue
            stops.append({"stationName": station_name, "arrival": hhmm, "departure": hhmm})
        if len(stops) < 2:
            continue
        origin = clean_text(origin_row[column] if column < len(origin_row) else "") or stops[0]["stationName"]
        destination = clean_text(destination_row[column] if column < len(destination_row) else "") or stops[-1]["stationName"]
        raw_trains.append(
            {
                "source": source,
                "column": column,
                "originHeader": origin,
                "headsign": destination,
                "stops": stops,
            }
        )
    return raw_trains


def build_train(raw_train: dict[str, Any], physical_index: KobeSubwayPhysicalIndex) -> tuple[dict[str, Any] | None, Counter[str], list[dict[str, Any]]]:
    source = raw_train["source"]
    primary_line = str(source["primaryLine"])
    stop_rows = raw_train["stops"]
    if len(stop_rows) < 2:
        return None, Counter(), []
    match_methods: Counter[str] = Counter()
    unmatched: list[dict[str, Any]] = []
    stop_times: list[dict[str, Any]] = []
    for sequence, row in enumerate(stop_rows, start=1):
        station_name = clean_text(row["stationName"])
        preferred_lines = preferred_lines_for_station(station_name, source)
        match = physical_index.match_stop(station_name, preferred_lines)
        station = physical_index.station_for_match(match)
        if match.get("matched"):
            match_methods[str(match["method"])] += 1
        else:
            match_methods[str(match.get("method") or "unmatched")] += 1
            if len(unmatched) < 25:
                unmatched.append({"stationName": station_name, "sourceKey": source["key"], "primaryLine": primary_line})
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
                "arrival_hhmm": row.get("arrival"),
                "departure_hhmm": row.get("departure"),
                "match_method": match.get("method"),
            }
        )
    first_time = stop_times[0].get("departure_hhmm") or stop_times[0].get("arrival_hhmm") or "00:00"
    service_name = primary_line
    service_instance_id = f"kobe_subway:{source['key']}:c{raw_train['column']}:{first_time.replace(':', '')}"
    train = {
        "train_number": f"{service_name}{first_time.replace(':', '')}",
        "service_instance_id": service_instance_id,
        "source_trip_id": service_instance_id,
        "operator_id": OPERATOR_NAME,
        "operator_name": OPERATOR_NAME,
        "service_name": service_name,
        "service_number": first_time.replace(":", ""),
        "headsign": raw_train.get("headsign") or stop_times[-1]["station_name_raw"],
        "train_type": "普通",
        "route_color": physical_index.route_color(primary_line),
        "line_id": physical_index.line_id(primary_line),
        "line_name": primary_line,
        "source_feed_key": SOURCE_FEED_KEY,
        "origin": stop_times[0]["station_name_raw"],
        "destination": raw_train.get("headsign") or stop_times[-1]["station_name_raw"],
        "source_timetable_url": source["url"],
        "first_departure_hhmm": first_time,
        "reconstruction_method": "official_csv_column_train",
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
    args = parser.parse_args()

    physical_index = KobeSubwayPhysicalIndex(load_physical_map(args.physical_map), load_json(args.line_inventory))
    raw_trains: list[dict[str, Any]] = []
    source_errors: list[dict[str, str]] = []
    for source in CSV_SOURCES:
        try:
            text = fetch_text_cached(source["url"], args.cache_dir, args.refresh)
            raw_trains.extend(parse_csv_table(text, source))
        except Exception as exc:
            source_errors.append({"sourceKey": source["key"], "url": source["url"], "error": str(exc)})

    trains: list[dict[str, Any]] = []
    match_methods: Counter[str] = Counter()
    unmatched_samples: list[dict[str, Any]] = []
    for raw_train in raw_trains:
        train, methods, unmatched = build_train(raw_train, physical_index)
        match_methods.update(methods)
        unmatched_samples.extend(unmatched)
        if train:
            trains.append(train)

    duplicate_ids = [item for item, count in Counter(train["service_instance_id"] for train in trains).items() if count > 1]
    line_counts = Counter(train["line_name"] for train in trains)
    stop_count_distribution = Counter(str(len(train["stop_times"])) for train in trains)
    audit = {
        "schema": "onichase.v4.kobe_subway_official_train_instances_audit.v1",
        "generatedAt": now_iso(),
        "serviceDate": args.service_date,
        "sourceFeedKey": SOURCE_FEED_KEY,
        "counts": {
            "sourceCount": len(CSV_SOURCES),
            "sourceErrorCount": len(source_errors),
            "rawTrainCount": len(raw_trains),
            "trainInstanceCount": len(trains),
            "stopTimeCount": sum(len(train.get("stop_times") or []) for train in trains),
            "unmatchedSampleCount": len(unmatched_samples),
            "duplicateIdCount": len(duplicate_ids),
        },
        "lineTrainCounts": dict(sorted(line_counts.items())),
        "stopCountDistribution": dict(sorted(stop_count_distribution.items(), key=lambda item: int(item[0]))),
        "matchMethods": dict(sorted(match_methods.items())),
        "duplicateIdSample": duplicate_ids[:20],
        "unmatchedSamples": unmatched_samples[:100],
        "sourceErrors": source_errors,
    }
    payload = {
        "schema": "onichase.v4.train_instances.v1",
        "id": "v4_kobe_subway_official_weekday_train_instances_v0_1",
        "label": "V4 weekday train instances reconstructed from Kobe City Subway official CSV open data",
        "generatedAt": now_iso(),
        "serviceDate": args.service_date,
        "sourceFeedKey": SOURCE_FEED_KEY,
        "train_instances": sorted(trains, key=lambda item: item["service_instance_id"]),
    }
    write_json(args.output, payload)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(trains)} trains, {audit['counts']['stopTimeCount']} stop_times")
    print(f"Wrote {args.audit_output}: unmatched={len(unmatched_samples)} duplicate_ids={len(duplicate_ids)} source_errors={len(source_errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
