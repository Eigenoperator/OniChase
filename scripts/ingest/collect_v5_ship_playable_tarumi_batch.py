#!/usr/bin/env python3
"""Promote Kagoshima Kotsu Tarumi Ferry official timetable and fare."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_tarumi_batch_official.json")
TIME_SOURCE = "https://www.iwasaki-corp.com/kagoshima_kotsu/tarumizuferry/t-timetable/"
FARE_SOURCE = "https://www.iwasaki-corp.com/kagoshima_kotsu/tarumizuferry/t-fare/"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    return {
        "routeId": route_id,
        "operator": "鹿児島交通",
        "routeName": "鴨池・垂水",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "short_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 550},
            "sourceUrls": [FARE_SOURCE],
            "notes": "Official 2024-08-01 adult one-way passenger fare ¥550. Excludes child fares, commuter tickets, coupon books, vehicle/bicycle fares, group/disabled discounts, and date-limited dock-dialect exceptions.",
        },
        "servicePatterns": [],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, calendar: str) -> dict:
    dep_min = hm(dep)
    arr_min = dep_min + 40
    return {
        "tripId": f"{route_id}_{calendar}_{no:03d}",
        "routeId": route_id,
        "operator": "鹿児島交通",
        "serviceNo": str(no),
        "vessel": None,
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": 40,
        "calendar": {"type": calendar},
        "sourceUrl": TIME_SOURCE,
    }


def add_departures(trips: list[dict], route_id: str, origin: str, destination: str, departures: list[str], calendar: str, start_no: int = 1) -> None:
    for offset, dep in enumerate(departures):
        trips.append(trip(route_id, start_no + offset, origin, destination, dep, calendar))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "tarumi_kamoike_tarumi_058_out"
    back_id = "tarumi_kamoike_tarumi_059_back"
    routes = [
        route(out_id, "鴨池港", "垂水港"),
        route(back_id, "垂水港", "鴨池港"),
    ]
    weekday = ["06:00", "06:50", "07:40", "08:30", "09:20", "10:10", "11:00", "11:50", "12:40", "13:30", "14:20", "15:10", "16:00", "16:50", "17:40", "18:30", "19:20", "20:10", "21:00"]
    weekend_kamoike = ["06:00", "06:50", "07:20", "07:55", "08:30", "09:00", "09:35", "10:10", "10:40", "11:15", "11:50", "12:20", "12:55", "13:30", "14:00", "14:35", "15:10", "15:40", "16:15", "16:50", "17:20", "17:55", "18:30", "19:00", "20:00", "21:00"]
    weekend_tarumi = ["06:00", "06:50", "07:40", "08:10", "08:45", "09:20", "09:50", "10:25", "11:00", "11:30", "12:05", "12:40", "13:10", "13:45", "14:20", "14:50", "15:25", "16:00", "16:30", "17:05", "17:40", "18:10", "18:45", "19:20", "20:10", "21:00"]
    trips: list[dict] = []
    add_departures(trips, out_id, "鴨池港", "垂水港", weekday, "weekday")
    add_departures(trips, back_id, "垂水港", "鴨池港", weekday, "weekday")
    add_departures(trips, out_id, "鴨池港", "垂水港", weekend_kamoike, "weekend_holiday", 100)
    add_departures(trips, back_id, "垂水港", "鴨池港", weekend_tarumi, "weekend_holiday", 100)
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "鹿児島交通",
        "operatorId": "kagoshima_kotsu_tarumi_ferry",
        "retrievedAt": retrieved_at,
        "sourceUrls": [TIME_SOURCE, FARE_SOURCE],
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
