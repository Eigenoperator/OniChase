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


def extract_route_name(html: str) -> str | None:
    match = re.search(r'<div class="route-name"><p>(.*?)</p>', html, re.DOTALL)
    return strip_tags(match.group(1)) if match else None


def extract_metadata_value(html: str, label: str) -> str | None:
    match = re.search(
        rf"<th[^>]*>\s*{re.escape(label)}\s*</th>\s*<td[^>]*colspan=\"2\"[^>]*>(.*?)</td>",
        html,
        re.DOTALL,
    )
    return strip_tags(match.group(1)) if match else None


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


def split_service_name(raw_name: str | None) -> tuple[str | None, str | None]:
    if not raw_name:
        return None, None
    match = re.match(r"^(.*?)(\d+)号?$", raw_name.strip())
    if not match:
        raw_service = raw_name.strip()
        return SERVICE_NAME_ALIASES.get(raw_service, raw_service), None
    raw_service = match.group(1).strip()
    return SERVICE_NAME_ALIASES.get(raw_service, raw_service), match.group(2)


def parse_html(html: str, source_url: str | None, line_id: str) -> dict[str, object]:
    train_type = extract_metadata_value(html, "列車種別") or extract_metadata_value(html, "列車種")
    raw_train_name = extract_metadata_value(html, "列車名")
    train_number = extract_metadata_value(html, "列車番号")
    operating_days = extract_metadata_value(html, "運転日")
    route_name = extract_route_name(html)

    if not train_number:
        raise ValueError("Could not parse JR West train number.")

    service_name, service_number = split_service_name(raw_train_name)

    train: dict[str, object] = {
        "train_number": train_number,
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
    if operating_days:
        train["operating_days"] = operating_days

    for sequence, row_html in enumerate(extract_stop_rows(html), start=1):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if len(cells) < 3:
            continue
        station_name = strip_tags(cells[0])
        time_info = parse_time_cell(cells[1])
        platform = strip_tags(cells[2]) or None
        if not station_name or not time_info:
            continue
        record = {
            "sequence": sequence,
            "station_name_raw": station_name,
            "line_id": line_id,
        }
        record.update(time_info)
        if platform is not None:
            record["platform"] = platform
        train["stop_times"].append(record)

    return {
        "source_url": source_url,
        "train_instances": [train],
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
