#!/usr/bin/env python3
"""Build the V5 ship/ferry official source inventory.

This is a source inventory, not a playable ferry bundle. Playable promotion
requires timetable, calendar, fare, coordinates, and connectors.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_source_inventory.json")


SOURCES = [
    {
        "id": "taiheiyo_ferry_nagoya_sendai_tomakomai",
        "priority": 1,
        "operator": "太平洋フェリー",
        "routeGroup": "名古屋・仙台・苫小牧",
        "ports": ["名古屋港", "仙台港", "苫小牧西港"],
        "officialUrls": [
            "https://www.taiheiyo-ferry.co.jp/koro/index.html",
            "https://www.taiheiyo-ferry.co.jp/",
        ],
        "notes": "Multi-leg long-distance route; collect all directional sections and long/night reveal.",
    },
    {
        "id": "mol_sunflower_oarai_tomakomai",
        "priority": 1,
        "operator": "商船三井さんふらわあ",
        "routeGroup": "大洗・苫小牧",
        "ports": ["大洗港", "苫小牧西港"],
        "officialUrls": ["https://www.sunflower.co.jp/route/line/"],
        "notes": "Hokkaido trunk; current MOL Sunflower site separates Hokkaido and Kansai-Kyushu products.",
    },
    {
        "id": "mol_sunflower_kansai_kyushu",
        "priority": 1,
        "operator": "商船三井さんふらわあ",
        "routeGroup": "大阪/神戸・別府/大分/志布志",
        "ports": ["大阪南港", "神戸港", "別府港", "大分港", "志布志港"],
        "officialUrls": ["https://www.ferry-sunflower.co.jp/"],
        "notes": "Collect route-level pages separately for Osaka-Beppu, Kobe-Oita, Osaka-Shibushi.",
    },
    {
        "id": "shin_nihonkai_ferry",
        "priority": 1,
        "operator": "新日本海フェリー",
        "routeGroup": "日本海側・北海道",
        "ports": ["舞鶴港", "敦賀港", "新潟港", "秋田港", "小樽港", "苫小牧東港"],
        "officialUrls": ["https://www.snf.jp/"],
        "notes": "Collect each published route and calendar; route set changes by season.",
    },
    {
        "id": "hankyu_ferry",
        "priority": 1,
        "operator": "阪九フェリー",
        "routeGroup": "泉大津/神戸・新門司",
        "ports": ["泉大津港", "神戸港", "新門司港"],
        "officialUrls": ["https://www.han9f.co.jp/"],
        "notes": "Two Kansai departure ports; keep routes separate.",
    },
    {
        "id": "meimon_taiyo_ferry",
        "priority": 1,
        "operator": "名門大洋フェリー",
        "routeGroup": "大阪南港・新門司",
        "ports": ["大阪南港", "新門司港"],
        "officialUrls": ["https://www.cityline.co.jp/"],
        "notes": "Multiple night sailings; official reservation/fare simulator may require parser fallback.",
    },
    {
        "id": "tokyo_kyushu_ferry",
        "priority": 1,
        "operator": "東京九州フェリー",
        "routeGroup": "横須賀・新門司",
        "ports": ["横須賀港", "新門司港"],
        "officialUrls": ["https://tqf.co.jp/", "https://t9f-kanri.kir.jp/en/fare/"],
        "notes": "Long-distance trunk; fares have period bands.",
    },
    {
        "id": "ocean_tokyu_ferry",
        "priority": 1,
        "operator": "オーシャン東九フェリー",
        "routeGroup": "東京・徳島・新門司",
        "ports": ["東京港", "徳島港", "新門司港"],
        "officialUrls": ["https://www.otf.jp/"],
        "notes": "Multi-leg route; collect Tokyo-Tokushima-Shinmoji through pattern.",
    },
    {
        "id": "miyazaki_car_ferry",
        "priority": 1,
        "operator": "宮崎カーフェリー",
        "routeGroup": "神戸・宮崎",
        "ports": ["神戸港", "宮崎港"],
        "officialUrls": ["https://www.miyazakicarferry.com/"],
        "notes": "Kansai-Miyazaki overnight route.",
    },
    {
        "id": "silver_ferry",
        "priority": 1,
        "operator": "シルバーフェリー",
        "routeGroup": "八戸・苫小牧",
        "ports": ["八戸港", "苫小牧西港"],
        "officialUrls": ["https://www.silverferry.jp/route_guide/?stt_lang=ja"],
        "notes": "Hokkaido trunk, about eight hours.",
    },
    {
        "id": "tsugaru_kaikyo_ferry",
        "priority": 1,
        "operator": "津軽海峡フェリー",
        "routeGroup": "青森/大間/室蘭・函館",
        "ports": ["青森港", "大間港", "室蘭港", "函館港"],
        "officialUrls": ["https://www.tsugarukaikyo.co.jp/service/"],
        "notes": "Collect active routes only; Muroran status may be seasonal/current.",
    },
    {
        "id": "seikan_ferry",
        "priority": 1,
        "operator": "青函フェリー",
        "routeGroup": "青森・函館",
        "ports": ["青森港", "函館港"],
        "officialUrls": ["https://www.seikan-ferry.co.jp/schedule/"],
        "notes": "Parallel operator to Tsugaru Kaikyo; no duplicate suppression across operators.",
    },
    {
        "id": "sadokisen",
        "priority": 2,
        "operator": "佐渡汽船",
        "routeGroup": "新潟/直江津・佐渡",
        "ports": ["新潟港", "両津港", "直江津港", "小木港"],
        "officialUrls": ["https://www.sadokisen.co.jp/reservation/timetables/"],
        "notes": "Ferry and jetfoil/high-speed services need separate service classes.",
    },
    {
        "id": "tokaikisen",
        "priority": 2,
        "operator": "東海汽船",
        "routeGroup": "東京/横浜・伊豆諸島",
        "ports": ["竹芝", "横浜", "大島", "利島", "新島", "式根島", "神津島", "三宅島", "御蔵島", "八丈島"],
        "officialUrls": ["https://www.tokaikisen.co.jp/boarding/"],
        "notes": "Collect large passenger ship and high-speed jet service separately.",
    },
    {
        "id": "nankai_ferry",
        "priority": 3,
        "operator": "南海フェリー",
        "routeGroup": "和歌山・徳島",
        "ports": ["和歌山港", "徳島港"],
        "officialUrls": ["https://nankai-ferry.co.jp/timetable", "https://nankai-ferry.co.jp/price"],
        "notes": "Important rail-connected Kansai-Shikoku crossing.",
    },
    {
        "id": "jumbo_ferry",
        "priority": 3,
        "operator": "ジャンボフェリー",
        "routeGroup": "神戸・小豆島・高松",
        "ports": ["神戸港", "坂手港", "高松東港"],
        "officialUrls": ["https://ferry.co.jp/"],
        "notes": "Collect through and segment availability.",
    },
    {
        "id": "shikoku_ferry_shodoshima",
        "priority": 3,
        "operator": "小豆島フェリー/四国フェリー",
        "routeGroup": "高松/岡山/姫路・小豆島",
        "ports": ["高松港", "土庄港", "新岡山港", "姫路港", "福田港"],
        "officialUrls": ["https://www.shikokuferry.com/"],
        "notes": "Route pages must be parsed individually.",
    },
    {
        "id": "koku94_ferry",
        "priority": 3,
        "operator": "国道九四フェリー",
        "routeGroup": "佐賀関・三崎",
        "ports": ["佐賀関港", "三崎港"],
        "officialUrls": ["https://www.koku94.jp/"],
        "notes": "Kyushu-Shikoku shortcut; high gameplay value.",
    },
    {
        "id": "setonaikai_kisen_ishizaki",
        "priority": 3,
        "operator": "瀬戸内海汽船/石崎汽船",
        "routeGroup": "広島/呉・松山",
        "ports": ["広島港", "呉港", "松山観光港"],
        "officialUrls": ["https://setonaikaikisen.co.jp/", "https://www.ishizakikisen.co.jp/"],
        "notes": "Ferry and Super Jet need separate service classes.",
    },
    {
        "id": "kumamoto_shimabara",
        "priority": 3,
        "operator": "熊本フェリー/九商フェリー",
        "routeGroup": "熊本・島原",
        "ports": ["熊本港", "島原港"],
        "officialUrls": ["https://www.kumamotoferry.co.jp/", "https://www.kyusho-ferry.co.jp/"],
        "notes": "Parallel operators on the same corridor; keep operator identity.",
    },
    {
        "id": "miyajima_ferries",
        "priority": 3,
        "operator": "JR西日本宮島フェリー/宮島松大汽船",
        "routeGroup": "宮島口・宮島",
        "ports": ["宮島口", "宮島"],
        "officialUrls": ["https://jr-miyajimaferry.co.jp/", "https://miyajima-matsudai.co.jp/"],
        "notes": "Short railway-adjacent route; no long ferry reveal.",
    },
    {
        "id": "tokyo_bay_ferry",
        "priority": 3,
        "operator": "東京湾フェリー",
        "routeGroup": "久里浜・金谷",
        "ports": ["久里浜港", "金谷港"],
        "officialUrls": ["https://www.tokyowanferry.com/"],
        "notes": "Tokyo Bay shortcut; useful when bus connectors exist.",
    },
]


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    payload = {
        "schema": "onichase.v5.ship.sourceInventory.v1",
        "retrievedAt": retrieved_at,
        "playablePromotionRule": "A route is not playable until official timetable, calendar, adult fare, coordinates, and connectors are attached.",
        "routeGroupCount": len(SOURCES),
        "items": SOURCES,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routeGroupCount={len(SOURCES)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
