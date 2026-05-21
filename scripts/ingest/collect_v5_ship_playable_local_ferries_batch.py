#!/usr/bin/env python3
"""Promote small official local-ferry timetables with adult fares."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_local_ferries_batch_official.json")


def hm(value: str) -> int:
    hour, minute = value.replace("：", ":").split(":")
    return int(hour) * 60 + int(minute)


def route(
    route_id: str,
    operator: str,
    origin: str,
    destination: str,
    fare: int,
    source: str,
    note: str,
) -> dict:
    return {
        "routeId": route_id,
        "operator": operator,
        "routeName": f"{origin}・{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "island_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": [source],
            "notes": note,
        },
        "servicePatterns": [],
    }


def trip(
    route_id: str,
    no: int,
    operator: str,
    origin: str,
    destination: str,
    dep: str,
    arr: str,
    source: str,
    calendar: str = "daily",
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
        "vessel": None,
        "origin": origin,
        "destination": destination,
        "departure": dep.replace("：", ":"),
        "arrival": f"{arr_min // 60:02d}:{arr_min % 60:02d}",
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": calendar},
        "sourceUrl": source,
    }


def add_pairs(
    trips: list[dict],
    route_id: str,
    operator: str,
    origin: str,
    destination: str,
    source: str,
    pairs: list[tuple[str, str]],
    calendar: str = "daily",
    start_no: int = 1,
) -> None:
    for offset, (dep, arr) in enumerate(pairs):
        trips.append(trip(route_id, start_no + offset, operator, origin, destination, dep, arr, source, calendar))


def jenova_times() -> dict[str, dict[str, list[str]]]:
    weekday_iwaya = {
        5: ["20"],
        6: ["40"],
        7: ["00", "20", "40"],
        8: ["00", "30"],
        9: ["00", "30"],
        10: ["00", "30"],
        11: ["10", "40"],
        12: ["30"],
        13: ["30"],
        14: ["30"],
        15: ["30"],
        16: ["20"],
        17: ["00", "40"],
        18: ["00", "20", "40"],
        19: ["00", "40"],
        20: ["20"],
        21: ["00", "40"],
        22: ["40"],
    }
    weekday_akashi = {
        6: ["05", "20"],
        7: ["00", "20", "40"],
        8: ["00", "30"],
        9: ["00", "30"],
        10: ["00", "40"],
        11: ["20"],
        12: ["00"],
        13: ["00"],
        14: ["00"],
        15: ["00", "40"],
        16: ["20", "40"],
        17: ["00", "20", "40"],
        18: ["20"],
        19: ["00", "40"],
        20: ["20"],
        21: ["20"],
        22: ["20"],
        23: ["40"],
    }
    weekend_iwaya = {
        6: ["00"],
        7: ["00"],
        8: ["00", "40"],
        9: ["20"],
        10: ["00", "40"],
        11: ["20"],
        12: ["40"],
        13: ["30"],
        14: ["30"],
        15: ["30"],
        16: ["20"],
        17: ["00", "40"],
        18: ["20"],
        19: ["00", "40"],
        20: ["20"],
        21: ["00", "40"],
        22: ["40"],
    }
    weekend_akashi = {
        6: ["30"],
        7: ["30"],
        8: ["20"],
        9: ["00", "40"],
        10: ["30"],
        11: ["20"],
        12: ["00"],
        13: ["00"],
        14: ["00"],
        15: ["00", "40"],
        16: ["20"],
        17: ["00", "40"],
        18: ["20"],
        19: ["00", "40"],
        20: ["20"],
        21: ["20"],
        22: ["20"],
        23: ["40"],
    }
    return {
        "weekday_iwaya_to_akashi": expand_minutes(weekday_iwaya),
        "weekday_akashi_to_iwaya": expand_minutes(weekday_akashi),
        "weekend_iwaya_to_akashi": expand_minutes(weekend_iwaya),
        "weekend_akashi_to_iwaya": expand_minutes(weekend_akashi),
    }


def expand_minutes(rows: dict[int, list[str]]) -> list[str]:
    return [f"{hour:02d}:{minute}" for hour, minutes in rows.items() for minute in minutes]


def with_duration(deps: list[str], minutes: int) -> list[tuple[str, str]]:
    pairs = []
    for dep in deps:
        total = hm(dep) + minutes
        pairs.append((dep, f"{total // 60:02d}:{total % 60:02d}"))
    return pairs


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes = []
    trips: list[dict] = []

    honjima_source = "https://honjima-kisen.com/about/"
    honjima_note = "Official adult one-way passenger fare 丸亀-本島 ¥560. Excludes child fares, round trips, commuter passes, vehicle/bicycle fares, discounts, and special tickets."
    routes += [
        route("mlit_map_193_027_本島汽船_本島_丸亀_000_out", "本島汽船", "本島", "丸亀", 560, honjima_source, honjima_note),
        route("mlit_map_193_027_本島汽船_本島_丸亀_000_back", "本島汽船", "丸亀", "本島", 560, honjima_source, honjima_note),
    ]
    add_pairs(trips, routes[-2]["routeId"], "本島汽船", "本島", "丸亀", honjima_source, [
        ("06:50", "07:20"), ("08:30", "08:50"), ("09:40", "10:10"), ("12:35", "13:05"),
        ("14:15", "14:35"), ("17:10", "17:40"), ("17:50", "18:10"), ("19:30", "19:50"),
    ])
    add_pairs(trips, routes[-1]["routeId"], "本島汽船", "丸亀", "本島", honjima_source, [
        ("06:10", "06:45"), ("07:40", "08:15"), ("10:40", "11:15"), ("12:10", "12:30"),
        ("15:30", "16:05"), ("16:30", "16:50"), ("18:15", "18:35"), ("20:00", "20:20"),
    ])

    atata_source = "https://atatajimakisen.sakura.ne.jp/timetable/"
    atata_note = "Official adult ordinary one-way passenger fare ¥710. Excludes child fares, books of tickets, commuter passes, vehicles, baggage, discounts, and New Year special timetable."
    routes += [
        route("atata_ogata_048_out", "阿多田島汽船", "阿多田港", "小方港", 710, atata_source, atata_note),
        route("atata_ogata_049_back", "阿多田島汽船", "小方港", "阿多田港", 710, atata_source, atata_note),
    ]
    add_pairs(trips, routes[-2]["routeId"], "阿多田島汽船", "阿多田港", "小方港", atata_source, [
        ("06:00", "06:35"), ("07:30", "08:05"), ("12:30", "13:05"), ("15:50", "16:25"), ("18:00", "18:35"),
    ])
    add_pairs(trips, routes[-1]["routeId"], "阿多田島汽船", "小方港", "阿多田港", atata_source, [
        ("06:45", "07:20"), ("09:30", "10:05"), ("14:40", "15:15"), ("17:15", "17:50"), ("18:45", "19:20"),
    ])

    tanaka_source = "https://tanakayuso.co.jp/timetable-fares/"
    tanaka_note = "Official adult one-way passenger fare ¥710. Excludes child fares, round trips, excursion tickets, baggage, vehicles, discounts, and the second/fourth Sunday third-trip suspension."
    routes += [
        route("mlit_map_193_040_田中輸送_大島_八幡浜_000_out", "田中輸送", "大島港", "八幡浜港", 710, tanaka_source, tanaka_note),
        route("mlit_map_193_040_田中輸送_大島_八幡浜_000_back", "田中輸送", "八幡浜港", "大島港", 710, tanaka_source, tanaka_note),
    ]
    add_pairs(trips, routes[-2]["routeId"], "田中輸送", "大島港", "八幡浜港", tanaka_source, [
        ("07:30", "07:55"), ("14:00", "14:25"), ("16:40", "17:05"),
    ])
    add_pairs(trips, routes[-1]["routeId"], "田中輸送", "八幡浜港", "大島港", tanaka_source, [
        ("06:50", "07:15"), ("11:30", "11:55"), ("16:00", "16:25"),
    ])

    jenova_source = "https://www.jenova-line.co.jp/jikoku.php"
    jenova_note = "Official 2025-01-01 adult one-way passenger fare 明石-岩屋 ¥700. Excludes child fares, books of tickets, commuter passes, bicycle/motorcycle fares, discounts, and temporary schedules."
    routes += [
        route("awaji_jenova_akashi_iwaya_026_out", "淡路ジェノバライン", "明石港", "岩屋港", 700, jenova_source, jenova_note),
        route("awaji_jenova_akashi_iwaya_027_back", "淡路ジェノバライン", "岩屋港", "明石港", 700, jenova_source, jenova_note),
    ]
    times = jenova_times()
    add_pairs(trips, routes[-2]["routeId"], "淡路ジェノバライン", "明石港", "岩屋港", jenova_source, with_duration(times["weekday_akashi_to_iwaya"], 13), "weekday")
    add_pairs(trips, routes[-1]["routeId"], "淡路ジェノバライン", "岩屋港", "明石港", jenova_source, with_duration(times["weekday_iwaya_to_akashi"], 13), "weekday")
    add_pairs(trips, routes[-2]["routeId"], "淡路ジェノバライン", "明石港", "岩屋港", jenova_source, with_duration(times["weekend_akashi_to_iwaya"], 13), "weekend_holiday", 100)
    add_pairs(trips, routes[-1]["routeId"], "淡路ジェノバライン", "岩屋港", "明石港", jenova_source, with_duration(times["weekend_iwaya_to_akashi"], 13), "weekend_holiday", 100)

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "local_ferry_batch",
        "operatorId": "local_ferry_batch",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for item in routes for url in item["fare"]["sourceUrls"]}),
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 4,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
