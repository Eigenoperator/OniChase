#!/usr/bin/env python3
"""Collect official Shikoku Chuo / Kanonji Takamatsu Airport bus PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE_URL = "https://www.takamatsu-airport.com/assets/timeschedule/timetable_bus_05.pdf"
TO_AIRPORT_STOPS = ["四国中央停留所", "高速観音寺バス停", "高速善通寺バス停", "高速丸亀バス停", "高松空港"]
FROM_AIRPORT_STOPS = list(reversed(TO_AIRPORT_STOPS))
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "takamatsu_shikokuchuo"
DEFAULT_OUTPUT = ROOT / "data" / "v5_takamatsu_shikokuchuo_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_takamatsu_shikokuchuo_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_takamatsu_shikokuchuo_official_bus_audit.json"


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


def stop_times(stops: list[str], times: list[str]) -> list[dict[str, str]]:
    return [{"stopName": stop, "time": time, "raw": time} for stop, time in zip(stops, times)]


def parse_trips(text: str) -> list[dict[str, Any]]:
    trips = []
    for line in text.splitlines():
        match = re.match(r"\s*(1|3|5|7|9|11|13)\s+", line)
        if not match:
            continue
        times = re.findall(r"\d{1,2}:\d{2}", line)
        if len(times) < 10:
            continue
        outbound_number = match.group(1)
        inbound_match = re.search(r"\s(2|4|6|8|10|12|14)\s+", line)
        outbound_times = times[:5]
        inbound_times = times[-5:]
        trips.append(
            {
                "tripId": f"tak_shikokuchuo:to_airport:{outbound_number}",
                "direction": "to_airport",
                "serviceNumber": outbound_number,
                "stopTimes": stop_times(TO_AIRPORT_STOPS, outbound_times),
            }
        )
        if inbound_match:
            inbound_number = inbound_match.group(1)
            trips.append(
                {
                    "tripId": f"tak_shikokuchuo:from_airport:{inbound_number}",
                    "direction": "from_airport",
                    "serviceNumber": inbound_number,
                    "reservationNote": "1便・14便 require reservation by previous day 17:00 per official PDF" if inbound_number == "14" else "",
                    "stopTimes": stop_times(FROM_AIRPORT_STOPS, inbound_times),
                }
            )
    return trips


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    pdf_path = fetch_pdf(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    trips = parse_trips(pdf_layout_text(pdf_path))
    directions = []
    for direction, stops in [("to_airport", TO_AIRPORT_STOPS), ("from_airport", FROM_AIRPORT_STOPS)]:
        direction_trips = [trip for trip in trips if trip["direction"] == direction]
        directions.append({"direction": direction, "stops": stops, "tripCount": len(direction_trips), "trips": direction_trips})
    route = {
        "sourceKind": "official_takamatsu_airport_pdf_timetable",
        "operatorName": "琴参バス・西讃観光バス",
        "airportIata": "TAK",
        "routeCode": "tak_shikokuchuo_kanonji_marugame",
        "routeName": "四国中央・観音寺・善通寺・丸亀 ⇔ 高松空港",
        "sourceUrl": SOURCE_URL,
        "cachePath": str(pdf_path.relative_to(ROOT)),
        "directions": directions,
        "routeStopNames": sorted(set(TO_AIRPORT_STOPS)),
        "tripCount": len(trips),
    }
    source = {
        "schemaVersion": "v5_official_bus_source.takamatsu_shikokuchuo.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Takamatsu Airport PDF timetable. The parser reads the complete left/right paired timetable rows; official reservation note for first/last trips is preserved.",
        "routes": [route],
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.takamatsu_shikokuchuo.v1",
        "generatedAt": generated_at,
        "routeCount": 1,
        "tripCount": route["tripCount"],
        "directions": [{"direction": item["direction"], "tripCount": item["tripCount"], "stopCount": len(item["stops"])} for item in directions],
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
