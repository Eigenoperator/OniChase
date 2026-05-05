#!/usr/bin/env python3
"""Build manual v4 train instances for special short lines.

These are short tourist/cable/DMV lines whose public timetable is published as
fixed intervals, images, or PDFs rather than machine-readable GTFS/HTML train
detail pages.  The collector keeps the scope narrow and records the source URL
on every generated train instance.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_LINE_INVENTORY = ROOT / "data" / "v4_nationwide_line_inventory.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_special_manual_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_special_manual_train_instances_audit.json"
DEFAULT_SERVICE_DATE = "2026-04-27"


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def hhmm_to_minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def minutes_to_hhmm(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def add_minutes(value: str, delta: int) -> str:
    return minutes_to_hhmm(hhmm_to_minutes(value) + delta)


def every(start: str, end: str, step: int) -> list[str]:
    current = hhmm_to_minutes(start)
    last = hhmm_to_minutes(end)
    output: list[str] = []
    while current <= last:
        output.append(minutes_to_hhmm(current))
        current += step
    return output


class PhysicalIndex:
    def __init__(self, physical_map: dict[str, Any], line_inventory: dict[str, Any]) -> None:
        self.station_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.line_id_by_key: dict[tuple[str, str], str] = {}
        self.line_color_by_key: dict[tuple[str, str], str] = {}
        for station in physical_map.get("physicalStations", []):
            self.station_by_key[
                (
                    str(station.get("operatorName") or ""),
                    str(station.get("lineName") or ""),
                    str(station.get("nameJa") or ""),
                )
            ] = station
        for line in line_inventory.get("lines", []):
            key = (str(line.get("operatorName") or ""), str(line.get("lineName") or ""))
            self.line_id_by_key[key] = str(line.get("id") or f"{key[0]}_{key[1]}")
            self.line_color_by_key[key] = str(line.get("lineColor") or line.get("operatorColor") or "#3A6EA5").lstrip("#")

    def station(self, operator_name: str, line_name: str, station_name: str) -> dict[str, Any]:
        station = self.station_by_key.get((operator_name, line_name, station_name))
        if not station:
            raise KeyError(f"Missing physical station: {operator_name} / {line_name} / {station_name}")
        return station

    def line_id(self, operator_name: str, line_name: str) -> str:
        return self.line_id_by_key[(operator_name, line_name)]

    def line_color(self, operator_name: str, line_name: str) -> str:
        return self.line_color_by_key[(operator_name, line_name)]


def make_train(
    index: PhysicalIndex,
    *,
    operator_name: str,
    line_name: str,
    sequence_no: int,
    direction_label: str,
    source_url: str,
    stops: list[tuple[str, str]],
    service_date: str,
) -> dict[str, Any]:
    line_id = index.line_id(operator_name, line_name)
    route_color = index.line_color(operator_name, line_name)
    stop_times: list[dict[str, Any]] = []
    for seq, (station_name, time_hhmm) in enumerate(stops, start=1):
        station = index.station(operator_name, line_name, station_name)
        stop_times.append(
            {
                "sequence": seq,
                "station_name_raw": station_name,
                "station_id": station["stationGroupId"],
                "station_group_id": station["stationGroupId"],
                "physical_station_id": station["id"],
                "line_id": line_id,
                "line_name": line_name,
                "arrival_hhmm": time_hhmm,
                "departure_hhmm": time_hhmm,
                "platform": None,
                "loop_pass_index": 1,
                "match_method": "manual_special_physical_station",
                "match_distance_m": None,
                "physical_operator_name": operator_name,
                "physical_line_name": line_name,
            }
        )
    train_number = f"{line_name}-{direction_label}-{sequence_no:03d}"
    service_instance_id = f"v4_special_manual:{operator_name}:{line_name}:{direction_label}:{sequence_no:03d}:{service_date}"
    return {
        "train_number": train_number,
        "service_instance_id": service_instance_id,
        "source_trip_id": service_instance_id,
        "operator_id": operator_name,
        "operator_name": operator_name,
        "service_name": line_name,
        "service_name_detail": direction_label,
        "display_name": line_name,
        "headsign": stops[-1][0],
        "train_type": "",
        "route_color": route_color,
        "line_id": line_id,
        "line_name": line_name,
        "source_feed_key": f"v4_special_manual_{service_date}",
        "source_url": source_url,
        "stop_times": stop_times,
    }


def add_bidirectional_interval(
    trains: list[dict[str, Any]],
    index: PhysicalIndex,
    *,
    operator_name: str,
    line_name: str,
    station_a: str,
    station_b: str,
    departures: list[str],
    travel_minutes: int,
    source_url: str,
    service_date: str,
) -> None:
    for idx, departure in enumerate(departures, start=1):
        trains.append(
            make_train(
                index,
                operator_name=operator_name,
                line_name=line_name,
                sequence_no=idx,
                direction_label=f"{station_a}->{station_b}",
                source_url=source_url,
                stops=[(station_a, departure), (station_b, add_minutes(departure, travel_minutes))],
                service_date=service_date,
            )
        )
        trains.append(
            make_train(
                index,
                operator_name=operator_name,
                line_name=line_name,
                sequence_no=idx,
                direction_label=f"{station_b}->{station_a}",
                source_url=source_url,
                stops=[(station_b, departure), (station_a, add_minutes(departure, travel_minutes))],
                service_date=service_date,
            )
        )


def build_trains(index: PhysicalIndex, service_date: str) -> list[dict[str, Any]]:
    trains: list[dict[str, Any]] = []

    # Official table: 09:30, 09:40, then every 20 minutes 10:00-17:00.
    add_bidirectional_interval(
        trains,
        index,
        operator_name="ラクテンチ",
        line_name="別府ラクテンチケーブル線",
        station_a="乙原",
        station_b="雲泉寺",
        departures=["09:30", "09:40", *every("10:00", "17:00", 20)],
        travel_minutes=3,
        source_url="https://rakutenchi.jp/guidance/calendar/",
        service_date=service_date,
    )

    # Official image timetable, 25-minute cycle.
    seikan_down = [
        "09:00", "09:25", "09:50", "10:15", "10:40", "11:05", "11:30", "11:55", "12:20", "12:45",
        "13:10", "13:35", "14:00", "14:25", "14:50", "15:15", "15:40", "16:05", "16:30",
    ]
    seikan_up = [
        "09:37", "10:02", "10:27", "10:52", "11:17", "11:42", "12:07", "12:32", "12:57", "13:22",
        "13:47", "14:12", "14:37", "15:02", "15:27", "15:52", "16:17", "16:42", "17:07",
    ]
    for idx, departure in enumerate(seikan_down, start=1):
        trains.append(
            make_train(
                index,
                operator_name="一般財団法人青函トンネル記念館",
                line_name="青函トンネル竜飛斜坑線",
                sequence_no=idx,
                direction_label="青函トンネル記念館->体験坑道",
                source_url="http://seikan-tunnel-museum.jp/info.html",
                stops=[("青函トンネル記念館", departure), ("体験坑道", add_minutes(departure, 8))],
                service_date=service_date,
            )
        )
    for idx, departure in enumerate(seikan_up, start=1):
        trains.append(
            make_train(
                index,
                operator_name="一般財団法人青函トンネル記念館",
                line_name="青函トンネル竜飛斜坑線",
                sequence_no=idx,
                direction_label="体験坑道->青函トンネル記念館",
                source_url="http://seikan-tunnel-museum.jp/info.html",
                stops=[("体験坑道", departure), ("青函トンネル記念館", add_minutes(departure, 7))],
                service_date=service_date,
            )
        )

    # 3月-10月: 09:00-18:00, every 15 minutes, about 4 minutes.
    add_bidirectional_interval(
        trains,
        index,
        operator_name="丹後海陸交通",
        line_name="天橋立鋼索鉄道",
        station_a="府中",
        station_b="傘松",
        departures=every("09:00", "18:00", 15),
        travel_minutes=4,
        source_url="https://www.tankai.jp/trip/cable/",
        service_date=service_date,
    )

    # Official guide: 09:00-17:00, every 15 minutes.
    add_bidirectional_interval(
        trains,
        index,
        operator_name="十国峠",
        line_name="十国鋼索線",
        station_a="十国峠山麓",
        station_b="十国峠山頂",
        departures=every("09:00", "17:00", 15),
        travel_minutes=3,
        source_url="https://www.jukkoku-cable.jp/guide/index.html",
        service_date=service_date,
    )

    # Alpine Route PDFs.  The manual subset covers the two cable-car sections.
    tateyama_departures = [
        "06:40", "07:00", "07:20", "07:40", "08:00", "08:20", "08:40", "09:00", "09:20", "09:40",
        "10:00", "10:20", "10:40", "11:00", "11:20", "11:40", "12:20", "12:40", "13:00", "13:20",
        "13:40", "14:00", "14:20", "14:40", "15:00", "15:20", "15:40", "16:00",
    ]
    add_bidirectional_interval(
        trains,
        index,
        operator_name="立山黒部貫光",
        line_name="鋼索線",
        station_a="立山",
        station_b="美女平",
        departures=tateyama_departures,
        travel_minutes=7,
        source_url="https://www.alpen-route.com/timetable/",
        service_date=service_date,
    )
    kurobedaira_departures = [
        "08:30", "08:50", "09:10", "09:30", "09:50", "10:10", "10:30", "10:50", "11:10", "11:30",
        "11:50", "12:20", "12:40", "13:00", "13:20", "13:40", "14:00", "14:20", "14:40", "15:00",
        "15:20", "15:30", "15:50", "16:15", "16:45",
    ]
    add_bidirectional_interval(
        trains,
        index,
        operator_name="立山黒部貫光",
        line_name="鋼索線",
        station_a="黒部平",
        station_b="黒部湖",
        departures=kurobedaira_departures,
        travel_minutes=7,
        source_url="https://www.alpen-route.com/timetable/",
        service_date=service_date,
    )

    asa_down = {
        "101": ["07:02", "07:07", "07:15", "07:23"],
        "103": ["08:18", "08:23", "08:31", "08:39"],
        "105": ["09:34", "09:39", "09:47", "09:55"],
        "109": ["10:58", "11:03", "11:11", "11:19"],
        "113": ["12:22", "12:27", "12:35", "12:43"],
        "117": ["13:56", "14:01", "14:09", "14:17"],
        "123": ["15:50", "15:55", "16:03", "16:11"],
        "125": ["17:08", "17:13", "17:21", "17:29"],
    }
    for idx, (train_no, times) in enumerate(asa_down.items(), start=1):
        trains.append(
            make_train(
                index,
                operator_name="阿佐海岸鉄道",
                line_name="阿佐東線",
                sequence_no=idx,
                direction_label=f"DMV{train_no}:阿波海南->甲浦",
                source_url="https://asatetu.com/schedule/",
                stops=list(zip(["阿波海南", "海部", "宍喰", "甲浦"], times, strict=True)),
                service_date=service_date,
            )
        )
    asa_up = {
        "2": ["06:30", "06:36", "06:44", "06:50"],
        "4": ["07:46", "07:52", "08:00", "08:06"],
        "6": ["09:02", "09:08", "09:16", "09:22"],
        "8": ["10:20", "10:26", "10:34", "10:40"],
        "12": ["11:44", "11:50", "11:58", "12:04"],
        "16": ["13:08", "13:14", "13:22", "13:28"],
        "22": ["15:12", "15:18", "15:26", "15:32"],
        "26": ["16:36", "16:42", "16:50", "16:56"],
    }
    for idx, (train_no, times) in enumerate(asa_up.items(), start=1):
        trains.append(
            make_train(
                index,
                operator_name="阿佐海岸鉄道",
                line_name="阿佐東線",
                sequence_no=idx,
                direction_label=f"DMV{train_no}:甲浦->阿波海南",
                source_url="https://asatetu.com/schedule/",
                stops=list(zip(["甲浦", "宍喰", "海部", "阿波海南"], times, strict=True)),
                service_date=service_date,
            )
        )

    # Official access page: 1-5月/9-12月 final up 16:30, final down 16:35, 15-20 minute interval.
    kurama_up = every("08:40", "16:30", 15)
    kurama_down = every("08:45", "16:35", 15)
    for idx, departure in enumerate(kurama_up, start=1):
        trains.append(
            make_train(
                index,
                operator_name="鞍馬寺",
                line_name="鞍馬山鋼索鉄道",
                sequence_no=idx,
                direction_label="山門->多宝塔",
                source_url="https://www.kuramadera.or.jp/access.html",
                stops=[("山門", departure), ("多宝塔", add_minutes(departure, 2))],
                service_date=service_date,
            )
        )
    for idx, departure in enumerate(kurama_down, start=1):
        trains.append(
            make_train(
                index,
                operator_name="鞍馬寺",
                line_name="鞍馬山鋼索鉄道",
                sequence_no=idx,
                direction_label="多宝塔->山門",
                source_url="https://www.kuramadera.or.jp/access.html",
                stops=[("多宝塔", departure), ("山門", add_minutes(departure, 2))],
                service_date=service_date,
            )
        )

    return trains


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--line-inventory", type=Path, default=DEFAULT_LINE_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--service-date", default=DEFAULT_SERVICE_DATE)
    args = parser.parse_args()

    physical_map = load_json(args.physical_map)
    line_inventory = load_json(args.line_inventory)
    index = PhysicalIndex(physical_map, line_inventory)
    trains = sorted(build_trains(index, args.service_date), key=lambda train: train["service_instance_id"])
    duplicate_ids = [
        service_id
        for service_id, count in Counter(train["service_instance_id"] for train in trains).items()
        if count > 1
    ]
    payload = {
        "id": "v4_special_manual_weekday_train_instances_v0_1",
        "label": "V4 special short-line weekday train instances from official pages/PDFs",
        "version": "0.1.0",
        "service_day": args.service_date,
        "source": "manual_official_short_line_timetables",
        "station_identity": physical_map.get("identityVersion"),
        "train_instances": trains,
    }
    audit = {
        "schema": "onichase.v4.special_manual_train_instances_audit.v1",
        "generatedAt": now_iso(),
        "serviceDay": args.service_date,
        "trainInstanceCount": len(trains),
        "stopTimeCount": sum(len(train.get("stop_times") or []) for train in trains),
        "duplicateServiceInstanceIdCount": len(duplicate_ids),
        "duplicateServiceInstanceIdsSample": duplicate_ids[:20],
        "operatorLineCounts": dict(Counter(f"{train['operator_name']}::{train['line_name']}" for train in trains)),
    }
    write_json(args.output, payload)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(trains)} trains")
    print(f"Wrote {args.audit_output}: duplicate_ids={len(duplicate_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
