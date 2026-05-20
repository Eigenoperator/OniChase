#!/usr/bin/env python3
"""Collect official island airport-bus timetables for V5 gameplay."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "island_airport_bus"
DEFAULT_OUTPUT = ROOT / "data" / "v5_island_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_island_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_island_airport_official_bus_audit.json"

IKI_SOURCE_URL = "https://iki-kotsu.com/pdf/iki_AirPortBus.pdf"
OKE_SOURCE_URL = "https://okinoerabubus.org/wp-content/uploads/2026/04/schedule_202604.pdf"

STOPS = {
    "郷ノ浦": {"lat": 33.7423282, "lon": 129.6852920, "coordinateSource": "nominatim:郷ノ浦港フェリーターミナル"},
    "壱岐空港": {"lat": 33.7490005493, "lon": 129.785003662, "coordinateSource": "OurAirports IKI coordinate"},
    "知名": {"lat": 27.3384823, "lon": 128.5738367, "coordinateSource": "nominatim:知名町役場"},
    "和泊": {"lat": 27.3920939, "lon": 128.6555217, "coordinateSource": "nominatim:和泊町役場"},
    "沖永良部空港": {"lat": 27.431604, "lon": 128.705564, "coordinateSource": "OurAirports OKE coordinate"},
}


def cache_path_for(cache_dir: Path, url: str) -> Path:
    suffix = Path(url.split("?", 1)[0]).suffix or ".html"
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}{suffix}"


def fetch(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> Path:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_trip(route_code: str, direction: str, index: int, start_name: str, end_name: str, start: str, end: str, service_start: str, service_end: str) -> dict[str, Any]:
    return {
        "tripId": f"{route_code}:{direction}:{index:03d}",
        "direction": direction,
        "serviceStart": service_start,
        "serviceEnd": service_end,
        "serviceDays": "daily",
        "stopTimes": [{"stopName": start_name, "time": start}, {"stopName": end_name, "time": end}],
    }


def route(
    *,
    source_kind: str,
    operator_name: str,
    airport_iata: str,
    route_code: str,
    route_name: str,
    source_url: str,
    cache_path: Path,
    service_start: str,
    service_end: str,
    fare: int | None,
    stops: list[str],
    trips: list[dict[str, Any]],
    source_notes: list[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "sourceKind": source_kind,
        "operatorName": operator_name,
        "airportIata": airport_iata,
        "routeCode": route_code,
        "routeName": route_name,
        "sourceUrl": source_url,
        "sourceUrls": [source_url],
        "cachePath": str(cache_path.relative_to(ROOT)),
        "cachePaths": [str(cache_path.relative_to(ROOT))],
        "serviceStart": service_start,
        "serviceEnd": service_end,
        "serviceDays": "daily",
        "routeStopNames": stops,
        "tripCount": len(trips),
        "stops": [{"stopName": name, **STOPS[name]} for name in stops],
        "busStops": [{"name": name, **STOPS[name]} for name in stops],
        "trips": trips,
        "sourceNotes": source_notes,
    }
    if fare is not None:
        payload["adultFareYen"] = fare
    return payload


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    iki_cache = fetch(IKI_SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    oke_cache = fetch(OKE_SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    if iki_cache.stat().st_size < 10_000:
        raise ValueError(f"Iki airport source looks too small: {iki_cache}")
    if oke_cache.stat().st_size < 10_000:
        raise ValueError(f"Okinoerabu airport source looks too small: {oke_cache}")

    routes = [
        route(
            source_kind="official_iki_kotsu_airport_pdf",
            operator_name="壱岐交通",
            airport_iata="IKI",
            route_code="iki_airport_gonoura",
            route_name="郷ノ浦 ⇔ 壱岐空港",
            source_url=IKI_SOURCE_URL,
            cache_path=iki_cache,
            service_start="20260329",
            service_end="20261024",
            fare=None,
            stops=["郷ノ浦", "壱岐空港"],
            trips=[
                make_trip("iki_airport_gonoura", "to_airport", 1, "郷ノ浦", "壱岐空港", "16:45", "17:10", "20260329", "20261024"),
                make_trip("iki_airport_gonoura", "from_airport", 1, "壱岐空港", "郷ノ浦", "17:20", "17:45", "20260329", "20261024"),
            ],
            source_notes=[
                "Official PDF includes ORC41/42 and ORC43/44 airport-connection buses for 2026-03-29 through 2026-10-24.",
                "ORC41/42 has explicit planned suspension windows in 2026, so only the ORC43/44 pair is promoted until calendar-date exceptions are modeled for official bus sources.",
                "Intermediate stops via 印通寺 are visible in the source PDF but not emitted until stop coordinates are reviewed.",
            ],
        ),
        route(
            source_kind="official_okinoerabu_bus_airport_pdf",
            operator_name="沖永良部バス企業団",
            airport_iata="OKE",
            route_code="okinoerabu_airport_china",
            route_name="知名 ⇔ 沖永良部空港",
            source_url=OKE_SOURCE_URL,
            cache_path=oke_cache,
            service_start="20251015",
            service_end="20270331",
            fare=850,
            stops=["知名", "沖永良部空港"],
            trips=[
                make_trip("okinoerabu_airport_china", "to_airport", i, "知名", "沖永良部空港", start, end, "20251015", "20270331")
                for i, (start, end) in enumerate(
                    [
                        ("07:35", "08:33"),
                        ("09:05", "10:03"),
                        ("10:25", "11:23"),
                        ("11:25", "12:23"),
                        ("12:30", "13:28"),
                        ("14:00", "14:58"),
                        ("15:20", "16:18"),
                    ],
                    start=1,
                )
            ]
            + [
                make_trip("okinoerabu_airport_china", "from_airport", i, "沖永良部空港", "知名", start, end, "20251015", "20270331")
                for i, (start, end) in enumerate(
                    [
                        ("09:25", "10:23"),
                        ("10:15", "11:13"),
                        ("11:45", "12:43"),
                        ("12:35", "13:33"),
                        ("14:15", "15:13"),
                        ("15:05", "16:03"),
                        ("16:40", "17:38"),
                    ],
                    start=1,
                )
            ],
            source_notes=[
                "Official PDF is the 空港線 / 知名・国頭線 timetable effective from 2025-10-15.",
                "Two 国頭-origin trips shown without airport departure/arrival are not promoted as airport-access trips.",
                "Intermediate stops through 和泊 are visible in the source PDF but only airport-to-town endpoint play is emitted until all stop coordinates are reviewed.",
            ],
        ),
        route(
            source_kind="official_okinoerabu_bus_airport_pdf",
            operator_name="沖永良部バス企業団",
            airport_iata="OKE",
            route_code="okinoerabu_airport_wadomari",
            route_name="和泊 ⇔ 沖永良部空港",
            source_url=OKE_SOURCE_URL,
            cache_path=oke_cache,
            service_start="20251015",
            service_end="20270331",
            fare=430,
            stops=["和泊", "沖永良部空港"],
            trips=[
                make_trip("okinoerabu_airport_wadomari", "to_airport", i, "和泊", "沖永良部空港", start, end, "20251015", "20270331")
                for i, (start, end) in enumerate(
                    [
                        ("08:12", "08:33"),
                        ("09:42", "10:03"),
                        ("11:02", "11:23"),
                        ("12:02", "12:23"),
                        ("13:07", "13:28"),
                        ("14:37", "14:58"),
                        ("15:57", "16:18"),
                    ],
                    start=1,
                )
            ]
            + [
                make_trip("okinoerabu_airport_wadomari", "from_airport", i, "沖永良部空港", "和泊", start, end, "20251015", "20270331")
                for i, (start, end) in enumerate(
                    [
                        ("09:25", "09:47"),
                        ("10:15", "10:37"),
                        ("11:45", "12:07"),
                        ("12:35", "12:57"),
                        ("14:15", "14:37"),
                        ("15:05", "15:27"),
                        ("16:40", "17:02"),
                    ],
                    start=1,
                )
            ],
            source_notes=[
                "Official PDF is the 空港線 / 知名・国頭線 timetable effective from 2025-10-15.",
                "和泊 is emitted as a second playable endpoint because the official airport line passes through the 和泊 town stop on every airport trip.",
            ],
        ),
    ]
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_island_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source PDFs retain copyright.",
        "routes": routes,
    }
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "routeCount": len(routes),
        "tripCount": sum(len(item["trips"]) for item in routes),
        "stopCount": len({stop["name"] for item in routes for stop in item["busStops"]}),
        "coordinateStopCount": len({stop["name"] for item in routes for stop in item["busStops"] if isinstance(stop.get("lat"), (int, float))}),
        "airportCounts": dict(Counter(route["airportIata"] for route in routes)),
        "operatorCounts": dict(Counter(route["operatorName"] for route in routes)),
        "sourceUrls": [IKI_SOURCE_URL, OKE_SOURCE_URL],
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
