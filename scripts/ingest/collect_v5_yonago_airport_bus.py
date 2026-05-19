#!/usr/bin/env python3
"""Collect Yonago Kitaro Airport official access-bus timetables."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "yonago_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_yonago_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_yonago_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_yonago_airport_official_bus_audit.json"

AIRPORT_ACCESS_URL = "https://www.yonago-air.com/access/bus/"
HINOMARU_URL = "https://hinomarubus.co.jp/route/airport/?tab=2"
MATSUE_URL = "https://t-matsue.ichibata.co.jp/airport-bus-yonago/"
MATSUE_PDF_URL = "https://t-matsue.ichibata.co.jp/wp-content/media/米子空港連絡バス時刻表新）2026.3.29～2026.10.24-2.pdf"
SERVICE_START = "20260329"
SERVICE_END = "20261024"

STOPS = {
    "米子駅": {"lat": 35.423335, "lon": 133.33668, "coordinateSource": "OniChase N02 rail station centroid: 米子"},
    "松江駅": {"lat": 35.46409, "lon": 133.063965, "coordinateSource": "OniChase N02 rail station centroid: 松江"},
    "米子鬼太郎空港": {"lat": 35.492199, "lon": 133.235992, "coordinateSource": "OurAirports YGJ coordinate"},
}

YONAGO_TO_AIRPORT = [
    ("06:20", "06:45", "ANA382"),
    ("07:20", "07:45", "ANA384"),
    ("09:40", "10:05", "ANA386"),
    ("12:35", "13:00", "ANA1088"),
    ("16:00", "16:25", "ANA388"),
    ("18:50", "19:15", "ANA390"),
]
YONAGO_FROM_AIRPORT = [
    ("08:25", "08:53", "ANA381"),
    ("10:35", "11:03", "ANA383"),
    ("13:25", "13:53", "ANA1087"),
    ("16:45", "17:13", "ANA385"),
    ("19:35", "20:03", "ANA387"),
    ("21:30", "21:58", "ANA389"),
]
MATSUE_TO_AIRPORT = [
    ("05:50", "06:35", "ANA382", "松江一畑"),
    ("07:15", "08:00", "ANA384", "日ノ丸"),
    ("09:25", "10:10", "ANA386", "松江一畑"),
    ("12:15", "13:00", "ANA1088", "日ノ丸"),
    ("15:40", "16:25", "ANA388", "松江一畑"),
    ("18:30", "19:15", "ANA390", "日ノ丸"),
]
MATSUE_FROM_AIRPORT = [
    ("08:25", "09:10", "ANA381", "松江一畑"),
    ("10:35", "11:20", "ANA383", "日ノ丸"),
    ("13:25", "14:10", "ANA1087", "松江一畑"),
    ("16:45", "17:30", "ANA385", "日ノ丸"),
    ("19:35", "20:20", "ANA387", "松江一畑"),
    ("21:35", "22:20", "ANA389", "日ノ丸"),
]


def cache_path_for(cache_dir: Path, url: str) -> Path:
    parsed = urllib.parse.urlparse(url)
    suffix = ".pdf" if parsed.path.lower().endswith(".pdf") else ".html"
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}{suffix}"


def fetch(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> Path:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path
    parts = urllib.parse.urlsplit(url)
    safe_url = urllib.parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            urllib.parse.quote(parts.path, safe="/%"),
            urllib.parse.quote_plus(parts.query, safe="=&"),
            parts.fragment,
        )
    )
    request = urllib.request.Request(safe_url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def assert_source_contains(access_cache: Path, hinomaru_cache: Path, matsue_cache: Path, matsue_pdf_cache: Path) -> None:
    access = access_cache.read_text(encoding="utf-8", errors="ignore")
    hinomaru = hinomaru_cache.read_text(encoding="utf-8", errors="ignore")
    matsue = matsue_cache.read_text(encoding="utf-8", errors="ignore")
    checks = [
        (access, ["米子駅", "松江駅", "640円", "1,200円"]),
        (hinomaru, ["令和8年3月29日～令和8年10月24日", "米子鬼太郎空港", "米子駅", "390便"]),
        (matsue, ["2026年03月29日～2026年10月24日", "米子空港連絡バス", "JR松江駅"]),
    ]
    for text, markers in checks:
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise ValueError(f"Yonago airport source is missing expected markers: {missing}")
    if matsue_pdf_cache.stat().st_size < 50_000:
        raise ValueError(f"Yonago Matsue PDF cache is unexpectedly small: {matsue_pdf_cache}")


def trip(trip_id: str, direction: str, start_name: str, end_name: str, start: str, end: str, flight: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "tripId": trip_id,
        "direction": direction,
        "serviceStart": SERVICE_START,
        "serviceEnd": SERVICE_END,
        "serviceDays": "daily",
        "notes": f"Connects flight {flight}",
        "stopTimes": [{"stopName": start_name, "time": start}, {"stopName": end_name, "time": end}],
    }
    payload.update(extra)
    return payload


def build_routes(cache_paths: dict[str, Path]) -> list[dict[str, Any]]:
    yonago_trips = []
    for index, (start, end, flight) in enumerate(YONAGO_TO_AIRPORT, start=1):
        yonago_trips.append(trip(f"yonago_airport_yonago_station:to_airport:{index:03d}", "to_airport", "米子駅", "米子鬼太郎空港", start, end, flight))
    for index, (start, end, flight) in enumerate(YONAGO_FROM_AIRPORT, start=1):
        yonago_trips.append(trip(f"yonago_airport_yonago_station:from_airport:{index:03d}", "from_airport", "米子鬼太郎空港", "米子駅", start, end, flight))

    matsue_trips = []
    for index, (start, end, flight, operator) in enumerate(MATSUE_TO_AIRPORT, start=1):
        matsue_trips.append(trip(f"yonago_airport_matsue_station:to_airport:{index:03d}", "to_airport", "松江駅", "米子鬼太郎空港", start, end, flight, operatingCompany=operator))
    for index, (start, end, flight, operator) in enumerate(MATSUE_FROM_AIRPORT, start=1):
        matsue_trips.append(trip(f"yonago_airport_matsue_station:from_airport:{index:03d}", "from_airport", "米子鬼太郎空港", "松江駅", start, end, flight, operatingCompany=operator))

    return [
        {
            "sourceKind": "official_yonago_airport_hinomaru_html",
            "operatorName": "日ノ丸自動車",
            "airportIata": "YGJ",
            "routeCode": "yonago_airport_yonago_station",
            "routeName": "米子鬼太郎空港連絡バス 米子駅 ⇔ 米子鬼太郎空港",
            "sourceUrl": HINOMARU_URL,
            "sourceUrls": [AIRPORT_ACCESS_URL, HINOMARU_URL],
            "cachePath": str(cache_paths["hinomaru"].relative_to(ROOT)),
            "cachePaths": [str(cache_paths["access"].relative_to(ROOT)), str(cache_paths["hinomaru"].relative_to(ROOT))],
            "serviceStart": SERVICE_START,
            "serviceEnd": SERVICE_END,
            "serviceDays": "daily",
            "adultFareYen": 640,
            "routeStopNames": ["米子駅", "米子鬼太郎空港"],
            "tripCount": len(yonago_trips),
            "stops": [{"stopName": name, **STOPS[name]} for name in ["米子駅", "米子鬼太郎空港"]],
            "busStops": [{"name": name, **STOPS[name]} for name in ["米子駅", "米子鬼太郎空港"]],
            "trips": yonago_trips,
            "sourceNotes": ["Official Hinomaru Bus page covers 2026-03-29 through 2026-10-24."],
        },
        {
            "sourceKind": "official_yonago_airport_matsue_pdf",
            "operatorName": "松江一畑交通・日ノ丸ハイヤー",
            "airportIata": "YGJ",
            "routeCode": "yonago_airport_matsue_station",
            "routeName": "米子空港連絡バス 松江駅 ⇔ 米子鬼太郎空港",
            "sourceUrl": MATSUE_PDF_URL,
            "sourceUrls": [AIRPORT_ACCESS_URL, MATSUE_URL, MATSUE_PDF_URL],
            "cachePath": str(cache_paths["matsue_pdf"].relative_to(ROOT)),
            "cachePaths": [
                str(cache_paths["access"].relative_to(ROOT)),
                str(cache_paths["matsue"].relative_to(ROOT)),
                str(cache_paths["matsue_pdf"].relative_to(ROOT)),
            ],
            "serviceStart": SERVICE_START,
            "serviceEnd": SERVICE_END,
            "serviceDays": "daily",
            "adultFareYen": 1200,
            "routeStopNames": ["松江駅", "米子鬼太郎空港"],
            "tripCount": len(matsue_trips),
            "stops": [{"stopName": name, **STOPS[name]} for name in ["松江駅", "米子鬼太郎空港"]],
            "busStops": [{"name": name, **STOPS[name]} for name in ["松江駅", "米子鬼太郎空港"]],
            "trips": matsue_trips,
            "sourceNotes": [
                "Official Matsue Ichibata PDF covers 2026-03-29 through 2026-10-24.",
                "Airport departures may wait for baggage claim after flight arrival, but the official timetable also publishes fixed scheduled departure times; those fixed times are emitted for gameplay.",
            ],
        },
    ]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cache_paths = {
        "access": fetch(AIRPORT_ACCESS_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout),
        "hinomaru": fetch(HINOMARU_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout),
        "matsue": fetch(MATSUE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout),
        "matsue_pdf": fetch(MATSUE_PDF_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout),
    }
    assert_source_contains(cache_paths["access"], cache_paths["hinomaru"], cache_paths["matsue"], cache_paths["matsue_pdf"])
    routes = build_routes(cache_paths)
    all_trips = [trip for route in routes for trip in route["trips"]]
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_yonago_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source pages retain copyright.",
        "routes": routes,
    }
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "routeCount": len(routes),
        "tripCount": len(all_trips),
        "stopCount": 3,
        "coordinateStopCount": 3,
        "directionCounts": dict(Counter(trip["direction"] for trip in all_trips)),
        "routeTripCounts": {route["routeCode"]: len(route["trips"]) for route in routes},
    }
    return payload, audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--refresh-cache", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload, audit = collect(args)
    write_json(args.output, payload)
    write_json(args.docs_output, payload)
    write_json(args.audit_output, audit)
    if args.docs_output != args.output:
        args.docs_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.output, args.docs_output)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
