#!/usr/bin/env python3
"""Collect official Niigata Airport bus PDF timetable sources.

The official PDFs publish complete endpoint times for the direct airport bus
between 新潟駅 and 新潟空港. The airport -> station PDF also lists local buses
via 万代シテイ with weekday/weekend departures and an official about-35-minute
runtime. Those local buses are promoted as endpoint-playable trips; the source
does not expose a full intermediate stop-time table.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE_URLS = [
    "https://www.niigata-kotsu.co.jp/~noriai/route-bus/timetable/access/airport/files/260329_niigatasta-tt.pdf",
    "https://www.niigata-kotsu.co.jp/~noriai/route-bus/timetable/access/airport/files/260329_airport-tt.pdf",
]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "niigata_airport_pdfs"
DEFAULT_OUTPUT = ROOT / "data" / "v5_niigata_airport_official_bus_pdfs.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_niigata_airport_official_bus_pdfs.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_niigata_airport_official_bus_pdfs_audit.json"

ALL_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
WEEKENDS = ["saturday", "sunday"]

TO_AIRPORT_DEPARTURES = [
    "06:10",
    "06:35",
    "07:20",
    "07:50",
    "08:25",
    "08:50",
    "09:25",
    "10:05",
    "10:30",
    "10:50",
    "11:20",
    "12:10",
    "13:05",
    "13:40",
    "14:00",
    "14:30",
    "14:50",
    "15:40",
    "16:05",
    "16:40",
    "17:20",
    "17:40",
    "17:55",
    "18:15",
]

FROM_AIRPORT_DIRECT_DEPARTURES = [
    "08:40",
    "09:10",
    "10:05",
    "10:45",
    "11:25",
    "11:40",
    "12:00",
    "12:20",
    "12:35",
    "12:50",
    "13:20",
    "13:40",
    "14:30",
    "15:25",
    "15:40",
    "15:50",
    "16:30",
    "17:00",
    "17:25",
    "18:40",
    "19:00",
    "19:25",
    "20:20",
    "21:05",
    "21:20",
]

FROM_AIRPORT_LOCAL_WEEKDAY_DEPARTURES = [
    "08:25",
    "09:00",
    "09:35",
    "10:40",
    "11:05",
    "11:35",
    "11:50",
    "12:25",
    "12:55",
    "13:10",
    "13:30",
    "14:20",
    "14:45",
    "15:20",
    "16:05",
    "16:35",
    "17:20",
    "17:35",
    "17:45",
    "18:20",
    "19:05",
    "19:15",
    "20:25",
    "20:35",
]

FROM_AIRPORT_LOCAL_WEEKEND_DEPARTURES = [
    "08:20",
    "09:15",
    "10:15",
    "11:05",
    "11:35",
    "12:05",
    "12:30",
    "13:00",
    "14:20",
    "15:20",
    "16:40",
    "17:15",
    "18:25",
    "19:15",
    "20:25",
    "20:40",
]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.pdf"


def fetch_bytes(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[bytes, Path, str]:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path.read_bytes(), path, "application/pdf"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        content_type = response.headers.get("content-type", "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data, path, content_type


def pdf_text(path: Path) -> str:
    result = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=False, capture_output=True, text=True, timeout=30)
    return result.stdout if result.returncode == 0 else ""


def add_minutes(value: str, minutes: int) -> str:
    hour, minute = [int(part) for part in value.split(":")]
    total = hour * 60 + minute + minutes
    return f"{total // 60:02d}:{total % 60:02d}"


def build_trip(
    route_code: str,
    direction: str,
    index: int,
    stop_names: list[str],
    departure: str,
    duration_minutes: int,
    service_days: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "tripId": f"niigata_kotsu:kij:{route_code}:{direction}:{index:03d}",
        "direction": direction,
        "serviceDays": service_days or ALL_DAYS,
        "stopTimes": [
            {"stopName": stop_names[0], "time": departure, "raw": departure},
            {"stopName": stop_names[1], "time": add_minutes(departure, duration_minutes), "raw": f"{departure}+{duration_minutes}min"},
        ],
    }


def build_routes() -> list[dict[str, Any]]:
    direct_trips = []
    for index, departure in enumerate(TO_AIRPORT_DEPARTURES, start=1):
        direct_trips.append(build_trip("niigata_station_airport_direct", "to_airport", index, ["新潟駅", "新潟空港"], departure, 25))
    for index, departure in enumerate(FROM_AIRPORT_DIRECT_DEPARTURES, start=1):
        direct_trips.append(build_trip("niigata_station_airport_direct", "from_airport", index, ["新潟空港", "新潟駅"], departure, 25))
    local_trips = []
    for index, departure in enumerate(FROM_AIRPORT_LOCAL_WEEKDAY_DEPARTURES, start=1):
        local_trips.append(
            build_trip("niigata_airport_bandai_city_local", "from_airport_weekday", index, ["新潟空港", "新潟駅"], departure, 35, WEEKDAYS)
        )
    for index, departure in enumerate(FROM_AIRPORT_LOCAL_WEEKEND_DEPARTURES, start=1):
        local_trips.append(
            build_trip("niigata_airport_bandai_city_local", "from_airport_weekend", index, ["新潟空港", "新潟駅"], departure, 35, WEEKENDS)
        )
    return [
        {
            "sourceKind": "official_niigata_kotsu_airport_pdf_direct_bus",
            "operatorName": "Niigata Kotsu",
            "airportIata": "KIJ",
            "routeCode": "niigata_station_airport_direct",
            "routeName": "新潟駅 ⇔ 新潟空港 直行リムジンバス",
            "sourceUrl": SOURCE_URLS[0],
            "sourcePolicy": "Official Niigata Kotsu PDF endpoint timetable. Direct buses are promoted with published departure times and the official about-25-minute runtime.",
            "adultFareYen": 470,
            "serviceStart": "20260329",
            "serviceEnd": "20270331",
            "trips": direct_trips,
            "tripCount": len(direct_trips),
        },
        {
            "sourceKind": "official_niigata_kotsu_airport_pdf_local_bus",
            "operatorName": "Niigata Kotsu",
            "airportIata": "KIJ",
            "routeCode": "niigata_airport_bandai_city_local",
            "routeName": "新潟空港 → 新潟駅 各停 万代シテイ経由",
            "sourceUrl": SOURCE_URLS[1],
            "sourcePolicy": "Official Niigata Kotsu PDF airport->station local-bus timetable. The PDF lists weekday/weekend airport departures via 万代シテイ and the official about-35-minute runtime, but not a complete intermediate stop-time table; promoted as endpoint-playable trips only.",
            "adultFareYen": 470,
            "serviceStart": "20260329",
            "serviceEnd": "20270331",
            "trips": local_trips,
            "tripCount": len(local_trips),
        },
    ]


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    pdfs = []
    for url in SOURCE_URLS:
        data, path, content_type = fetch_bytes(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        text = pdf_text(path)
        times = sorted(set(re.findall(r"\b\d{1,2}:\d{2}\b", text)))
        direction = "to_airport" if "niigatasta" in url else "from_airport"
        status = "pdf_time_text_found" if times else "pdf_cached_no_time_text"
        pdfs.append(
            {
                "url": url,
                "direction": direction,
                "status": status,
                "contentType": content_type,
                "cachePath": str(path.relative_to(ROOT)),
                "byteCount": len(data),
                "timeTextCount": len(times),
                "sampleTimes": times[:30],
                "textSample": re.sub(r"\s+", " ", text).strip()[:800],
            }
        )
    status_counts = Counter(pdf["status"] for pdf in pdfs)
    source = {
        "schemaVersion": "v5_official_bus_source.niigata_airport_pdfs.v2",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Niigata Kotsu airport-bus PDF timetable sources. Direct airport-bus endpoint times and airport->station local buses via 万代シテイ are normalized into playable route data. Local buses are endpoint-playable because the PDF does not expose intermediate stop-times.",
        "airportIata": "KIJ",
        "operatorName": "Niigata Kotsu",
        "pdfs": pdfs,
        "routes": build_routes(),
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.niigata_airport_pdfs.v2",
        "generatedAt": generated_at,
        "pdfCount": len(pdfs),
        "statusCounts": dict(sorted(status_counts.items())),
        "timeTextPdfCount": status_counts["pdf_time_text_found"],
        "routeCount": 2,
        "tripCount": len(TO_AIRPORT_DEPARTURES)
        + len(FROM_AIRPORT_DIRECT_DEPARTURES)
        + len(FROM_AIRPORT_LOCAL_WEEKDAY_DEPARTURES)
        + len(FROM_AIRPORT_LOCAL_WEEKEND_DEPARTURES),
        "promotedPolicy": "Direct 新潟駅 ⇔ 新潟空港 buses and airport->station 万代シテイ経由 local buses are promoted. Local buses are endpoint-playable only because the PDF does not expose complete intermediate stop-times.",
        "pdfs": pdfs,
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
    print(json.dumps({"pdfCount": audit["pdfCount"], "timeTextPdfCount": audit["timeTextPdfCount"], "statusCounts": audit["statusCounts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
