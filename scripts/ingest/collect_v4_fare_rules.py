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

# Real adult ordinary fare tables from official operator fare pages/PDFs.
# Values use the ticket / 10-yen unit fare where operators publish both IC and ticket fares,
# because gameplay fares are displayed as a simple yen total and should avoid 1-yen IC rounding details.
MANUAL_OPERATOR_FARE_TABLES = [
    {
        "key": "kintetsu",
        "operatorIds": ["近畿日本鉄道"],
        "operatorName": "近畿日本鉄道",
        "url": "https://www.kintetsu.co.jp/gyoumu/kippu/pdf/kirotei_20260314.pdf",
        "notes": [
            "普通旅客運賃・鉄軌道線の大人普通運賃。吉野線/湯の山線/志摩線、鳥羽線、けいはんな線などの加算運賃は未適用。",
        ],
        "rows": [
            (1, 3, 180), (4, 6, 240), (7, 10, 300), (11, 14, 360), (15, 18, 430),
            (19, 22, 490), (23, 26, 530), (27, 30, 590), (31, 35, 680), (36, 40, 760),
            (41, 45, 830), (46, 50, 910), (51, 55, 1000), (56, 60, 1070), (61, 65, 1140),
            (66, 70, 1210), (71, 75, 1290), (76, 80, 1370), (81, 85, 1450), (86, 90, 1530),
            (91, 95, 1600), (96, 100, 1670), (101, 110, 1740), (111, 120, 1880), (121, 130, 2040),
            (131, 140, 2170), (141, 150, 2310), (151, 160, 2430), (161, 170, 2560),
            (171, 180, 2710), (181, 190, 2860), (191, 200, 3000), (201, 210, 3130),
            (211, 220, 3280), (221, 230, 3410), (231, 240, 3560), (241, 250, 3690),
        ],
    },
    {
        "key": "tobu",
        "operatorIds": ["tobu"],
        "operatorName": "東武鉄道",
        "url": "https://www.tobu.co.jp/pdf/ticket/unchinTable.pdf?2023=",
        "notes": ["大人普通運賃。運賃計算キロによる距離分段。"],
        "rows": [
            (1, 4, 160), (5, 7, 180), (8, 10, 210), (11, 15, 270), (16, 20, 330),
            (21, 25, 380), (26, 30, 430), (31, 35, 490), (36, 40, 540), (41, 45, 610),
            (46, 50, 670), (51, 60, 750), (61, 70, 830), (71, 80, 920), (81, 90, 1000),
            (91, 100, 1090), (101, 120, 1230), (121, 140, 1400), (141, 178, 1590),
        ],
    },
    {
        "key": "seibu",
        "operatorIds": ["seibu"],
        "operatorName": "西武鉄道",
        "url": "https://www.seiburailway.jp/file.jsp?file%2F202603_fare_bykm.pdf=",
        "notes": ["2025年7月改定後の大人普通旅客運賃・きっぷ10円単位。"],
        "rows": [
            (1, 4, 170), (5, 8, 210), (9, 12, 250), (13, 16, 290), (17, 20, 330),
            (21, 24, 370), (25, 28, 410), (29, 32, 450), (33, 36, 490), (37, 40, 530),
            (41, 44, 560), (45, 48, 600), (49, 52, 630), (53, 56, 660), (57, 60, 690),
            (61, 64, 710), (65, 68, 740), (69, 72, 760), (73, 76, 790), (77, 81, 800),
        ],
    },
    {
        "key": "tokyu",
        "operatorIds": ["tokyu"],
        "operatorName": "東急電鉄",
        "url": "https://www.tokyu.co.jp/railway/ticket/fares/?vm=r",
        "notes": [
            "片道普通旅客運賃表の大人きっぷ10円単位。世田谷線/こどもの国線は均一運賃だが、この距離表とは別体系。",
            "東急新横浜線の加算運賃は未適用。",
        ],
        "rows": [
            (1, 3, 140), (4, 7, 180), (8, 11, 230), (12, 15, 250), (16, 20, 290),
            (21, 25, 310), (26, 30, 350), (31, 35, 390), (36, 40, 430),
        ],
    },
    {
        "key": "tokyo_metro",
        "operatorIds": ["tokyo_metro"],
        "operatorName": "東京地下鉄",
        "url": "https://www.tokyometro.jp/ticket/types/regular/index.html",
        "notes": ["東京メトロ普通旅客運賃・きっぷ10円単位。"],
        "rows": [(1, 6, 180), (7, 11, 210), (12, 19, 260), (20, 27, 300), (28, 40, 330)],
    },
    {
        "key": "toei_subway",
        "operatorIds": ["toei"],
        "operatorName": "東京都交通局",
        "url": "https://www.kotsu.metro.tokyo.jp/subway/fare/regular.html",
        "notes": ["都営地下鉄普通旅客運賃・きっぷ10円単位。都電荒川線と日暮里・舎人ライナーは別体系のため未適用リスクあり。"],
        "rows": [(1, 4, 180), (5, 9, 220), (10, 15, 280), (16, 21, 330), (22, 27, 380), (28, 46, 430)],
    },
    {
        "key": "osaka_metro",
        "operatorIds": ["大阪市高速電気軌道"],
        "operatorName": "Osaka Metro",
        "url": "https://subway.osakametro.co.jp/guide/fare/fare/price.php",
        "notes": ["Osaka Metro普通運賃の区数制。距離上限で近似せず、公式区数の距離境界を使用。"],
        "rows": [(1, 3, 190), (4, 7, 240), (8, 13, 290), (14, 19, 340), (20, 100, 390)],
    },
    {
        "key": "keio",
        "operatorIds": ["keio"],
        "operatorName": "京王電鉄",
        "url": "https://www.keio.co.jp/train/ticket/fare_chart/fare_chart_km.html",
        "notes": ["2023年10月1日改定のキロ別旅客運賃表・大人普通運賃・きっぷ10円単位。"],
        "rows": [(1, 4, 140), (5, 6, 160), (7, 9, 190), (10, 12, 210), (13, 15, 230),
                 (16, 19, 280), (20, 24, 320), (25, 30, 360), (31, 37, 390),
                 (38, 44, 410), (45, 52, 430)],
    },
    {
        "key": "sotetsu",
        "operatorIds": ["sotetsu"],
        "operatorName": "相模鉄道",
        "url": "https://www.sotetsu.co.jp/media/2019/trans/train/search/pdf/kiro_fares.pdf",
        "notes": ["キロ別旅客運賃表・大人普通運賃・きっぷ10円単位。いずみ野線加算運賃は未適用。"],
        "rows": [(1, 3, 150), (4, 7, 180), (8, 11, 200), (12, 15, 230),
                 (16, 19, 260), (20, 23, 280), (24, 26, 310)],
    },
    {
        "key": "nagoya_subway",
        "operatorIds": ["名古屋市"],
        "operatorName": "名古屋市交通局",
        "url": "https://www.kotsu.city.nagoya.jp/rp/subway/trp0000172.htm",
        "notes": ["地下鉄普通料金・対キロ区間制。大人普通料金。"],
        "rows": [(1, 3, 210), (4, 7, 240), (8, 11, 270), (12, 15, 310), (16, 100, 340)],
    },
]


def manual_rows(rows: list[tuple[int, int | None, int]]) -> list[dict[str, Any]]:
    return [{"fromKm": start, "toKm": end, "yen": yen} for start, end, yen in rows]


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

    for table in MANUAL_OPERATOR_FARE_TABLES:
        cache_path, _lines, error = try_fetch_text(table["url"], cache_dir)
        source_record = {
            "key": table["key"],
            "url": table["url"],
            "kind": "ordinary_fare_table",
            "operatorIds": table["operatorIds"],
            "operatorName": table["operatorName"],
            "extraction": "manual_from_official_source",
        }
        if cache_path:
            source_record["cachePath"] = cache_path
        if error:
            source_record["fetchError"] = error
        sources.append(source_record)
        ordinary_tables[table["key"]] = {
            "operatorIds": table["operatorIds"],
            "sourceKey": table["key"],
            "operatorName": table["operatorName"],
            "notes": table.get("notes") or [],
            "tables": {
                "main": {
                    "marker": "adult ordinary fare table",
                    "rows": manual_rows(table["rows"]),
                },
            },
        }

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
            "The game fare resolver uses these tables for JR distance-band legs and marks fare as unknown where no collected operator table exists.",
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
