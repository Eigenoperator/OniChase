#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
SECONDARY_SOURCE_PATH = DATA_DIR / "shinkansen_station_coordinates_wikipedia.json"


KANJI_BY_ID = {
    "TOKYO": "東京",
    "UENO": "上野",
    "OMIYA": "大宮",
    "KUMAGAYA": "熊谷",
    "HONJO_WASEDA": "本庄早稲田",
    "TAKASAKI": "高崎",
    "OYAMA": "小山",
    "UTSUNOMIYA": "宇都宮",
    "NASUSHIOBARA": "那須塩原",
    "SHIN_SHIRAKAWA": "新白河",
    "KORIYAMA": "郡山",
    "FUKUSHIMA": "福島",
    "SHIROISHI_ZAO": "白石蔵王",
    "SENDAI_TOHOKU": "仙台",
    "FURUKAWA": "古川",
    "KURIKOMA_KOGEN": "くりこま高原",
    "ICHINOSEKI": "一ノ関",
    "MIZUSAWA_ESASHI": "水沢江刺",
    "KITAKAMI": "北上",
    "SHIN_HANAMAKI": "新花巻",
    "MORIOKA": "盛岡",
    "IWATE_NUMAKUNAI": "いわて沼宮内",
    "NINOHE": "二戸",
    "HACHINOHE": "八戸",
    "SHICHINOHE_TOWADA": "七戸十和田",
    "SHIN_AOMORI": "新青森",
    "OKU_TSUGARU_IMABETSU": "奥津軽いまべつ",
    "KIKONAI": "木古内",
    "SHIN_HAKODATE_HOKUTO": "新函館北斗",
    "YONEZAWA": "米沢",
    "TAKAHATA": "高畠",
    "AKAYU": "赤湯",
    "KAMINOYAMA_ONSEN": "かみのやま温泉",
    "YAMAGATA": "山形",
    "TENDO": "天童",
    "SAKURANBO_HIGASHINE": "さくらんぼ東根",
    "MURAYAMA": "村山",
    "OISHIDA": "大石田",
    "SHINJO": "新庄",
    "SHIZUKUISHI": "雫石",
    "TAZAWAKO": "田沢湖",
    "KAKUNODATE": "角館",
    "OMAGARI": "大曲",
    "AKITA": "秋田",
    "JOMO_KOGEN": "上毛高原",
    "ECHIGO_YUZAWA": "越後湯沢",
    "GALA_YUZAWA": "ガーラ湯沢",
    "URASA": "浦佐",
    "NAGAOKA": "長岡",
    "TSUBAME_SANJO": "燕三条",
    "NIIGATA": "新潟",
    "ANNAKA_HARUNA": "安中榛名",
    "KARUIZAWA": "軽井沢",
    "SAKUDAIRA": "佐久平",
    "UEDA": "上田",
    "NAGANO": "長野",
    "IIYAMA": "飯山",
    "JOETSUMYOKO": "上越妙高",
    "ITOIGAWA": "糸魚川",
    "KUROBE_UNAZUKIONSEN": "黒部宇奈月温泉",
    "TOYAMA": "富山",
    "SHIN_TAKAOKA": "新高岡",
    "KANAZAWA": "金沢",
    "KOMATSU": "小松",
    "KAGAONSEN": "加賀温泉",
    "AWARAONSEN": "芦原温泉",
    "FUKUI": "福井",
    "ECHIZEN_TAKEFU": "越前たけふ",
    "TSURUGA": "敦賀",
    "SHINAGAWA": "品川",
    "SHIN_YOKOHAMA": "新横浜",
    "ODAWARA": "小田原",
    "ATAMI": "熱海",
    "MISHIMA": "三島",
    "SHIN_FUJI": "新富士",
    "SHIZUOKA": "静岡",
    "KAKEGAWA": "掛川",
    "HAMAMATSU": "浜松",
    "TOYOHASHI": "豊橋",
    "MIKAWA_ANJO": "三河安城",
    "NAGOYA": "名古屋",
    "GIFU_HASHIMA": "岐阜羽島",
    "MAIBARA": "米原",
    "KYOTO": "京都",
    "SHIN_OSAKA": "新大阪",
    "SHIN_KOBE": "新神戸",
    "NISHI_AKASHI": "西明石",
    "HIMEJI": "姫路",
    "AIOI": "相生",
    "OKAYAMA": "岡山",
    "SHIN_KURASHIKI": "新倉敷",
    "FUKUYAMA": "福山",
    "SHIN_ONOMICHI": "新尾道",
    "MIHARA": "三原",
    "HIGASHI_HIROSHIMA": "東広島",
    "HIROSHIMA": "広島",
    "SHIN_IWAKUNI": "新岩国",
    "TOKUYAMA": "徳山",
    "SHIN_YAMAGUCHI": "新山口",
    "ASA": "厚狭",
    "SHIN_SHIMONOSEKI": "新下関",
    "KOKURA": "小倉",
    "HAKATA": "博多",
    "SHIN_TOSU": "新鳥栖",
    "KURUME": "久留米",
    "CHIKUGO_FUNAGOYA": "筑後船小屋",
    "SHIN_OMUTA": "新大牟田",
    "SHIN_TAMANA": "新玉名",
    "KUMAMOTO": "熊本",
    "SHIN_YATSUSHIRO": "新八代",
    "SHIN_MINAMATA": "新水俣",
    "IZUMI": "出水",
    "SENDAI_KYUSHU": "川内",
    "KAGOSHIMA_CHUO": "鹿児島中央",
    "TAKEO_ONSEN": "武雄温泉",
    "URESHINO_ONSEN": "嬉野温泉",
    "SHIN_OMURA": "新大村",
    "ISAHAYA": "諫早",
    "NAGASAKI": "長崎",
}

PREFECTURE_BY_ID = {
    "OMIYA": "11",
    "FUKUSHIMA": "07",
    "KORIYAMA": "07",
    "FUKUI": "18",
    "KOKURA": "40",
    "NAGASAKI": "42",
}

ALIAS_BY_ID = {
    "SHIN_IWAKUNI": "清流新岩国",
}

MANUAL_LATLON_BY_ID = {}


def load_source():
    return json.loads((DATA_DIR / "japan_station_coordinates_source.json").read_text(encoding="utf-8"))


def load_secondary_source():
    if not SECONDARY_SOURCE_PATH.exists():
        return {}
    return json.loads(SECONDARY_SOURCE_PATH.read_text(encoding="utf-8"))


def main():
    stations_path = DATA_DIR / "shinkansen_v2_stations.json"
    stations = json.loads(stations_path.read_text(encoding="utf-8"))
    source_items = load_source()
    secondary_source = load_secondary_source()

    updated = 0
    missing = []
    for station in stations:
        if station["id"] in MANUAL_LATLON_BY_ID:
            manual = MANUAL_LATLON_BY_ID[station["id"]]
            station["lat"] = manual["lat"]
            station["lon"] = manual["lon"]
            station["names"]["ja"] = manual["ja"]
            station["latlon_status"] = "manual"
            station["latlon_source"] = "manual"
            updated += 1
            continue

        kanji = KANJI_BY_ID.get(station["id"])
        if not kanji:
            missing.append(station["id"])
            continue
        alias = ALIAS_BY_ID.get(station["id"], kanji)
        candidates = [item for item in source_items if item["name_kanji"] == alias]
        if station["id"] in PREFECTURE_BY_ID:
            candidates = [item for item in candidates if item.get("prefecture") == PREFECTURE_BY_ID[station["id"]]]
        if not candidates:
            secondary = secondary_source.get(alias)
            if secondary:
                station["lat"] = secondary["lat"]
                station["lon"] = secondary["lon"]
                station["names"]["ja"] = alias
                station["latlon_status"] = "real"
                station["latlon_source"] = secondary.get("source", "secondary")
                updated += 1
                continue
            missing.append(station["id"])
            continue
        source = candidates[0]
        if not source.get("stations"):
            missing.append(station["id"])
            continue
        lat = source["stations"][0]["lat"]
        lon = source["stations"][0]["lon"]
        station["lat"] = lat
        station["lon"] = lon
        station["names"]["ja"] = alias
        station["latlon_status"] = "real"
        station["latlon_source"] = "open-data-jp-railway-stations"
        updated += 1

    stations_path.write_text(json.dumps(stations, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated lat/lon for {updated} stations")
    if missing:
        print("Missing mappings:")
        for station_id in missing:
            print(station_id)


if __name__ == "__main__":
    main()
