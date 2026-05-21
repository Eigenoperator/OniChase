#!/usr/bin/env python3
"""Promote verified Tencho Ferry full-route playable ship routes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_tencho_batch_official.json")
SOURCE_URLS = [
    "https://tenchou-ferry.co.jp/pages/44/",
    "https://tenchou-ferry.co.jp/pages/45/",
    "https://www.town.nagashima.lg.jp/shishijima/access/",
]


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    return {
        "routeId": route_id,
        "routeGroupId": "mlit_map_193_083_天長フェリー_天草_長島",
        "operator": "天長フェリー",
        "routeName": "天草・長島",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "short_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 410},
            "sourceUrls": SOURCE_URLS,
            "notes": (
                "Official Tencho Ferry fare table lists the adult passenger fare for 中田-諸浦 as 410 JPY. "
                "Only the full 天草/中田港-長島/諸浦港 through legs are promoted here; partial 片側港 legs, "
                "vehicle fares, bicycle/motorcycle fares, discounts, and disruption notices are excluded."
            ),
        },
        "servicePatterns": [],
        "sourceUrls": SOURCE_URLS,
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str, note: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_daily_{no:03d}",
        "routeId": route_id,
        "operator": "天長フェリー",
        "serviceNo": str(no),
        "vessel": "ロザリオ・カーム",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": SOURCE_URLS[0],
        "notes": note,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "mlit_map_193_083_天長フェリー_天草_長島_000_out"
    back_id = "mlit_map_193_083_天長フェリー_天草_長島_000_back"
    routes = [
        route(out_id, "天草", "長島"),
        route(back_id, "長島", "天草"),
    ]
    trips: list[dict] = []
    for idx, (dep, arr, note) in enumerate([
        ("08:10", "09:05", "片側港経由"),
        ("10:15", "11:10", "片側港経由"),
        ("12:15", "13:10", "片側港経由"),
        ("13:55", "14:50", "片側港経由"),
        ("15:55", "16:30", "直行"),
    ], 1):
        trips.append(trip(out_id, idx, "天草", "長島", dep, arr, note))
    for idx, (dep, arr, note) in enumerate([
        ("07:10", "08:05", "片側港経由"),
        ("09:15", "10:10", "片側港経由"),
        ("11:15", "12:10", "片側港経由"),
        ("13:15", "13:50", "直行"),
        ("14:55", "15:50", "片側港経由"),
    ], 1):
        trips.append(trip(back_id, idx, "長島", "天草", dep, arr, note))
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "天長フェリー",
        "operatorId": "tencho_ferry",
        "retrievedAt": retrieved_at,
        "sourceUrls": SOURCE_URLS,
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 1,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "excludedDirections": [
                "片側港-only first/last sailings are not promoted because current MLIT route IDs are the full 天草-長島 pair.",
                "片側港 as an intermediate playable stop is deferred until the ship model supports explicit intermediate port stop times for this route group.",
            ],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
