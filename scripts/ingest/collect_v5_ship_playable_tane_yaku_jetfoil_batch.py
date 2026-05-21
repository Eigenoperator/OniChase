#!/usr/bin/env python3
"""Promote verified Tane-Yaku Jetfoil current summer timetable legs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_tane_yaku_jetfoil_batch_official.json")
SOURCE_URL = "https://www.tykousoku.jp/fare_time/"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    note = (
        "Official Toppy & Rocket fare/time page lists seasonal timetables. "
        "V5 current service date 2026-05-21 falls in the 2026-04-01 to 2026-06-30 summer timetable. "
        "Only the 西之表港-宮之浦港 summer services explicitly marked for 宮之浦 are promoted; 安房 services are excluded. "
        "The same official page lists adult one-way 種子島-屋久島 fare as 6,200 JPY from 2026-05-11 onward, including fuel adjustment. "
        "Discount tickets, islander fares, child fares, web discounts, cancelled special dates, and reservation/boarding rules are excluded."
    )
    return {
        "routeId": route_id,
        "routeGroupId": "mlit_map_193_062_種子屋久高速船_鹿児島_種子_屋久",
        "operator": "種子屋久高速船",
        "routeName": f"{origin}-{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "intercity_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 6200},
            "sourceUrls": [SOURCE_URL],
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": [SOURCE_URL],
    }


def trip(route_id: str, service_no: str, origin: str, destination: str, dep: str, arr: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_summer_20260401_20260630_{service_no}",
        "routeId": route_id,
        "operator": "種子屋久高速船",
        "serviceNo": service_no,
        "vessel": "トッピー/ロケット",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": SOURCE_URL,
        "notes": "Current V5 summer timetable 2026-04-01 to 2026-06-30.",
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "mlit_map_193_062_種子屋久高速船_鹿児島_種子_屋久_001_out"
    back_id = "mlit_map_193_062_種子屋久高速船_鹿児島_種子_屋久_001_back"
    routes = [
        route(out_id, "西之表港", "宮之浦港"),
        route(back_id, "宮之浦港", "西之表港"),
    ]
    trips = [
        trip(out_id, "111", "西之表港", "宮之浦港", "09:30", "10:20"),
        trip(out_id, "127", "西之表港", "宮之浦港", "14:45", "15:35"),
        trip(back_id, "112", "宮之浦港", "西之表港", "10:00", "10:50"),
        trip(back_id, "117", "宮之浦港", "西之表港", "15:45", "16:30"),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "種子屋久高速船",
        "operatorId": "tane_yaku_jetfoil",
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
                "安房港 services are excluded from this 西之表-宮之浦 route.",
                "Other seasonal timetable blocks are excluded from this current V5 service-date batch.",
            ],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
