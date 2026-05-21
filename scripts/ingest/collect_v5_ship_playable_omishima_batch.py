#!/usr/bin/env python3
"""Promote Omishima Blue Line official ship timetable and fares."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_omishima_batch_official.json")
SOURCE = "https://omishima-bl.net/"


def hm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def hhmm(minutes: int) -> str:
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


def route(route_id: str, origin: str, destination: str, fare: int, distance_km: float) -> dict:
    return {
        "routeId": route_id,
        "operator": "大三島ブルーライン",
        "routeName": f"{origin}・{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": distance_km,
        "routeClass": "regional_shortcut_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": [SOURCE],
            "notes": "Adult passenger fare from the official Omishima Blue Line passenger fare table; excludes child fares, vehicle fares, and discounts.",
        },
        "servicePatterns": [],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str) -> dict:
    dep_min = hm_to_minutes(dep)
    arr_min = hm_to_minutes(arr)
    if arr_min < dep_min:
        arr_min += 24 * 60
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": "大三島ブルーライン",
        "serviceNo": str(no),
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": hhmm(arr_min),
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": SOURCE,
    }


def add_pairs(trips: list[dict], route_id: str, origin: str, destination: str, pairs: list[tuple[str, str]]) -> None:
    for index, (dep, arr) in enumerate(pairs, 1):
        trips.append(trip(route_id, index, origin, destination, dep, arr))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes = [
        route("mlit_map_193_038_大三島ブルーライン_今治_大崎上島_木江_大三島_宗方_岡村_000_out", "今治港", "木江港", 980, 25),
        route("mlit_map_193_038_大三島ブルーライン_今治_大崎上島_木江_大三島_宗方_岡村_000_back", "木江港", "今治港", 980, 25),
        route("mlit_map_193_038_大三島ブルーライン_今治_大崎上島_木江_大三島_宗方_岡村_001_out", "木江港", "宗方港", 270, 5),
        route("mlit_map_193_038_大三島ブルーライン_今治_大崎上島_木江_大三島_宗方_岡村_001_back", "宗方港", "木江港", 270, 5),
        route("mlit_map_193_038_大三島ブルーライン_今治_大崎上島_木江_大三島_宗方_岡村_002_out", "宗方港", "岡村港", 420, 9),
        route("mlit_map_193_038_大三島ブルーライン_今治_大崎上島_木江_大三島_宗方_岡村_002_back", "岡村港", "宗方港", 420, 9),
    ]
    trips: list[dict] = []
    add_pairs(trips, routes[0]["routeId"], "今治港", "木江港", [("06:30", "07:38"), ("13:05", "14:13")])
    add_pairs(trips, routes[1]["routeId"], "木江港", "今治港", [("10:50", "12:05"), ("18:45", "19:55")])
    add_pairs(trips, routes[2]["routeId"], "木江港", "宗方港", [("07:40", "07:53"), ("08:30", "08:43"), ("10:50", "11:05"), ("14:15", "14:28"), ("17:25", "17:38"), ("18:45", "19:00")])
    add_pairs(trips, routes[3]["routeId"], "宗方港", "木江港", [("07:25", "07:38"), ("08:10", "08:23"), ("10:35", "10:48"), ("14:00", "14:13"), ("16:30", "16:43"), ("18:30", "18:43")])
    add_pairs(trips, routes[4]["routeId"], "宗方港", "岡村港", [("08:50", "09:13"), ("09:40", "10:03"), ("14:35", "14:58"), ("15:25", "15:48"), ("17:40", "18:03")])
    add_pairs(trips, routes[5]["routeId"], "岡村港", "宗方港", [("09:15", "09:38"), ("10:05", "10:28"), ("15:00", "15:23"), ("15:50", "16:13"), ("18:05", "18:28")])

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "大三島ブルーライン",
        "operatorId": "omishima_blue_line",
        "retrievedAt": retrieved_at,
        "sourceUrls": [SOURCE],
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
