#!/usr/bin/env python3
"""Promote Heartland Ferry current regular timetable and adult 2nd-class fares."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_heartland_batch_official.json")
OPERATOR = "ハートランドフェリー"


def hm(value: str) -> int:
    value = value.replace("：", ":")
    next_day = value.startswith("翌")
    value = value.replace("翌", "")
    hour, minute = value.split(":")
    total = int(hour) * 60 + int(minute)
    if next_day:
        total += 24 * 60
    return total


def route(route_id: str, origin: str, destination: str, fare: int, source_urls: list[str], note: str) -> dict:
    return {
        "routeId": route_id,
        "operator": OPERATOR,
        "routeName": f"{origin}・{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "island_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": source_urls,
            "notes": note,
        },
        "servicePatterns": [],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str, source_url: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    if arr_min < dep_min:
        arr_min += 24 * 60
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": OPERATOR,
        "serviceNo": str(no),
        "vessel": None,
        "origin": origin,
        "destination": destination,
        "departure": dep.replace("：", ":"),
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": source_url,
    }


def add_trips(trips: list[dict], route_id: str, origin: str, destination: str, source_url: str, rows: list[tuple[int, str, str]]) -> None:
    for service_no, dep, arr in rows:
        trips.append(trip(route_id, service_no, origin, destination, dep, arr, source_url))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    wakkanai_rishiri_time = "https://heartlandferry.jp/timetable/"
    wakkanai_rebun_time = "https://heartlandferry.jp/timetable/time1/"
    rishiri_rebun_time = "https://heartlandferry.jp/timetable/time2/"
    okushiri_time = "https://heartlandferry.jp/timetable/time3/"
    rishiri_rebun_fare = "https://heartlandferry.jp/faretable/"
    okushiri_fare = "https://heartlandferry.jp/faretable/okushiri-route/"
    common_note = "Official 2026 timetable/fare page, adult passenger 2nd-class one-way fare only. Current V5 collection date 2026-05-21 uses the 4/28-5/31 timetable for Wakkanai/Rishiri/Rebun and the 5/7-6/30 timetable plus 2026-01-01 to 2026-06-30 fare table for Esashi/Okushiri. Reserved seats, 1st class, vehicles, baggage, discounts, temporary extra sailings, disruption status, and future date-range fare/calendar selection are excluded."
    routes = [
        route("heartland_wakkanai_rishiri_rebun_000_out", "稚内港", "鴛泊港", 3590, [wakkanai_rishiri_time, rishiri_rebun_fare], common_note),
        route("heartland_wakkanai_rishiri_rebun_001_back", "鴛泊港", "稚内港", 3590, [wakkanai_rishiri_time, rishiri_rebun_fare], common_note),
        route("heartland_wakkanai_rishiri_rebun_002_out", "鴛泊港", "香深港", 1800, [rishiri_rebun_time, rishiri_rebun_fare], common_note),
        route("heartland_wakkanai_rishiri_rebun_003_back", "香深港", "鴛泊港", 1800, [rishiri_rebun_time, rishiri_rebun_fare], common_note),
        route("heartland_esashi_okushiri_004_out", "江差港", "奥尻港", 3460, [okushiri_time, okushiri_fare], common_note),
        route("heartland_esashi_okushiri_005_back", "奥尻港", "江差港", 3460, [okushiri_time, okushiri_fare], common_note),
    ]
    trips: list[dict] = []
    add_trips(trips, routes[0]["routeId"], "稚内港", "鴛泊港", wakkanai_rishiri_time, [
        (1, "06:45", "08:25"),
        (2, "10:10", "11:50"),
        (3, "14:30", "16:10"),
    ])
    add_trips(trips, routes[1]["routeId"], "鴛泊港", "稚内港", wakkanai_rishiri_time, [
        (4, "08:55", "10:35"),
        (5, "14:35", "16:15"),
        (6, "16:40", "18:20"),
    ])
    add_trips(trips, routes[2]["routeId"], "鴛泊港", "香深港", rishiri_rebun_time, [(7, "12:15", "13:00")])
    add_trips(trips, routes[3]["routeId"], "香深港", "鴛泊港", rishiri_rebun_time, [(8, "13:25", "14:10")])
    add_trips(trips, routes[4]["routeId"], "江差港", "奥尻港", okushiri_time, [(9, "13:00", "15:10")])
    add_trips(trips, routes[5]["routeId"], "奥尻港", "江差港", okushiri_time, [(10, "07:00", "09:10")])
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": OPERATOR,
        "operatorId": "heartland_ferry",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({wakkanai_rishiri_time, wakkanai_rebun_time, rishiri_rebun_time, okushiri_time, rishiri_rebun_fare, okushiri_fare}),
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
