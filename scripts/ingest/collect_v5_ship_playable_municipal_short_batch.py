#!/usr/bin/env python3
"""Promote municipal short ferry routes with official text timetables and fares."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_municipal_short_batch_official.json")


def hm(value: str) -> int:
    hour, minute = value.replace("時", ":").replace("分", "").split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, operator: str, origin: str, destination: str, fare: int, source: str, note: str) -> dict:
    return {
        "routeId": route_id,
        "operator": operator,
        "routeName": f"{origin}・{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "municipal_island_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": [source],
            "notes": note,
        },
        "servicePatterns": [],
    }


def trip(route_id: str, no: int, operator: str, origin: str, destination: str, dep: str, arr: str, source: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    if arr_min < dep_min:
        arr_min += 24 * 60
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": operator,
        "serviceNo": str(no),
        "vessel": None,
        "origin": origin,
        "destination": destination,
        "departure": dep.replace("時", ":").replace("分", ""),
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": source,
    }


def add_pairs(trips: list[dict], route_id: str, operator: str, origin: str, destination: str, source: str, pairs: list[tuple[str, str]]) -> None:
    for index, (dep, arr) in enumerate(pairs, 1):
        trips.append(trip(route_id, index, operator, origin, destination, dep, arr, source))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes = []
    trips: list[dict] = []

    dewa_source = "https://www.town.tokushima-mugi.lg.jp/doc/2024020100029/"
    dewa_note = "Official adult one-way fare ¥220; August-September fare is ¥230 and is excluded until date-range fare selection is modeled. Excludes child fares, round trips, group/disabled discounts, and temporary inspection replacement service."
    routes += [
        route("mlit_map_193_030_出羽島連絡事業_牟岐_出羽島_000_out", "出羽島連絡事業", "牟岐", "出羽島", 220, dewa_source, dewa_note),
        route("mlit_map_193_030_出羽島連絡事業_牟岐_出羽島_000_back", "出羽島連絡事業", "出羽島", "牟岐", 220, dewa_source, dewa_note),
    ]
    add_pairs(trips, routes[-2]["routeId"], "出羽島連絡事業", "牟岐", "出羽島", dewa_source, [
        ("07:00", "07:15"), ("08:20", "08:35"), ("11:10", "11:25"), ("13:30", "13:45"), ("16:00", "16:15"), ("17:20", "17:35"),
    ])
    add_pairs(trips, routes[-1]["routeId"], "出羽島連絡事業", "出羽島", "牟岐", dewa_source, [
        ("06:30", "06:45"), ("07:25", "07:40"), ("09:00", "09:15"), ("12:20", "12:35"), ("15:00", "15:15"), ("16:35", "16:50"),
    ])

    shingu_time_source = "https://www.town.shingu.fukuoka.jp/soshiki/sangyo_shinko/8/1/2/1844.html"
    shingu_fare_source = "https://www.town.shingu.fukuoka.jp/kurashi/doro_kotsuu/2/2/3163.html"
    shingu_note = "Official adult one-way fare ¥480. V5 uses the official March 1-October 31 timetable, matching the current release date; winter timetable is excluded until date-range service selection is modeled. Excludes child fares, commuter tickets, discounts, and capacity restrictions."
    routes += [
        route("mlit_map_193_046_新宮町_相島_新宮_000_out", "新宮町", "相島", "新宮", 480, shingu_fare_source, shingu_note),
        route("mlit_map_193_046_新宮町_相島_新宮_000_back", "新宮町", "新宮", "相島", 480, shingu_fare_source, shingu_note),
    ]
    add_pairs(trips, routes[-2]["routeId"], "新宮町", "相島", "新宮", shingu_time_source, [
        ("07:00", "07:17"), ("08:40", "08:57"), ("10:50", "11:07"), ("13:50", "14:07"), ("16:00", "16:17"), ("17:30", "17:47"),
    ])
    add_pairs(trips, routes[-1]["routeId"], "新宮町", "新宮", "相島", shingu_time_source, [
        ("07:50", "08:07"), ("09:20", "09:37"), ("11:30", "11:47"), ("14:30", "14:47"), ("16:40", "16:57"), ("18:10", "18:27"),
    ])

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "municipal_short_ferry_batch",
        "operatorId": "municipal_short_ferry_batch",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({dewa_source, shingu_time_source, shingu_fare_source}),
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 2,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
