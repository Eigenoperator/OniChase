#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "data" / "japan_station_coordinates_source.json"
TOKYO_NETWORK_SEED_PATH = ROOT / "data" / "v3_tokyo_phase1_network_seed.json"
OUTPUT_PATH = ROOT / "data" / "v3_jreast_station_seed.json"


EXTRA_TOKYO_STATIONS = [
    {
        "id": "HAZAWAYOKOHAMAKOKUDAI",
        "name": "Hazawa-Yokohama-Kokudai",
        "names": {
            "en": "Hazawa-Yokohama-Kokudai",
            "ja": "羽沢横浜国大",
            "zh_hans": "羽沢横浜国大",
        },
        "line_codes": ["JR-East.Tokaido"],
    },
    {
        "id": "MAKUHARITOYOSUNA",
        "name": "Makuhari-Toyosuna",
        "names": {
            "en": "Makuhari-Toyosuna",
            "ja": "幕張豊砂",
            "zh_hans": "幕張豊砂",
        },
        "line_codes": ["JR-East.Keiyo"],
    },
    {
        "id": "SHINONOME_RINKAI",
        "name": "Shinonome",
        "names": {
            "en": "Shinonome",
            "ja": "東雲",
            "zh_hans": "东云",
        },
        "line_codes": ["TWR.Rinkai"],
    },
    {
        "id": "SHINAGAWASEASIDE",
        "name": "Shinagawa-Seaside",
        "names": {
            "en": "Shinagawa-Seaside",
            "ja": "品川シーサイド",
            "zh_hans": "品川海滨",
        },
        "line_codes": ["TWR.Rinkai"],
    },
    {
        "id": "TOKYOTELEPORT",
        "name": "Tokyo-Teleport",
        "names": {
            "en": "Tokyo-Teleport",
            "ja": "東京テレポート",
            "zh_hans": "东京电讯港",
        },
        "line_codes": ["TWR.Rinkai"],
    },
    {
        "id": "TENNOZUAIRU_RINKAI",
        "name": "Tennozu-Airu",
        "names": {
            "en": "Tennozu-Airu",
            "ja": "天王洲アイル",
            "zh_hans": "天王洲岛",
        },
        "line_codes": ["TWR.Rinkai"],
    },
    {
        "id": "KOKUSAITENJIJO",
        "name": "Kokusai-Tenjijo",
        "names": {
            "en": "Kokusai-Tenjijo",
            "ja": "国際展示場",
            "zh_hans": "国际展示场",
        },
        "line_codes": ["TWR.Rinkai"],
    },
    {
        "id": "NARITAAIRPORTTERMINAL2AND3",
        "name": "Narita Airport Terminal 2,3",
        "names": {
            "en": "Narita Airport Terminal 2,3",
            "ja": "空港第２ビル（第２旅客ターミナル）",
            "zh_hans": "成田机场第2、3航站楼",
        },
        "line_codes": ["JR-East.Narita"],
    },
]


def slugify(value: str) -> str:
    value = value.strip().upper()
    value = re.sub(r"[^A-Z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def build_station_id(group: dict) -> str:
    for station in group.get("stations", []):
        code = station.get("code") or ""
        if code.startswith("JR-East.") and code.count(".") >= 2:
            tail = code.split(".")[-1]
            if tail:
                return slugify(tail)
    romaji = group.get("name_romaji") or ""
    if romaji:
        return slugify(romaji)
    return f"JR_EAST_{group['group_code']}"


def main() -> int:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    stations = []
    for group in source:
        line_codes = group.get("line_codes", [])

        names = {
            "en": group.get("name_romaji") or build_station_id(group),
            "ja": group.get("name_kanji"),
            "zh_hans": group.get("name_kanji"),
        }
        alt_names = [name for name in group.get("alternative_names", []) if name]
        for station in group.get("stations", []):
            alt_names.extend(name for name in station.get("alternative_names", []) if name)

        lat_candidates = [station["lat"] for station in group.get("stations", []) if station.get("lat") is not None]
        lon_candidates = [station["lon"] for station in group.get("stations", []) if station.get("lon") is not None]
        if not lat_candidates or not lon_candidates:
            continue

        station_id = build_station_id(group)
        stations.append(
            {
                "id": station_id,
                "name": names["en"],
                "names": names,
                "group_code": group.get("group_code"),
                "line_codes": sorted({code for code in line_codes if code}),
                "alternative_names": sorted(set(alt_names)),
                "lat": sum(lat_candidates) / len(lat_candidates),
                "lon": sum(lon_candidates) / len(lon_candidates),
                "prefecture": group.get("prefecture"),
            }
        )

    stations_by_id = {station["id"]: station for station in stations}
    if TOKYO_NETWORK_SEED_PATH.exists():
        visible_stations = json.loads(TOKYO_NETWORK_SEED_PATH.read_text(encoding="utf-8")).get("visibleStations", [])
        visible_by_ja = {}
        for station in visible_stations:
            name_ja = station.get("name_ja")
            if name_ja and name_ja not in visible_by_ja:
                visible_by_ja[name_ja] = station

        for extra in EXTRA_TOKYO_STATIONS:
            if extra["id"] in stations_by_id:
                continue
            visible = visible_by_ja.get(extra["names"]["ja"])
            if visible is None:
                continue
            stations_by_id[extra["id"]] = {
                "id": extra["id"],
                "name": extra["name"],
                "names": extra["names"],
                "group_code": None,
                "line_codes": extra["line_codes"],
                "alternative_names": [],
                "lat": visible["lat"],
                "lon": visible["lon"],
                "prefecture": None,
            }

    output = {
        "id": "v3_jreast_station_seed_v0_1",
        "label": "Canonical all-station seed for v3 Tokyo conventional timetable ingestion",
        "version": "0.1.0",
        "source": "data/japan_station_coordinates_source.json",
        "stations": sorted(stations_by_id.values(), key=lambda item: item["id"]),
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Stations: {len(output['stations'])}")
    print(f"Wrote: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
