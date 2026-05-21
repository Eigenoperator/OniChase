#!/usr/bin/env python3
"""Promote remaining Setouchi Sea Line directions from official pages."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_setonaikai_remaining_batch_official.json")
OPERATOR = "瀬戸内シーライン"


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(route_id, origin, destination, fare, source):
    note = (
        "Official Setonaikai Kisen/Setouchi Sea Line timetable and fare pages list explicit departure/arrival times and adult one-way fares. "
        "V5 promotes representative current daily/seasonal public sailings; discounts, commuter passes, vehicles, and disruption notices are excluded."
    )
    return {
        "routeId": route_id,
        "routeGroupId": "mlit_map_193_016_瀬戸内シーライン_広島_宮島_宇品_小用_小用_呉中央_宇品_高田_中町_三高_宇品",
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
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": [source],
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": [source],
    }


def trip(route_id, no, origin, destination, dep, arr, source, vessel="高速船"):
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_daily_{no:03d}",
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
        "sourceUrl": source,
    }


def main() -> None:
    sources = {
        "miyajima": "https://setonaikaikisen.co.jp/kouro/highspeedship/",
        "koyo_hiroshima": "https://setonaikaikisen.co.jp/kouro/highspeedship2/",
        "koyo_kure": "https://setonaikaikisen.co.jp/kouro/highspeedship3/",
        "takamachi": "https://setonaikaikisen.co.jp/kouro/highspeedship4/",
        "mitaka": "https://setonaikaikisen.co.jp/kouro/ferry/",
    }
    specs = [
        ("mlit_map_193_016_瀬戸内シーライン_広島_宮島_宇品_小用_小用_呉中央_宇品_高田_中町_三高_宇品_000_out", "広島港宇品", "宮島", 2300, "08:25", "08:57", sources["miyajima"], "高速船"),
        ("mlit_map_193_016_瀬戸内シーライン_広島_宮島_宇品_小用_小用_呉中央_宇品_高田_中町_三高_宇品_000_back", "宮島", "広島港宇品", 2300, "09:00", "09:31", sources["miyajima"], "高速船"),
        ("mlit_map_193_016_瀬戸内シーライン_広島_宮島_宇品_小用_小用_呉中央_宇品_高田_中町_三高_宇品_001_out", "広島港宇品", "小用", 1080, "06:46", "07:07", sources["koyo_hiroshima"], "高速船"),
        ("mlit_map_193_016_瀬戸内シーライン_広島_宮島_宇品_小用_小用_呉中央_宇品_高田_中町_三高_宇品_001_back", "小用", "広島港宇品", 1080, "06:16", "06:44", sources["koyo_hiroshima"], "高速船"),
        ("mlit_map_193_016_瀬戸内シーライン_広島_宮島_宇品_小用_小用_呉中央_宇品_高田_中町_三高_宇品_002_out", "小用", "呉中央", 650, "05:50", "06:00", sources["koyo_kure"], "高速船"),
        ("mlit_map_193_016_瀬戸内シーライン_広島_宮島_宇品_小用_小用_呉中央_宇品_高田_中町_三高_宇品_002_back", "呉中央", "小用", 650, "06:03", "06:13", sources["koyo_kure"], "高速船"),
        ("mlit_map_193_016_瀬戸内シーライン_広島_宮島_宇品_小用_小用_呉中央_宇品_高田_中町_三高_宇品_003_out", "広島港宇品", "高田", 1080, "06:19", "06:41", sources["takamachi"], "高速船"),
        ("mlit_map_193_016_瀬戸内シーライン_広島_宮島_宇品_小用_小用_呉中央_宇品_高田_中町_三高_宇品_003_back", "高田", "広島港宇品", 1080, "05:54", "06:17", sources["takamachi"], "高速船"),
        ("mlit_map_193_016_瀬戸内シーライン_広島_宮島_宇品_小用_小用_呉中央_宇品_高田_中町_三高_宇品_004_out", "高田", "中町", 150, "06:41", "06:48", sources["takamachi"], "高速船"),
        ("mlit_map_193_016_瀬戸内シーライン_広島_宮島_宇品_小用_小用_呉中央_宇品_高田_中町_三高_宇品_004_back", "中町", "高田", 150, "05:47", "05:54", sources["takamachi"], "高速船"),
        ("mlit_map_193_016_瀬戸内シーライン_広島_宮島_宇品_小用_小用_呉中央_宇品_高田_中町_三高_宇品_005_out", "三高", "広島港宇品", 690, "06:05", "06:45", sources["mitaka"], "フェリー"),
        ("mlit_map_193_016_瀬戸内シーライン_広島_宮島_宇品_小用_小用_呉中央_宇品_高田_中町_三高_宇品_005_back", "広島港宇品", "三高", 690, "06:53", "07:33", sources["mitaka"], "フェリー"),
    ]
    routes = [route(route_id, origin, dest, fare, source) for route_id, origin, dest, fare, _dep, _arr, source, _vessel in specs]
    trips = [trip(route_id, i, origin, dest, dep, arr, source, vessel) for i, (route_id, origin, dest, _fare, dep, arr, source, vessel) in enumerate(specs, 1)]
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": OPERATOR,
        "operatorId": "setouchi_sea_line_remaining",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted(sources.values()),
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
