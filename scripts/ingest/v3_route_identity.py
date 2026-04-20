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


def _station_names(train: dict[str, Any]) -> set[str]:
    return {
        str(stop.get("station_name") or stop.get("station_key") or "")
        for stop in train.get("stops", [])
    }


def _is_odakyu_limited_express(line: str) -> bool:
    return any(re.match(pattern, line) for pattern in ODAKYU_LIMITED_EXPRESS_PATTERNS)


def canonical_route_line(train: dict[str, Any]) -> str:
    operator_id = str(train.get("operator_id") or "")
    line = str(train.get("line") or train.get("service_name") or train.get("operator") or operator_id or "unknown")

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
