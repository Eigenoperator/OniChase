#!/usr/bin/env python3
"""Promote verified Ozu Aoshima-Kaiun Nagahama-Aoshima route."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_aoshima_batch_official.json")
SOURCE_URL = "https://www.city.ozu.ehime.jp/soshiki/nagahamash/0375.html"
OPERATOR = "青島海運"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str) -> dict:
    note = (
        "Official Ozu city page lists year-round Aoshima passenger ship timetable and fare table. "
        "Adult one-way fare is 700 JPY. "
        "Child fares, round-trip fares, baggage charges, disability refunds/discounts, weather disruption rules, and passenger-capacity restrictions are excluded."
    )
    return {
        "routeId": route_id,
        "routeGroupId": "mlit_map_193_036_青島海運_青島_長浜",
        "operator": OPERATOR,
        "routeName": f"{origin}-{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "regional_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": 700},
            "sourceUrls": [SOURCE_URL],
            "notes": note,
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
        "operator": OPERATOR,
        "serviceNo": str(no),
        "vessel": "あおしま",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": SOURCE_URL,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    out_id = "mlit_map_193_036_青島海運_青島_長浜_000_back"
    back_id = "mlit_map_193_036_青島海運_青島_長浜_000_out"
    routes = [
        route(out_id, "長浜港", "青島"),
        route(back_id, "青島", "長浜港"),
    ]
    trips = [
        trip(out_id, 1, "長浜港", "青島", "08:00", "08:35"),
        trip(back_id, 1, "青島", "長浜港", "08:45", "09:20"),
        trip(out_id, 2, "長浜港", "青島", "14:30", "15:05"),
        trip(back_id, 2, "青島", "長浜港", "16:15", "16:50"),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": OPERATOR,
        "operatorId": "aoshima_kaiun",
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
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
