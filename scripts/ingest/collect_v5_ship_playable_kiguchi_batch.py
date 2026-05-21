#!/usr/bin/env python3
"""Promote Kiguchi Kisen official timetable and adult fares."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_kiguchi_batch_official.json")
SOURCE = "https://www.kiguchi-kisen.jp/contents/timetable/"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str, fare: int, note: str) -> dict:
    return {
        "routeId": route_id,
        "operator": "木口汽船",
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
            "sourceUrls": [SOURCE],
            "notes": note,
        },
        "servicePatterns": [],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str, vessel: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    if arr_min < dep_min:
        arr_min += 24 * 60
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": "木口汽船",
        "serviceNo": str(no),
        "vessel": vessel,
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": SOURCE,
    }


def add_pairs(trips: list[dict], route_id: str, origin: str, destination: str, vessel: str, pairs: list[tuple[str, str]]) -> None:
    for index, (dep, arr) in enumerate(pairs, 1):
        trips.append(trip(route_id, index, origin, destination, dep, arr, vessel))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    hisaka_note = "Adult passenger fare 福江-田の浦 ¥790 from official 木口汽船 table; V5 route uses 久賀 as the island aggregate. Excludes child fares, resident discounts, baggage, vehicles, and special items."
    kabashima_note = "Adult passenger fare for 福江-椛島 official ports is ¥810-¥830 depending on 本窯/伊福貴; V5 uses ¥830 for the island aggregate. Excludes child fares, resident discounts, baggage, vehicles, and special items."
    routes = [
        route("mlit_map_193_055_木口汽船_久賀_福江_椛島_000_out", "久賀", "福江港", 790, hisaka_note),
        route("mlit_map_193_055_木口汽船_久賀_福江_椛島_000_back", "福江港", "久賀", 790, hisaka_note),
        route("mlit_map_193_055_木口汽船_久賀_福江_椛島_001_out", "福江港", "椛島", 830, kabashima_note),
        route("mlit_map_193_055_木口汽船_久賀_福江_椛島_001_back", "椛島", "福江港", 830, kabashima_note),
    ]
    trips: list[dict] = []
    add_pairs(trips, routes[0]["routeId"], "久賀", "福江港", "フェリーひさか/シーガル", [("08:00", "08:34"), ("09:35", "09:55"), ("12:30", "12:50"), ("17:10", "17:30")])
    add_pairs(trips, routes[1]["routeId"], "福江港", "久賀", "フェリーひさか/シーガル", [("09:10", "09:30"), ("12:05", "12:25"), ("13:35", "14:09"), ("16:45", "17:05")])
    add_pairs(trips, routes[2]["routeId"], "福江港", "椛島", "ソレイユ", [("07:25", "08:00"), ("13:15", "13:34"), ("16:35", "16:54")])
    add_pairs(trips, routes[3]["routeId"], "椛島", "福江港", "ソレイユ", [("08:05", "08:24"), ("13:40", "14:13"), ("17:00", "17:33")])
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "木口汽船",
        "operatorId": "kiguchi_kisen",
        "retrievedAt": retrieved_at,
        "sourceUrls": [SOURCE],
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 2,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
