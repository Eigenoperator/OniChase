#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "docs" / "data" / "v4_fare_rules.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_fare_source_cache"

JR_FARE_SOURCES = [
    {
        "key": "jr_hokkaido",
        "operatorIds": ["jr_hokkaido"],
        "url": "https://jr-group.jp/hokkaido-fare/",
        "tables": [
            {"key": "main", "marker": "JR北海道幹線運賃表"},
            {"key": "local", "marker": "JR北海道地方交通線運賃表"},
        ],
    },
    {
        "key": "jr_east",
        "operatorIds": ["jr_east"],
        "url": "https://jr-group.jp/higashinihon-fare/",
        "tables": [
            {"key": "main", "marker": "JR東日本幹線運賃表"},
            {"key": "local", "marker": "JR東日本「地方交通線」運賃表"},
        ],
    },
    {
        "key": "jr_central_west",
        "operatorIds": ["jr_central", "jr_west"],
        "url": "https://jr-group.jp/tokai-fare/",
        "tables": [
            {"key": "main", "marker": "JR東海幹線運賃表"},
            {"key": "local", "marker": "JR東海・JR西日本エリア内の「地方交通線のみを利用する場合」の運賃表"},
        ],
    },
    {
        "key": "jr_shikoku",
        "operatorIds": ["jr_shikoku"],
        "url": "https://jr-group.jp/shikoku-fare/",
        "tables": [
            {"key": "main", "marker": "JR四国の普通運賃表"},
        ],
    },
    {
        "key": "jr_kyushu",
        "operatorIds": ["jr_kyushu"],
        "url": "https://jr-group.jp/kyushu-fare/",
        "tables": [
            {"key": "main", "marker": "JR九州の普通運賃表"},
        ],
    },
]

LIMITED_EXPRESS_SOURCE = {
    "key": "jr_conventional_limited_express",
    "url": "https://jr-group.jp/zairaisen-tokkyu-ryokin/",
    "tables": [
        {"key": "a", "marker": "A特急料金表"},
        {"key": "a_hokkaido", "marker": "JR北海道のA特急料金表"},
        {"key": "b_east_central", "marker": "B特急料金表（JR東日本、JR東海）"},
        {"key": "b_kyushu", "marker": "B特急料金表（JR九州）"},
    ],
}

OFFICIAL_REFERENCE_SOURCES = [
    {
        "key": "jreast_limited_express_ticket",
        "url": "https://www.jreast.co.jp/kippu/1203.html",
        "reason": "JR East official explanation: limited express requires an express ticket, conventional limited express charges are by riding distance.",
    },
]


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self.lines.append(text)


def fetch_text(url: str, cache_dir: Path) -> tuple[str, list[str]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / (re.sub(r"[^a-zA-Z0-9_.-]+", "_", url).strip("_") + ".html")
    response = requests.get(url, timeout=30, headers={"User-Agent": "OniChase fare rule collector/1.0"})
    response.raise_for_status()
    cache_path.write_text(response.text, encoding=response.encoding or "utf-8")
    parser = TextExtractor()
    parser.feed(response.text)
    return str(cache_path.relative_to(ROOT)), parser.lines


def try_fetch_text(url: str, cache_dir: Path) -> tuple[str | None, list[str], str | None]:
    try:
      cache_path, lines = fetch_text(url, cache_dir)
      return cache_path, lines, None
    except requests.RequestException as error:
      return None, [], str(error)


def parse_money(value: str) -> int:
    return int(re.sub(r"\D+", "", value))


def parse_km_range(value: str) -> tuple[int, int | None] | None:
    normalized = value.replace(",", "")
    match = re.search(r"(\d+)-(\d+)", normalized)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"(\d+)キロまで", normalized)
    if match:
        return 1, int(match.group(1))
    match = re.search(r"(\d+)キロ以上", normalized)
    if match:
        return int(match.group(1)), None
    return None


def marker_index(lines: list[str], marker: str) -> int:
    for index, line in enumerate(lines):
        if marker in line:
            return index
    return -1


def parse_adjacent_range_fare_rows(lines: list[str], marker: str, max_rows: int = 80) -> list[dict[str, Any]]:
    start = marker_index(lines, marker)
    if start < 0:
        return []
    rows: list[dict[str, Any]] = []
    index = start + 1
    while index < len(lines) - 1 and len(rows) < max_rows:
        km_range = parse_km_range(lines[index])
        if km_range and re.search(r"円$", lines[index + 1]):
            rows.append({"fromKm": km_range[0], "toKm": km_range[1], "yen": parse_money(lines[index + 1])})
            index += 2
            continue
        if rows and (lines[index].startswith("PR") or "運賃表" in lines[index] or "料金表" in lines[index]):
            break
        index += 1
    return rows


def parse_limited_express_rows(lines: list[str], marker: str, max_rows: int = 16) -> list[dict[str, Any]]:
    start = marker_index(lines, marker)
    if start < 0:
        return []
    rows: list[dict[str, Any]] = []
    index = start + 1
    while index < len(lines) - 2 and len(rows) < max_rows:
        km_range = parse_km_range(lines[index])
        if km_range and re.search(r"円$", lines[index + 1]) and re.search(r"円$", lines[index + 2]):
            rows.append({
                "fromKm": km_range[0],
                "toKm": km_range[1],
                "reservedYen": parse_money(lines[index + 1]),
                "unreservedYen": parse_money(lines[index + 2]),
            })
            index += 3
            continue
        if rows and (lines[index].startswith("PR") or "料金表" in lines[index]):
            break
        index += 1
    return rows


def build_rules(cache_dir: Path) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    ordinary_tables: dict[str, Any] = {}
    for source in JR_FARE_SOURCES:
        cache_path, lines = fetch_text(source["url"], cache_dir)
        source_record = {
            "key": source["key"],
            "url": source["url"],
            "cachePath": cache_path,
            "kind": "ordinary_fare_table",
            "operatorIds": source["operatorIds"],
        }
        sources.append(source_record)
        parsed_tables = {}
        for table in source["tables"]:
            rows = parse_adjacent_range_fare_rows(lines, table["marker"])
            if rows:
                parsed_tables[table["key"]] = {
                    "marker": table["marker"],
                    "rows": rows,
                }
        ordinary_tables[source["key"]] = {
            "operatorIds": source["operatorIds"],
            "sourceKey": source["key"],
            "tables": parsed_tables,
        }

    limited_cache_path, limited_lines = fetch_text(LIMITED_EXPRESS_SOURCE["url"], cache_dir)
    sources.append({
        "key": LIMITED_EXPRESS_SOURCE["key"],
        "url": LIMITED_EXPRESS_SOURCE["url"],
        "cachePath": limited_cache_path,
        "kind": "limited_express_surcharge_table",
    })
    limited_tables = {}
    for table in LIMITED_EXPRESS_SOURCE["tables"]:
        rows = parse_limited_express_rows(limited_lines, table["marker"])
        if rows:
            limited_tables[table["key"]] = {
                "marker": table["marker"],
                "rows": rows,
            }

    for reference in OFFICIAL_REFERENCE_SOURCES:
        cache_path, _lines, error = try_fetch_text(reference["url"], cache_dir)
        record = {
            **reference,
            "kind": "official_reference",
        }
        if cache_path:
            record["cachePath"] = cache_path
        if error:
            record["fetchError"] = error
        sources.append(record)

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "modelVersion": "v4_collected_fare_rules_2026_05",
        "currency": "JPY",
        "sources": sources,
        "ordinaryFareTables": ordinary_tables,
        "limitedExpressSurchargeTables": limited_tables,
        "coverageNotes": [
            "JR ordinary fare tables and conventional limited express surcharge tables are collected from published fare-rule pages.",
            "The game fare resolver uses these tables for JR distance-band legs and falls back to the existing distance estimate where no collected operator table exists.",
            "Limited express fare is represented as base fare plus surcharge; reserved ordinary-car normal-season surcharge is used as the default.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args()

    payload = build_rules(args.cache_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output.relative_to(ROOT)),
        "ordinaryTableCount": len(payload["ordinaryFareTables"]),
        "limitedExpressTableCount": len(payload["limitedExpressSurchargeTables"]),
        "sourceCount": len(payload["sources"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
