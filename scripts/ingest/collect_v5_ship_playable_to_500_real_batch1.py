#!/usr/bin/env python3
"""Verified real-data V5 ship promotions after the 400-route gate."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collect_v5_ship_playable_to_400_batch1 import add_route


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
