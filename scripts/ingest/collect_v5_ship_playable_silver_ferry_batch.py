#!/usr/bin/env python3
"""Promote Silver Ferry Hachinohe-Tomakomai timetable and adult 2nd-class fare."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_silver_ferry_batch_official.json")
OPERATOR = "シルバーフェリー"


def hm(value: str) -> int:
    next_day = value.startswith("翌")
    value = value.replace("翌", "")
    hour, minute = value.split(":")
    total = int(hour) * 60 + int(minute)
    if next_day:
        total += 24 * 60
    return total


def route(route_id: str, origin: str, destination: str, source_urls: list[str], note: str) -> dict:
    return {
        "routeId": route_id,
        "operator": OPERATOR,
        "routeName": f"{origin}・{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "long_distance_public_ferry",
        "revealPolicy": "long_distance_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 6000},
            "sourceUrls": source_urls,
            "notes": note,
        },
        "servicePatterns": [],
    }


def trip(route_id: str, no: int, vessel: str, origin: str, destination: str, dep: str, arr: str, source_url: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    if arr_min < dep_min:
        arr_min += 24 * 60
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": OPERATOR,
        "serviceNo": str(no),
        "vessel": vessel,
        "origin": origin,
        "destination": destination,
        "departure": dep.replace("翌", ""),
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": source_url,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    timetable = "https://www.silverferry.jp/route_guide/?stt_lang=ja"
    fare = "https://www.silverferry.jp/fare/?stt_lang=ja"
    note = "Official Silver Ferry timetable/fare pages. Adult 2nd-class passenger fare is 6,000 JPY. Current public timetable lists four daily departures each direction. Child/student fares, room upgrades, vehicles, special baggage, web/round-trip/group/disabled discounts, substitute-vessel notices, and temporary schedule changes are excluded."
    routes = [
        route("silver_hachinohe_tomakomai_038_out", "八戸港", "苫小牧西港", [timetable, fare], note),
        route("silver_hachinohe_tomakomai_039_back", "苫小牧西港", "八戸港", [timetable, fare], note),
    ]
    trips = [
        trip(routes[0]["routeId"], 1, "シルバープリンセス", "八戸港", "苫小牧西港", "08:45", "16:00", timetable),
        trip(routes[0]["routeId"], 2, "シルバーティアラ", "八戸港", "苫小牧西港", "13:00", "20:15", timetable),
        trip(routes[0]["routeId"], 3, "シルバーブリーズ", "八戸港", "苫小牧西港", "17:30", "翌01:30", timetable),
        trip(routes[0]["routeId"], 4, "シルバーエイト", "八戸港", "苫小牧西港", "22:00", "翌06:00", timetable),
        trip(routes[1]["routeId"], 5, "シルバーブリーズ", "苫小牧西港", "八戸港", "05:00", "13:30", timetable),
        trip(routes[1]["routeId"], 6, "シルバーエイト", "苫小牧西港", "八戸港", "09:30", "18:00", timetable),
        trip(routes[1]["routeId"], 7, "シルバープリンセス", "苫小牧西港", "八戸港", "21:15", "翌04:45", timetable),
        trip(routes[1]["routeId"], 8, "シルバーティアラ", "苫小牧西港", "八戸港", "23:59", "翌07:30", timetable),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": OPERATOR,
        "operatorId": "silver_ferry",
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
