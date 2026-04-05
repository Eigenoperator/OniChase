#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from html import unescape
from typing import Any


TAG_RE = re.compile(r"<[^>]+>")
SERVICE_NAME_ALIASES = {
    "のぞみ": "Nozomi",
    "ひかり": "Hikari",
    "こだま": "Kodama",
    "みずほ": "Mizuho",
    "さくら": "Sakura",
    "つばめ": "Tsubame",
    "かもめ": "Kamome",
}


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(TAG_RE.sub(" ", value))).strip()


def extract_metadata_value(html: str, label: str) -> str | None:
    match = re.search(
        rf"<td[^>]*>\s*{re.escape(label)}\s*</td>\s*<td[^>]*colspan=\"2\"[^>]*>(.*?)</td>",
        html,
        re.DOTALL,
    )
    return strip_tags(match.group(1)) if match else None


def extract_metadata_columns(html: str) -> dict[str, list[str]]:
    rows = re.findall(r"<tr[^>]*>\s*<!--\s*(.*?)\s*-->(.*?)</tr>", html, re.DOTALL)
    metadata: dict[str, list[str]] = {}
    for raw_label, row_html in rows:
        label = strip_tags(raw_label)
        if not label:
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if not cells:
            continue
        values = [strip_tags(cell) for cell in cells[1:]]
        if values:
            metadata[label] = values
    return metadata


def split_service_name(raw_name: str | None) -> tuple[str | None, str | None]:
    if not raw_name:
        return None, None
    match = re.match(r"^(.*?)(\d+)号?$", raw_name.strip())
    if not match:
        raw_service = raw_name.strip()
        return SERVICE_NAME_ALIASES.get(raw_service, raw_service), None
    raw_service = match.group(1).strip()
    return SERVICE_NAME_ALIASES.get(raw_service, raw_service), match.group(2)


def choose_service_column(metadata: dict[str, list[str]], line_id: str) -> int:
    train_types = metadata.get("列車種", [])
    names = metadata.get("列車名", [])

    if line_id == "SHINKANSEN_NISHI_KYUSHU":
        for index, value in enumerate(train_types):
            if "新幹線" in value:
                return index
        for index, value in enumerate(names):
            if "かもめ" in value and "リレー" not in value:
                return index
    if line_id == "SHINKANSEN_KYUSHU":
        for index, value in enumerate(train_types):
            if "新幹線" in value:
                return index
    return 0


def metadata_value_for_column(metadata: dict[str, list[str]], label: str, column_index: int) -> str | None:
    values = metadata.get(label, [])
    if column_index < len(values):
        return values[column_index] or None
    return values[0] if values else None


def extract_stop_rows(html: str, column_index: int) -> list[tuple[str, str, str | None]]:
    rows = re.findall(r"<tr>\s*<!--\s*駅名\s*-->(.*?)</tr>", html, re.DOTALL)
    parsed: list[tuple[str, str, str | None]] = []
    for row_html in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if len(cells) < 3:
            continue
        station_name = strip_tags(cells[0])
        service_cells = cells[1:]
        groups: list[tuple[str, str | None]] = []
        for index in range(0, len(service_cells), 2):
            time_cell = service_cells[index] if index < len(service_cells) else ""
            platform_cell = service_cells[index + 1] if index + 1 < len(service_cells) else ""
            groups.append((strip_tags(time_cell), strip_tags(platform_cell) or None))
        if column_index >= len(groups):
            continue
        time_text, platform = groups[column_index]
        parsed.append((station_name, time_text, platform))
    return parsed


def parse_time_cell(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    if "レ" in text:
        return result
    entries = re.findall(r"(\d{2}:\d{2})\s*(着|発)", text)
    for hhmm, kind in entries:
        if kind == "着":
            result["arrival_hhmm"] = hhmm
        elif kind == "発":
            result["departure_hhmm"] = hhmm
    return result


def parse_html(html: str, source_url: str | None, line_id: str) -> dict[str, object]:
    metadata = extract_metadata_columns(html)
    column_index = choose_service_column(metadata, line_id)

    train_type = metadata_value_for_column(metadata, "列車種", column_index)
    raw_train_name = metadata_value_for_column(metadata, "列車名", column_index)
    train_number = metadata_value_for_column(metadata, "列車番号", column_index)
    operating_days = metadata_value_for_column(metadata, "運転日", column_index)

    if not train_type:
        train_type = extract_metadata_value(html, "列車種")
    if not raw_train_name:
        raw_train_name = extract_metadata_value(html, "列車名")
    if not train_number:
        train_number = extract_metadata_value(html, "列車番号")
    if not operating_days:
        operating_days = extract_metadata_value(html, "運転日")

    if not train_number:
        raise ValueError("Could not parse JR Kyushu train number.")

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
    if operating_days:
        train["operating_days"] = operating_days

    for sequence, (station_name, time_text, platform) in enumerate(extract_stop_rows(html, column_index), start=1):
        time_info = parse_time_cell(time_text)
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
    parser = argparse.ArgumentParser(description="Parse a JR Kyushu train timetable HTML page from stdin.")
    parser.add_argument("--source-url", help="Optional source URL to embed in output.")
    parser.add_argument("--line-id", default="SHINKANSEN_KYUSHU")
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
