from __future__ import annotations

import re
from typing import Any


ODAKYU_LIMITED_EXPRESS_PATTERNS = [
    r"^(メトロ)?はこね\d+号$",
    r"^ふじさん\d+号$",
    r"^さがみ\d+号$",
    r"^えのしま\d+号$",
    r"^(メトロ)?ホームウェイ\d+号$",
    r"^(メトロ)?モーニングウェイ\d+号$",
]

ODAKYU_ENOSHIMA_STATIONS = {
    "藤沢",
    "片瀬江ノ島",
    "中央林間",
    "大和",
    "湘南台",
    "長後",
    "高座渋谷",
    "桜ヶ丘",
    "鶴間",
    "南林間",
}

ODAKYU_TAMA_STATIONS = {
    "唐木田",
    "小田急多摩センター",
    "小田急永山",
    "栗平",
    "黒川",
    "はるひ野",
    "五月台",
}

TOKYO_METRO_SERVICE_LINE_TO_ROUTE = {
    "銀座線": "3号線銀座線",
    "丸ノ内線": "4号線丸ノ内線",
    "日比谷線": "2号線日比谷線",
    "東西線": "5号線東西線",
    "千代田線": "9号線千代田線",
    "有楽町線": "8号線有楽町線",
    "半蔵門線": "11号線半蔵門線",
    "南北線": "7号線南北線",
    "副都心線": "13号線副都心線",
}

TOKYO_METRO_OFFICIAL_ROUTE_NAMES = {
    *TOKYO_METRO_SERVICE_LINE_TO_ROUTE.values(),
    "4号線丸ノ内線分岐線",
}

TOKYO_METRO_ROUTE_SIGNATURE_STATIONS = {
    "2号線日比谷線": {"日比谷", "人形町", "小伝馬町", "築地", "神谷町", "広尾", "六本木", "茅場町", "入谷", "三ノ輪", "南千住"},
    "3号線銀座線": {"浅草", "田原町", "稲荷町", "末広町", "京橋", "銀座", "虎ノ門", "外苑前"},
    "4号線丸ノ内線": {"新宿御苑前", "四谷三丁目", "赤坂見附", "国会議事堂前", "御茶ノ水", "茗荷谷", "新大塚", "方南町"},
    "5号線東西線": {"早稲田", "神楽坂", "竹橋", "茅場町", "木場", "東陽町", "南砂町", "西葛西", "葛西", "浦安"},
    "7号線南北線": {"白金高輪", "麻布十番", "六本木一丁目", "溜池山王", "東大前", "本駒込", "王子神谷"},
    "8号線有楽町線": {"麹町", "桜田門", "護国寺", "江戸川橋", "月島", "豊洲", "辰巳", "新木場"},
    "9号線千代田線": {"代々木上原", "乃木坂", "根津", "千駄木", "町屋", "綾瀬", "北綾瀬"},
    "11号線半蔵門線": {"半蔵門", "水天宮前", "清澄白河", "住吉", "神保町", "九段下"},
    "13号線副都心線": {"北参道", "東新宿", "西早稲田", "雑司が谷", "要町", "氷川台", "平和台", "地下鉄赤塚", "地下鉄成増"},
}


def _station_names(train: dict[str, Any]) -> set[str]:
    return {
        str(stop.get("station_name") or stop.get("station_key") or "")
        for stop in train.get("stops", [])
    }


def _tokyo_metro_signature_route(train: dict[str, Any]) -> str | None:
    stops = _station_names(train)
    best_route = None
    best_score = 0
    tied = False
    for route, signatures in TOKYO_METRO_ROUTE_SIGNATURE_STATIONS.items():
        score = len(stops & signatures)
        if score > best_score:
            best_route = route
            best_score = score
            tied = False
        elif score and score == best_score:
            tied = True
    if best_score >= 2 and not tied:
        return best_route
    return None


def _is_odakyu_limited_express(line: str) -> bool:
    return any(re.match(pattern, line) for pattern in ODAKYU_LIMITED_EXPRESS_PATTERNS)


def canonical_route_line(train: dict[str, Any]) -> str:
    operator_id = str(train.get("operator_id") or "")
    line = str(train.get("line") or train.get("service_name") or train.get("operator") or operator_id or "unknown")

    if operator_id == "tokyo_metro":
        service_name = str(train.get("service_name") or "")
        signature_route = _tokyo_metro_signature_route(train)
        if signature_route:
            return signature_route
        service_route = next(
            (
                route_name
                for service_token, route_name in TOKYO_METRO_SERVICE_LINE_TO_ROUTE.items()
                if service_token in service_name
            ),
            None,
        )
        if service_route:
            if line == "4号線丸ノ内線分岐線" and service_route == "4号線丸ノ内線":
                return line
            if line in TOKYO_METRO_OFFICIAL_ROUTE_NAMES and line == service_route:
                return line
            return service_route

    if operator_id == "tokyu" and line in {"", "None", "Tokyu"}:
        return "Tokyu"

    if operator_id == "odakyu" and _is_odakyu_limited_express(line):
        stops = _station_names(train)
        if stops & ODAKYU_ENOSHIMA_STATIONS:
            return "小田急江ノ島線"
        if stops & ODAKYU_TAMA_STATIONS:
            return "小田急多摩線"
        return "小田急小田原線"

    if operator_id == "odakyu" and line == "箱根登山線（小田原-箱根湯本）":
        return "小田急小田原線"

    return line
