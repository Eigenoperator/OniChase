#!/usr/bin/env python3
"""Collect official Miyazaki Kotsu airport-bus timetable source data.

The airport website only publishes summary departure times.  For playable V5
runtime data we use the linked Miyazaki Kotsu official route PDFs, which publish
paired stop times for the airport corridors.
"""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "miyazaki_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_miyazaki_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_miyazaki_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_miyazaki_airport_official_bus_audit.json"

MIYAKOH_BASE = "https://www.miyakoh.co.jp"
PDFS = {
    "airport_city": f"{MIYAKOH_BASE}/rosen/0_jikoku/1-16_20260401.pdf",
    "miyakonojo": f"{MIYAKOH_BASE}/rosen/0_jikoku/5-07_20250701.pdf",
    "nichinan_obi": f"{MIYAKOH_BASE}/rosen/0_jikoku/9-02_20260401.pdf",
    "seagaia": f"{MIYAKOH_BASE}/rosen/0_jikoku/1-04_20260401.pdf",
}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
WEEKENDS = ["saturday", "sunday"]
ALL_DAYS = WEEKDAYS + WEEKENDS


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
    if not data.startswith(b"%PDF"):
        raise RuntimeError(f"Expected PDF from {url}, got {data[:20]!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def pdf_text(path: Path) -> str:
    result = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True, text=True, capture_output=True)
    return result.stdout


def build_trip(route_code: str, direction: str, index: int, stop_names: list[str], times: list[str], service_days: list[str]) -> dict[str, Any]:
    return {
        "tripId": f"miyazaki_kotsu:{route_code}:{direction}:{index:03d}",
        "direction": direction,
        "serviceDays": service_days,
        "stopTimes": [{"stopName": stop, "time": time, "raw": time} for stop, time in zip(stop_names, times, strict=True)],
    }


def paired_trips(
    route_code: str,
    direction: str,
    stop_names: list[str],
    origin_times: list[str],
    destination_times: list[str],
    service_days: list[str],
    *,
    start_index: int = 1,
) -> list[dict[str, Any]]:
    if len(origin_times) != len(destination_times):
        raise ValueError(f"{route_code} {direction} has mismatched stop times: {len(origin_times)} vs {len(destination_times)}")
    return [
        build_trip(route_code, direction, start_index + index, stop_names, [origin, destination], service_days)
        for index, (origin, destination) in enumerate(zip(origin_times, destination_times, strict=True))
    ]


def parse_miyakonojo_rows(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse the endpoint and airport columns from the official 都城 PDF.

    The PDF has many intermediate columns.  For airport gameplay we preserve the
    real published endpoint/airport times and use the stop sequence
    西都城駅前バスセンター <-> 宮崎空港.
    """
    to_airport: list[dict[str, Any]] = []
    from_airport: list[dict[str, Any]] = []
    for line in text.splitlines():
        times = re.findall(r"\d{1,2}:\d{2}", line)
        if len(times) < 20:
            continue
        # 西都城 -> 宮崎空港 rows have the airport arrival at the 19th time.
        if times[0] < "19:00" and times[18] > times[0]:
            to_airport.append(build_trip("nishi_miyakonojo", "to_airport", len(to_airport) + 1, ["西都城駅前バスセンター", "宮崎空港"], [times[0], times[18]], ALL_DAYS))
        # 宮崎/宮崎空港 -> 西都城 rows have airport departure at the 7th time.
        if len(times) >= 23 and times[6] >= "06:00" and times[-1] > times[6]:
            from_airport.append(build_trip("nishi_miyakonojo", "from_airport", len(from_airport) + 1, ["宮崎空港", "西都城駅前バスセンター"], [times[6], times[-1]], ALL_DAYS))
    # Deduplicate repeated weekday/weekend rows while preserving order.
    def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set()
        output = []
        for row in rows:
            key = tuple(item["time"] for item in row["stopTimes"])
            if key in seen:
                continue
            seen.add(key)
            row["tripId"] = f"miyazaki_kotsu:nishi_miyakonojo:{row['direction']}:{len(output)+1:03d}"
            output.append(row)
        return output
    return dedupe(to_airport), dedupe(from_airport)


def parse_obi_rows(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    to_city = []
    to_obi = []
    in_obi_to_city = False
    in_city_to_obi = False
    for line in text.splitlines():
        if "宮 崎 線 （飫肥→油津→宮崎空港→宮崎駅）" in line:
            in_obi_to_city = True
            in_city_to_obi = False
            continue
        if "宮 崎 線 （宮崎駅→宮崎空港→油津→飫肥）" in line:
            in_obi_to_city = False
            in_city_to_obi = True
            continue
        if "幸 島 線" in line:
            in_obi_to_city = False
            in_city_to_obi = False
        times = re.findall(r"\d{1,2}:\d{2}", line)
        if in_obi_to_city and len(times) >= 16:
            # 飫肥 is first column; 宮崎空港 is 13th; 宮崎駅 is last.
            to_city.append(build_trip("obi_nichinan", "from_obi", len(to_city) + 1, ["飫肥", "宮崎空港", "宮崎駅"], [times[0], times[12], times[-1]], ALL_DAYS))
        if in_city_to_obi and len(times) >= 16:
            # 宮崎駅 is first column; 宮崎空港 is fourth; 飫肥 is last.
            to_obi.append(build_trip("obi_nichinan", "to_obi", len(to_obi) + 1, ["宮崎駅", "宮崎空港", "飫肥"], [times[0], times[3], times[-1]], ALL_DAYS))
    return to_city, to_obi


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cache_paths = {key: fetch_pdf(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout) for key, url in PDFS.items()}
    texts = {key: pdf_text(path) for key, path in cache_paths.items()}

    city_to_airport_weekday = paired_trips(
        "miyazaki_station",
        "to_airport",
        ["宮崎駅", "宮崎空港"],
        ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:30", "12:10", "12:30", "14:15", "14:30", "15:00", "16:00", "16:20", "17:20", "18:20", "19:10", "20:30"],
        ["08:30", "09:00", "09:35", "09:55", "10:35", "11:05", "12:05", "12:35", "13:05", "14:40", "14:55", "15:35", "16:25", "16:55", "17:55", "18:55", "19:45", "21:00"],
        WEEKDAYS,
    )
    city_from_airport_weekday = paired_trips(
        "miyazaki_station",
        "from_airport",
        ["宮崎空港", "宮崎駅"],
        ["07:04", "07:34", "08:04", "08:34", "09:48", "10:01", "10:50", "11:44", "12:44", "13:10", "13:54", "14:53", "15:05", "15:26", "15:30", "16:26", "17:00", "17:26", "18:16", "19:46"],
        ["07:30", "08:10", "08:40", "09:10", "10:14", "10:30", "11:15", "12:10", "13:10", "13:35", "14:20", "15:22", "15:30", "15:52", "15:56", "16:52", "17:25", "17:52", "18:42", "20:12"],
        WEEKDAYS,
        start_index=100,
    )
    city_to_airport_weekend = paired_trips(
        "miyazaki_station",
        "to_airport",
        ["宮崎駅", "宮崎空港"],
        ["06:40", "08:30", "09:00", "10:00", "10:30", "11:30", "12:00", "13:20", "14:00", "15:00", "16:00", "16:40", "17:30", "19:10", "20:10"],
        ["07:05", "09:00", "09:35", "10:35", "11:05", "12:05", "12:25", "13:45", "14:35", "15:25", "16:35", "17:05", "18:05", "19:40", "20:40"],
        WEEKENDS,
        start_index=200,
    )
    city_from_airport_weekend = paired_trips(
        "miyazaki_station",
        "from_airport",
        ["宮崎空港", "宮崎駅"],
        ["07:34", "08:04", "08:34", "10:04", "11:44", "12:24", "12:40", "13:54", "14:15", "14:56", "15:45", "16:26", "17:20", "18:16", "19:16", "19:55"],
        ["08:00", "08:30", "09:00", "10:30", "12:10", "12:50", "13:05", "14:20", "14:40", "15:22", "16:10", "16:52", "17:45", "18:42", "19:42", "20:21"],
        WEEKENDS,
        start_index=300,
    )

    miyakonojo_to_airport, miyakonojo_from_airport = parse_miyakonojo_rows(texts["miyakonojo"])
    obi_to_city, city_to_obi = parse_obi_rows(texts["nichinan_obi"])
    seagaia_to = paired_trips(
        "seagaia",
        "from_airport",
        ["宮崎空港", "シーガイアＯＴ"],
        ["08:50", "10:15", "12:30", "14:45", "16:40"],
        ["09:17", "10:40", "12:55", "15:10", "17:05"],
        WEEKENDS,
    )
    seagaia_from = paired_trips(
        "seagaia",
        "to_airport",
        ["シーガイアＯＴ", "宮崎空港"],
        ["09:30", "11:40", "13:35", "15:35", "17:15"],
        ["09:54", "12:04", "13:59", "15:59", "17:41"],
        WEEKENDS,
        start_index=100,
    )

    route_specs = [
        ("miyazaki_station", "宮崎駅 ⇔ 宮崎空港", PDFS["airport_city"], city_to_airport_weekday + city_from_airport_weekday + city_to_airport_weekend + city_from_airport_weekend),
        ("nishi_miyakonojo", "西都城駅前バスセンター ⇔ 宮崎空港", PDFS["miyakonojo"], miyakonojo_to_airport + miyakonojo_from_airport),
        ("obi_nichinan", "飫肥・日南 ⇔ 宮崎空港", PDFS["nichinan_obi"], obi_to_city + city_to_obi),
        ("seagaia", "シーガイア ⇔ 宮崎空港", PDFS["seagaia"], seagaia_to + seagaia_from),
    ]
    routes = []
    for code, name, url, trips in route_specs:
        routes.append(
            {
                "sourceKind": "official_miyakoh_pdf_timetable",
                "operatorName": "Miyazaki Kotsu",
                "airportIata": "KMI",
                "routeCode": code,
                "routeName": name,
                "sourceUrl": url,
                "cachePath": str(cache_paths[next(key for key, value in PDFS.items() if value == url)].relative_to(ROOT)),
                "sourcePolicy": "Official Miyazaki Kotsu PDF timetable. Endpoint/airport stop times are preserved from the published route tables.",
                "trips": trips,
                "tripCount": len(trips),
            }
        )
    source = {
        "schemaVersion": "v5_official_bus_source.miyazaki_airport.v2",
        "generatedAt": generated_at,
        "sourceUrls": PDFS,
        "sourcePolicy": "Playable Miyazaki Airport bus source built from official Miyazaki Kotsu route PDFs instead of airport summary departure-only rows.",
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.miyazaki_airport.v2",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "tripCount": sum(route["tripCount"] for route in routes),
        "routes": [
            {
                "routeCode": route["routeCode"],
                "routeName": route["routeName"],
                "tripCount": route["tripCount"],
                "status": "complete_endpoint_airport_stop_times",
            }
            for route in routes
        ],
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
    print(json.dumps({"routeCount": audit["routeCount"], "tripCount": audit["tripCount"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
