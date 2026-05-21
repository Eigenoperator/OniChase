#!/usr/bin/env python3
"""Promote Tsugaru Kaikyo Ferry current regular timetable and A-period fares."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_tsugaru_batch_official.json")
SOURCE_BASE = "https://www.tsugarukaikyo.co.jp/service/"


def hm(value: str) -> int:
    value = value.replace("：", ":")
    next_day = value.startswith("翌")
    value = value.replace("翌", "")
    hour, minute = value.split(":")
    total = int(hour) * 60 + int(minute)
    if next_day or total == 0:
        total += 24 * 60
    return total


def route(route_id: str, origin: str, destination: str, fare: int, time_source: str, fare_source: str, note: str) -> dict:
    return {
        "routeId": route_id,
        "operator": "津軽海峡フェリー",
        "routeName": f"{origin}・{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "interregional_public_ferry",
        "revealPolicy": "long_distance_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": [fare_source],
            "notes": note,
        },
        "servicePatterns": [],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str, vessel: str, source: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    if arr_min < dep_min:
        arr_min += 24 * 60
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": "津軽海峡フェリー",
        "serviceNo": str(no),
        "vessel": vessel,
        "origin": origin,
        "destination": destination,
        "departure": dep.replace("：", ":"),
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": source,
    }


def add_pairs(trips: list[dict], route_id: str, origin: str, destination: str, source: str, rows: list[tuple[int, str, str, str]]) -> None:
    for service_no, vessel, dep, arr in rows:
        trips.append(trip(route_id, service_no, origin, destination, dep, arr, vessel, source))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    muroran_time = "https://www.tsugarukaikyo.co.jp/service/timetable/muroran-aomori/"
    hakodate_aomori_time = "https://www.tsugarukaikyo.co.jp/service/timetable/hakodate-aomori/"
    hakodate_oma_time = "https://www.tsugarukaikyo.co.jp/service/timetable/hakodate-oma/"
    muroran_fare = "https://www.tsugarukaikyo.co.jp/service/fare/muroran-aomori/"
    hakodate_aomori_fare = "https://www.tsugarukaikyo.co.jp/service/fare/hakodate-aomori/"
    hakodate_oma_fare = "https://www.tsugarukaikyo.co.jp/service/fare/hakodate-oma/"
    common_note = "Official 2026-04-01 A-period adult standard-seat fare. Current V5 release date 2026-05-21 is in A period. B/C period fare selection, room upgrades, vehicle fares, discounts, web discounts, dog rooms, baggage, and special/inspection/holiday schedule exceptions are excluded until date-range fare/calendar modeling is added."
    routes = [
        route("tsugaru_aomori_muroran_044_out", "青森港", "室蘭港", 5590, muroran_time, muroran_fare, common_note),
        route("tsugaru_aomori_muroran_045_back", "室蘭港", "青森港", 5590, muroran_time, muroran_fare, common_note),
        route("tsugaru_aomori_hakodate_040_out", "青森港", "函館港", 3160, hakodate_aomori_time, hakodate_aomori_fare, common_note),
        route("tsugaru_aomori_hakodate_041_back", "函館港", "青森港", 3160, hakodate_aomori_time, hakodate_aomori_fare, common_note),
        route("tsugaru_oma_hakodate_042_out", "大間港", "函館港", 2520, hakodate_oma_time, hakodate_oma_fare, common_note),
        route("tsugaru_oma_hakodate_043_back", "函館港", "大間港", 2520, hakodate_oma_time, hakodate_oma_fare, common_note),
    ]
    trips: list[dict] = []
    add_pairs(trips, routes[0]["routeId"], "青森港", "室蘭港", muroran_time, [(1, "ブルーグレイス", "10:40", "17:25")])
    add_pairs(trips, routes[1]["routeId"], "室蘭港", "青森港", muroran_time, [(2, "ブルーグレイス", "20:50", "翌3:50")])
    add_pairs(trips, routes[2]["routeId"], "青森港", "函館港", hakodate_aomori_time, [
        (3, "ブルーマーメイド", "2:30", "6:10"), (7, "ブルーハピネス", "6:25", "10:05"),
        (11, "ブルードルフィン", "10:15", "13:55"), (13, "ブルーマーメイド", "14:20", "18:00"),
        (17, "ブルーハピネス", "17:15", "20:50"), (23, "ブルードルフィン", "22:25", "翌2:05"),
    ])
    add_pairs(trips, routes[3]["routeId"], "函館港", "青森港", hakodate_aomori_time, [
        (4, "ブルードルフィン", "3:20", "7:00"), (8, "ブルーマーメイド", "7:40", "11:20"),
        (14, "ブルーハピネス", "12:30", "16:05"), (18, "ブルードルフィン", "17:30", "21:10"),
        (22, "ブルーマーメイド", "20:15", "24:00"), (24, "ブルーハピネス", "22:05", "翌1:45"),
    ])
    add_pairs(trips, routes[4]["routeId"], "大間港", "函館港", hakodate_oma_time, [
        (5, "大函丸", "6:50", "8:20"), (9, "大函丸", "13:40", "15:10"),
    ])
    add_pairs(trips, routes[5]["routeId"], "函館港", "大間港", hakodate_oma_time, [
        (6, "大函丸", "9:10", "10:40"), (10, "大函丸", "16:00", "17:30"),
    ])
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "津軽海峡フェリー",
        "operatorId": "tsugaru_kaikyo_ferry",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({SOURCE_BASE, muroran_time, hakodate_aomori_time, hakodate_oma_time, muroran_fare, hakodate_aomori_fare, hakodate_oma_fare}),
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 3,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
