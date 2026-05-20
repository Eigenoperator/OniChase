#!/usr/bin/env python3
"""Collect the V5 ship expansion batch from 35 to 70 route groups.

This is still a source/port/route promotion layer, not playable boarding data.
Every route group is a current scheduled public route from the MLIT discovery
baseline or an operator official page. Timetable/calendar/fare parsing remains
separate because many of these routes have seasonal or vessel-class variants.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_expansion_to_70_official.json")

PORTS = {
    "稚内港": [141.6869, 45.4167, "稚内"],
    "鴛泊港": [141.2283156, 45.2413058, "利尻"],
    "香深港": [141.0460516, 45.2984182, "礼文"],
    "江差港": [140.1230, 41.8650, "江差"],
    "奥尻港": [139.5172910, 42.1746686, "奥尻"],
    "羽幌港": [141.6990, 44.3610, "羽幌"],
    "焼尻港": [141.4140, 44.4340, "焼尻"],
    "天売港": [141.3170, 44.4300, "天売"],
    "下田港": [138.9450, 34.6750, "下田"],
    "利島港": [139.2810088, 34.5323982, "利島"],
    "新島港": [139.2570, 34.3770, "新島"],
    "式根島野伏港": [139.2140, 34.3260, "式根島"],
    "神津島港": [139.1298479, 34.2107964, "神津島"],
    "八丈島底土港": [139.8212331, 33.1236155, "八丈"],
    "青ヶ島三宝港": [139.7630, 32.4460, "青ヶ島"],
    "父島二見港": [142.1986423, 27.0847550, "小笠原"],
    "母島沖港": [142.1596800, 26.6388300, "母島"],
    "岩船港": [139.4390, 38.2030, "村上"],
    "粟島港": [139.2540, 38.4680, "粟島浦"],
    "輪島港": [136.9000, 37.3990, "輪島"],
    "舳倉島港": [136.9180, 37.8480, "舳倉島"],
    "熱海港": [139.0761296, 35.0896639, "熱海"],
    "初島港": [139.1710, 35.0390, "初島"],
    "和具港": [136.8420, 34.2580, "志摩"],
    "賢島港": [136.8180, 34.3090, "志摩"],
    "佐賀関港": [131.8790, 33.2490, "大分"],
    "三崎港": [132.1200, 33.3860, "伊方"],
    "清水港": [138.4960, 35.0120, "静岡"],
    "土肥港": [138.7862481, 34.9060292, "伊豆"],
    "柳井港": [132.1180, 33.9630, "柳井"],
    "伊保田港": [132.4391337, 33.9442177, "周防大島"],
    "三津浜港": [132.7070, 33.8610, "松山"],
    "徳山港": [131.8060, 34.0520, "周南"],
    "竹田津港": [131.5370, 33.6270, "国東"],
    "熊本港": [130.5895594, 32.7636661, "熊本"],
    "島原港": [130.3700, 32.7760, "島原"],
    "蔵之元港": [130.1540, 32.0900, "長島"],
    "牛深港": [130.0260, 32.1950, "天草"],
    "宮島口": [132.3020, 34.3120, "廿日市"],
    "宮島": [132.3222470, 34.3020947, "宮島"],
    "久里浜港": [139.7170, 35.2230, "横須賀"],
    "金谷港": [139.8173913, 35.1693601, "富津"],
    "高松港": [134.0486568, 34.3540829, "高松"],
    "宇野港": [133.9530, 34.4920, "玉野"],
    "宮浦港": [133.9741355, 34.4563509, "直島"],
    "本村港": [133.9940, 34.4580, "直島"],
    "鴨池港": [130.5570, 31.5530, "鹿児島"],
    "垂水港": [130.7010, 31.4920, "垂水"],
    "八幡浜港": [132.4150, 33.4590, "八幡浜"],
    "別府港": [131.5009, 33.2932, "別府"],
    "臼杵港": [131.8103648, 33.1260457, "臼杵"],
    "口之津港": [130.1880, 32.6110, "南島原"],
    "鬼池港": [130.1930, 32.5260, "天草"],
    "鹿児島港": [130.5630, 31.5960, "鹿児島"],
    "西之表港": [130.9899535, 30.7317427, "種子島"],
    "宮之浦港": [130.5713756, 30.4326809, "屋久島"],
    "安房港": [130.6557025, 30.3164466, "屋久島"],
    "那覇泊港": [127.6826, 26.2302, "那覇"],
    "渡名喜港": [127.1382878, 26.3732954, "渡名喜"],
    "兼城港": [126.7637, 26.3417, "久米島"],
    "座間味港": [127.3013511, 26.2264520, "座間味"],
    "阿嘉港": [127.2790, 26.1990, "阿嘉"],
    "渡嘉敷港": [127.3695236, 26.1991475, "渡嘉敷"],
    "粟国港": [127.2342749, 26.5786296, "粟国"],
    "石垣港": [124.1555288, 24.3375501, "石垣"],
    "竹富港": [124.0850, 24.3310, "竹富"],
    "小浜港": [123.9984943, 24.3481468, "小浜"],
    "黒島港": [124.0033922, 24.2568787, "黒島"],
    "西表大原港": [123.8720, 24.2640, "西表"],
    "西表上原港": [123.7800, 24.4280, "西表"],
    "波照間港": [123.7740, 24.0580, "波照間"],
    "鳩間港": [123.8205414, 24.4664744, "鳩間"],
    "七類港": [133.1770, 35.5640, "松江"],
    "境港": [133.2480, 35.5480, "境港"],
    "西郷港": [133.3350634, 36.2034165, "隠岐の島"],
    "隠岐別府港": [133.0415524, 36.1076638, "西ノ島"],
    "菱浦港": [133.0990, 36.0980, "海士"],
    "来居港": [133.0380, 36.0140, "知夫"],
}


def port_payload() -> dict[str, dict]:
    return {
        name: {
            "lon": lon,
            "lat": lat,
            "city": city,
            "coordinateSource": "online_verified:MLIT discovery, official terminal pages, or OSM/Nominatim port POI",
        }
        for name, (lon, lat, city) in PORTS.items()
    }


def route(route_id: str, group_id: str, operator: str, name: str, origin: str, destination: str, urls: list[str]) -> dict:
    return {
        "routeId": route_id,
        "routeGroupId": group_id,
        "operator": operator,
        "routeName": name,
        "origin": origin,
        "destination": destination,
        "routeClass": "ship_public_transport",
        "revealPolicy": "reveal_if_long_distance_or_night",
        "playablePromotionStatus": "official_route_and_ports_collected_timetable_calendar_fare_pending",
        "sourceUrls": urls,
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": None,
            "sourceUrls": urls,
            "notes": "Fare parser pending; do not guess ship fares.",
        },
        "servicePatterns": [
            {
                "calendar": "source_pending",
                "sourceNote": "Official/current scheduled public route exists; timetable/calendar parser pending.",
            }
        ],
    }


def add_pair(routes: list[dict], group_id: str, operator: str, route_name: str, a: str, b: str, urls: list[str]) -> None:
    base = group_id.replace("-", "_")
    routes.append(route(f"{base}_{len(routes):03d}_out", group_id, operator, route_name, a, b, urls))
    routes.append(route(f"{base}_{len(routes):03d}_back", group_id, operator, route_name, b, a, urls))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes: list[dict] = []
    groups = [
        ("heartland_wakkanai_rishiri_rebun", "ハートランドフェリー", "稚内・利尻・礼文", [("稚内港", "鴛泊港"), ("鴛泊港", "香深港")], ["https://heartlandferry.jp/status/"]),
        ("heartland_esashi_okushiri", "ハートランドフェリー", "江差・奥尻", [("江差港", "奥尻港")], ["https://heartlandferry.jp/status/"]),
        ("haboro_yagishiri_teuri", "羽幌沿海フェリー", "羽幌・焼尻・天売", [("羽幌港", "焼尻港"), ("焼尻港", "天売港")], ["https://haboro-enkai.com/"]),
        ("shinshin_shimoda_izu", "神新汽船", "下田・伊豆諸島", [("下田港", "利島港"), ("利島港", "新島港"), ("新島港", "式根島野伏港"), ("式根島野伏港", "神津島港")], ["https://shinshin-kisen.jp/"]),
        ("izu_shoto_hachijo_aogashima", "伊豆諸島開発", "八丈島・青ヶ島", [("八丈島底土港", "青ヶ島三宝港")], ["https://www.tokaikisen.co.jp/schedule/"]),
        ("izu_shoto_chichijima_hahajima", "伊豆諸島開発", "父島・母島", [("父島二見港", "母島沖港")], ["https://www.tokaikisen.co.jp/schedule/"]),
        ("awashima_iwafune", "粟島汽船", "岩船・粟島", [("岩船港", "粟島港")], ["https://awashimakisen.co.jp/"]),
        ("hegura_wajima", "へぐら航路", "輪島・舳倉島", [("輪島港", "舳倉島港")], ["https://hegura.com/"]),
        ("hatsushima_atami", "富士急マリンリゾート", "熱海・初島", [("熱海港", "初島港")], ["https://www.hatsushima.jp/"]),
        ("shima_wagu_kashikojima", "志摩マリンレジャー", "和具・賢島", [("和具港", "賢島港")], ["https://shima-marineleisure.com/"]),
        ("koku94_saganoseki_misaki", "国道九四フェリー", "佐賀関・三崎", [("佐賀関港", "三崎港")], ["https://www.koku94.jp/"]),
        ("suruga_shimizu_toi", "ふじさん駿河湾フェリー", "清水・土肥", [("清水港", "土肥港")], ["https://www.223-ferry.or.jp/"]),
        ("suoshima_yanai_ihota_mitsuhama", "周防大島松山フェリー", "柳井・伊保田・松山", [("柳井港", "伊保田港"), ("伊保田港", "三津浜港")], ["https://www.suo-oshima-matsuyamaferry.com/"]),
        ("suonada_tokuyama_taketatsu", "周防灘フェリー", "徳山・竹田津", [("徳山港", "竹田津港")], ["https://www.suonada.co.jp/"]),
        ("kumamoto_ferry_kumamoto_shimabara", "熊本フェリー", "熊本・島原", [("熊本港", "島原港")], ["https://www.kumamotoferry.co.jp/"]),
        ("kyusho_ferry_kumamoto_shimabara", "九商フェリー", "熊本・島原", [("熊本港", "島原港")], ["https://www.kyusho-ferry.co.jp/"]),
        ("sanwa_kuranomoto_ushibuka", "三和商船", "蔵之元・牛深", [("蔵之元港", "牛深港")], ["https://ezax.co.jp/"]),
        ("jr_miyajima", "JR西日本宮島フェリー", "宮島口・宮島", [("宮島口", "宮島")], ["https://jr-miyajimaferry.co.jp/"]),
        ("miyajima_matsudai", "宮島松大汽船", "宮島口・宮島", [("宮島口", "宮島")], ["https://miyajima-matsudai.co.jp/"]),
        ("tokyo_bay_kurihama_kanaya", "東京湾フェリー", "久里浜・金谷", [("久里浜港", "金谷港")], ["https://www.tokyowanferry.com/diagram/"]),
        ("shikoku_kisen_naoshima", "四国汽船", "高松・宇野・直島", [("高松港", "宮浦港"), ("宮浦港", "宇野港"), ("本村港", "宇野港")], ["https://www.shikokukisen.com/"]),
        ("tarumi_kamoike_tarumi", "鹿児島交通", "鴨池・垂水", [("鴨池港", "垂水港")], ["https://www.iwasaki-corp.com/kagoshima_kotsu/tarumizuferry/"]),
        ("uwajima_unyu_yawatahama_beppu", "宇和島運輸", "八幡浜・別府", [("八幡浜港", "別府港")], ["https://www.uwajimaunyu.co.jp/"]),
        ("uwajima_unyu_yawatahama_usuki", "宇和島運輸", "八幡浜・臼杵", [("八幡浜港", "臼杵港")], ["https://www.uwajimaunyu.co.jp/"]),
        ("kyushi_orange_yawatahama_usuki", "九四オレンジフェリー", "八幡浜・臼杵", [("八幡浜港", "臼杵港")], ["https://www.orange-ferry.co.jp/"]),
        ("shimatetsu_kuchinotsu_oniike", "島原鉄道", "口之津・鬼池", [("口之津港", "鬼池港")], ["https://www.shimatetsu.co.jp/"]),
        ("cosmo_kagoshima_tanegashima_yakushima", "コスモライン", "鹿児島・種子島・屋久島", [("鹿児島港", "西之表港"), ("西之表港", "宮之浦港")], ["https://cosmoline.jp/"]),
        ("orita_kagoshima_yakushima", "折田汽船", "鹿児島・屋久島", [("鹿児島港", "宮之浦港")], ["https://ferryyakusima2.com/"]),
        ("kume_naha_tonaki_kume", "久米商船", "那覇・渡名喜・久米島", [("那覇泊港", "渡名喜港"), ("渡名喜港", "兼城港")], ["http://www.kumeline.com/"]),
        ("zamami_naha_zamami_aka", "座間味村", "那覇・座間味・阿嘉", [("那覇泊港", "座間味港"), ("座間味港", "阿嘉港")], ["https://www.vill.zamami.okinawa.jp/"]),
        ("tokashiki_naha_tokashiki", "渡嘉敷村", "那覇・渡嘉敷", [("那覇泊港", "渡嘉敷港")], ["https://www.vill.tokashiki.okinawa.jp/"]),
        ("aguni_naha_aguni", "粟国村", "那覇・粟国", [("那覇泊港", "粟国港")], ["https://www.vill.aguni.okinawa.jp/"]),
        ("anei_ishigaki_yaeyama", "安栄観光", "石垣・八重山諸島", [("石垣港", "竹富港"), ("石垣港", "小浜港"), ("石垣港", "黒島港"), ("石垣港", "西表大原港"), ("石垣港", "西表上原港"), ("石垣港", "波照間港"), ("石垣港", "鳩間港")], ["https://aneikankou.co.jp/"]),
        ("yaeyama_kanko_ishigaki_yaeyama", "八重山観光フェリー", "石垣・八重山諸島", [("石垣港", "竹富港"), ("石垣港", "小浜港"), ("石垣港", "黒島港"), ("石垣港", "西表大原港"), ("石垣港", "西表上原港"), ("石垣港", "波照間港"), ("石垣港", "鳩間港")], ["https://yaeyama.co.jp/"]),
        ("oki_kisen_shimane_oki", "隠岐汽船", "本土・隠岐諸島", [("七類港", "西郷港"), ("境港", "西郷港"), ("七類港", "隠岐別府港"), ("隠岐別府港", "菱浦港"), ("菱浦港", "来居港")], ["https://www.oki-kisen.co.jp/situation/"]),
    ]

    for group_id, operator, group_name, pairs, urls in groups:
        for origin, destination in pairs:
            add_pair(routes, group_id, operator, group_name, origin, destination, urls)

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "ship_expansion_to_70_batch",
        "operatorId": "ship_expansion_to_70",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for group in groups for url in group[4]}),
        "ports": port_payload(),
        "routes": routes,
        "trips": [],
        "summary": {
            "routeGroupCount": len(groups),
            "directionalRouteCount": len(routes),
            "explicitTripCount": 0,
            "portCount": len(PORTS),
            "playablePromotionStatus": "official_route_and_ports_collected_timetable_calendar_fare_pending",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routeGroups={len(groups)} routes={len(routes)} ports={len(PORTS)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
