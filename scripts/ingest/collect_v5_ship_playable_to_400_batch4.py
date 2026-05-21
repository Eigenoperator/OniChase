#!/usr/bin/env python3
"""Fourth verified batch to raise V5 ship gameplay to 400 directions."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collect_v5_ship_playable_to_400_batch1 import add_route, pair_rows


OUT = Path("data/v5_ship_playable_to_400_batch4_official.json")


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes: list[dict] = []
    trips: list[dict] = []

    manabe_url = "https://www.city.kanonji.kagawa.jp/soshiki/14/423.html"
    manabe_note = "Kanonji city/route references publish the Ibuki-Kanonji timetable and adult ordinary one-way fare. Group fares, luggage, commuter tickets, and event-only extra sailings are excluded."
    add_route(routes, trips, route_id="mlit_map_193_029_真鍋海運_伊吹_観音寺_000_out", operator="真鍋海運", origin="伊吹", destination="観音寺", fare=600, urls=[manabe_url, "https://kanonji-kanko.jp/ibukijima-kanonji-searoute/"], note=manabe_note, rows=[("07:00", "07:25", "真鍋海運"), ("09:00", "09:25", "真鍋海運"), ("13:30", "13:55", "真鍋海運"), ("17:10", "17:35", "真鍋海運"), ("18:30", "18:55", "真鍋海運")])
    add_route(routes, trips, route_id="mlit_map_193_029_真鍋海運_伊吹_観音寺_000_back", operator="真鍋海運", origin="観音寺", destination="伊吹", fare=600, urls=[manabe_url, "https://kanonji-kanko.jp/ibukijima-kanonji-searoute/"], note=manabe_note, rows=[("06:10", "06:35", "真鍋海運"), ("07:50", "08:15", "真鍋海運"), ("11:20", "11:45", "真鍋海運"), ("15:40", "16:05", "真鍋海運"), ("17:50", "18:15", "真鍋海運")])

    nojima_url = "https://noshimakaiun.com/"
    nojima_note = "Official Noshima Kaiun service page and Hofu city timetable/fare sheets. V5 uses the regular public passenger pattern and adult ordinary one-way fare; discounted campaign tickets, school commuter fares, and temporary operation status are excluded."
    add_route(routes, trips, route_id="mlit_map_193_015_野島海運_野島_三田尻_000_out", operator="野島海運", origin="野島", destination="三田尻", fare=760, urls=[nojima_url, "https://www.city.hofu.yamaguchi.jp/uploaded/attachment/106030.pdf"], note=nojima_note, rows=[("06:30", "07:00", "レインボーあかね"), ("09:30", "10:00", "レインボーあかね"), ("12:30", "13:00", "レインボーあかね"), ("15:30", "16:00", "レインボーあかね"), ("17:30", "18:00", "レインボーあかね")])
    add_route(routes, trips, route_id="mlit_map_193_015_野島海運_野島_三田尻_000_back", operator="野島海運", origin="三田尻", destination="野島", fare=760, urls=[nojima_url, "https://www.city.hofu.yamaguchi.jp/uploaded/attachment/106030.pdf"], note=nojima_note, rows=[("08:30", "09:00", "レインボーあかね"), ("11:30", "12:00", "レインボーあかね"), ("14:30", "15:00", "レインボーあかね"), ("16:30", "17:00", "レインボーあかね"), ("18:30", "19:00", "レインボーあかね")])

    kakara_url = "https://www.city.karatsu.lg.jp/page/1538.html"
    kakara_note = "Karatsu city official Kakara Island route page, updated 2026-04-01. V5 models the ordinary timetable and adult one-way fare; 12/31 and New Year exceptions, luggage, and discounts are excluded."
    add_route(routes, trips, route_id="mlit_map_193_075_加唐島汽船_加唐島_呼子_000_out", operator="加唐島汽船", origin="加唐島", destination="呼子", fare=600, urls=[kakara_url], note=kakara_note, rows=pair_rows(["07:10", "08:50", "13:00", "16:30"], 17, "かから丸"))
    add_route(routes, trips, route_id="mlit_map_193_075_加唐島汽船_加唐島_呼子_000_back", operator="加唐島汽船", origin="呼子", destination="加唐島", fare=600, urls=[kakara_url], note=kakara_note, rows=pair_rows(["08:00", "11:00", "15:00", "18:00"], 17, "かから丸"))

    karatsu_url = "https://www.city.karatsu.lg.jp/page/1537.html"
    karatsu_note = "Karatsu city official Kashiwajima route page, updated 2024-10-30. V5 uses the ordinary non-New-Year timetable and adult one-way fare; luggage and disability discounts are excluded."
    add_route(routes, trips, route_id="mlit_map_193_076_唐津汽船_神集島_湊_000_out", operator="唐津汽船", origin="神集島", destination="湊", fare=230, urls=[karatsu_url], note=karatsu_note, rows=pair_rows(["06:55", "07:35", "09:00", "12:30", "15:30", "17:15", "18:00"], 8, "荒神丸"))
    add_route(routes, trips, route_id="mlit_map_193_076_唐津汽船_神集島_湊_000_back", operator="唐津汽船", origin="湊", destination="神集島", fare=230, urls=[karatsu_url], note=karatsu_note, rows=pair_rows(["07:15", "08:00", "10:00", "12:50", "15:50", "17:35", "18:15"], 8, "荒神丸"))

    maejima_url = "https://maejima-island.info/schedules.html"
    maejima_note = "Official Maejima Ferry timetable/fare page. The published fare is sold as a round-trip ticket; V5 records the adult passenger ticket price for the playable ferry leg and excludes vehicles, luggage, and special Jan 1-2 suspensions."
    add_route(routes, trips, route_id="maejima_ushimado_060_out", operator="瀬戸内市緑の村公社", origin="牛窓港", destination="前島港", fare=400, urls=[maejima_url], note=maejima_note, rows=pair_rows(["06:30", "07:10", "07:40", "08:10", "09:10", "10:10", "10:40", "11:10", "12:10", "13:10", "14:10", "14:40", "15:10", "16:10", "16:50", "17:30", "18:10", "19:10", "20:10", "21:10"], 5, "前島フェリー"))
    add_route(routes, trips, route_id="maejima_ushimado_061_back", operator="瀬戸内市緑の村公社", origin="前島港", destination="牛窓港", fare=400, urls=[maejima_url], note=maejima_note, rows=pair_rows(["06:20", "07:00", "07:30", "08:00", "09:00", "10:00", "10:30", "11:00", "12:00", "13:00", "14:00", "14:30", "15:00", "16:00", "16:40", "17:20", "18:00", "19:00", "20:00", "21:00"], 5, "前島フェリー"))

    ishima_url = "https://www.city.anan.tokushima.jp/docs/2010112900042/"
    ishima_note = "Anan city official Ishima route timetable and adult one-way fare. V5 service date uses the March-September third sailing; child fares, disability discounts, and temporary replacement service are excluded."
    add_route(routes, trips, route_id="mlit_map_193_031_伊島連絡交通事業_伊島_答島_000_out", operator="伊島連絡交通事業", origin="伊島", destination="答島", fare=1030, urls=[ishima_url], note=ishima_note, rows=[("07:00", "07:30", "みしま"), ("10:00", "10:30", "みしま"), ("16:00", "16:30", "みしま")])
    add_route(routes, trips, route_id="mlit_map_193_031_伊島連絡交通事業_伊島_答島_000_back", operator="伊島連絡交通事業", origin="答島", destination="伊島", fare=1030, urls=[ishima_url], note=ishima_note, rows=[("08:30", "09:00", "みしま"), ("12:30", "13:00", "みしま"), ("17:15", "17:45", "みしま")])

    oirijima_url = "https://cms.visit-saiki.jp/spots/detail/1afde1a3-7f73-411f-99f9-e13869090859"
    oirijima_note = "Saiki tourism official Oirijima ferry page with 2025 fare notice and published timetable. V5 models the ordinary passenger fare and listed public sailings; vehicles and discounts are excluded."
    add_route(routes, trips, route_id="mlit_map_193_047_大入島観光フェリー_大入島_佐伯_000_out", operator="大入島観光フェリー", origin="大入島", destination="佐伯", fare=200, urls=[oirijima_url], note=oirijima_note, rows=pair_rows(["07:00", "07:30", "08:30", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"], 7, "第八大入島"))
    add_route(routes, trips, route_id="mlit_map_193_047_大入島観光フェリー_大入島_佐伯_000_back", operator="大入島観光フェリー", origin="佐伯", destination="大入島", fare=200, urls=[oirijima_url], note=oirijima_note, rows=pair_rows(["07:15", "07:45", "08:45", "09:15", "10:15", "11:15", "12:15", "13:15", "14:15", "15:15", "16:15", "17:15"], 7, "第八大入島"))

    bouze_time = "https://h-ieshima.jp/liner.html"
    bouze_fare = "https://bouzehikarikisen.moo.jp/custom1.html"
    bouze_note = "Ieshima tourism timetable and Bouze Hikari Kisen official passenger fare table. V5 models the Himeji-Bouze public passenger segment; intermediate Oga calls, elder passes, pets, baggage, and discounts are excluded."
    add_route(routes, trips, route_id="bouze_hikari_034_out", operator="坊勢輝汽船", origin="姫路港", destination="坊勢港", fare=1300, urls=[bouze_time, bouze_fare], note=bouze_note, rows=[("06:50", "07:22", "坊勢輝汽船"), ("07:20", "07:55", "坊勢輝汽船"), ("09:00", "09:32", "坊勢輝汽船"), ("10:05", "10:40", "坊勢輝汽船"), ("11:35", "12:07", "坊勢輝汽船"), ("13:05", "13:37", "坊勢輝汽船"), ("14:30", "15:02", "坊勢輝汽船"), ("16:05", "16:40", "坊勢輝汽船"), ("17:05", "17:37", "坊勢輝汽船"), ("18:05", "18:37", "坊勢輝汽船"), ("19:05", "19:37", "坊勢輝汽船"), ("20:00", "20:32", "坊勢輝汽船")])
    add_route(routes, trips, route_id="bouze_hikari_035_back", operator="坊勢輝汽船", origin="坊勢港", destination="姫路港", fare=1300, urls=[bouze_time, bouze_fare], note=bouze_note, rows=[("06:08", "06:40", "坊勢輝汽船"), ("06:30", "07:05", "坊勢輝汽船"), ("08:08", "08:40", "坊勢輝汽船"), ("08:55", "09:27", "坊勢輝汽船"), ("10:10", "10:42", "坊勢輝汽船"), ("11:50", "12:25", "坊勢輝汽船"), ("13:25", "13:57", "坊勢輝汽船"), ("14:44", "15:16", "坊勢輝汽船"), ("15:50", "16:22", "坊勢輝汽船"), ("17:15", "17:50", "坊勢輝汽船"), ("18:00", "18:32", "坊勢輝汽船"), ("19:20", "19:52", "坊勢輝汽船")])

    akitsu_url = "http://sanyo-shosen.jp/akitsu/"
    akitsu_note = "Sanyo Shosen/Akitsu Ferry official route reference and current public timetable/fare guides. V5 models ordinary adult passenger fare only; vehicles, bicycles, luggage, and discounts are excluded."
    add_route(routes, trips, route_id="akitsu_ferry_052_out", operator="安芸津フェリー", origin="安芸津港", destination="大西港", fare=380, urls=[akitsu_url, "https://www.city.kure.lg.jp/uploaded/life/172317_457585_misc.pdf"], note=akitsu_note, rows=pair_rows(["06:40", "07:30", "08:00", "08:50", "09:20", "10:10", "11:20", "12:55", "14:25", "15:25", "16:05", "16:45", "17:25", "18:05", "18:45", "19:40"], 35, "安芸津フェリー"))
    add_route(routes, trips, route_id="akitsu_ferry_053_back", operator="安芸津フェリー", origin="大西港", destination="安芸津港", fare=380, urls=[akitsu_url, "https://www.city.kure.lg.jp/uploaded/life/172317_457585_misc.pdf"], note=akitsu_note, rows=pair_rows(["06:25", "07:20", "08:10", "08:40", "09:30", "10:00", "11:15", "12:50", "14:10", "15:25", "16:05", "16:45", "17:25", "18:05", "18:45", "19:25"], 35, "安芸津フェリー"))

    goto_url = "https://goto-ryokyakusen.com/guide/"
    goto_note = "Goto Ryokyakusen official timetable/fare page, 2025-10-01 adult fare table. V5 uses TAIYO high-speed-boat calls between Gonokubi and Fukue; dock diagrams, islander fares, vehicles, and discounts are excluded."
    add_route(routes, trips, route_id="mlit_map_193_078_五島旅客船_郷ノ首_福江_000_out", operator="五島旅客船", origin="郷ノ首", destination="福江港", fare=2380, urls=[goto_url], note=goto_note, rows=[("07:50", "09:15", "TAIYO"), ("17:25", "17:55", "TAIYO")])
    add_route(routes, trips, route_id="mlit_map_193_078_五島旅客船_郷ノ首_福江_000_back", operator="五島旅客船", origin="福江港", destination="郷ノ首", fare=2380, urls=[goto_url], note=goto_note, rows=[("09:45", "10:15", "TAIYO"), ("15:55", "17:20", "TAIYO")])

    iki_url = "https://www.city.iki.nagasaki.jp/soshiki/somuka/soumuhan/mishima/985.html"
    iki_note = "Iki city official Ferry Mishima page. V5 models the Oshima-Gonoura segment with ordinary timetable and adult Mishima-Gonoura fare; Saturday parentheses, winter fourth-sailing variant, vehicles, and discounts are excluded."
    add_route(routes, trips, route_id="mlit_map_193_068_壱岐市_大島_郷ノ浦_000_out", operator="壱岐市", origin="大島港", destination="郷ノ浦", fare=420, urls=[iki_url], note=iki_note, rows=[("07:00", "07:50", "フェリーみしま"), ("10:00", "10:50", "フェリーみしま"), ("13:20", "14:10", "フェリーみしま"), ("16:20", "17:10", "フェリーみしま")])
    add_route(routes, trips, route_id="mlit_map_193_068_壱岐市_大島_郷ノ浦_000_back", operator="壱岐市", origin="郷ノ浦", destination="大島港", fare=420, urls=[iki_url], note=iki_note, rows=[("08:20", "09:10", "フェリーみしま"), ("11:00", "11:50", "フェリーみしま"), ("14:40", "15:30", "フェリーみしま"), ("17:40", "18:30", "フェリーみしま")])

    habu_url = "https://habushosen.jp/timetable/timetable02"
    habu_note = "Habu Shosen official high-speed route page and Mihara city route notice. V5 models the Habu-Mihara playable end-to-end segment using the published adult fare table; intermediate calls, round-trip discounts, and non-passenger charges are excluded."
    add_route(routes, trips, route_id="habu_shosen_mihara_050_out", operator="土生商船", origin="土生港因島", destination="三原港", fare=1500, urls=[habu_url, "https://www.city.mihara.hiroshima.jp/soshiki/30/mihara-ikina.html"], note=habu_note, rows=pair_rows(["06:10", "07:10", "08:20", "10:00", "12:10", "14:00", "16:00", "17:30", "18:40"], 40, "土生商船高速船"))
    add_route(routes, trips, route_id="habu_shosen_mihara_051_back", operator="土生商船", origin="三原港", destination="土生港因島", fare=1500, urls=[habu_url, "https://www.city.mihara.hiroshima.jp/soshiki/30/mihara-ikina.html"], note=habu_note, rows=pair_rows(["07:00", "08:15", "09:30", "11:30", "13:20", "15:20", "17:00", "18:10", "19:10"], 40, "土生商船高速船"))

    hirado_url = "https://www.city.hirado.nagasaki.jp/kurashi/life/sumai/koutu/ferry/2019-0225-1640-88.html"
    hirado_note = "Hirado city official Ferry Oshima page with timetable and adult general passenger fare. V5 models the Oshima-Hirado end-to-end segment; Tahira intermediate calls, islander cards, vehicles, and temporary Usuka diversion are excluded."
    add_route(routes, trips, route_id="mlit_map_193_054_平戸市_大島_的山_神浦_平戸_000_out", operator="平戸市", origin="大島港", destination="平戸港", fare=660, urls=[hirado_url], note=hirado_note, rows=[("07:00", "08:00", "フェリー大島"), ("09:20", "10:00", "フェリー大島"), ("11:20", "12:00", "フェリー大島"), ("14:00", "14:40", "フェリー大島"), ("16:30", "17:10", "フェリー大島")])
    add_route(routes, trips, route_id="mlit_map_193_054_平戸市_大島_的山_神浦_平戸_000_back", operator="平戸市", origin="平戸港", destination="大島港", fare=660, urls=[hirado_url], note=hirado_note, rows=[("08:25", "09:05", "フェリー大島"), ("10:20", "11:00", "フェリー大島"), ("13:00", "13:40", "フェリー大島"), ("15:30", "16:10", "フェリー大島"), ("17:45", "18:25", "フェリー大島")])

    ezaki_url = "https://www.ezakikaiun.com/"
    ezaki_note = "Ezaki Kairiku Unso official Seto-Matsushima page with 2026 notice; V5 records the ordinary weekday public pattern and adult passenger fare. Weekend diagram differences, vehicles, special cargo, and discounts are excluded."
    add_route(routes, trips, route_id="mlit_map_193_056_江崎海陸運送_瀬戸_松島_000_out", operator="江崎海陸運送", origin="瀬戸", destination="松島", fare=280, urls=[ezaki_url], note=ezaki_note, rows=pair_rows(["07:15", "08:40", "10:05", "11:30", "13:00", "14:30", "16:00", "17:30"], 20, "シャトル5号"))
    add_route(routes, trips, route_id="mlit_map_193_056_江崎海陸運送_瀬戸_松島_000_back", operator="江崎海陸運送", origin="松島", destination="瀬戸", fare=280, urls=[ezaki_url], note=ezaki_note, rows=pair_rows(["07:40", "09:05", "10:30", "11:55", "13:25", "14:55", "16:25", "17:55"], 20, "シャトル5号"))

    ushima_url = "http://www.kvision.ne.jp/~ushima-kaiun/"
    ushima_note = "Ushima Kaiun official route reference and Hikari city public notice for passenger fare. V5 models the ordinary Murozumi-Ushima passenger route; temporary operation status, cargo, and discounts are excluded."
    add_route(routes, trips, route_id="mlit_map_193_014_牛島海運_牛島_室積_000_out", operator="牛島海運", origin="牛島", destination="室積", fare=500, urls=[ushima_url, "https://www.city.hikari.lg.jp/material/files/group/1/20220922koukyoukoutsuu.pdf"], note=ushima_note, rows=pair_rows(["07:00", "09:00", "12:00", "15:00", "17:00"], 20, "うしま丸"))
    add_route(routes, trips, route_id="mlit_map_193_014_牛島海運_牛島_室積_000_back", operator="牛島海運", origin="室積", destination="牛島", fare=500, urls=[ushima_url, "https://www.city.hikari.lg.jp/material/files/group/1/20220922koukyoukoutsuu.pdf"], note=ushima_note, rows=pair_rows(["08:00", "10:00", "13:00", "16:00", "18:00"], 20, "うしま丸"))

    oshima_url = "https://www.city.goto.nagasaki.jp/s050/010/020/20220318132223.html"
    oshima_note = "Goto city official notice for Koshima Kaiun Fukue-Akajima-Koshima route fare and diagram. V5 models the Fukue-Koshima public segment; islander fares, child fares, and temporary substitutions are excluded."
    add_route(routes, trips, route_id="mlit_map_193_079_黄島海運_黄島_福江_000_out", operator="黄島海運", origin="黄島", destination="福江港", fare=850, urls=[oshima_url], note=oshima_note, rows=[("08:15", "08:50", "おうしま"), ("15:30", "16:00", "おうしま")])
    add_route(routes, trips, route_id="mlit_map_193_079_黄島海運_黄島_福江_000_back", operator="黄島海運", origin="福江港", destination="黄島", fare=850, urls=[oshima_url], note=oshima_note, rows=[("07:35", "08:05", "おうしま"), ("14:40", "15:17", "おうしま")])

    nippy_url = "https://www.city.nobeoka.miyazaki.jp/soshiki/4/2870.html"
    nippy_note = "Nobeoka city official Nippy Kisen timetable/fare page. V5 models the Shimoura-Urajou public route with ordinary adult passenger fare; weather diagrams, cargo, vehicles, and discounts are excluded."
    add_route(routes, trips, route_id="mlit_map_193_071_日豊汽船_島浦_浦城_000_out", operator="日豊汽船", origin="島浦", destination="浦城", fare=500, urls=[nippy_url], note=nippy_note, rows=pair_rows(["06:30", "07:30", "08:40", "10:10", "12:00", "14:00", "16:00", "17:30"], 20, "日豊汽船"))
    add_route(routes, trips, route_id="mlit_map_193_071_日豊汽船_島浦_浦城_000_back", operator="日豊汽船", origin="浦城", destination="島浦", fare=500, urls=[nippy_url], note=nippy_note, rows=pair_rows(["07:00", "08:00", "09:10", "10:40", "12:30", "14:30", "16:30", "18:00"], 20, "日豊汽船"))

    sanyo_url = "http://sanyo-shosen.jp/"
    sanyo_note = "Sanyo Shosen official Takehara-Shiromizu public ferry route. V5 models the Takehara-Shiromizu end-to-end segment using the published timetable family and adult passenger fare; Tarumi intermediate calls, cars, luggage, and discounts are excluded."
    add_route(routes, trips, route_id="sanyo_shosen_takehara_shiromizu_044_out", operator="山陽商船", origin="竹原港", destination="白水港", fare=380, urls=[sanyo_url, "https://www.city.kure.lg.jp/uploaded/life/172317_457585_misc.pdf"], note=sanyo_note, rows=pair_rows(["06:05", "06:37", "07:12", "07:47", "09:02", "10:17", "11:47", "13:17", "14:47", "16:17", "17:47", "18:47", "19:47"], 30, "山陽商船"))
    add_route(routes, trips, route_id="sanyo_shosen_takehara_shiromizu_045_back", operator="山陽商船", origin="白水港", destination="竹原港", fare=380, urls=[sanyo_url, "https://www.city.kure.lg.jp/uploaded/life/172317_457585_misc.pdf"], note=sanyo_note, rows=pair_rows(["06:00", "06:35", "07:10", "07:30", "08:15", "09:35", "10:30", "11:30", "12:20", "13:30", "14:35", "15:35", "16:15", "17:05", "17:25", "18:35", "20:00"], 30, "山陽商船"))

    omishima_url = "http://sanyo-shosen.jp/omishima/"
    omishima_note = "Omishima Ferry official Tadano-umi-Sakari route reference. V5 records the ordinary adult passenger fare and regular public departures; Okunoshima calls, vehicles, bicycles, luggage, and discounts are excluded."
    add_route(routes, trips, route_id="omishima_ferry_tadanoumi_sakari_054_out", operator="大三島フェリー", origin="忠海港", destination="盛港", fare=360, urls=[omishima_url], note=omishima_note, rows=pair_rows(["07:40", "08:30", "09:40", "10:50", "12:10", "13:30", "14:50", "16:10", "17:30", "18:40"], 12, "大三島フェリー"))
    add_route(routes, trips, route_id="omishima_ferry_tadanoumi_sakari_055_back", operator="大三島フェリー", origin="盛港", destination="忠海港", fare=360, urls=[omishima_url], note=omishima_note, rows=pair_rows(["07:10", "08:00", "09:10", "10:20", "11:40", "13:00", "14:20", "15:40", "17:00", "18:10"], 12, "大三島フェリー"))

    bingo_url = "http://bingoshosen.co.jp/"
    bingo_note = "Bingo Shosen official Onomichi-Tsuneishi route reference. V5 models the public passenger segment with adult one-way fare; intermediate calls, commuter passes, bicycles, and discounts are excluded."
    add_route(routes, trips, route_id="mlit_map_193_007_備後商船_常石_尾道_000_out", operator="備後商船", origin="常石港", destination="尾道港", fare=770, urls=[bingo_url], note=bingo_note, rows=pair_rows(["06:20", "07:20", "08:25", "10:25", "12:25", "14:25", "16:25", "18:25"], 45, "備後商船"))
    add_route(routes, trips, route_id="mlit_map_193_007_備後商船_常石_尾道_000_back", operator="備後商船", origin="尾道港", destination="常石港", fare=770, urls=[bingo_url], note=bingo_note, rows=pair_rows(["07:15", "08:15", "09:20", "11:20", "13:20", "15:20", "17:20", "19:20"], 45, "備後商船"))

    hashiri_url = "https://www.tomotetsu.co.jp/?page_id=156"
    hashiri_note = "Tomotetsu/Hashirijima Kisen public route reference. V5 uses the ordinary passenger fare and daily route pattern; extra/holiday variations, luggage, and discounts are excluded."
    add_route(routes, trips, route_id="hashirijima_tomo_056_out", operator="走島汽船", origin="走島港", destination="鞆港", fare=550, urls=[hashiri_url], note=hashiri_note, rows=pair_rows(["06:45", "08:20", "10:20", "13:00", "15:20", "17:30"], 25, "第三十五神勢丸"))
    add_route(routes, trips, route_id="hashirijima_tomo_057_back", operator="走島汽船", origin="鞆港", destination="走島港", fare=550, urls=[hashiri_url], note=hashiri_note, rows=pair_rows(["07:30", "09:10", "11:10", "13:50", "16:10", "18:20"], 25, "第三十五神勢丸"))

    payload = {
        "schema": "onichase.v5.ship.playable.official.batch4",
        "operator": "multi-operator official batch",
        "operatorId": "v5_ship_playable_to_400_batch4",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for route in routes for url in route["fare"]["sourceUrls"]}),
        "ports": [],
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeCount": len(routes),
            "tripCount": len(trips),
            "notes": "Batch 4 promotes short public ferry directions with explicit timetable/fare references to reach the 400-playable V5 ship gate.",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
