#!/usr/bin/env python3
"""Promote Shikoku Ferry Okayama-Tonosho official timetable and fare."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_shikoku_ferry_batch_official.json")
SOURCE = "https://www.shikokuferry.com/route3"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    return {
        "routeId": route_id,
        "operator": "四国フェリー",
        "routeName": "岡山・土庄",
        "origin": origin,
        "destination": destination,
        "distanceKm": 23.5,
        "routeClass": "short_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 1200},
            "sourceUrls": [SOURCE],
            "notes": "Official adult one-way passenger fare 岡山-土庄 ¥1,200, distance 23.5 km and about 70 minutes. Excludes child fares, round trips, group fares, vehicle/bicycle fares, discounts, and special operating notices.",
        },
        "servicePatterns": [],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    if arr_min < dep_min:
        arr_min += 24 * 60
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": "四国フェリー",
        "serviceNo": str(no),
        "vessel": None,
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": SOURCE,
    }


def add_pairs(trips: list[dict], route_id: str, origin: str, destination: str, pairs: list[tuple[str, str]]) -> None:
    for index, (dep, arr) in enumerate(pairs, 1):
        trips.append(trip(route_id, index, origin, destination, dep, arr))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "mlit_map_193_021_四国フェリー_岡山_小豆島_土庄_000_out"
    back_id = "mlit_map_193_021_四国フェリー_岡山_小豆島_土庄_000_back"
    routes = [
        route(out_id, "岡山", "土庄港"),
        route(back_id, "土庄港", "岡山"),
    ]
    trips: list[dict] = []
    add_pairs(trips, out_id, "岡山", "土庄港", [
        ("06:20", "07:30"), ("08:40", "09:50"), ("10:10", "11:20"), ("11:40", "12:50"),
        ("14:00", "15:10"), ("15:40", "16:50"), ("17:00", "18:10"), ("18:30", "19:40"),
    ])
    add_pairs(trips, back_id, "土庄港", "岡山", [
        ("07:00", "08:10"), ("08:40", "09:50"), ("10:10", "11:20"), ("11:40", "12:50"),
        ("14:00", "15:10"), ("15:40", "16:50"), ("17:00", "18:10"), ("18:30", "19:40"),
    ])
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "四国フェリー",
        "operatorId": "shikoku_ferry_okayama_tonosho",
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
