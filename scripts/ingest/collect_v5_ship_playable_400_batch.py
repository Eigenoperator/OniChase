#!/usr/bin/env python3
"""Promote high-frequency official ferry timetables toward the 400 sailing gate."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_400_batch_official.json")


def hm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def hhmm(minutes: int) -> str:
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


def times(rows: dict[int, list[int]]) -> list[str]:
    return [f"{hour:02d}:{minute:02d}" for hour, minutes in rows.items() for minute in minutes]


def trip(operator: str, route_id: str, no: int, origin: str, destination: str, dep: str, duration: int, source: str, calendar: str = "daily") -> dict:
    dep_min = hm_to_minutes(dep)
    arr_min = dep_min + duration
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": operator,
        "serviceNo": str(no),
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": hhmm(arr_min),
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": duration,
        "calendar": {"type": calendar},
        "sourceUrl": source,
    }


def directional_route(route_id: str, operator: str, route_name: str, origin: str, destination: str, fare: int, source_urls: list[str], *, distance_km: float | None, route_class: str, notes: str = "") -> dict:
    return {
        "routeId": route_id,
        "operator": operator,
        "routeName": route_name,
        "origin": origin,
        "destination": destination,
        "distanceKm": distance_km,
        "routeClass": route_class,
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": source_urls,
            "notes": notes or "Adult normal passenger fare only; excludes discounts, vehicles, special rooms, vehicles, and special campaigns.",
        },
        "servicePatterns": [],
    }


def add_directional_trips(trips: list[dict], operator: str, route_id: str, origin: str, destination: str, departures: list[str], duration: int, source: str, calendar: str = "daily") -> None:
    for index, dep in enumerate(departures, 1):
        trips.append(trip(operator, route_id, index, origin, destination, dep, duration, source, calendar))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes: list[dict] = []
    trips: list[dict] = []
    sources: list[str] = []

    # JR西日本宮島フェリー: official normal timetable and fare pages, about 10 minutes.
    jr_time = "https://jr-miyajimaferry.co.jp/timetable/"
    jr_fare = "https://jr-miyajimaferry.co.jp/fare/"
    sources += [jr_time, jr_fare]
    routes += [
        directional_route("jr_miyajima_046_out", "JR西日本宮島フェリー", "宮島口・宮島", "宮島口", "宮島", 300, [jr_time, jr_fare], distance_km=2.0, route_class="urban_public_ferry", notes="Adult one-way ordinary fare ¥200 plus the mandatory Miyajima visitor tax ¥100 when entering Miyajima; excludes discounts and vehicle/baggage fares."),
        directional_route("jr_miyajima_047_back", "JR西日本宮島フェリー", "宮島・宮島口", "宮島", "宮島口", 200, [jr_time, jr_fare], distance_km=2.0, route_class="urban_public_ferry", notes="Adult one-way ordinary fare ¥200; excludes Miyajima visitor tax on the return direction, discounts, and vehicle/baggage fares."),
    ]
    add_directional_trips(trips, "JR西日本宮島フェリー", "jr_miyajima_046_out", "宮島口", "宮島", times({
        6: [25], 7: [5, 40, 57], 8: [10, 25, 40, 55], 9: [10, 25, 40, 55],
        10: [10, 25, 40, 55], 11: [10, 25, 40, 55], 12: [10, 25, 40, 55],
        13: [10, 25, 40, 55], 14: [10, 25, 40, 55], 15: [10, 25, 40, 55],
        16: [10, 25, 40, 55], 17: [10, 25, 40, 55], 18: [10, 25, 45],
        19: [15, 45], 20: [27], 21: [10], 22: [0, 42],
    }), 10, jr_time)
    add_directional_trips(trips, "JR西日本宮島フェリー", "jr_miyajima_047_back", "宮島", "宮島口", times({
        5: [45], 6: [40], 7: [20, 55], 8: [10, 25, 40, 55], 9: [10, 25, 40, 55],
        10: [10, 25, 40, 55], 11: [10, 25, 40, 55], 12: [10, 25, 40, 55],
        13: [10, 25, 40, 55], 14: [10, 25, 40, 55], 15: [10, 25, 40, 55],
        16: [10, 25, 40, 55], 17: [10, 25, 40, 55], 18: [10, 25, 40],
        19: [0, 30], 20: [0, 42], 21: [25], 22: [14],
    }), 10, jr_time)

    # 宮島松大汽船: official normal passenger timetable and fare page, about 10 minutes.
    matsu_time = "https://miyajima-matsudai.co.jp/schedule.html"
    matsu_fare = "https://miyajima-matsudai.co.jp/price.html"
    sources += [matsu_time, matsu_fare]
    routes += [
        directional_route("miyajima_matsudai_048_out", "宮島松大汽船", "宮島口・宮島", "宮島口", "宮島", 300, [matsu_time, matsu_fare], distance_km=2.0, route_class="urban_public_ferry", notes="Adult one-way ordinary fare ¥200 plus the mandatory Miyajima visitor tax ¥100 when entering Miyajima; excludes discounts and vehicle/baggage fares."),
        directional_route("miyajima_matsudai_049_back", "宮島松大汽船", "宮島・宮島口", "宮島", "宮島口", 200, [matsu_time, matsu_fare], distance_km=2.0, route_class="urban_public_ferry", notes="Adult one-way ordinary fare ¥200; excludes Miyajima visitor tax on the return direction, discounts, and vehicle/baggage fares."),
    ]
    add_directional_trips(trips, "宮島松大汽船", "miyajima_matsudai_048_out", "宮島口", "宮島", times({
        7: [15, 45], 8: [0, 15, 30, 45], 9: [5, 20, 35, 50], 10: [5, 20, 35, 50],
        11: [5, 20, 35, 50], 12: [5, 20, 35, 50], 13: [10, 30, 45],
        14: [0, 15, 30, 45], 15: [0, 15, 30, 45], 16: [0, 15, 30, 45],
        17: [0, 15, 30, 45], 18: [0, 15, 30, 45], 19: [0, 15, 30], 20: [0, 35],
    }), 10, matsu_time)
    add_directional_trips(trips, "宮島松大汽船", "miyajima_matsudai_049_back", "宮島", "宮島口", times({
        7: [0, 30, 45], 8: [0, 15, 30, 45], 9: [5, 20, 35, 50], 10: [5, 20, 35, 50],
        11: [5, 20, 35, 50], 12: [5, 20, 35, 50], 13: [10, 30, 45],
        14: [0, 15, 30, 45], 15: [0, 15, 30, 45], 16: [0, 15, 30, 45],
        17: [0, 15, 30, 45], 18: [0, 15, 30, 45], 19: [0, 15, 45], 20: [15],
    }), 10, matsu_time)

    # 桜島フェリー: official weekday PDF/table linked from Kagoshima City, about 15 minutes.
    sakura_time = "https://www.city.kagoshima.lg.jp/sakurajima-ferry/koro-jikoku/timetable.html"
    sakura_pdf = "https://www.city.kagoshima.lg.jp/soumu/shichoshitu/kokusai/ja/traffic/documents/unkou_schedule.pdf"
    sakura_fare = "https://www.city.kagoshima.lg.jp/sakurajima-ferry/unchin/unchin.html"
    sources += [sakura_time, sakura_pdf, sakura_fare]
    routes += [
        directional_route("sakurajima_ferry_kagoshima_sakurajima", "鹿児島市船舶局", "鹿児島・桜島", "鹿児島港", "桜島港", 250, [sakura_time, sakura_pdf, sakura_fare], distance_km=4.0, route_class="urban_public_ferry"),
        directional_route("sakurajima_ferry_sakurajima_kagoshima", "鹿児島市船舶局", "桜島・鹿児島", "桜島港", "鹿児島港", 250, [sakura_time, sakura_pdf, sakura_fare], distance_km=4.0, route_class="urban_public_ferry"),
    ]
    add_directional_trips(trips, "鹿児島市船舶局", "sakurajima_ferry_kagoshima_sakurajima", "鹿児島港", "桜島港", times({
        4: [30], 5: [30], 6: [0, 30], 7: [0, 20, 40], 8: [0, 20, 40],
        9: [0, 20, 40], 10: [0, 20, 40], 11: [0, 20, 40], 12: [0, 20, 40],
        13: [0, 20, 40], 14: [0, 20, 40], 15: [0, 20, 40], 16: [0, 20, 40],
        17: [0, 20, 40], 18: [0, 20, 40], 19: [0, 30], 20: [0, 30],
        21: [30], 22: [30], 23: [30],
    }), 15, sakura_time, "weekday")
    add_directional_trips(trips, "鹿児島市船舶局", "sakurajima_ferry_sakurajima_kagoshima", "桜島港", "鹿児島港", times({
        4: [0], 5: [0], 6: [5, 25, 45], 7: [5, 25, 45], 8: [5, 25, 45],
        9: [5, 25, 45], 10: [5, 25, 45], 11: [5, 25, 45], 12: [5, 25, 45],
        13: [5, 25, 45], 14: [5, 25, 45], 15: [5, 25, 45], 16: [5, 25, 45],
        17: [5, 25, 45], 18: [5, 25, 45], 19: [5, 30], 20: [0],
        21: [0], 22: [0], 23: [0],
    }), 15, sakura_time, "weekday")

    # 有明フェリー: official operation timetable PDF, normal A timetable, about 45 minutes.
    ariake = "https://www.ariake-ferry.com/"
    ariake_pdf = "https://www.ariake-ferry.com/wp-content/uploads/2024/01/568672bf1610b8eb56ff45068b4a375f.pdf"
    sources += [ariake, ariake_pdf]
    routes += [
        directional_route("ariake_ferry_taira_nagasu", "有明フェリー", "多比良・長洲", "多比良港", "長洲港", 450, [ariake, ariake_pdf], distance_km=14, route_class="regional_shortcut_ferry"),
        directional_route("ariake_ferry_nagasu_taira", "有明フェリー", "長洲・多比良", "長洲港", "多比良港", 450, [ariake, ariake_pdf], distance_km=14, route_class="regional_shortcut_ferry"),
    ]
    add_directional_trips(trips, "有明フェリー", "ariake_ferry_taira_nagasu", "多比良港", "長洲港", [
        "06:00", "07:00", "08:00", "08:35", "09:15", "09:55", "10:30", "11:10", "12:00",
        "13:05", "13:55", "14:35", "15:15", "15:55", "16:35", "17:15", "18:05", "19:05", "20:00",
    ], 45, ariake_pdf)
    add_directional_trips(trips, "有明フェリー", "ariake_ferry_nagasu_taira", "長洲港", "多比良港", [
        "06:00", "07:00", "08:00", "08:55", "09:30", "10:10", "11:00", "12:05", "12:55",
        "13:35", "14:15", "14:55", "15:35", "16:15", "16:55", "17:35", "18:10", "19:05", "20:00",
    ], 45, ariake_pdf)

    # 南海フェリー: official timetable and fare pages, current normal operating timetable.
    nankai_time = "https://nankai-ferry.co.jp/timetable/"
    nankai_fare = "https://nankai-ferry.co.jp/price"
    sources += [nankai_time, nankai_fare]
    routes += [
        directional_route("nankai_ferry_wakayama_tokushima", "南海フェリー", "和歌山・徳島", "和歌山港", "徳島港", 2500, [nankai_time, nankai_fare], distance_km=61, route_class="regional_shortcut_ferry"),
        directional_route("nankai_ferry_tokushima_wakayama", "南海フェリー", "徳島・和歌山", "徳島港", "和歌山港", 2500, [nankai_time, nankai_fare], distance_km=61, route_class="regional_shortcut_ferry"),
    ]
    for no, dep, arr in [
        (2, "02:40", "04:55"), (3, "05:30", "07:35"), (4, "08:25", "10:30"), (5, "10:35", "12:50"),
        (6, "13:40", "15:55"), (7, "16:20", "18:30"), (8, "19:10", "21:25"), (9, "21:50", "00:05"),
    ]:
        trips.append(trip("南海フェリー", "nankai_ferry_wakayama_tokushima", no, "和歌山港", "徳島港", dep, (hm_to_minutes(arr) + (1440 if hm_to_minutes(arr) <= hm_to_minutes(dep) else 0)) - hm_to_minutes(dep), nankai_time))
    for no, dep, arr in [
        (2, "02:45", "05:05"), (3, "05:30", "07:50"), (4, "08:00", "10:10"), (5, "10:55", "13:05"),
        (6, "13:20", "15:40"), (7, "16:25", "18:40"), (8, "18:55", "21:15"), (9, "21:50", "00:10"),
    ]:
        trips.append(trip("南海フェリー", "nankai_ferry_tokushima_wakayama", no, "徳島港", "和歌山港", dep, (hm_to_minutes(arr) + (1440 if hm_to_minutes(arr) <= hm_to_minutes(dep) else 0)) - hm_to_minutes(dep), nankai_time))

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "playable_400_batch",
        "operatorId": "playable_ship_400_batch_1",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted(set(sources)),
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 5,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "promotionNote": "High-frequency official ferry routes promoted with explicit departure/arrival times and adult ordinary fare.",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
