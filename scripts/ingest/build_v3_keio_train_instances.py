#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests


ROOT = Path(__file__).resolve().parents[2]
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_keio_weekday_train_instances.json"
CHECKPOINT_EVERY = 1
CHECKPOINT_TRAINS_EVERY = 50
SERVICE_DAY = "2026-04-15"
TIMEOUT = 30
USER_AGENT = {"User-Agent": "Mozilla/5.0"}
OFFICIAL_TIMETABLE_URL = "https://www.keio.co.jp/train/timetable/"
API_BASE = "https://transfer-train.navitime.biz/api/keio"


def centroid(coords: list) -> tuple[float, float]:
    points: list[tuple[float, float]] = []

    def walk(node: list) -> None:
        if not node:
            return
        if isinstance(node[0], (int, float)):
            points.append((float(node[0]), float(node[1])))
            return
        for child in node:
            walk(child)

    walk(coords)
    lon = sum(p[0] for p in points) / len(points)
    lat = sum(p[1] for p in points) / len(points)
    return lon, lat


def load_station_seed() -> list[dict]:
    geojson = json.loads(N02_STATION_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for feature in geojson["features"]:
        props = feature["properties"]
        if props.get("N02_004") != "京王電鉄":
            continue
        name = props.get("N02_005")
        if not name or name in out:
            continue
        lon, lat = centroid(feature["geometry"]["coordinates"])
        out[name] = {
            "station_id": f"KEIO_{name}",
            "name_ja": name,
            "operator": "京王電鉄",
            "line_id": props.get("N02_003", ""),
            "lat": round(lat, 8),
            "lon": round(lon, 8),
            "n02_station_code": props.get("N02_005c"),
            "n02_group_code": props.get("N02_005g"),
        }
    return sorted(out.values(), key=lambda item: item["name_ja"])


def official_combos() -> list[tuple[str, str, str]]:
    text = requests.get(OFFICIAL_TIMETABLE_URL, timeout=TIMEOUT, headers=USER_AGENT).text
    combos = sorted(set(re.findall(r"station=(\d+)&line=(\d+)&direction=(\d+)", text)))
    return combos


def fetch_json(path: str) -> dict:
    response = requests.get(f"{API_BASE}{path}", timeout=TIMEOUT, headers=USER_AGENT)
    response.raise_for_status()
    return response.json()


def hhmm(value: str | None) -> str:
    if not value:
        return ""
    time_part = value.split("T", 1)[-1].split("+", 1)[0]
    return time_part[:5]


def station_name_to_seed_key(name: str) -> str:
    return name.replace("ヶ", "ケ")


def build_instances(station_lookup: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    source_reports: list[dict] = []
    train_instances: list[dict] = []
    seen_instances: set[str] = set()
    seen_timetables: set[tuple[str, str, str]] = set()

    combos = official_combos()
    total = len(combos)

    def write_checkpoint() -> None:
        payload = {
            "id": "v3_tokyo_keio_weekday_train_instances_v0_1",
            "label": "v3 Tokyo Keio weekday train instances",
            "version": "0.1.0",
            "service_day": SERVICE_DAY,
            "station_seed": sorted(station_lookup.values(), key=lambda item: item["name_ja"]),
            "source_reports": source_reports,
            "train_instances": sorted(
                train_instances,
                key=lambda item: (item["stop_times"][0]["departure_hhmm"], item["train_number"]),
            ),
        }
        OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    next_train_checkpoint = CHECKPOINT_TRAINS_EVERY

    for combo_index, (station_id, line_id, direction) in enumerate(combos, start=1):
        combo = (station_id, line_id, direction)
        if combo in seen_timetables:
            continue
        seen_timetables.add(combo)
        timetable_url = (
            f"/timetable/{station_id}/{line_id}/{direction}"
            f"?datetime={SERVICE_DAY}T06:00:00%2B09:00&target=weekday&lang=ja"
        )
        payload = fetch_json(timetable_url)
        timetables = payload.get("timetables") or []
        if not timetables:
            continue
        operations = timetables[0].get("operations", [])
        source_reports.append(
            {
                "station_id": station_id,
                "line_id": line_id,
                "direction": direction,
                "source_url": f"{API_BASE}{timetable_url}",
                "operation_count": sum(len(hour.get("minutes", [])) for hour in operations),
            }
        )
        for hour in operations:
            for minute in hour.get("minutes", []):
                operation_id = minute.get("id")
                train_no = minute.get("train_no")
                depart_time = minute.get("time")
                if not operation_id or not train_no or not depart_time:
                    continue
                detail_url = (
                    f"/stops/{station_id}/{line_id}?operation_id={operation_id}"
                    f"&train_no={train_no}&datetime={depart_time.replace('+', '%2B')}"
                    f"&all=1&lang=ja&direction={direction}"
                )
                detail = fetch_json(detail_url)
                raw_stops = detail.get("stops", [])
                stop_times = []
                for entry in raw_stops:
                    if "id" not in entry or "name" not in entry:
                        continue
                    station_name = station_name_to_seed_key(entry["name"])
                    station = station_lookup.get(station_name)
                    if station is None:
                        continue
                    arrival_hhmm = hhmm(entry.get("arrive_time") or entry.get("departure_time"))
                    departure_hhmm = hhmm(entry.get("departure_time") or entry.get("arrive_time"))
                    stop_times.append(
                        {
                            "sequence": len(stop_times) + 1,
                            "station_name_raw": entry["name"],
                            "station_id": station["station_id"],
                            "line_id": station.get("line_id"),
                            "arrival_hhmm": arrival_hhmm,
                            "departure_hhmm": departure_hhmm,
                            "platform": minute.get("platform"),
                        }
                    )
                if len(stop_times) < 2:
                    continue
                service_instance_id = f"KEIO_{operation_id}_{train_no}_{stop_times[0]['departure_hhmm']}"
                if service_instance_id in seen_instances:
                    continue
                seen_instances.add(service_instance_id)
                destinations = minute.get("destinations") or []
                headsign = destinations[0]["name"] if destinations else ""
                train_instances.append(
                    {
                        "service_instance_id": service_instance_id,
                        "train_number": train_no,
                        "service_name": "Keio",
                        "headsign": headsign,
                        "train_type": minute.get("type") or "",
                        "route_color": minute.get("color", "#d5007f").lstrip("#"),
                        "stop_times": stop_times,
                        "source_url": f"{API_BASE}{detail_url}",
                    }
                )
                if len(train_instances) >= next_train_checkpoint:
                    write_checkpoint()
                    print(
                        f"[keio] train checkpoint {len(train_instances)} trains "
                        f"after combo {combo_index}/{total}"
                    )
                    next_train_checkpoint += CHECKPOINT_TRAINS_EVERY

        if combo_index % CHECKPOINT_EVERY == 0:
            write_checkpoint()
            print(
                f"[keio] checkpoint {combo_index}/{total}: "
                f"{len(source_reports)} source pages, {len(train_instances)} trains"
            )

    write_checkpoint()
    return source_reports, sorted(
        train_instances,
        key=lambda item: (item["stop_times"][0]["departure_hhmm"], item["train_number"]),
    )


def main() -> int:
    station_seed = load_station_seed()
    station_lookup = {entry["name_ja"]: entry for entry in station_seed}
    source_reports, train_instances = build_instances(station_lookup)
    payload = {
        "id": "v3_tokyo_keio_weekday_train_instances_v0_1",
        "label": "v3 Tokyo Keio weekday train instances",
        "version": "0.1.0",
        "service_day": SERVICE_DAY,
        "station_seed": station_seed,
        "source_reports": source_reports,
        "train_instances": train_instances,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[keio] wrote {len(train_instances)} train instances -> {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
