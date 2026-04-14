#!/usr/bin/env python3

from __future__ import annotations

import csv
import io
import json
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GTFS_PATH = ROOT / "data" / "v3_external" / "Toei-Train-GTFS.zip"
GTFS_URL = "https://api-public.odpt.org/api/v4/files/Toei/data/Toei-Train-GTFS.zip"
STATIONS_PATH = ROOT / "data" / "v3_jreast_station_seed.json"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_toei_weekday_train_instances.json"

TARGET_DATE = date(2026, 4, 13)

ROUTE_TO_LINE = {
    "浅草線": "TOEI_ASAKUSA",
    "三田線": "TOEI_MITA",
    "新宿線": "TOEI_SHINJUKU",
    "大江戸線": "TOEI_OEDO",
    "日暮里・舎人ライナー": "TOEI_NIPPORI_TONERI",
    "東京さくらトラム（都電荒川線）": "TOEI_ARAKAWA",
}

ROUTE_TO_SEED_LINE_CODE = {
    "浅草線": "Toei.Asakusa",
    "三田線": "Toei.Mita",
    "新宿線": "Toei.Shinjuku",
    "大江戸線": "Toei.Oedo",
    "日暮里・舎人ライナー": "Toei.NipporiToneri",
    "東京さくらトラム（都電荒川線）": "Toei.Arakawa",
}


def normalize_name(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("・", "")
        .replace("（", "")
        .replace("）", "")
        .replace("(", "")
        .replace(")", "")
        .replace("〈", "")
        .replace("〉", "")
        .replace("､", "")
        .replace("，", "")
        .replace(",", "")
    )


def slugify(value: str) -> str:
    text = normalize_name(value).upper()
    return "".join(ch if ch.isalnum() else "_" for ch in text)


def read_gtfs_csv(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    with zf.open(name) as handle:
        return list(csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig")))


def active_service_ids(calendar_rows: list[dict[str, str]], calendar_dates_rows: list[dict[str, str]]) -> set[str]:
    weekday_key = TARGET_DATE.strftime("%A").lower()
    active = {
        row["service_id"]
        for row in calendar_rows
        if row.get(weekday_key) == "1"
        and row.get("start_date", "") <= TARGET_DATE.strftime("%Y%m%d") <= row.get("end_date", "")
    }
    for row in calendar_dates_rows:
        if row.get("date") != TARGET_DATE.strftime("%Y%m%d"):
            continue
        if row.get("exception_type") == "1":
            active.add(row["service_id"])
        elif row.get("exception_type") == "2":
            active.discard(row["service_id"])
    return active


def build_station_lookup(stations: list[dict[str, object]]) -> dict[tuple[str, str], str]:
    lookup: dict[tuple[str, str], str] = {}
    for station in stations:
        line_codes = station.get("line_codes", [])
        if not isinstance(line_codes, list):
            continue
        name_ja = ((station.get("names") or {}).get("ja") if isinstance(station.get("names"), dict) else None) or station.get("name")
        if not name_ja:
            continue
        normalized = normalize_name(str(name_ja))
        for line_code in line_codes:
            lookup[(normalized, str(line_code))] = str(station["id"])
    return lookup


def hhmm_from_gtfs_time(value: str) -> str | None:
    if not value:
        return None
    hours, minutes, _seconds = value.split(":")
    return f"{int(hours):02d}:{minutes}"


def main() -> int:
    if not GTFS_PATH.exists():
        GTFS_PATH.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(GTFS_URL, GTFS_PATH)

    stations_seed = json.loads(STATIONS_PATH.read_text(encoding="utf-8"))
    station_lookup = build_station_lookup(stations_seed["stations"])

    with zipfile.ZipFile(GTFS_PATH) as zf:
        routes = {row["route_id"]: row for row in read_gtfs_csv(zf, "routes.txt")}
        trips = read_gtfs_csv(zf, "trips.txt")
        stops = {row["stop_id"]: row for row in read_gtfs_csv(zf, "stops.txt")}
        stop_times = read_gtfs_csv(zf, "stop_times.txt")
        calendar_rows = read_gtfs_csv(zf, "calendar.txt")
        calendar_dates_rows = read_gtfs_csv(zf, "calendar_dates.txt")

    active_services = active_service_ids(calendar_rows, calendar_dates_rows)
    trip_stop_times: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in stop_times:
        trip_stop_times[row["trip_id"]].append(row)
    for rows in trip_stop_times.values():
        rows.sort(key=lambda item: int(item["stop_sequence"]))

    train_instances: list[dict[str, object]] = []
    fallback_physical_stations: dict[str, dict[str, object]] = {}

    for trip in trips:
        if trip["service_id"] not in active_services:
            continue
        route = routes[trip["route_id"]]
        route_name = route["route_long_name"]
        line_id = ROUTE_TO_LINE.get(route_name)
        seed_line_code = ROUTE_TO_SEED_LINE_CODE.get(route_name)
        if line_id is None or seed_line_code is None:
            continue

        normalized_stop_times: list[dict[str, object]] = []
        for stop_time in trip_stop_times.get(trip["trip_id"], []):
            stop = stops[stop_time["stop_id"]]
            station_name_raw = stop["stop_name"]
            station_id = station_lookup.get((normalize_name(station_name_raw), seed_line_code))
            if station_id is None:
                station_id = f"{line_id}_{slugify(stop.get('stop_code') or stop_time['stop_id'] or station_name_raw)}"
                fallback_physical_stations.setdefault(
                    station_id,
                    {
                        "id": station_id,
                        "name": station_name_raw,
                        "names": {
                            "en": station_name_raw,
                            "ja": station_name_raw,
                            "zh_hans": station_name_raw,
                        },
                        "group_code": None,
                        "line_codes": [seed_line_code],
                        "alternative_names": [],
                        "lat": float(stop["stop_lat"]) if stop.get("stop_lat") else None,
                        "lon": float(stop["stop_lon"]) if stop.get("stop_lon") else None,
                        "prefecture": None,
                        "source": "Toei-Train-GTFS fallback physical station",
                    },
                )
            normalized_stop_times.append(
                {
                    "sequence": int(stop_time["stop_sequence"]),
                    "station_name_raw": station_name_raw,
                    "station_id": station_id,
                    "line_id": line_id,
                    "arrival_hhmm": hhmm_from_gtfs_time(stop_time.get("arrival_time", "")),
                    "departure_hhmm": hhmm_from_gtfs_time(stop_time.get("departure_time", "")),
                    "platform": stop.get("stop_code") or None,
                }
            )

        if not normalized_stop_times:
            continue

        train_instances.append(
            {
                "train_number": trip["trip_id"],
                "service_instance_id": trip["trip_id"],
                "service_name": route_name,
                "headsign": trip.get("trip_headsign") or "",
                "train_type": None,
                "route_color": route.get("route_color") or None,
                "stop_times": normalized_stop_times,
            }
        )

    output = {
        "id": "v3_tokyo_toei_weekday_train_instances_v0_1",
        "label": "V3 Tokyo Toei weekday train instances from public GTFS",
        "version": "0.1.0",
        "service_day": TARGET_DATE.isoformat(),
        "station_seed_id": stations_seed["id"],
        "source_gtfs": str(GTFS_PATH.relative_to(ROOT)),
        "active_service_ids": sorted(active_services),
        "route_mapping": ROUTE_TO_LINE,
        "fallback_physical_stations": sorted(fallback_physical_stations.values(), key=lambda item: item["id"]),
        "train_instances": train_instances,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Active services: {sorted(active_services)}")
    print(f"Train instances: {len(train_instances)}")
    print(f"Wrote: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
