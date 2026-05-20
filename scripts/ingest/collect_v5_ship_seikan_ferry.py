#!/usr/bin/env python3
"""Collect the official Seikan Ferry Aomori-Hakodate ship source data.

The current collector is intentionally explicit: the official page publishes a
small stable table, so storing the normalized rows keeps the source auditable.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_seikan_ferry_official.json")
SCHEDULE_URL = "https://www.seikan-ferry.co.jp/schedule/"
FARE_URL = "https://www.seikan-ferry.co.jp/fare/"

PORTS = {
    "青森フェリーターミナル": {
        "lat": 40.8393,
        "lon": 140.7362,
        "coordinateSource": "manual_geocode:青森フェリーターミナル",
        "city": "青森",
    },
    "函館フェリーターミナル": {
        "lat": 41.8065,
        "lon": 140.7169,
        "coordinateSource": "manual_geocode:函館フェリーターミナル",
        "city": "函館",
    },
}


def hm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def make_trip(direction: str, service_no: str, departure: str, arrival: str, vessel: str) -> dict:
    if direction == "aomori_to_hakodate":
        origin = "青森フェリーターミナル"
        destination = "函館フェリーターミナル"
        route_id = "seikan_ferry_aomori_hakodate"
    else:
        origin = "函館フェリーターミナル"
        destination = "青森フェリーターミナル"
        route_id = "seikan_ferry_hakodate_aomori"
    departure_minute = hm_to_minutes(departure)
    arrival_minute = hm_to_minutes(arrival)
    if arrival_minute <= departure_minute:
        arrival_minute += 24 * 60
    return {
        "tripId": f"seikan_ferry_{service_no}",
        "routeId": route_id,
        "operator": "青函フェリー",
        "serviceNo": service_no,
        "vessel": vessel,
        "origin": origin,
        "destination": destination,
        "departure": departure,
        "arrival": arrival,
        "departureMinute": departure_minute,
        "arrivalMinute": arrival_minute,
        "durationMinutes": arrival_minute - departure_minute,
        "calendar": {"type": "daily", "sourceNote": "Official page publishes a daily timetable without weekday exceptions."},
        "sourceUrl": SCHEDULE_URL,
    }


TRIPS = [
    make_trip("aomori_to_hakodate", "1", "02:00", "05:50", "はやぶさⅡ"),
    make_trip("aomori_to_hakodate", "3", "04:30", "08:30", "あさかぜ21"),
    make_trip("aomori_to_hakodate", "5", "08:10", "12:10", "はやぶさⅢ"),
    make_trip("aomori_to_hakodate", "7", "11:35", "15:25", "はやぶさ"),
    make_trip("aomori_to_hakodate", "9", "14:35", "18:25", "はやぶさⅡ"),
    make_trip("aomori_to_hakodate", "11", "18:00", "21:50", "あさかぜ21"),
    make_trip("aomori_to_hakodate", "13", "20:30", "00:20", "はやぶさⅢ"),
    make_trip("aomori_to_hakodate", "15", "23:30", "03:20", "はやぶさ"),
    make_trip("hakodate_to_aomori", "2", "02:00", "05:50", "はやぶさⅢ"),
    make_trip("hakodate_to_aomori", "4", "04:30", "08:30", "はやぶさ"),
    make_trip("hakodate_to_aomori", "6", "08:10", "12:10", "はやぶさⅡ"),
    make_trip("hakodate_to_aomori", "8", "11:35", "15:25", "あさかぜ21"),
    make_trip("hakodate_to_aomori", "10", "14:35", "18:25", "はやぶさⅢ"),
    make_trip("hakodate_to_aomori", "12", "18:00", "21:50", "はやぶさ"),
    make_trip("hakodate_to_aomori", "14", "20:30", "00:20", "はやぶさⅡ"),
    make_trip("hakodate_to_aomori", "16", "23:30", "03:20", "あさかぜ21"),
]


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes = [
        {
            "routeId": "seikan_ferry_aomori_hakodate",
            "operator": "青函フェリー",
            "routeName": "青森・函館",
            "origin": "青森フェリーターミナル",
            "destination": "函館フェリーターミナル",
            "distanceKm": 113,
            "routeClass": "short_intercity_ferry",
            "revealPolicy": "no_reveal",
            "fare": {
                "currency": "JPY",
                "adultPassengerFare": {
                    "normalSeason": {"months": [10, 11, 12, 1, 2, 3, 4, 5], "amount": 2700},
                    "peakSeason": {"months": [6, 7, 8, 9], "amount": 3200},
                },
                "sourceUrl": FARE_URL,
                "notes": "2-season adult passenger fare, excluding discounts, state room, vehicle, bicycle, motorcycle, and fuel adjustment for large vehicles.",
            },
        },
        {
            "routeId": "seikan_ferry_hakodate_aomori",
            "operator": "青函フェリー",
            "routeName": "函館・青森",
            "origin": "函館フェリーターミナル",
            "destination": "青森フェリーターミナル",
            "distanceKm": 113,
            "routeClass": "short_intercity_ferry",
            "revealPolicy": "no_reveal",
            "fare": {
                "currency": "JPY",
                "adultPassengerFare": {
                    "normalSeason": {"months": [10, 11, 12, 1, 2, 3, 4, 5], "amount": 2700},
                    "peakSeason": {"months": [6, 7, 8, 9], "amount": 3200},
                },
                "sourceUrl": FARE_URL,
                "notes": "2-season adult passenger fare, excluding discounts, state room, vehicle, bicycle, motorcycle, and fuel adjustment for large vehicles.",
            },
        },
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "青函フェリー",
        "operatorId": "seikan_ferry",
        "retrievedAt": retrieved_at,
        "sourceUrls": [SCHEDULE_URL, FARE_URL],
        "ports": PORTS,
        "routes": routes,
        "trips": TRIPS,
        "summary": {
            "routeCount": len(routes),
            "tripCount": len(TRIPS),
            "portCount": len(PORTS),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} trips={len(TRIPS)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
