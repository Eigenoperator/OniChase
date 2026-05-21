#!/usr/bin/env python3
"""Promote verified Shiogama city Urato island ferry route."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_urato_batch_official.json")
OPERATOR = "塩竈市"
SOURCE_URL = "https://urato-island.jp/wp-content/uploads/2025/10/料金・時刻表.pdf"

DOWN_STOPS = ["塩竈港", "桂島港", "野々島港", "石浜港", "寒風沢港", "朴島港"]
UP_STOPS = list(reversed(DOWN_STOPS))
DOWN_ROWS = [
    ["05:30", "05:48", "05:54", "05:57", "06:05", "06:13"],
    ["07:20", "07:38", "07:45", "07:49", "07:57", "08:05"],
    ["09:30", "09:48", "09:55", "09:59", "10:07", "10:15"],
    ["11:30", "11:48", "11:55", "11:59", "12:07", "12:15"],
    ["13:30", "13:48", "13:55", "13:59", "14:07", "14:15"],
    ["15:45", "16:03", "16:10", "16:14", "16:22", "16:30"],
    ["18:15", "18:32", "18:37", "18:40", "18:47", "18:55"],
]
UP_ROWS = [
    ["06:15", "06:23", "06:31", "06:34", "06:40", "06:58"],
    ["08:10", "08:18", "08:26", "08:30", "08:37", "08:55"],
    ["10:25", "10:33", "10:41", "10:45", "10:52", "11:10"],
    ["12:25", "12:33", "12:41", "12:45", "12:52", "13:10"],
    ["14:25", "14:33", "14:41", "14:45", "14:52", "15:10"],
    ["16:40", "16:48", "16:56", "17:00", "17:07", "17:25"],
]
ROUTE_IDS = {
    ("塩竈港", "桂島港"): "shiogama_urato_000_out",
    ("桂島港", "塩竈港"): "shiogama_urato_001_back",
    ("桂島港", "野々島港"): "shiogama_urato_002_out",
    ("野々島港", "桂島港"): "shiogama_urato_003_back",
    ("野々島港", "石浜港"): "shiogama_urato_004_out",
    ("石浜港", "野々島港"): "shiogama_urato_005_back",
    ("石浜港", "寒風沢港"): "shiogama_urato_006_out",
    ("寒風沢港", "石浜港"): "shiogama_urato_007_back",
    ("寒風沢港", "朴島港"): "shiogama_urato_008_out",
    ("朴島港", "寒風沢港"): "shiogama_urato_009_back",
}
FARES = {
    ("塩竈港", "桂島港"): 520,
    ("桂島港", "野々島港"): 110,
    ("野々島港", "石浜港"): 110,
    ("石浜港", "寒風沢港"): 110,
    ("寒風沢港", "朴島港"): 110,
}


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def fare_for(origin: str, destination: str) -> int:
    return FARES.get((origin, destination)) or FARES[(destination, origin)]


def route(origin: str, destination: str) -> dict:
    fare = fare_for(origin, destination)
    note = (
        "Official Shiogama Urato PDF lists the one-way adult fare matrix and the 2025-10 timetable. "
        f"Adult ordinary fare used for {origin}-{destination} is {fare} JPY. "
        "Only adjacent physical segments are promoted here, matching the current V5 map route decomposition. "
        "Child fares, temporary/special sailings, island-internal free tosen, holiday exceptions, and the partial Tuesday/Friday-only last return pattern are excluded."
    )
    return {
        "routeId": ROUTE_IDS[(origin, destination)],
        "routeGroupId": "shiogama_urato",
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
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": [SOURCE_URL],
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": [SOURCE_URL],
    }


def trip(origin: str, destination: str, service_no: int, dep: str, arr: str, calendar: str) -> dict:
    route_id = ROUTE_IDS[(origin, destination)]
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_{calendar}_{service_no:03d}",
        "routeId": route_id,
        "operator": OPERATOR,
        "serviceNo": str(service_no),
        "vessel": "塩竈市営汽船",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": calendar},
        "sourceUrl": SOURCE_URL,
    }


def add_rows(trips: list[dict], stops: list[str], rows: list[list[str]], first_calendar: str) -> None:
    for service_no, row in enumerate(rows, start=1):
        calendar = first_calendar if service_no == 1 else "daily"
        for i in range(len(stops) - 1):
            trips.append(trip(stops[i], stops[i + 1], service_no, row[i], row[i + 1], calendar))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    route_pairs = list(ROUTE_IDS)
    routes = [route(origin, destination) for origin, destination in route_pairs]
    trips: list[dict] = []
    add_rows(trips, DOWN_STOPS, DOWN_ROWS, "monday_to_saturday")
    add_rows(trips, UP_STOPS, UP_ROWS, "monday_to_saturday")
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": OPERATOR,
        "operatorId": "shiogama_urato",
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
            "excludedDirections": ["Tuesday/Friday-only final return pattern is not promoted because the PDF row includes skipped stops and V5 service date is Thursday."],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
