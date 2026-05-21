#!/usr/bin/env python3
"""Promote additional short ferry routes with official times and adult fares."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_short_ferries_batch_official.json")


def hm(value: str) -> int:
    hour, minute = value.replace("：", ":").split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, operator: str, origin: str, destination: str, fare: int, source: str, note: str) -> dict:
    return {
        "routeId": route_id,
        "operator": operator,
        "routeName": f"{origin}・{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "short_public_ferry",
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


def trip(route_id: str, no: int, operator: str, origin: str, destination: str, dep: str, arr: str, source: str, calendar: str = "daily") -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    if arr_min < dep_min:
        arr_min += 24 * 60
    return {
        "tripId": f"{route_id}_{calendar}_{no:03d}",
        "routeId": route_id,
        "operator": operator,
        "serviceNo": str(no),
        "vessel": None,
        "origin": origin,
        "destination": destination,
        "departure": dep.replace("：", ":"),
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": calendar},
        "sourceUrl": source,
    }


def add_pairs(trips: list[dict], route_id: str, operator: str, origin: str, destination: str, source: str, pairs: list[tuple[str, str]], calendar: str = "daily") -> None:
    for index, (dep, arr) in enumerate(pairs, 1):
        trips.append(trip(route_id, index, operator, origin, destination, dep, arr, source, calendar))


def with_duration(deps: list[str], minutes: int) -> list[tuple[str, str]]:
    pairs = []
    for dep in deps:
        total = hm(dep) + minutes
        pairs.append((dep, f"{total // 60:02d}:{total % 60:02d}"))
    return pairs


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes = []
    trips: list[dict] = []

    karouto_source = "https://karouto-ferry.com/time/"
    karouto_note = "Official adult one-way passenger fare ¥100. Timetable page states all trips suspended on Sundays and during dock periods; V5 encodes regular Monday-Saturday service. Excludes child fares, round trips, vehicles, bicycles, discounts, and Jan 1 exceptions."
    routes += [
        route("karouto_kamiyuge_058_out", "家老渡フェリー汽船", "家老渡港", "上弓削港", 100, karouto_source, karouto_note),
        route("karouto_kamiyuge_059_back", "家老渡フェリー汽船", "上弓削港", "家老渡港", 100, karouto_source, karouto_note),
    ]
    add_pairs(trips, routes[-2]["routeId"], "家老渡フェリー汽船", "家老渡港", "上弓削港", karouto_source, with_duration([
        "06:50", "07:10", "07:30", "07:50", "08:10", "08:30", "09:10", "10:10", "11:10",
        "13:10", "14:10", "15:10", "16:10", "16:50", "17:10", "17:30", "17:50",
        "18:10", "18:30", "18:50", "19:10", "19:50",
    ], 7), "monday_to_saturday")
    add_pairs(trips, routes[-1]["routeId"], "家老渡フェリー汽船", "上弓削港", "家老渡港", karouto_source, with_duration([
        "07:00", "07:20", "07:40", "08:00", "08:20", "08:40", "09:20", "10:20", "11:20",
        "13:20", "14:20", "15:20", "16:20", "17:00", "17:20", "17:40",
        "18:00", "18:20", "18:40", "19:00", "19:20", "20:00",
    ], 7), "monday_to_saturday")

    hatsushima_source = "https://www.hatsushima.jp/access/"
    hatsushima_note = "Official adult one-way fare ¥1,450 from the 2025-07-12 fare notice area and access page. Uses the official 10-sailing daily table shown on the access page. Excludes child fares, round trips, pet fares, set tickets, discounts, and temporary disruption changes."
    routes += [
        route("hatsushima_atami_026_out", "富士急マリンリゾート", "熱海港", "初島港", 1450, hatsushima_source, hatsushima_note),
        route("hatsushima_atami_027_back", "富士急マリンリゾート", "初島港", "熱海港", 1450, hatsushima_source, hatsushima_note),
    ]
    add_pairs(trips, routes[-2]["routeId"], "富士急マリンリゾート", "熱海港", "初島港", hatsushima_source, [
        ("07:30", "08:00"), ("08:40", "09:10"), ("10:00", "10:30"), ("10:40", "11:10"), ("12:00", "12:30"),
        ("13:00", "13:30"), ("14:00", "14:30"), ("14:40", "15:10"), ("16:00", "16:30"), ("17:20", "17:50"),
    ])
    add_pairs(trips, routes[-1]["routeId"], "富士急マリンリゾート", "初島港", "熱海港", hatsushima_source, [
        ("08:00", "08:30"), ("09:20", "09:50"), ("10:40", "11:10"), ("11:20", "11:50"), ("13:00", "13:30"),
        ("14:00", "14:30"), ("14:40", "15:10"), ("15:20", "15:50"), ("16:40", "17:10"), ("17:50", "18:20"),
    ])

    suruga_source = "https://www.223-ferry.or.jp/timetable.html"
    suruga_fare_source = "https://www.223-ferry.or.jp/fare.html"
    suruga_note = "Official adult one-way passenger fare ¥3,000 effective 2026-05-01. Timetable has three regular daily trips per direction; optional fourth service is excluded until its limited operating calendar is modeled. Excludes vehicle, bicycle, pet, special room, round-trip discounts, and coupons."
    routes += [
        route("suruga_shimizu_toi_032_out", "ふじさん駿河湾フェリー", "清水港", "土肥港", 3000, suruga_fare_source, suruga_note),
        route("suruga_shimizu_toi_033_back", "ふじさん駿河湾フェリー", "土肥港", "清水港", 3000, suruga_fare_source, suruga_note),
    ]
    add_pairs(trips, routes[-2]["routeId"], "ふじさん駿河湾フェリー", "清水港", "土肥港", suruga_source, [
        ("07:40", "09:10"), ("11:20", "12:50"), ("14:40", "16:10"),
    ])
    add_pairs(trips, routes[-1]["routeId"], "ふじさん駿河湾フェリー", "土肥港", "清水港", suruga_source, [
        ("09:35", "11:05"), ("13:00", "14:30"), ("16:30", "18:00"),
    ])

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "short_ferry_batch",
        "operatorId": "short_ferry_batch",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for item in routes for url in item["fare"]["sourceUrls"]} | {suruga_source}),
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 3,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
