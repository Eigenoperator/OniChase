#!/usr/bin/env python3
"""Promote Haboro Enkai Ferry current C-period ferry timetable and fares."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_haboro_batch_official.json")
OPERATOR = "羽幌沿海フェリー"


def hm(value: str) -> int:
    hour, minute = value.replace("：", ":").split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str, fare: int, source_urls: list[str], note: str) -> dict:
    return {
        "routeId": route_id,
        "operator": OPERATOR,
        "routeName": f"{origin}・{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "island_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": source_urls,
            "notes": note,
        },
        "servicePatterns": [],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str, source_url: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": OPERATOR,
        "serviceNo": str(no),
        "vessel": "おろろん2",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": source_url,
    }


def add_trips(trips: list[dict], route_id: str, origin: str, destination: str, source_url: str, rows: list[tuple[int, str, str]]) -> None:
    for service_no, dep, arr in rows:
        trips.append(trip(route_id, service_no, origin, destination, dep, arr, source_url))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    timetable = "https://haboro-enkai.com/timetable/"
    fare = "https://haboro-enkai.com/fare/"
    note = "Official 2026 timetable/fare pages. Current V5 collection date 2026-05-21 uses C period (5/7-5/31) regular ferry rows and September-June general adult 2nd-class one-way ferry fare. High-speed vessel, July/August fares, first class, child/group/discount fares, vehicles, baggage, temporary extra/early sailings, and disruption status are excluded."
    routes = [
        route("haboro_yagishiri_teuri_006_out", "羽幌港", "焼尻港", 1600, [timetable, fare], note),
        route("haboro_yagishiri_teuri_007_back", "焼尻港", "羽幌港", 1600, [timetable, fare], note),
        route("haboro_yagishiri_teuri_008_out", "焼尻港", "天売港", 730, [timetable, fare], note),
        route("haboro_yagishiri_teuri_009_back", "天売港", "焼尻港", 730, [timetable, fare], note),
    ]
    trips: list[dict] = []
    add_trips(trips, routes[0]["routeId"], "羽幌港", "焼尻港", timetable, [(1, "08:30", "09:30"), (2, "14:00", "15:00")])
    add_trips(trips, routes[2]["routeId"], "焼尻港", "天売港", timetable, [(3, "09:40", "10:05"), (4, "15:10", "15:35")])
    add_trips(trips, routes[3]["routeId"], "天売港", "焼尻港", timetable, [(5, "10:25", "10:50"), (6, "15:50", "16:15")])
    add_trips(trips, routes[1]["routeId"], "焼尻港", "羽幌港", timetable, [(7, "11:10", "12:10"), (8, "16:25", "17:25")])
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": OPERATOR,
        "operatorId": "haboro_enkai_ferry",
        "retrievedAt": retrieved_at,
        "sourceUrls": [fare, timetable],
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
