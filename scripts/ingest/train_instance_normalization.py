#!/usr/bin/env python3

from __future__ import annotations

import re
from typing import Any


def normalize_name(name: str) -> str:
    lowered = name.lower().strip()
    return re.sub(r"[\s\-_()（）・'’.,/]", "", lowered)


AMBIGUOUS_STATION_BY_LINE = {
    ("sendai", "SHINKANSEN_TOHOKU_HOKKAIDO"): "SENDAI_TOHOKU",
    ("sendai", "SHINKANSEN_AKITA"): "SENDAI_TOHOKU",
    ("sendai", "SHINKANSEN_YAMAGATA"): "SENDAI_TOHOKU",
    ("sendai", "SHINKANSEN_KYUSHU"): "SENDAI_KYUSHU",
}

MANUAL_STATION_ALIASES = {
    "akasaka": "JR_EAST_9940105",
    "fujisan": "JR_EAST_9940116",
    "fujikyuhighland": "JR_EAST_9940117",
    "futamatagawa": "JR_EAST_2900110",
    "gekkoji": "JR_EAST_9940115",
    "hazawayokohamakokudai": "HAZAWAYOKOHAMAKOKUDAI",
    "higashikatsura": "JR_EAST_9940110",
    "jichimedicaluniversity": "JICHIIDAI",
    "kamiotsuki": "JR_EAST_9940102",
    "kannami": "JR_EAST_1150102",
    "kasairinkaipark": "KASAIRINKAIKOEN",
    "kasei": "JR_EAST_9940104",
    "kashiwadai": "JR_EAST_2900117",
    "kawaguchiko": "JR_EAST_9940118",
    "kibogaoka": "JR_EAST_2900111",
    "kokusaitenjijo": "KOKUSAITENJIJO",
    "kotobuki": "JR_EAST_9940112",
    "makuharitoyosuna": "MAKUHARITOYOSUNA",
    "mishima": "JR_EAST_1150103",
    "mitsukyo": "JR_EAST_2900112",
    "mitsutoge": "JR_EAST_9940111",
    "naritaairportterminal23": "NARITAAIRPORTTERMINAL2AND3",
    "nishiya": "JR_EAST_2900108",
    "numazu": "JR_EAST_1150104",
    "ryugasakishi": "SANUKI",
    "sagamiotsuka": "JR_EAST_2900115",
    "sagamino": "JR_EAST_2900116",
    "seya": "JR_EAST_2900113",
    "shimoyoshida": "JR_EAST_9940114",
    "shinagawaseaside": "SHINAGAWASEASIDE",
    "shinonome": "SHINONOME_RINKAI",
    "tanokura": "JR_EAST_9940103",
    "tennozuairu": "TENNOZUAIRU_RINKAI",
    "tokyoteleport": "TOKYOTELEPORT",
    "tsurubunkadaigakumae": "JR_EAST_9940108",
    "tsurushi": "JR_EAST_9940106",
    "tsurugamine": "JR_EAST_2900109",
    "yamato": "JR_EAST_1133909",
    "yamuramachi": "JR_EAST_9940107",
    "yoshiikeonsenmae": "JR_EAST_9940113",
}

MANUAL_STATION_NAME_ALIASES = {
    "abukuma": "あぶくま",
    "adachi": "安達",
    "arikabe": "有壁",
    "asakanagamori": "安積永盛",
    "date": "伊達",
    "fujita": "藤田",
    "fukushima": "福島",
    "funaoka": "船岡",
    "furudate": "古館",
    "gohyakugawa": "五百川",
    "hanaizumi": "花泉",
    "hanamaki": "花巻",
    "hanamakikuko": "花巻空港",
    "higashifukushima": "東福島",
    "higashisendai": "東仙台",
    "higashishiroishi": "東白石",
    "hiraizumi": "平泉",
    "hiwada": "日和田",
    "hizume": "日詰",
    "ishidoriya": "石鳥谷",
    "ishikoshi": "石越",
    "iwakiri": "岩切",
    "iwateiioka": "岩手飯岡",
    "izumizaki": "泉崎",
    "jvillage": "Jヴィレッジ",
    "kagamiishi": "鏡石",
    "kaida": "貝田",
    "kanayagawa": "金谷川",
    "kanegasaki": "金ヶ崎",
    "kashimadai": "鹿島台",
    "kitashirakawa": "北白川",
    "kogota": "小牛田",
    "kokufutagajo": "国府多賀城",
    "koori": "桑折",
    "kosugo": "越河",
    "kurodahara": "黒田原",
    "kutano": "久田野",
    "maesawa": "前沢",
    "matsukawa": "松川",
    "matsushima": "松島",
    "matsuyamamachi": "松山町",
    "minamifukushima": "南福島",
    "mizusawa": "水沢",
    "motomiya": "本宮",
    "murasakino": "村崎野",
    "nihommatsu": "二本松",
    "ogawara": "大河原",
    "rikuzensanno": "陸前山王",
    "rikuchuorii": "陸中折居",
    "rifu": "利府",
    "rokuhara": "六原",
    "sembokucho": "仙北町",
    "semine": "瀬峰",
    "shimizuhara": "清水原",
    "shinainuma": "品井沼",
    "shinrifu": "新利府",
    "shiogama": "塩釜",
    "shirasaka": "白坂",
    "shirakawa": "白河",
    "shiroishi": "白石",
    "shiwachuo": "紫波中央",
    "sukagawa": "須賀川",
    "tajiri": "田尻",
    "takagimachi": "高城町",
    "takaku": "高久",
    "toyohara": "豊原",
    "tsukinoki": "槻木",
    "umegasawa": "梅ヶ沢",
    "yabuki": "矢吹",
    "yahaba": "矢幅",
    "yamanome": "山ノ目",
    "yushima": "油島",
}

LINE_STATION_NAME_ALIASES = {
    ("kawashima", "JR_CHUO"): "SHINANOKAWASHIMA",
    ("ono", "JR_CHUO"): "ONO",
    ("ono", "JR_JOBAN"): "大野",
    ("takagimachi", "JR_SENSEKI"): "高城町",
    ("ueda", "JR_JOBAN"): "植田",
    ("kashimasoccerstadium", "JR_KASHIMA"): "KASHIMASOCCERSTADIUM",
    ("kashimasoccerstadiumseasonal", "JR_KASHIMA"): "KASHIMASOCCERSTADIUM",
    ("shinanokawashima", "JR_CHUO"): "信濃川島",
}


def build_station_lookup(stations_data: dict[str, Any]) -> dict[str, str]:
    stations = stations_data["stations"] if isinstance(stations_data, dict) else stations_data
    lookup: dict[str, str] = {}
    for station in stations:
        station_id = station["id"]
        lookup[normalize_name(station_id)] = station_id
        names = station.get("names", {})
        for value in [station.get("name"), names.get("en"), names.get("ja"), names.get("zh_hans")]:
            if value:
                lookup[normalize_name(value)] = station_id

    lookup.update(
        {
            "takanawagateway": "TAKANAWA_GATEWAY",
            "shinokubo": "SHIN_OKUBO",
            "nishinippori": "NISHI_NIPPORI",
            "sakurambohigashine": "SAKURANBO_HIGASHINE",
            "galayuzawaseasonal": "GALA_YUZAWA",
            "shinosaka": "SHIN_OSAKA",
            "shinyokohama": "SHIN_YOKOHAMA",
            "shinhakodatehokuto": "SHIN_HAKODATE_HOKUTO",
            "shinshimonoseki": "SHIN_SHIMONOSEKI",
            "shinomura": "SHIN_OMURA",
            "新岩国": "SHIN_IWAKUNI",
        }
    )
    return lookup


def resolve_station_id(raw_name: str, line_id: str | None, station_lookup: dict[str, str]) -> str | None:
    normalized = normalize_name(raw_name)
    if line_id is not None:
        keyed = AMBIGUOUS_STATION_BY_LINE.get((normalized, line_id))
        if keyed is not None:
            return keyed
        line_alias = LINE_STATION_NAME_ALIASES.get((normalized, line_id))
        if line_alias is not None:
            return station_lookup.get(normalize_name(line_alias), line_alias)
    manual = MANUAL_STATION_ALIASES.get(normalized)
    if manual is not None:
        return manual
    manual_name = MANUAL_STATION_NAME_ALIASES.get(normalized)
    if manual_name is not None:
        return station_lookup.get(normalize_name(manual_name), manual_name)
    return station_lookup.get(normalized)


def normalize_train_instances(
    raw_instances: list[dict[str, Any]],
    stations_data: dict[str, Any],
) -> tuple[list[dict[str, Any]], set[str]]:
    station_lookup = build_station_lookup(stations_data)
    unresolved: set[str] = set()
    normalized_instances: list[dict[str, Any]] = []

    for train in raw_instances:
        normalized_stop_times: list[dict[str, Any]] = []
        station_visit_counts: dict[str, int] = {}

        for stop_time in train.get("stop_times", []):
            raw_name = stop_time["station_name_raw"]
            station_id = resolve_station_id(raw_name, stop_time.get("line_id"), station_lookup)
            if station_id is None:
                unresolved.add(raw_name)
                continue

            normalized_stop_time = dict(stop_time)
            normalized_stop_time["station_id"] = station_id
            station_visit_counts[station_id] = station_visit_counts.get(station_id, 0) + 1
            normalized_stop_time["loop_pass_index"] = station_visit_counts[station_id]
            normalized_stop_times.append(normalized_stop_time)

        normalized_train = dict(train)
        normalized_train["service_instance_id"] = train.get("service_instance_id") or train["train_number"]
        normalized_train["stop_times"] = normalized_stop_times
        normalized_instances.append(normalized_train)

    return normalized_instances, unresolved
