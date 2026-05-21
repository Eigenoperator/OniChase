#!/usr/bin/env python3
"""Promote verified Ieshima Liner Himeji-Miya sailings."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_ieshima_liner_batch_official.json")
SOURCE_URL = "https://h-ieshima.jp/liner.html"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    return {
        "routeId": route_id,
        "routeGroupId": "kofuku_liner",
        "operator": "家島ライナー",
        "routeName": "姫路-家島宮港",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "short_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 1000},
            "sourceUrls": [SOURCE_URL],
            "notes": (
                "Ieshima tourism access page lists 株式会社家島ライナー adult one-way fare as 1,000 JPY "
                "for 家島-姫路. Student/child fares, other island routes, motorcycle fares, sea taxis, "
                "alternate vessel notes, and disruption notices are excluded."
            ),
        },
        "servicePatterns": [],
        "sourceUrls": [SOURCE_URL],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_daily_{no:03d}",
        "routeId": route_id,
        "operator": "家島ライナー",
        "serviceNo": str(no),
        "vessel": "家島ライナー",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": SOURCE_URL,
        "notes": "Official/area access page table for 家島-姫路港. Some sailings call at 真浦; intermediate playable stops are deferred.",
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "kofuku_liner_032_out"
    back_id = "kofuku_liner_033_back"
    routes = [
        route(out_id, "姫路港", "家島宮港"),
        route(back_id, "家島宮港", "姫路港"),
    ]
    trips: list[dict] = []
    for no, (dep, arr) in enumerate([
        ("06:55", "07:28"),
        ("07:10", "07:37"),
        ("08:18", "08:53"),
        ("09:10", "09:45"),
        ("10:00", "10:35"),
        ("11:40", "12:07"),
        ("13:40", "14:13"),
        ("15:30", "16:15"),
        ("16:30", "17:05"),
        ("17:10", "17:37"),
        ("18:15", "18:50"),
        ("19:00", "19:35"),
        ("19:55", "20:30"),
        ("20:35", "21:02"),
    ], 1):
        trips.append(trip(out_id, no, "姫路港", "家島宮港", dep, arr))
    for no, (dep, arr) in enumerate([
        ("06:00", "06:37"),
        ("06:20", "07:00"),
        ("07:31", "08:04"),
        ("08:05", "08:45"),
        ("09:02", "09:37"),
        ("10:50", "11:27"),
        ("12:50", "13:27"),
        ("14:20", "15:00"),
        ("15:35", "16:12"),
        ("16:25", "16:52"),
        ("17:33", "18:00"),
        ("17:45", "18:27"),
        ("19:00", "19:37"),
        ("20:00", "20:27"),
    ], 1):
        trips.append(trip(back_id, no, "家島宮港", "姫路港", dep, arr))
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "家島ライナー",
        "operatorId": "ieshima_liner",
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
                "真浦 as an intermediate playable stop is deferred until the ship model supports explicit intermediate port stop times for this route group.",
                "Other routes on the same access page, including 坊勢 and 網手, remain separate queue items and are not promoted here.",
            ],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
