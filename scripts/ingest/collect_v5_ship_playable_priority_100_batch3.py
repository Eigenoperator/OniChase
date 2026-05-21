#!/usr/bin/env python3
"""Promote the final slice of the current V5 ship priority-100 queue."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_priority_100_batch3_official.json")


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


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes: list[dict] = []
    trips: list[dict] = []

    taiko_time = "https://www.nomo.co.jp/taiko/timetable.html"
    taiko_fare = "https://www.nomo.co.jp/taiko/wp-content/uploads/sites/2/fare_20241024.pdf"
    taiko_note = "Official Nomo Shosen Ferry Taiko timetable and adult passenger fare table. Cabin charges, vehicles, baggage, discounts, reservations, operation calendar suspensions, and dock-period changes are excluded."
    taiko_urls = [taiko_time, taiko_fare]
    for route_id, origin, destination, fare, rows in [
        ("mlit_map_193_085_野母商船_福江_青方_博多_長崎_伊王島_高島_000_out", "福江港", "青方", 1660, [("10:10", "13:00", "太古")]),
        ("mlit_map_193_085_野母商船_福江_青方_博多_長崎_伊王島_高島_000_back", "青方", "福江港", 1660, [("06:05", "08:15", "太古")]),
        ("mlit_map_193_085_野母商船_福江_青方_博多_長崎_伊王島_高島_001_out", "青方", "博多港", 4370, [("13:10", "17:50", "太古")]),
        ("mlit_map_193_085_野母商船_福江_青方_博多_長崎_伊王島_高島_001_back", "博多港", "青方", 4370, [("23:45", "翌05:40", "太古")]),
    ]:
        add_route(routes, trips, route_id=route_id, operator="野母商船", origin=origin, destination=destination, fare=fare, urls=taiko_urls, note=taiko_note, rows=rows, route_class="long_distance_public_ferry")

    takasu_url = "https://www.nomo.co.jp/nomo/takasu-shunkan/"
    takasu_fare_pdf = "https://www.nomo.co.jp/wp-content/uploads/c3d99798463a27dd6858ea9bbaee3494.pdf"
    takasu_note = "Official Nomo Shosen Takasu/Shunkan timetable and 2025-09-01 adult passenger fare table. Discounts, baggage, temporary cancellations, and special operation notices are excluded."
    takasu_urls = [takasu_url, takasu_fare_pdf]
    for route_id, origin, destination, fare, rows in [
        ("mlit_map_193_085_野母商船_福江_青方_博多_長崎_伊王島_高島_002_out", "長崎港", "伊王島", 710, [("05:50", "06:11", "鷹巢/俊寛"), ("07:20", "07:42", "鷹巢/俊寛"), ("08:50", "09:12", "鷹巢/俊寛"), ("11:50", "12:15", "鷹巢/俊寛"), ("14:20", "14:43", "鷹巢/俊寛"), ("17:15", "17:42", "鷹巢/俊寛"), ("19:20", "19:42", "鷹巢/俊寛"), ("21:05", "21:27", "鷹巢/俊寛")]),
        ("mlit_map_193_085_野母商船_福江_青方_博多_長崎_伊王島_高島_002_back", "伊王島", "長崎港", 710, [("06:45", "07:04", "鷹巢/俊寛"), ("08:15", "08:34", "鷹巢/俊寛"), ("09:47", "10:06", "鷹巢/俊寛"), ("12:55", "13:14", "鷹巢/俊寛"), ("15:17", "15:36", "鷹巢/俊寛"), ("18:16", "18:35", "鷹巢/俊寛"), ("20:30", "20:49", "鷹巢/俊寛"), ("21:57", "22:16", "鷹巢/俊寛")]),
        ("mlit_map_193_085_野母商船_福江_青方_博多_長崎_伊王島_高島_003_out", "伊王島", "高島港", 430, [("06:11", "06:23", "鷹巢/俊寛"), ("07:42", "07:54", "鷹巢/俊寛"), ("09:12", "09:24", "鷹巢/俊寛"), ("12:15", "12:27", "鷹巢/俊寛"), ("14:43", "14:55", "鷹巢/俊寛"), ("17:42", "17:54", "鷹巢/俊寛"), ("19:42", "19:54", "鷹巢/俊寛"), ("21:27", "21:39", "鷹巢/俊寛")]),
        ("mlit_map_193_085_野母商船_福江_青方_博多_長崎_伊王島_高島_003_back", "高島港", "伊王島", 430, [("06:27", "06:45", "鷹巢/俊寛"), ("08:00", "08:15", "鷹巢/俊寛"), ("09:30", "09:47", "鷹巢/俊寛"), ("12:40", "12:55", "鷹巢/俊寛"), ("15:00", "15:17", "鷹巢/俊寛"), ("18:00", "18:16", "鷹巢/俊寛"), ("20:15", "20:30", "鷹巢/俊寛"), ("21:42", "21:57", "鷹巢/俊寛")]),
    ]:
        add_route(routes, trips, route_id=route_id, operator="野母商船", origin=origin, destination=destination, fare=fare, urls=takasu_urls, note=takasu_note, rows=rows)

    setouchi_time = "https://www.town.setouchi.lg.jp/senpaku/jikokuhyou.html"
    setouchi_fare = "https://www.town.setouchi.lg.jp/senpaku/ferrykakeroma_fare.html"
    setouchi_note = "Official Setouchi Town Ferry Kakeroma timetable and adult one-way passenger fare. Islander discounts, vehicle fares, baggage, replacement-vessel notices, and temporary cancellations are excluded."
    setouchi_urls = [setouchi_time, setouchi_fare]
    for route_id, origin, destination, rows in [
        ("mlit_map_193_091_瀬戸内町_瀬相_古仁屋_生間_与路_古仁屋_000_back", "古仁屋", "瀬相", [("07:00", "07:25", "フェリーかけろま"), ("10:20", "10:45", "フェリーかけろま"), ("14:00", "14:25", "フェリーかけろま"), ("17:30", "17:55", "フェリーかけろま")]),
        ("mlit_map_193_091_瀬戸内町_瀬相_古仁屋_生間_与路_古仁屋_000_out", "瀬相", "古仁屋", [("07:35", "08:00", "フェリーかけろま"), ("11:00", "11:25", "フェリーかけろま"), ("14:40", "15:05", "フェリーかけろま"), ("18:05", "18:30", "フェリーかけろま")]),
        ("mlit_map_193_091_瀬戸内町_瀬相_古仁屋_生間_与路_古仁屋_001_out", "古仁屋", "生間", [("08:10", "08:30", "フェリーかけろま"), ("11:40", "12:00", "フェリーかけろま"), ("16:00", "16:20", "フェリーかけろま")]),
        ("mlit_map_193_091_瀬戸内町_瀬相_古仁屋_生間_与路_古仁屋_001_back", "生間", "古仁屋", [("08:40", "09:00", "フェリーかけろま"), ("12:10", "12:30", "フェリーかけろま"), ("16:30", "16:50", "フェリーかけろま")]),
    ]:
        add_route(routes, trips, route_id=route_id, operator="瀬戸内町", origin=origin, destination=destination, fare=360, urls=setouchi_urls, note=setouchi_note, rows=rows)

    kumanami_time = "https://www.town.tabuse.lg.jp/soshiki/35/1753.html"
    kumanami_fare = "https://www.town.tabuse.lg.jp/soshiki/35/1621.html"
    kumanami_note = "Official Tabuse Town/Kumanami General Affairs Association Mashima-Sagoshima timetable and fare page. The official adult fare is JPY 160 for one person up to two sections; seasonal summer extra trips are excluded."
    kumanami_urls = [kumanami_time, kumanami_fare]
    for route_id, origin, destination, rows in [
        ("mlit_map_193_013_熊南総合事務組合_馬島_麻里府_佐合島_佐賀_000_out", "馬島", "麻里府", [("06:50", "06:58", "ましま丸"), ("08:25", "08:33", "ましま丸"), ("12:15", "12:23", "ましま丸"), ("14:35", "14:43", "ましま丸"), ("16:10", "16:18", "ましま丸"), ("17:51", "17:59", "ましま丸")]),
        ("mlit_map_193_013_熊南総合事務組合_馬島_麻里府_佐合島_佐賀_000_back", "麻里府", "馬島", [("07:05", "07:13", "ましま丸"), ("10:20", "10:28", "ましま丸"), ("13:35", "13:43", "ましま丸"), ("15:10", "15:18", "ましま丸"), ("16:25", "16:33", "ましま丸"), ("18:00", "18:08", "ましま丸")]),
        ("mlit_map_193_013_熊南総合事務組合_馬島_麻里府_佐合島_佐賀_001_out", "麻里府", "佐合島", [("07:05", "07:31", "ましま丸"), ("10:20", "10:41", "ましま丸"), ("13:35", "13:56", "ましま丸"), ("15:10", "15:31", "ましま丸"), ("16:25", "16:46", "ましま丸")]),
        ("mlit_map_193_013_熊南総合事務組合_馬島_麻里府_佐合島_佐賀_001_back", "佐合島", "麻里府", [("08:10", "08:33", "ましま丸"), ("12:00", "12:23", "ましま丸"), ("14:20", "14:43", "ましま丸"), ("15:55", "16:18", "ましま丸"), ("17:39", "17:59", "ましま丸")]),
        ("mlit_map_193_013_熊南総合事務組合_馬島_麻里府_佐合島_佐賀_002_back", "佐賀", "佐合島", [("07:50", "07:58", "ましま丸"), ("11:50", "11:58", "ましま丸"), ("14:10", "14:18", "ましま丸"), ("15:45", "15:53", "ましま丸"), ("17:30", "17:38", "ましま丸")]),
        ("mlit_map_193_013_熊南総合事務組合_馬島_麻里府_佐合島_佐賀_002_out", "佐合島", "佐賀", [("07:35", "07:43", "ましま丸"), ("10:45", "10:53", "ましま丸"), ("14:00", "14:08", "ましま丸"), ("15:35", "15:43", "ましま丸"), ("16:50", "16:58", "ましま丸")]),
    ]:
        add_route(routes, trips, route_id=route_id, operator="熊南総合事務組合", origin=origin, destination=destination, fare=160, urls=kumanami_urls, note=kumanami_note, rows=rows)

    nishio_url = "https://sakushima.com/guide-top/access/"
    nishio_note = "Official Sakushima/Nishio access page for fare and timetable image. Adult one-way fare is JPY 830. Times are transcribed from the official ferry timetable image; temporary operation changes are excluded."
    nishio_rows_out = [("06:30", "06:50", "西尾市営渡船"), ("07:40", "08:00", "西尾市営渡船"), ("09:30", "09:50", "西尾市営渡船"), ("11:30", "11:50", "西尾市営渡船"), ("13:40", "14:00", "西尾市営渡船"), ("15:50", "16:10", "西尾市営渡船"), ("17:50", "18:10", "西尾市営渡船")]
    nishio_rows_back = [("07:07", "07:37", "西尾市営渡船"), ("08:37", "09:07", "西尾市営渡船"), ("10:17", "10:47", "西尾市営渡船"), ("12:37", "13:07", "西尾市営渡船"), ("14:57", "15:27", "西尾市営渡船"), ("17:22", "17:52", "西尾市営渡船"), ("18:27", "18:57", "西尾市営渡船")]
    for route_id, origin, destination, rows in [
        ("nishio_sakushima_022_out", "一色港", "佐久島西港", nishio_rows_out),
        ("nishio_sakushima_023_back", "佐久島西港", "一色港", nishio_rows_back),
    ]:
        add_route(routes, trips, route_id=route_id, operator="西尾市", origin=origin, destination=destination, fare=830, urls=[nishio_url], note=nishio_note, rows=rows)
    add_route(routes, trips, route_id="nishio_sakushima_024_out", operator="西尾市", origin="佐久島西港", destination="佐久島東港", fare=830, urls=[nishio_url], note=nishio_note, rows=[("06:50", "06:55", "西尾市営渡船"), ("08:00", "08:05", "西尾市営渡船"), ("09:50", "09:55", "西尾市営渡船"), ("11:50", "11:55", "西尾市営渡船"), ("14:00", "14:05", "西尾市営渡船"), ("16:10", "16:15", "西尾市営渡船"), ("18:10", "18:15", "西尾市営渡船")])
    add_route(routes, trips, route_id="nishio_sakushima_025_back", operator="西尾市", origin="佐久島東港", destination="佐久島西港", fare=830, urls=[nishio_url], note=nishio_note, rows=[("07:00", "07:07", "西尾市営渡船"), ("08:30", "08:37", "西尾市営渡船"), ("10:10", "10:17", "西尾市営渡船"), ("12:30", "12:37", "西尾市営渡船"), ("14:50", "14:57", "西尾市営渡船"), ("17:15", "17:22", "西尾市営渡船"), ("18:20", "18:27", "西尾市営渡船")])

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "priority_100_batch3",
        "operatorId": "priority_100_batch3",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for route_item in routes for url in route_item["fare"]["sourceUrls"]}),
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
