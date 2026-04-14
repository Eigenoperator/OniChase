#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_yurikamome_weekday_train_instances.json"
DOWNLOAD_DIR = ROOT / "data" / "v3_external" / "yurikamome"
SERVICE_DAY = "2026-04-13"

LINE_ID = "YURIKAMOME"
SERVICE_NAME = "Yurikamome"
ROUTE_COLOR = "009FE8"

STATION_SEQUENCE = [
    ("U01", "新橋"),
    ("U02", "汐留"),
    ("U03", "竹芝"),
    ("U04", "日の出"),
    ("U05", "芝浦ふ頭"),
    ("U06", "お台場海浜公園"),
    ("U07", "台場"),
    ("U08", "東京国際クルーズターミナル"),
    ("U09", "テレコムセンター"),
    ("U10", "青海"),
    ("U11", "東京ビッグサイト"),
    ("U12", "有明"),
    ("U13", "有明テニスの森"),
    ("U14", "市場前"),
    ("U15", "新豊洲"),
    ("U16", "豊洲"),
]


def ensure_pdf(pdf_code: str) -> Path:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = DOWNLOAD_DIR / f"{pdf_code}.pdf"
    if path.exists():
        return path
    url = f"https://www.yurikamome.co.jp/station-timetable/pdf/time/{pdf_code}.pdf"
    urllib.request.urlretrieve(url, path)
    return path


def pdf_text(path: Path) -> str:
    return subprocess.check_output(["pdftotext", "-layout", str(path), "-"]).decode("utf-8", "ignore")


def parse_terminal_weekday_departures(page: str) -> list[int]:
    departures: list[int] = []
    for raw in page.splitlines():
        match = re.match(r"^\s*(\d{1,2})\s+([0-9 ]+?)\s{2,}", raw.rstrip())
        if not match:
            continue
        hour = int(match.group(1))
        for minute_text in re.findall(r"\b(\d{1,2})\b", match.group(2)):
            minute = int(minute_text)
            if minute < 60:
                departures.append(to_service_minute(hour, minute))
    return departures


def parse_intermediate_weekday_departures(page: str) -> tuple[list[int], list[int]]:
    toward_toyosu: list[int] = []
    toward_shimbashi: list[int] = []
    for raw in page.splitlines():
        match = re.match(
            r"^\s*(\d{1,2})\s+([0-9 ]+?)\s{2,}(\d{1,2})\s+([0-9 ]+)",
            raw.rstrip(),
        )
        if not match:
            continue
        left_hour = int(match.group(1))
        right_hour = int(match.group(3))
        for minute_text in re.findall(r"\b(\d{1,2})\b", match.group(2)):
            minute = int(minute_text)
            if minute < 60:
                toward_toyosu.append(to_service_minute(left_hour, minute))
        for minute_text in re.findall(r"\b(\d{1,2})\b", match.group(4)):
            minute = int(minute_text)
            if minute < 60:
                toward_shimbashi.append(to_service_minute(right_hour, minute))
    return toward_toyosu, toward_shimbashi


def to_service_minute(hour: int, minute: int) -> int:
    return (24 * 60 + minute) if hour == 0 else (hour * 60 + minute)


def hhmm(total_minutes: int) -> str:
    hour = total_minutes // 60
    minute = total_minutes % 60
    return f"{hour:02d}:{minute:02d}"


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
    geojson = json.loads(N02_STATION_PATH.read_text())
    lookup: dict[str, dict] = {}
    for feature in geojson["features"]:
        props = feature["properties"]
        if props.get("N02_004") != "ゆりかもめ":
            continue
        if props.get("N02_003") != "東京臨海新交通臨海線":
            continue
        name = props.get("N02_005")
        if not name:
            continue
        lon, lat = centroid(feature["geometry"]["coordinates"])
        lookup[name] = {
            "station_id": f"YURIKAMOME_{next(code for code, station_name in STATION_SEQUENCE if station_name == name)}",
            "station_code": next(code for code, station_name in STATION_SEQUENCE if station_name == name),
            "name_ja": name,
            "operator": "ゆりかもめ",
            "line_id": LINE_ID,
            "lat": round(lat, 8),
            "lon": round(lon, 8),
            "n02_station_code": props.get("N02_005c"),
            "n02_group_code": props.get("N02_005g"),
        }
    return [lookup[name] for _, name in STATION_SEQUENCE]


def load_station_departures() -> dict[str, dict[str, list[int]]]:
    station_departures: dict[str, dict[str, list[int]]] = {}
    for index, (_, station_name) in enumerate(STATION_SEQUENCE, start=1):
        pdf_path = ensure_pdf(f"u-{index:02d}")
        text = pdf_text(pdf_path)
        pages = [page for page in text.split("\f") if page.strip()]
        weekday_page = next(page for page in pages if "平 日" in page[:200])
        if station_name == "新橋":
            station_departures[station_name] = {
                "toward_toyosu": parse_terminal_weekday_departures(weekday_page),
                "toward_shimbashi": [],
            }
        elif station_name == "豊洲":
            station_departures[station_name] = {
                "toward_toyosu": [],
                "toward_shimbashi": parse_terminal_weekday_departures(weekday_page),
            }
        else:
            toward_toyosu, toward_shimbashi = parse_intermediate_weekday_departures(weekday_page)
            station_departures[station_name] = {
                "toward_toyosu": toward_toyosu,
                "toward_shimbashi": toward_shimbashi,
            }
    return station_departures


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
    append_terminal_arrivals(trips, order, direction_key, station_departures)
    return trips


def append_terminal_arrivals(
    trips: list[dict],
    order: list[str],
    direction_key: str,
    station_departures: dict[str, dict[str, list[int]]],
) -> None:
    if len(order) < 2:
        return
    terminal_name = order[-1]
    prev_station_name = order[-2]
    if direction_key == "toward_toyosu":
        terminal_runtime = 2
    else:
        terminal_runtime = 1
    for trip in trips:
        if trip["stop_times"][-1]["station_name_raw"] != prev_station_name:
            continue
        arrival = parse_hhmm(trip["stop_times"][-1]["departure_hhmm"]) + terminal_runtime
        trip["stop_times"].append(
            {
                "sequence": len(trip["stop_times"]) + 1,
                "station_name_raw": terminal_name,
                "station_id": f"YURIKAMOME_{next(code for code, station_name in STATION_SEQUENCE if station_name == terminal_name)}",
                "line_id": LINE_ID,
                "arrival_hhmm": hhmm(arrival),
                "departure_hhmm": hhmm(arrival),
                "platform": None,
            }
        )


def parse_hhmm(value: str) -> int:
    hour_text, minute_text = value.split(":")
    return int(hour_text) * 60 + int(minute_text)


def main() -> None:
    station_seed = load_station_seed()
    station_departures = load_station_departures()

    toward_toyosu_order = [name for _, name in STATION_SEQUENCE]
    toward_shimbashi_order = list(reversed(toward_toyosu_order))

    toward_toyosu_trips = build_direction_instances(
        station_seed,
        station_departures,
        "toward_toyosu",
        toward_toyosu_order,
        "豊洲",
    )
    toward_shimbashi_trips = build_direction_instances(
        station_seed,
        station_departures,
        "toward_shimbashi",
        toward_shimbashi_order,
        "新橋",
    )

    output = {
        "id": "v3_tokyo_yurikamome_weekday_train_instances",
        "label": "v3 Tokyo Yurikamome Weekday Train Instances",
        "version": 1,
        "service_day": SERVICE_DAY,
        "source": "Official Yurikamome station timetable PDFs (weekday pages)",
        "station_seed": station_seed,
        "station_departure_counts": {
            station_name: {
                direction: len(departures)
                for direction, departures in data.items()
            }
            for station_name, data in station_departures.items()
        },
        "train_instances": toward_toyosu_trips + toward_shimbashi_trips,
        "train_length_histogram": Counter(len(trip["stop_times"]) for trip in toward_toyosu_trips + toward_shimbashi_trips),
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Toward Toyosu trips: {len(toward_toyosu_trips)}")
    print(f"Toward Shimbashi trips: {len(toward_shimbashi_trips)}")
    print(f"Wrote: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
