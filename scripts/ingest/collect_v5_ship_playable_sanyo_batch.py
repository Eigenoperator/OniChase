#!/usr/bin/env python3
"""Promote Sanyo Kisen official timetable and adult fares."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_sanyo_batch_official.json")
TIME_SAYANAGI = "https://sanyo-kisen.jp/%e6%99%82%e5%88%bb%e8%a1%a8/%e7%ac%a0%e5%b2%a1-%ef%bd%9e-%e4%bd%90%e6%9f%b3%e6%9c%ac%e6%b5%a6-%e6%99%82%e5%88%bb%e8%a1%a8"
TIME_TOBISHIMA = "https://sanyo-kisen.jp/%e6%99%82%e5%88%bb%e8%a1%a8/%e7%ac%a0%e5%b2%a1%ef%bd%9e%e9%a3%9b%e5%b3%b6%ef%bd%9e%e5%85%ad%e5%b3%b6-%e6%99%82%e5%88%bb%e8%a1%a8"
FARE_SAYANAGI = "https://sanyo-kisen.jp/%e9%81%8b%e8%b3%83/%e7%ac%a0%e5%b2%a1%ef%bd%9e%e4%bd%90%e6%9f%b3%e6%9c%ac%e6%b5%a6-%e9%81%8b%e8%b3%83%e8%a1%a8"
FARE_TOBISHIMA = "https://sanyo-kisen.jp/%e9%81%8b%e8%b3%83/%e7%ac%a0%e5%b2%a1%ef%bd%9e%e9%a3%9b%e5%b3%b6%ef%bd%9e%e5%85%ad%e5%b3%b6-%e9%81%8b%e8%b3%83%e8%a1%a8"


def hm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def hhmm(minutes: int) -> str:
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


def route(route_id: str, route_name: str, origin: str, destination: str, fare: int, sources: list[str], notes: str = "") -> dict:
    return {
        "routeId": route_id,
        "operator": "三洋汽船",
        "routeName": route_name,
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "island_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": sources,
            "notes": notes or "Adult passenger fare from the official Sanyo Kisen fare table; excludes child fares, baggage, bicycles, vehicles, and discounts.",
        },
        "servicePatterns": [],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str, source: str) -> dict:
    dep_min = hm_to_minutes(dep)
    arr_min = hm_to_minutes(arr)
    if arr_min < dep_min:
        arr_min += 24 * 60
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": "三洋汽船",
        "serviceNo": str(no),
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": hhmm(arr_min),
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": source,
    }


def add_pairs(trips: list[dict], route_id: str, origin: str, destination: str, pairs: list[tuple[str, str]], source: str) -> None:
    for index, (dep, arr) in enumerate(pairs, 1):
        trips.append(trip(route_id, index, origin, destination, dep, arr, source))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes = [
        route("mlit_map_193_020_三洋汽船_笠岡_佐柳本浦_笠岡_飛鳥_六島_000_out", "笠岡・佐柳本浦", "笠岡", "佐柳本浦", 1200, [TIME_SAYANAGI, FARE_SAYANAGI]),
        route("mlit_map_193_020_三洋汽船_笠岡_佐柳本浦_笠岡_飛鳥_六島_000_back", "佐柳本浦・笠岡", "佐柳本浦", "笠岡", 1200, [TIME_SAYANAGI, FARE_SAYANAGI]),
        route("mlit_map_193_020_三洋汽船_笠岡_佐柳本浦_笠岡_飛鳥_六島_001_out", "笠岡・飛島", "笠岡", "飛鳥", 1020, [TIME_TOBISHIMA, FARE_TOBISHIMA], "Official Sanyo Kisen table is 笠岡-飛島-六島; the MLIT-derived route inventory labels this port as 飛鳥."),
        route("mlit_map_193_020_三洋汽船_笠岡_佐柳本浦_笠岡_飛鳥_六島_001_back", "飛島・笠岡", "飛鳥", "笠岡", 1020, [TIME_TOBISHIMA, FARE_TOBISHIMA], "Official Sanyo Kisen table is 笠岡-飛島-六島; the MLIT-derived route inventory labels this port as 飛鳥."),
        route("mlit_map_193_020_三洋汽船_笠岡_佐柳本浦_笠岡_飛鳥_六島_002_out", "飛島・六島", "飛鳥", "六島", 430, [TIME_TOBISHIMA, FARE_TOBISHIMA], "Official Sanyo Kisen table is 笠岡-飛島-六島; the MLIT-derived route inventory labels this port as 飛鳥."),
        route("mlit_map_193_020_三洋汽船_笠岡_佐柳本浦_笠岡_飛鳥_六島_002_back", "六島・飛島", "六島", "飛鳥", 430, [TIME_TOBISHIMA, FARE_TOBISHIMA], "Official Sanyo Kisen table is 笠岡-飛島-六島; the MLIT-derived route inventory labels this port as 飛鳥."),
    ]
    trips: list[dict] = []
    add_pairs(trips, routes[0]["routeId"], "笠岡", "佐柳本浦", [("07:25", "08:09"), ("08:10", "09:14"), ("09:10", "09:54"), ("11:20", "12:24"), ("13:45", "14:54"), ("16:30", "17:14"), ("17:47", "18:55")], TIME_SAYANAGI)
    add_pairs(trips, routes[1]["routeId"], "佐柳本浦", "笠岡", [("06:30", "07:34"), ("08:15", "08:59"), ("09:14", "10:18"), ("12:35", "13:39"), ("15:35", "16:19"), ("16:30", "17:34"), ("17:28", "18:12"), ("18:55", "19:30")], TIME_SAYANAGI)
    add_pairs(trips, routes[2]["routeId"], "笠岡", "飛鳥", [("08:50", "09:25"), ("13:20", "13:55"), ("16:40", "17:15")], TIME_TOBISHIMA)
    add_pairs(trips, routes[3]["routeId"], "飛鳥", "笠岡", [("08:10", "08:45"), ("10:35", "11:15"), ("14:40", "15:15")], TIME_TOBISHIMA)
    add_pairs(trips, routes[4]["routeId"], "飛鳥", "六島", [("09:25", "09:45"), ("13:55", "14:15"), ("17:15", "17:35")], TIME_TOBISHIMA)
    add_pairs(trips, routes[5]["routeId"], "六島", "飛鳥", [("07:50", "08:10"), ("10:20", "10:35"), ("14:15", "14:40")], TIME_TOBISHIMA)

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "三洋汽船",
        "operatorId": "sanyo_kisen",
        "retrievedAt": retrieved_at,
        "sourceUrls": [TIME_SAYANAGI, TIME_TOBISHIMA, FARE_SAYANAGI, FARE_TOBISHIMA],
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
