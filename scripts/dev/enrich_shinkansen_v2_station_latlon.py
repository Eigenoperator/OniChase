#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


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
}

ALIAS_BY_ID = {
    "SHIN_IWAKUNI": "清流新岩国",
}

MANUAL_LATLON_BY_ID = {
    "NAGASAKI": {"lat": 32.75275, "lon": 129.86908, "ja": "長崎"},
    "HONJO_WASEDA": {"lat": 36.218766, "lon": 139.179519, "ja": "本庄早稲田"},
    "SHIROISHI_ZAO": {"lat": 37.991783056, "lon": 140.636077778, "ja": "白石蔵王"},
    "KURIKOMA_KOGEN": {"lat": 38.748678077, "lon": 141.071560979, "ja": "くりこま高原"},
    "MIZUSAWA_ESASHI": {"lat": 39.145217, "lon": 141.188329, "ja": "水沢江刺"},
    "SHICHINOHE_TOWADA": {"lat": 40.719861, "lon": 141.154028, "ja": "七戸十和田"},
    "OKU_TSUGARU_IMABETSU": {"lat": 41.145089, "lon": 140.515583, "ja": "奥津軽いまべつ"},
    "JOMO_KOGEN": {"lat": 36.692777585, "lon": 138.977640867, "ja": "上毛高原"},
    "GALA_YUZAWA": {"lat": 36.950461927, "lon": 138.799450994, "ja": "ガーラ湯沢"},
    "ANNAKA_HARUNA": {"lat": 36.362576042, "lon": 138.849484921, "ja": "安中榛名"},
    "KUROBE_UNAZUKIONSEN": {"lat": 36.874093593, "lon": 137.481268644, "ja": "黒部宇奈月温泉"},
    "ECHIZEN_TAKEFU": {"lat": 35.895630927, "lon": 136.198924434, "ja": "越前たけふ"},
    "GIFU_HASHIMA": {"lat": 35.31583, "lon": 136.68556, "ja": "岐阜羽島"},
    "SHIN_ONOMICHI": {"lat": 34.426746944, "lon": 133.192649722, "ja": "新尾道"},
    "HIGASHI_HIROSHIMA": {"lat": 34.389252894, "lon": 132.75959909, "ja": "東広島"},
    "SHIN_OMUTA": {"lat": 33.071108036, "lon": 130.48881948, "ja": "新大牟田"},
    "SHIN_TAMANA": {"lat": 32.9379663, "lon": 130.5714667, "ja": "新玉名"},
    "URESHINO_ONSEN": {"lat": 33.106381, "lon": 129.998823, "ja": "嬉野温泉"},
    "SHIN_OMURA": {"lat": 32.93278, "lon": 129.95694, "ja": "新大村"},
}


def load_source():
    return json.loads((DATA_DIR / "japan_station_coordinates_source.json").read_text(encoding="utf-8"))


def main():
    stations_path = DATA_DIR / "shinkansen_v2_stations.json"
    stations = json.loads(stations_path.read_text(encoding="utf-8"))
    source_items = load_source()

    updated = 0
    missing = []
    for station in stations:
        if station["id"] in MANUAL_LATLON_BY_ID:
            manual = MANUAL_LATLON_BY_ID[station["id"]]
            station["lat"] = manual["lat"]
            station["lon"] = manual["lon"]
            station["names"]["ja"] = manual["ja"]
            station["latlon_status"] = "manual"
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
        updated += 1

    stations_path.write_text(json.dumps(stations, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated lat/lon for {updated} stations")
    if missing:
        print("Missing mappings:")
        for station_id in missing:
            print(station_id)


if __name__ == "__main__":
    main()
