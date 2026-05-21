#!/usr/bin/env python3
"""Promote verified Kaminoseki Koun Iwaishima route batch."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_kaminoseki_iwaishima_batch_official.json")
SOURCE_URL = "https://www.town.kaminoseki.lg.jp/wp-content/uploads/2024/09/iwaisimaunntinn20191001.pdf"
PAGE_URL = "https://www.town.kaminoseki.lg.jp/%E9%9B%A2%E5%B3%B6%E8%88%AA%E8%B7%AF.html"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str, fare_yen: int) -> dict:
    note = (
        "Official Kaminoseki Town離島航路 page links the 2019-10-01 revised Iwaishima-Yanai timetable/fare PDF. "
        "Only trips that explicitly stop at both route endpoints are promoted. "
        "Adult ordinary fares are taken from the same official PDF: 柳井港-上関 880 JPY and 上関-祝島 930 JPY. "
        "Child fares, intermediate-only legs, New Year suspension, disruption/Facebook status, and boarding-procedure notes are excluded."
    )
    return {
        "routeId": route_id,
        "routeGroupId": "kaminoseki_iwaishima",
        "operator": "上関航運",
        "routeName": f"{origin}-{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "regional_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare_yen},
            "sourceUrls": [PAGE_URL, SOURCE_URL],
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": [PAGE_URL, SOURCE_URL],
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_daily_{no:03d}",
        "routeId": route_id,
        "operator": "上関航運",
        "serviceNo": str(no),
        "vessel": "いわい",
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
    routes = [
        route("kaminoseki_iwaishima_070_out", "柳井港", "上関港", 880),
        route("kaminoseki_iwaishima_071_back", "上関港", "柳井港", 880),
        route("kaminoseki_iwaishima_072_out", "上関港", "祝島港", 930),
        route("kaminoseki_iwaishima_073_back", "祝島港", "上関港", 930),
    ]
    trips = [
        trip(routes[0]["routeId"], 1, "柳井港", "上関港", "09:30", "10:05"),
        trip(routes[0]["routeId"], 2, "柳井港", "上関港", "15:45", "16:20"),
        trip(routes[1]["routeId"], 1, "上関港", "柳井港", "07:20", "07:55"),
        trip(routes[1]["routeId"], 2, "上関港", "柳井港", "13:05", "13:40"),
        trip(routes[2]["routeId"], 1, "上関港", "祝島港", "10:05", "10:40"),
        trip(routes[2]["routeId"], 2, "上関港", "祝島港", "16:20", "16:55"),
        trip(routes[3]["routeId"], 1, "祝島港", "上関港", "06:45", "07:20"),
        trip(routes[3]["routeId"], 2, "祝島港", "上関港", "12:30", "13:05"),
        trip(routes[3]["routeId"], 3, "祝島港", "上関港", "17:05", "17:40"),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "上関航運",
        "operatorId": "kaminoseki_iwaishima",
        "retrievedAt": retrieved_at,
        "sourceUrls": [PAGE_URL, SOURCE_URL],
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 1,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "excludedDirections": ["Intermediate-only 室津/蒲井/四代 legs are not promoted in this endpoint route batch."],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
