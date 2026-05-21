#!/usr/bin/env python3
"""Promote verified Teshima Ferry current-season weekday route batch."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_teshima_ferry_batch_official.json")

SCHEDULE_URL = "https://t-ferry.com/schedule/"
FARE_URL = "https://t-ferry.com/price/"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    note = (
        "Official Teshima Ferry schedule page lists the 3/20-11/30 current-season 水・木・金 timetable. "
        "V5 current service date is 2026-05-21 Thursday, so only that current-season Wednesday/Thursday/Friday pattern is promoted. "
        "Official fare page lists adult one-way 高松港-豊島家浦港 fare as 1,450 JPY. "
        "Other seasonal/day patterns, holiday handling, temporary disruptions, child fares, group discounts, and cash-only notes are excluded."
    )
    return {
        "routeId": route_id,
        "routeGroupId": "mlit_map_193_026_豊島フェリー_家浦_高松",
        "operator": "豊島フェリー",
        "routeName": f"{origin}-{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "regional_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 1450},
            "sourceUrls": [SCHEDULE_URL, FARE_URL],
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": [SCHEDULE_URL, FARE_URL],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str, notes: str = "") -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_wednesday_thursday_friday_{no:03d}",
        "routeId": route_id,
        "operator": "豊島フェリー",
        "serviceNo": str(no),
        "vessel": "旅客船",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "wednesday_thursday_friday"},
        "sourceUrl": SCHEDULE_URL,
        "notes": notes,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "mlit_map_193_026_豊島フェリー_家浦_高松_000_back"
    back_id = "mlit_map_193_026_豊島フェリー_家浦_高松_000_out"
    routes = [
        route(out_id, "高松港", "家浦"),
        route(back_id, "家浦", "高松港"),
    ]
    trips: list[dict] = []
    for no, (dep, arr, notes) in enumerate([
        ("07:41", "08:16", ""),
        ("09:02", "09:37", ""),
        ("10:45", "11:35", "Official timetable marks this sailing as via 直島本村港; intermediate stop is not yet modeled in V5 ship legs."),
        ("16:25", "17:00", ""),
        ("18:03", "18:38", ""),
    ], 1):
        trips.append(trip(out_id, no, "高松港", "家浦", dep, arr, notes))
    for no, (dep, arr) in enumerate([
        ("07:00", "07:35"),
        ("08:20", "08:55"),
        ("09:40", "10:15"),
        ("15:10", "15:45"),
        ("17:20", "17:55"),
    ], 1):
        trips.append(trip(back_id, no, "家浦", "高松港", dep, arr))
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "豊島フェリー",
        "operatorId": "teshima_ferry",
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
            "excludedDirections": [
                "月・土・日・祝 pattern not promoted in this V5 current-date batch.",
                "火曜日 reduced pattern not promoted in this V5 current-date batch.",
                "12/1-3/19 winter patterns not promoted in this V5 current-date batch.",
                "高松-豊島唐櫃 seasonal event-only sailing not promoted.",
            ],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
