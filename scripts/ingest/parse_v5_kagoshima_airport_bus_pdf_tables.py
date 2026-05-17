#!/usr/bin/env python3
"""Parse reliable Kagoshima Airport bus PDF timetable tables into source JSON.

This parser is intentionally conservative.  It only emits trips from table
blocks where the number of stop names matches the number of HH:MM cells.  Large
multi-page or visually wrapped tables remain in the PDF source audit until they
can be handled without inventing stops or times.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PDF_SOURCE = ROOT / "data" / "v5_kagoshima_airport_official_bus_pdfs.json"
DEFAULT_OUTPUT = ROOT / "data" / "v5_kagoshima_airport_official_bus_tables.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_kagoshima_airport_official_bus_tables.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_kagoshima_airport_official_bus_tables_audit.json"

TIME_RE = re.compile(r"[△※○＊*（(]*\d{1,2}:\d{2}[）)]?")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pdf_text(path: Path) -> str:
    result = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=False, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return ""
    return result.stdout


def time_cell(value: str) -> dict[str, Any]:
    raw = value.strip()
    time = re.search(r"\d{1,2}:\d{2}", raw)
    marks = [char for char in raw if char not in "0123456789:()（） "]
    return {"time": time.group(0) if time else None, "raw": raw, "marks": marks}


def parse_time_line(line: str) -> list[dict[str, Any]]:
    return [time_cell(match.group(0)) for match in TIME_RE.finditer(line)]


def split_stops(line: str) -> list[str]:
    text = re.sub(r"¥[\d,]+|－|-", " ", line)
    return [part.strip() for part in re.split(r"\s{2,}", text.strip()) if part.strip()]


def rows_by_index(lines: list[str], indexes: list[int]) -> list[str]:
    return [lines[index] for index in indexes if 0 <= index < len(lines)]


def make_trips(route_code: str, direction: str, stops: list[str], rows: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trips = []
    skipped = []
    for row_number, line in enumerate(rows, start=1):
        times = parse_time_line(line)
        if len(times) != len(stops):
            skipped.append({"row": line.strip(), "timeCount": len(times), "stopCount": len(stops), "reason": "time_count_stop_count_mismatch"})
            continue
        stop_times = []
        for stop, cell in zip(stops, times):
            if not cell["time"]:
                continue
            stop_times.append({"stopName": stop, **cell})
        if len(stop_times) >= 2:
            trips.append(
                {
                    "tripId": f"kagoshima_airport:{route_code}:{direction}:{row_number:03d}",
                    "direction": direction,
                    "stopTimes": stop_times,
                }
            )
    return trips, skipped


def parse_two_side_stop_rows(route_code: str, text: str, line_indexes: list[int], left_stops: list[str], right_stops: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lines = text.splitlines()
    left_columns: list[list[dict[str, Any]]] | None = None
    right_columns: list[list[dict[str, Any]]] | None = None
    skipped = []
    left_trip_count: int | None = None
    right_trip_count: int | None = None
    stop_rows = []
    for index in line_indexes:
        line = lines[index]
        cells = parse_time_line(line)
        if not cells:
            continue
        if left_trip_count is None:
            midpoint = max(1, len(cells) // 2)
            left_trip_count = midpoint
            right_trip_count = len(cells) - midpoint
            left_columns = [[] for _ in range(left_trip_count)]
            right_columns = [[] for _ in range(right_trip_count)]
        if len(cells) != left_trip_count + (right_trip_count or 0):
            skipped.append({"lineIndex": index, "row": line.strip(), "reason": "not_enough_time_cells"})
            continue
        stop_rows.append(cells)
    if left_columns is None or right_columns is None or left_trip_count is None or right_trip_count is None:
        return [], skipped
    if len(stop_rows) != len(left_stops) or len(stop_rows) != len(right_stops):
        skipped.append({"reason": "stop_row_count_mismatch", "stopRowCount": len(stop_rows), "leftStopCount": len(left_stops), "rightStopCount": len(right_stops)})
    usable_count = min(len(stop_rows), len(left_stops), len(right_stops))
    for stop_index in range(usable_count):
        cells = stop_rows[stop_index]
        for trip_index in range(left_trip_count):
            left_columns[trip_index].append({"stopName": left_stops[stop_index], **cells[trip_index]})
        for trip_index in range(right_trip_count):
            right_columns[trip_index].append({"stopName": right_stops[stop_index], **cells[left_trip_count + trip_index]})
    trips = []
    for trip_index, stop_times in enumerate(left_columns, start=1):
        if len(stop_times) >= 2:
            trips.append({"tripId": f"kagoshima_airport:{route_code}:to_airport:{trip_index:03d}", "direction": "to_airport", "stopTimes": stop_times})
    for trip_index, stop_times in enumerate(right_columns, start=1):
        if len(stop_times) >= 2:
            trips.append({"tripId": f"kagoshima_airport:{route_code}:from_airport:{trip_index:03d}", "direction": "from_airport", "stopTimes": stop_times})
    return trips, skipped


def parse_horizontal_table(route_code: str, direction: str, text: str, header_index: int, row_indexes: list[int], *, header_override: list[str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    lines = text.splitlines()
    stops = header_override or split_stops(lines[header_index])
    trips, skipped = make_trips(route_code, direction, stops, rows_by_index(lines, row_indexes))
    return trips, skipped, stops


def parse_pdf(label: str, path: Path) -> dict[str, Any]:
    text = pdf_text(path)
    routes: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    if "垂水・国分" in label:
        trips1, bad1, stops1 = parse_horizontal_table("tarumizu_airport", "to_airport", text, 2, [6, 7, 9, 10])
        trips2, bad2, stops2 = parse_horizontal_table("tarumizu_airport", "from_airport", text, 15, [19, 22, 23])
        routes.append({"routeCode": "tarumizu_airport", "routeName": "垂水港 ⇔ 鹿児島空港", "directions": [{"direction": "to_airport", "stops": stops1}, {"direction": "from_airport", "stops": stops2}], "trips": trips1 + trips2})
        skipped.extend(bad1 + bad2)

    elif "国分～空港線" in label:
        left_stops = [
            "京セラ国分", "迫田", "国分Ａコープ前", "唐仁町", "中馬場", "福島団地入口", "国分山形屋前", "国分駅②",
            "国分中央高校前", "向花公会堂前", "新町", "阿多石", "中ノ城", "姫城温泉", "隼人温泉病院前", "姫城Ａコープ前",
            "日当山小前", "日当山小北", "西光寺③", "鉄橋下", "中西光寺", "糸走", "空港ホテル前", "鹿児島空港",
        ]
        right_stops = [
            "鹿児島空港⑩", "空港ホテル前", "糸走", "中西光寺", "鉄橋下", "西光寺④", "日当山小北", "日当山小前",
            "姫城Ａコープ前", "隼人温泉病院前", "姫城温泉", "中ノ城", "阿多石", "新町", "向花公会堂前",
            "国分中央高校前", "国分駅③", "国分山形屋前", "福島団地入口", "中馬場", "唐仁町", "国分Ａコープ前", "迫田", "京セラ国分",
        ]
        trips, bad = parse_two_side_stop_rows("kokubu_airport", text, list(range(4, 28)), left_stops, right_stops)
        routes.append({"routeCode": "kokubu_airport", "routeName": "京セラ国分・国分駅 ⇔ 鹿児島空港", "trips": trips})
        skipped.extend(bad)

    elif "志布志" in label:
        to_stops = ["志布志駅", "農協前", "山之口", "字尾", "八合原", "県改良研究所", "岩川", "高校前河原", "笠木小前", "飛佐入口", "二重堀", "福山高校前", "牧之原十文字", "牧之原", "検校橋", "霧島市役所", "鹿児島空港"]
        from_stops = ["鹿児島空港⑩", "霧島市役所", "検校橋", "牧之原", "福山高校前", "二重堀", "飛佐入口", "笠木小前", "高校前河原", "岩川", "県改良研究所", "八合原", "字尾", "山之口", "農協前", "志布志駅"]
        trips1, bad1, _ = parse_horizontal_table("shibushi_airport", "to_airport", text, 2, [5, 6, 8, 9, 11], header_override=to_stops)
        trips2, bad2, _ = parse_horizontal_table("shibushi_airport", "from_airport", text, 15, [18, 19, 20, 23, 24], header_override=from_stops)
        routes.append({"routeCode": "shibushi_airport", "routeName": "志布志・岩川 ⇔ 鹿児島空港", "trips": trips1 + trips2})
        skipped.extend(bad1 + bad2)

    elif "鹿屋" in label:
        to_fast = ["東笠之原", "東団地前", "寿中央", "鹿屋市役所前", "鹿屋着", "鹿屋発", "旭原", "道の駅あらさの", "鹿児島空港"]
        from_fast = ["鹿児島空港", "道の駅あらさの", "旭原", "鹿屋着", "鹿屋発", "鹿屋市役所前", "寿中央", "東団地前", "東笠之原"]
        trips1, bad1, _ = parse_horizontal_table("kanoya_airport", "to_airport_fast", text, 6, [8, 9, 10, 11, 12], header_override=to_fast)
        trips2, bad2, _ = parse_horizontal_table("kanoya_airport", "from_airport_fast", text, 29, [31, 32, 33, 34, 35], header_override=from_fast)
        routes.append({"routeCode": "kanoya_airport", "routeName": "鹿屋 ⇔ 鹿児島空港", "trips": trips1 + trips2})
        skipped.extend(bad1 + bad2)

    return {"routes": routes, "skippedRows": skipped}


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    pdf_source = json.loads(args.pdf_source.read_text(encoding="utf-8"))
    parsed_pdfs = []
    route_payloads = []
    for pdf in pdf_source.get("pdfs") or []:
        label = pdf.get("label") or ""
        parsed = parse_pdf(label, ROOT / pdf["cachePath"])
        trip_count = sum(len(route.get("trips") or []) for route in parsed["routes"])
        parsed_pdfs.append(
            {
                "label": label,
                "url": pdf.get("url"),
                "cachePath": pdf.get("cachePath"),
                "status": "parsed_reliable_tables" if trip_count else "kept_as_pdf_source_only",
                "routeCount": len(parsed["routes"]),
                "tripCount": trip_count,
                "skippedRowCount": len(parsed["skippedRows"]),
                "skippedRows": parsed["skippedRows"][:20],
            }
        )
        for route in parsed["routes"]:
            route_payloads.append(
                {
                    "sourceKind": "official_kagoshima_airport_pdf_table",
                    "operatorName": "Kagoshima Kotsu",
                    "airportIata": "KOJ",
                    "sourcePdfLabel": label,
                    "sourceUrl": pdf.get("url"),
                    **route,
                }
            )
    source = {
        "schemaVersion": "v5_official_bus_source.kagoshima_airport_pdf_tables.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Conservative parsed subset of official Kagoshima Airport bus PDFs. Only rows with matching stop/time counts are emitted; skipped rows remain auditable.",
        "routes": route_payloads,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.kagoshima_airport_pdf_tables.v1",
        "generatedAt": generated_at,
        "pdfCount": len(parsed_pdfs),
        "parsedPdfCount": sum(1 for item in parsed_pdfs if item["tripCount"]),
        "routeCount": len(route_payloads),
        "tripCount": sum(len(route.get("trips") or []) for route in route_payloads),
        "parsedPdfs": parsed_pdfs,
    }
    return source, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-source", type=Path, default=DEFAULT_PDF_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    args = parser.parse_args()
    source, audit = collect(args)
    write_json(args.output, source)
    write_json(args.docs_output, source)
    write_json(args.audit_output, audit)
    print(json.dumps({"parsedPdfCount": audit["parsedPdfCount"], "routeCount": audit["routeCount"], "tripCount": audit["tripCount"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
