#!/usr/bin/env python3
"""Promote verified Tsuyoshi/Tsuyoshi Shosen playable ship routes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_tsuyoshi_batch_official.json")
SOURCE_URLS = [
    "https://www.nomo.co.jp/tsuyoshi/tsuyoshi/",
    "https://www.city.hirado.nagasaki.jp/kurashi/life/sumai/koutu/ferry/fe04.html",
]


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, origin: str, destination: str, fare: int) -> dict:
    return {
        "routeId": route_id,
        "routeGroupId": "mlit_map_193_080_津吉商船_津吉_相浦_佐世保",
        "operator": "津吉商船",
        "routeName": "つよし",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "short_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": SOURCE_URLS,
            "notes": "Official Tsuyoshi Shosen/Nomo group and Hirado City pages. Adult one-way fare only; child, round-trip, disability, group, bicycle, cargo, and disruption handling are excluded.",
        },
        "servicePatterns": [],
        "sourceUrls": SOURCE_URLS,
    }


def trip(route_id: str, no: int, origin: str, destination: str, dep: str, arr: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_daily_{no:03d}",
        "routeId": route_id,
        "operator": "津吉商船",
        "serviceNo": str(no),
        "vessel": "つよし",
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily", "except": ["jan_1"]},
        "sourceUrl": SOURCE_URLS[0],
        "notes": "Operator page notes Jan 1 suspension and possible weather/temporary operation changes.",
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    ids = {
        ("津吉", "相浦"): "mlit_map_193_080_津吉商船_津吉_相浦_佐世保_000_out",
        ("相浦", "佐世保港"): "mlit_map_193_080_津吉商船_津吉_相浦_佐世保_001_out",
    }
    routes = [
        route(ids[("津吉", "相浦")], "津吉", "相浦", 1130),
        route(ids[("相浦", "佐世保港")], "相浦", "佐世保港", 1050),
    ]
    trips = [
        trip(ids[("津吉", "相浦")], 1, "津吉", "相浦", "07:40", "08:10"),
        trip(ids[("相浦", "佐世保港")], 1, "相浦", "佐世保港", "08:12", "08:47"),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "津吉商船",
        "operatorId": "tsuyoshi_shosen",
        "retrievedAt": retrieved_at,
        "sourceUrls": SOURCE_URLS,
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 1,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "excludedDirections": [
                "佐世保港-相浦 and 相浦-津吉 reverse split routes are not promoted because the official reverse timetable is published as 佐世保-前津吉 without explicit 相浦 stop times.",
                "Later outbound 津吉-佐世保 direct sailings are not split through 相浦 because the official table does not publish intermediate stop times.",
            ],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
