#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_tama_monorail_weekday_train_instances.json"
DOWNLOAD_DIR = ROOT / "data" / "v3_external" / "tama_monorail"
SERVICE_DAY = "2026-04-15"

LINE_ID = "TAMA_MONORAIL"
SERVICE_NAME = "Tama Monorail"
ROUTE_COLOR = "E60012"

STATION_SEQUENCE = [
    ("TT19", "上北台"),
    ("TT18", "桜街道"),
    ("TT17", "玉川上水"),
    ("TT16", "砂川七番"),
    ("TT15", "泉体育館"),
    ("TT14", "立飛"),
    ("TT13", "高松"),
    ("TT12", "立川北"),
    ("TT11", "立川南"),
    ("TT10", "柴崎体育館"),
    ("TT9", "甲州街道"),
    ("TT8", "万願寺"),
    ("TT7", "高幡不動"),
    ("TT6", "程久保"),
    ("TT5", "多摩動物公園"),
    ("TT4", "中央大学・明星大学"),
    ("TT3", "大塚・帝京大学"),
    ("TT2", "松が谷"),
    ("TT1", "多摩センター"),
]


def ensure_pdf(pdf_code: str) -> Path:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = DOWNLOAD_DIR / f"{pdf_code}.pdf"
    if path.exists():
        return path
    url = f"https://www.tama-monorail.co.jp/monorail/station/{pdf_code}.pdf"
    urllib.request.urlretrieve(url, path)
    return path


def pdf_text(path: Path) -> str:
    return subprocess.check_output(["pdftotext", "-layout", str(path), "-"]).decode("utf-8", "ignore")


def to_service_minute(hour: int, minute: int) -> int:
    return (24 * 60 + minute) if hour == 0 else (hour * 60 + minute)


def hhmm(total_minutes: int) -> str:
    hour = total_minutes // 60
    minute = total_minutes % 60
    return f"{hour:02d}:{minute:02d}"


def parse_direction_minutes(section_text: str) -> list[int]:
    departures: list[int] = []
    for raw in section_text.splitlines():
        raw = raw.rstrip()
        match = re.match(r"^\s*(\d{1,2})\s+(.+)$", raw)
        if not match:
            continue
        hour = int(match.group(1))
        for minute_text in re.findall(r"(?<!\d)(\d{1,2})(?!\d)", match.group(2)):
            minute = int(minute_text)
            if minute < 60:
                departures.append(to_service_minute(hour, minute))
    return departures


def parse_station_departures() -> dict[str, dict[str, list[int]]]:
    station_departures: dict[str, dict[str, list[int]]] = {}
    for pdf_code, station_name in STATION_SEQUENCE:
        text = pdf_text(ensure_pdf(pdf_code))
        pages = [page for page in text.split("\f") if page.strip()]
        weekday_page = next((page for page in pages if "平 日" in page[:500]), pages[0])
        north_match = re.search(r"上北台方面【北行】(.*?)(多摩センター方面【南行】|$)", weekday_page, re.S)
        south_match = re.search(r"多摩センター方面【南行】(.*)$", weekday_page, re.S)
        toward_kamikitadai = parse_direction_minutes(north_match.group(1)) if north_match else []
        toward_tama_center = parse_direction_minutes(south_match.group(1)) if south_match else []
        station_departures[station_name] = {
            "toward_kamikitadai": toward_kamikitadai,
            "toward_tama_center": toward_tama_center,
        }
    return station_departures


def centroid(coords: list) -> tuple[float, float]:
    flat: list[tuple[float, float]] = []

    def walk(node: list) -> None:
        if not node:
            return
        if isinstance(node[0], (int, float)):
            flat.append((float(node[0]), float(node[1])))
            return
        for child in node:
            walk(child)

    walk(coords)
    lon = sum(p[0] for p in flat) / len(flat)
    lat = sum(p[1] for p in flat) / len(flat)
    return lon, lat


def load_station_seed() -> list[dict]:
    geojson = json.loads(N02_STATION_PATH.read_text(encoding="utf-8"))
    station_names = {name for _, name in STATION_SEQUENCE}
    lookup: dict[str, dict] = {}
    for feature in geojson["features"]:
        props = feature["properties"]
        if props.get("N02_004") != "多摩都市モノレール":
            continue
        if props.get("N02_003") != "多摩都市モノレール線":
            continue
        name = props.get("N02_005")
        if name not in station_names:
            continue
        lon, lat = centroid(feature["geometry"]["coordinates"])
        lookup[name] = {
            "station_id": f"TAMA_MONORAIL_{name}",
            "name_ja": name,
            "operator": "多摩都市モノレール",
            "line_id": LINE_ID,
            "lat": round(lat, 8),
            "lon": round(lon, 8),
            "n02_station_code": props.get("N02_005c"),
            "n02_group_code": props.get("N02_005g"),
        }
    return [lookup[name] for _, name in STATION_SEQUENCE]


def parse_hhmm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def build_direction_instances(
    station_seed: list[dict],
    station_departures: dict[str, dict[str, list[int]]],
    direction_key: str,
    order: list[str],
    headsign: str,
) -> list[dict]:
    station_lookup = {entry["name_ja"]: entry for entry in station_seed}
    terminal_departures = station_departures[order[0]][direction_key]
    trips = [
        {
            "service_instance_id": f"{LINE_ID}_{direction_key}_{index:04d}",
            "train_number": f"{LINE_ID}_{direction_key}_{index:04d}",
            "service_name": SERVICE_NAME,
            "headsign": headsign,
            "train_type": "Local",
            "route_color": ROUTE_COLOR,
            "stop_times": [
                {
                    "sequence": 1,
                    "station_name_raw": order[0],
                    "station_id": station_lookup[order[0]]["station_id"],
                    "line_id": LINE_ID,
                    "arrival_hhmm": hhmm(minute),
                    "departure_hhmm": hhmm(minute),
                    "platform": None,
                }
            ],
        }
        for index, minute in enumerate(terminal_departures, start=1)
    ]
    active_indices = list(range(len(trips)))
    for station_name in order[1:]:
        departures = station_departures[station_name][direction_key]
        next_active: list[int] = []
        cursor = 0
        for trip_index in active_indices:
            trip = trips[trip_index]
            previous_departure = parse_hhmm(trip["stop_times"][-1]["departure_hhmm"])
            while cursor < len(departures) and departures[cursor] < previous_departure:
                cursor += 1
            if cursor >= len(departures):
                continue
            if departures[cursor] - previous_departure > 20:
                continue
            departure = departures[cursor]
            cursor += 1
            trip["stop_times"].append(
                {
                    "sequence": len(trip["stop_times"]) + 1,
                    "station_name_raw": station_name,
                    "station_id": station_lookup[station_name]["station_id"],
                    "line_id": LINE_ID,
                    "arrival_hhmm": hhmm(departure),
                    "departure_hhmm": hhmm(departure),
                    "platform": None,
                }
            )
            next_active.append(trip_index)
        active_indices = next_active
    return trips


def main() -> int:
    station_seed = load_station_seed()
    station_departures = parse_station_departures()
    toward_tama_center = build_direction_instances(
        station_seed,
        station_departures,
        "toward_tama_center",
        [name for _, name in STATION_SEQUENCE],
        "多摩センター",
    )
    toward_kamikitadai = build_direction_instances(
        station_seed,
        station_departures,
        "toward_kamikitadai",
        [name for _, name in reversed(STATION_SEQUENCE)],
        "上北台",
    )
    output = {
        "id": "v3_tokyo_tama_monorail_weekday_train_instances_v0_1",
        "label": "V3 Tama Monorail weekday train instances from official station timetable PDFs",
        "version": "0.1.0",
        "service_day": SERVICE_DAY,
        "station_seed": station_seed,
        "train_instances": toward_tama_center + toward_kamikitadai,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Train instances: {len(output['train_instances'])}")
    print(f"Wrote: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
