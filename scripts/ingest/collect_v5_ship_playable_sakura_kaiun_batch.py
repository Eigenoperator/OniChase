#!/usr/bin/env python3
"""Promote Sakura Kaiun official timetable and adult fare."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_sakura_kaiun_batch_official.json")
SOURCE = "https://sakurakaiun.jimdofree.com/"


def hm_to_minutes(value: str) -> int:
    hour, minute = value.replace("：", ":").split(":")
    return int(hour) * 60 + int(minute)


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, calendar: str = "daily") -> dict:
    dep_min = hm_to_minutes(dep)
    arr_min = dep_min + 12
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": "さくら海運",
        "serviceNo": str(no),
        "origin": origin,
        "destination": destination,
        "departure": f"{dep_min // 60:02d}:{dep_min % 60:02d}",
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": 12,
        "calendar": {"type": calendar},
        "sourceUrl": SOURCE,
    }


def route(route_id: str, origin: str, destination: str) -> dict:
    return {
        "routeId": route_id,
        "operator": "さくら海運",
        "routeName": f"{origin}・{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "urban_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 380},
            "sourceUrls": [SOURCE],
            "notes": "Adult passenger fare from the official Sakura Kaiun fare table; excludes child fares, round trips, vehicles, bicycles, and baggage.",
        },
        "servicePatterns": [],
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes = [
        route("mlit_map_193_010_さくら海運_呉ポートピアパーク_切串_000_out", "天応港", "切串"),
        route("mlit_map_193_010_さくら海運_呉ポートピアパーク_切串_000_back", "切串", "天応港"),
    ]
    trips = []
    for index, dep in enumerate(["05:45", "06:20", "06:55", "07:30", "08:05", "09:00", "10:00", "11:00", "12:00", "13:00", "14:15", "15:30", "16:30", "17:05", "17:55", "18:30", "19:10", "20:25"], 1):
        trips.append(trip(routes[0]["routeId"], index, "天応港", "切串", dep, "weekday" if dep == "05:45" else "daily"))
    for index, dep in enumerate(["06:02", "06:37", "07:12", "07:47", "08:22", "09:17", "10:17", "11:17", "12:17", "13:17", "14:32", "15:47", "16:47", "17:22", "18:12", "18:47", "19:27", "20:42"], 1):
        trips.append(trip(routes[1]["routeId"], index, "切串", "天応港", dep, "weekday" if dep == "06:02" else "daily"))
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "さくら海運",
        "operatorId": "sakura_kaiun",
        "retrievedAt": retrieved_at,
        "sourceUrls": [SOURCE],
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 1,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "sourceNote": "Official page marks the first early service in each direction as weekday-only; those trips use weekday calendar.",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
