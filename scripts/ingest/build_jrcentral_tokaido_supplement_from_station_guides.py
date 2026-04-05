#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests

from train_instance_normalization import build_station_lookup


SERVICE_NAME_ALIASES = {
    "のぞみ": "Nozomi",
    "ひかり": "Hikari",
    "こだま": "Kodama",
}

LINE_JSON_URL = "https://railway.jr-central.co.jp/common/_api/time-schedule/list_line_station.json"
RESULT_CONTROL_URL = "https://railway.jr-central.co.jp/time-schedule/search/ResultControl?st={station_code}"

TRAIN_BLOCK_RE = re.compile(
    r"<TD nowrap class=S>(?P<raw>[^<]+?)<TR><TD nowrap class=M[A-Z]+><B>(?P<minute>\d{1,2})</B>(?:◆)?<TR><TD nowrap class=S>(?P<dest>[^<]+)",
    re.S,
)
HEADER_RE = re.compile(r"<FONT size=4><B>(?P<hour>\d{1,2})</B></FONT>", re.S)
PAGE_TITLE_RE = re.compile(r"<FONT size=4>(?P<station>[^<]+?)駅　</FONT><FONT size=5>東海道・山陽新幹線　(?P<dir>[^<]+)</FONT>", re.S)
RAW_SERVICE_RE = re.compile(r"(?P<service>[ぁ-んァ-ヶー一-龯]+)(?P<number>\d+)号")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_station_timetable_page(html: str, station_name_ja: str, station_id: str, direction_label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    hour_iter = list(HEADER_RE.finditer(html))
    for idx, hour_match in enumerate(hour_iter):
        hour = int(hour_match.group("hour"))
        start = hour_match.end()
        end = hour_iter[idx + 1].start() if idx + 1 < len(hour_iter) else len(html)
        hour_chunk = html[start:end]
        for train_match in TRAIN_BLOCK_RE.finditer(hour_chunk):
            raw = train_match.group("raw").strip()
            minute = int(train_match.group("minute"))
            destination = train_match.group("dest").strip()
            service_match = RAW_SERVICE_RE.search(raw)
            if not service_match:
                continue
            service_name_raw = service_match.group("service")
            service_number = int(service_match.group("number"))
            service_name = SERVICE_NAME_ALIASES.get(service_name_raw, service_name_raw)
            hhmm = f"{hour:02d}:{minute:02d}"
            rows.append(
                {
                    "station_name_ja": station_name_ja,
                    "station_id": station_id,
                    "direction_label": direction_label,
                    "departure_hhmm": hhmm,
                    "train_name_raw": raw,
                    "service_name": service_name,
                    "service_number": service_number,
                    "destination_name_raw": destination,
                }
            )
    return rows


def fetch_tokaido_station_links() -> list[dict[str, str]]:
    data = requests.get(LINE_JSON_URL, timeout=20).json()
    for line in data["line_list"]:
        if line["line_name"] == "東海道新幹線":
            return line["station"]
    raise RuntimeError("JR Central Tokaido Shinkansen station list not found")


def fetch_station_timetable_links(station_code: str) -> dict[str, str]:
    obj = requests.get(RESULT_CONTROL_URL.format(station_code=station_code), timeout=20).json()
    links: dict[str, str] = {}
    for item in obj.get("timetable", []):
        if item["text"] == "東海道新幹線[上]":
            links["inbound"] = item["href"]
        elif item["text"] == "東海道新幹線[下]":
            links["outbound"] = item["href"]
    return links


def fetch_and_parse_station_page(url: str, station_name_ja: str, station_id: str, direction_label: str) -> list[dict[str, Any]]:
    html = requests.get(url, timeout=20).content.decode("euc_jp", "replace")
    return parse_station_timetable_page(html, station_name_ja, station_id, direction_label)


def station_order_map(routes: list[dict[str, Any]]) -> dict[str, int]:
    for route in routes:
        if route["id"] == "TOKAIDO":
            return {station_id: idx for idx, station_id in enumerate(route["station_ids"])}
    raise RuntimeError("TOKAIDO route not found")


def aggregate_rows(rows: list[dict[str, Any]], route_order: dict[str, int]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["service_name"], row["service_number"], row["direction_label"])].append(row)

    train_instances: list[dict[str, Any]] = []
    for (service_name, service_number, direction_label), group_rows in grouped.items():
        unique_by_station: dict[str, dict[str, Any]] = {}
        for row in group_rows:
            station_id = row["station_id"]
            current = unique_by_station.get(station_id)
            if current is None:
                unique_by_station[station_id] = row
            else:
                if direction_label == "outbound":
                    if row["departure_hhmm"] < current["departure_hhmm"]:
                        unique_by_station[station_id] = row
                else:
                    if row["departure_hhmm"] > current["departure_hhmm"]:
                        unique_by_station[station_id] = row

        ordered_rows = sorted(
            unique_by_station.values(),
            key=lambda row: route_order[row["station_id"]],
            reverse=(direction_label == "inbound"),
        )

        stop_times = []
        for idx, row in enumerate(ordered_rows, start=1):
            stop_times.append(
                {
                    "sequence": idx,
                    "station_name_raw": row["station_name_ja"],
                    "station_id": row["station_id"],
                    "line_id": "SHINKANSEN_TOKAIDO_SANYO",
                    "departure_hhmm": row["departure_hhmm"],
                    "loop_pass_index": 1,
                }
            )

        first_station_id = ordered_rows[0]["station_id"]
        if first_station_id in {"TOKYO", "SHIN_OSAKA"}:
            continue

        display_name = f"{service_name} {service_number}"
        train_instances.append(
            {
                "train_number": f"JRC_{service_name.upper()}_{service_number}_{direction_label.upper()}",
                "train_name_raw": f"{ordered_rows[0]['train_name_raw']}",
                "display_name": display_name,
                "service_name": service_name,
                "service_number": service_number,
                "direction_label": direction_label,
                "service_instance_id": f"{service_name}_{service_number}_{direction_label}",
                "stop_times": stop_times,
            }
        )

    train_instances.sort(
        key=lambda train: (
            train["stop_times"][0]["departure_hhmm"],
            train["service_name"],
            train["service_number"],
            train["direction_label"],
        )
    )
    return train_instances


def main() -> int:
    parser = argparse.ArgumentParser(description="Build JR Central Tokaido supplemental train instances from official station guides.")
    parser.add_argument("--stations", required=True)
    parser.add_argument("--routes", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()

    stations_data = load_json(Path(args.stations))
    routes_data = load_json(Path(args.routes))
    station_lookup = build_station_lookup(stations_data)
    route_order = station_order_map(routes_data)

    all_rows: list[dict[str, Any]] = []
    station_entries = fetch_tokaido_station_links()
    for station_entry in station_entries:
        station_name_ja = station_entry["name"]
        station_code = station_entry["code"]
        station_id = station_lookup.get(station_name_ja)
        if not station_id:
            continue
        links = fetch_station_timetable_links(station_code)
        if "outbound" in links:
            all_rows.extend(fetch_and_parse_station_page(links["outbound"], station_name_ja, station_id, "outbound"))
        if "inbound" in links:
            all_rows.extend(fetch_and_parse_station_page(links["inbound"], station_name_ja, station_id, "inbound"))

    train_instances = aggregate_rows(all_rows, route_order)
    output = {
        "id": args.dataset_id,
        "label": args.label,
        "version": "0.1.0",
        "operator_id": "JR_CENTRAL",
        "service_day": "weekday",
        "route_family": "TOKAIDO_SUPPLEMENT",
        "train_instances": train_instances,
    }
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Station departure rows: {len(all_rows)}")
    print(f"Supplemental train instances: {len(train_instances)}")
    print(f"Wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
