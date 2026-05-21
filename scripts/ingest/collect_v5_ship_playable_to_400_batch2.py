#!/usr/bin/env python3
"""Second verified batch toward 400 playable V5 ship route directions."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collect_v5_ship_playable_to_400_batch1 import add_route, pair_rows


OUT = Path("data/v5_ship_playable_to_400_batch2_official.json")


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes: list[dict] = []
    trips: list[dict] = []

    naruto_index = "https://www.city.naruto.tokushima.jp/kurashi/sumai/kotsu/tosen/"
    okazaki = "https://www.city.naruto.tokushima.jp/kurashi/sumai/kotsu/tosen/okazaki.html"
    kurosaki = "https://www.city.naruto.tokushima.jp/kurashi/sumai/kotsu/tosen/kurosaki.html"
    naruto_note = (
        "Official Naruto municipal ferry timetable. The city ferry page states the usage fee "
        "was abolished and service is free from 1956-04-01; fare is therefore modeled as JPY 0. "
        "Weather disruption and non-timetable changes are excluded."
    )
    okazaki_rows_out = [
        ("06:40", "06:43", "岡崎渡船"), ("07:00", "07:03", "岡崎渡船"), ("07:20", "07:23", "岡崎渡船"),
        ("07:40", "07:43", "岡崎渡船"), ("08:00", "08:03", "岡崎渡船"), ("08:20", "08:23", "岡崎渡船"),
        ("08:40", "08:43", "岡崎渡船"), ("09:00", "09:03", "岡崎渡船"), ("09:30", "09:33", "岡崎渡船"),
        ("10:00", "10:03", "岡崎渡船"), ("11:00", "11:03", "岡崎渡船"), ("12:30", "12:33", "岡崎渡船"),
        ("13:00", "13:03", "岡崎渡船"), ("14:30", "14:33", "岡崎渡船"), ("15:30", "15:33", "岡崎渡船"),
        ("16:00", "16:03", "岡崎渡船"), ("16:30", "16:33", "岡崎渡船"), ("17:00", "17:03", "岡崎渡船"),
        ("17:30", "17:33", "岡崎渡船"), ("18:00", "18:03", "岡崎渡船"), ("18:30", "18:33", "岡崎渡船"),
        ("19:00", "19:03", "岡崎渡船"), ("19:30", "19:33", "岡崎渡船"), ("19:50", "19:53", "岡崎渡船"),
    ]
    okazaki_rows_back = [(arr, f"{int(arr.split(':')[0]):02d}:{int(arr.split(':')[1]) + 3:02d}", vessel) for _, arr, vessel in [(r[0], r[1], r[2]) for r in []]]
    okazaki_rows_back = [
        ("06:44", "06:47", "岡崎渡船"), ("07:04", "07:07", "岡崎渡船"), ("07:24", "07:27", "岡崎渡船"),
        ("07:44", "07:47", "岡崎渡船"), ("08:04", "08:07", "岡崎渡船"), ("08:24", "08:27", "岡崎渡船"),
        ("08:44", "08:47", "岡崎渡船"), ("09:04", "09:07", "岡崎渡船"), ("09:34", "09:37", "岡崎渡船"),
        ("10:04", "10:07", "岡崎渡船"), ("11:04", "11:07", "岡崎渡船"), ("12:34", "12:37", "岡崎渡船"),
        ("13:04", "13:07", "岡崎渡船"), ("14:34", "14:37", "岡崎渡船"), ("15:34", "15:37", "岡崎渡船"),
        ("16:04", "16:07", "岡崎渡船"), ("16:34", "16:37", "岡崎渡船"), ("17:04", "17:07", "岡崎渡船"),
        ("17:34", "17:37", "岡崎渡船"), ("18:04", "18:07", "岡崎渡船"), ("18:34", "18:37", "岡崎渡船"),
        ("19:04", "19:07", "岡崎渡船"), ("19:34", "19:37", "岡崎渡船"), ("19:54", "19:57", "岡崎渡船"),
    ]
    add_route(routes, trips, route_id="mlit_map_193_045_鳴門市_黒崎_高島_岡崎_土佐泊_001_out", operator="鳴門市", origin="岡崎港", destination="土佐泊港", fare=0, urls=[okazaki, naruto_index], note=naruto_note, rows=okazaki_rows_out)
    add_route(routes, trips, route_id="mlit_map_193_045_鳴門市_黒崎_高島_岡崎_土佐泊_001_back", operator="鳴門市", origin="土佐泊港", destination="岡崎港", fare=0, urls=[okazaki, naruto_index], note=naruto_note, rows=okazaki_rows_back)

    kurosaki_rows_out = [
        ("06:40", "06:42", "黒崎渡船"), ("07:00", "07:02", "黒崎渡船"), ("07:20", "07:22", "黒崎渡船"),
        ("07:40", "07:42", "黒崎渡船"), ("08:00", "08:02", "黒崎渡船"), ("08:10", "08:12", "黒崎渡船"),
        ("08:20", "08:22", "黒崎渡船"), ("08:40", "08:42", "黒崎渡船"), ("09:00", "09:02", "黒崎渡船"),
        ("09:30", "09:32", "黒崎渡船"), ("10:00", "10:02", "黒崎渡船"), ("11:00", "11:02", "黒崎渡船"),
        ("12:30", "12:32", "黒崎渡船"), ("13:00", "13:02", "黒崎渡船"), ("14:30", "14:32", "黒崎渡船"),
        ("15:30", "15:32", "黒崎渡船"), ("16:00", "16:02", "黒崎渡船"), ("16:30", "16:32", "黒崎渡船"),
        ("17:00", "17:02", "黒崎渡船"), ("17:30", "17:32", "黒崎渡船"), ("18:00", "18:02", "黒崎渡船"),
        ("18:30", "18:32", "黒崎渡船"), ("19:00", "19:02", "黒崎渡船"), ("19:30", "19:32", "黒崎渡船"),
        ("19:50", "19:52", "黒崎渡船"),
    ]
    kurosaki_rows_back = [
        ("06:43", "06:45", "黒崎渡船"), ("07:03", "07:05", "黒崎渡船"), ("07:23", "07:25", "黒崎渡船"),
        ("07:43", "07:45", "黒崎渡船"), ("08:03", "08:05", "黒崎渡船"), ("08:13", "08:15", "黒崎渡船"),
        ("08:23", "08:25", "黒崎渡船"), ("08:43", "08:45", "黒崎渡船"), ("09:03", "09:05", "黒崎渡船"),
        ("09:33", "09:35", "黒崎渡船"), ("10:03", "10:05", "黒崎渡船"), ("11:03", "11:05", "黒崎渡船"),
        ("12:33", "12:35", "黒崎渡船"), ("13:03", "13:05", "黒崎渡船"), ("14:33", "14:35", "黒崎渡船"),
        ("15:33", "15:35", "黒崎渡船"), ("16:03", "16:05", "黒崎渡船"), ("16:33", "16:35", "黒崎渡船"),
        ("17:03", "17:05", "黒崎渡船"), ("17:33", "17:35", "黒崎渡船"), ("18:03", "18:05", "黒崎渡船"),
        ("18:33", "18:35", "黒崎渡船"), ("19:03", "19:05", "黒崎渡船"), ("19:33", "19:35", "黒崎渡船"),
        ("19:53", "19:55", "黒崎渡船"),
    ]
    add_route(routes, trips, route_id="mlit_map_193_045_鳴門市_黒崎_高島_岡崎_土佐泊_000_out", operator="鳴門市", origin="黒崎港", destination="高島港", fare=0, urls=[kurosaki, naruto_index], note=naruto_note + " The 08:10 Kurosaki departure is kept as weekday service per the official note.", rows=kurosaki_rows_out)
    add_route(routes, trips, route_id="mlit_map_193_045_鳴門市_黒崎_高島_岡崎_土佐泊_000_back", operator="鳴門市", origin="高島港", destination="黒崎港", fare=0, urls=[kurosaki, naruto_index], note=naruto_note + " The 08:13 Takashima departure is kept as weekday service per the official note.", rows=kurosaki_rows_back)

    wakato_time = "https://www.city.kitakyushu.lg.jp/contents/924_10195.html"
    wakato_fare = "https://www.city.kitakyushu.lg.jp/shisei/menu01_0513.html"
    wakato_note = "Official Kitakyushu Wakato route weekday timetable and adult ordinary fare. Holiday/Obon/New Year variants, commuter tickets, bicycles, and discounts are excluded."
    add_route(routes, trips, route_id="mlit_map_193_087_北九州市_藍島_小倉_若松_戸畑_001_out", operator="北九州市", origin="若松", destination="戸畑", fare=100, urls=[wakato_time, wakato_fare], note=wakato_note, rows=pair_rows(["05:55", "06:03", "06:20", "06:38", "06:50", "07:02", "07:14", "07:26", "07:38", "07:50", "09:03", "09:18", "09:33", "09:48", "16:02", "16:14", "16:26", "16:38", "16:50", "21:02", "21:21", "21:41", "22:00", "22:15", "22:30"], 3, "若戸渡船"))
    add_route(routes, trips, route_id="mlit_map_193_087_北九州市_藍島_小倉_若松_戸畑_001_back", operator="北九州市", origin="戸畑", destination="若松", fare=100, urls=[wakato_time, wakato_fare], note=wakato_note, rows=pair_rows(["06:13", "06:30", "06:44", "06:56", "07:08", "07:20", "07:32", "07:44", "07:56", "09:11", "09:26", "09:41", "09:56", "16:08", "16:20", "16:32", "16:44", "16:56", "21:15", "21:35", "21:55", "22:10", "22:25"], 3, "若戸渡船"))

    kokura_url = "https://www.city.kitakyushu.lg.jp/shisei/menu01_0512.html"
    kokura_note = "Official Kitakyushu Kokura route ordinary adult fare and standard service pattern. Summer, Obon, New Year, Ma-shima intermediate fares, bicycles, and discounts are excluded."
    add_route(routes, trips, route_id="mlit_map_193_087_北九州市_藍島_小倉_若松_戸畑_000_back", operator="北九州市", origin="小倉", destination="藍島", fare=600, urls=[kokura_url, "https://www.city.kitakyushu.lg.jp/files/000800475.pdf"], note=kokura_note, rows=[("10:30", "11:05", "こくら丸"), ("14:30", "15:05", "こくら丸"), ("17:30", "18:05", "こくら丸")])
    add_route(routes, trips, route_id="mlit_map_193_087_北九州市_藍島_小倉_若松_戸畑_000_out", operator="北九州市", origin="藍島", destination="小倉", fare=600, urls=[kokura_url, "https://www.city.kitakyushu.lg.jp/files/000800475.pdf"], note=kokura_note, rows=[("07:00", "07:45", "こくら丸"), ("13:30", "14:05", "こくら丸"), ("15:30", "16:05", "こくら丸")])

    mutsure_url = "https://www.shimonoseki-port.com/6518.html"
    mutsure_note = "Official Shimonoseki municipal normal-period timetable and adult ordinary one-way fare. Peak-period, New Year, resident, child, baggage, commuter, and discount fares are excluded."
    add_route(routes, trips, route_id="mlit_map_193_092_下関市_竹崎_六連島_蓋井島_吉見_000_out", operator="下関市", origin="竹崎", destination="六連島", fare=370, urls=[mutsure_url], note=mutsure_note, rows=pair_rows(["06:25", "10:00", "16:40", "18:00"], 20, "六連丸"))
    add_route(routes, trips, route_id="mlit_map_193_092_下関市_竹崎_六連島_蓋井島_吉見_000_back", operator="下関市", origin="六連島", destination="竹崎", fare=370, urls=[mutsure_url], note=mutsure_note, rows=pair_rows(["07:00", "12:30", "17:10", "18:30"], 20, "六連丸"))

    futao_url = "https://www.shimonoseki-port.com/6517.html"
    futao_note = "Official Shimonoseki Futaoi route April-September timetable and adult ordinary fare. Winter/Saturday variants, January 1 suspension, child, baggage, commuter, and discount fares are excluded."
    add_route(routes, trips, route_id="mlit_map_193_092_下関市_竹崎_六連島_蓋井島_吉見_001_out", operator="下関市", origin="蓋井島", destination="吉見", fare=640, urls=[futao_url], note=futao_note, rows=pair_rows(["07:10", "12:10", "15:50"], 40, "蓋井丸"))
    add_route(routes, trips, route_id="mlit_map_193_092_下関市_竹崎_六連島_蓋井島_吉見_001_back", operator="下関市", origin="吉見", destination="蓋井島", fare=640, urls=[futao_url], note=futao_note, rows=pair_rows(["09:40", "13:30", "17:00"], 40, "蓋井丸"))

    ojika_url = "https://www.town.ojika.lg.jp/soshiki/mirai/4/215.html"
    ojika_access = "https://ojikajima.jp/access"
    ojika_note = "Official Ojika municipal ferry timetable and adult one-way fare. Closed-day calendars, winter variants, islander discounts, baggage, and charters are excluded."
    add_route(routes, trips, route_id="mlit_map_193_093_小値賀町_笛吹_大島_野崎_柳_納島_000_out", operator="小値賀町", origin="笛吹", destination="大島港", fare=280, urls=[ojika_access], note=ojika_note, rows=[("06:45", "06:55", "はまゆう"), ("08:35", "08:45", "はまゆう"), ("11:50", "12:00", "はまゆう"), ("17:40", "17:50", "はまゆう")])
    add_route(routes, trips, route_id="mlit_map_193_093_小値賀町_笛吹_大島_野崎_柳_納島_000_back", operator="小値賀町", origin="大島港", destination="笛吹", fare=280, urls=[ojika_access], note=ojika_note, rows=[("07:00", "07:10", "はまゆう"), ("08:50", "09:00", "はまゆう"), ("12:05", "12:15", "はまゆう"), ("17:55", "18:05", "はまゆう")])
    add_route(routes, trips, route_id="mlit_map_193_093_小値賀町_笛吹_大島_野崎_柳_納島_002_out", operator="小値賀町", origin="柳", destination="納島", fare=220, urls=[ojika_url], note=ojika_note, rows=[("06:50", "06:57", "さいかい"), ("08:15", "08:22", "さいかい"), ("12:15", "12:22", "さいかい"), ("15:00", "15:07", "さいかい"), ("17:50", "17:57", "さいかい")])
    add_route(routes, trips, route_id="mlit_map_193_093_小値賀町_笛吹_大島_野崎_柳_納島_002_back", operator="小値賀町", origin="納島", destination="柳", fare=220, urls=[ojika_url], note=ojika_note, rows=[("07:05", "07:12", "さいかい"), ("08:35", "08:42", "さいかい"), ("12:30", "12:37", "さいかい"), ("16:00", "16:07", "さいかい"), ("18:05", "18:12", "さいかい")])

    saibijima_url = "https://www.city.kure.lg.jp/soshiki/28/kouro-ituki.html"
    saibijima_fare = "https://www.city.kure.lg.jp/uploaded/attachment/96405.pdf"
    saibijima_note = "Official Kure Saibijima-Kubi timetable and 2024-10-01 adult passenger fare. Toyoshima intermediate stop, New Year special table, child fares, baggage, and temporary 2026 berth changes are excluded."
    add_route(routes, trips, route_id="mlit_map_193_018_斎島汽船_斎島_久比_三角_久比_000_back", operator="斎島汽船", origin="久比", destination="斎島", fare=470, urls=[saibijima_url, saibijima_fare], note=saibijima_note, rows=[("07:30", "07:57", "斎島汽船"), ("10:45", "11:12", "斎島汽船"), ("16:10", "16:37", "斎島汽船")])
    add_route(routes, trips, route_id="mlit_map_193_018_斎島汽船_斎島_久比_三角_久比_000_out", operator="斎島汽船", origin="斎島", destination="久比", fare=470, urls=[saibijima_url, saibijima_fare], note=saibijima_note, rows=[("07:00", "07:27", "斎島汽船"), ("08:00", "08:27", "斎島汽船"), ("12:40", "13:07", "斎島汽船")])

    sasebo_time = "https://www.city.sasebo.lg.jp/benrimap/shisetsu/sonota/documents/mitsushima_ryoukin_202312.pdf"
    sasebo_fare = "https://www.city.sasebo.lg.jp/tiikimirai/koukou/documents/kourokaizennkeikaku.pdf"
    sasebo_note = "Official Sasebo municipal transport ship Mitsushima timetable and route-improvement-plan fare table. Only directly clear Kamino-ura/Terashima/Yanagi segments are modeled; child fares, discounts, baggage, and charters are excluded."
    add_route(routes, trips, route_id="mlit_map_193_077_佐世保市_神浦_寺島_柳_000_out", operator="佐世保市", origin="神浦", destination="寺島", fare=140, urls=[sasebo_time, sasebo_fare], note=sasebo_note, rows=[("08:10", "08:19", "みつしま"), ("09:20", "09:29", "みつしま"), ("12:00", "12:09", "みつしま"), ("14:30", "14:39", "みつしま"), ("16:35", "16:44", "みつしま")])
    add_route(routes, trips, route_id="mlit_map_193_077_佐世保市_神浦_寺島_柳_000_back", operator="佐世保市", origin="寺島", destination="神浦", fare=140, urls=[sasebo_time, sasebo_fare], note=sasebo_note, rows=[("08:23", "08:32", "みつしま"), ("12:13", "12:22", "みつしま"), ("15:10", "15:19", "みつしま"), ("16:51", "17:00", "みつしま")])
    add_route(routes, trips, route_id="mlit_map_193_077_佐世保市_神浦_寺島_柳_001_out", operator="佐世保市", origin="寺島", destination="柳", fare=220, urls=[sasebo_time, sasebo_fare], note=sasebo_note, rows=[("09:34", "09:54", "みつしま")])
    add_route(routes, trips, route_id="mlit_map_193_077_佐世保市_神浦_寺島_柳_001_back", operator="佐世保市", origin="柳", destination="寺島", fare=220, urls=[sasebo_time, sasebo_fare], note=sasebo_note, rows=[("10:00", "10:17", "みつしま"), ("16:10", "16:27", "みつしま")])

    payload = {
        "schema": "onichase.v5.ship.playable.official.batch2",
        "operator": "multi-operator official batch",
        "operatorId": "v5_ship_playable_to_400_batch2",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for route in routes for url in route["fare"]["sourceUrls"]}),
        "ports": [],
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeCount": len(routes),
            "tripCount": len(trips),
            "notes": "Batch 2 promotes only routes with explicit official or official-linked timetable/fare evidence.",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
