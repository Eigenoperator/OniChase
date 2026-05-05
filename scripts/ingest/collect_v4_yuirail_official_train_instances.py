#!/usr/bin/env python3
"""Collect v4 weekday train instances from Yui Rail official timetable JSON."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collect_v4_gtfs_train_instances import V4StationMatcher, load_json, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_LINE_INVENTORY = ROOT / "data" / "v4_nationwide_line_inventory.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_yuirail_official_cache"
DEFAULT_OUTPUT = ROOT / "data" / "v4_yuirail_official_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_yuirail_official_train_instances_audit.json"
DEFAULT_SERVICE_DATE = "2026-04-27"

BASE = "https://www.yui-rail.co.jp"
NORMAL_JSON_URL = f"{BASE}/common/json/timetable/normal/normal.json"
REALTIME_JSON_URL = f"{BASE}/common/json/timetable/realtime.json"
OPERATOR_NAME = "沖縄都市モノレール"
LINE_NAME = "沖縄都市モノレール線"
SOURCE_FEED_KEY = "yuirail_official_normal_json"
TERMINAL_LABELS = {
    "首": "syuri",
    "牧": "makishi",
}
TERMINAL_ARRIVAL_OFFSET_MINUTES = 2


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
            "User-Agent": "Mozilla/5.0 (compatible; OniChase-v4-yuirail-official-collector/0.1)",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        raw = response.read()
    path.write_bytes(raw)
    return json.loads(raw.decode("utf-8"))


def clean_station_name(value: str) -> str:
    text = str(value or "").strip()
    return re.sub(r"駅$", "", text)


def clean_minutes(value: Any) -> str | None:
    match = re.search(r"(\d{1,2})", str(value or ""))
    if not match:
        return None
    return f"{int(match.group(1)):02d}"


def clean_train_number(value: Any) -> str:
    match = re.search(r"(\d+)", str(value or ""))
    return match.group(1) if match else str(value or "").strip()


def hhmm(hour: Any, minutes: Any) -> str | None:
    minute_text = clean_minutes(minutes)
    if minute_text is None:
        return None
    try:
        hour_int = int(str(hour))
    except ValueError:
        return None
    return f"{hour_int:02d}:{minute_text}"


def add_minutes(value: str, offset: int) -> str:
    hour_text, minute_text = value.split(":", 1)
    total = int(hour_text) * 60 + int(minute_text) + offset
    return f"{total // 60:02d}:{total % 60:02d}"


def minute_order(value: str | None) -> int:
    if not value:
        return -1
    hour_text, minute_text = value.split(":", 1)
    total = int(hour_text) * 60 + int(minute_text)
    if total < 3 * 60:
        total += 24 * 60
    return total


def load_physical_map(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


class YuiRailPhysicalIndex:
    def __init__(self, physical_map: dict[str, Any], line_inventory: dict[str, Any]) -> None:
        self.matcher = V4StationMatcher(physical_map)
        self.line = self._find_line(line_inventory)
        self.operator_id = str(self.line.get("operatorId") or OPERATOR_NAME)
        self.line_id = str(self.line.get("id") or LINE_NAME)
        self.route_color = str(self.line.get("lineColor") or self.line.get("operatorColor") or "#32BD98").lstrip("#")

    @staticmethod
    def _find_line(line_inventory: dict[str, Any]) -> dict[str, Any]:
        for line in line_inventory.get("lines", []):
            if line.get("operatorName") == OPERATOR_NAME and line.get("lineName") == LINE_NAME:
                return line
        raise RuntimeError(f"Could not find {OPERATOR_NAME} / {LINE_NAME} in v4 line inventory")

    def match_stop(self, station_name: str) -> dict[str, Any]:
        return self.matcher.match(
            operator_name=OPERATOR_NAME,
            line_name=LINE_NAME,
            stop_name=station_name,
            stop_lat=None,
            stop_lon=None,
        )


def station_rows(realtime_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = sorted(realtime_payload["stationInfoList"], key=lambda item: int(item["station_number"]))
    output = []
    for zero_index, row in enumerate(rows):
        station_name = clean_station_name(row["labels"].get("jp_title") or "")
        output.append(
            {
                "slug": row["slug"],
                "stationNumber": int(row["station_number"]),
                "order": zero_index,
                "nameJa": station_name,
            }
        )
    return output


def collect_train_departures(normal_payload: dict[str, Any], stations: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    by_train: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    station_by_slug = {station["slug"]: station for station in stations}
    for slug, station_data in normal_payload.items():
        station = station_by_slug.get(slug)
        if not station:
            continue
        weekday = station_data.get("weekday") or {}
        for direction, hours in weekday.items():
            for hour, departures in (hours or {}).items():
                for item in departures:
                    train_number = clean_train_number(item.get("trainNumber"))
                    time = hhmm(hour, item.get("minutes"))
                    if not train_number or not time:
                        continue
                    by_train[(direction, train_number)].append(
                        {
                            **station,
                            "time": time,
                            "label": str(item.get("label") or ""),
                            "platform": str(item.get("platform") or ""),
                        }
                    )
    return by_train


def travel_sort_key(direction: str, row: dict[str, Any]) -> int:
    order = int(row["order"])
    return -order if direction == "upLine" else order


def maybe_add_terminal(rows: list[dict[str, Any]], station_by_slug: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    labels = {row.get("label") for row in rows}
    for label, terminal_slug in TERMINAL_LABELS.items():
        if label not in labels or any(row["slug"] == terminal_slug for row in rows):
            continue
        terminal = station_by_slug.get(terminal_slug)
        if not terminal or not rows:
            continue
        last = rows[-1]
        rows.append(
            {
                **terminal,
                "time": add_minutes(last["time"], TERMINAL_ARRIVAL_OFFSET_MINUTES),
                "label": label,
                "platform": "",
                "isSyntheticTerminal": True,
            }
        )
        return rows, label
    return rows, None


def build_stop_times(
    rows: list[dict[str, Any]],
    physical_index: YuiRailPhysicalIndex,
    match_methods: Counter[str],
    unmatched: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    stop_times: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        match = physical_index.match_stop(row["nameJa"])
        if match.get("matched"):
            match_methods[str(match["method"])] += 1
        else:
            match_methods[str(match["method"])] += 1
            if len(unmatched) < 30:
                unmatched.append(
                    {
                        "stationName": row["nameJa"],
                        "slug": row["slug"],
                        "method": str(match.get("method")),
                    }
                )
        is_first = index == 1
        is_last = index == len(rows)
        stop_times.append(
            {
                "sequence": index,
                "station_name_raw": row["nameJa"],
                "station_id": match.get("stationGroupId"),
                "station_group_id": match.get("stationGroupId"),
                "physical_station_id": match.get("physicalStationId"),
                "line_id": physical_index.line_id,
                "line_name": LINE_NAME,
                "arrival_hhmm": row["time"] if not is_first else None,
                "departure_hhmm": row["time"] if not is_last else None,
                "platform": row.get("platform") or None,
                "match_method": match.get("method"),
                "source_slug": row["slug"],
                "source_label": row.get("label") or None,
                "synthetic_terminal": bool(row.get("isSyntheticTerminal")),
            }
        )
    return stop_times


def build_trains(
    normal_payload: dict[str, Any],
    realtime_payload: dict[str, Any],
    physical_index: YuiRailPhysicalIndex,
    service_date: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    stations = station_rows(realtime_payload)
    station_by_slug = {station["slug"]: station for station in stations}
    raw_by_train = collect_train_departures(normal_payload, stations)
    trains: list[dict[str, Any]] = []
    match_methods: Counter[str] = Counter()
    terminal_additions: Counter[str] = Counter()
    stop_count_distribution: Counter[str] = Counter()
    unmatched: list[dict[str, Any]] = []
    duplicate_stop_samples: list[dict[str, Any]] = []

    for (direction, train_number), rows in sorted(raw_by_train.items()):
        rows = sorted(rows, key=lambda row: (travel_sort_key(direction, row), minute_order(row["time"])))
        seen_slugs: set[str] = set()
        deduped_rows: list[dict[str, Any]] = []
        for row in rows:
            if row["slug"] in seen_slugs:
                if len(duplicate_stop_samples) < 20:
                    duplicate_stop_samples.append({"direction": direction, "trainNumber": train_number, "slug": row["slug"]})
                continue
            seen_slugs.add(row["slug"])
            deduped_rows.append(row)
        rows, terminal_label = maybe_add_terminal(deduped_rows, station_by_slug)
        if terminal_label:
            terminal_additions[terminal_label] += 1
        if len(rows) < 2:
            continue
        stop_times = build_stop_times(rows, physical_index, match_methods, unmatched)
        headsign = rows[-1]["nameJa"]
        origin = rows[0]["nameJa"]
        train = {
            "train_number": train_number,
            "service_instance_id": f"yuirail:{service_date}:weekday:{direction}:{train_number}",
            "source_trip_id": f"yuirail:{service_date}:weekday:{direction}:{train_number}",
            "operator_id": physical_index.operator_id,
            "operator_name": OPERATOR_NAME,
            "service_name": "ゆいレール",
            "service_number": train_number,
            "headsign": headsign,
            "train_type": "普通",
            "route_color": physical_index.route_color,
            "line_id": physical_index.line_id,
            "line_name": LINE_NAME,
            "source_feed_key": SOURCE_FEED_KEY,
            "origin": origin,
            "destination": headsign,
            "direction": direction,
            "stop_times": stop_times,
        }
        stop_count_distribution[str(len(stop_times))] += 1
        trains.append(train)

    audit = {
        "stationCount": len(stations),
        "rawTrainKeys": len(raw_by_train),
        "trainInstanceCount": len(trains),
        "stopTimeCount": sum(len(train["stop_times"]) for train in trains),
        "stopCountDistribution": dict(sorted(stop_count_distribution.items(), key=lambda item: int(item[0]))),
        "terminalAdditions": dict(sorted(terminal_additions.items())),
        "stationMatchMethods": dict(sorted(match_methods.items())),
        "unmatchedStopSample": unmatched,
        "duplicateStopSample": duplicate_stop_samples,
        "firstTrainSample": trains[0] if trains else None,
        "lastTrainSample": trains[-1] if trains else None,
    }
    return trains, audit


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

    physical_map = load_physical_map(args.physical_map)
    line_inventory = load_json(args.line_inventory)
    normal_payload = fetch_json_cached(NORMAL_JSON_URL, args.cache_dir, "json", args.refresh)
    realtime_payload = fetch_json_cached(REALTIME_JSON_URL, args.cache_dir, "json", args.refresh)
    physical_index = YuiRailPhysicalIndex(physical_map, line_inventory)
    trains, train_audit = build_trains(normal_payload, realtime_payload, physical_index, args.service_date)

    output = {
        "id": "v4_yuirail_official_weekday_train_instances_v0_1",
        "label": "V4 Yui Rail official weekday train instances",
        "version": "0.1.0",
        "generatedAt": now_iso(),
        "service_date": args.service_date,
        "source": {
            "normalJsonUrl": NORMAL_JSON_URL,
            "realtimeJsonUrl": REALTIME_JSON_URL,
            "operatorName": OPERATOR_NAME,
            "lineName": LINE_NAME,
        },
        "train_instances": trains,
    }
    audit = {
        "schema": "onichase.v4.yuirail_official_train_instances_audit.v1",
        "generatedAt": now_iso(),
        "serviceDate": args.service_date,
        "operatorName": OPERATOR_NAME,
        "lineName": LINE_NAME,
        **train_audit,
    }
    write_json(args.output, output)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(trains)} trains")
    print(
        f"Wrote {args.audit_output}: stops={audit['stopTimeCount']} "
        f"unmatched={len(audit['unmatchedStopSample'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
