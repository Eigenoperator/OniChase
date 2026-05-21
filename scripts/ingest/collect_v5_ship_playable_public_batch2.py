#!/usr/bin/env python3
"""Promote another batch of verified public ferry routes.

Routes in this file are only added when an official/operator source gives
explicit departure/arrival times and an adult passenger fare.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_public_batch2_official.json")

AGUNI_SOURCES = [
    "https://www.vill.aguni.okinawa.jp/material/files/group/1/unkou_2026_05_1.pdf",
    "https://www.vill.aguni.okinawa.jp/material/files/group/1/unkou_2026_06.pdf",
    "https://www.aguni-archive.jp/access/",
]
TOBA_SOURCES = [
    "https://www.city.toba.mie.jp/soshiki/t_kanri/gyomu/doro_kotsu/kokyo_kotsu/3151.html",
    "https://www.city.toba.mie.jp/material/files/group/45/teikisendaiya.pdf",
]
IESHIMA_SOURCES = [
    "https://kousoku-ieshima.jp/%E6%99%82%E5%88%BB%E8%A1%A8/",
    "https://kousoku-ieshima.jp/sample-page/",
]


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(
    route_id: str,
    group_id: str,
    operator: str,
    route_name: str,
    origin: str,
    destination: str,
    fare_yen: int,
    source_urls: list[str],
    notes: str,
) -> dict:
    return {
        "routeId": route_id,
        "routeGroupId": group_id,
        "operator": operator,
        "routeName": route_name,
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "short_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare_yen},
            "sourceUrls": source_urls,
            "notes": notes,
        },
        "servicePatterns": [],
        "sourceUrls": source_urls,
    }


def trip(
    route_id: str,
    operator: str,
    vessel: str,
    no: int,
    origin: str,
    destination: str,
    dep: str,
    arr: str,
    source_url: str,
    notes: str = "",
) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    if arr_min < dep_min:
        arr_min += 24 * 60
    return {
        "tripId": f"{route_id}_daily_{no:03d}",
        "routeId": route_id,
        "operator": operator,
        "serviceNo": str(no),
        "vessel": vessel,
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": source_url,
        "notes": notes,
    }


def add_aguni(routes: list[dict], trips: list[dict]) -> None:
    out_id = "aguni_naha_aguni_084_out"
    back_id = "aguni_naha_aguni_085_back"
    fare_note = (
        "Aguni Archive access page lists the regular adult passenger one-way fare as 3,470 JPY. "
        "May/June 2026 Aguni Village monthly operation PDFs list 泊港 09:30 and 粟国港 13:45, "
        "with about two hours travel time. Child fares, islander discounts, round-trip discounts, "
        "air service, baggage, vehicles, weather cancellations, and monthly maintenance exceptions are excluded."
    )
    routes.extend([
        route(out_id, "aguni_naha_aguni", "粟国村", "ニューフェリーあぐに", "那覇泊港", "粟国港", 3470, AGUNI_SOURCES, fare_note),
        route(back_id, "aguni_naha_aguni", "粟国村", "ニューフェリーあぐに", "粟国港", "那覇泊港", 3470, AGUNI_SOURCES, fare_note),
    ])
    trips.append(trip(out_id, "粟国村", "ニューフェリーあぐに", 1, "那覇泊港", "粟国港", "09:30", "11:30", AGUNI_SOURCES[0], "Official monthly PDFs list departure times; arrival uses the official approximately two-hour sailing time."))
    trips.append(trip(back_id, "粟国村", "ニューフェリーあぐに", 1, "粟国港", "那覇泊港", "13:45", "15:45", AGUNI_SOURCES[0], "Official monthly PDFs list departure times; arrival uses the official approximately two-hour sailing time."))


def add_toba_kamishima(routes: list[dict], trips: list[dict]) -> None:
    out_id = "toba_kamishima_020_out"
    back_id = "toba_kamishima_021_back"
    fare_note = (
        "Toba City 2026-04-01 regular ship timetable PDF lists the adult fare table; "
        "鳥羽-神島 is 740 JPY. Seasonal/charter-only late sailings, child fares, free passes, "
        "bus discounts, and disruption notices are excluded."
    )
    routes.extend([
        route(out_id, "toba_kamishima", "鳥羽市", "鳥羽市営定期船 神島航路", "鳥羽港", "神島港", 740, TOBA_SOURCES, fare_note),
        route(back_id, "toba_kamishima", "鳥羽市", "鳥羽市営定期船 神島航路", "神島港", "鳥羽港", 740, TOBA_SOURCES, fare_note),
    ])
    for no, (dep, arr, note) in enumerate([
        ("07:40", "08:20", "Via 和具."),
        ("10:40", "11:20", "Via 和具."),
        ("14:30", "15:00", "Direct sailing in the official 神島行 table."),
    ], 1):
        trips.append(trip(out_id, "鳥羽市", "鳥羽市営定期船", no, "鳥羽港", "神島港", dep, arr, TOBA_SOURCES[1], note))
    for no, (dep, arr, note) in enumerate([
        ("06:50", "07:28", "Via 菅島 in the official 鳥羽行 table."),
        ("08:35", "09:13", "Via 菅島 in the official 鳥羽行 table."),
        ("11:35", "12:00", "Direct sailing in the official 鳥羽行 table."),
        ("15:10", "15:40", "Direct sailing in the official 鳥羽行 table."),
    ], 1):
        trips.append(trip(back_id, "鳥羽市", "鳥羽市営定期船", no, "神島港", "鳥羽港", dep, arr, TOBA_SOURCES[1], note))


def add_kousoku_ieshima(routes: list[dict], trips: list[dict]) -> None:
    out_id = "kousoku_ieshima_030_out"
    back_id = "kousoku_ieshima_031_back"
    fare_note = (
        "Operator fare image lists adult passenger fare for 家島(真浦) and 家島(宮) to 姫路 as 1,000 JPY. "
        "Operator timetable image is marked 2025-02-08 revised and shows the same weekday/weekend-holiday schedule. "
        "Student/child fares, commuter tickets, baggage, bicycle, disability discounts, and disruption notices are excluded."
    )
    routes.extend([
        route(out_id, "kousoku_ieshima", "高速いえしま", "姫路-家島高速船", "姫路港", "家島真浦港", 1000, IESHIMA_SOURCES, fare_note),
        route(back_id, "kousoku_ieshima", "高速いえしま", "姫路-家島高速船", "家島真浦港", "姫路港", 1000, IESHIMA_SOURCES, fare_note),
    ])
    for no, (dep, arr, note) in enumerate([
        ("07:10", "07:41", "Via 宮港."),
        ("09:10", "09:41", "Via 宮港."),
        ("11:05", "11:43", "Via 宮港."),
        ("13:40", "14:11", "Direct to 真浦港 in the operator table."),
        ("15:30", "16:01", "Via 宮港."),
        ("17:10", "17:50", "Via 宮港."),
        ("19:00", "19:31", "Direct to 真浦港 in the operator table."),
        ("20:35", "21:13", "Via 宮港."),
    ], 1):
        trips.append(trip(out_id, "高速いえしま", "高速いえしま", no, "姫路港", "家島真浦港", dep, arr, IESHIMA_SOURCES[0], note))
    for no, (dep, arr, note) in enumerate([
        ("06:30", "07:01", "Direct from 真浦港 in the operator table."),
        ("08:15", "08:46", "Direct from 真浦港 in the operator table."),
        ("09:50", "10:31", "Via 宮港."),
        ("13:00", "13:31", "Direct from 真浦港 in the operator table."),
        ("14:30", "15:01", "Direct from 真浦港 in the operator table."),
        ("16:10", "16:51", "Via 宮港."),
        ("17:55", "18:26", "Direct from 真浦港 in the operator table."),
        ("19:50", "20:31", "Via 宮港."),
    ], 1):
        trips.append(trip(back_id, "高速いえしま", "高速いえしま", no, "家島真浦港", "姫路港", dep, arr, IESHIMA_SOURCES[0], note))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes: list[dict] = []
    trips: list[dict] = []
    add_aguni(routes, trips)
    add_toba_kamishima(routes, trips)
    add_kousoku_ieshima(routes, trips)
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "public_ferry_batch2",
        "operatorId": "public_ferry_batch2",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for route_item in routes for url in route_item["sourceUrls"]}),
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 3,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "excludedDirections": [
                "鳥羽市営定期船 seasonal/charter-only late 神島 sailings are excluded until calendar/season handling is represented explicitly.",
                "高速いえしま 宮港-only playable legs are deferred because the current queue route pair is 姫路港-家島真浦港.",
                "ニューフェリーあぐに monthly maintenance/no-service exceptions are documented but not yet represented in the gameplay calendar model.",
            ],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
