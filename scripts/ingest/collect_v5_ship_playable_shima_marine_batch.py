#!/usr/bin/env python3
"""Promote verified Shima Marine Leisure Ago Bay regular ship routes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_shima_marine_batch_official.json")
SOURCE_URL = "https://shima-marineleisure.com/ago"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    return {
        "routeId": route_id,
        "routeGroupId": "shima_wagu_kashikojima",
        "operator": "志摩マリンレジャー",
        "routeName": "あご湾定期船",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "short_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 800},
            "sourceUrls": [SOURCE_URL],
            "notes": "Official Ago Bay regular ship page. Adult fare for 賢島-和具 only; child fares, group/disability discounts, pets, bicycles, and disruption notices are excluded.",
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
        "operator": "志摩マリンレジャー",
        "serviceNo": str(no),
        "vessel": "あご湾定期船",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": SOURCE_URL,
        "notes": "Via 間崎. Operator asks passengers to arrive 15 minutes before departure.",
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "shima_wagu_kashikojima_028_out"
    back_id = "shima_wagu_kashikojima_029_back"
    routes = [
        route(out_id, "和具港", "賢島港"),
        route(back_id, "賢島港", "和具港"),
    ]
    trips: list[dict] = []
    for idx, (dep, arr) in enumerate([
        ("06:35", "07:00"),
        ("07:35", "08:00"),
        ("08:35", "09:00"),
        ("10:15", "10:40"),
        ("11:10", "11:35"),
        ("13:05", "13:30"),
        ("15:15", "15:40"),
        ("16:10", "16:35"),
        ("17:05", "17:30"),
    ], 1):
        trips.append(trip(out_id, idx, "和具港", "賢島港", dep, arr))
    for idx, (dep, arr) in enumerate([
        ("07:10", "07:35"),
        ("08:10", "08:35"),
        ("09:50", "10:15"),
        ("10:45", "11:10"),
        ("12:40", "13:05"),
        ("14:50", "15:15"),
        ("15:45", "16:10"),
        ("16:40", "17:05"),
        ("17:30", "17:55"),
    ], 1):
        trips.append(trip(back_id, idx, "賢島港", "和具港", dep, arr))
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "志摩マリンレジャー",
        "operatorId": "shima_marine_leisure",
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
            "excludedDirections": ["賢島-間崎 and 間崎-和具 partial legs are not promoted because current queue route IDs are the full 和具-賢島 pair."],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
