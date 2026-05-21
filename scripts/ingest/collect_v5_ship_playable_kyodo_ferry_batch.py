#!/usr/bin/env python3
"""Promote verified Kyodo Ferry playable ship routes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_kyodo_ferry_batch_official.json")


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    timetable_url = "https://kyodoferry.com/schedule.html"
    local_url = "https://www.goshoura.net/timetable"
    fare_pdf = "https://kyodoferry.com/materials/170297073795701.pdf"
    return {
        "routeId": route_id,
        "routeGroupId": "mlit_map_193_070_共同フェリー_御所浦_棚底_大道",
        "operator": "共同フェリー",
        "routeName": "御所浦・棚底",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "short_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 400},
            "sourceUrls": [fare_pdf, local_url],
            "notes": (
                "Official Kyodo Ferry passenger fare PDF and Goshoura timetable page both support the adult one-way "
                "御所浦-棚底 fare. Child fares, car ferry/vehicle fares, commuter tickets, discounts, temporary "
                "GW/Obon/New Year schedules, and disruption notices are excluded."
            ),
        },
        "servicePatterns": [],
        "sourceUrls": [timetable_url, local_url, fare_pdf],
    }


def trip(route_id: str, no: int, vessel: str, origin: str, destination: str, dep: str, arr: str, note: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_daily_{no:03d}",
        "routeId": route_id,
        "operator": "共同フェリー",
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
        "sourceUrl": "https://kyodoferry.com/schedule.html",
        "notes": note,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_route_id = "mlit_map_193_070_共同フェリー_御所浦_棚底_大道_000_out"
    back_route_id = "mlit_map_193_070_共同フェリー_御所浦_棚底_大道_000_back"
    routes = [
        route(out_route_id, "御所浦", "棚底"),
        route(back_route_id, "棚底", "御所浦"),
    ]
    out_rows = [
        ("栄久丸", "07:05", "07:30", "嵐口港・横浦港・与一ヶ浦港経由"),
        ("八りゅう丸", "08:15", "08:50", "嵐口港・与一ヶ浦港経由"),
        ("しいがる", "10:15", "10:30", "直行"),
        ("八りゅう丸", "11:25", "11:55", "横浦港・与一ヶ浦港経由"),
        ("栄久丸", "12:35", "13:00", "横浦港経由"),
        ("しいがる", "14:05", "14:45", "嵐口港・与一ヶ浦港経由"),
        ("栄久丸", "15:30", "16:05", "嵐口港・横浦港・与一ヶ浦港経由"),
        ("八りゅう丸", "15:50", "16:20", "横浦港・与一ヶ浦港経由"),
        ("しいがる", "17:30", "17:50", "直行"),
        ("栄久丸", "17:45", "18:05", "直行"),
        ("八りゅう丸", "17:50", "18:20", "横浦港・与一ヶ浦港経由"),
    ]
    back_rows = [
        ("八りゅう丸", "06:40", "07:10", "与一ヶ浦港・横浦港経由"),
        ("しいがる", "07:10", "07:30", "直行"),
        ("栄久丸", "07:45", "08:20", "与一ヶ浦港・嵐口港・横浦港経由"),
        ("八りゅう丸", "09:10", "09:40", "与一ヶ浦港・横浦港経由"),
        ("八りゅう丸", "13:00", "13:30", "与一ヶ浦港・横浦港経由"),
        ("しいがる", "14:45", "15:10", "横浦港・嵐口港経由"),
        ("八りゅう丸", "16:25", "16:55", "与一ヶ浦港・横浦港経由"),
        ("栄久丸", "17:15", "17:45", "与一ヶ浦港・横浦港・嵐口港経由"),
        ("栄久丸", "18:05", "18:25", "横浦港・嵐口港経由"),
    ]
    trips: list[dict] = []
    for idx, (vessel, dep, arr, note) in enumerate(out_rows, 1):
        trips.append(trip(out_route_id, idx, vessel, "御所浦", "棚底", dep, arr, note))
    for idx, (vessel, dep, arr, note) in enumerate(back_rows, 1):
        trips.append(trip(back_route_id, idx, vessel, "棚底", "御所浦", dep, arr, note))
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "共同フェリー",
        "operatorId": "kyodo_ferry",
        "retrievedAt": retrieved_at,
        "sourceUrls": [
            "https://kyodoferry.com/schedule.html",
            "https://www.goshoura.net/timetable",
            "https://kyodoferry.com/materials/170297073795701.pdf",
        ],
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 1,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "excludedDirections": [
                "棚底-大道 MLIT split is not promoted because official current timetable is published as 御所浦-大道 via ports, without exact 棚底 segment stop times.",
                "大道-棚底 MLIT split is not promoted for the same reason.",
            ],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
