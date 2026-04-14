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
    manual = MANUAL_STATION_ALIASES.get(normalized)
    if manual is not None:
        return manual
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
