#!/usr/bin/env python3
"""Collect official remote-airport bus timetables for V5 gameplay."""

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
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "remote_airport_bus"
DEFAULT_OUTPUT = ROOT / "data" / "v5_remote_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_remote_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_remote_airport_official_bus_audit.json"

OGN_SOURCE_URL = "https://welcome-yonaguni.jp/wp-content/uploads/2026/03/yonaguni_bus_2026.pdf"
NTQ_SOURCE_URLS = [
    "https://www.hokutetsu.co.jp/highway-bus/noto/",
    "https://www.hokutetsu.co.jp/_wp/wp-content/uploads/2026/04/c8b02ddbc9a94b03a25f5e6255891183-1.pdf",
    "https://www.hokutetsu.co.jp/_wp/wp-content/uploads/2026/04/eaa060855d021d23056f6b8dc576b0f0-1.pdf",
]

STOPS = {
    "与那国空港": {"lat": 24.467298, "lon": 122.979827, "coordinateSource": "OurAirports OGN coordinate"},
    "祖納": {"lat": 24.4682479, "lon": 122.9990670, "coordinateSource": "nominatim:与那国 祖納"},
    "久部良": {"lat": 24.4515554, "lon": 122.9432108, "coordinateSource": "nominatim:久部良 bus_stop"},
    "金沢駅西口": {"lat": 36.5782273, "lon": 136.6464271, "coordinateSource": "nominatim:金沢駅西口 bus_stop"},
    "穴水駅前": {"lat": 37.2283081, "lon": 136.9045919, "coordinateSource": "nominatim:穴水駅前 bus_stop"},
    "のと里山空港": {"lat": 37.293098, "lon": 136.962006, "coordinateSource": "OurAirports NTQ coordinate"},
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


def make_trip(route_code: str, direction: str, index: int, start_name: str, end_name: str, start: str, end: str) -> dict[str, Any]:
    return {
        "tripId": f"{route_code}:{direction}:{index:03d}",
        "direction": direction,
        "serviceStart": "20260401" if route_code.startswith("yonaguni") else "20260315",
        "serviceEnd": "20270331",
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
    source_urls: list[str],
    cache_paths: list[Path],
    service_start: str,
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
        "sourceUrl": source_urls[0],
        "sourceUrls": source_urls,
        "cachePath": str(cache_paths[0].relative_to(ROOT)),
        "cachePaths": [str(path.relative_to(ROOT)) for path in cache_paths],
        "serviceStart": service_start,
        "serviceEnd": "20270331",
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
    ogn_cache = fetch(OGN_SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    ntq_caches = [fetch(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout) for url in NTQ_SOURCE_URLS]
    for path in [ogn_cache, *ntq_caches]:
        if path.stat().st_size < 10_000:
            raise ValueError(f"Remote airport source looks too small: {path}")

    routes = [
        route(
            source_kind="official_yonaguni_town_bus_pdf",
            operator_name="与那国町生活路線バス",
            airport_iata="OGN",
            route_code="yonaguni_airport_sonai",
            route_name="祖納 ⇔ 与那国空港",
            source_urls=[OGN_SOURCE_URL],
            cache_paths=[ogn_cache],
            service_start="20260401",
            fare=0,
            stops=["祖納", "与那国空港"],
            trips=[
                make_trip("yonaguni_airport_sonai", "to_airport", i, "祖納", "与那国空港", start, end)
                for i, (start, end) in enumerate(
                    [("07:30", "08:07"), ("09:10", "09:47"), ("11:20", "12:15"), ("13:40", "14:17"), ("15:00", "15:55"), ("16:45", "17:22")],
                    start=1,
                )
            ]
            + [
                make_trip("yonaguni_airport_sonai", "from_airport", i, "与那国空港", "祖納", start, end)
                for i, (start, end) in enumerate(
                    [("09:05", "09:10"), ("11:15", "11:20"), ("13:35", "13:40"), ("14:55", "15:00"), ("16:40", "16:45"), ("18:45", "18:50")],
                    start=1,
                )
            ],
            source_notes=["Official 2026-04-01 Yonaguni route-bus PDF. Endpoint segments are emitted from airport passes to 祖納."],
        ),
        route(
            source_kind="official_yonaguni_town_bus_pdf",
            operator_name="与那国町生活路線バス",
            airport_iata="OGN",
            route_code="yonaguni_airport_kubura",
            route_name="久部良 ⇔ 与那国空港",
            source_urls=[OGN_SOURCE_URL],
            cache_paths=[ogn_cache],
            service_start="20260401",
            fare=0,
            stops=["久部良", "与那国空港"],
            trips=[
                make_trip("yonaguni_airport_kubura", "to_airport", i, "久部良", "与那国空港", start, end)
                for i, (start, end) in enumerate(
                    [("07:59", "08:25"), ("09:39", "10:05"), ("11:41", "12:15"), ("15:21", "15:55"), ("17:14", "17:40")],
                    start=1,
                )
            ]
            + [
                make_trip("yonaguni_airport_kubura", "from_airport", i, "与那国空港", "久部良", start, end)
                for i, (start, end) in enumerate(
                    [("09:05", "09:39"), ("11:15", "11:41"), ("13:35", "14:09"), ("14:55", "15:21"), ("16:40", "17:14"), ("18:45", "19:11")],
                    start=1,
                )
            ],
            source_notes=["Official 2026-04-01 Yonaguni route-bus PDF. Endpoint segments are emitted from airport passes to 久部良."],
        ),
        route(
            source_kind="official_hokutetsu_noto_pdf",
            operator_name="北陸鉄道",
            airport_iata="NTQ",
            route_code="noto_airport_kanazawa",
            route_name="金沢駅西口 ⇔ のと里山空港",
            source_urls=NTQ_SOURCE_URLS,
            cache_paths=ntq_caches,
            service_start="20260315",
            fare=None,
            stops=["金沢駅西口", "のと里山空港"],
            trips=[
                make_trip("noto_airport_kanazawa", "to_airport", i, "金沢駅西口", "のと里山空港", start, end)
                for i, (start, end) in enumerate(
                    [("07:15", "09:34"), ("10:20", "12:39"), ("12:00", "14:19"), ("13:30", "15:49"), ("15:40", "17:59"), ("17:20", "19:39")],
                    start=1,
                )
            ]
            + [
                make_trip("noto_airport_kanazawa", "from_airport", i, "のと里山空港", "金沢駅西口", start, end)
                for i, (start, end) in enumerate(
                    [("06:45", "09:09"), ("07:55", "10:19"), ("10:25", "12:49"), ("11:55", "14:19"), ("13:55", "16:19"), ("17:45", "20:09")],
                    start=1,
                )
            ],
            source_notes=["Official Hokutetsu Noto limited-bus timetable revised 2026-03-15. Endpoint gameplay uses 金沢駅西口 and のと里山空港 rows from the directional PDFs."],
        ),
        route(
            source_kind="official_hokutetsu_noto_pdf",
            operator_name="北陸鉄道",
            airport_iata="NTQ",
            route_code="noto_airport_anamizu",
            route_name="穴水駅前 ⇔ のと里山空港",
            source_urls=NTQ_SOURCE_URLS,
            cache_paths=ntq_caches,
            service_start="20260315",
            fare=None,
            stops=["穴水駅前", "のと里山空港"],
            trips=[
                make_trip("noto_airport_anamizu", "to_airport", i, "穴水駅前", "のと里山空港", start, end)
                for i, (start, end) in enumerate(
                    [("09:14", "09:34"), ("12:19", "12:39"), ("13:59", "14:19"), ("15:29", "15:49"), ("17:39", "17:59"), ("19:19", "19:39")],
                    start=1,
                )
            ]
            + [
                make_trip("noto_airport_anamizu", "from_airport", i, "のと里山空港", "穴水駅前", start, end)
                for i, (start, end) in enumerate(
                    [("06:45", "07:00"), ("07:55", "08:10"), ("10:25", "10:40"), ("11:55", "12:10"), ("13:55", "14:10"), ("17:45", "18:00")],
                    start=1,
                )
            ],
            source_notes=["Official Hokutetsu Noto limited-bus timetable revised 2026-03-15. Endpoint gameplay uses 穴水駅前 and のと里山空港 rows from the directional PDFs."],
        ),
    ]
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_remote_airport_bus",
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
        "sourceUrls": [OGN_SOURCE_URL, *NTQ_SOURCE_URLS],
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
