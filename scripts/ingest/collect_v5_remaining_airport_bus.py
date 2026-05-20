#!/usr/bin/env python3
"""Collect remaining small-airport public-bus sources for V5 gameplay."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "remaining_airport_bus"
DEFAULT_OUTPUT = ROOT / "data" / "v5_remaining_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_remaining_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_remaining_airport_official_bus_audit.json"

ASJ_SOURCE_URL = "https://amami-airport.co.jp/access/bus"
KKX_SOURCE_URLS = [
    "https://www.town.kikai.lg.jp/kankou/kanko-iju/kotsuannai/documents/jikokuhyo.pdf",
    "https://www.town.kikai.lg.jp/kikaku/documents/r6kotsukaigisiryo.pdf",
]
TNE_SOURCE_URL = "https://www.furusato-tanegashima.net/access/airport-taxi.html"
RNJ_SOURCE_URL = "https://www.yoron.jp/kiji0037638/index.html"
RNJ_TIMETABLE_URL = "https://www.yoron.jp/kiji0037638/3_7638_432_up_5prbvmn5.pdf"
OIR_SOURCE_URLS = [
    "https://www.town.okushiri.lg.jp/hotnews/detail/00009548.html",
    "https://www.town.okushiri.lg.jp/hotnews/files/00008000/00008088/20250401094722.pdf",
    "https://unimaru.com/wordpress/wp-content/uploads/2024/06/2ff428d15b8e6ab83130f2331573abfe.pdf",
]
RIS_SOURCE_URLS = [
    "https://www.soyabus.co.jp/routebus/rishiri",
    "https://www.soyabus.co.jp/app-wp/wp-content/themes/Souyabus-child/images/routebus/rishiri_airport_202507-09.pdf",
]
KTD_NO_BUS_URL = "https://mb.jorudan.co.jp/os/blim/ktd/"

STOPS = {
    "奄美空港": {"lat": 28.430633, "lon": 129.712542, "coordinateSource": "OurAirports ASJ coordinate"},
    "名瀬郵便局": {"lat": 28.380694, "lon": 129.494167, "coordinateSource": "manual_review:naze_post_office"},
    "ホテルウエストコート": {"lat": 28.3779, "lon": 129.4935, "coordinateSource": "manual_review:Hotel West Court Amami"},
    "喜界空港": {"lat": 28.321301, "lon": 129.928055, "coordinateSource": "OurAirports KKX coordinate"},
    "湾営業所": {"lat": 28.3190, "lon": 129.9401, "coordinateSource": "manual_review:Kikai Wan bus depot"},
    "種子島空港": {"lat": 30.605101, "lon": 130.991, "coordinateSource": "OurAirports TNE coordinate"},
    "西之表港": {"lat": 30.7325, "lon": 130.9979, "coordinateSource": "manual_review:Nishinoomote Port"},
    "中種子町役場": {"lat": 30.5329, "lon": 130.9586, "coordinateSource": "manual_review:Nakatane Town Hall"},
    "与論空港": {"lat": 27.044001, "lon": 128.401993, "coordinateSource": "OurAirports RNJ coordinate"},
    "茶花海岸前": {"lat": 27.0491, "lon": 128.4142, "coordinateSource": "manual_review:Chabana coast bus stop"},
    "南バス前": {"lat": 27.0478, "lon": 128.4148, "coordinateSource": "manual_review:Nanriku bus depot"},
    "奥尻空港": {"lat": 42.071701, "lon": 139.432999, "coordinateSource": "OurAirports OIR coordinate"},
    "奥尻港フェリーターミナル": {"lat": 42.1724, "lon": 139.5161, "coordinateSource": "manual_review:Okushiri ferry terminal"},
    "神威脇温泉": {"lat": 42.0634, "lon": 139.4379, "coordinateSource": "manual_review:Kamuiwaki Onsen"},
    "利尻空港": {"lat": 45.242001, "lon": 141.186005, "coordinateSource": "OurAirports RIS coordinate"},
    "鴛泊フェリーターミナル": {"lat": 45.2442, "lon": 141.2265, "coordinateSource": "manual_review:Oshidomari ferry terminal"},
}


def cache_path_for(cache_dir: Path, url: str) -> Path:
    suffix = Path(url.split("?", 1)[0]).suffix or ".html"
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}{suffix}"


def fetch(url: str, cache_dir: Path, *, refresh: bool, timeout: int, optional: bool = False) -> Path | None:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        if optional:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"Optional source fetch failed for {url}: {exc}\n", encoding="utf-8")
            return path
        raise
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
        "serviceStart": "20260329",
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
    fare: int | None,
    stops: list[str],
    trips: list[dict[str, Any]],
    source_notes: list[str],
    service_days: str = "daily",
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
        "serviceStart": "20260329",
        "serviceEnd": "20270331",
        "serviceDays": service_days,
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
    cache_paths = {
        "asj": [fetch(ASJ_SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)],
        "kkx": [fetch(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout, optional=(i == 0)) for i, url in enumerate(KKX_SOURCE_URLS)],
        "tne": [fetch(TNE_SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)],
        "rnj": [
            fetch(RNJ_SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout, optional=True),
            fetch(RNJ_TIMETABLE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout),
        ],
        "oir": [fetch(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout, optional=True) for url in OIR_SOURCE_URLS],
        "ris": [fetch(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout, optional=True) for url in RIS_SOURCE_URLS],
        "ktd": [fetch(KTD_NO_BUS_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout, optional=True)],
    }
    routes = [
        route(
            source_kind="official_amami_airport_html",
            operator_name="しまバス",
            airport_iata="ASJ",
            route_code="amami_airport_naze",
            route_name="名瀬市街 ⇔ 奄美空港",
            source_urls=[ASJ_SOURCE_URL],
            cache_paths=cache_paths["asj"],
            fare=None,
            stops=["名瀬郵便局", "ホテルウエストコート", "奄美空港"],
            trips=[
                make_trip("amami_airport_naze", "from_airport", i, "奄美空港", "ホテルウエストコート", start, end)
                for i, (start, end) in enumerate(
                    [
                        ("06:50", "07:55"), ("08:15", "09:20"), ("08:47", "09:41"), ("09:15", "10:11"),
                        ("09:45", "10:35"), ("10:15", "11:11"), ("10:45", "11:41"), ("11:15", "12:05"),
                        ("11:45", "12:41"), ("12:15", "13:11"), ("12:45", "13:35"), ("13:15", "14:11"),
                        ("13:45", "14:41"), ("14:15", "15:05"), ("14:45", "15:41"), ("15:15", "16:11"),
                        ("15:45", "16:35"), ("16:45", "17:41"), ("17:15", "18:11"), ("17:45", "18:41"),
                        ("18:17", "19:05"), ("18:47", "19:41"),
                    ],
                    start=1,
                )
            ]
            + [
                make_trip("amami_airport_naze", "to_airport", i, "名瀬郵便局", "奄美空港", start, end)
                for i, (start, end) in enumerate(
                    [
                        ("06:39", "07:47"), ("07:09", "07:56"), ("07:12", "08:20"), ("08:07", "09:03"),
                        ("08:42", "09:33"), ("09:12", "10:03"), ("09:34", "10:25"), ("10:12", "11:03"),
                        ("10:42", "11:33"), ("11:04", "11:55"), ("11:42", "12:33"), ("12:12", "13:03"),
                        ("12:34", "13:25"), ("13:12", "14:03"), ("13:42", "14:33"), ("14:04", "14:55"),
                        ("14:42", "15:33"), ("15:12", "16:03"), ("15:34", "16:25"), ("16:12", "17:03"),
                        ("16:42", "17:33"), ("17:04", "17:55"), ("18:09", "19:17"),
                    ],
                    start=1,
                )
            ],
            source_notes=["Amami Airport official access page publishes the Naze-city airport bus timetable and states airport-city travel is about 55 minutes."],
        ),
        route(
            source_kind="official_kikai_bus_pdf",
            operator_name="奄美航空喜界バス",
            airport_iata="KKX",
            route_code="kikai_airport_wan",
            route_name="湾営業所 ⇔ 喜界空港",
            source_urls=KKX_SOURCE_URLS,
            cache_paths=[p for p in cache_paths["kkx"] if p],
            fare=None,
            stops=["湾営業所", "喜界空港"],
            trips=[
                make_trip("kikai_airport_wan", "to_airport", i, "湾営業所", "喜界空港", start, end)
                for i, (start, end) in enumerate(
                    [("08:40", "09:00"), ("09:50", "10:03"), ("11:00", "11:16"), ("12:00", "12:21"), ("13:30", "13:43"), ("15:20", "15:36"), ("16:50", "17:11")],
                    start=1,
                )
            ]
            + [
                make_trip("kikai_airport_wan", "from_airport", i, "喜界空港", "湾営業所", start, end)
                for i, (start, end) in enumerate(
                    [("08:42", "08:57"), ("10:33", "10:38"), ("11:11", "11:23"), ("11:56", "12:02"), ("12:47", "13:02"), ("13:53", "13:58"), ("14:51", "15:03"), ("15:56", "16:02"), ("17:07", "17:22")],
                    start=1,
                )
            ],
            source_notes=["Kikai Town public-transport meeting PDF contains the same Kikai Bus timetable as the current public timetable page; endpoint rows between 湾営業所 and 空港 are promoted for gameplay."],
        ),
        route(
            source_kind="official_tanegashima_reservation_taxi_html",
            operator_name="種子島地域公共交通活性化協議会",
            airport_iata="TNE",
            route_code="tanegashima_airport_nishinoomote",
            route_name="西之表港 ⇔ 種子島空港",
            source_urls=[TNE_SOURCE_URL],
            cache_paths=cache_paths["tne"],
            fare=1200,
            stops=["西之表港", "種子島空港"],
            trips=[
                make_trip("tanegashima_airport_nishinoomote", "to_airport", i, "西之表港", "種子島空港", start, end)
                for i, (start, end) in enumerate([("08:20", "08:50"), ("11:20", "11:50"), ("13:45", "14:15"), ("17:00", "17:30")], start=1)
            ]
            + [
                make_trip("tanegashima_airport_nishinoomote", "from_airport", i, "種子島空港", "西之表港", start, end)
                for i, (start, end) in enumerate([("09:10", "09:40"), ("12:10", "12:40"), ("14:35", "15:05"), ("17:50", "18:20")], start=1)
            ],
            source_notes=["Official Furusato Tanegashima page says the airport public transport is reservation-type shared taxi, usable by anyone with prior reservation."],
        ),
        route(
            source_kind="official_tanegashima_reservation_taxi_html",
            operator_name="種子島地域公共交通活性化協議会",
            airport_iata="TNE",
            route_code="tanegashima_airport_nakatane",
            route_name="中種子町役場 ⇔ 種子島空港",
            source_urls=[TNE_SOURCE_URL],
            cache_paths=cache_paths["tne"],
            fare=800,
            stops=["中種子町役場", "種子島空港"],
            trips=[
                make_trip("tanegashima_airport_nakatane", "to_airport", i, "中種子町役場", "種子島空港", start, end)
                for i, (start, end) in enumerate([("08:30", "08:50"), ("11:25", "11:45"), ("13:50", "14:10"), ("17:10", "17:30")], start=1)
            ]
            + [
                make_trip("tanegashima_airport_nakatane", "from_airport", i, "種子島空港", "中種子町役場", start, end)
                for i, (start, end) in enumerate([("09:10", "09:30"), ("12:05", "12:25"), ("14:30", "14:50"), ("17:50", "18:10")], start=1)
            ],
            source_notes=["Official Furusato Tanegashima page gives four daily reservation-type shared taxi round trips between 中種子町役場 and 種子島空港."],
        ),
        route(
            source_kind="official_yoron_town_bus_pdf",
            operator_name="南陸運",
            airport_iata="RNJ",
            route_code="yoron_bus_chabana",
            route_name="南バス前・茶花海岸前 島内循環",
            source_urls=[RNJ_SOURCE_URL, RNJ_TIMETABLE_URL],
            cache_paths=cache_paths["rnj"],
            fare=200,
            stops=["南バス前", "茶花海岸前"],
            trips=[
                make_trip("yoron_bus_chabana", "clockwise", i, "南バス前", "茶花海岸前", start, end)
                for i, (start, end) in enumerate([("07:30", "07:32"), ("09:30", "09:32"), ("10:30", "10:32"), ("14:30", "14:32"), ("15:30", "15:32")], start=1)
            ]
            + [
                make_trip("yoron_bus_chabana", "counterclockwise", i, "茶花海岸前", "南バス前", start, end)
                for i, (start, end) in enumerate([("09:11", "09:13"), ("12:11", "12:13"), ("13:41", "13:43"), ("17:21", "17:23")], start=1)
            ],
            source_notes=["Yoron Town official page publishes Nanriku island-loop buses. The loop does not enter 与論空港, but 茶花/南バス前 stops are close enough for V5 walking airport access."],
        ),
        route(
            source_kind="official_okushiri_town_bus_pdf",
            operator_name="奥尻町有バス",
            airport_iata="OIR",
            route_code="okushiri_airport_ferry",
            route_name="奥尻港フェリーターミナル ⇔ 奥尻空港",
            source_urls=OIR_SOURCE_URLS,
            cache_paths=[p for p in cache_paths["oir"] if p],
            fare=None,
            stops=["奥尻港フェリーターミナル", "奥尻空港"],
            trips=[
                make_trip("okushiri_airport_ferry", "to_airport", 1, "奥尻港フェリーターミナル", "奥尻空港", "11:15", "12:01"),
                make_trip("okushiri_airport_ferry", "from_airport", 1, "奥尻空港", "奥尻港フェリーターミナル", "12:40", "13:26"),
            ],
            source_notes=["Okushiri Town announces a flight-connected bus diagram from 2026-04-01; airport-origin timing uses the published 奥尻空港12:40発 connection."],
        ),
        route(
            source_kind="official_soya_bus_rishiri_airport_pdf",
            operator_name="宗谷バス",
            airport_iata="RIS",
            route_code="rishiri_airport_oshidomari",
            route_name="鴛泊フェリーターミナル ⇔ 利尻空港",
            source_urls=RIS_SOURCE_URLS,
            cache_paths=[p for p in cache_paths["ris"] if p],
            fare=None,
            stops=["鴛泊フェリーターミナル", "利尻空港"],
            trips=[
                make_trip("rishiri_airport_oshidomari", "to_airport", 1, "鴛泊フェリーターミナル", "利尻空港", "13:40", "13:55"),
                make_trip("rishiri_airport_oshidomari", "from_airport", 1, "利尻空港", "鴛泊フェリーターミナル", "13:35", "13:55"),
            ],
            source_notes=["Soya Bus publishes a seasonal 利尻空港専用バス timetable for the ANA CTS flight. Endpoint times are promoted for the current seasonal flight pair."],
        ),
    ]
    documented_no_public_bus = [
        {
            "airportIata": "KTD",
            "airportName": "北大東空港",
            "sourceUrl": KTD_NO_BUS_URL,
            "cachePath": str(cache_paths["ktd"][0].relative_to(ROOT)) if cache_paths["ktd"][0] else None,
            "reason": "Official airport-bus indexes and public airport guides do not list any fixed public bus for 北大東空港; do not invent a playable bus route.",
        }
    ]
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_remaining_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source pages/PDFs retain copyright.",
        "routes": routes,
        "documentedNoPublicBus": documented_no_public_bus,
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
        "documentedNoPublicBus": documented_no_public_bus,
        "sourceUrls": [ASJ_SOURCE_URL, *KKX_SOURCE_URLS, TNE_SOURCE_URL, RNJ_SOURCE_URL, RNJ_TIMETABLE_URL, *OIR_SOURCE_URLS, *RIS_SOURCE_URLS, KTD_NO_BUS_URL],
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
