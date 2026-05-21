#!/usr/bin/env python3
"""Promote verified Suo-Oshima Matsuyama Ferry Ihota-Mitsuhama legs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_suo_oshima_batch_official.json")
TIME_URL = "https://www.boyoferry.co.jp/c_timetable.html"
FARE_URL = "https://www.boyoferry.co.jp/c_fare2.html"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    note = (
        "Official Boyo/Suo-Oshima Matsuyama Ferry timetable lists the 2025-03-01 normal timetable with Ihota calls. "
        "The operator page notes the Ihota call time is the departure time and arrival is 5 minutes before departure. "
        "For V5 gameplay, Ihota->Mitsuhama uses the listed Ihota departure and Mitsuhama arrival; "
        "Mitsuhama->Ihota uses the listed Mitsuhama departure and the 5-min-before-Ihota-departure arrival. "
        "Official fare2 page lists adult one-way 伊保田港-三津浜港 fare as 2,570 JPY. "
        "Vehicle fares, reservation rules, child fares, return discounts, dangerous goods, disruption notices, and Yanai-Ihota fare handling are excluded."
    )
    return {
        "routeId": route_id,
        "routeGroupId": "suoshima_yanai_ihota_mitsuhama",
        "operator": "周防大島松山フェリー",
        "routeName": f"{origin}-{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "regional_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 2570},
            "sourceUrls": [TIME_URL, FARE_URL],
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": [TIME_URL, FARE_URL],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_daily_{no:03d}",
        "routeId": route_id,
        "operator": "周防大島松山フェリー",
        "serviceNo": str(no),
        "vessel": "フェリー",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": TIME_URL,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "suoshima_yanai_ihota_mitsuhama_036_out"
    back_id = "suoshima_yanai_ihota_mitsuhama_037_back"
    routes = [
        route(out_id, "伊保田港", "三津浜"),
        route(back_id, "三津浜", "伊保田港"),
    ]
    trips: list[dict] = []
    for no, (dep, arr) in enumerate([("08:15", "09:30"), ("13:45", "14:55"), ("19:10", "20:20")], 1):
        trips.append(trip(out_id, no, "伊保田港", "三津浜", dep, arr))
    for no, (dep, arr) in enumerate([("09:40", "10:47"), ("15:05", "16:12"), ("20:30", "21:37")], 1):
        trips.append(trip(back_id, no, "三津浜", "伊保田港", dep, arr))
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "周防大島松山フェリー",
        "operatorId": "suo_oshima_matsuyama_ferry",
        "retrievedAt": retrieved_at,
        "sourceUrls": [TIME_URL, FARE_URL],
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 1,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "excludedDirections": [
                "柳井港-伊保田港 directions are kept pending because the adult passenger fare was not safely parsed from the official fare pages.",
                "Through 柳井港-三津浜 sailings remain covered by their separate route/fare model and are not duplicated here.",
            ],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
