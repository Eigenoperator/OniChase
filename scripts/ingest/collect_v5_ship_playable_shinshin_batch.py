#!/usr/bin/env python3
"""Promote Shinshin Kisen Shimoda-Izu island loop with official May 2026 fares."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_shinshin_batch_official.json")
OPERATOR = "神新汽船"
TIMETABLE_URL = "https://shinshin-kisen.jp/service/index.html?date=20260521"


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
            "sourceUrls": [TIMETABLE_URL],
            "notes": note,
        },
        "servicePatterns": [],
    }


def trip(
    route_id: str,
    no: int,
    origin: str,
    destination: str,
    dep: str,
    arr: str,
    calendar: str,
) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_{calendar}_{no:03d}",
        "routeId": route_id,
        "operator": OPERATOR,
        "serviceNo": str(no),
        "vessel": "あぜりあ丸",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": calendar},
        "sourceUrl": TIMETABLE_URL,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    note = (
        "Official Shinshin Kisen timetable/fare page for 2026-05-21. "
        "Adult 2nd-class May 2026 passenger fares are used. "
        "The route operates as a loop: 月・木・土 下田-神津島-式根島-新島-利島-下田, "
        "火・金・日 下田-利島-新島-式根島-神津島-下田. "
        "Wednesday non-operation, child fares, higher classes, cars, baggage, discounts, "
        "weather cancellations, and future month fuel adjustment changes are excluded."
    )
    routes = [
        route("shinshin_shimoda_izu_010_out", "下田港", "利島港", 5010, note),
        route("shinshin_shimoda_izu_011_back", "利島港", "下田港", 5010, note),
        route("shinshin_shimoda_izu_012_out", "利島港", "新島港", 720, note),
        route("shinshin_shimoda_izu_013_back", "新島港", "利島港", 720, note),
        route("shinshin_shimoda_izu_014_out", "新島港", "式根島野伏港", 340, note),
        route("shinshin_shimoda_izu_015_back", "式根島野伏港", "新島港", 340, note),
        route("shinshin_shimoda_izu_016_out", "式根島野伏港", "神津島港", 740, note),
        route("shinshin_shimoda_izu_017_back", "神津島港", "式根島野伏港", 740, note),
    ]
    trips = [
        trip("shinshin_shimoda_izu_010_out", 1, "下田港", "利島港", "09:30", "11:05", "tuesday_friday_sunday"),
        trip("shinshin_shimoda_izu_012_out", 2, "利島港", "新島港", "11:10", "12:10", "tuesday_friday_sunday"),
        trip("shinshin_shimoda_izu_014_out", 3, "新島港", "式根島野伏港", "12:25", "12:45", "tuesday_friday_sunday"),
        trip("shinshin_shimoda_izu_016_out", 4, "式根島野伏港", "神津島港", "13:00", "13:50", "tuesday_friday_sunday"),
        trip("shinshin_shimoda_izu_017_back", 5, "神津島港", "式根島野伏港", "12:10", "13:00", "monday_thursday_saturday"),
        trip("shinshin_shimoda_izu_015_back", 6, "式根島野伏港", "新島港", "13:10", "13:30", "monday_thursday_saturday"),
        trip("shinshin_shimoda_izu_013_back", 7, "新島港", "利島港", "13:50", "14:40", "monday_thursday_saturday"),
        trip("shinshin_shimoda_izu_011_back", 8, "利島港", "下田港", "14:45", "16:30", "monday_thursday_saturday"),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": OPERATOR,
        "operatorId": "shinshin_kisen",
        "retrievedAt": retrieved_at,
        "sourceUrls": [TIMETABLE_URL],
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
