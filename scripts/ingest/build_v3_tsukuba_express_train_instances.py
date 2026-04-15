#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_tsukuba_express_weekday_train_instances.json"
SERVICE_DAY = "2026-04-15"
TIMEOUT = 30
ROUTE_COLOR = "003B83"
API_BASE = "https://transfer-train.navitime.biz/api/tx"
USER_AGENT = {"User-Agent": "Mozilla/5.0"}


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
        if props.get("N02_004") != "首都圏新都市鉄道":
            continue
        name = props.get("N02_005")
        if not name or name in out:
            continue
        lon, lat = centroid(feature["geometry"]["coordinates"])
        out[name] = {
            "station_id": f"TX_{name}",
            "name_ja": name,
            "operator": "首都圏新都市鉄道",
            "line_id": props.get("N02_003", ""),
            "lat": round(lat, 8),
            "lon": round(lon, 8),
            "n02_station_code": props.get("N02_005c"),
            "n02_group_code": props.get("N02_005g"),
        }
    return sorted(out.values(), key=lambda item: item["name_ja"])


def fetch_json(path: str) -> dict:
    response = requests.get(f"{API_BASE}{path}", timeout=TIMEOUT, headers=USER_AGENT)
    response.raise_for_status()
    return response.json()


def hhmm_from_time(value: str) -> str:
    time_part = value.split("T", 1)[-1].split("+", 1)[0]
    return time_part[:5].lstrip("0") if time_part.startswith("0") else time_part[:5]


def build_instances(station_lookup: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    source_reports: list[dict] = []
    seen: set[str] = set()
    train_instances: list[dict] = []

    for direction in ("0", "1"):
        payload = fetch_json(
            f"/trains/timetable/weekday/{direction}?datetime={SERVICE_DAY}T06:00:00%2B09:00&lang=ja"
        )
        source_reports.append(
            {
                "direction": direction,
                "source_url": f"{API_BASE}/trains/timetable/weekday/{direction}?datetime={SERVICE_DAY}T06:00:00%2B09:00&lang=ja",
                "train_count": len(payload.get("train_numbers", [])),
                "stop_count": len(payload.get("stops", [])),
            }
        )
        train_numbers = payload["train_numbers"]
        train_types = payload["train_types"]
        terminals = payload.get("departures" if direction == "0" else "destinations", [])
        platforms = payload.get("platform", {}).get("numbers", [None] * len(train_numbers))
        stops = payload["stops"]

        for index, train_number in enumerate(train_numbers):
            stop_times = []
            for stop in stops:
                raw = stop["times"][index]
                if raw in (None, "", "↓"):
                    continue
                station = station_lookup.get(stop["name"])
                if station is None:
                    continue
                hhmm = raw if len(raw) == 5 else f"0{raw}"
                if stop["dep_or_arv"] == "着":
                    arrival_hhmm = hhmm
                    departure_hhmm = hhmm
                else:
                    arrival_hhmm = hhmm
                    departure_hhmm = hhmm
                stop_times.append(
                    {
                        "sequence": len(stop_times) + 1,
                        "station_name_raw": stop["name"],
                        "station_id": station["station_id"],
                        "line_id": station.get("line_id"),
                        "arrival_hhmm": arrival_hhmm,
                        "departure_hhmm": departure_hhmm,
                        "platform": platforms[index],
                    }
                )
            if len(stop_times) < 2:
                continue
            service_instance_id = f"TX_{direction}_{train_number}_{stop_times[0]['departure_hhmm']}"
            if service_instance_id in seen:
                continue
            seen.add(service_instance_id)
            train_instances.append(
                {
                    "service_instance_id": service_instance_id,
                    "train_number": train_number,
                    "service_name": "Tsukuba Express",
                    "headsign": terminals[index] if index < len(terminals) else "",
                    "train_type": train_types[index]["name"],
                    "route_color": ROUTE_COLOR,
                    "stop_times": stop_times,
                    "source_url": source_reports[-1]["source_url"],
                }
            )

    return source_reports, sorted(
        train_instances,
        key=lambda item: (item["stop_times"][0]["departure_hhmm"], item["train_number"]),
    )


def main() -> int:
    station_seed = load_station_seed()
    station_lookup = {entry["name_ja"]: entry for entry in station_seed}
    source_reports, train_instances = build_instances(station_lookup)
    payload = {
        "id": "v3_tokyo_tsukuba_express_weekday_train_instances_v0_1",
        "label": "v3 Tokyo Tsukuba Express weekday train instances",
        "version": "0.1.0",
        "service_day": SERVICE_DAY,
        "station_seed": station_seed,
        "source_reports": source_reports,
        "train_instances": train_instances,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[tx] wrote {len(train_instances)} train instances -> {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
