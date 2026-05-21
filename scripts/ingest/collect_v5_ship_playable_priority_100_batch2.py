#!/usr/bin/env python3
"""Promote another official V5 ship batch from the remaining queue."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_priority_100_batch2_official.json")


def hm(value: str) -> int:
    next_day = value.startswith("翌")
    value = value.replace("翌", "")
    hour, minute = value.split(":")
    total = int(hour) * 60 + int(minute)
    return total + (24 * 60 if next_day else 0)


def route(route_id: str, operator: str, origin: str, destination: str, fare: int, urls: list[str], note: str, route_class: str = "public_ferry") -> dict:
    return {
        "routeId": route_id,
        "operator": operator,
        "routeName": f"{origin}・{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": route_class,
        "revealPolicy": "long_distance_reveal" if route_class == "long_distance_public_ferry" else "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": urls,
            "notes": note,
        },
        "servicePatterns": [],
    }


def trip(route_id: str, no: int, operator: str, vessel: str, origin: str, destination: str, dep: str, arr: str, url: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    if arr_min < dep_min:
        arr_min += 24 * 60
    return {
        "tripId": f"{route_id}_{no:03d}",
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
        "calendar": {"type": "daily"},
        "sourceUrl": url,
    }


def add_route_with_trips(routes: list[dict], trips: list[dict], *, route_id: str, operator: str, origin: str, destination: str, fare: int, urls: list[str], note: str, trip_rows: list[tuple[str, str, str]], route_class: str = "public_ferry") -> None:
    routes.append(route(route_id, operator, origin, destination, fare, urls, note, route_class))
    for idx, (dep, arr, vessel) in enumerate(trip_rows, 1):
        trips.append(trip(route_id, idx, operator, vessel, origin, destination, dep, arr, urls[0]))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes: list[dict] = []
    trips: list[dict] = []

    munakata_oshima_time = "https://www.city.munakata.lg.jp/kiji0034192/index.html"
    munakata_oshima_fare = "https://www.city.munakata.lg.jp/kiji0034188/index.html"
    munakata_chijima_time = "https://www.city.munakata.lg.jp/kiji0034191/index.html"
    munakata_chijima_fare = "https://www.city.munakata.lg.jp/kiji0034189/index.html"
    add_route_with_trips(
        routes, trips,
        route_id="mlit_map_193_088_宗像市_大島_神湊_地島_地島_白浜_神湊_000_back",
        operator="宗像市", origin="神湊", destination="大島港", fare=570,
        urls=[munakata_oshima_time, munakata_oshima_fare],
        note="Official Munakata Oshima ferry timetable and one-way adult passenger fare. Vehicle fares, discounts, and temporary operation notices are excluded.",
        trip_rows=[("07:40", "08:05", "フェリーおおしま"), ("09:25", "09:50", "フェリーおおしま"), ("11:15", "11:30", "旅客船しおかぜ"), ("13:50", "14:15", "フェリーおおしま"), ("15:30", "15:45", "旅客船しおかぜ"), ("17:10", "17:35", "フェリーおおしま"), ("19:00", "19:25", "フェリーおおしま")],
    )
    add_route_with_trips(
        routes, trips,
        route_id="mlit_map_193_088_宗像市_大島_神湊_地島_地島_白浜_神湊_000_out",
        operator="宗像市", origin="大島港", destination="神湊", fare=570,
        urls=[munakata_oshima_time, munakata_oshima_fare],
        note="Official Munakata Oshima ferry timetable and one-way adult passenger fare. Vehicle fares, discounts, and temporary operation notices are excluded.",
        trip_rows=[("06:50", "07:15", "フェリーおおしま"), ("08:35", "09:00", "フェリーおおしま"), ("10:15", "10:30", "旅客船しおかぜ"), ("13:00", "13:25", "フェリーおおしま"), ("14:40", "14:55", "旅客船しおかぜ"), ("16:20", "16:45", "フェリーおおしま"), ("18:00", "18:25", "フェリーおおしま")],
    )
    for route_id, origin, destination, fare, rows in [
        ("mlit_map_193_088_宗像市_大島_神湊_地島_地島_白浜_神湊_001_out", "神湊", "地島", 380, [("07:45", "08:00", "ニューじのしま"), ("10:05", "10:20", "ニューじのしま"), ("12:20", "12:35", "ニューじのしま"), ("15:10", "15:25", "ニューじのしま"), ("16:40", "16:55", "ニューじのしま"), ("18:20", "18:35", "ニューじのしま")]),
        ("mlit_map_193_088_宗像市_大島_神湊_地島_地島_白浜_神湊_002_back", "神湊", "地島", 410, [("07:45", "08:10", "ニューじのしま"), ("10:05", "10:30", "ニューじのしま"), ("12:20", "12:45", "ニューじのしま"), ("15:10", "15:35", "ニューじのしま"), ("16:40", "17:05", "ニューじのしま"), ("18:20", "18:45", "ニューじのしま")]),
        ("mlit_map_193_088_宗像市_大島_神湊_地島_地島_白浜_神湊_001_back", "地島", "神湊", 380, [("06:55", "07:10", "ニューじのしま"), ("08:50", "09:05", "ニューじのしま"), ("11:40", "11:55", "ニューじのしま"), ("14:20", "14:35", "ニューじのしま"), ("16:05", "16:20", "ニューじのしま"), ("17:40", "17:55", "ニューじのしま")]),
        ("mlit_map_193_088_宗像市_大島_神湊_地島_地島_白浜_神湊_002_out", "地島", "神湊", 410, [("06:45", "07:10", "ニューじのしま"), ("08:40", "09:05", "ニューじのしま"), ("11:30", "11:55", "ニューじのしま"), ("14:10", "14:35", "ニューじのしま"), ("15:55", "16:20", "ニューじのしま"), ("17:30", "17:55", "ニューじのしま")]),
    ]:
        add_route_with_trips(routes, trips, route_id=route_id, operator="宗像市", origin=origin, destination=destination, fare=fare, urls=[munakata_chijima_time, munakata_chijima_fare], note="Official Munakata Chijima ferry timetable and one-way adult passenger fare. The V5 map has a generalized Chijima node, so Tomari/Shirahama variants are preserved as separate MLIT directions.", trip_rows=rows)

    kyu_time = "https://www.kyu-you.co.jp/files/download/PdfFiles/3a5b7f8d-a255-43f8-8b6d-52c6b1f3b207/file/"
    kyu_fare = "https://kyu-you.co.jp/price/09.html"
    for route_id, origin, destination, fare, rows in [
        ("mlit_map_193_089_九州郵船_博多_壱岐_対馬_博多_比田勝_印通寺_唐津_000_out", "博多港", "壱岐", 3180, [("00:05", "02:15", "フェリーちくし"), ("10:00", "12:20", "フェリーきずな"), ("20:35", "22:55", "フェリーきずな")]),
        ("mlit_map_193_089_九州郵船_博多_壱岐_対馬_博多_比田勝_印通寺_唐津_000_back", "壱岐", "博多港", 3180, [("07:00", "09:25", "フェリーきずな"), ("11:10", "13:25", "フェリーちくし"), ("17:45", "20:10", "フェリーきずな")]),
        ("mlit_map_193_089_九州郵船_博多_壱岐_対馬_博多_比田勝_印通寺_唐津_001_out", "壱岐", "対馬", 3040, [("02:25", "04:45", "フェリーちくし"), ("12:35", "14:45", "フェリーきずな")]),
        ("mlit_map_193_089_九州郵船_博多_壱岐_対馬_博多_比田勝_印通寺_唐津_001_back", "対馬", "壱岐", 3040, [("08:50", "11:05", "フェリーきずな"), ("15:25", "17:30", "フェリーきずな")]),
        ("mlit_map_193_089_九州郵船_博多_壱岐_対馬_博多_比田勝_印通寺_唐津_002_out", "博多港", "比田勝", 6780, [("22:30", "翌03:25", "うみてらし")]),
        ("mlit_map_193_089_九州郵船_博多_壱岐_対馬_博多_比田勝_印通寺_唐津_002_back", "比田勝", "博多港", 6780, [("16:00", "20:55", "うみてらし")]),
        ("mlit_map_193_089_九州郵船_博多_壱岐_対馬_博多_比田勝_印通寺_唐津_003_back", "唐津港", "印通寺", 2230, [("08:40", "10:25", "エメラルドからつ"), ("10:20", "12:05", "エメラルドからつ"), ("13:20", "15:05", "エメラルドからつ"), ("15:30", "17:15", "エメラルドからつ"), ("18:20", "20:05", "エメラルドからつ")]),
        ("mlit_map_193_089_九州郵船_博多_壱岐_対馬_博多_比田勝_印通寺_唐津_003_out", "印通寺", "唐津港", 2230, [("08:20", "10:00", "エメラルドからつ"), ("10:50", "12:30", "エメラルドからつ"), ("13:20", "15:00", "エメラルドからつ"), ("15:30", "17:10", "エメラルドからつ"), ("17:30", "19:10", "エメラルドからつ")]),
    ]:
        add_route_with_trips(routes, trips, route_id=route_id, operator="九州郵船", origin=origin, destination=destination, fare=fare, urls=[kyu_time, kyu_fare], note="Official Kyushu Yusen 2026 April-June timetable PDF and adult 2nd-class fare table. Jetfoil, vehicle fares, seasonal dock substitutions, island-resident discounts, and temporary restrictions are excluded.", trip_rows=rows)

    kyusho_url = "https://kyusho.co.jp/schedule"
    for route_id, origin, destination, fare, rows in [
        ("mlit_map_193_090_九州商船_長崎_五島_佐世保_上五島_長崎_有川_000_out", "長崎港", "五島", 8900, [("07:40", "09:05", "ジェットフォイル"), ("11:30", "12:55", "ジェットフォイル"), ("14:50", "16:15", "ジェットフォイル"), ("16:30", "18:15", "高速船")]),
        ("mlit_map_193_090_九州商船_長崎_五島_佐世保_上五島_長崎_有川_000_back", "五島", "長崎港", 8900, [("07:30", "09:15", "高速船"), ("09:20", "11:05", "高速船"), ("13:40", "15:05", "ジェットフォイル"), ("16:30", "18:15", "高速船")]),
        ("mlit_map_193_090_九州商船_長崎_五島_佐世保_上五島_長崎_有川_001_out", "佐世保港", "上五島", 6400, [("08:40", "10:05", "高速船"), ("10:40", "13:15", "フェリー"), ("17:15", "18:40", "高速船")]),
        ("mlit_map_193_090_九州商船_長崎_五島_佐世保_上五島_長崎_有川_001_back", "上五島", "佐世保港", 6400, [("07:00", "08:25", "高速船"), ("13:35", "16:10", "フェリー"), ("15:00", "16:25", "高速船")]),
    ]:
        add_route_with_trips(routes, trips, route_id=route_id, operator="九州商船", origin=origin, destination=destination, fare=fare, urls=[kyusho_url], note="Official Kyusho schedule page queried for 2026-05-22 with route/date parameters; adult fare shown by the official page. Routes without current direct official results are left unpromoted.", trip_rows=rows)

    tqf_time = "https://tqf.co.jp/time_schedule/"
    tqf_fare = "https://tqf.co.jp/fare/"
    add_route_with_trips(routes, trips, route_id="tokyo_kyushu_yokosuka_shinmoji_030_out", operator="東京九州フェリー", origin="横須賀港", destination="新門司港", fare=14000, urls=[tqf_time, tqf_fare], note="Official timetable and period-A Tourist A adult base fare. Period B/C fares, cabin charges, vehicles, baggage, and discounts are excluded.", route_class="long_distance_public_ferry", trip_rows=[("23:45", "翌21:00", "はまゆう/それいゆ/すずらん")])
    add_route_with_trips(routes, trips, route_id="tokyo_kyushu_yokosuka_shinmoji_031_back", operator="東京九州フェリー", origin="新門司港", destination="横須賀港", fare=14000, urls=[tqf_time, tqf_fare], note="Official timetable and period-A Tourist A adult base fare. Period B/C fares, cabin charges, vehicles, baggage, and discounts are excluded.", route_class="long_distance_public_ferry", trip_rows=[("23:55", "翌20:45", "はまゆう/それいゆ/すずらん")])

    sukumo_url = "https://www.city.sukumo.kochi.jp/docs-05/p0325.html"
    add_route_with_trips(routes, trips, route_id="mlit_map_193_043_宿毛市_沖の島_片島_000_back", operator="宿毛市", origin="片島", destination="沖の島", fare=1350, urls=[sukumo_url], note="Official Sukumo municipal Okinoshima timetable/fare table. Intermediate ports are collapsed to the V5 generalized Okinoshima map node.", trip_rows=[("07:00", "07:50", "おきのしま"), ("14:30", "15:20", "おきのしま")])
    add_route_with_trips(routes, trips, route_id="mlit_map_193_043_宿毛市_沖の島_片島_000_out", operator="宿毛市", origin="沖の島", destination="片島", fare=1350, urls=[sukumo_url], note="Official Sukumo municipal Okinoshima timetable/fare table. Intermediate ports are collapsed to the V5 generalized Okinoshima map node.", trip_rows=[("08:35", "09:25", "おきのしま"), ("16:05", "16:55", "おきのしま")])

    sado_time = "https://www.sadokisen.co.jp/news/wp-content/uploads/sites/14/2025/11/timetable_2026.pdf"
    sado_fare = "https://www.city.sado.niigata.jp/soshiki/2016/80418.html"
    for route_id, origin, destination, fare, rows in [
        ("sadokisen_niigata_ryotsu_046_out", "新潟佐渡汽船ターミナル", "両津港", 3290, [("06:00", "08:30", "カーフェリー"), ("09:25", "11:55", "カーフェリー"), ("12:35", "15:05", "カーフェリー"), ("16:05", "18:35", "カーフェリー"), ("19:30", "22:00", "カーフェリー")]),
        ("sadokisen_niigata_ryotsu_047_back", "両津港", "新潟佐渡汽船ターミナル", 3290, [("05:30", "08:00", "カーフェリー"), ("09:15", "11:45", "カーフェリー"), ("12:45", "15:15", "カーフェリー"), ("16:05", "18:35", "カーフェリー")]),
        ("sadokisen_naoetsu_ogi_048_out", "直江津港", "小木港", 3530, [("10:35", "13:15", "カーフェリー"), ("17:25", "20:05", "カーフェリー")]),
        ("sadokisen_naoetsu_ogi_049_back", "小木港", "直江津港", 3530, [("07:10", "09:50", "カーフェリー"), ("14:00", "16:40", "カーフェリー")]),
    ]:
        add_route_with_trips(routes, trips, route_id=route_id, operator="佐渡汽船", origin=origin, destination=destination, fare=fare, urls=[sado_time, sado_fare], note="Official Sado Kisen 2026 timetable PDF and Sado City fare-change notice for adult car-ferry 2nd-class fare. Jetfoil, vehicle fares, islander discounts, and seasonal exceptions are excluded.", trip_rows=rows)

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "priority_100_batch2",
        "operatorId": "priority_100_batch2",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for route_item in routes for url in route_item["fare"]["sourceUrls"]}),
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 7,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
