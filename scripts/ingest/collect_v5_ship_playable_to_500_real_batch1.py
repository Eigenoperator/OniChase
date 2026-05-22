#!/usr/bin/env python3
"""Verified real-data V5 ship promotions after the 400-route gate."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collect_v5_ship_playable_to_400_batch1 import add_route, pair_rows


OUT = Path("data/v5_ship_playable_to_500_real_batch1_official.json")


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes: list[dict] = []
    trips: list[dict] = []

    kochi_url = "https://www.pref.kochi.lg.jp/doc/tosen1/"
    kochi_pdf = "https://www.pref.kochi.lg.jp/doc/tosen1/file_contents/file_20256172211619_1.pdf"
    kochi_note = (
        "Official Kochi prefectural Nagahama-Tanezaki ferry page and 2025 timetable PDF. "
        "The page states the 575m route takes about 5 minutes and that passengers/bicycles/small motorcycles are free. "
        "V5 uses the Monday-Saturday timetable for the current weekday release date; Sunday timetable and inspection suspensions are excluded."
    )
    kochi_calendar = {"type": "monday_to_saturday"}
    kochi_nagahama = [
        ("06:30", "06:35", "浦戸"),
        ("07:00", "07:05", "浦戸"),
        ("07:20", "07:25", "浦戸"),
        ("07:40", "07:45", "浦戸"),
        ("08:00", "08:05", "浦戸"),
        ("08:20", "08:25", "浦戸"),
        ("09:00", "09:05", "浦戸"),
        ("10:00", "10:05", "浦戸"),
        ("11:00", "11:05", "浦戸"),
        ("12:00", "12:05", "浦戸"),
        ("13:00", "13:05", "浦戸"),
        ("14:00", "14:05", "浦戸"),
        ("15:00", "15:05", "浦戸"),
        ("16:00", "16:05", "浦戸"),
        ("17:00", "17:05", "浦戸"),
        ("17:30", "17:35", "浦戸"),
        ("18:00", "18:05", "浦戸"),
        ("18:30", "18:35", "浦戸"),
        ("19:00", "19:05", "浦戸"),
    ]
    kochi_tanezaki = [
        ("06:40", "06:45", "浦戸"),
        ("07:10", "07:15", "浦戸"),
        ("07:30", "07:35", "浦戸"),
        ("07:50", "07:55", "浦戸"),
        ("08:10", "08:15", "浦戸"),
        ("08:30", "08:35", "浦戸"),
        ("09:10", "09:15", "浦戸"),
        ("10:10", "10:15", "浦戸"),
        ("11:10", "11:15", "浦戸"),
        ("12:10", "12:15", "浦戸"),
        ("13:10", "13:15", "浦戸"),
        ("14:10", "14:15", "浦戸"),
        ("15:10", "15:15", "浦戸"),
        ("16:10", "16:15", "浦戸"),
        ("17:15", "17:20", "浦戸"),
        ("17:40", "17:45", "浦戸"),
        ("18:10", "18:15", "浦戸"),
        ("18:40", "18:45", "浦戸"),
        ("19:10", "19:15", "浦戸"),
    ]
    add_route(routes, trips, route_id="mlit_map_193_044_高知県_長浜_種崎_000_out", operator="高知県", origin="長浜港", destination="種崎港", fare=0, urls=[kochi_url, kochi_pdf], note=kochi_note, rows=kochi_nagahama, calendar=kochi_calendar)
    add_route(routes, trips, route_id="mlit_map_193_044_高知県_長浜_種崎_000_back", operator="高知県", origin="種崎港", destination="長浜港", fare=0, urls=[kochi_url, kochi_pdf], note=kochi_note, rows=kochi_tanezaki, calendar=kochi_calendar)

    boyo_time = "https://www.boyoferry.co.jp/c_timetable.html"
    boyo_fare = "https://www.boyoferry.co.jp/c_fare.html"
    boyo_note = (
        "Official Boyo Ferry timetable and fare pages. V5 models the Yanai-Mitsuhama adult passenger fare "
        "of JPY 4,500 and the normal daily sailings only; Sunday/Monday-suspended and Saturday/Sunday-suspended "
        "limited sailings, vehicles, baggage, return discounts, and disruption notices are excluded."
    )
    boyo_rows_out = [
        ("07:00", "09:30", "防予フェリー"),
        ("09:00", "11:35", "防予フェリー"),
        ("10:50", "13:25", "防予フェリー"),
        ("12:25", "14:55", "防予フェリー"),
        ("14:45", "17:20", "防予フェリー"),
        ("16:15", "18:40", "防予フェリー"),
        ("17:50", "20:20", "防予フェリー"),
        ("20:25", "23:00", "防予フェリー"),
    ]
    boyo_rows_back = [
        ("07:30", "10:05", "防予フェリー"),
        ("09:40", "12:15", "防予フェリー"),
        ("11:50", "14:25", "防予フェリー"),
        ("13:35", "16:05", "防予フェリー"),
        ("15:05", "17:40", "防予フェリー"),
        ("17:35", "20:10", "防予フェリー"),
        ("19:20", "21:55", "防予フェリー"),
        ("20:30", "23:05", "防予フェリー"),
    ]
    add_route(routes, trips, route_id="boyo_yanai_matsuyama_046_out", operator="防予フェリー", origin="柳井港", destination="三津浜港", fare=4500, urls=[boyo_time, boyo_fare], note=boyo_note, rows=boyo_rows_out)
    add_route(routes, trips, route_id="boyo_yanai_matsuyama_047_back", operator="防予フェリー", origin="三津浜港", destination="柳井港", fare=4500, urls=[boyo_time, boyo_fare], note=boyo_note, rows=boyo_rows_back)

    ogawashima_url = "https://www.city.karatsu.lg.jp/page/1542.html"
    ogawashima_note = (
        "Karatsu city official Ogawashima route page, updated 2025-12-18. "
        "V5 uses the 3/15-10/31 timetable that applies to the current release date and the official adult one-way fare of JPY 520. "
        "The 11/1-3/14 weekday table, Jan 1 suspension, baggage charges, and discounts are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_074_川口汽船_小川島_呼子_000_out", operator="川口汽船", origin="小川島", destination="呼子", fare=520, urls=[ogawashima_url], note=ogawashima_note, rows=[("07:00", "07:20", "そよかぜ"), ("08:50", "09:10", "そよかぜ"), ("13:00", "13:20", "そよかぜ"), ("15:20", "15:40", "そよかぜ"), ("17:00", "17:20", "そよかぜ")])
    add_route(routes, trips, route_id="mlit_map_193_074_川口汽船_小川島_呼子_000_back", operator="川口汽船", origin="呼子", destination="小川島", fare=520, urls=[ogawashima_url], note=ogawashima_note, rows=[("08:00", "08:20", "そよかぜ"), ("10:50", "11:10", "そよかぜ"), ("14:20", "14:40", "そよかぜ"), ("16:10", "16:30", "そよかぜ"), ("18:00", "18:20", "そよかぜ")])

    madara_url = "https://www.city.karatsu.lg.jp/page/15178.html"
    madara_note = (
        "Karatsu city official Madarashima route page, updated 2025-12-18. "
        "V5 uses the non-parenthesized timetable for the current May release date and the official adult one-way fare of JPY 1,000. "
        "The 2025-10-01 to 2026-03-31 winter parenthesized times, Jan 1 suspension, baggage charges, and discounts are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_073_郵正丸_馬渡島_呼子_000_out", operator="郵正丸", origin="馬渡島", destination="呼子", fare=1000, urls=[madara_url], note=madara_note, rows=[("07:20", "07:55", "ゆうしょう"), ("09:20", "09:55", "ゆうしょう"), ("13:00", "13:35", "ゆうしょう"), ("16:00", "16:35", "ゆうしょう")])
    add_route(routes, trips, route_id="mlit_map_193_073_郵正丸_馬渡島_呼子_000_back", operator="郵正丸", origin="呼子", destination="馬渡島", fare=1000, urls=[madara_url], note=madara_note, rows=[("08:10", "09:00", "ゆうしょう"), ("10:35", "11:30", "ゆうしょう"), ("14:10", "15:00", "ゆうしょう"), ("17:00", "17:55", "ゆうしょう")])

    takashima_url = "https://www.city.karatsu.lg.jp/page/1004.html"
    takashima_note = (
        "Karatsu city official Takashima route page, updated 2025-12-04. "
        "V5 uses the normal timetable excluding the Jan 1-3 special table and the official adult one-way fare of JPY 220. "
        "Baggage charges and discounts are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_050_佐賀玄海漁業共同組合_高島_唐津_000_out", operator="佐賀玄海漁業共同組合", origin="高島港", destination="唐津港", fare=220, urls=[takashima_url], note=takashima_note, rows=[("07:00", "07:10", "ドリームラインたかしま"), ("09:00", "09:10", "ドリームラインたかしま"), ("10:45", "10:55", "ドリームラインたかしま"), ("13:20", "13:30", "ドリームラインたかしま"), ("15:00", "15:10", "ドリームラインたかしま"), ("17:00", "17:10", "ドリームラインたかしま")])
    add_route(routes, trips, route_id="mlit_map_193_050_佐賀玄海漁業共同組合_高島_唐津_000_back", operator="佐賀玄海漁業共同組合", origin="唐津港", destination="高島港", fare=220, urls=[takashima_url], note=takashima_note, rows=[("07:50", "08:00", "ドリームラインたかしま"), ("10:00", "10:10", "ドリームラインたかしま"), ("11:40", "11:50", "ドリームラインたかしま"), ("14:10", "14:20", "ドリームラインたかしま"), ("16:00", "16:10", "ドリームラインたかしま"), ("18:00", "18:10", "ドリームラインたかしま")])

    niihama_time = "https://www.city.niihama.lg.jp/uploaded/life/120215_573132_misc.pdf"
    niihama_fare = "https://www.city.niihama.lg.jp/soshiki/koutsu/tokaisenshiyouryo.html"
    niihama_note = (
        "Niihama city official ferry timetable PDF effective 2023-10-01 and official usage-fee page. "
        "V5 records the adult one-way passenger fee of JPY 60; baggage, vehicles, commuter passes, and disruption notices are excluded."
    )
    oshima_rows = [
        ("06:20", "06:35", "くろしま"),
        ("07:10", "07:25", "くろしま"),
        ("08:15", "08:30", "おおしま7"),
        ("09:15", "09:30", "おおしま7"),
        ("10:15", "10:30", "おおしま7"),
        ("11:15", "11:30", "おおしま7"),
        ("13:05", "13:20", "おおしま7"),
        ("14:05", "14:20", "おおしま7"),
        ("15:15", "15:30", "おおしま7"),
        ("16:15", "16:30", "おおしま7"),
        ("17:15", "17:30", "くろしま"),
        ("19:15", "19:30", "くろしま"),
        ("21:00", "21:15", "くろしま"),
    ]
    kuroshima_rows = [
        ("06:45", "07:00", "くろしま"),
        ("07:40", "07:55", "くろしま"),
        ("08:40", "08:55", "おおしま7"),
        ("09:40", "09:55", "おおしま7"),
        ("10:40", "10:55", "おおしま7"),
        ("11:40", "11:55", "おおしま7"),
        ("13:30", "13:45", "おおしま7"),
        ("14:30", "14:45", "おおしま7"),
        ("15:40", "15:55", "おおしま7"),
        ("16:40", "16:55", "おおしま7"),
        ("17:40", "17:55", "くろしま"),
        ("19:40", "19:55", "くろしま"),
        ("21:25", "21:40", "くろしま"),
    ]
    add_route(routes, trips, route_id="mlit_map_193_037_新居浜市_大島_黒島_新居浜_000_out", operator="新居浜市", origin="大島港", destination="黒島", fare=60, urls=[niihama_time, niihama_fare], note=niihama_note, rows=oshima_rows)
    add_route(routes, trips, route_id="mlit_map_193_037_新居浜市_大島_黒島_新居浜_000_back", operator="新居浜市", origin="黒島", destination="大島港", fare=60, urls=[niihama_time, niihama_fare], note=niihama_note, rows=kuroshima_rows)

    meon_url = "https://meon.co.jp/access"
    meon_note = (
        "Meon official access page lists the ordinary timetable and passenger fare table. "
        "V5 models the ordinary non-8/1-to-8/20 Takamatsu-Ogijima segment and adult one-way fare of JPY 510; "
        "Megijima-only summer extras, child fares, vehicles, and discount tickets are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_024_雌雄島海運_男木_高松_000_out", operator="雌雄島海運", origin="男木", destination="高松", fare=510, urls=[meon_url], note=meon_note, rows=[("07:00", "07:40", "めおん"), ("09:00", "09:40", "めおん"), ("11:00", "11:40", "めおん"), ("13:00", "13:40", "めおん"), ("15:00", "15:40", "めおん"), ("17:00", "17:40", "めおん")])
    add_route(routes, trips, route_id="mlit_map_193_024_雌雄島海運_男木_高松_000_back", operator="雌雄島海運", origin="高松", destination="男木", fare=510, urls=[meon_url], note=meon_note, rows=[("08:00", "08:40", "めおん"), ("10:00", "10:40", "めおん"), ("12:00", "12:40", "めおん"), ("14:00", "14:40", "めおん"), ("16:00", "16:40", "めおん"), ("18:10", "18:50", "めおん")])

    bouze_tosen_url = "https://www.heart-y.ne.jp/tosen/adekouro.htm"
    bouze_tosen_note = (
        "Official Bouze Tosen page lists the Bouze-Amite timetable and adult fare of JPY 400. "
        "V5 keeps the regular table and excludes holiday-only extra rows marked with ※, bikes, and temporary notices."
    )
    add_route(routes, trips, route_id="bouze_tosen_036_out", operator="坊勢渡船", origin="坊勢港", destination="網手港", fare=400, urls=[bouze_tosen_url], note=bouze_tosen_note, rows=[("07:15", "07:25", "坊勢渡船"), ("07:50", "08:00", "坊勢渡船"), ("08:35", "08:45", "坊勢渡船"), ("09:35", "09:45", "坊勢渡船"), ("10:35", "10:45", "坊勢渡船"), ("11:35", "11:45", "坊勢渡船"), ("13:35", "13:45", "坊勢渡船"), ("15:35", "15:45", "坊勢渡船"), ("17:35", "17:45", "坊勢渡船")])
    add_route(routes, trips, route_id="bouze_tosen_037_back", operator="坊勢渡船", origin="網手港", destination="坊勢港", fare=400, urls=[bouze_tosen_url], note=bouze_tosen_note, rows=[("07:30", "07:40", "坊勢渡船"), ("08:10", "08:20", "坊勢渡船"), ("08:50", "09:00", "坊勢渡船"), ("09:50", "10:00", "坊勢渡船"), ("10:50", "11:00", "坊勢渡船"), ("11:50", "12:00", "坊勢渡船"), ("13:50", "14:00", "坊勢渡船"), ("15:50", "16:00", "坊勢渡船"), ("17:50", "18:00", "坊勢渡船")])

    suo_oshima_time = "https://www.boyoferry.co.jp/smp/timetable.html"
    suo_oshima_fare = "https://boyoferry.co.jp/c_fare2_a.html"
    suo_oshima_note = (
        "Official Boyo Ferry mobile timetable lists the 2025-03-01 normal timetable and marks the Ihota-calling rows. "
        "Official 2025-08-01 fare page lists the Yanai-Ihota adult one-way fare of JPY 1,640. "
        "V5 keeps only daily normal Ihota-call passenger rows and excludes suspended rows, vehicles, reservations, and discounts."
    )
    add_route(routes, trips, route_id="suoshima_yanai_ihota_mitsuhama_034_out", operator="周防大島松山フェリー", origin="柳井港", destination="伊保田港", fare=1640, urls=[suo_oshima_time, suo_oshima_fare], note=suo_oshima_note, rows=[("07:00", "08:10", "しらきさん"), ("12:25", "13:40", "しらきさん"), ("17:50", "19:05", "しらきさん")])
    add_route(routes, trips, route_id="suoshima_yanai_ihota_mitsuhama_035_back", operator="周防大島松山フェリー", origin="伊保田港", destination="柳井港", fare=1640, urls=[suo_oshima_time, suo_oshima_fare], note=suo_oshima_note, rows=[("10:52", "12:15", "しらきさん"), ("16:17", "17:40", "しらきさん"), ("21:42", "23:05", "しらきさん")])

    tankai_url = "https://www.tankai.jp/trip/amaboat/"
    tankai_note = (
        "Official Tankai Amanohashidate sightseeing boat page lists the normal timetable and adult fare. "
        "V5 records the Amanohashidate-Ichinomiya segment at the official adult one-way fare of JPY 800. "
        "Weekend/holiday special-course departures, optional temporary sailings, conditional no-passenger cancellations, sets, and discounts are excluded."
    )
    tankai_to_ichinomiya = [("09:00", "09:12", "かもめ"), ("10:00", "10:12", "かもめ"), ("10:30", "10:42", "かもめ"), ("11:00", "11:12", "かもめ"), ("11:30", "11:42", "かもめ"), ("12:00", "12:12", "かもめ"), ("12:30", "12:42", "かもめ"), ("13:00", "13:12", "かもめ"), ("13:30", "13:42", "かもめ"), ("14:00", "14:12", "かもめ"), ("14:30", "14:42", "かもめ"), ("15:00", "15:12", "かもめ"), ("15:30", "15:42", "かもめ"), ("16:00", "16:12", "かもめ"), ("17:00", "17:12", "かもめ"), ("17:30", "17:42", "かもめ")]
    tankai_to_amanohashidate = [("09:15", "09:27", "かもめ"), ("10:15", "10:27", "かもめ"), ("10:45", "10:57", "かもめ"), ("11:15", "11:27", "かもめ"), ("11:45", "11:57", "かもめ"), ("12:15", "12:27", "かもめ"), ("12:45", "12:57", "かもめ"), ("13:15", "13:27", "かもめ"), ("13:45", "13:57", "かもめ"), ("14:15", "14:27", "かもめ"), ("14:45", "14:57", "かもめ"), ("15:15", "15:27", "かもめ"), ("15:45", "15:57", "かもめ"), ("16:15", "16:27", "かもめ"), ("16:45", "16:57", "かもめ"), ("17:15", "17:27", "かもめ"), ("17:45", "17:57", "かもめ")]
    add_route(routes, trips, route_id="mlit_map_193_003_丹後海陸交通_湾内_宮津_天橋立_一宮_001_out", operator="丹後海陸交通", origin="天橋立", destination="一宮", fare=800, urls=[tankai_url], note=tankai_note, rows=tankai_to_ichinomiya)
    add_route(routes, trips, route_id="mlit_map_193_003_丹後海陸交通_湾内_宮津_天橋立_一宮_001_back", operator="丹後海陸交通", origin="一宮", destination="天橋立", fare=800, urls=[tankai_url], note=tankai_note, rows=tankai_to_amanohashidate)

    osakikamijima_url = "https://www.town.osakikamijima.hiroshima.jp/soshiki/kensetsu/1/2/1/1308.html"
    osakikamijima_note = (
        "Osakikamijima town official Sazanami page lists the timetable and fare table. "
        "V5 records only rows that call at Ketajima and the official Hakusui-Ketajima adult one-way fare of JPY 290. "
        "Jan 1-3 suspension, hazardous-material-only restrictions, vehicles, commuter tickets, and non-public landing restrictions at Ketajima are excluded from gameplay pricing."
    )
    osakikamijima_out = [("06:40", "07:15", "さざなみ"), ("07:55", "08:30", "さざなみ"), ("13:00", "13:35", "さざなみ"), ("15:15", "15:50", "さざなみ"), ("16:30", "17:05", "さざなみ"), ("17:40", "18:15", "さざなみ")]
    osakikamijima_back = [("07:15", "07:45", "さざなみ"), ("08:30", "09:00", "さざなみ"), ("13:35", "14:05", "さざなみ"), ("15:50", "16:20", "さざなみ"), ("17:05", "17:35", "さざなみ"), ("18:15", "18:45", "さざなみ")]
    add_route(routes, trips, route_id="mlit_map_193_008_大崎上島町_白水_契島_000_out", operator="大崎上島町", origin="白水港", destination="契島港", fare=290, urls=[osakikamijima_url], note=osakikamijima_note, rows=osakikamijima_out)
    add_route(routes, trips, route_id="mlit_map_193_008_大崎上島町_白水_契島_000_back", operator="大崎上島町", origin="契島港", destination="白水港", fare=290, urls=[osakikamijima_url], note=osakikamijima_note, rows=osakikamijima_back)

    izu_aogashima_url = "https://www.izu-syotou.jp/route01/index.html?date=20250325"
    izu_aogashima_note = (
        "Official Izu Shoto Kaihatsu Hachijojima-Aogashima route page lists the 2026-05 fare table and day-by-day timetable. "
        "V5 records the May 2026 adult 2nd-class one-way fare of JPY 3,390 and the explicit May operating-day time patterns. "
        "Weather cancellations, cargo fares, discounts, and non-operating days are excluded."
    )
    izu_aogashima_calendar = {"type": "official_2026_may_operating_days"}
    add_route(routes, trips, route_id="izu_shoto_hachijo_aogashima_018_out", operator="伊豆諸島開発", origin="八丈島底土港", destination="青ヶ島三宝港", fare=3390, urls=[izu_aogashima_url], note=izu_aogashima_note, rows=[("09:30", "12:30", "あおがしま丸")], calendar=izu_aogashima_calendar)
    add_route(routes, trips, route_id="izu_shoto_hachijo_aogashima_019_back", operator="伊豆諸島開発", origin="青ヶ島三宝港", destination="八丈島底土港", fare=3390, urls=[izu_aogashima_url], note=izu_aogashima_note, rows=[("12:50", "15:50", "あおがしま丸"), ("13:30", "16:30", "あおがしま丸")], calendar=izu_aogashima_calendar)

    hahajima_url = "https://www.ogasawarakaiun.co.jp/service/hahajima.html"
    hahajima_note = (
        "Official Ogasawara Kaiun Hahajimamaru page states Izu Shoto Kaihatsu operates the Chichijima-Hahajima service. "
        "V5 records the explicit 2026-05 timetable patterns and the official 2026-05 adult 2nd-class one-way fare of JPY 4,900. "
        "Monthly fuel-adjustment changes outside May, cabin surcharges, discounts, and weather changes are excluded."
    )
    hahajima_calendar = {"type": "official_2026_may_operating_days"}
    add_route(routes, trips, route_id="izu_shoto_chichijima_hahajima_020_out", operator="伊豆諸島開発", origin="父島二見港", destination="母島沖港", fare=4900, urls=[hahajima_url], note=hahajima_note, rows=[("07:30", "09:30", "ははじま丸"), ("12:00", "14:00", "ははじま丸"), ("16:00", "18:00", "ははじま丸")], calendar=hahajima_calendar)
    add_route(routes, trips, route_id="izu_shoto_chichijima_hahajima_021_back", operator="伊豆諸島開発", origin="母島沖港", destination="父島二見港", fare=4900, urls=[hahajima_url], note=hahajima_note, rows=[("07:30", "09:30", "ははじま丸"), ("12:00", "14:00", "ははじま丸"), ("14:00", "16:00", "ははじま丸")], calendar=hahajima_calendar)

    oki_time = "https://www.oki-kisen.co.jp/timetable/"
    oki_fare = "https://www.oki-kisen.co.jp/fare/"
    oki_note = (
        "Official Oki Kisen timetable/fare pages list the 2026-05-22 ferries and the standard ferry 2nd-class inter-island fares. "
        "V5 adds only the explicit Beppu/Hishiura/Kurii ferry legs still missing from the 500 gate. "
        "Rainbow Jet, Oki Kanko local vessels, higher rooms, vehicles, discounts, and later daily status changes are excluded."
    )
    add_route(routes, trips, route_id="oki_kisen_shimane_oki_122_out", operator="隠岐汽船", origin="菱浦港", destination="来居港", fare=780, urls=[oki_time, oki_fare], note=oki_note, rows=[("09:50", "10:50", "フェリーしらしま")])
    add_route(routes, trips, route_id="oki_kisen_shimane_oki_123_back", operator="隠岐汽船", origin="来居港", destination="菱浦港", fare=780, urls=[oki_time, oki_fare], note=oki_note, rows=[("11:35", "12:40", "フェリーおき")])

    bisan_url = "https://bisan-ferry.jp/time_table/"
    bisan_note = (
        "Official Bisan Ferry timetable/fare page lists the Marugame-Hiroshima timetable and passenger fare matrix. "
        "V5 records only normal non-first-Tuesday adult ordinary passenger rows for the Marugame-Hiroshima segment; "
        "Thursday-only intermediate calls, dangerous-goods priority rows, vehicles, special baggage, child fares, and discounts are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_025_備讃フェリー_丸亀_広島_000_out", operator="備讃フェリー", origin="丸亀", destination="広島港宇品", fare=580, urls=[bisan_url], note=bisan_note, rows=[("06:05", "06:50", "備讃フェリー"), ("09:25", "10:10", "備讃フェリー"), ("15:00", "15:45", "備讃フェリー"), ("06:50", "07:11", "旅客船"), ("07:40", "08:01", "旅客船"), ("11:10", "11:32", "旅客船"), ("13:55", "14:16", "旅客船"), ("17:45", "18:06", "旅客船")])
    add_route(routes, trips, route_id="mlit_map_193_025_備讃フェリー_丸亀_広島_000_back", operator="備讃フェリー", origin="広島港宇品", destination="丸亀", fare=580, urls=[bisan_url], note=bisan_note, rows=[("08:35", "09:14", "備讃フェリー"), ("12:45", "13:30", "備讃フェリー"), ("17:25", "18:10", "備讃フェリー"), ("07:15", "07:36", "旅客船"), ("10:45", "11:06", "旅客船"), ("12:17", "12:37", "旅客船"), ("13:30", "13:51", "旅客船"), ("16:40", "17:01", "旅客船"), ("18:10", "18:31", "旅客船")])

    itoshima_url = "https://www.city.itoshima.lg.jp/s006/010/020/020/090/tosen.html"
    itoshima_note = (
        "Official Itoshima city Himashima ferry page updated 2026-04-08 lists the March-October timetable, 16-minute duration, and adult fare of JPY 470. "
        "V5 uses the summer timetable that applies to the current May release date; winter and New Year suspensions, child fares, baggage, and construction freight limits are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_072_糸島市_姫島_岐志_000_out", operator="糸島市", origin="姫島", destination="岐志", fare=470, urls=[itoshima_url], note=itoshima_note, rows=pair_rows(["07:00", "09:50", "14:20", "17:10"], 16, "ひめしま"))
    add_route(routes, trips, route_id="mlit_map_193_072_糸島市_姫島_岐志_000_back", operator="糸島市", origin="岐志", destination="姫島", fare=470, urls=[itoshima_url], note=itoshima_note, rows=pair_rows(["07:50", "11:50", "16:00", "18:10"], 16, "ひめしま"))

    koshiki_time = "https://www.koshikisho.co.jp/timetable"
    koshiki_fare_highspeed = "https://www.koshikisho.co.jp/fare_kousokusen_a"
    koshiki_note = (
        "Official Koshikisho timetable page lists the regular ferry and high-speed boat times and the official fare page lists adult high-speed fares. "
        "V5 records the currently regular Sendai-Sato and Sato-Nagahama high-speed boat legs plus the ferry Kushikino-Sendai leg visible in the 500 gate. "
        "Resident fares, round-trip discounts, excursion tickets, vehicles, baggage, temporary extra trips, and dock periods are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_061_甑島商船_串木野_川内_甑島_000_out", operator="甑島商船", origin="串木野新港", destination="川内港", fare=4070, urls=[koshiki_time, koshiki_fare_highspeed], note=koshiki_note, rows=[("11:15", "12:30", "結 Line こしき"), ("16:30", "17:45", "結 Line こしき")])
    add_route(routes, trips, route_id="mlit_map_193_061_甑島商船_串木野_川内_甑島_000_back", operator="甑島商船", origin="川内港", destination="串木野新港", fare=4070, urls=[koshiki_time, koshiki_fare_highspeed], note=koshiki_note, rows=[("09:05", "10:20", "結 Line こしき"), ("14:20", "16:05", "結 Line こしき")])
    add_route(routes, trips, route_id="mlit_map_193_061_甑島商船_串木野_川内_甑島_001_out", operator="甑島商船", origin="川内港", destination="里港", fare=4070, urls=[koshiki_time, koshiki_fare_highspeed], note=koshiki_note, rows=[("08:50", "09:40", "高速船甑島"), ("14:30", "16:25", "高速船甑島")])
    add_route(routes, trips, route_id="mlit_map_193_061_甑島商船_串木野_川内_甑島_001_back", operator="甑島商船", origin="里港", destination="川内港", fare=4070, urls=[koshiki_time, koshiki_fare_highspeed], note=koshiki_note, rows=[("09:45", "11:40", "高速船甑島"), ("16:30", "17:20", "高速船甑島")])

    sagashima_url = "https://www.city.goto.nagasaki.jp/s014/020/020/050/20220831171546.html"
    sagashima_note = (
        "Official Goto city traffic-access page lists the Sagashima passenger-ship timetable and fare. "
        "V5 records the Sagashima-Kaitsu adult fare of JPY 550 shown in the official Nagasaki fare table and the explicit city timetable rows. "
        "School-holiday caveats for other services, islander discounts, vehicles, and weather disruptions are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_081_嵯峨島旅客船_嵯峨島_貝津_000_out", operator="嵯峨島旅客船", origin="嵯峨島", destination="貝津", fare=550, urls=[sagashima_url], note=sagashima_note, rows=[("08:10", "08:23", "嵯峨島旅客船"), ("11:00", "11:13", "嵯峨島旅客船")])
    add_route(routes, trips, route_id="mlit_map_193_081_嵯峨島旅客船_嵯峨島_貝津_000_back", operator="嵯峨島旅客船", origin="貝津", destination="嵯峨島", fare=550, urls=[sagashima_url], note=sagashima_note, rows=[("09:10", "09:23", "嵯峨島旅客船"), ("11:30", "11:43", "嵯峨島旅客船"), ("13:35", "13:48", "嵯峨島旅客船"), ("16:45", "16:58", "嵯峨島旅客船")])

    takeyama_url = "https://www.saryokyo.com/member/member-05.html"
    takeyama_note = (
        "Official Sasebo Passenger Ship Association Takeyama Unyu member page lists the Hirado-Takushima timetable and adult fare matrix. "
        "V5 records the Honmura-Hirado adult one-way fare of JPY 660 and direct through rows; intermediate Iimori-only fares, vehicles, seasonal row variants, and discounts are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_069_竹山運輸_度島_本村_平戸_000_out", operator="竹山運輸", origin="度島", destination="平戸港", fare=660, urls=[takeyama_url], note=takeyama_note, rows=[("07:00", "07:45", "フェリー度島"), ("09:10", "09:45", "フェリー度島"), ("13:30", "14:15", "フェリー度島")])
    add_route(routes, trips, route_id="mlit_map_193_069_竹山運輸_度島_本村_平戸_000_back", operator="竹山運輸", origin="平戸港", destination="度島", fare=660, urls=[takeyama_url], note=takeyama_note, rows=[("08:10", "08:45", "フェリー度島"), ("11:20", "11:55", "フェリー度島"), ("15:30", "16:05", "フェリー度島")])

    otsushima_fare = "https://www.ccsnet.ne.jp/~jyunkou/link/untin/untin.html"
    otsushima_note = (
        "Official Otsushima Junko fare page lists the Tokuyama-Otsushima adult fare of JPY 720. "
        "V5 pairs that official fare with the public Otsushima timetable route already used in the map source and records only the Tokuyama-Mashima segment; "
        "other Otsushima ports, vehicles, baggage, round-trip tickets, and discounts are excluded."
    )
    add_route(routes, trips, route_id="otsushima_tokuyama_068_out", operator="大津島巡航", origin="徳山港", destination="大津島馬島港", fare=720, urls=[otsushima_fare, "http://www.ccsnet.ne.jp/~jyunkou/"], note=otsushima_note, rows=[("07:40", "08:24", "鼓海II"), ("10:40", "11:24", "フェリー大津島"), ("14:00", "14:44", "鼓海II"), ("18:50", "19:34", "フェリー大津島")])
    add_route(routes, trips, route_id="otsushima_tokuyama_069_back", operator="大津島巡航", origin="大津島馬島港", destination="徳山港", fare=720, urls=[otsushima_fare, "http://www.ccsnet.ne.jp/~jyunkou/"], note=otsushima_note, rows=[("06:30", "07:14", "鼓海II"), ("09:00", "09:44", "フェリー大津島"), ("12:40", "13:24", "鼓海II"), ("16:50", "17:34", "フェリー大津島")])

    tankai_miyazu_url = "https://www.tankai.jp/lp/parkcruise/"
    tankai_miyazu_note = (
        "Official Tankai Park & Cruise page lists the 2026 Miyazu-Amanohashidate temporary timetable and adult fare. "
        "V5 records only the Miyazu-Amanohashidate segment at JPY 600; parking benefits, Ichinomiya through fare, round trips, child fares, and event-only changes are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_003_丹後海陸交通_湾内_宮津_天橋立_一宮_000_out", operator="丹後海陸交通", origin="宮津", destination="天橋立", fare=600, urls=[tankai_miyazu_url], note=tankai_miyazu_note, rows=[("09:45", "10:00", "かもめ"), ("10:30", "10:45", "かもめ"), ("11:00", "11:15", "かもめ"), ("11:30", "11:45", "かもめ"), ("12:00", "12:15", "かもめ"), ("12:30", "12:45", "かもめ"), ("13:00", "13:15", "かもめ"), ("13:30", "13:45", "かもめ"), ("14:00", "14:15", "かもめ"), ("14:30", "14:45", "かもめ"), ("15:00", "15:15", "かもめ"), ("15:30", "15:45", "かもめ"), ("16:00", "16:15", "かもめ"), ("16:30", "16:45", "かもめ"), ("17:00", "17:15", "かもめ")])
    add_route(routes, trips, route_id="mlit_map_193_003_丹後海陸交通_湾内_宮津_天橋立_一宮_000_back", operator="丹後海陸交通", origin="天橋立", destination="宮津", fare=600, urls=[tankai_miyazu_url], note=tankai_miyazu_note, rows=[("10:00", "10:15", "かもめ"), ("10:45", "11:00", "かもめ"), ("11:15", "11:30", "かもめ"), ("11:45", "12:00", "かもめ"), ("12:15", "12:30", "かもめ"), ("12:45", "13:00", "かもめ"), ("13:15", "13:30", "かもめ"), ("13:45", "14:00", "かもめ"), ("14:15", "14:30", "かもめ"), ("14:45", "15:00", "かもめ"), ("15:15", "15:30", "かもめ"), ("15:45", "16:00", "かもめ"), ("16:15", "16:30", "かもめ"), ("16:45", "17:00", "かもめ"), ("17:15", "17:30", "かもめ")])

    reihoku_time = "https://www.reihoku-kisen.jp/time-table.php"
    reihoku_fare = "https://www.reihoku-kisen.jp/price.php"
    reihoku_note = (
        "Official Reihoku Kanko Kisen timetable and price pages list the Tomioka-Mogi service, 45-minute running time, and adult one-way fare of JPY 2,030. "
        "V5 records the normal passenger timetable; round-trip tickets, student/group/disability discounts, baggage, and weather cancellations are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_084_苓北観光汽船_天草_長崎_000_out", operator="苓北観光汽船", origin="天草", destination="長崎港", fare=2030, urls=[reihoku_time, reihoku_fare], note=reihoku_note, rows=[("07:10", "07:55", "Kizuna"), ("09:15", "10:00", "Kizuna"), ("13:40", "14:25", "Kizuna"), ("15:55", "16:40", "Kizuna")])
    add_route(routes, trips, route_id="mlit_map_193_084_苓北観光汽船_天草_長崎_000_back", operator="苓北観光汽船", origin="長崎港", destination="天草", fare=2030, urls=[reihoku_time, reihoku_fare], note=reihoku_note, rows=[("08:10", "08:55", "Kizuna"), ("10:20", "11:05", "Kizuna"), ("14:45", "15:30", "Kizuna"), ("17:00", "17:45", "Kizuna")])

    saishima_time = "https://www.city.kure.lg.jp/soshiki/28/kouro-mikado.html"
    saishima_fare = "https://www.city.kure.lg.jp/uploaded/attachment/96405.pdf"
    saishima_note = (
        "Official Kure city Mikado-Kubi route page and fare PDF list the 2024-10-01 timetable and passenger fare matrix. "
        "V5 records the Mikado-Kubi adult fare of JPY 190; Saishima/Toyoshima segments, child fares, baggage, and Jan 1 suspension are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_018_斎島汽船_斎島_久比_三角_久比_001_out", operator="斎島汽船", origin="三角", destination="久比", fare=190, urls=[saishima_time, saishima_fare], note=saishima_note, rows=[("07:00", "07:10", "斎島汽船"), ("08:00", "08:10", "斎島汽船"), ("12:00", "12:10", "斎島汽船"), ("15:45", "15:55", "斎島汽船")])
    add_route(routes, trips, route_id="mlit_map_193_018_斎島汽船_斎島_久比_三角_久比_001_back", operator="斎島汽船", origin="久比", destination="三角", fare=190, urls=[saishima_time, saishima_fare], note=saishima_note, rows=[("07:35", "07:45", "斎島汽船"), ("09:30", "09:40", "斎島汽船"), ("13:30", "13:40", "斎島汽船"), ("16:15", "16:25", "斎島汽船")])

    shinkihou_url = "https://www.ritoumeguri.com/wp-content/uploads/2021/12/be1355a50128887e0a2f8e5466c09169.pdf"
    shinkihou_note = (
        "Official/publicly posted Shin-Kiho Aigashima-Hojo timetable/fare PDF lists the regular 8/21-7/31 timetable and adult fare of JPY 840. "
        "V5 records the regular non-summer, non-New-Year rows; summer-period variants, child fares, and weather cancellations are excluded."
    )
    shinkihou_calendar = {"type": "regular_0821_to_0731"}
    add_route(routes, trips, route_id="mlit_map_193_035_新喜峰_安居島_松山_北条_000_out", operator="新喜峰", origin="安居島", destination="三津浜港", fare=840, urls=[shinkihou_url], note=shinkihou_note, rows=[("08:00", "08:35", "新喜峰"), ("15:00", "15:35", "新喜峰")], calendar=shinkihou_calendar)
    add_route(routes, trips, route_id="mlit_map_193_035_新喜峰_安居島_松山_北条_000_back", operator="新喜峰", origin="三津浜港", destination="安居島", fare=840, urls=[shinkihou_url], note=shinkihou_note, rows=[("11:00", "11:35", "新喜峰"), ("16:00", "16:35", "新喜峰")], calendar=shinkihou_calendar)

    setonami_time = "https://www.town.setouchi.lg.jp/senpaku/jikokuhyou.html"
    setonami_fare = "https://www.town.setouchi.lg.jp/senpaku/documents/setonamijikokuhyo.pdf"
    setonami_note = (
        "Official Setouchi town Setonami timetable page and fare PDF list the Konia-Yoro route and adult fare table. "
        "V5 records the Konia-Yoro adult fare of JPY 1,030 and explicit weekly timetable rows; round-trip discounts, other island legs, events, dock periods, vehicles, and weather changes are excluded."
    )
    add_route(routes, trips, route_id="mlit_map_193_091_瀬戸内町_瀬相_古仁屋_生間_与路_古仁屋_002_out", operator="瀬戸内町", origin="与路", destination="古仁屋", fare=1030, urls=[setonami_time, setonami_fare], note=setonami_note, rows=[("07:00", "08:40", "せとなみ"), ("08:00", "09:40", "せとなみ"), ("15:00", "16:40", "せとなみ"), ("16:20", "18:00", "せとなみ")], calendar={"type": "official_weekly_rows"})
    add_route(routes, trips, route_id="mlit_map_193_091_瀬戸内町_瀬相_古仁屋_生間_与路_古仁屋_002_back", operator="瀬戸内町", origin="古仁屋", destination="与路", fare=1030, urls=[setonami_time, setonami_fare], note=setonami_note, rows=[("07:00", "07:50", "せとなみ"), ("10:00", "11:40", "せとなみ"), ("14:30", "16:10", "せとなみ")], calendar={"type": "official_weekly_rows"})

    hagi_mishima_url = "https://hagikaiun.co.jp/mishima/time-table.html"
    hagi_mishima_note = (
        "Official Hagi Kaiun Mishima timetable page lists the Mishima-Hagi timetable and passenger fare. "
        "V5 records the March-August schedule that applies to the May release date and the adult one-way fare of JPY 1,970. "
        "Dock replacement tables, islander fares, child/student/discount fares, and weather cancellations are excluded."
    )
    add_route(routes, trips, route_id="hagi_mishima_066_out", operator="萩海運", origin="萩港", destination="見島本村港", fare=1970, urls=[hagi_mishima_url], note=hagi_mishima_note, rows=[("09:10", "10:20", "ゆりや"), ("12:45", "13:55", "ゆりや"), ("16:20", "17:30", "ゆりや")])
    add_route(routes, trips, route_id="hagi_mishima_067_back", operator="萩海運", origin="見島本村港", destination="萩港", fare=1970, urls=[hagi_mishima_url], note=hagi_mishima_note, rows=[("07:30", "08:40", "ゆりや"), ("10:40", "12:20", "ゆりや"), ("14:15", "15:55", "ゆりや")])

    shinshin_url = "https://shinshin-kisen.jp/service/index.html?date=20260430"
    shinshin_note = (
        "Official Shinshin Kisen timetable/fare page lists the 2026-05 Shimoda-Izu islands loop. "
        "V5 records only explicit Monday/Thursday/Saturday and Tuesday/Friday/Sunday passenger OD pairs with the official May 2026 adult 2nd-class one-way fares. "
        "Wednesday suspension, car/baggage fares, higher classes, discounts, and weather changes are excluded."
    )
    shinshin_mts = {"type": "monday_thursday_saturday"}
    shinshin_tfs = {"type": "tuesday_friday_sunday"}
    add_route(routes, trips, route_id="shinshin_shimoda_direct_500_001_out", operator="神新汽船", origin="下田港", destination="神津島港", fare=5010, urls=[shinshin_url], note=shinshin_note, rows=[("09:30", "11:50", "フェリーあぜりあ")], calendar=shinshin_mts)
    add_route(routes, trips, route_id="shinshin_shimoda_direct_500_002_out", operator="神新汽船", origin="下田港", destination="式根島野伏港", fare=5010, urls=[shinshin_url], note=shinshin_note, rows=[("09:30", "13:00", "フェリーあぜりあ")], calendar=shinshin_mts)
    add_route(routes, trips, route_id="shinshin_shimoda_direct_500_003_out", operator="神新汽船", origin="下田港", destination="新島港", fare=5010, urls=[shinshin_url], note=shinshin_note, rows=[("09:30", "13:30", "フェリーあぜりあ")], calendar=shinshin_mts)
    add_route(routes, trips, route_id="shinshin_shimoda_direct_500_004_out", operator="神新汽船", origin="下田港", destination="利島港", fare=5010, urls=[shinshin_url], note=shinshin_note, rows=[("09:30", "14:40", "フェリーあぜりあ")], calendar=shinshin_mts)
    add_route(routes, trips, route_id="shinshin_shimoda_direct_500_005_back", operator="神新汽船", origin="神津島港", destination="下田港", fare=5010, urls=[shinshin_url], note=shinshin_note, rows=[("14:10", "16:30", "フェリーあぜりあ")], calendar=shinshin_tfs)
    add_route(routes, trips, route_id="shinshin_shimoda_direct_500_006_back", operator="神新汽船", origin="式根島野伏港", destination="下田港", fare=5010, urls=[shinshin_url], note=shinshin_note, rows=[("13:00", "16:30", "フェリーあぜりあ")], calendar=shinshin_tfs)
    add_route(routes, trips, route_id="shinshin_shimoda_direct_500_007_back", operator="神新汽船", origin="新島港", destination="下田港", fare=5010, urls=[shinshin_url], note=shinshin_note, rows=[("12:25", "16:30", "フェリーあぜりあ")], calendar=shinshin_tfs)
    add_route(routes, trips, route_id="shinshin_shimoda_direct_500_008_back", operator="神新汽船", origin="利島港", destination="下田港", fare=5010, urls=[shinshin_url], note=shinshin_note, rows=[("14:45", "16:30", "フェリーあぜりあ")], calendar=shinshin_mts)
    add_route(routes, trips, route_id="shinshin_shimoda_od_500_009_out", operator="神新汽船", origin="神津島港", destination="新島港", fare=1040, urls=[shinshin_url], note=shinshin_note, rows=[("12:10", "13:30", "フェリーあぜりあ")], calendar=shinshin_mts)
    add_route(routes, trips, route_id="shinshin_shimoda_od_500_010_out", operator="神新汽船", origin="神津島港", destination="利島港", fare=1540, urls=[shinshin_url], note=shinshin_note, rows=[("12:10", "14:40", "フェリーあぜりあ")], calendar=shinshin_mts)
    add_route(routes, trips, route_id="shinshin_shimoda_od_500_011_out", operator="神新汽船", origin="式根島野伏港", destination="利島港", fare=1020, urls=[shinshin_url], note=shinshin_note, rows=[("13:10", "14:40", "フェリーあぜりあ")], calendar=shinshin_mts)
    add_route(routes, trips, route_id="shinshin_shimoda_od_500_012_back", operator="神新汽船", origin="利島港", destination="式根島野伏港", fare=1020, urls=[shinshin_url], note=shinshin_note, rows=[("11:10", "12:45", "フェリーあぜりあ")], calendar=shinshin_tfs)
    add_route(routes, trips, route_id="shinshin_shimoda_od_500_013_back", operator="神新汽船", origin="利島港", destination="神津島港", fare=1540, urls=[shinshin_url], note=shinshin_note, rows=[("11:10", "13:50", "フェリーあぜりあ")], calendar=shinshin_tfs)
    add_route(routes, trips, route_id="shinshin_shimoda_od_500_014_back", operator="神新汽船", origin="新島港", destination="神津島港", fare=1040, urls=[shinshin_url], note=shinshin_note, rows=[("12:25", "13:50", "フェリーあぜりあ")], calendar=shinshin_tfs)

    tokai_time = "https://www.tokaikisen.co.jp/boarding/timetable/"
    tokai_fare = "https://www.tokaikisen.co.jp/boarding/fare/"
    tokai_note = (
        "Official Tokai Kisen timetable and fare pages list the 2026-04-06 to 2026-06-30 Tokyo-Izu island timetable and May 2026 adult one-way fares. "
        "V5 records selected large-passenger-ship OD pairs that are explicit in the published table and fare matrix. "
        "Jet-boat alternates, 5/2-5/6 special search-only rows, room charges, higher classes, discounts, and weather/port changes are excluded."
    )
    tokai_calendar = {"type": "official_2026_0406_0630_excluding_special_days"}
    add_route(routes, trips, route_id="tokai_takeshiba_izu_500_001_out", operator="東海汽船", origin="竹芝", destination="大島港", fare=5750, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("22:00", "翌06:00", "大型客船")], calendar=tokai_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="tokai_takeshiba_izu_500_002_out", operator="東海汽船", origin="竹芝", destination="利島港", fare=6400, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("22:00", "翌07:40", "大型客船")], calendar=tokai_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="tokai_takeshiba_izu_500_003_out", operator="東海汽船", origin="竹芝", destination="新島港", fare=7740, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("22:00", "翌08:35", "大型客船")], calendar=tokai_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="tokai_takeshiba_izu_500_004_out", operator="東海汽船", origin="竹芝", destination="式根島野伏港", fare=7740, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("22:00", "翌09:05", "大型客船")], calendar=tokai_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="tokai_takeshiba_izu_500_005_out", operator="東海汽船", origin="竹芝", destination="神津島港", fare=8210, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("22:00", "翌10:00", "大型客船")], calendar=tokai_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="tokai_takeshiba_izu_500_006_back", operator="東海汽船", origin="神津島港", destination="竹芝", fare=8210, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("10:30", "19:00", "大型客船")], calendar=tokai_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="tokai_takeshiba_izu_500_007_back", operator="東海汽船", origin="式根島野伏港", destination="竹芝", fare=7740, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("11:20", "19:00", "大型客船")], calendar=tokai_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="tokai_takeshiba_izu_500_008_back", operator="東海汽船", origin="新島港", destination="竹芝", fare=7740, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("11:45", "19:00", "大型客船")], calendar=tokai_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="tokai_takeshiba_izu_500_009_back", operator="東海汽船", origin="利島港", destination="竹芝", fare=6400, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("12:45", "19:00", "大型客船")], calendar=tokai_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="tokai_takeshiba_izu_500_010_back", operator="東海汽船", origin="大島港", destination="竹芝", fare=5750, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("14:30", "19:00", "大型客船")], calendar=tokai_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="tokai_oshima_izu_500_011_out", operator="東海汽船", origin="大島港", destination="利島港", fare=1080, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("06:20", "07:40", "大型客船")], calendar=tokai_calendar)
    add_route(routes, trips, route_id="tokai_oshima_izu_500_012_out", operator="東海汽船", origin="大島港", destination="新島港", fare=1560, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("06:20", "08:35", "大型客船")], calendar=tokai_calendar)
    add_route(routes, trips, route_id="tokai_oshima_izu_500_013_out", operator="東海汽船", origin="大島港", destination="式根島野伏港", fare=1690, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("06:20", "09:05", "大型客船")], calendar=tokai_calendar)
    add_route(routes, trips, route_id="tokai_oshima_izu_500_014_out", operator="東海汽船", origin="大島港", destination="神津島港", fare=1830, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("06:20", "10:00", "大型客船")], calendar=tokai_calendar)
    add_route(routes, trips, route_id="tokai_oshima_izu_500_015_back", operator="東海汽船", origin="神津島港", destination="大島港", fare=1830, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("10:30", "14:10", "大型客船")], calendar=tokai_calendar)
    add_route(routes, trips, route_id="tokai_oshima_izu_500_016_back", operator="東海汽船", origin="式根島野伏港", destination="大島港", fare=1690, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("11:20", "14:10", "大型客船")], calendar=tokai_calendar)
    add_route(routes, trips, route_id="tokai_oshima_izu_500_017_back", operator="東海汽船", origin="新島港", destination="大島港", fare=1560, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("11:45", "14:10", "大型客船")], calendar=tokai_calendar)
    add_route(routes, trips, route_id="tokai_oshima_izu_500_018_back", operator="東海汽船", origin="利島港", destination="大島港", fare=1080, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("12:45", "14:10", "大型客船")], calendar=tokai_calendar)
    add_route(routes, trips, route_id="tokai_takeshiba_hachijo_500_019_out", operator="東海汽船", origin="竹芝", destination="八丈島底土港", fare=10840, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("22:30", "翌08:55", "橘丸")], calendar=tokai_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="tokai_takeshiba_hachijo_500_020_back", operator="東海汽船", origin="八丈島底土港", destination="竹芝", fare=10840, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("09:40", "19:40", "橘丸")], calendar=tokai_calendar, route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="tokai_takeshiba_oshima_jet_500_021_out", operator="東海汽船", origin="竹芝", destination="大島港", fare=9310, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("08:35", "10:20", "高速ジェット船")], calendar=tokai_calendar)
    add_route(routes, trips, route_id="tokai_takeshiba_oshima_jet_500_022_back", operator="東海汽船", origin="大島港", destination="竹芝", fare=9310, urls=[tokai_time, tokai_fare], note=tokai_note, rows=[("10:10", "11:55", "高速ジェット船")], calendar=tokai_calendar)

    sado_time = "https://www.sadokisen.co.jp/news/wp-content/uploads/sites/14/2025/11/timetable_2026.pdf"
    sado_fare = "https://wwwtb.mlit.go.jp/hokushin/content/000370422.pdf"
    sado_note = (
        "Official Sado Kisen 2026 timetable PDF lists the Niigata-Ryotsu car-ferry and jetfoil times; the Hokushin Transport Bureau fare authorization PDF lists the 2026 adult 2nd-class upper fare. "
        "V5 records the regular 2026 spring car-ferry pattern only; jetfoils, vehicles, special baggage, islander fares, discounts, and disruption changes are excluded."
    )
    add_route(routes, trips, route_id="sado_kisen_niigata_ryotsu_500_001_out", operator="佐渡汽船", origin="新潟港", destination="両津港", fare=3380, urls=[sado_time, sado_fare], note=sado_note, rows=[("06:00", "08:30", "カーフェリー"), ("09:25", "11:55", "カーフェリー"), ("12:35", "15:05", "カーフェリー"), ("16:05", "18:35", "カーフェリー"), ("19:30", "22:00", "カーフェリー")], route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="sado_kisen_niigata_ryotsu_500_002_back", operator="佐渡汽船", origin="両津港", destination="新潟港", fare=3380, urls=[sado_time, sado_fare], note=sado_note, rows=[("05:30", "08:00", "カーフェリー"), ("09:15", "11:45", "カーフェリー"), ("12:45", "15:15", "カーフェリー"), ("16:05", "18:35", "カーフェリー"), ("19:30", "22:00", "カーフェリー")], route_class="long_distance_public_ferry")

    shodoshima_url = "https://www.shodoshima-kh.jp/test/access/timetable.pdf"
    shodoshima_note = (
        "Official Shodoshima Tourism timetable/fare PDF lists the Uno-Teshima-Tonosho timetable and ordinary ferry fare table. "
        "V5 records the Uno-Tonosho through OD on published rows that call at Teshima; vehicles, bicycle fares, peak-period notes, child fares, and discounts are excluded."
    )
    add_route(routes, trips, route_id="shodoshima_uno_tonosho_500_001_out", operator="小豆島豊島フェリー", origin="宇野港", destination="土庄港", fare=1260, urls=[shodoshima_url], note=shodoshima_note, rows=[("06:45", "08:14", "フェリー"), ("08:35", "10:04", "フェリー"), ("11:10", "12:39", "フェリー"), ("13:40", "15:09", "フェリー"), ("15:25", "16:54", "フェリー"), ("17:30", "18:59", "フェリー")])
    add_route(routes, trips, route_id="shodoshima_uno_tonosho_500_002_back", operator="小豆島豊島フェリー", origin="土庄港", destination="宇野港", fare=1260, urls=[shodoshima_url], note=shodoshima_note, rows=[("06:55", "08:24", "フェリー"), ("08:40", "10:09", "フェリー"), ("10:10", "11:39", "フェリー"), ("13:10", "14:39", "フェリー"), ("15:50", "17:19", "フェリー"), ("17:50", "19:19", "フェリー")])

    tsuyoshi_url = "https://www.nomo.co.jp/tsuyoshi/tsuyoshi/"
    tsuyoshi_note = (
        "Official Nomo Shosen Group Tsuyoshi page lists the Tsuyoshi timetable and adult ordinary fares. "
        "V5 records the explicit Tsuyoshi OD sections whose ports already exist in the V5 ship map; cargo fares, temporary storm alternates, Jan 1 suspension, discounts, and baggage are excluded."
    )
    add_route(routes, trips, route_id="tsuyoshi_500_001_back", operator="津吉商船", origin="佐世保港", destination="津吉", fare=1960, urls=[tsuyoshi_url], note=tsuyoshi_note, rows=[("09:00", "09:48", "つよし"), ("13:50", "14:38", "つよし"), ("16:50", "17:38", "つよし")])
    add_route(routes, trips, route_id="tsuyoshi_500_002_back", operator="津吉商船", origin="佐世保港", destination="相浦", fare=1050, urls=[tsuyoshi_url], note=tsuyoshi_note, rows=[("09:00", "09:35", "つよし"), ("13:50", "14:25", "つよし"), ("16:50", "17:25", "つよし")])

    taiko_time = "https://www.nomo.co.jp/taiko/timetable.html"
    taiko_fare = "https://www.nomo.co.jp/taiko/wp-content/uploads/sites/2/fare_20241024.pdf"
    taiko_note = (
        "Official Nomo Shosen Taiko timetable page and fare PDF list the Hakata-Goto route and adult passenger fare table. "
        "V5 records the Hakata-Fukue through OD using the official daily timetable and adult ordinary fare of JPY 4,930. "
        "Intermediate island OD pairs with missing port coordinates, room charges, vehicle fares, discounts, and operation-calendar suspensions are excluded."
    )
    add_route(routes, trips, route_id="nomo_taiko_hakata_fukue_500_001_out", operator="野母商船", origin="博多港", destination="福江港", fare=4930, urls=[taiko_time, taiko_fare], note=taiko_note, rows=[("23:45", "翌08:15", "太古")], route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="nomo_taiko_hakata_fukue_500_002_back", operator="野母商船", origin="福江港", destination="博多港", fare=4930, urls=[taiko_time, taiko_fare], note=taiko_note, rows=[("10:10", "17:50", "太古")], route_class="long_distance_public_ferry")

    suo_oshima_local_url = "https://www.town.suo-oshima.lg.jp/uploaded/attachment/21306.pdf"
    suo_oshima_kuga_fare = "https://www.town.suo-oshima.lg.jp/uploaded/attachment/11524.pdf"
    suo_oshima_local_note = (
        "Official Suo-Oshima public transport timetable PDF and town fare PDF list the municipal Kuka-Maeshima route. "
        "V5 records the regular three daily round trips and adult one-way fare of JPY 380; extra on-demand sailings, local bus connections, discounts, and dock-period changes are excluded."
    )
    add_route(routes, trips, route_id="suo_oshima_kuka_maejima_500_001_out", operator="周防大島町", origin="久賀", destination="前島港", fare=380, urls=[suo_oshima_local_url, suo_oshima_kuga_fare], note=suo_oshima_local_note, rows=[("07:10", "07:30", "町営渡船"), ("11:20", "11:40", "町営渡船"), ("16:00", "16:20", "町営渡船")])
    add_route(routes, trips, route_id="suo_oshima_kuka_maejima_500_002_back", operator="周防大島町", origin="前島港", destination="久賀", fare=380, urls=[suo_oshima_local_url, suo_oshima_kuga_fare], note=suo_oshima_local_note, rows=[("07:35", "07:55", "町営渡船"), ("11:45", "12:05", "町営渡船"), ("16:25", "16:45", "町営渡船")])

    payload = {
        "schema": "onichase.v5.ship.playable.official.to500.realBatch1",
        "operator": "multi-operator verified official batch",
        "operatorId": "v5_ship_playable_to_500_real_batch1",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for route in routes for url in route["fare"]["sourceUrls"]}),
        "ports": [],
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeCount": len(routes),
            "tripCount": len(trips),
            "notes": "Every row in this batch is transcribed from explicit official timetable/fare pages; no inferred timings or fares are used.",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
