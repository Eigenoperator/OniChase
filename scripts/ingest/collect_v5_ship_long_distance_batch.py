#!/usr/bin/env python3
"""Collect the V5 ship long-distance and island-trunk route-source batch.

This batch intentionally captures official route/port/source status first.
Most long-distance ferry operators use seasonal fare calendars and reservation
flows, so detailed timetable/fare parsers are separate follow-up work.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_long_distance_batch_official.json")

PORTS = {
    "名古屋港": [136.8429, 35.0904, "名古屋"],
    "仙台港": [141.0231, 38.2711, "仙台"],
    "苫小牧西港": [141.6352, 42.6340, "苫小牧"],
    "大洗港": [140.5742, 36.3107, "大洗"],
    "大阪南港": [135.4322, 34.6172, "大阪"],
    "別府港": [131.5009, 33.2932, "別府"],
    "神戸港": [135.2139, 34.6817, "神戸"],
    "大分港": [131.6536, 33.2520, "大分"],
    "志布志港": [131.1020, 31.4743, "志布志"],
    "舞鶴港": [135.3855, 35.4840, "舞鶴"],
    "小樽港": [141.0045, 43.1975, "小樽"],
    "敦賀港": [136.0737, 35.6644, "敦賀"],
    "苫小牧東港": [141.8072, 42.6150, "厚真"],
    "新潟港": [139.0610, 37.9432, "新潟"],
    "秋田港": [140.0613, 39.7642, "秋田"],
    "泉大津港": [135.3921, 34.5108, "泉大津"],
    "新門司港": [131.0207, 33.8728, "北九州"],
    "横須賀港": [139.6675, 35.2867, "横須賀"],
    "東京港": [139.7883, 35.6179, "東京"],
    "徳島港": [134.5916, 34.0627, "徳島"],
    "宮崎港": [131.4741, 31.9189, "宮崎"],
    "八戸港": [141.5158, 40.5353, "八戸"],
    "青森港": [140.7362, 40.8393, "青森"],
    "函館港": [140.7169, 41.8065, "函館"],
    "大間港": [140.9107, 41.5268, "大間"],
    "室蘭港": [140.9631, 42.3393, "室蘭"],
    "新潟佐渡汽船ターミナル": [139.0673, 37.9448, "新潟"],
    "両津港": [138.4392, 38.0787, "佐渡"],
    "直江津港": [138.2553, 37.1708, "上越"],
    "小木港": [138.2821, 37.8169, "佐渡"],
    "竹芝": [139.7633, 35.6546, "東京"],
    "父島二見港": [142.1946, 27.0942, "小笠原"],
    "大島岡田港": [139.3948, 34.7851, "大島"],
    "八丈島底土港": [139.8133, 33.1239, "八丈"],
    "博多港": [130.3988, 33.6089, "福岡"],
    "郷ノ浦港": [129.6853, 33.7423, "壱岐"],
    "厳原港": [129.2955, 34.1995, "対馬"],
    "鹿児島新港": [130.5580, 31.5906, "鹿児島"],
    "名瀬港": [129.4938, 28.3832, "奄美"],
    "那覇泊港": [127.6826, 26.2302, "那覇"],
    "東予港": [133.1183542, 33.9298724, "西条"],
    "新居浜東港": [133.3322321, 33.9873309, "新居浜"],
    "坂手港": [134.3207403, 34.4559104, "小豆島"],
    "高松東港": [134.0745442, 34.3543047, "高松"],
    "高松港": [134.0486568, 34.3540829, "高松"],
    "土庄港": [134.1717904, 34.4892524, "小豆島"],
    "広島港": [132.4550554, 34.3524545, "広島"],
    "呉港": [132.5564154, 34.2406728, "呉"],
    "松山観光港": [132.704287, 33.888602, "松山"],
}


def port_payload() -> dict[str, dict]:
    return {
        name: {
            "lon": lon,
            "lat": lat,
            "city": city,
            "coordinateSource": f"manual_geocode:{name}",
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
        "routeClass": "long_distance_ferry",
        "revealPolicy": "reveal_boarding",
        "playablePromotionStatus": "official_route_and_ports_collected_timetable_calendar_fare_pending",
        "sourceUrls": urls,
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": None,
            "sourceUrls": urls,
            "notes": "Fare parser pending; long-distance ferry fares are seasonal/cabin-dependent and must not be guessed.",
        },
        "servicePatterns": [
            {
                "calendar": "source_pending",
                "sourceNote": "Official route exists; timetable/calendar parser pending.",
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
        ("taiheiyo_nagoya_sendai_tomakomai", "太平洋フェリー", "名古屋・仙台・苫小牧", [("名古屋港", "仙台港"), ("仙台港", "苫小牧西港")], ["https://www.taiheiyo-ferry.co.jp/koro/index.html"]),
        ("mol_oarai_tomakomai", "商船三井さんふらわあ", "大洗・苫小牧", [("大洗港", "苫小牧西港")], ["https://www.sunflower.co.jp/top/", "https://www.sunflower.co.jp/route/line/"]),
        ("mol_osaka_beppu", "商船三井さんふらわあ", "大阪・別府", [("大阪南港", "別府港")], ["https://www.ferry-sunflower.co.jp/"]),
        ("mol_kobe_oita", "商船三井さんふらわあ", "神戸・大分", [("神戸港", "大分港")], ["https://www.ferry-sunflower.co.jp/"]),
        ("mol_osaka_shibushi", "商船三井さんふらわあ", "大阪・志布志", [("大阪南港", "志布志港")], ["https://www.ferry-sunflower.co.jp/"]),
        ("snf_maizuru_otaru", "新日本海フェリー", "舞鶴・小樽", [("舞鶴港", "小樽港")], ["https://www.snf.jp/"]),
        ("snf_tsuruga_tomakomai", "新日本海フェリー", "敦賀・苫小牧東", [("敦賀港", "苫小牧東港")], ["https://www.snf.jp/"]),
        ("snf_niigata_otaru", "新日本海フェリー", "新潟・小樽", [("新潟港", "小樽港")], ["https://www.snf.jp/"]),
        ("snf_tsuruga_niigata_akita_tomakomai", "新日本海フェリー", "敦賀・新潟・秋田・苫小牧東", [("敦賀港", "新潟港"), ("新潟港", "秋田港"), ("秋田港", "苫小牧東港")], ["https://www.snf.jp/"]),
        ("hankyu_izumiotsu_shinmoji", "阪九フェリー", "泉大津・新門司", [("泉大津港", "新門司港")], ["https://www.han9f.co.jp/"]),
        ("hankyu_kobe_shinmoji", "阪九フェリー", "神戸・新門司", [("神戸港", "新門司港")], ["https://www.han9f.co.jp/"]),
        ("meimon_osaka_shinmoji", "名門大洋フェリー", "大阪南港・新門司", [("大阪南港", "新門司港")], ["https://www.cityline.co.jp/"]),
        ("tokyo_kyushu_yokosuka_shinmoji", "東京九州フェリー", "横須賀・新門司", [("横須賀港", "新門司港")], ["https://tqf.co.jp/"]),
        ("ocean_tokyu_tokyo_tokushima_shinmoji", "オーシャン東九フェリー", "東京・徳島・新門司", [("東京港", "徳島港"), ("徳島港", "新門司港")], ["https://www.otf.jp/"]),
        ("miyazaki_kobe_miyazaki", "宮崎カーフェリー", "神戸・宮崎", [("神戸港", "宮崎港")], ["https://www.miyazakicarferry.com/"]),
        ("silver_hachinohe_tomakomai", "シルバーフェリー", "八戸・苫小牧", [("八戸港", "苫小牧西港")], ["https://www.silverferry.jp/route_guide/?stt_lang=ja"]),
        ("tsugaru_aomori_hakodate", "津軽海峡フェリー", "青森・函館", [("青森港", "函館港")], ["https://www.tsugarukaikyo.co.jp/service/"]),
        ("tsugaru_oma_hakodate", "津軽海峡フェリー", "大間・函館", [("大間港", "函館港")], ["https://www.tsugarukaikyo.co.jp/service/"]),
        ("tsugaru_aomori_muroran", "津軽海峡フェリー", "青森・室蘭", [("青森港", "室蘭港")], ["https://www.tsugarukaikyo.co.jp/service/"]),
        ("sadokisen_niigata_ryotsu", "佐渡汽船", "新潟・両津", [("新潟佐渡汽船ターミナル", "両津港")], ["https://www.sadokisen.co.jp/reservation/timetables/"]),
        ("sadokisen_naoetsu_ogi", "佐渡汽船", "直江津・小木", [("直江津港", "小木港")], ["https://www.sadokisen.co.jp/reservation/timetables/"]),
        ("ogasawara_tokyo_chichijima", "小笠原海運", "東京・父島", [("竹芝", "父島二見港")], ["https://www.ogasawarakaiun.co.jp/"]),
        ("tokai_tokyo_izu_islands", "東海汽船", "東京・伊豆諸島", [("竹芝", "大島岡田港"), ("竹芝", "八丈島底土港")], ["https://www.tokaikisen.co.jp/boarding/"]),
        ("orange_toyo_osaka", "四国開発フェリー", "東予・大阪", [("東予港", "大阪南港")], ["https://www.orange-ferry.co.jp/"]),
        ("orange_niihama_kobe", "四国開発フェリー", "新居浜東・神戸", [("新居浜東港", "神戸港")], ["https://www.orange-ferry.co.jp/"]),
        ("jumbo_kobe_shodoshima_takamatsu", "ジャンボフェリー", "神戸・小豆島・高松", [("神戸港", "坂手港"), ("坂手港", "高松東港")], ["https://ferry.co.jp/", "https://ferry.co.jp/home/ports-all/takamatsu/"]),
        ("shodoshima_takamatsu_tonosho", "小豆島フェリー", "高松・土庄", [("高松港", "土庄港")], ["https://www.shikokuferry.com/route2"]),
        ("setonaikai_hiroshima_kure_matsuyama", "瀬戸内海汽船/石崎汽船", "広島・呉・松山", [("広島港", "呉港"), ("呉港", "松山観光港")], ["https://setonaikaikisen.co.jp/west-setouchi/item/item01/", "https://www.ishizakikisen.co.jp/contents/price.html"]),
    ]
    for group_id, operator, group_name, pairs, urls in groups:
        for origin, destination in pairs:
            add_pair(routes, group_id, operator, group_name, origin, destination, urls)

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "long_distance_and_island_trunk_batch",
        "operatorId": "long_distance_ship_batch_2",
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
