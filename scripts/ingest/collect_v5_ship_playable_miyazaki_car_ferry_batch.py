#!/usr/bin/env python3
"""Promote verified Miyazaki Car Ferry current-period route batch."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_miyazaki_car_ferry_batch_official.json")
SCHEDULE_URL = "https://www.miyazakicarferry.com/schedule/"
FARE_URL = "https://www.miyazakicarferry.com/fare/tel-reservation/"


def hm(value: str) -> int:
    next_day = value.startswith("翌")
    value = value.replace("翌", "")
    hour, minute = value.split(":")
    total = int(hour) * 60 + int(minute)
    if next_day:
        total += 24 * 60
    return total


def route(route_id: str, origin: str, destination: str) -> dict:
    note = (
        "Official Miyazaki Car Ferry schedule page lists Miyazaki->Kobe daily 19:10-翌07:30 and "
        "Kobe->Miyazaki Monday-Saturday 19:10-翌08:40, with a separate Sunday departure. "
        "V5 current service date 2026-05-21 is Thursday, so the Monday-Saturday Kobe->Miyazaki pattern is promoted. "
        "Official telephone-reservation fare page lists 2026-04-01 to 2026-06-30 normal-period adult Tourist fare as 13,100 JPY, including fuel adjustment and tax. "
        "Premium rooms, vehicles, motorcycles, web fares, busy-period fares, discounts, onboard charges, and disruption notices are excluded."
    )
    return {
        "routeId": route_id,
        "routeGroupId": "miyazaki_kobe_miyazaki",
        "operator": "宮崎カーフェリー",
        "routeName": f"{origin}-{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "long_distance_public_ferry",
        "revealPolicy": "long_distance_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 13100},
            "sourceUrls": [SCHEDULE_URL, FARE_URL],
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": [SCHEDULE_URL, FARE_URL],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str, calendar: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_{calendar}_{no:03d}",
        "routeId": route_id,
        "operator": "宮崎カーフェリー",
        "serviceNo": str(no),
        "vessel": "フェリーたかちほ/ろっこう",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": calendar},
        "sourceUrl": SCHEDULE_URL,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "miyazaki_kobe_miyazaki_036_out"
    back_id = "miyazaki_kobe_miyazaki_037_back"
    routes = [
        route(out_id, "神戸港", "宮崎港"),
        route(back_id, "宮崎港", "神戸港"),
    ]
    trips = [
        trip(out_id, 1, "神戸港", "宮崎港", "19:10", "翌08:40", "monday_to_saturday"),
        trip(back_id, 1, "宮崎港", "神戸港", "19:10", "翌07:30", "daily"),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "宮崎カーフェリー",
        "operatorId": "miyazaki_car_ferry",
        "retrievedAt": retrieved_at,
        "sourceUrls": [SCHEDULE_URL, FARE_URL],
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 1,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "excludedDirections": ["神戸港->宮崎港 Sunday 18:00 departure is not promoted in this current Thursday V5 batch."],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
