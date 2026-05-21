#!/usr/bin/env python3
"""Promote verified Saikai Engan Shosen Sasebo-Konoura ferry sailings."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_saikai_engan_batch_official.json")
SOURCE_URL = "https://www.saryokyo.com/member/member-01.html"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    return {
        "routeId": route_id,
        "routeGroupId": "mlit_map_193_052_西海沿岸商船_佐世保_神浦",
        "operator": "西海沿岸商船",
        "routeName": "佐世保-神浦",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "regional_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 2090},
            "sourceUrls": [SOURCE_URL],
            "notes": (
                "Sasebo Passenger Boat Association page for Saikai Engan Shosen lists the adult fare table revised 2024-10-01; "
                "佐世保-神浦 is 2,090 JPY. Only clearly marked full-route ferry (F) sailings are promoted. "
                "High-speed partial routings, Tuesday/Friday variants, shipyard-holiday variants, vehicle fares, child fares, "
                "discounts, and disruption status are excluded."
            ),
        },
        "servicePatterns": [],
        "sourceUrls": [SOURCE_URL],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_daily_ferry_{no:03d}",
        "routeId": route_id,
        "operator": "西海沿岸商船",
        "serviceNo": f"F{no}",
        "vessel": "フェリーかしま",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": SOURCE_URL,
        "notes": "Official full-route ferry row. Intermediate calls include 大島, 松島, 瀬戸, and/or 池島 depending on the row.",
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "mlit_map_193_052_西海沿岸商船_佐世保_神浦_000_out"
    back_id = "mlit_map_193_052_西海沿岸商船_佐世保_神浦_000_back"
    routes = [
        route(out_id, "佐世保港", "神浦"),
        route(back_id, "神浦", "佐世保港"),
    ]
    trips: list[dict] = []
    for no, (dep, arr) in enumerate([
        ("07:05", "07:48"),
        ("08:40", "10:11"),
        ("12:44", "13:43"),
        ("15:00", "16:55"),
        ("17:55", "18:35"),
    ], 1):
        trips.append(trip(out_id, no, "佐世保港", "神浦", dep, arr))
    for no, (dep, arr) in enumerate([
        ("07:35", "08:35"),
        ("10:30", "11:28"),
        ("13:46", "14:57"),
        ("17:00", "17:50"),
        ("18:40", "19:08"),
    ], 1):
        trips.append(trip(back_id, no, "神浦", "佐世保港", dep, arr))
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "西海沿岸商船",
        "operatorId": "saikai_engan_shosen",
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
                "Non-F high-speed rows and Tuesday/Friday-only rows are excluded until the calendar model can preserve those variants cleanly.",
                "Intermediate 大島/松島/瀬戸/池島 playable legs are deferred until explicit intermediate stop handling is promoted for this route group.",
            ],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
