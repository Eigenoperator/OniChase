#!/usr/bin/env python3
"""Promote verified Orita Ferry Yakushima 2 route batch."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_orita_yakushima_batch_official.json")
SOURCE_URL = "https://ferryyakusima2.com/timetable"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    note = (
        "Official Ferry Yakushima 2 timetable/fare page lists 鹿児島発 08:30 宮之浦着 12:30 and "
        "宮之浦発 13:30 鹿児島着 17:40. The same page lists adult one-way 2nd-class fare as 6,500 JPY, "
        "including fuel adjustment. First-class fare, vehicles, baggage, pets, discounts, islander fares, "
        "payment-method notes, and disruption notices are excluded."
    )
    return {
        "routeId": route_id,
        "routeGroupId": "orita_kagoshima_yakushima",
        "operator": "折田汽船",
        "routeName": f"{origin}-{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "intercity_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 6500},
            "sourceUrls": [SOURCE_URL],
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": [SOURCE_URL],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_daily_{no:03d}",
        "routeId": route_id,
        "operator": "折田汽船",
        "serviceNo": str(no),
        "vessel": "フェリー屋久島2",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": SOURCE_URL,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "orita_kagoshima_yakushima_072_out"
    back_id = "orita_kagoshima_yakushima_073_back"
    routes = [
        route(out_id, "鹿児島港", "宮之浦港"),
        route(back_id, "宮之浦港", "鹿児島港"),
    ]
    trips = [
        trip(out_id, 1, "鹿児島港", "宮之浦港", "08:30", "12:30"),
        trip(back_id, 1, "宮之浦港", "鹿児島港", "13:30", "17:40"),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "折田汽船",
        "operatorId": "orita_yakushima",
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
            "excludedDirections": [],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
