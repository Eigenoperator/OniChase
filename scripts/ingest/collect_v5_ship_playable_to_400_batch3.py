#!/usr/bin/env python3
"""Third verified batch toward 400 playable V5 ship route directions."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collect_v5_ship_playable_to_400_batch1 import add_route, pair_rows


OUT = Path("data/v5_ship_playable_to_400_batch3_official.json")


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes: list[dict] = []
    trips: list[dict] = []

    kuro_url = "https://www.saryokyo.com/member/member-03.html"
    kuro_note = "Official Sasebo Passenger Ship Association page for Kuroshima Ryokyaku-sen, 2025-10-01 fare table and normal timetable. GW/Obon extra sailings, vehicles, and discounts are excluded."
    add_route(routes, trips, route_id="mlit_map_193_053_黒島旅客船_黒島_高島_相浦_000_out", operator="黒島旅客船", origin="黒島", destination="高島港", fare=760, urls=[kuro_url], note=kuro_note, rows=[("06:40", "07:05", "フェリーくろしま"), ("11:10", "11:35", "フェリーくろしま"), ("15:30", "15:55", "フェリーくろしま")])
    add_route(routes, trips, route_id="mlit_map_193_053_黒島旅客船_黒島_高島_相浦_000_back", operator="黒島旅客船", origin="高島港", destination="黒島", fare=760, urls=[kuro_url], note=kuro_note, rows=[("10:25", "10:50", "フェリーくろしま"), ("13:25", "13:50", "フェリーくろしま"), ("17:25", "17:50", "フェリーくろしま")])
    add_route(routes, trips, route_id="mlit_map_193_053_黒島旅客船_黒島_高島_相浦_001_out", operator="黒島旅客船", origin="高島港", destination="相浦", fare=760, urls=[kuro_url], note=kuro_note, rows=[("07:10", "07:30", "フェリーくろしま"), ("11:40", "12:00", "フェリーくろしま"), ("16:00", "16:20", "フェリーくろしま")])
    add_route(routes, trips, route_id="mlit_map_193_053_黒島旅客船_黒島_高島_相浦_001_back", operator="黒島旅客船", origin="相浦", destination="高島港", fare=760, urls=[kuro_url], note=kuro_note, rows=[("10:00", "10:20", "フェリーくろしま"), ("13:00", "13:20", "フェリーくろしま"), ("17:00", "17:20", "フェリーくろしま")])

    tokyo_bay_time = "https://www.tokyowanferry.com/diagram/"
    tokyo_bay_note = "Tokyo Wan Ferry published timetable route. The V5 playable row uses the regular A-diamond public timetable shown by timetable mirrors and the adult passenger fare currently surfaced in public fare guides; vehicle fares and special New Year timetables are excluded."
    add_route(routes, trips, route_id="tokyo_bay_kurihama_kanaya_050_out", operator="東京湾フェリー", origin="久里浜港", destination="金谷港", fare=800, urls=[tokyo_bay_time], note=tokyo_bay_note, rows=[("06:20", "07:00", "東京湾フェリー"), ("08:20", "09:00", "東京湾フェリー"), ("10:20", "11:00", "東京湾フェリー"), ("12:15", "12:55", "東京湾フェリー"), ("14:15", "14:55", "東京湾フェリー"), ("16:15", "16:55", "東京湾フェリー"), ("18:15", "18:45", "東京湾フェリー")])
    add_route(routes, trips, route_id="tokyo_bay_kurihama_kanaya_051_back", operator="東京湾フェリー", origin="金谷港", destination="久里浜港", fare=800, urls=[tokyo_bay_time], note=tokyo_bay_note, rows=[("06:15", "06:55", "東京湾フェリー"), ("08:15", "08:55", "東京湾フェリー"), ("10:15", "10:55", "東京湾フェリー"), ("12:10", "12:50", "東京湾フェリー"), ("14:10", "14:50", "東京湾フェリー"), ("16:10", "16:50", "東京湾フェリー"), ("18:10", "18:40", "東京湾フェリー")])

    ise_time = "https://www.isewanferry.co.jp/publics/index/22/"
    ise_fare = "https://www.isewanferry.co.jp/relays/download/1/1122/3129/18471/?file=%2Ffiles%2Flibs%2F18471%2F%2F202506191742303976.pdf"
    ise_note = "Official Isewan Ferry timetable/fare references. V5 uses the standard A-diamond passenger timetable; B/C-diamond, vehicles, bicycles, special rooms, and discounts are excluded."
    ise_rows = pair_rows(["08:10", "09:30", "10:40", "12:00", "13:40", "15:20", "16:30", "17:40"], 55, "伊勢湾フェリー")
    add_route(routes, trips, route_id="ise_wan_ferry_toba_irago", operator="伊勢湾フェリー", origin="鳥羽港", destination="伊良湖港", fare=1800, urls=[ise_time, ise_fare], note=ise_note, rows=ise_rows)
    add_route(routes, trips, route_id="ise_wan_ferry_irago_toba", operator="伊勢湾フェリー", origin="伊良湖港", destination="鳥羽港", fare=1800, urls=[ise_time, ise_fare], note=ise_note, rows=ise_rows)

    nushima_url = "https://nushima-yoshijin.jp/go_kisen"
    nushima_note = "Nushima Kisen regular Nada-line timetable and adult one-way fare. Special/extra services, baggage, and parking information are excluded."
    add_route(routes, trips, route_id="nushima_habu_028_out", operator="沼島汽船", origin="沼島港", destination="土生港", fare=480, urls=[nushima_url], note=nushima_note, rows=[("06:20", "06:30", "沼島汽船"), ("07:25", "07:35", "沼島汽船"), ("08:30", "08:40", "沼島汽船"), ("09:50", "10:00", "沼島汽船"), ("11:20", "11:30", "沼島汽船"), ("13:20", "13:30", "沼島汽船"), ("14:40", "14:50", "沼島汽船"), ("15:50", "16:00", "沼島汽船"), ("17:40", "17:50", "沼島汽船"), ("18:30", "18:40", "沼島汽船")])
    add_route(routes, trips, route_id="nushima_habu_029_back", operator="沼島汽船", origin="土生港", destination="沼島港", fare=480, urls=[nushima_url], note=nushima_note, rows=[("07:00", "07:10", "沼島汽船"), ("07:50", "08:00", "沼島汽船"), ("09:00", "09:10", "沼島汽船"), ("10:30", "10:40", "沼島汽船"), ("11:55", "12:05", "沼島汽船"), ("13:50", "14:00", "沼島汽船"), ("15:10", "15:20", "沼島汽船"), ("16:30", "16:40", "沼島汽船"), ("18:05", "18:15", "沼島汽船"), ("19:00", "19:10", "沼島汽船")])

    tsukumi_url = "https://www.city.tsukumi.oita.jp/soshiki/10/21233.html"
    tsukumi_note = "Official Tsukumi city Hotoshima route page and fare PDF. V5 models the ordinary adult one-way fare and regular timetable; discounts, baggage, and temporary changes are excluded."
    add_route(routes, trips, route_id="mlit_map_193_082_津久見市_津久見_保戸島_000_out", operator="津久見市", origin="津久見", destination="保戸島", fare=880, urls=[tsukumi_url, "https://www.city.tsukumi.oita.jp/uploaded/attachment/13122.pdf"], note=tsukumi_note, rows=pair_rows(["07:30", "10:00", "12:00", "14:30", "17:30"], 25, "津久見市保戸島航路"))
    add_route(routes, trips, route_id="mlit_map_193_082_津久見市_津久見_保戸島_000_back", operator="津久見市", origin="保戸島", destination="津久見", fare=880, urls=[tsukumi_url, "https://www.city.tsukumi.oita.jp/uploaded/attachment/13122.pdf"], note=tsukumi_note, rows=pair_rows(["07:00", "08:30", "11:00", "13:30", "16:30"], 25, "津久見市保戸島航路"))

    heigun_url = "https://www.city-yanai.jp/soshiki/15/heigunferry.html"
    heigun_note = "Official Yanai city Heigun route normal timetable and 2019-10-01 adult passenger fare. V5 groups Heigun East/West under the existing Heigun port node; extra services, vehicles, baggage, and discounts are excluded."
    add_route(routes, trips, route_id="heigun_yanai_075_back", operator="平郡航路", origin="平郡港", destination="柳井港", fare=1570, urls=[heigun_url], note=heigun_note, rows=[("06:00", "07:40", "平郡航路"), ("14:00", "15:40", "平郡航路")])
    add_route(routes, trips, route_id="heigun_yanai_074_out", operator="平郡航路", origin="柳井港", destination="平郡港", fare=1570, urls=[heigun_url], note=heigun_note, rows=[("08:30", "10:10", "平郡航路"), ("16:30", "18:10", "平郡航路")])

    ogasawara_url = "https://www.ogasawarakaiun.co.jp/service/index.html"
    ogasawara_note = "Official Ogasawara Kaiun 2026 timetable and April 2026 adult 2nd-class Japanese-room fare including fuel adjustment. Month-specific fare variation, replacement-ship sailings, cabins, cargo, and discounts are excluded."
    add_route(routes, trips, route_id="ogasawara_tokyo_chichijima_050_out", operator="小笠原海運", origin="竹芝", destination="父島二見港", fare=27190, urls=[ogasawara_url], note=ogasawara_note, rows=[("11:00", "翌11:00", "おがさわら丸")], route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="ogasawara_tokyo_chichijima_051_back", operator="小笠原海運", origin="父島二見港", destination="竹芝", fare=27190, urls=[ogasawara_url], note=ogasawara_note, rows=[("15:00", "翌15:00", "おがさわら丸")], route_class="long_distance_public_ferry")

    meimon_url = "https://www.cityline.co.jp/route"
    meimon_fare = "https://www.cityline.co.jp/fare"
    meimon_note = "Official Meimon Taiyo Ferry route timetable and fare page. V5 models the regular 1st and 2nd overnight departures with a conservative economy passenger fare placeholder from the official fare table family; cabin upgrades, vehicles, discounts, and New Year variants are excluded."
    add_route(routes, trips, route_id="meimon_osaka_shinmoji_028_out", operator="名門大洋フェリー", origin="大阪南港", destination="新門司港", fare=8980, urls=[meimon_url, meimon_fare], note=meimon_note, rows=[("17:00", "翌05:30", "名門大洋フェリー1便"), ("19:50", "翌08:30", "名門大洋フェリー2便")], route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="meimon_osaka_shinmoji_029_back", operator="名門大洋フェリー", origin="新門司港", destination="大阪南港", fare=8980, urls=[meimon_url, meimon_fare], note=meimon_note, rows=[("17:00", "翌05:30", "名門大洋フェリー1便"), ("19:50", "翌08:30", "名門大洋フェリー2便")], route_class="long_distance_public_ferry")

    mol_url = "https://www.sunflower.co.jp/route/facilities/timetable/index.html"
    mol_note = "Official MOL Sunflower Oarai-Tomakomai timetable. V5 models the published evening and late-night public sailing pattern with base tourist-class fare pending season refinements; vehicles, private rooms, discounts, and campaign tickets are excluded."
    add_route(routes, trips, route_id="mol_oarai_tomakomai_004_out", operator="商船三井さんふらわあ", origin="大洗港", destination="苫小牧西港", fare=10740, urls=[mol_url], note=mol_note, rows=[("01:45", "19:45", "さんふらわあ かむい/ぴりか"), ("19:45", "翌13:30", "さんふらわあ さっぽろ/ふらの")], route_class="long_distance_public_ferry")
    add_route(routes, trips, route_id="mol_oarai_tomakomai_005_back", operator="商船三井さんふらわあ", origin="苫小牧西港", destination="大洗港", fare=10740, urls=[mol_url], note=mol_note, rows=[("01:30", "19:30", "さんふらわあ かむい/ぴりか"), ("18:45", "翌14:00", "さんふらわあ さっぽろ/ふらの")], route_class="long_distance_public_ferry")

    payload = {
        "schema": "onichase.v5.ship.playable.official.batch3",
        "operator": "multi-operator official batch",
        "operatorId": "v5_ship_playable_to_400_batch3",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for route in routes for url in route["fare"]["sourceUrls"]}),
        "ports": [],
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeCount": len(routes),
            "tripCount": len(trips),
            "notes": "Batch 3 focuses on high-confidence public ferry pages with explicit timetable/fare signals.",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
