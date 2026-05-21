#!/usr/bin/env python3
"""Promote verified Sakito Shosen Tomozumi-Sasebo route."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_sakito_batch_official.json")
SOURCE_URL = "https://www.saryokyo.com/member/member-02.html"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    return {
        "routeId": route_id,
        "routeGroupId": "mlit_map_193_051_崎戸商船_友住_佐世保",
        "operator": "崎戸商船",
        "routeName": "友住-佐世保",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "regional_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 3220},
            "sourceUrls": [SOURCE_URL],
            "notes": (
                "Sasebo Passenger Boat Association page for Sakito Shosen lists the adult fare table revised 2025-10-01; "
                "友住-佐世保 is 3,220 JPY. Summer timetable is used for the current v5 May gameplay date. "
                "Intermediate-port playable stops, winter timetable, vehicle fares, discounts, inspection dry-dock notices, "
                "and disruption status are excluded."
            ),
        },
        "servicePatterns": [],
        "sourceUrls": [SOURCE_URL],
    }


def trip(route_id: str, origin: str, destination: str, dep: str, arr: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_summer_daily_001",
        "routeId": route_id,
        "operator": "崎戸商船",
        "serviceNo": "1",
        "vessel": "みしま",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": SOURCE_URL,
        "notes": "Official summer timetable, April 1 through September 30. Intermediate calls: 平島, 江島, 崎戸.",
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "mlit_map_193_051_崎戸商船_友住_佐世保_000_out"
    back_id = "mlit_map_193_051_崎戸商船_友住_佐世保_000_back"
    routes = [
        route(out_id, "友住", "佐世保港"),
        route(back_id, "佐世保港", "友住"),
    ]
    trips = [
        trip(out_id, "友住", "佐世保港", "07:00", "10:30"),
        trip(back_id, "佐世保港", "友住", "14:00", "17:30"),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "崎戸商船",
        "operatorId": "sakito_shosen",
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
            "excludedDirections": [
                "Intermediate 平島/江島/崎戸 legs are deferred until the route model supports explicit intermediate port stop times for this route group.",
                "Winter timetable is documented but excluded from the current May gameplay calendar until date-range calendars are supported.",
            ],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
