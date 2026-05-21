#!/usr/bin/env python3
"""Promote small verified ferry batches while excluding suspended/ambiguous legs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_verified_short_batch_official.json")


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def route(
    route_id: str,
    operator: str,
    origin: str,
    destination: str,
    fare_yen: int,
    source_urls: list[str],
    note: str,
    route_class: str = "short_public_ferry",
) -> dict:
    return {
        "routeId": route_id,
        "operator": operator,
        "routeName": f"{origin}・{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": route_class,
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare_yen},
            "sourceUrls": source_urls,
            "notes": note,
        },
        "servicePatterns": [],
    }


def trip(
    route_id: str,
    operator: str,
    no: int,
    vessel: str,
    origin: str,
    destination: str,
    dep: str,
    arr: str,
    source_url: str,
    calendar: str = "daily",
) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_{calendar}_{no:03d}",
        "routeId": route_id,
        "operator": operator,
        "serviceNo": str(no),
        "vessel": vessel,
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": calendar},
        "sourceUrl": source_url,
    }


def add_pairs(
    trips: list[dict],
    route_id: str,
    operator: str,
    vessel: str,
    origin: str,
    destination: str,
    pairs: list[tuple[str, str]],
    source_url: str,
    calendar: str = "daily",
    start_no: int = 1,
) -> None:
    for offset, (dep, arr) in enumerate(pairs):
        trips.append(trip(route_id, operator, start_no + offset, vessel, origin, destination, dep, arr, source_url, calendar))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    cosmo_url = "https://cosmoline.jp/guide"
    shimanami_url = "https://habushosen.jp/timetable/timetable04/"
    cosmo_note = (
        "Official Cosmo Line guide page. Promotes only the ferry Princess Wakasa 鹿児島南埠頭-種子島西之表 "
        "leg because the current official Cosmo Line page gives explicit daily ferry times and adult standard "
        "2nd-class fare. 宮之浦/Yakushima-related queue entries are excluded here because they belong to a "
        "different high-speed service/source model. Child/islander/student/group fares, special rooms, vehicles, "
        "baggage, pets, fuel-change notices after retrieval, and temporary dock cancellations are excluded."
    )
    shimanami_note = (
        "Official Habu Shosen Group timetable04 page for Shimanami Kaiun 明石-小長. Adult passenger fare is 370 JPY. "
        "The first weekday-only sailing in each direction is marked ◇ and uses weekday calendar. "
        "The separate 竹原-大長 route is explicitly marked suspended on the operator page and is not promoted. "
        "Child fares, commuter tickets, vehicle fares, bicycle/small baggage, discounts, and disruption notices are excluded."
    )
    routes = [
        route("cosmo_kagoshima_tanegashima_yakushima_068_out", "コスモライン", "鹿児島港", "西之表港", 6000, [cosmo_url], cosmo_note, "intercity_public_ferry"),
        route("cosmo_kagoshima_tanegashima_yakushima_069_back", "コスモライン", "西之表港", "鹿児島港", 6000, [cosmo_url], cosmo_note, "intercity_public_ferry"),
        route("mlit_map_193_017_しまなみ海運_竹原_大長_明石_小長_001_out", "しまなみ海運", "明石", "小長", 370, [shimanami_url], shimanami_note),
        route("mlit_map_193_017_しまなみ海運_竹原_大長_明石_小長_001_back", "しまなみ海運", "小長", "明石", 370, [shimanami_url], shimanami_note),
    ]
    trips: list[dict] = [
        trip(routes[0]["routeId"], "コスモライン", 1, "プリンセスわかさ", "鹿児島港", "西之表港", "08:40", "12:10", cosmo_url),
        trip(routes[1]["routeId"], "コスモライン", 2, "プリンセスわかさ", "西之表港", "鹿児島港", "13:45", "17:25", cosmo_url),
    ]
    add_pairs(trips, routes[2]["routeId"], "しまなみ海運", "第五かんおん", "明石", "小長", [("06:37", "06:52")], shimanami_url, "weekday")
    add_pairs(trips, routes[3]["routeId"], "しまなみ海運", "第五かんおん", "小長", "明石", [("06:20", "06:35")], shimanami_url, "weekday")
    add_pairs(
        trips,
        routes[2]["routeId"],
        "しまなみ海運",
        "第五かんおん",
        "明石",
        "小長",
        [
            ("07:12", "07:27"),
            ("07:47", "08:02"),
            ("09:02", "09:17"),
            ("10:17", "10:32"),
            ("11:47", "12:02"),
            ("13:17", "13:32"),
            ("14:47", "15:02"),
            ("16:17", "16:32"),
            ("17:47", "18:02"),
            ("18:47", "19:02"),
            ("19:47", "20:02"),
        ],
        shimanami_url,
        start_no=2,
    )
    add_pairs(
        trips,
        routes[3]["routeId"],
        "しまなみ海運",
        "第五かんおん",
        "小長",
        "明石",
        [
            ("06:55", "07:10"),
            ("07:30", "07:45"),
            ("08:45", "09:00"),
            ("10:00", "10:15"),
            ("11:30", "11:45"),
            ("13:00", "13:15"),
            ("14:30", "14:45"),
            ("16:00", "16:15"),
            ("17:30", "17:45"),
            ("18:30", "18:45"),
            ("19:30", "19:45"),
        ],
        shimanami_url,
        start_no=2,
    )
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "verified_short_batch",
        "operatorId": "verified_short_batch",
        "retrievedAt": retrieved_at,
        "sourceUrls": [cosmo_url, shimanami_url],
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 2,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "excludedDirections": ["竹原-大長 suspended", "大長-竹原 suspended", "西之表-宮之浦 source-model pending", "宮之浦-西之表 source-model pending"],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
