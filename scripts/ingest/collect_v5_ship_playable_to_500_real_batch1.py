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
