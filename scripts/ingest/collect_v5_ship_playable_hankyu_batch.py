#!/usr/bin/env python3
"""Promote verified Hankyu Ferry Shinmoji-Izumiotsu/Kobe routes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_hankyu_batch_official.json")
OPERATOR = "阪九フェリー"
IZUMI_TIMETABLE_URL = "https://www.han9f.co.jp/izumiotsu/timetable/"
IZUMI_FARE_URL = "https://www.han9f.co.jp/izumiotsu/fare/"
KOBE_TIMETABLE_URL = "https://www.han9f.co.jp/kobe/timetable/"
KOBE_FARE_URL = "https://www.han9f.co.jp/kobe/fare/"


def hm(value: str) -> int:
    next_day = value.startswith("翌")
    value = value.replace("翌", "").replace("：", ":")
    hour, minute = value.split(":")
    total = int(hour) * 60 + int(minute)
    if next_day:
        total += 24 * 60
    return total


def route(route_id: str, group_id: str, origin: str, destination: str, timetable_url: str, fare_url: str) -> dict:
    note = (
        "Official Hankyu Ferry route page lists the current sailing timetable. "
        "Official fare page embeds the 2026-05 calendar; for the V5 service date 2026-05-21 the adult passenger "
        "スタンダード和室 fare is 10,780 JPY for both Shinmoji-Izumiotsu and Shinmoji-Kobe routes. "
        "Other room grades, child fares, vehicles, motorcycles, baggage, web discounts, season changes outside the V5 service date, and disruption notices are excluded."
    )
    return {
        "routeId": route_id,
        "routeGroupId": group_id,
        "operator": OPERATOR,
        "routeName": f"{origin}-{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "long_distance_public_ferry",
        "revealPolicy": "long_distance_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 10780},
            "sourceUrls": [timetable_url, fare_url],
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": [timetable_url, fare_url],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str, calendar: str, source_url: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_{calendar}_{no:03d}",
        "routeId": route_id,
        "operator": OPERATOR,
        "serviceNo": str(no),
        "vessel": "阪九フェリー",
        "origin": origin,
        "destination": destination,
        "departure": dep.replace("：", ":"),
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": calendar},
        "sourceUrl": source_url,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes = [
        route("hankyu_izumiotsu_shinmoji_024_out", "hankyu_izumiotsu_shinmoji", "泉大津港", "新門司港", IZUMI_TIMETABLE_URL, IZUMI_FARE_URL),
        route("hankyu_izumiotsu_shinmoji_025_back", "hankyu_izumiotsu_shinmoji", "新門司港", "泉大津港", IZUMI_TIMETABLE_URL, IZUMI_FARE_URL),
        route("hankyu_kobe_shinmoji_026_out", "hankyu_kobe_shinmoji", "神戸港", "新門司港", KOBE_TIMETABLE_URL, KOBE_FARE_URL),
        route("hankyu_kobe_shinmoji_027_back", "hankyu_kobe_shinmoji", "新門司港", "神戸港", KOBE_TIMETABLE_URL, KOBE_FARE_URL),
    ]
    trips = [
        trip("hankyu_izumiotsu_shinmoji_024_out", 1, "泉大津港", "新門司港", "17:30", "翌06:00", "daily", IZUMI_TIMETABLE_URL),
        trip("hankyu_izumiotsu_shinmoji_025_back", 1, "新門司港", "泉大津港", "17:30", "翌06:00", "daily", IZUMI_TIMETABLE_URL),
        trip("hankyu_kobe_shinmoji_026_out", 1, "神戸港", "新門司港", "18:30", "翌07:00", "sunday_to_thursday", KOBE_TIMETABLE_URL),
        trip("hankyu_kobe_shinmoji_027_back", 1, "新門司港", "神戸港", "18:40", "翌07:10", "sunday_to_thursday", KOBE_TIMETABLE_URL),
        trip("hankyu_kobe_shinmoji_026_out", 2, "神戸港", "新門司港", "20:00", "翌08:30", "friday_saturday", KOBE_TIMETABLE_URL),
        trip("hankyu_kobe_shinmoji_027_back", 2, "新門司港", "神戸港", "20:00", "翌08:30", "friday_saturday", KOBE_TIMETABLE_URL),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": OPERATOR,
        "operatorId": "hankyu_ferry",
        "retrievedAt": retrieved_at,
        "sourceUrls": [IZUMI_TIMETABLE_URL, IZUMI_FARE_URL, KOBE_TIMETABLE_URL, KOBE_FARE_URL],
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
