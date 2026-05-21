#!/usr/bin/env python3
"""Promote verified Setonaikai Kisen / Ishizaki Kisen Hiroshima-Kure-Matsuyama routes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_setonaikai_batch_official.json")
OPERATOR = "瀬戸内海汽船/石崎汽船"
ROUTE_GROUP = "setonaikai_hiroshima_kure_matsuyama"
CRUISE_URL = "https://setonaikaikisen.co.jp/kouro/cruise/"
SUPERJET_URL = "https://setonaikaikisen.co.jp/kouro/superjet/"

PORT_COORDS = {
    "広島港": [132.4550554, 34.3524545, "広島"],
    "呉港": [132.5564154, 34.2406728, "呉"],
    "松山観光港": [132.704287, 33.888602, "松山"],
}

FARES = {
    "cruise_ferry": {
        ("広島港", "松山観光港"): 5800,
        ("呉港", "松山観光港"): 4700,
        ("広島港", "呉港"): 1100,
    },
    "superjet": {
        ("広島港", "松山観光港"): 8800,
        ("呉港", "松山観光港"): 6900,
        ("広島港", "呉港"): 2800,
    },
}

CRUISE_TIMETABLE = [
    ("5:45", None, "8:12", "6:20", "8:17", "9:02"),
    ("6:45", "7:30", "9:27", "8:25", "10:22", "11:07"),
    ("8:05", "8:50", "10:47", "9:40", "11:37", "12:22"),
    ("9:15", "10:00", "11:57", "11:00", None, "13:27"),
    ("11:20", "12:05", "14:02", "12:10", "14:07", "14:52"),
    ("12:35", "13:20", "15:17", "14:15", "16:12", "16:57"),
    ("13:40", "14:25", "16:22", "15:30", "17:27", "18:12"),
    ("15:05", "15:50", "17:47", "16:35", "18:32", "19:17"),
    ("17:15", "18:00", "19:57", "18:00", "19:57", "20:42"),
    ("19:30", "20:15", "22:12", "20:10", "22:07", "22:52"),
]

SUPERJET_TIMETABLE = [
    ("7:30", None, "8:50", "7:30", None, "8:50"),
    ("9:05", "9:30", "10:35", "9:05", "10:10", "10:35"),
    ("10:50", None, "12:10", "10:50", None, "12:10"),
    ("12:25", "12:50", "13:55", "12:25", "13:30", "13:55"),
    ("15:15", None, "16:35", "15:15", None, "16:35"),
    ("16:45", "17:10", "18:15", "16:45", "17:50", "18:15"),
    ("18:30", None, "19:50", "18:30", None, "19:50"),
    ("20:00", None, "21:20", "20:00", None, "21:20"),
]


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def fare_for(mode: str, origin: str, destination: str) -> int:
    key = (origin, destination)
    reverse = (destination, origin)
    return FARES[mode].get(key) or FARES[mode][reverse]


def route_id(mode: str, origin: str, destination: str) -> str:
    names = {"広島港": "hiroshima", "呉港": "kure", "松山観光港": "matsuyama"}
    return f"{ROUTE_GROUP}_{mode}_{names[origin]}_{names[destination]}"


def route(mode: str, mode_label: str, origin: str, destination: str, source_url: str) -> dict:
    fare = fare_for(mode, origin, destination)
    note = (
        f"Official Setonaikai Kisen {mode_label} page lists the 2025-11-01 timetable and 2025-08-01 adult one-way passenger fares. "
        f"Adult ordinary fare used for {origin}-{destination} is {fare:,} JPY. "
        "Child fares, group/student/disability discounts, super seats, vehicles, baggage, bundled tickets, temporary disruption notices, and bus/tram connector timetables are excluded."
    )
    return {
        "routeId": route_id(mode, origin, destination),
        "routeGroupId": ROUTE_GROUP,
        "operator": OPERATOR,
        "routeName": f"{mode_label} {origin}-{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "regional_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": [source_url],
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": [source_url],
    }


def trip(route_id_value: str, mode_label: str, no: int, origin: str, destination: str, dep: str, arr: str, source_url: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id_value}_daily_{no:03d}",
        "routeId": route_id_value,
        "operator": OPERATOR,
        "serviceNo": str(no),
        "vessel": mode_label,
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": source_url,
    }


def add_direction_trips(
    trips: list[dict],
    mode: str,
    mode_label: str,
    source_url: str,
    no: int,
    a: str,
    b: str | None,
    c: str,
    forward: bool,
) -> None:
    if forward:
        if b:
            trips.append(trip(route_id(mode, "広島港", "呉港"), mode_label, no, "広島港", "呉港", a, b, source_url))
            trips.append(trip(route_id(mode, "呉港", "松山観光港"), mode_label, no, "呉港", "松山観光港", b, c, source_url))
        trips.append(trip(route_id(mode, "広島港", "松山観光港"), mode_label, no, "広島港", "松山観光港", a, c, source_url))
    else:
        if b:
            trips.append(trip(route_id(mode, "松山観光港", "呉港"), mode_label, no, "松山観光港", "呉港", a, b, source_url))
            trips.append(trip(route_id(mode, "呉港", "広島港"), mode_label, no, "呉港", "広島港", b, c, source_url))
        trips.append(trip(route_id(mode, "松山観光港", "広島港"), mode_label, no, "松山観光港", "広島港", a, c, source_url))


def build_mode(mode: str, mode_label: str, source_url: str, timetable: list[tuple[str, str | None, str, str, str | None, str]]) -> tuple[list[dict], list[dict]]:
    pairs = [
        ("広島港", "呉港"),
        ("呉港", "広島港"),
        ("呉港", "松山観光港"),
        ("松山観光港", "呉港"),
        ("広島港", "松山観光港"),
        ("松山観光港", "広島港"),
    ]
    routes = [route(mode, mode_label, origin, destination, source_url) for origin, destination in pairs]
    trips: list[dict] = []
    for no, (h_dep, k_arr, m_arr, m_dep, k_arr_back, h_arr) in enumerate(timetable, start=1):
        add_direction_trips(trips, mode, mode_label, source_url, no, h_dep, k_arr, m_arr, True)
        add_direction_trips(trips, mode, mode_label, source_url, no, m_dep, k_arr_back, h_arr, False)
    return routes, trips


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    cruise_routes, cruise_trips = build_mode("cruise_ferry", "クルーズフェリー", CRUISE_URL, CRUISE_TIMETABLE)
    superjet_routes, superjet_trips = build_mode("superjet", "スーパージェット", SUPERJET_URL, SUPERJET_TIMETABLE)
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": OPERATOR,
        "operatorId": "setonaikai_kisen_ishizaki",
        "retrievedAt": retrieved_at,
        "sourceUrls": [CRUISE_URL, SUPERJET_URL],
        "ports": {
            name: {
                "name": name,
                "lon": coords[0],
                "lat": coords[1],
                "city": coords[2],
                "source": "existing_v5_verified_port_coordinate",
            }
            for name, coords in PORT_COORDS.items()
        },
        "routes": cruise_routes + superjet_routes,
        "trips": cruise_trips + superjet_trips,
        "summary": {
            "routeGroupCount": 1,
            "directionalRouteCount": len(cruise_routes) + len(superjet_routes),
            "explicitTripCount": len(cruise_trips) + len(superjet_trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "excludedDirections": [
                "Older MLIT 三津浜-広島宇品 records are not promoted because current official Hiroshima/Kure-Matsuyama service uses 松山観光港.",
            ],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(payload['routes'])} trips={len(payload['trips'])} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
