#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from html import unescape


TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(TAG_RE.sub(" ", value))).strip()


def extract_table(html: str) -> str:
    match = re.search(r'<table id="tbl_train"[^>]*>(.*?)</table>', html, re.DOTALL)
    if not match:
        raise ValueError("Could not find train detail table.")
    return match.group(1)


def extract_labeled_cells(table_html: str, labels: tuple[str, ...]) -> list[str]:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"<th>(?:{label_pattern})</th>(.*?)</tr>", table_html, re.DOTALL)
    if not match:
        return []
    cells = re.findall(r"<td[^>]*colspan=\"2\"[^>]*>(.*?)</td>", match.group(1), re.DOTALL)
    return [strip_tags(cell) for cell in cells]


def extract_train_numbers(table_html: str) -> list[str]:
    values = extract_labeled_cells(table_html, ("Train number", "列車番号"))
    if not values:
        raise ValueError("Could not find train number row.")
    return values


def extract_train_names(table_html: str) -> list[str]:
    return extract_labeled_cells(table_html, ("Train name", "列車名"))


def extract_train_types(table_html: str) -> list[str]:
    return extract_labeled_cells(table_html, ("Train type", "列車種別"))


def extract_rows(table_html: str) -> list[str]:
    return re.findall(r'<tr class="time">(.*?)</tr>', table_html, re.DOTALL)


def extract_station_name(row_html: str) -> str:
    match = re.search(r'<th class="time">(.*?)</th>', row_html, re.DOTALL)
    if not match:
        return ""
    return strip_tags(match.group(1))


def extract_time_platform_cells(row_html: str) -> list[tuple[str, str]]:
    matches = re.findall(
        r'<td class="time">(.*?)</td>\s*<td class="platform">(.*?)</td>',
        row_html,
        re.DOTALL,
    )
    return [(time_html, platform_html) for time_html, platform_html in matches]


def parse_time_cell(cell_html: str) -> dict[str, str]:
    entries = re.findall(r'(\d{2}:\d{2})\s*<span class="dep_arr">(Arr\.|Dep\.)</span>', cell_html)
    result: dict[str, str] = {}
    for hhmm, kind in entries:
        if kind == "Arr.":
            result["arrival_hhmm"] = hhmm
        elif kind == "Dep.":
            result["departure_hhmm"] = hhmm
    jp_entries = re.findall(r"(\d{2}:\d{2})\s*(着|発)", strip_tags(cell_html))
    for hhmm, kind in jp_entries:
        if kind == "着":
            result["arrival_hhmm"] = hhmm
        elif kind == "発":
            result["departure_hhmm"] = hhmm
    return result


def parse_platform_cell(cell_html: str) -> str | None:
    value = strip_tags(cell_html)
    return value or None


def parse_direction(html: str) -> str | None:
    match = re.search(r"Yamanote Line for (.*?)\s+\((Clockwise|Counterclockwise)\)", html)
    if not match:
        return None
    return match.group(2).lower()


def parse_source_month(html: str) -> str | None:
    match = re.search(r"based on ([A-Za-z]+\.?\s+\d{4}) issue", html)
    if not match:
        return None
    return match.group(1)


def split_service_name(raw_name: str) -> tuple[str | None, str | None]:
    value = raw_name.strip()
    if not value:
        return None, None
    match = re.match(r"^(.*?)\s*(\d+号)$", value)
    if not match:
        match = re.match(r"^(.*?)(\d+)$", value)
    if not match:
        return value, None
    return match.group(1).strip(), match.group(2).strip()


def merge_stop_times(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    merged = copy.deepcopy(left)
    for key, value in right.items():
        if key == "sequence":
            continue
        if value and not merged.get(key):
            merged[key] = value
    return merged


def connected_at_same_station(left: dict[str, object], right: dict[str, object]) -> bool:
    left_stops = left.get("stop_times") or []
    right_stops = right.get("stop_times") or []
    if not left_stops or not right_stops:
        return False
    if left.get("display_name") != right.get("display_name"):
        return False
    return (
        left_stops[-1].get("station_name_raw")
        and left_stops[-1].get("station_name_raw") == right_stops[0].get("station_name_raw")
    )


def merge_connected_train_instances(trains: list[dict[str, object]]) -> list[dict[str, object]]:
    merged: list[dict[str, object]] = []
    for train in trains:
        if merged and connected_at_same_station(merged[-1], train):
            previous = merged[-1]
            previous_numbers = [
                value
                for value in (
                    str(previous.get("train_number") or ""),
                    str(train.get("train_number") or ""),
                )
                if value
            ]
            previous["train_number"] = "+".join(dict.fromkeys(previous_numbers))
            previous_stops = previous["stop_times"]
            current_stops = train["stop_times"]
            previous_stops[-1] = merge_stop_times(previous_stops[-1], current_stops[0])
            previous_stops.extend(copy.deepcopy(current_stops[1:]))
            for sequence, stop in enumerate(previous_stops, start=1):
                stop["sequence"] = sequence
            continue
        merged.append(copy.deepcopy(train))
    return merged


def parse_html(html: str, source_url: str | None, line_id: str = "JR_YAMANOTE") -> dict[str, object]:
    table_html = extract_table(html)
    train_numbers = extract_train_numbers(table_html)
    train_names = extract_train_names(table_html)
    train_types = extract_train_types(table_html)
    rows = extract_rows(table_html)

    trains = []
    for index, train_number in enumerate(train_numbers):
        raw_train_name = train_names[index] if index < len(train_names) else None
        service_name, service_number = split_service_name(raw_train_name or "")
        train_type = train_types[index] if index < len(train_types) else None
        train = {
            "train_number": train_number,
            "stop_times": [],
        }
        if train_type:
            train["train_type"] = train_type
        if raw_train_name:
            train["train_name_raw"] = raw_train_name
            train["display_name"] = raw_train_name
        if service_name:
            train["service_name"] = service_name
        if service_number:
            train["service_number"] = service_number
        trains.append(train)

    for sequence, row_html in enumerate(rows, start=1):
        station_name = extract_station_name(row_html)
        cells = extract_time_platform_cells(row_html)
        for index, (time_html, platform_html) in enumerate(cells):
            if index >= len(trains):
                continue
            time_info = parse_time_cell(time_html)
            platform = parse_platform_cell(platform_html)
            if not time_info:
                continue
            record = {
                "sequence": sequence,
                "station_name_raw": station_name,
                "line_id": line_id,
            }
            record.update(time_info)
            if platform is not None:
                record["platform"] = platform
            trains[index]["stop_times"].append(record)

    return {
        "source_url": source_url,
        "direction_label": parse_direction(html),
        "source_issue": parse_source_month(html),
        "train_instances": merge_connected_train_instances(trains),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse a JR East train-detail HTML page from stdin.")
    parser.add_argument("--source-url", help="Optional source URL to embed in the output.")
    args = parser.parse_args()

    html = sys.stdin.read()
    if not html.strip():
        print("No HTML received on stdin.", file=sys.stderr)
        return 1

    data = parse_html(html, args.source_url)
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
