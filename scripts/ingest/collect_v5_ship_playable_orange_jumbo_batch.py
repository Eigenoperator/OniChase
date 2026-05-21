#!/usr/bin/env python3
"""Promote verified Orange Ferry and Jumbo Ferry route batches."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_orange_jumbo_batch_official.json")

ORANGE_TIME = "https://www.orange-ferry.co.jp/time-table/kyuushi/yawatahama-usuki/index.html"
ORANGE_FARE = "https://www.orange-ferry.co.jp/7396.html"
JUMBO_KOBE = "https://ferry.co.jp/home/kobe-shodoshima/"
JUMBO_TAKAMATSU = "https://ferry.co.jp/home/takamatsu-shodoshima/"


def hm(value: str) -> int:
    next_day = value.startswith("翌")
    value = value.replace("翌", "")
    hour, minute = value.split(":")
    total = int(hour) * 60 + int(minute)
    if next_day:
        total += 24 * 60
    return total


def route(
    route_id: str,
    group_id: str,
    operator: str,
    route_name: str,
    origin: str,
    destination: str,
    route_class: str,
    fare_yen: int,
    sources: list[str],
    note: str,
) -> dict:
    reveal = "long_distance_reveal" if route_class == "long_distance_public_ferry" else "no_reveal"
    return {
        "routeId": route_id,
        "routeGroupId": group_id,
        "operator": operator,
        "routeName": route_name,
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": route_class,
        "revealPolicy": reveal,
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare_yen},
            "sourceUrls": sources,
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": sources,
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
    notes: str = "",
) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    if arr_min < dep_min:
        arr_min += 24 * 60
    return {
        "tripId": f"{route_id}_{calendar}_{no:03d}",
        "routeId": route_id,
        "operator": operator,
        "serviceNo": str(no),
        "vessel": vessel,
        "origin": origin,
        "destination": destination,
        "departure": dep.replace("翌", ""),
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": calendar},
        "sourceUrl": source_url,
        "notes": notes,
    }


def add_orange(routes: list[dict], trips: list[dict]) -> None:
    out_id = "kyushi_orange_yawatahama_usuki_064_out"
    back_id = "kyushi_orange_yawatahama_usuki_065_back"
    sources = [ORANGE_TIME, ORANGE_FARE]
    note = (
        "Official Orange Ferry timetable page lists the 八幡浜-臼杵 departures/arrivals. "
        "Official 2025-07-01 fare revision notice lists adult 2nd-class passenger fare as 3,600 JPY, "
        "including fuel adjustment stage 7. Child fares, cabins, vehicles, special baggage, weekend reductions, "
        "dock/inspection notices, and temporary operation status are excluded."
    )
    routes.extend([
        route(out_id, "kyushi_orange_yawatahama_usuki", "九四オレンジフェリー", "八幡浜-臼杵", "八幡浜港", "臼杵港", "regional_public_ferry", 3600, sources, note),
        route(back_id, "kyushi_orange_yawatahama_usuki", "九四オレンジフェリー", "臼杵-八幡浜", "臼杵港", "八幡浜港", "regional_public_ferry", 3600, sources, note),
    ])
    for no, (dep, arr) in enumerate([
        ("01:15", "03:40"),
        ("02:50", "05:15"),
        ("08:30", "10:55"),
        ("12:45", "15:10"),
        ("14:30", "16:55"),
        ("18:45", "21:10"),
        ("21:00", "23:25"),
    ], 1):
        trips.append(trip(out_id, "九四オレンジフェリー", no, "おれんじ九州/四国", "八幡浜港", "臼杵港", dep, arr, ORANGE_TIME))
    for no, (dep, arr) in enumerate([
        ("04:45", "07:05"),
        ("07:40", "10:00"),
        ("11:30", "13:50"),
        ("15:50", "18:10"),
        ("17:35", "19:55"),
        ("22:20", "翌00:40"),
        ("23:55", "翌02:15"),
    ], 1):
        trips.append(trip(back_id, "九四オレンジフェリー", no, "おれんじ九州/四国", "臼杵港", "八幡浜港", dep, arr, ORANGE_TIME))


def add_jumbo(routes: list[dict], trips: list[dict]) -> None:
    kobe_note = (
        "Jumbo Ferry official Kobe-Shodoshima page lists weekday timetable and adult passenger fare 1,990 JPY. "
        "For the V5 current 2026-05-21 weekday release, fuel surcharge for 4/1-6/30 is 300 JPY, so playable fare is 2,290 JPY. "
        "Night surcharge, weekend surcharge, net discounts, premium seats, vehicles, buses, and holiday/peak calendars are excluded."
    )
    takamatsu_note = (
        "Jumbo Ferry official Takamatsu-Shodoshima page lists weekday timetable and adult passenger fare 700 JPY. "
        "Net discounts, vehicles, premium seats, weekend/holiday/peak calendars, and bus connections are excluded."
    )
    routes.extend([
        route("jumbo_kobe_shodoshima_takamatsu_060_out", "jumbo_kobe_shodoshima", "ジャンボフェリー", "神戸-小豆島坂手", "神戸港", "坂手港", "regional_public_ferry", 2290, [JUMBO_KOBE], kobe_note),
        route("jumbo_kobe_shodoshima_takamatsu_061_back", "jumbo_kobe_shodoshima", "ジャンボフェリー", "小豆島坂手-神戸", "坂手港", "神戸港", "regional_public_ferry", 2290, [JUMBO_KOBE], kobe_note),
        route("jumbo_kobe_shodoshima_takamatsu_062_out", "jumbo_takamatsu_shodoshima", "ジャンボフェリー", "小豆島坂手-高松東", "坂手港", "高松東港", "regional_public_ferry", 700, [JUMBO_TAKAMATSU], takamatsu_note),
        route("jumbo_kobe_shodoshima_takamatsu_063_back", "jumbo_takamatsu_shodoshima", "ジャンボフェリー", "高松東-小豆島坂手", "高松東港", "坂手港", "regional_public_ferry", 700, [JUMBO_TAKAMATSU], takamatsu_note),
    ])
    for no, (dep, arr) in enumerate([
        ("01:00", "07:30"),
        ("08:15", "11:35"),
        ("13:00", "16:20"),
    ], 1):
        trips.append(trip("jumbo_kobe_shodoshima_takamatsu_060_out", "ジャンボフェリー", no, "りつりん2/あおい", "神戸港", "坂手港", dep, arr, JUMBO_KOBE, "weekday", "Official weekday table; 01:00 night sailing reaches 坂手 via 高松."))
    for no, (dep, arr) in enumerate([
        ("07:30", "11:00"),
        ("15:15", "18:45"),
        ("20:30", "翌00:00"),
    ], 1):
        trips.append(trip("jumbo_kobe_shodoshima_takamatsu_061_back", "ジャンボフェリー", no, "りつりん2/あおい", "坂手港", "神戸港", dep, arr, JUMBO_KOBE, "weekday"))
    for no, (dep, arr) in enumerate([
        ("11:35", "13:00"),
        ("16:20", "17:45"),
    ], 1):
        trips.append(trip("jumbo_kobe_shodoshima_takamatsu_062_out", "ジャンボフェリー", no, "りつりん2/あおい", "坂手港", "高松東港", dep, arr, JUMBO_TAKAMATSU, "weekday"))
    for no, (dep, arr) in enumerate([
        ("06:15", "07:30"),
        ("14:00", "15:15"),
        ("19:15", "20:30"),
    ], 1):
        trips.append(trip("jumbo_kobe_shodoshima_takamatsu_063_back", "ジャンボフェリー", no, "りつりん2/あおい", "高松東港", "坂手港", dep, arr, JUMBO_TAKAMATSU, "weekday"))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes: list[dict] = []
    trips: list[dict] = []
    add_orange(routes, trips)
    add_jumbo(routes, trips)
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "orange_jumbo_batch",
        "operatorId": "orange_jumbo_batch",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for item in routes for url in item["sourceUrls"]}),
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 3,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "excludedDirections": [
                "Orange Ferry Kansai routes are not promoted in this batch because May 2026 dock/temporary operation notices and fare-period calendars need a route-specific model.",
                "Jumbo Ferry weekend/holiday and peak calendars are intentionally excluded; only the V5 current weekday timetable is promoted.",
            ],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
