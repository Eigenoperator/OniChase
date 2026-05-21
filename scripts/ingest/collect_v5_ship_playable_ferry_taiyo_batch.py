#!/usr/bin/env python3
"""Promote verified Yakushima Town Ferry Taiyo II route batch."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_ferry_taiyo_batch_official.json")
SOURCE_URL = "https://www.town.yakushima.kagoshima.jp/ferry-taiyou/"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str, fare_yen: int) -> dict:
    note = (
        "Official Yakushima Town Ferry Taiyo II page lists the current timetable and adult ordinary passenger fares. "
        "The timetable has even-day and odd-day operation patterns; these are preserved as calendar labels for gameplay. "
        "Adult ordinary fares used here are 宮之浦-口永良部島 2,140 JPY, 宮之浦-島間 1,460 JPY, and 口永良部島-島間 3,580 JPY. "
        "Town resident discounts, child fares, disability/student/group discounts, cargo, vehicles, pets/livestock, sales-window rules, and disruption/dock notices are excluded."
    )
    return {
        "routeId": route_id,
        "routeGroupId": "mlit_map_193_066_屋久島町_宮之浦_永良部_島間",
        "operator": "屋久島町",
        "routeName": f"{origin}-{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "regional_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare_yen},
            "sourceUrls": [SOURCE_URL],
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": [SOURCE_URL],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str, calendar: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_{calendar}_{no:03d}",
        "routeId": route_id,
        "operator": "屋久島町",
        "serviceNo": str(no),
        "vessel": "フェリー太陽II",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": calendar},
        "sourceUrl": SOURCE_URL,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes = [
        route("mlit_map_193_066_屋久島町_宮之浦_永良部_島間_000_out", "宮之浦", "口永良部島港", 2140),
        route("mlit_map_193_066_屋久島町_宮之浦_永良部_島間_000_back", "口永良部島港", "宮之浦", 2140),
        route("mlit_map_193_066_屋久島町_宮之浦_永良部_島間_001_out", "口永良部島港", "島間港", 3580),
        route("mlit_map_193_066_屋久島町_宮之浦_永良部_島間_001_back", "島間港", "口永良部島港", 3580),
    ]
    trips = [
        trip(routes[0]["routeId"], 1, "宮之浦", "口永良部島港", "08:00", "09:40", "even_day"),
        trip(routes[1]["routeId"], 1, "口永良部島港", "宮之浦", "10:20", "12:00", "even_day"),
        trip(routes[2]["routeId"], 1, "口永良部島港", "島間港", "13:00", "14:05", "even_day"),
        trip(routes[3]["routeId"], 1, "島間港", "口永良部島港", "14:45", "15:50", "even_day"),
        trip(routes[0]["routeId"], 1, "宮之浦", "口永良部島港", "13:00", "14:40", "odd_day"),
        trip(routes[1]["routeId"], 1, "口永良部島港", "宮之浦", "15:20", "17:00", "odd_day"),
        trip(routes[2]["routeId"], 1, "口永良部島港", "島間港", "15:20", "17:00", "odd_day"),
        trip(routes[3]["routeId"], 1, "島間港", "口永良部島港", "09:00", "10:05", "odd_day"),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "屋久島町",
        "operatorId": "yakushima_ferry_taiyo",
        "retrievedAt": retrieved_at,
        "sourceUrls": [SOURCE_URL],
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 1,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "excludedDirections": ["宮之浦-島間 direct fare is listed but no direct same-trip endpoint leg is promoted; the service runs through 口永良部島."],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
