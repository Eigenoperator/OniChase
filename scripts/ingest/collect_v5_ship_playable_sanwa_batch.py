#!/usr/bin/env python3
"""Promote Sanwa Ferry official timetable and adult fare."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_sanwa_batch_official.json")
SOURCE = "https://ezax.co.jp/time/"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    return {
        "routeId": route_id,
        "operator": "三和商船",
        "routeName": f"{origin}・{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": 10,
        "routeClass": "regional_shortcut_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 540},
            "sourceUrls": [SOURCE],
            "notes": "Adult passenger fare from the official Sanwa Ferry timetable/fare page; excludes child fares, round trips, vehicles, bicycles, and discounts.",
        },
        "servicePatterns": [],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str) -> dict:
    dep_min = hm(dep)
    arr_min = dep_min + 30
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": "三和商船",
        "serviceNo": str(no),
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": 30,
        "calendar": {"type": "daily"},
        "sourceUrl": SOURCE,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes = [
        route("sanwa_kuranomoto_ushibuka_044_out", "蔵之元港", "牛深港"),
        route("sanwa_kuranomoto_ushibuka_045_back", "牛深港", "蔵之元港"),
    ]
    trips = []
    for index, dep in enumerate(["07:40", "09:00", "10:20", "11:40", "13:20", "14:40", "16:00", "17:20", "18:40"], 1):
        trips.append(trip(routes[0]["routeId"], index, "蔵之元港", "牛深港", dep))
    for index, dep in enumerate(["07:00", "08:20", "09:40", "11:00", "12:40", "14:00", "15:20", "16:40", "18:00"], 1):
        trips.append(trip(routes[1]["routeId"], index, "牛深港", "蔵之元港", dep))
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "三和商船",
        "operatorId": "sanwa_ferry",
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
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
