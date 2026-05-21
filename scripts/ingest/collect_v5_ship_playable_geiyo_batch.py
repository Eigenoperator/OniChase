#!/usr/bin/env python3
"""Promote Geiyo Kisen Imabari-Habu official timetable and fare."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_geiyo_batch_official.json")
SOURCE = "https://geiyokisen.com/"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    return {
        "routeId": route_id,
        "operator": "芸予汽船",
        "routeName": "今治・土生",
        "origin": origin,
        "destination": destination,
        "distanceKm": 36.8,
        "routeClass": "island_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 1780},
            "sourceUrls": [SOURCE],
            "notes": "Official rapid-boat adult one-way fare 今治-土生 ¥1,780, distance 36.8 km. Excludes child fares, round trips, commuter passes, bicycle/luggage limits, discounts, and special Obon/New Year calendar handling beyond weekday/weekend tables.",
        },
        "servicePatterns": [],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str, calendar: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    if arr_min < dep_min:
        arr_min += 24 * 60
    return {
        "tripId": f"{route_id}_{calendar}_{no:03d}",
        "routeId": route_id,
        "operator": "芸予汽船",
        "serviceNo": str(no),
        "vessel": None,
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": calendar},
        "sourceUrl": SOURCE,
    }


def add_pairs(trips: list[dict], route_id: str, origin: str, destination: str, pairs: list[tuple[str, str]], calendar: str, start_no: int = 1) -> None:
    for offset, (dep, arr) in enumerate(pairs):
        trips.append(trip(route_id, start_no + offset, origin, destination, dep, arr, calendar))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "mlit_map_193_039_芸予汽船_今治_土生_000_out"
    back_id = "mlit_map_193_039_芸予汽船_今治_土生_000_back"
    routes = [
        route(out_id, "今治港", "土生"),
        route(back_id, "土生", "今治港"),
    ]
    trips: list[dict] = []
    add_pairs(trips, out_id, "今治港", "土生", [("06:00", "07:10"), ("08:00", "09:20"), ("14:30", "15:50"), ("17:20", "18:35")], "weekday")
    add_pairs(trips, back_id, "土生", "今治港", [("06:22", "07:38"), ("12:20", "13:40"), ("16:00", "17:15"), ("18:40", "19:55")], "weekday")
    add_pairs(trips, out_id, "今治港", "土生", [("06:20", "07:40"), ("09:15", "10:35"), ("14:30", "15:50"), ("17:20", "18:35")], "weekend_holiday", 100)
    add_pairs(trips, back_id, "土生", "今治港", [("07:45", "09:05"), ("12:20", "13:40"), ("16:00", "17:15"), ("18:40", "19:55")], "weekend_holiday", 100)
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "芸予汽船",
        "operatorId": "geiyo_kisen",
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
