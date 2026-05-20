#!/usr/bin/env python3
"""Promote the first reviewed V5 ship source-only records into the ship map.

This file covers routes whose public route text can be tied to concrete ports
without inventing intermediate stops. Timetables, calendars, fares, and port
connectors remain pending, so these routes are map-visible but not boardable.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_expansion_150_map_batch1_official.json")

PORTS = {
    "塩竈港": [141.0225, 38.3160, "塩竈"],
    "桂島港": [141.1244, 38.3312, "浦戸桂島"],
    "野々島港": [141.1390, 38.3330, "浦戸野々島"],
    "石浜港": [141.1498, 38.3384, "浦戸石浜"],
    "寒風沢港": [141.1578, 38.3275, "浦戸寒風沢"],
    "朴島港": [141.1725, 38.3286, "浦戸朴島"],
    "酒田港": [139.8150, 38.9300, "酒田"],
    "飛島勝浦港": [139.5500, 39.1850, "飛島"],
    "石巻中央発着所": [141.3130, 38.4300, "石巻"],
    "田代島仁斗田港": [141.4200, 38.3000, "田代島"],
    "網地港": [141.4720, 38.2570, "網地島"],
    "鮎川港": [141.5060, 38.3010, "石巻"],
    "女川港": [141.4480, 38.4450, "女川"],
    "江島港": [141.5920, 38.3990, "江島"],
    "鳥羽港": [136.844942, 34.490033, "鳥羽"],
    "神島港": [136.9840, 34.5460, "鳥羽"],
    "一色港": [137.0090, 34.8020, "西尾"],
    "佐久島西港": [137.0490, 34.7290, "佐久島"],
    "佐久島東港": [137.0640, 34.7240, "佐久島"],
    "明石港": [134.9930, 34.6440, "明石"],
    "岩屋港": [135.0190, 34.5900, "淡路"],
    "沼島港": [134.8200, 34.1710, "沼島"],
    "土生港": [134.7320, 34.2320, "南あわじ"],
    "姫路港": [134.6740, 34.7700, "姫路"],
    "家島真浦港": [134.5330, 34.6740, "家島"],
    "家島宮港": [134.5510, 34.6810, "家島"],
    "坊勢港": [134.5160, 34.6510, "坊勢島"],
    "網手港": [134.5230, 34.6630, "坊勢島"],
    "広島港宇品": [132.4550554, 34.3524545, "広島"],
    "切串港": [132.4650, 34.2860, "江田島"],
    "似島港": [132.4300, 34.3090, "似島"],
    "竹原港": [132.9200, 34.3370, "竹原"],
    "白水港": [132.8920, 34.2480, "大崎上島"],
    "柳井港": [132.1180, 33.9630, "柳井"],
    "三津浜港": [132.7070, 33.8610, "松山"],
    "阿多田港": [132.2740, 34.1480, "阿多田島"],
    "小方港": [132.2200, 34.2180, "大竹"],
    "土生港因島": [133.1730, 34.2820, "因島"],
    "三原港": [133.0830, 34.3970, "三原"],
    "安芸津港": [132.8200, 34.3190, "東広島"],
    "大西港": [132.9060, 34.2400, "大崎上島"],
    "忠海港": [132.9910, 34.3370, "竹原"],
    "盛港": [133.0070, 34.2500, "大三島"],
    "走島港": [133.4030, 34.3480, "走島"],
    "鞆港": [133.3820, 34.3840, "福山"],
    "家老渡港": [133.0970, 34.2330, "因島"],
    "上弓削港": [133.2050, 34.2580, "弓削島"],
    "牛窓港": [134.1640, 34.6140, "瀬戸内"],
    "前島港": [134.1470, 34.6050, "前島"],
    "日生港": [134.2750, 34.7330, "備前"],
    "大多府港": [134.2950, 34.6620, "大多府島"],
    "岩国港": [132.2350, 34.1650, "岩国"],
    "柱島港": [132.4050, 34.0660, "柱島"],
    "萩港": [131.4040, 34.4250, "萩"],
    "見島本村港": [131.1430, 34.7650, "見島"],
    "徳山港": [131.8060, 34.0520, "周南"],
    "大津島馬島港": [131.7500, 33.9940, "大津島"],
    "祝島港": [132.0280, 33.7820, "祝島"],
    "上関港": [132.1130, 33.8310, "上関"],
    "平郡港": [132.2410, 33.7750, "平郡島"],
}


GROUPS = [
    ("shiogama_urato", "塩竈市", "塩竈・浦戸諸島", [("塩竈港", "桂島港"), ("桂島港", "野々島港"), ("野々島港", "石浜港"), ("石浜港", "寒風沢港"), ("寒風沢港", "朴島港")], ["https://urato-island.jp/"]),
    ("sakata_tobishima", "酒田市", "酒田・飛島", [("酒田港", "飛島勝浦港")], ["https://sakata-kankou.com/tobishima/"]),
    ("ajishima_line", "網地島ライン", "石巻・田代島・網地島・鮎川", [("石巻中央発着所", "田代島仁斗田港"), ("田代島仁斗田港", "網地港"), ("網地港", "鮎川港")], ["http://ajishimaline.com/index.html"]),
    ("seapal_onagawa_enoshima", "シーパル女川汽船", "女川・江島", [("女川港", "江島港")], ["http://seapal-kisen.co.jp/"]),
    ("toba_kamishima", "鳥羽市", "鳥羽・神島", [("鳥羽港", "神島港")], ["https://www.city.toba.mie.jp/soshiki/t_kanri/gyomu/doro_kotsu/kokyo_kotsu/1913.html"]),
    ("nishio_sakushima", "西尾市", "一色・佐久島", [("一色港", "佐久島西港"), ("佐久島西港", "佐久島東港")], ["https://sakushima.com/"]),
    ("awaji_jenova_akashi_iwaya", "淡路ジェノバライン", "明石・岩屋", [("明石港", "岩屋港")], ["http://www.jenova-line.co.jp/"]),
    ("nushima_habu", "沼島汽船", "沼島・土生", [("沼島港", "土生港")], ["https://nushima-yoshijin.jp/go_kisen"]),
    ("kousoku_ieshima", "高速いえしま", "家島・姫路", [("姫路港", "家島真浦港")], ["https://kousoku-ieshima.jp/"]),
    ("kofuku_liner", "髙福ライナー", "家島宮・姫路", [("姫路港", "家島宮港")], ["https://h-ieshima.jp/liner.html"]),
    ("bouze_hikari", "坊勢輝汽船", "坊勢・姫路", [("姫路港", "坊勢港")], ["https://bouzehikarikisen.moo.jp/"]),
    ("bouze_tosen", "坊勢渡船", "坊勢・網手", [("坊勢港", "網手港")], ["https://www.heart-y.ne.jp/tosen/"]),
    ("kamimura_kirikushi", "上村汽船", "宇品・切串", [("広島港宇品", "切串港")], ["http://kamimurakisen.com/osirase.html"]),
    ("ninoshima_kisen", "似島汽船", "宇品・似島", [("広島港宇品", "似島港")], ["https://ninoshimakisen.jp/"]),
    ("osaki_kisen_takehara_shiromizu", "大崎汽船", "竹原・白水", [("竹原港", "白水港")], ["http://www.oktravel.co.jp/"]),
    ("sanyo_shosen_takehara_shiromizu", "山陽商船", "竹原・白水", [("竹原港", "白水港")], ["http://sanyo-shosen.jp/"]),
    ("boyo_yanai_matsuyama", "防予フェリー", "柳井・松山", [("柳井港", "三津浜港")], ["https://www.boyoferry.co.jp/"]),
    ("atata_ogata", "阿多田島汽船", "阿多田・小方", [("阿多田港", "小方港")], ["https://atatajimakisen.sakura.ne.jp/"]),
    ("habu_shosen_mihara", "土生商船", "土生・三原", [("土生港因島", "三原港")], ["https://habushosen.jp/"]),
    ("akitsu_ferry", "安芸津フェリー", "安芸津・大西", [("安芸津港", "大西港")], ["http://sanyo-shosen.jp/akitsu/"]),
    ("omishima_ferry_tadanoumi_sakari", "大三島フェリー", "忠海・盛", [("忠海港", "盛港")], ["http://sanyo-shosen.jp/omishima/"]),
    ("hashirijima_tomo", "走島汽船", "走島・鞆", [("走島港", "鞆港")], ["https://www.tomotetsu.co.jp/?page_id=156"]),
    ("karouto_kamiyuge", "家老渡フェリー汽船", "家老渡・上弓削", [("家老渡港", "上弓削港")], ["https://karouto-ferry.com/"]),
    ("maejima_ushimado", "瀬戸内市緑の村公社", "牛窓・前島", [("牛窓港", "前島港")], ["https://www.maejima-island.info/index.html"]),
    ("taisei_hinase_otabu", "大生汽船", "日生・大多府", [("日生港", "大多府港")], ["https://taiseikisen.com/"]),
    ("iwakuni_hashirajima", "岩国柱島海運", "岩国・柱島", [("岩国港", "柱島港")], ["http://www4.et.tiki.ne.jp/~suisei-ihk/"]),
    ("hagi_mishima", "萩海運", "萩・見島", [("萩港", "見島本村港")], ["http://hagikaiun.co.jp/"]),
    ("otsushima_tokuyama", "大津島巡航", "徳山・大津島", [("徳山港", "大津島馬島港")], ["http://www.ccsnet.ne.jp/~jyunkou"]),
    ("kaminoseki_iwaishima", "上関航運", "柳井・上関・祝島", [("柳井港", "上関港"), ("上関港", "祝島港")], ["https://www.town.kaminoseki.lg.jp/%E9%9B%A2%E5%B3%B6%E8%88%AA%E8%B7%AF.html"]),
    ("heigun_yanai", "平郡航路", "柳井・平郡", [("柳井港", "平郡港")], ["https://www.city-yanai.jp/soshiki/15/heigunferry.html"]),
]


def port_payload() -> dict[str, dict]:
    return {
        name: {
            "lon": lon,
            "lat": lat,
            "city": city,
            "coordinateSource": "online_verified:official operator or municipality route page plus OSM/terminal map spot check",
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
        "revealPolicy": "local_short_route_no_reveal_by_default",
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
    routes: list[dict] = []
    for group_id, operator, group_name, pairs, urls in GROUPS:
        for origin, destination in pairs:
            add_pair(routes, group_id, operator, group_name, origin, destination, urls)

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "ship_expansion_150_map_batch1",
        "operatorId": "ship_expansion_150_map_batch1",
        "retrievedAt": datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "sourceUrls": sorted({url for group in GROUPS for url in group[4]}),
        "ports": port_payload(),
        "routes": routes,
        "trips": [],
        "summary": {
            "routeGroupCount": len(GROUPS),
            "directionalRouteCount": len(routes),
            "explicitTripCount": 0,
            "portCount": len(PORTS),
            "playablePromotionStatus": "official_route_and_ports_collected_timetable_calendar_fare_pending",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routeGroups={len(GROUPS)} routes={len(routes)} ports={len(PORTS)}")


if __name__ == "__main__":
    main()
