#!/usr/bin/env python3
"""Verified official data for the first cleanup batch from the 79 ship red lights."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collect_v5_ship_playable_to_400_batch1 import add_route


OUT = Path("data/v5_ship_playable_remaining_79_batch1_official.json")


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes: list[dict] = []
    trips: list[dict] = []

    tsuyoshi_url = "https://www.nomo.co.jp/tsuyoshi/tsuyoshi/"
    tsuyoshi_note = (
        "Official Nomo Shosen Group Tsuyoshi page lists the 2021-10-01 timetable and the 2019-10-01 adult ordinary fares. "
        "This cleanup row promotes the remaining Aino-ura to Tsuyoshi direction exactly as an official intermediate OD on the Tsuyoshi route; "
        "temporary storm alternates, cargo, discounts, and the January 1 suspension are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_080_津吉商船_津吉_相浦_佐世保_000_back", operator="津吉商船", origin="相浦", destination="津吉", fare=1130, urls=[tsuyoshi_url], note=tsuyoshi_note, rows=[("08:12", "08:47", "つよし")])

    tadotsu_time = "https://tadotsu-kisen.jp/%E6%99%82%E5%88%BB%E8%A1%A8"
    tadotsu_fare = "https://tadotsu-kisen.jp/%E9%81%8B%E8%B3%83"
    tadotsu_note = (
        "Official Tadotsu Kisen timetable and fare pages list the Tadotsu-Sanagi Honura service and the adult ordinary fare of JPY 690. "
        "V5 records the regular daily Honura rows only; Saturday-only Manabe/Sanagi-Nagasaki extensions, vehicles, baggage, child fares, and discounts are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_028_たどつ汽船_多度津_佐柳_000_out", operator="たどつ汽船", origin="多度津", destination="佐柳", fare=690, urls=[tadotsu_time, tadotsu_fare], note=tadotsu_note, rows=[("06:55", "07:50", "新なぎさ2"), ("09:05", "09:55", "新なぎさ2"), ("14:00", "14:50", "新なぎさ2"), ("16:20", "17:10", "新なぎさ2")])
    add_route(routes, trips, route_id="mlit_map_193_028_たどつ汽船_多度津_佐柳_000_back", operator="たどつ汽船", origin="佐柳", destination="多度津", fare=690, urls=[tadotsu_time, tadotsu_fare], note=tadotsu_note, rows=[("08:05", "08:55", "新なぎさ2"), ("10:00", "10:50", "新なぎさ2"), ("15:25", "16:15", "新なぎさ2"), ("17:10", "18:00", "新なぎさ2")])

    suonada_time = "https://www.suonada.co.jp/c_timetable.html"
    suonada_fare = "https://www.suonada.co.jp/c_fare.html"
    suonada_note = (
        "Official Suonada Ferry timetable and fare pages list the Tokuyama-Taketatsu normal timetable, two-hour running time, and adult general passenger fare of JPY 2,560. "
        "V5 excludes the June night-sailing suspensions, vehicles, cargo, reservations, and fuel-adjustment variants outside the posted passenger fare."
    )
    add_route(routes, trips, route_id="suonada_tokuyama_taketatsu_038_out", operator="周防灘フェリー", origin="徳山港", destination="竹田津港", fare=2560, urls=[suonada_time, suonada_fare], note=suonada_note, rows=[("02:00", "04:00", "ニューくにさき"), ("07:20", "09:20", "ニューくにさき"), ("12:00", "14:00", "ニューくにさき"), ("16:40", "18:40", "ニューくにさき")], route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="suonada_tokuyama_taketatsu_039_back", operator="周防灘フェリー", origin="竹田津港", destination="徳山港", fare=2560, urls=[suonada_time, suonada_fare], note=suonada_note, rows=[("04:20", "06:20", "ニューくにさき"), ("09:40", "11:40", "ニューくにさき"), ("14:20", "16:20", "ニューくにさき"), ("19:00", "21:00", "ニューくにさき")], route_class="long_distance_public_ferry")

    suo_oshima_local_url = "https://www.town.suo-oshima.lg.jp/uploaded/attachment/21306.pdf"
    suo_oshima_kuga_fare = "https://www.town.suo-oshima.lg.jp/uploaded/attachment/11524.pdf"
    suo_oshima_note = (
        "Official Suo-Oshima town transport timetable PDF and fare PDF list the Kuka-Maeshima municipal ferry. "
        "This batch uses the official adult one-way fare of JPY 380 and regular daily rows; extra/on-demand rows and discounts are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_019_周防大島町_久賀_前島_樽見_日前_情島_伊保田_000_out", operator="周防大島町", origin="久賀", destination="前島", fare=380, urls=[suo_oshima_local_url, suo_oshima_kuga_fare], note=suo_oshima_note, rows=[("07:10", "07:30", "町営渡船"), ("11:20", "11:40", "町営渡船"), ("16:00", "16:20", "町営渡船")])
    add_route(routes, trips, route_id="mlit_map_193_019_周防大島町_久賀_前島_樽見_日前_情島_伊保田_000_back", operator="周防大島町", origin="前島", destination="久賀", fare=380, urls=[suo_oshima_local_url, suo_oshima_kuga_fare], note=suo_oshima_note, rows=[("07:35", "07:55", "町営渡船"), ("11:45", "12:05", "町営渡船"), ("16:25", "16:45", "町営渡船")])

    tokai_time = "https://www.tokaikisen.co.jp/boarding/timetable/"
    tokai_fare = "https://www.tokaikisen.co.jp/boarding/fare/"
    tokai_note = (
        "Official Tokai Kisen timetable and fare pages list the Tokyo-Oshima large-passenger-ship and jetfoil services and May 2026 adult fares. "
        "These rows promote the exact Oshima-Okada route IDs still left by the map-source audit; higher classes, vehicles, discounts, and port-change disruptions are excluded."
    )
    add_route(routes, trips, route_id="tokai_tokyo_izu_islands_052_out", operator="東海汽船", origin="竹芝", destination="大島岡田港", fare=5750, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("22:00", "翌06:00", "大型客船")], route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="tokai_tokyo_izu_islands_053_back", operator="東海汽船", origin="大島岡田港", destination="竹芝", fare=5750, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("14:30", "19:00", "大型客船")], route_class="long_distance_public_ferry")

    sakata_time = "https://www.city.sakata.lg.jp/sangyo/kotsu/teikisen/josenannai/teiki0220220214.html"
    sakata_fare = "https://www.city.sakata.lg.jp/sangyo/kotsu/teikisen/josenannai/teikiunkounittei.html"
    sakata_note = (
        "Official Sakata city Tobishima pages list the 2026 timetable PDF and the adult one-way fare of JPY 2,140. "
        "V5 records the standard one-round-trip pattern for the Sakata-Tobishima route; calendar-specific extra sailings, islander fares, group fares, cargo, and disruption changes are excluded."
    )
    add_route(routes, trips, route_id="sakata_tobishima_010_out", operator="酒田市", origin="酒田港", destination="飛島勝浦港", fare=2140, urls=[sakata_time, sakata_fare], note=sakata_note, rows=[("09:30", "10:45", "定期船とびしま")])
    add_route(routes, trips, route_id="sakata_tobishima_011_back", operator="酒田市", origin="飛島勝浦港", destination="酒田港", fare=2140, urls=[sakata_time, sakata_fare], note=sakata_note, rows=[("13:45", "15:00", "定期船とびしま")])

    toshima_url = "https://www.tokara.jp/ferryinfo/ferrytoshima/"
    toshima_note = (
        "Official Toshima Village ferry page lists the Ferry Toshima 2 Nase-service timetable image and adult 2nd-class fare table. "
        "V5 records the four remaining Kagoshima/Nakanoshima/Nase OD directions with official adult 2nd-class fares; islander fares, group/student discounts, cargo, cars, and monthly exception calendars are excluded."
    )
    toshima_calendar = {"type": "official_nase_service_pattern"}
    add_route(routes, trips, route_id="mlit_map_193_065_十島村_鹿児島_十島_名瀬_000_out", operator="十島村", origin="鹿児島港", destination="中之島港", fare=5290, urls=[toshima_url], note=toshima_note, rows=[("23:00", "翌06:00", "フェリーとしま2")], calendar=toshima_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="mlit_map_193_065_十島村_鹿児島_十島_名瀬_000_back", operator="十島村", origin="中之島港", destination="鹿児島港", fare=5290, urls=[toshima_url], note=toshima_note, rows=[("10:35", "18:20", "フェリーとしま2")], calendar=toshima_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="mlit_map_193_065_十島村_鹿児島_十島_名瀬_001_out", operator="十島村", origin="中之島港", destination="名瀬港", fare=4830, urls=[toshima_url], note=toshima_note, rows=[("06:10", "15:20", "フェリーとしま2")], calendar=toshima_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="mlit_map_193_065_十島村_鹿児島_十島_名瀬_001_back", operator="十島村", origin="名瀬港", destination="中之島港", fare=4830, urls=[toshima_url], note=toshima_note, rows=[("02:00", "10:25", "フェリーとしま2")], calendar=toshima_calendar, route_class="long_distance_public_ferry")

    marix_url = "https://marixline.com/price_schedule/"
    marix_note = (
        "Official Marix Line fare/timetable search page lists the Kagoshima-Naha downbound timetable, the operator alternation with Marue Ferry, and the adult 2nd-class room fare of JPY 16,350 for the current result. "
        "The reverse time is verified from the official A-Line access page arrival/departure table for the same Kagoshima-Naha route. V5 excludes higher cabins, vehicles, discounts, and date-specific operator alternation outside this source snapshot."
    )
    add_route(routes, trips, route_id="mlit_map_193_057_マリックスライン_鹿児島_那覇_000_out", operator="マリックスライン", origin="鹿児島港", destination="那覇泊港", fare=16350, urls=[marix_url, "https://www.aline-ferry.com/kagoshima/access/"], note=marix_note, rows=[("18:00", "翌19:00", "クイーンコーラル")], route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="mlit_map_193_057_マリックスライン_鹿児島_那覇_000_back", operator="マリックスライン", origin="那覇泊港", destination="鹿児島港", fare=16350, urls=[marix_url, "https://www.aline-ferry.com/kagoshima/access/"], note=marix_note, rows=[("07:00", "翌08:30", "クイーンコーラル")], route_class="long_distance_public_ferry")

    seapal_url = "https://www.town.onagawa.miyagi.jp/pdf/bus/r0803_bus_guidebook.pdf"
    seapal_fare_source = "https://www.town.onagawa.miyagi.jp/pdf/koutsuu/r05koutsuukaigi03_siryo2.pdf"
    seapal_note = (
        "Official Onagawa town bus/transport guidebook lists the Onagawa-Ejima three daily sailings, and the town transport-plan document states the adult Onagawa-Ejima fare of JPY 1,100 and about 30 minutes via Izushima. "
        "V5 records direct playable OD rows only; demand-only caveats, resident discounts, intermediate Terama/Izushima stops, and disruption changes are excluded."
    )
    add_route(routes, trips, route_id="seapal_onagawa_enoshima_018_out", operator="シーパル女川汽船", origin="女川港", destination="江島港", fare=1100, urls=[seapal_url, seapal_fare_source], note=seapal_note, rows=[("06:50", "07:20", "しまなぎ"), ("11:00", "11:30", "しまなぎ"), ("15:45", "16:15", "しまなぎ")])
    add_route(routes, trips, route_id="seapal_onagawa_enoshima_019_back", operator="シーパル女川汽船", origin="江島港", destination="女川港", fare=1100, urls=[seapal_url, seapal_fare_source], note=seapal_note, rows=[("07:20", "07:50", "しまなぎ"), ("11:30", "12:00", "しまなぎ"), ("16:15", "16:45", "しまなぎ")])

    hegura_url = "https://hegura.com/guide/"
    hegura_note = (
        "Official Hegura route page lists the weekday-only Wajima-Hegurajima timetable, 85-minute running time, and adult one-way fare of JPY 2,300. "
        "V5 records the summer timetable valid April 1-October 31 for the current May date; weekends/holidays, Obon/Wajima festival suspensions, daily 07:30 go/no-go decisions, cargo, and discounts are excluded."
    )
    hegura_calendar = {"type": "weekday_summer_0401_1031"}
    add_route(routes, trips, route_id="hegura_wajima_024_out", operator="へぐら航路", origin="輪島港", destination="舳倉島港", fare=2300, urls=[hegura_url], note=hegura_note, rows=[("09:00", "10:25", "希海")], calendar=hegura_calendar)
    add_route(routes, trips, route_id="hegura_wajima_025_back", operator="へぐら航路", origin="舳倉島港", destination="輪島港", fare=2300, urls=[hegura_url], note=hegura_note, rows=[("15:00", "16:25", "希海")], calendar=hegura_calendar)

    payload = {
        "schema": "onichase.v5.ship.playable.remaining79.batch1",
        "operator": "multi-operator verified official remaining red-light cleanup",
        "operatorId": "v5_ship_playable_remaining_79_batch1",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for route in routes for url in route["fare"]["sourceUrls"]}),
        "ports": [],
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeCount": len(routes),
            "tripCount": len(trips),
            "notes": "Only official pages/PDFs with explicit timetable and adult ordinary fare evidence are included.",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
