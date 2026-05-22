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

    susaki_time = "https://www.city.susaki.lg.jp/download/?fid=36165&id=3548&t=LD"
    susaki_fare = "https://www.city.susaki.lg.jp/download/?fid=36164&id=3548&t=LD"
    susaki_page = "https://www.city.susaki.lg.jp/life/detail.php?hdnKey=3548"
    susaki_note = (
        "Official Susaki municipal cruise-ship page and PDFs list the Umetate-Sakanai timetable, Sunday/holiday/New-Year suspension, "
        "and the adult ordinary Umetate-Sakanai fare of JPY 640. V5 records only the direct end-to-end OD rows; intermediate-stop boarding, "
        "school/discount fares, baggage, GTFS variants, and disruption changes are excluded."
    )
    susaki_calendar = {"type": "weekdays_and_saturdays_except_holidays_new_year"}
    add_route(routes, trips, route_id="mlit_map_193_042_須崎市_坂内_埋立_000_out", operator="須崎市", origin="坂内", destination="埋立", fare=640, urls=[susaki_page, susaki_time, susaki_fare], note=susaki_note, rows=[("08:21", "09:22", "須崎市営巡航船"), ("13:38", "14:40", "須崎市営巡航船"), ("16:20", "17:10", "須崎市営巡航船")], calendar=susaki_calendar)
    add_route(routes, trips, route_id="mlit_map_193_042_須崎市_坂内_埋立_000_back", operator="須崎市", origin="埋立", destination="坂内", fare=640, urls=[susaki_page, susaki_time, susaki_fare], note=susaki_note, rows=[("07:10", "08:11", "須崎市営巡航船"), ("10:05", "11:07", "須崎市営巡航船"), ("14:50", "15:40", "須崎市営巡航船")], calendar=susaki_calendar)

    onomichi_page = "https://www.city.onomichi.hiroshima.jp/soshiki/39/69388.html"
    onomichi_pdf = "https://www.city.onomichi.hiroshima.jp/uploaded/attachment/46298.pdf"
    onomichi_note = (
        "Official Onomichi city Hososhima route page and timetable/fare PDF list municipal ferry Komataki service between Nishihama and Hososhima. "
        "V5 records the weekday table and adult ordinary passenger fare of JPY 150; Sunday/holiday pattern, vehicle fares, commuter tickets, baggage, "
        "discounts, and temporary changes are excluded."
    )
    onomichi_weekday = {"type": "weekday"}
    add_route(routes, trips, route_id="mlit_map_193_009_尾道市因島総合支所_細島_因島_西浜_000_back", operator="尾道市因島総合支所", origin="因島西浜港", destination="細島港", fare=150, urls=[onomichi_page, onomichi_pdf], note=onomichi_note, rows=[("07:00", "07:15", "こまたき"), ("07:40", "07:55", "こまたき"), ("09:30", "09:45", "こまたき"), ("11:00", "11:15", "こまたき"), ("13:40", "13:55", "こまたき"), ("15:40", "15:55", "こまたき"), ("17:20", "17:35", "こまたき"), ("18:40", "18:55", "こまたき")], calendar=onomichi_weekday)
    add_route(routes, trips, route_id="mlit_map_193_009_尾道市因島総合支所_細島_因島_西浜_000_out", operator="尾道市因島総合支所", origin="細島港", destination="因島西浜港", fare=150, urls=[onomichi_page, onomichi_pdf], note=onomichi_note, rows=[("07:20", "07:35", "こまたき"), ("08:10", "08:25", "こまたき"), ("10:40", "10:55", "こまたき"), ("12:00", "12:15", "こまたき"), ("14:00", "14:15", "こまたき"), ("16:00", "16:15", "こまたき"), ("17:40", "17:55", "こまたき"), ("19:00", "19:15", "こまたき")], calendar=onomichi_weekday)

    suo_oshima_jowa_time = "https://www.town.suo-oshima.lg.jp/uploaded/attachment/11520.pdf"
    suo_oshima_jowa_fare = "https://www.town.suo-oshima.lg.jp/uploaded/attachment/5060.pdf"
    suo_oshima_tarumi_time = "https://www.town.suo-oshima.lg.jp/uploaded/attachment/11525.pdf"
    suo_oshima_tarumi_fare = "https://www.town.suo-oshima.lg.jp/uploaded/attachment/11526.pdf"
    suo_oshima_reiki = "https://www1.g-reiki.net/town.suo-oshima/reiki_honbun/r050RG00000064.html"
    suo_oshima_remaining_note = (
        "Official Suo-Oshima municipal ferry timetable PDFs and fare PDFs/bylaw list the remaining Jowa and Tarumi-Hizumi town routes. "
        "V5 records regular adult one-way fares and timetable rows only; ad-hoc extra/charter sailings, child fares, commuter tickets, baggage, "
        "and disruption changes are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_019_周防大島町_久賀_前島_樽見_日前_情島_伊保田_002_back", operator="周防大島町", origin="伊保田", destination="情島", fare=290, urls=[suo_oshima_jowa_time, suo_oshima_jowa_fare, suo_oshima_reiki], note=suo_oshima_remaining_note, rows=[("06:20", "06:35", "せと丸"), ("11:00", "11:15", "せと丸"), ("14:30", "14:45", "せと丸"), ("18:00", "18:15", "せと丸")])
    add_route(routes, trips, route_id="mlit_map_193_019_周防大島町_久賀_前島_樽見_日前_情島_伊保田_002_out", operator="周防大島町", origin="情島", destination="伊保田", fare=290, urls=[suo_oshima_jowa_time, suo_oshima_jowa_fare, suo_oshima_reiki], note=suo_oshima_remaining_note, rows=[("06:50", "07:05", "せと丸"), ("12:20", "12:35", "せと丸"), ("15:00", "15:15", "せと丸"), ("18:20", "18:35", "せと丸")])
    add_route(routes, trips, route_id="mlit_map_193_019_周防大島町_久賀_前島_樽見_日前_情島_伊保田_001_back", operator="周防大島町", origin="日前", destination="樽見", fare=330, urls=[suo_oshima_tarumi_time, suo_oshima_tarumi_fare, suo_oshima_reiki], note=suo_oshima_remaining_note, rows=[("08:00", "08:30", "ひらい丸"), ("11:30", "12:00", "ひらい丸"), ("16:50", "17:20", "ひらい丸"), ("18:00", "18:30", "ひらい丸")])
    add_route(routes, trips, route_id="mlit_map_193_019_周防大島町_久賀_前島_樽見_日前_情島_伊保田_001_out", operator="周防大島町", origin="樽見", destination="日前", fare=330, urls=[suo_oshima_tarumi_time, suo_oshima_tarumi_fare, suo_oshima_reiki], note=suo_oshima_remaining_note, rows=[("07:10", "07:40", "ひらい丸"), ("10:00", "10:30", "ひらい丸"), ("15:00", "15:30", "ひらい丸"), ("17:25", "17:55", "ひらい丸")])

    iwakuni_time = "http://ww4.et.tiki.ne.jp/~suisei-ihk/jikoku.htm"
    iwakuni_fare = "http://ww4.et.tiki.ne.jp/~suisei-ihk/unntinn.htm"
    iwakuni_note = (
        "Official Iwakuni Hashirajima Kaiun timetable and fare pages list the Iwakuni-Hashirajima route, adult fare of JPY 1,860, "
        "and weekend/New-Year/Obon-only marked sailings. V5 records the unmarked regular rows only; intermediate Hashima/Kuroshima "
        "boarding, child fares, baggage, discounts, and disruption changes are excluded."
    )
    add_route(routes, trips, route_id="iwakuni_hashirajima_064_out", operator="岩国柱島海運", origin="岩国港", destination="柱島港", fare=1860, urls=[iwakuni_time, iwakuni_fare], note=iwakuni_note, rows=[("07:40", "08:39", "岩国柱島海運"), ("15:30", "16:08", "岩国柱島海運"), ("17:30", "18:29", "岩国柱島海運")])
    add_route(routes, trips, route_id="iwakuni_hashirajima_065_back", operator="岩国柱島海運", origin="柱島港", destination="岩国港", fare=1860, urls=[iwakuni_time, iwakuni_fare], note=iwakuni_note, rows=[("06:45", "07:30", "岩国柱島海運"), ("08:50", "09:28", "岩国柱島海運"), ("16:15", "17:14", "岩国柱島海運")])

    amami_time = "https://www.aline-ferry.com/cms/wp-content/uploads/2022/02/73aaa91a02188a28a82ce85a28ef8710.pdf"
    amami_fare = "https://www.aline-ferry.com/cms/wp-content/uploads/2019/03/c3b4804d070ddf88c5d9766d041e0e5f-1.pdf"
    amami_page = "https://www.aline-ferry.com/amami/fare/passenger/"
    amami_note = (
        "Official A-Line/Amami Kaiun May-July 2026 timetable PDF and passenger-fare PDF list the Kagoshima-Kikai service and 2026-05-01 "
        "2nd-class adult one-way fare of JPY 9,220 before fuel adjustment. V5 records the current post-2025 China-port-suspension pattern; "
        "BAF fuel adjustment, resident discounts, higher cabins, bedding charges, vehicles, and monthly non-operating dates are excluded."
    )
    amami_calendar = {"type": "official_may_july_2026_pattern_dates_in_source_pdf"}
    add_route(routes, trips, route_id="mlit_map_193_058_奄美海運_鹿児島_喜界_知名_000_out", operator="奄美海運", origin="鹿児島港", destination="喜界港", fare=9220, urls=[amami_page, amami_time, amami_fare], note=amami_note, rows=[("17:30", "翌04:30", "フェリーあまみ/フェリーきかい")], calendar=amami_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="mlit_map_193_058_奄美海運_鹿児島_喜界_知名_000_back", operator="奄美海運", origin="喜界港", destination="鹿児島港", fare=9220, urls=[amami_page, amami_time, amami_fare], note=amami_note, rows=[("21:00", "翌08:30", "フェリーあまみ/フェリーきかい")], calendar=amami_calendar, route_class="long_distance_public_ferry")

    mishima_page = "https://mishimamura.com/ferry/"
    mishima_note = (
        "Official Mishima Village Ferry Mishima page lists the normal one-night/two-day timetable and the adult 2nd-class passenger fare of JPY 3,660 "
        "for Kagoshima to Mishima islands. V5 records the normal Kagoshima-Iojima OD rows only; monthly sailing calendars, day-trip variants, "
        "islander discounts, higher class, cargo, vehicles, and weather changes are excluded."
    )
    mishima_calendar = {"type": "official_monthly_calendar_required_normal_pattern"}
    add_route(routes, trips, route_id="mlit_map_193_064_三島村_鹿児島_三島_000_out", operator="三島村", origin="鹿児島港", destination="硫黄島港", fare=3660, urls=[mishima_page], note=mishima_note, rows=[("09:30", "13:25", "フェリーみしま")], calendar=mishima_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="mlit_map_193_064_三島村_鹿児島_三島_000_back", operator="三島村", origin="硫黄島港", destination="鹿児島港", fare=3660, urls=[mishima_page], note=mishima_note, rows=[("10:10", "14:05", "フェリーみしま")], calendar=mishima_calendar, route_class="long_distance_public_ferry")

    ajishima_timetable = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRisF8TXvcY1UfMIT5SgIqM4F7ZnX6Xp6lXwwvelqtM-cDbtnGRHAksGrmHd4VvEYH_NU3UdqBzZtqu/pub?output=csv"
    ajishima_page = "https://ajishimaline.com/pg117.html"
    ajishima_fare = "https://ajishimaline.com/about.html"
    ajishima_note = (
        "Official Ajishima Line timetable page embeds the public Google Sheet for the 2026-02-01 year-round timetable, and the official fare page "
        "lists the one-way adult fares. V5 records only OD rows with explicit stop times in that sheet; Odomari/Futawatashi alternate boarding, "
        "vehicle fares, free coupons, discounts, cash-only notes, and same-day disruption changes are excluded."
    )
    ajishima_calendar = {"type": "official_year_round_from_2026_02_01"}
    add_route(routes, trips, route_id="ajishima_line_012_out", operator="網地島ライン", origin="石巻中央発着所", destination="田代島仁斗田港", fare=1250, urls=[ajishima_page, ajishima_timetable, ajishima_fare], note=ajishima_note, rows=[("09:00", "09:44", "シーキャット"), ("12:30", "13:34", "マーメイドII"), ("15:30", "16:14", "シーキャット")], calendar=ajishima_calendar)
    add_route(routes, trips, route_id="ajishima_line_013_back", operator="網地島ライン", origin="田代島仁斗田港", destination="石巻中央発着所", fare=1250, urls=[ajishima_page, ajishima_timetable, ajishima_fare], note=ajishima_note, rows=[("07:55", "08:42", "シーキャット"), ("13:55", "14:40", "シーキャット"), ("15:30", "16:27", "マーメイドII")], calendar=ajishima_calendar)
    add_route(routes, trips, route_id="ajishima_line_014_out", operator="網地島ライン", origin="田代島仁斗田港", destination="網地港", fare=350, urls=[ajishima_page, ajishima_timetable, ajishima_fare], note=ajishima_note, rows=[("06:40", "06:50", "シーキャット"), ("09:44", "09:54", "シーキャット"), ("13:34", "13:52", "マーメイドII"), ("16:14", "16:24", "シーキャット")], calendar=ajishima_calendar)
    add_route(routes, trips, route_id="ajishima_line_015_back", operator="網地島ライン", origin="網地港", destination="田代島仁斗田港", fare=350, urls=[ajishima_page, ajishima_timetable, ajishima_fare], note=ajishima_note, rows=[("07:45", "07:55", "シーキャット"), ("13:45", "13:55", "シーキャット"), ("15:12", "15:30", "マーメイドII"), ("17:09", "17:28", "シーキャット")], calendar=ajishima_calendar)
    add_route(routes, trips, route_id="ajishima_line_016_out", operator="網地島ライン", origin="網地港", destination="鮎川港", fare=470, urls=[ajishima_page, ajishima_timetable, ajishima_fare], note=ajishima_note, rows=[("06:50", "07:18", "シーキャット"), ("09:54", "10:20", "シーキャット"), ("13:52", "14:31", "マーメイドII"), ("16:24", "16:50", "シーキャット")], calendar=ajishima_calendar)
    add_route(routes, trips, route_id="ajishima_line_017_back", operator="網地島ライン", origin="鮎川港", destination="網地港", fare=470, urls=[ajishima_page, ajishima_timetable, ajishima_fare], note=ajishima_note, rows=[("07:20", "07:45", "シーキャット"), ("10:30", "10:55", "シーキャット"), ("14:35", "15:12", "マーメイドII"), ("16:51", "17:09", "シーキャット")], calendar=ajishima_calendar)

    saikai_time = "https://www.city.saikai.nagasaki.jp/material/files/group/5/saikaienganferi-.pdf"
    saikai_fare = "https://www.city.saikai.nagasaki.jp/material/files/group/5/ryokakuuntinhyo.pdf"
    saikai_page = "https://www.city.saikai.nagasaki.jp/kurashi/kotsu/3/index.html"
    saikai_note = (
        "Official Saikai coastal ferry timetable PDF lists the normal ferry pattern for the Sasebo-Kono-ura route, and the official passenger-fare PDF "
        "lists the Seto-Matsushima adult ordinary ferry fare of JPY 240. The MLIT source labels the Matsushima-side port as Kamaura; V5 keeps the MLIT "
        "port name for route-key compatibility while using only rows with explicit Matsushima/Seto departure-arrival times. Dock-replacement high-speed "
        "boat rows, monthly extra sailings, child/disabled fares, commuter tickets, and disruption changes are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_067_西海市_釜浦_瀬戸_000_out", operator="西海市", origin="釜浦", destination="瀬戸", fare=240, urls=[saikai_page, saikai_time, saikai_fare], note=saikai_note, rows=[("08:40", "08:50", "フェリーかしま"), ("15:00", "15:10", "フェリーかしま"), ("17:55", "18:05", "フェリーかしま")])
    add_route(routes, trips, route_id="mlit_map_193_067_西海市_釜浦_瀬戸_000_back", operator="西海市", origin="瀬戸", destination="釜浦", fare=240, urls=[saikai_page, saikai_time, saikai_fare], note=saikai_note, rows=[("08:20", "08:35", "フェリーかしま"), ("14:47", "14:57", "フェリーかしま"), ("17:40", "17:50", "フェリーかしま")])

    taiheiyo_time = "https://www.taiheiyo-ferry.co.jp/koro/index.html"
    taiheiyo_fare = "https://www.taiheiyo-ferry.co.jp/unchin/pdf/20241213.pdf"
    taiheiyo_note = (
        "Official Taiheiyo Ferry timetable page lists the Sendai/Tomakomai/Nagoya departure and arrival times, and the official fare PDF valid from "
        "2025-01-06 lists adult 2nd-class basic fares. V5 uses the A-period adult 2nd-class base fare as the conservative playable fare; other seasons, "
        "ship/room classes, private-room surcharge rules, internet discounts, vehicle fares, January-March irregular diagrams, and disruption changes are excluded."
    )
    daily_calendar = {"type": "daily"}
    alternate_calendar = {"type": "official_alternate_day"}
    add_route(routes, trips, route_id="taiheiyo_nagoya_sendai_tomakomai_000_out", operator="太平洋フェリー", origin="名古屋港", destination="仙台港", fare=8200, urls=[taiheiyo_time, taiheiyo_fare], note=taiheiyo_note, rows=[("19:00", "翌16:40", "太平洋フェリー")], calendar=alternate_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="taiheiyo_nagoya_sendai_tomakomai_001_back", operator="太平洋フェリー", origin="仙台港", destination="名古屋港", fare=8200, urls=[taiheiyo_time, taiheiyo_fare], note=taiheiyo_note, rows=[("12:50", "翌10:30", "太平洋フェリー")], calendar=alternate_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="taiheiyo_nagoya_sendai_tomakomai_002_out", operator="太平洋フェリー", origin="仙台港", destination="苫小牧西港", fare=9500, urls=[taiheiyo_time, taiheiyo_fare], note=taiheiyo_note, rows=[("19:40", "翌11:00", "太平洋フェリー")], calendar=daily_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="taiheiyo_nagoya_sendai_tomakomai_003_back", operator="太平洋フェリー", origin="苫小牧西港", destination="仙台港", fare=9500, urls=[taiheiyo_time, taiheiyo_fare], note=taiheiyo_note, rows=[("19:00", "翌10:00", "太平洋フェリー")], calendar=daily_calendar, route_class="long_distance_public_ferry")

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
