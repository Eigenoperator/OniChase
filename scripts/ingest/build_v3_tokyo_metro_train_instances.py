#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_tokyo_metro_weekday_train_instances.json"
SERVICE_DAY = "2026-04-15"
TIMEOUT = 30
USER_AGENT = {"User-Agent": "Mozilla/5.0"}
LINE_PAGE_BASE = "https://www.tokyometro.jp/station"
API_BASE = "https://transfer.tokyometro.jp/api"
CHECKPOINT_OPERATIONS_EVERY = 100
TIMETABLE_DISCOVERY_WORKERS = 12

LINE_SLUGS = {
    "line_ginza": ("G", "3号線銀座線", "#FF9500"),
    "line_marunouchi": ("M", "4号線丸ノ内線", "#E60012"),
    "line_hibiya": ("H", "2号線日比谷線", "#B5B5AC"),
    "line_tozai": ("T", "5号線東西線", "#00A7DB"),
    "line_chiyoda": ("C", "9号線千代田線", "#00BB85"),
    "line_yurakucho": ("Y", "8号線有楽町線", "#C1A470"),
    "line_hanzomon": ("Z", "11号線半蔵門線", "#8F76D6"),
    "line_namboku": ("N", "7号線南北線", "#00ADA9"),
    "line_fukutoshin": ("F", "13号線副都心線", "#9C5E31"),
}
BRANCH_PREFIXES = {
    "Mb": ("4号線丸ノ内線分岐線", "#E60012"),
}


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


def normalize_station_name(name: str) -> str:
    return (
        name.replace("ヶ", "ケ")
        .replace("ケ丘", "ヶ丘")
        .replace("ノ", "の")
        .replace("之", "の")
        .strip()
    )


def line_metadata_from_numbering(numbering: str) -> tuple[str, str]:
    if numbering.startswith("Mb"):
        return BRANCH_PREFIXES["Mb"]
    prefix = re.match(r"[A-Z]+", numbering)
    if not prefix:
        return "", "#000000"
    symbol = prefix.group(0)
    for _, (expected_symbol, line_name, color) in LINE_SLUGS.items():
        if symbol == expected_symbol:
            return line_name, color
    return "", "#000000"


def load_station_indexes() -> tuple[list[dict], dict[str, dict], dict[str, list[dict]]]:
    geojson = json.loads(N02_STATION_PATH.read_text(encoding="utf-8"))
    metro_seed: dict[str, dict] = {}
    all_by_name: dict[str, list[dict]] = defaultdict(list)

    for feature in geojson["features"]:
        props = feature["properties"]
        name_raw = props.get("N02_005")
        if not name_raw:
            continue
        name = normalize_station_name(name_raw)
        lon, lat = centroid(feature["geometry"]["coordinates"])
        entry = {
            "station_id": f"N02_{props.get('N02_004','')}_{props.get('N02_003','')}_{name_raw}",
            "name_ja": name_raw,
            "operator": props.get("N02_004", ""),
            "line_id": props.get("N02_003", ""),
            "lat": round(lat, 8),
            "lon": round(lon, 8),
            "n02_station_code": props.get("N02_005c"),
            "n02_group_code": props.get("N02_005g"),
        }
        all_by_name[name].append(entry)
        if props.get("N02_004") != "東京地下鉄":
            continue
        metro_seed.setdefault(
            name,
            {
                "station_id": f"TOKYO_METRO_{name_raw}",
                "name_ja": name_raw,
                "operator": "東京地下鉄",
                "line_id": props.get("N02_003", ""),
                "lat": round(lat, 8),
                "lon": round(lon, 8),
                "n02_station_code": props.get("N02_005c"),
                "n02_group_code": props.get("N02_005g"),
            },
        )

    station_seed = sorted(metro_seed.values(), key=lambda item: item["name_ja"])
    station_lookup = {normalize_station_name(item["name_ja"]): item for item in station_seed}
    return station_seed, station_lookup, all_by_name


def fetch_text(url: str) -> str:
    response = requests.get(url, timeout=TIMEOUT, headers=USER_AGENT)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def discover_numberings() -> list[str]:
    numberings: set[str] = set()
    for slug in LINE_SLUGS:
        html = fetch_text(f"{LINE_PAGE_BASE}/{slug}/index.html")
        found = set(re.findall(r"([A-Z][a-z]?\d{2})", html))
        for numbering in found:
            if numbering.startswith("Mb"):
                numberings.add(numbering)
                continue
            prefix = re.match(r"[A-Z]+", numbering)
            if prefix and any(prefix.group(0) == meta[0] for meta in LINE_SLUGS.values()):
                numberings.add(numbering)
    return sorted(numberings, key=lambda item: (re.sub(r"\d+", "", item), item))


def fetch_json(path: str, *, params: dict | None = None) -> dict:
    response = requests.get(
        f"{API_BASE}{path}",
        params=params,
        timeout=TIMEOUT,
        headers=USER_AGENT,
    )
    response.raise_for_status()
    return response.json()


def request_url(path: str, params: dict) -> str:
    return requests.Request("GET", f"{API_BASE}{path}", params=params).prepare().url


def hhmm(value: str | None) -> str:
    if not value:
        return ""
    time_part = value.split("T", 1)[-1].split("+", 1)[0]
    return time_part[:5]


def resolve_station_seed(
    stop: dict,
    station_lookup: dict[str, dict],
    station_seed: list[dict],
    all_by_name: dict[str, list[dict]],
) -> dict:
    name = normalize_station_name(stop.get("name", ""))
    existing = station_lookup.get(name)
    if existing:
        return existing

    candidates = all_by_name.get(name, [])
    if len(candidates) == 1:
        candidate = candidates[0]
        resolved = {
            "station_id": f"EXT_{candidate['station_id']}",
            "name_ja": candidate["name_ja"],
            "operator": candidate["operator"],
            "line_id": candidate["line_id"],
            "lat": candidate["lat"],
            "lon": candidate["lon"],
            "n02_station_code": candidate.get("n02_station_code"),
            "n02_group_code": candidate.get("n02_group_code"),
        }
    else:
        line_name, line_color = line_metadata_from_numbering(
            next((n["symbol"] for n in stop.get("numberings", []) if n.get("symbol")), "")
        )
        resolved = {
            "station_id": f"TM_EXT_{stop.get('id', name)}",
            "name_ja": stop.get("name", name),
            "operator": "UNKNOWN_THROUGH",
            "line_id": line_name,
            "lat": None,
            "lon": None,
            "n02_station_code": None,
            "n02_group_code": None,
            "line_color_hint": line_color,
        }

    station_lookup[name] = resolved
    station_seed.append(resolved)
    return resolved


def build_instances(
    station_seed: list[dict],
    station_lookup: dict[str, dict],
    all_by_name: dict[str, list[dict]],
) -> tuple[list[dict], list[dict]]:
    source_reports: list[dict] = []
    train_instances: list[dict] = []
    operations: dict[tuple[str, str, str], dict] = {}

    numberings = discover_numberings()
    timetable_jobs = [(numbering, direction) for numbering in numberings for direction in ("0", "1")]

    def fetch_timetable(job: tuple[str, str]) -> tuple[str, str, dict | None]:
        numbering, direction = job
        params = {
            "numbering": numbering,
            "direction": direction,
            "schedule": "weekday",
            "lang": "ja",
        }
        try:
            payload = fetch_json("/timetable", params=params)
        except requests.HTTPError:
            return numbering, direction, None
        return numbering, direction, payload

    with ThreadPoolExecutor(max_workers=TIMETABLE_DISCOVERY_WORKERS) as executor:
        future_map = {executor.submit(fetch_timetable, job): job for job in timetable_jobs}
        for completed, future in enumerate(as_completed(future_map), start=1):
            numbering, direction = future_map[future]
            _, _, payload = future.result()
            if payload is None:
                continue
            params = {
                "numbering": numbering,
                "direction": direction,
                "schedule": "weekday",
                "lang": "ja",
            }
            items = payload.get("timetable_items", [])
            source_reports.append(
                {
                    "numbering": numbering,
                    "direction": direction,
                    "source_url": request_url("/timetable", params),
                    "item_count": len(items),
                    "operation_count": sum(
                        len(timetable.get("operations", []))
                        for item in items
                        for timetable in item.get("timetables", [])
                    ),
                }
            )
            for item in items:
                line_info = item.get("line", {})
                route_color = (line_info.get("mark") or {}).get("color") or line_metadata_from_numbering(numbering)[1]
                station_info = item.get("station", {})
                for timetable in item.get("timetables", []):
                    for op in timetable.get("operations", []):
                        operation_id = op.get("id")
                        time = op.get("time")
                        train_no = op.get("train_no") or ""
                        if not operation_id or not time:
                            continue
                        key = (operation_id, train_no)
                        operations.setdefault(
                            key,
                            {
                                "operation_id": operation_id,
                                "numbering": numbering,
                                "station_numbering": next(
                                    (
                                        n.get("symbol")
                                        for n in station_info.get("numberings", [])
                                        if n.get("symbol")
                                    ),
                                    numbering,
                                ),
                                "train_number": train_no,
                                "time": time,
                                "train_type": op.get("type") or "",
                                "service_name": op.get("train_name") or line_info.get("name", "Tokyo Metro"),
                                "headsign": ", ".join(op.get("destinations") or []),
                                "route_color": route_color.lstrip("#"),
                                "line_name": line_info.get("name") or "",
                            },
                        )
            if completed % 25 == 0:
                print(
                    f"[tokyo_metro] timetable discovery {completed}/{len(timetable_jobs)}: "
                    f"{len(source_reports)} pages, {len(operations)} ops"
                )

    print(
        f"[tokyo_metro] discovered {len(source_reports)} source pages and "
        f"{len(operations)} unique operations"
    )

    seen_instances: set[str] = set()

    def write_checkpoint() -> None:
        payload = {
            "id": "v3_tokyo_tokyo_metro_weekday_train_instances_v0_1",
            "label": "v3 Tokyo Metro weekday train instances",
            "version": "0.1.0",
            "service_day": SERVICE_DAY,
            "station_seed": sorted(station_seed, key=lambda item: (item["name_ja"], item["station_id"])),
            "source_reports": source_reports,
            "train_instances": sorted(
                train_instances,
                key=lambda item: (item["stop_times"][0]["departure_hhmm"], item["train_number"]),
            ),
        }
        OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    write_checkpoint()

    for index, op in enumerate(operations.values(), start=1):
        detail = fetch_json(
            "/stop",
            params={
                "numbering": op["station_numbering"],
                "operation": op["operation_id"],
                "datetime": op["time"],
                "lang": "ja",
            },
        )
        raw_stops = detail.get("stops", [])
        stop_times = []
        for entry in raw_stops:
            station = resolve_station_seed(entry, station_lookup, station_seed, all_by_name)
            stop_times.append(
                {
                    "sequence": len(stop_times) + 1,
                    "station_name_raw": entry.get("name", station["name_ja"]),
                    "station_id": station["station_id"],
                    "line_id": station.get("line_id"),
                    "arrival_hhmm": hhmm(entry.get("arrival_time") or entry.get("departure_time")),
                    "departure_hhmm": hhmm(entry.get("departure_time") or entry.get("arrival_time")),
                    "platform": None,
                }
            )
        if len(stop_times) < 2:
            continue
        operation_id = op["operation_id"]
        service_instance_id = f"TM_{operation_id}_{op['train_number']}_{stop_times[0]['departure_hhmm']}"
        if service_instance_id in seen_instances:
            continue
        seen_instances.add(service_instance_id)
        train_instances.append(
            {
                "service_instance_id": service_instance_id,
                "train_number": op["train_number"],
                "service_name": op["service_name"],
                "headsign": detail.get("train_info", {}).get("destination") or op["headsign"],
                "train_type": op["train_type"],
                "route_color": op["route_color"],
                "stop_times": stop_times,
                "source_url": requests.Request(
                    "GET",
                    f"{API_BASE}/stop",
                    params={
                        "numbering": op["station_numbering"],
                        "operation": operation_id,
                        "datetime": op["time"],
                        "lang": "ja",
                    },
                ).prepare().url,
            }
        )
        if index % CHECKPOINT_OPERATIONS_EVERY == 0:
            write_checkpoint()
            print(
                f"[tokyo_metro] checkpoint {index}/{len(operations)} ops: "
                f"{len(train_instances)} trains, {len(station_seed)} stations"
            )

    write_checkpoint()
    return source_reports, sorted(
        train_instances,
        key=lambda item: (item["stop_times"][0]["departure_hhmm"], item["train_number"]),
    )


def main() -> int:
    station_seed, station_lookup, all_by_name = load_station_indexes()
    source_reports, train_instances = build_instances(station_seed, station_lookup, all_by_name)
    payload = {
        "id": "v3_tokyo_tokyo_metro_weekday_train_instances_v0_1",
        "label": "v3 Tokyo Metro weekday train instances",
        "version": "0.1.0",
        "service_day": SERVICE_DAY,
        "station_seed": sorted(station_seed, key=lambda item: (item["name_ja"], item["station_id"])),
        "source_reports": source_reports,
        "train_instances": train_instances,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[tokyo_metro] wrote {len(train_instances)} train instances -> {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
