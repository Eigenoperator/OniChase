#!/usr/bin/env python3
"""Promote verified Kamimura Kisen Ujina-Kirikushi route."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_kamimura_batch_official.json")
OPERATOR = "上村汽船"
TIMETABLE_URL = "https://kamimurakisen.com/jikokuhyou.html"
FARE_URL = "https://kamimurakisen.com/ryoukinhyou.html"

KIRIKUSHI_DEPS = [
    "06:40", "07:10", "07:40", "08:10", "08:40", "09:20", "10:00", "10:40", "11:20", "12:00", "13:30",
    "14:10", "14:50", "15:30", "16:10", "16:50", "17:30", "18:05", "18:40", "19:20", "20:10", "20:55",
]
UJINA_DEPS = [
    "07:10", "07:40", "08:10", "08:40", "09:20", "10:00", "10:40", "11:20", "12:00", "13:30", "14:10",
    "14:50", "15:30", "16:10", "16:50", "17:30", "18:05", "18:40", "19:20", "20:00", "20:45", "21:30",
]


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def add_minutes(value: str, minutes: int) -> str:
    total = hm(value) + minutes
    return f"{total // 60:02d}:{total % 60:02d}"


def route(route_id: str, origin: str, destination: str) -> dict:
    note = (
        "Official Kamimura Kisen timetable image lists Ujina-Kirikushi departures and states one-way travel time is about 30 minutes. "
        "Official fare image lists adult passenger fare as 470 JPY. "
        "The final marked departures are not operated on Sundays/holidays, so they are emitted as Monday-Saturday for gameplay. "
        "Child fares, coupon tickets, commuter/student passes, vehicles, motorcycles, bicycles, group/disability discounts, charter/cruise products, and holiday calendars are excluded."
    )
    return {
        "routeId": route_id,
        "routeGroupId": "kamimura_kirikushi",
        "operator": OPERATOR,
        "routeName": f"{origin}-{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "regional_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 470},
            "sourceUrls": [TIMETABLE_URL, FARE_URL],
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": [TIMETABLE_URL, FARE_URL],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, calendar: str) -> dict:
    dep_min = hm(dep)
    arr = add_minutes(dep, 30)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_{calendar}_{no:03d}",
        "routeId": route_id,
        "operator": OPERATOR,
        "serviceNo": str(no),
        "vessel": "上村汽船フェリー",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": calendar},
        "sourceUrl": TIMETABLE_URL,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "kamimura_kirikushi_038_out"
    back_id = "kamimura_kirikushi_039_back"
    routes = [
        route(out_id, "広島港宇品", "切串港"),
        route(back_id, "切串港", "広島港宇品"),
    ]
    trips = []
    for no, dep in enumerate(UJINA_DEPS, start=1):
        trips.append(trip(out_id, no, "広島港宇品", "切串港", dep, "monday_to_saturday" if no == len(UJINA_DEPS) else "daily"))
    for no, dep in enumerate(KIRIKUSHI_DEPS, start=1):
        trips.append(trip(back_id, no, "切串港", "広島港宇品", dep, "monday_to_saturday" if no == len(KIRIKUSHI_DEPS) else "daily"))
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": OPERATOR,
        "operatorId": "kamimura_kisen",
        "retrievedAt": retrieved_at,
        "sourceUrls": [TIMETABLE_URL, FARE_URL],
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
