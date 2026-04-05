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


def split_service_name(raw_name: str | None) -> tuple[str | None, str | None]:
    if not raw_name:
        return None, None
    match = re.match(r"^(.*?)(\d+)号?$", raw_name.strip())
    if not match:
        raw_service = raw_name.strip()
        return SERVICE_NAME_ALIASES.get(raw_service, raw_service), None
    raw_service = match.group(1).strip()
    return SERVICE_NAME_ALIASES.get(raw_service, raw_service), match.group(2)


def extract_stop_rows(html: str) -> list[tuple[str, str, str | None]]:
    rows = re.findall(r"<tr>\s*<!-- 駅名 -->(.*?)</tr>", html, re.DOTALL)
    parsed: list[tuple[str, str, str | None]] = []
    for row_html in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if len(cells) < 3:
            continue
        station_name = strip_tags(cells[0])
        time_cell = strip_tags(cells[1])
        platform = strip_tags(cells[2]) or None
        parsed.append((station_name, time_cell, platform))
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
    train_type = extract_metadata_value(html, "列車種")
    raw_train_name = extract_metadata_value(html, "列車名")
    train_number = extract_metadata_value(html, "列車番号")
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

    for sequence, (station_name, time_text, platform) in enumerate(extract_stop_rows(html), start=1):
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
