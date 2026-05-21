#!/usr/bin/env python3
"""Promote Oki Kisen ferry routes with official current timetable and adult fares."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_oki_kisen_batch_official.json")
OPERATOR = "隠岐汽船"
TIMETABLE_URL = "https://www.oki-kisen.co.jp/timetable/"
FARE_URL = "https://www.oki-kisen.co.jp/fare/"
STATUS_URL = "https://www.oki-kisen.co.jp/situation/"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str, fare_yen: int, note: str) -> dict:
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
            "adultPassengerFare": {"amount": fare_yen},
            "sourceUrls": [TIMETABLE_URL, FARE_URL, STATUS_URL],
            "notes": note,
        },
        "servicePatterns": [],
    }


def trip(
    route_id: str,
    no: int,
    vessel: str,
    origin: str,
    destination: str,
    dep: str,
    arr: str,
) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": OPERATOR,
        "serviceNo": str(no),
        "vessel": vessel,
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": TIMETABLE_URL,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    note = (
        "Official Oki Kisen timetable/fare/status pages retrieved for 2026-05-21. "
        "Status page marks both ferry and Rainbow Jet as regular operation. "
        "Adult passenger fare uses the official standard table: ferry 2nd-class for regular ferries, "
        "and the published Rainbow Jet fare only where it is the same 別府-菱浦 amount. "
        "Child/student/group/disabled fares, higher rooms, cars, baggage, connecting buses, "
        "Oki Kanko inter-island vessels, weather cancellations after retrieval, and non-adjacent "
        "through-stop modeling are excluded."
    )
    routes = [
        route("oki_kisen_shimane_oki_114_out", "七類港", "西郷港", 3510, note),
        route("oki_kisen_shimane_oki_118_out", "七類港", "隠岐別府港", 3510, note),
        route("oki_kisen_shimane_oki_116_out", "境港", "西郷港", 3510, note),
        route("oki_kisen_shimane_oki_121_back", "菱浦港", "隠岐別府港", 410, note),
        route("oki_kisen_shimane_oki_115_back", "西郷港", "七類港", 3510, note),
        route("oki_kisen_shimane_oki_117_back", "西郷港", "境港", 3510, note),
        route("oki_kisen_shimane_oki_119_back", "隠岐別府港", "七類港", 3510, note),
        route("oki_kisen_shimane_oki_120_out", "隠岐別府港", "菱浦港", 410, note),
    ]
    trips = [
        trip("oki_kisen_shimane_oki_114_out", 1, "おき", "七類港", "西郷港", "09:00", "11:25"),
        trip("oki_kisen_shimane_oki_114_out", 2, "くにが", "七類港", "西郷港", "09:30", "14:00"),
        trip("oki_kisen_shimane_oki_118_out", 3, "くにが", "七類港", "隠岐別府港", "09:30", "12:05"),
        trip("oki_kisen_shimane_oki_116_out", 4, "しらしま", "境港", "西郷港", "14:25", "18:30"),
        trip("oki_kisen_shimane_oki_121_back", 5, "おき", "菱浦港", "隠岐別府港", "15:15", "15:30"),
        trip("oki_kisen_shimane_oki_121_back", 6, "しらしま", "菱浦港", "隠岐別府港", "09:50", "10:05"),
        trip("oki_kisen_shimane_oki_121_back", 7, "レインボージェット", "菱浦港", "隠岐別府港", "18:39", "18:49"),
        trip("oki_kisen_shimane_oki_115_back", 8, "くにが", "西郷港", "七類港", "15:10", "17:35"),
        trip("oki_kisen_shimane_oki_117_back", 9, "しらしま", "西郷港", "境港", "08:30", "13:20"),
        trip("oki_kisen_shimane_oki_119_back", 10, "おき", "隠岐別府港", "七類港", "15:45", "17:55"),
        trip("oki_kisen_shimane_oki_120_out", 11, "くにが", "隠岐別府港", "菱浦港", "12:20", "12:40"),
        trip("oki_kisen_shimane_oki_120_out", 12, "レインボージェット", "隠岐別府港", "菱浦港", "08:00", "08:10"),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": OPERATOR,
        "operatorId": "oki_kisen",
        "retrievedAt": retrieved_at,
        "sourceUrls": [TIMETABLE_URL, FARE_URL, STATUS_URL],
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 1,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "excludedDirections": ["菱浦港-来居港", "来居港-菱浦港"],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
