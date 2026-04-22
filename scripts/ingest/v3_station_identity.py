from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any


MANUAL_STATION_ALIASES = {
    "明治神宮前〈原宿〉": "明治神宮前",
    "霞ケ関": "霞ヶ関",
    "市ケ谷": "市ヶ谷",
    "takanawagateway": "高輪ゲートウェイ",
    "天王洲岛": "天王洲アイル",
    "溝の口〔東急線〕": "溝の口",
    "押上〈スカイツリ前〉": "押上",
    "押上〈スカイツリー前〉": "押上",
    "元町中華街": "元町・中華街",
    "阿佐ケ谷": "阿佐ヶ谷",
    "东京电讯港": "東京テレポート",
    "国际展示场": "国際展示場",
    "东云": "東雲",
    "品川海滨": "品川シーサイド",
    "二重橋前〈丸の内〉": "二重橋前",
    "西ケ原": "西ヶ原",
    "千駄ケ谷": "千駄ヶ谷",
    "南阿佐ケ谷": "南阿佐ヶ谷",
    "本八幡〔jr〕": "本八幡",
    "本八幡〔ＪＲ〕": "本八幡",
    "両国〔jr〕": "両国",
    "両国〔ＪＲ〕": "両国",
    "茅ケ崎": "茅ヶ崎",
    "姉ケ崎": "姉ヶ崎",
    "袖ケ浦": "袖ヶ浦",
    "箱根ケ崎": "箱根ヶ崎",
    "hakonegasaki": "箱根ヶ崎",
    "獨協大学前[草加松原]": "獨協大学前",
    "麴町": "麹町",
    "kasairinkaipark": "葛西臨海公園",
    "ryugasakishi": "龍ケ崎市",
    "jichimedicaluniversity": "自治医大",
    "naritaairportterminal2,3": "空港第2ビル",
    "sakurambohigashine": "さくらんぼ東根",
    "morioka": "盛岡",
    "akita": "秋田",
    "omagari": "大曲",
    "kakunodate": "角館",
    "tazawako": "田沢湖",
    "yamagata": "山形",
    "yonezawa": "米沢",
    "kaminoyamaonsen": "かみのやま温泉",
    "akayu": "赤湯",
    "shinjo": "新庄",
    "oishida": "大石田",
    "murayama": "村山",
    "tendo": "天童",
    "takahata": "高畠",
    "kannami": "函南",
    "numazu": "沼津",
    "akasaka": "赤坂",
    "fujikyuhighland": "富士急ハイランド",
    "fujisan": "富士山",
    "gekkoji": "月江寺",
    "higashikatsura": "東桂",
    "kamiotsuki": "上大月",
    "kasei": "禾生",
    "kawaguchiko": "河口湖",
    "kotobuki": "寿",
    "mitsutoge": "三つ峠",
    "shimoyoshida": "下吉田",
    "tanokura": "田野倉",
    "tsurubunkadaigakumae": "都留文科大学前",
    "tsurushi": "都留市",
    "yamuramachi": "谷村町",
    "yoshiikeonsenmae": "葭池温泉前",
    "futamatagawa": "二俣川",
    "kashiwadai": "かしわ台",
    "kibogaoka": "希望ヶ丘",
    "mitsukyo": "三ツ境",
    "nishiya": "西谷",
    "sagamino": "さがみ野",
    "sagamiotsuka": "相模大塚",
    "seya": "瀬谷",
    "tsurugamine": "鶴ヶ峰",
    "yamato": "大和",
}

MANUAL_GROUP_ALIASES = {
    "原宿": "明治神宮前",
}


def normalize_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"[\s\-‐‑‒–—ー・･'’`]", "", text)
    return text


def loose_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = text.replace("ヶ", "ケ")
    text = text.replace("ケ", "が")
    text = text.replace("ヵ", "カ")
    text = text.replace("髙", "高")
    text = text.replace("﨑", "崎")
    text = text.replace("麴", "麹")
    text = re.sub(r"[\(（\[【〔〈<].*?[\)）\]】〕〉>]", "", text)
    text = re.sub(r"[\s\-‐‑‒–—ー・･'’`/／]", "", text)
    return text


def canonical_station_key(value: Any) -> str:
    raw = str(value or "")
    manual = MANUAL_STATION_ALIASES.get(raw)
    if manual is not None:
        return normalize_key(manual)
    normalized = normalize_key(raw)
    manual = MANUAL_STATION_ALIASES.get(normalized)
    if manual is not None:
        return normalize_key(manual)
    return normalized


def canonical_group_key(value: Any) -> str:
    station_key = canonical_station_key(value)
    manual = MANUAL_GROUP_ALIASES.get(station_key)
    if manual is not None:
        return canonical_station_key(manual)
    return station_key


def build_station_alias_index(map_stations: list[dict[str, Any]]) -> dict[str, str]:
    index: dict[str, str] = {}
    loose_index: dict[str, list[str]] = defaultdict(list)

    for station in map_stations:
        name = station.get("name_ja") or station.get("name_en")
        key = canonical_station_key(name)
        if not key:
            continue
        index[key] = key
        loose_index[loose_key(name)].append(key)

    for source, target in MANUAL_STATION_ALIASES.items():
        source_key = normalize_key(source)
        target_key = canonical_station_key(target)
        if target_key:
            index[source_key] = target_key
            index[loose_key(source)] = target_key

    for loose, targets in loose_index.items():
        unique_targets = sorted(set(targets))
        if len(unique_targets) == 1:
            index.setdefault(loose, unique_targets[0])

    return index


def resolve_station_key(value: Any, alias_index: dict[str, str]) -> str:
    key = canonical_station_key(value)
    if key in alias_index:
        return alias_index[key]
    loose = loose_key(value)
    if loose in alias_index:
        return alias_index[loose]
    return key
