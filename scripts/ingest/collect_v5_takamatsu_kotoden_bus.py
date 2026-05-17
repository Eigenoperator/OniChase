#!/usr/bin/env python3
"""Collect Kotoden official Takamatsu Airport limousine PDF timetables."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASE = "https://www.kotoden.co.jp/publichtm/bus/limousine/"
PDF_SOURCES = [
    {"serviceStart": "2026-03-29", "serviceEnd": "2026-05-31", "direction": "to_airport", "url": urllib.parse.urljoin(BASE, "2012/pdf/20260329kudari.pdf")},
    {"serviceStart": "2026-03-29", "serviceEnd": "2026-05-31", "direction": "from_airport", "url": urllib.parse.urljoin(BASE, "2012/pdf/20260329nobori.pdf")},
    {"serviceStart": "2026-06-01", "serviceEnd": "2026-06-30", "direction": "to_airport", "url": urllib.parse.urljoin(BASE, "2012/pdf/20260601kudari.pdf")},
    {"serviceStart": "2026-06-01", "serviceEnd": "2026-06-30", "direction": "from_airport", "url": urllib.parse.urljoin(BASE, "2012/pdf/20260601nobori.pdf")},
]
TO_AIRPORT_STOPS = [
    "JRホテルクレメント高松",
    "高松駅",
    "フェリー乗り場",
    "県民ホール・県立ミュージアム",
    "高松築港",
    "兵庫町",
    "県庁通り中央公園前",
    "瓦町",
    "中新町",
    "栗林公園前",
    "ゆめタウン高松前",
    "香川大学附属中学校前",
    "空港通り一宮",
    "高松空港",
]
FROM_AIRPORT_STOPS = [
    "高松空港",
    "空港通り一宮",
    "香川大学附属中学校前",
    "ゆめタウン高松前",
    "栗林公園前",
    "中新町",
    "瓦町",
    "県庁通り中央公園前",
    "兵庫町",
    "高松築港",
    "JRホテルクレメント高松",
    "高松駅",
    "フェリー乗り場",
    "県民ホール・県立ミュージアム",
]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "takamatsu_kotoden"
DEFAULT_OUTPUT = ROOT / "data" / "v5_takamatsu_kotoden_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_takamatsu_kotoden_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_takamatsu_kotoden_official_bus_audit.json"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.pdf"


def fetch_pdf(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> Path:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def pdf_layout_text(path: Path) -> str:
    completed = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=False, capture_output=True, text=True, timeout=30)
    return completed.stdout if completed.returncode == 0 else ""


def marks_from(value: str) -> list[str]:
    return [mark for mark in ["▲", "☆", "■", "●", "〇", "◆", "□"] if mark in value]


def parse_pdf(source: dict[str, str], path: Path) -> dict[str, Any]:
    text = pdf_layout_text(path)
    direction = source["direction"]
    stops = TO_AIRPORT_STOPS if direction == "to_airport" else FROM_AIRPORT_STOPS
    trips = []
    for line_index, line in enumerate(text.splitlines(), start=1):
        times = re.findall(r"[▲☆■●〇◆□]?\d{1,2}:\d{2}", line)
        if direction == "to_airport":
            if len(times) < len(stops):
                continue
            bus_times = times[: len(stops)]
        else:
            if len(times) < len(stops) + 1:
                continue
            bus_times = times[1 : len(stops) + 1]
        stop_times = []
        limited_marks = []
        for stop, raw_time in zip(stops, bus_times):
            marks = marks_from(raw_time)
            limited_marks.extend(mark for mark in marks if mark not in limited_marks)
            stop_times.append({"stopName": stop, "time": re.search(r"\d{1,2}:\d{2}", raw_time).group(0), "raw": raw_time, "marks": marks})
        if len(stop_times) == len(stops):
            trips.append(
                {
                    "tripId": f"tak_kotoden:{source['serviceStart']}:{direction}:{len(trips) + 1:03d}",
                    "direction": direction,
                    "serviceStart": source["serviceStart"],
                    "serviceEnd": source["serviceEnd"],
                    "limitedOperationMarks": limited_marks,
                    "sourceLine": line_index,
                    "stopTimes": stop_times,
                }
            )
    return {
        "direction": direction,
        "serviceStart": source["serviceStart"],
        "serviceEnd": source["serviceEnd"],
        "sourceUrl": source["url"],
        "cachePath": str(path.relative_to(ROOT)),
        "status": "ok" if trips else "no_trips",
        "stops": stops,
        "tripCount": len(trips),
        "trips": trips,
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    directions = []
    for source in PDF_SOURCES:
        path = fetch_pdf(source["url"], args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        directions.append(parse_pdf(source, path))
    routes = [
        {
            "sourceKind": "official_kotoden_pdf_timetable",
            "operatorName": "ことでんバス",
            "airportIata": "TAK",
            "routeCode": "tak_kotoden_takamatsu_city",
            "routeName": "高松市内 ⇔ 高松空港リムジンバス",
            "sourceUrl": BASE,
            "directions": directions,
            "routeStopNames": sorted({stop for direction in directions for stop in direction["stops"]}),
            "tripCount": sum(direction["tripCount"] for direction in directions),
        }
    ]
    source = {
        "schemaVersion": "v5_official_bus_source.takamatsu_kotoden.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Kotoden Takamatsu Airport limousine PDFs. Limited-operation symbols are preserved on trips; service-date windows are copied from each PDF.",
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.takamatsu_kotoden.v1",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "tripCount": sum(route["tripCount"] for route in routes),
        "directions": [{k: direction[k] for k in ["direction", "serviceStart", "serviceEnd", "status", "tripCount", "sourceUrl"]} for direction in directions],
    }
    return source, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    source, audit = collect(args)
    write_json(args.output, source)
    write_json(args.docs_output, source)
    write_json(args.audit_output, audit)
    print(json.dumps({"routeCount": audit["routeCount"], "tripCount": audit["tripCount"], "directions": audit["directions"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
