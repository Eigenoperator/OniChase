#!/usr/bin/env python3
"""Promote verified V5 ship routes toward the 400-playable target."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_to_400_batch1_official.json")


def hm(value: str) -> int:
    next_day = value.startswith("翌")
    value = value.replace("翌", "")
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute) + (24 * 60 if next_day else 0)


def route(
    route_id: str,
    operator: str,
    origin: str,
    destination: str,
    fare: int,
    urls: list[str],
    note: str,
    route_class: str = "public_ferry",
) -> dict:
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


def trip(
    route_id: str,
    no: int,
    operator: str,
    vessel: str,
    origin: str,
    destination: str,
    dep: str,
    arr: str,
    url: str,
    calendar: dict | None = None,
) -> dict:
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
        "calendar": calendar or {"type": "daily"},
        "sourceUrl": url,
    }


def add_route(
    routes: list[dict],
    trips: list[dict],
    *,
    route_id: str,
    operator: str,
    origin: str,
    destination: str,
    fare: int,
    urls: list[str],
    note: str,
    rows: list[tuple[str, str, str]],
    route_class: str = "public_ferry",
    calendar: dict | None = None,
) -> None:
    routes.append(route(route_id, operator, origin, destination, fare, urls, note, route_class))
    for idx, (dep, arr, vessel) in enumerate(rows, 1):
        trips.append(trip(route_id, idx, operator, vessel, origin, destination, dep, arr, urls[0], calendar))


def pair_rows(deps: list[str], duration_minutes: int, vessel: str) -> list[tuple[str, str, str]]:
    rows = []
    for dep in deps:
        minutes = hm(dep) + duration_minutes
        rows.append((dep, f"{minutes // 60:02d}:{minutes % 60:02d}", vessel))
    return rows


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes: list[dict] = []
    trips: list[dict] = []

    koku_time = "https://www.koku94.jp/operation"
    koku_fare = "https://www.koku94.jp/price/"
    koku_note = (
        "Official normal timetable and adult general-seat fare. The 2026-05 fuel surcharge "
        "is included: base JPY 1,200 plus passenger surcharge JPY 40. Dock timetable, "
        "observation-seat/private-room supplements, vehicles, discounts, and reservations are excluded."
    )
    add_route(
        routes,
        trips,
        route_id="koku94_saganoseki_misaki_030_out",
        operator="国道九四フェリー",
        origin="佐賀関港",
        destination="三崎港",
        fare=1240,
        urls=[koku_time, koku_fare],
        note=koku_note,
        rows=pair_rows(
            ["07:00", "08:00", "09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00", "23:00"],
            70,
            "国道九四フェリー",
        ),
    )
    add_route(
        routes,
        trips,
        route_id="koku94_saganoseki_misaki_031_back",
        operator="国道九四フェリー",
        origin="三崎港",
        destination="佐賀関港",
        fare=1240,
        urls=[koku_time, koku_fare],
        note=koku_note,
        rows=pair_rows(
            ["07:30", "08:30", "09:30", "10:30", "11:30", "12:30", "14:30", "15:30", "16:30", "17:30", "18:30", "19:30", "20:30", "21:30", "22:30", "23:30"],
            70,
            "国道九四フェリー",
        ),
    )

    shima_time = "https://www.shimatetsu.co.jp/ferry/guide/"
    shima_fuel = "https://www.shimatetsu.co.jp/upload/save/content/button/5e3fb679c7a5cd7745b596b9eae3d7f0.pdf"
    shima_note = (
        "Official 2026-03-01 to 2026-06-30 winter timetable, same departures from Kuchinotsu and Oniike. "
        "Fare includes the 2026-04 to 2026-06 passenger fuel adjustment: base JPY 500 plus JPY 50. "
        "Weekend-only extra departures, vehicles, baggage, discounts, and later seasonal tables are excluded."
    )
    shima_rows = pair_rows(
        ["07:15", "08:00", "09:00", "09:45", "10:45", "11:30", "12:30", "13:15", "14:15", "15:00", "16:00", "16:45", "17:45"],
        30,
        "フェリーくちのつ/フェリーあまくさII",
    )
    for route_id, origin, destination in [
        ("shimatetsu_kuchinotsu_oniike_066_out", "口之津港", "鬼池港"),
        ("shimatetsu_kuchinotsu_oniike_067_back", "鬼池港", "口之津港"),
    ]:
        add_route(routes, trips, route_id=route_id, operator="島原鉄道", origin=origin, destination=destination, fare=550, urls=[shima_time, shima_fuel], note=shima_note, rows=shima_rows)

    nino_url = "https://ninoshimakisen.jp/time_price"
    nino_note = "Official Ninoshima Kisen regular timetable and adult one-way passenger fare. Gakuen pier intermediate calls, New Year timetables, vehicles, baggage, commuter tickets, and discounts are excluded."
    add_route(routes, trips, route_id="ninoshima_kisen_040_out", operator="似島汽船", origin="広島港宇品", destination="似島港", fare=450, urls=[nino_url], note=nino_note, rows=pair_rows(["06:30", "07:30", "08:30", "09:30", "11:00", "12:30", "14:00", "15:30", "16:30", "17:30", "18:30", "19:30", "20:30"], 20, "似島汽船"))
    add_route(routes, trips, route_id="ninoshima_kisen_041_back", operator="似島汽船", origin="似島港", destination="広島港宇品", fare=450, urls=[nino_url], note=nino_note, rows=pair_rows(["06:00", "07:00", "08:00", "09:00", "10:15", "11:30", "13:00", "14:30", "16:00", "17:00", "18:00", "19:00", "20:00"], 20, "似島汽船"))

    st_time = "https://www.shodoshima-ferry.co.jp/timetable/"
    st_fare = "https://www.shodoshima-ferry.co.jp/fare/"
    st_note = "Official 2025-12-01 timetable and 2023-10-01 adult passenger fares. Only direct Uno-Tonosho ferry/regular passenger services are modeled; dangerous-goods-only days, vehicles, baggage, and discounts are excluded."
    add_route(routes, trips, route_id="mlit_map_193_023_小豆島豊島フェリー_宇野_小豆島_土庄_000_out", operator="小豆島豊島フェリー", origin="宇野", destination="土庄港", fare=1260, urls=[st_time, st_fare], note=st_note, rows=[("06:45", "08:14", "フェリー"), ("08:40", "09:40", "旅客船"), ("11:10", "12:39", "フェリー"), ("13:25", "14:25", "旅客船"), ("15:25", "16:54", "フェリー"), ("17:30", "18:30", "旅客船")])
    add_route(routes, trips, route_id="mlit_map_193_023_小豆島豊島フェリー_宇野_小豆島_土庄_000_back", operator="小豆島豊島フェリー", origin="土庄港", destination="宇野", fare=1260, urls=[st_time, st_fare], note=st_note, rows=[("07:35", "08:35", "旅客船"), ("08:40", "10:09", "フェリー"), ("10:30", "11:30", "旅客船"), ("13:10", "14:39", "フェリー"), ("15:50", "16:50", "旅客船"), ("17:50", "19:19", "フェリー")])

    awashima_url = "https://awashimakisen.co.jp/"
    awashima_note = "Official Awashima Kisen operating-status/timetable page for the current 2026-05 service day and adult passenger fare from the Awashima tourism access page. Vehicle fares, buses, reservations, and temporary cancellations are excluded."
    add_route(routes, trips, route_id="awashima_iwafune_022_out", operator="粟島汽船", origin="岩船港", destination="粟島港", fare=700, urls=[awashima_url, "https://awa-isle.jp/ship_timetable/"], note=awashima_note, rows=[("10:15", "11:45", "フェリーニューあわしま"), ("15:00", "16:30", "フェリーニューあわしま")])
    add_route(routes, trips, route_id="awashima_iwafune_023_back", operator="粟島汽船", origin="粟島港", destination="岩船港", fare=700, urls=[awashima_url, "https://awa-isle.jp/ship_timetable/"], note=awashima_note, rows=[("08:00", "09:30", "フェリーニューあわしま"), ("12:45", "14:15", "フェリーニューあわしま")])

    taisei_url = "https://taiseikisen.com/service/"
    taisei_note = "Official Taisei Kisen 2024-10-01 timetable and adult passenger fare matrix. Only the Hinase-Otabu playable segment is modeled; taxis, vehicles, baggage, and discounts are excluded."
    add_route(routes, trips, route_id="taisei_hinase_otabu_062_out", operator="大生汽船", origin="日生港", destination="大多府港", fare=620, urls=[taisei_url], note=taisei_note, rows=[("06:15", "06:40", "大生汽船"), ("07:30", "08:00", "大生汽船"), ("09:15", "09:47", "大生汽船"), ("12:15", "12:55", "大生汽船"), ("14:30", "15:15", "大生汽船"), ("16:40", "17:12", "大生汽船"), ("18:50", "19:20", "大生汽船")])
    add_route(routes, trips, route_id="taisei_hinase_otabu_063_back", operator="大生汽船", origin="大多府港", destination="日生港", fare=620, urls=[taisei_url], note=taisei_note, rows=[("06:45", "07:25", "大生汽船"), ("08:25", "09:05", "大生汽船"), ("10:12", "10:42", "大生汽船"), ("13:00", "13:30", "大生汽船"), ("15:45", "16:15", "大生汽船"), ("18:05", "18:35", "大生汽船")])

    hime_url = "https://www.himeshima.jp/access/"
    hime_note = "Official Himeshima village ferry timetable and adult one-way passenger fare. The winter-only suspension of the 12th trip, vehicles, bicycles, and discounts are excluded for the 2026-05 V5 service date."
    add_route(routes, trips, route_id="mlit_map_193_048_姫島村_姫島_国見_000_out", operator="姫島村", origin="姫島", destination="国見", fare=580, urls=[hime_url], note=hime_note, rows=pair_rows(["05:50", "06:55", "08:00", "09:15", "10:25", "11:35", "13:00", "14:10", "15:20", "16:30", "18:00", "19:15"], 20, "姫島村営フェリー"))
    add_route(routes, trips, route_id="mlit_map_193_048_姫島村_姫島_国見_000_back", operator="姫島村", origin="国見", destination="姫島", fare=580, urls=[hime_url], note=hime_note, rows=pair_rows(["06:20", "07:30", "08:40", "09:50", "11:00", "12:10", "13:35", "14:45", "15:55", "17:25", "18:45", "19:45"], 20, "姫島村営フェリー"))

    kyusho_time = "https://www.kyusho-ferry.co.jp/diagram/"
    kyusho_fare = "https://www.kyusho-ferry.co.jp/fare/"
    kyusho_note = "Official Kyusho Ferry normal timetable and adult passenger fare. Dock timetable, special starred peak trips, vehicles, bicycles, discounts, and the free shuttle bus are excluded."
    add_route(routes, trips, route_id="kyusho_ferry_kumamoto_shimabara_042_out", operator="九商フェリー", origin="熊本港", destination="島原港", fare=1180, urls=[kyusho_time, kyusho_fare], note=kyusho_note, rows=pair_rows(["07:00", "08:20", "09:50", "11:00", "12:20", "13:35", "15:10", "16:05", "17:45"], 60, "九商フェリー"))
    add_route(routes, trips, route_id="kyusho_ferry_kumamoto_shimabara_043_back", operator="九商フェリー", origin="島原港", destination="熊本港", fare=1180, urls=[kyusho_time, kyusho_fare], note=kyusho_note, rows=pair_rows(["07:00", "08:35", "09:40", "11:05", "12:15", "13:40", "14:50", "16:25", "17:45"], 60, "九商フェリー"))

    uwa_time = "https://www.uwajimaunyu.co.jp/timetable/?newwindow=true"
    uwa_fare = "https://www.uwajimaunyu.co.jp/sp/timetable/fare.html"
    uwa_note = "Official Uwajima Unyu timetable and 2026-04-01 to 2026-06-30 adult 2nd-class passenger fare. Cabins, vehicles, discounts, ship-rest service, and temporary inspection suspensions are excluded."
    add_route(routes, trips, route_id="uwajima_unyu_yawatahama_beppu_060_out", operator="宇和島運輸", origin="八幡浜港", destination="別府港", fare=4600, urls=[uwa_time, uwa_fare], note=uwa_note, rows=[("00:20", "03:10", "宇和島運輸フェリー"), ("06:20", "09:10", "宇和島運輸フェリー"), ("10:15", "13:05", "宇和島運輸フェリー"), ("13:00", "15:50", "宇和島運輸フェリー"), ("17:25", "20:15", "宇和島運輸フェリー"), ("20:30", "23:20", "宇和島運輸フェリー")], route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="uwajima_unyu_yawatahama_beppu_061_back", operator="宇和島運輸", origin="別府港", destination="八幡浜港", fare=4600, urls=[uwa_time, uwa_fare], note=uwa_note, rows=[("06:25", "09:10", "宇和島運輸フェリー"), ("09:45", "12:30", "宇和島運輸フェリー"), ("14:00", "16:45", "宇和島運輸フェリー"), ("16:45", "19:30", "宇和島運輸フェリー"), ("20:50", "23:35", "宇和島運輸フェリー"), ("23:50", "翌02:35", "宇和島運輸フェリー")], route_class="long_distance_public_ferry")

    otf_time = "https://www.otf.jp/english-page/"
    otf_fare = "https://www.otf.jp/fee/"
    otf_note = "Official Ocean Tokyu timetable and 2026-04 to 2026-06 adult 2nd-class shared-cabin fare including fuel adjustment. Current V5 service day uses the Monday-Thursday pattern; Friday/Sunday/holiday variants, private rooms, vehicles, bicycles, and discounts are excluded."
    weekday_calendar = {"type": "monday_to_thursday"}
    for spec in [
        ("ocean_tokyu_tokyo_tokushima_shinmoji_032_out", "東京港", "徳島港", 14300, "19:00", "翌13:20"),
        ("ocean_tokyu_tokyo_tokushima_shinmoji_034_out", "徳島港", "新門司港", 11000, "14:20", "翌05:35"),
        ("ocean_tokyu_tokyo_tokushima_shinmoji_035_back", "新門司港", "徳島港", 11000, "19:00", "翌09:20"),
        ("ocean_tokyu_tokyo_tokushima_shinmoji_033_back", "徳島港", "東京港", 14300, "11:20", "翌05:30"),
    ]:
        route_id, origin, destination, fare, dep, arr = spec
        add_route(routes, trips, route_id=route_id, operator="オーシャン東九フェリー", origin=origin, destination=destination, fare=fare, urls=[otf_time, otf_fare], note=otf_note, rows=[(dep, arr, "オーシャン東九フェリー")], route_class="long_distance_public_ferry", calendar=weekday_calendar)

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "playable_to_400_batch1",
        "operatorId": "playable_to_400_batch1",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for item in routes for url in item["fare"]["sourceUrls"]}),
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
