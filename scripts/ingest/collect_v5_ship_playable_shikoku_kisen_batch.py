#!/usr/bin/env python3
"""Promote Shikoku Kisen Naoshima official passenger timetable and fares."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_shikoku_kisen_batch_official.json")
TIME_SOURCE = "https://www.shikokukisen.com/instant/"
FARE_SOURCE = "https://www.shikokukisen.com/fare/"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str, fare: int, note: str) -> dict:
    return {
        "routeId": route_id,
        "operator": "四国汽船",
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
            "sourceUrls": [FARE_SOURCE],
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
        "operator": "四国汽船",
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
        "sourceUrl": TIME_SOURCE,
    }


def add_pairs(trips: list[dict], route_id: str, origin: str, destination: str, pairs: list[tuple[str, str]], vessel: str) -> None:
    for index, (dep, arr) in enumerate(pairs, 1):
        trips.append(trip(route_id, index, origin, destination, dep, arr, vessel))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    takamatsu_note = "Official 2026-02-01 adult one-way passenger fare 高松-直島（宮浦） ferry ¥680. V5 includes ferry sailings only because high-speed passenger boats use a different ¥1,590 fare. Excludes child fares, round trips, group fares, bicycles, vehicles, and discounts."
    uno_miyanoura_note = "Official 2026-02-01 adult one-way passenger fare 宇野-直島（宮浦） ferry/passenger boat ¥370. V5 excludes late-night premium sailings until per-sailing premium fare is modeled. Excludes child fares, round trips, group fares, bicycles, vehicles, and discounts."
    uno_honmura_note = "Official 2026-02-01 adult one-way passenger fare 宇野-直島（本村） ¥370. Excludes child fares, round trips, group fares, bicycles, vehicles, and discounts."
    routes = [
        route("shikoku_kisen_naoshima_052_out", "高松港", "宮浦港", 680, takamatsu_note),
        route("shikoku_kisen_naoshima_053_back", "宮浦港", "高松港", 680, takamatsu_note),
        route("shikoku_kisen_naoshima_054_out", "宮浦港", "宇野港", 370, uno_miyanoura_note),
        route("shikoku_kisen_naoshima_055_back", "宇野港", "宮浦港", 370, uno_miyanoura_note),
        route("shikoku_kisen_naoshima_056_out", "本村港", "宇野港", 370, uno_honmura_note),
        route("shikoku_kisen_naoshima_057_back", "宇野港", "本村港", 370, uno_honmura_note),
    ]
    trips: list[dict] = []
    add_pairs(trips, routes[0]["routeId"], "高松港", "宮浦港", [("08:12", "09:02"), ("10:14", "11:04"), ("12:40", "13:30"), ("15:35", "16:25"), ("18:05", "18:55")], "フェリー")
    add_pairs(trips, routes[1]["routeId"], "宮浦港", "高松港", [("07:00", "08:00"), ("09:07", "10:07"), ("11:30", "12:30"), ("14:20", "15:20"), ("17:00", "18:00")], "フェリー")
    add_pairs(trips, routes[3]["routeId"], "宇野港", "宮浦港", [
        ("06:10", "06:30"), ("06:30", "06:50"), ("07:20", "07:40"), ("08:22", "08:42"), ("09:22", "09:42"),
        ("11:00", "11:20"), ("12:15", "12:35"), ("13:30", "13:45"), ("14:25", "14:45"), ("15:30", "15:50"),
        ("16:30", "16:50"), ("17:05", "17:25"), ("18:53", "19:13"), ("20:25", "20:45"), ("22:30", "22:45"),
    ], "フェリー/旅客船")
    add_pairs(trips, routes[2]["routeId"], "宮浦港", "宇野港", [
        ("06:00", "06:20"), ("06:40", "07:00"), ("07:50", "08:10"), ("08:52", "09:12"), ("09:52", "10:12"),
        ("11:10", "11:30"), ("12:45", "13:05"), ("13:55", "14:10"), ("14:55", "15:15"), ("16:02", "16:22"),
        ("16:35", "16:55"), ("17:35", "17:55"), ("19:02", "19:22"), ("20:25", "20:45"), ("21:15", "21:30"),
    ], "フェリー/旅客船")
    add_pairs(trips, routes[5]["routeId"], "宇野港", "本村港", [("07:25", "07:45"), ("11:55", "12:15"), ("16:50", "17:10"), ("17:45", "18:05"), ("18:35", "18:55")], "旅客船")
    add_pairs(trips, routes[4]["routeId"], "本村港", "宇野港", [("06:45", "07:05"), ("07:55", "08:15"), ("13:00", "13:20"), ("17:20", "17:40"), ("18:10", "18:30")], "旅客船")
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "四国汽船",
        "operatorId": "shikoku_kisen",
        "retrievedAt": retrieved_at,
        "sourceUrls": [TIME_SOURCE, FARE_SOURCE],
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
