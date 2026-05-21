#!/usr/bin/env python3
"""Promote current official Kume Line temporary timetable and fares."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_kume_batch_official.json")
TIME_SOURCE = "http://www.kumeline.com/"
FARE_SOURCE = "http://www.kumeline.com/fare_ticket/"


def hm_to_minutes(value: str) -> int:
    hour, minute = value.replace("：", ":").split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, route_name: str, origin: str, destination: str, fare: int) -> dict:
    return {
        "routeId": route_id,
        "operator": "久米商船",
        "routeName": route_name,
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "island_public_ferry",
        "revealPolicy": "long_distance_or_overnight_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": [FARE_SOURCE],
            "notes": "Adult passenger fare from the official Kume Line fare table; excludes child fares, round trips, baggage, vehicles, and discounts.",
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
        "operator": "久米商船",
        "serviceNo": str(no),
        "vessel": "フェリー海邦",
        "origin": origin,
        "destination": destination,
        "departure": f"{dep_min // 60:02d}:{dep_min % 60:02d}",
        "arrival": f"{(arr_min // 60) % 24:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": TIME_SOURCE,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes = [
        route("kume_naha_tonaki_kume_074_out", "那覇・渡名喜", "那覇泊港", "渡名喜港", 2750),
        route("kume_naha_tonaki_kume_075_back", "渡名喜・那覇", "渡名喜港", "那覇泊港", 2750),
        route("kume_naha_tonaki_kume_076_out", "渡名喜・兼城", "渡名喜港", "兼城港", 1160),
        route("kume_naha_tonaki_kume_077_back", "兼城・渡名喜", "兼城港", "渡名喜港", 1160),
    ]
    trips = [
        trip(routes[0]["routeId"], 1, "那覇泊港", "渡名喜港", "09:00", "10:55"),
        trip(routes[2]["routeId"], 1, "渡名喜港", "兼城港", "11:10", "12:30"),
        trip(routes[3]["routeId"], 1, "兼城港", "渡名喜港", "14:00", "15:20"),
        trip(routes[1]["routeId"], 1, "渡名喜港", "那覇泊港", "15:35", "17:30"),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "久米商船",
        "operatorId": "kume_line",
        "retrievedAt": retrieved_at,
        "sourceUrls": [TIME_SOURCE, FARE_SOURCE],
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 2,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "sourceNote": "Official page states the 2026-05-19 to 2026-06-18 one-vessel temporary operation via Tonaki; this covers the current V5 service date.",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
