#!/usr/bin/env python3

from __future__ import annotations

import argparse
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


def extract_train_numbers(table_html: str) -> list[str]:
    match = re.search(r"<th>Train number</th>(.*?)</tr>", table_html, re.DOTALL)
    if not match:
        raise ValueError("Could not find train number row.")
    cells = re.findall(r"<td[^>]*colspan=\"2\"[^>]*>(.*?)</td>", match.group(1), re.DOTALL)
    return [strip_tags(cell) for cell in cells]


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


def parse_html(html: str, source_url: str | None) -> dict[str, object]:
    table_html = extract_table(html)
    train_numbers = extract_train_numbers(table_html)
    rows = extract_rows(table_html)

    trains = [
        {
            "train_number": train_number,
            "stop_times": [],
        }
        for train_number in train_numbers
    ]

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
                "line_id": "JR_YAMANOTE",
            }
            record.update(time_info)
            if platform is not None:
                record["platform"] = platform
            trains[index]["stop_times"].append(record)

    return {
        "source_url": source_url,
        "direction_label": parse_direction(html),
        "source_issue": parse_source_month(html),
        "train_instances": trains,
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
