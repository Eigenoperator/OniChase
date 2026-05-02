#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from html import unescape


TAG_RE = re.compile(r"<[^>]+>")
SERVICE_NAME_ALIASES = {
    "のぞみ": "Nozomi",
    "ひかり": "Hikari",
    "こだま": "Kodama",
    "つるぎ": "Tsurugi",
    "みずほ": "Mizuho",
    "さくら": "Sakura",
    "つばめ": "Tsubame",
    "かもめ": "Kamome",
}


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(TAG_RE.sub(" ", value))).strip()


def extract_route_names(html: str) -> list[str]:
    match = re.search(r'<div class="route-name">(.*?)</div>', html, re.DOTALL)
    if not match:
        return []
    return [
        strip_tags(item)
        for item in re.findall(r"<p>(.*?)</p>", match.group(1), re.DOTALL)
        if strip_tags(item)
    ]


def clean_route_service_name(value: str) -> str:
    text = re.sub(r"^特急\s*", "", value.strip())
    text = re.sub(r"\s*（[^）]*）", "", text)
    text = re.sub(r"\s+[^ ]+行$", "", text)
    return text.strip()


def extract_route_name(html: str) -> str | None:
    route_names = [clean_route_service_name(name) for name in extract_route_names(html)]
    return "・".join(route_names) if route_names else None


def extract_metadata_value(html: str, label: str) -> str | None:
    match = re.search(
        rf"<th[^>]*>\s*{re.escape(label)}\s*</th>\s*<td[^>]*colspan=\"2\"[^>]*>(.*?)</td>",
        html,
        re.DOTALL,
    )
    return strip_tags(match.group(1)) if match else None


def extract_metadata_values(html: str, label: str) -> list[str]:
    match = re.search(
        rf"<th[^>]*>\s*{re.escape(label)}\s*</th>\s*(.*?)</tr>",
        html,
        re.DOTALL,
    )
    if not match:
        return []
    return [
        strip_tags(cell)
        for cell in re.findall(r"<td[^>]*colspan=\"2\"[^>]*>(.*?)</td>", match.group(1), re.DOTALL)
    ]


def extract_stop_rows(html: str) -> list[str]:
    match = re.search(r'<tbody class="time-details">(.*?)</tbody>', html, re.DOTALL)
    if not match:
        raise ValueError("Could not find JR West time-details tbody.")
    return re.findall(r"<tr>(.*?)</tr>", match.group(1), re.DOTALL)


def parse_time_cell(cell_html: str) -> dict[str, str]:
    result: dict[str, str] = {}
    if "レ" in cell_html:
        return result
    entries = re.findall(r"(\d{2}:\d{2})\s*(着|発)", strip_tags(cell_html))
    for hhmm, kind in entries:
        if kind == "着":
            result["arrival_hhmm"] = hhmm
        elif kind == "発":
            result["departure_hhmm"] = hhmm
    return result


def minutes_from_hhmm(value: object) -> int | None:
    text = str(value or "")
    if ":" not in text:
        return None
    hour, minute = text.split(":", 1)
    try:
        return int(hour) * 60 + int(minute)
    except ValueError:
        return None


def stop_minute(stop: dict[str, object]) -> int | None:
    return minutes_from_hhmm(stop.get("departure_hhmm") or stop.get("arrival_hhmm"))


def stops_are_close(left: dict[str, object], right: dict[str, object], max_gap_minutes: int = 20) -> bool:
    left_minute = stop_minute(left)
    right_minute = stop_minute(right)
    if left_minute is None or right_minute is None:
        return True
    return abs(left_minute - right_minute) <= max_gap_minutes


def resequence_stops(train: dict[str, object]) -> None:
    for sequence, stop in enumerate(train.get("stop_times") or [], start=1):
        stop["sequence"] = sequence


def merged_split_stop(shared_stop: dict[str, object], branch_stop: dict[str, object]) -> dict[str, object]:
    merged = dict(shared_stop)
    if branch_stop.get("arrival_hhmm"):
        merged["arrival_hhmm"] = branch_stop["arrival_hhmm"]
    if branch_stop.get("departure_hhmm"):
        merged["departure_hhmm"] = branch_stop["departure_hhmm"]
    if branch_stop.get("platform"):
        merged["platform"] = branch_stop["platform"]
    return merged


def is_named_coupled_portion(train: dict[str, object], route_names: list[str]) -> bool:
    route_name = str(train.get("route_name") or "")
    train_type = str(train.get("train_type") or "")
    return any(name and (name == route_name or name == train_type) for name in route_names)


def inherit_shared_coupled_segments(trains: list[dict[str, object]], route_names: list[str]) -> None:
    """Fill blank coupled columns with the shared segment from their partner column."""

    if len(trains) < 2:
        return
    for train in trains:
        if not is_named_coupled_portion(train, route_names):
            continue
        stops = train.get("stop_times") or []
        if len(stops) < 2:
            continue
        first_stop = stops[0]
        if first_stop.get("departure_hhmm"):
            best_prefix: tuple[int, dict[str, object], int] | None = None
            for donor in trains:
                if donor is train:
                    continue
                donor_stops = donor.get("stop_times") or []
                for donor_index, donor_stop in enumerate(donor_stops):
                    if donor_index == 0:
                        continue
                    if donor_stop.get("station_name_raw") != first_stop.get("station_name_raw"):
                        continue
                    if not stops_are_close(donor_stop, first_stop):
                        continue
                    score = donor_index
                    if best_prefix is None or score > best_prefix[0]:
                        best_prefix = (score, donor, donor_index)
            if best_prefix:
                _, donor, donor_index = best_prefix
                donor_stops = donor.get("stop_times") or []
                train["stop_times"] = [
                    dict(stop) for stop in donor_stops[:donor_index]
                ] + [
                    merged_split_stop(donor_stops[donor_index], first_stop),
                    *[dict(stop) for stop in stops[1:]],
                ]
                resequence_stops(train)

        stops = train.get("stop_times") or []
        last_stop = stops[-1] if stops else None
        if not last_stop or not last_stop.get("arrival_hhmm"):
            continue
        best_suffix: tuple[int, dict[str, object], int] | None = None
        for donor in trains:
            if donor is train:
                continue
            donor_stops = donor.get("stop_times") or []
            for donor_index, donor_stop in enumerate(donor_stops):
                if donor_index >= len(donor_stops) - 1:
                    continue
                if donor_stop.get("station_name_raw") != last_stop.get("station_name_raw"):
                    continue
                if not stops_are_close(donor_stop, last_stop):
                    continue
                score = len(donor_stops) - donor_index - 1
                if best_suffix is None or score > best_suffix[0]:
                    best_suffix = (score, donor, donor_index)
        if best_suffix:
            _, donor, donor_index = best_suffix
            donor_stops = donor.get("stop_times") or []
            train["stop_times"] = [
                *[dict(stop) for stop in stops[:-1]],
                merged_split_stop(last_stop, donor_stops[donor_index]),
                *[dict(stop) for stop in donor_stops[donor_index + 1:]],
            ]
            resequence_stops(train)


def split_service_name(raw_name: str | None) -> tuple[str | None, str | None]:
    if not raw_name:
        return None, None
    match = re.match(r"^(.*?)(\d+)号?$", raw_name.strip())
    if not match:
        raw_service = raw_name.strip()
        return SERVICE_NAME_ALIASES.get(raw_service, raw_service), None
    raw_service = match.group(1).strip()
    return SERVICE_NAME_ALIASES.get(raw_service, raw_service), match.group(2)


def pick_column_value(values: list[str], index: int) -> str | None:
    if not values:
        return None
    if index < len(values):
        return values[index] or None
    return values[0] or None


def route_name_for_column(route_names: list[str], column_index: int, column_count: int) -> str | None:
    if not route_names:
        return None
    if len(route_names) == column_count and column_index < len(route_names):
        return route_names[column_index]
    if len(route_names) == column_count - 1 and column_index > 0:
        return route_names[column_index - 1]
    if len(route_names) == column_count - 1 and column_index == 0:
        return None
    if len(route_names) == 1:
        return route_names[0]
    return "・".join(route_names)


def infer_column_count(html: str, metadata_values: list[list[str]]) -> int:
    counts = [len(values) for values in metadata_values if values]
    for row_html in extract_stop_rows(html):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if len(cells) >= 3:
            counts.append((len(cells) - 1) // 2)
            break
    return max(counts) if counts else 1


def parse_html(html: str, source_url: str | None, line_id: str) -> dict[str, object]:
    train_types = extract_metadata_values(html, "列車種別") or extract_metadata_values(html, "列車種")
    raw_train_names = extract_metadata_values(html, "列車名")
    train_numbers = extract_metadata_values(html, "列車番号")
    operating_days_values = extract_metadata_values(html, "運転日")
    route_names = [clean_route_service_name(name) for name in extract_route_names(html)]

    column_count = infer_column_count(html, [train_types, raw_train_names, train_numbers, operating_days_values])
    if not train_numbers:
        raise ValueError("Could not parse JR West train number.")

    trains: list[dict[str, object]] = []
    for column_index in range(column_count):
        train_number = pick_column_value(train_numbers, column_index)
        if not train_number:
            continue
        train_type = pick_column_value(train_types, column_index)
        raw_train_name = pick_column_value(raw_train_names, column_index)
        operating_days = pick_column_value(operating_days_values, column_index)
        route_name = route_name_for_column(route_names, column_index, column_count)
        service_name, service_number = split_service_name(raw_train_name)

        train: dict[str, object] = {
            "train_number": train_number,
            "source_column_index": column_index,
            "source_column_count": column_count,
            "stop_times": [],
        }
        if source_url:
            train["source_url"] = source_url
        if train_type:
            train["train_type"] = train_type
        if raw_train_name:
            train["train_name_raw"] = raw_train_name
            train["display_name"] = raw_train_name
        if service_name:
            train["service_name"] = service_name
        if service_number:
            train["service_number"] = service_number
        if route_name:
            train["route_name"] = route_name
        if len(route_names) > 1:
            train["coupled_route_names"] = route_names
        if operating_days:
            train["operating_days"] = operating_days
        trains.append(train)

    for sequence, row_html in enumerate(extract_stop_rows(html), start=1):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if len(cells) < 3:
            continue
        station_name = strip_tags(cells[0])
        if not station_name:
            continue
        for column_index, train in enumerate(trains):
            time_cell_index = 1 + (column_index * 2)
            platform_cell_index = time_cell_index + 1
            if platform_cell_index >= len(cells):
                continue
            time_info = parse_time_cell(cells[time_cell_index])
            platform = strip_tags(cells[platform_cell_index]) or None
            if not time_info:
                continue
            record = {
                "sequence": len(train["stop_times"]) + 1,
                "source_row_sequence": sequence,
                "station_name_raw": station_name,
                "line_id": line_id,
            }
            record.update(time_info)
            if platform is not None:
                record["platform"] = platform
            train["stop_times"].append(record)

    if len(route_names) > 1:
        inherit_shared_coupled_segments(trains, route_names)

    return {
        "source_url": source_url,
        "train_instances": trains,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse a JR West train timetable HTML page from stdin.")
    parser.add_argument("--source-url", help="Optional source URL to embed in output.")
    parser.add_argument("--line-id", default="SHINKANSEN_TOKAIDO_SANYO")
    args = parser.parse_args()

    html = sys.stdin.read()
    if not html.strip():
        print("No HTML received on stdin.", file=sys.stderr)
        return 1

    data = parse_html(html, args.source_url, args.line_id)
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
