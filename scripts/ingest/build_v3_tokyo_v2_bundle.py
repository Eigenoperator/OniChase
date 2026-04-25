#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from v3_station_identity import (
    build_station_alias_index,
    canonical_group_key,
    canonical_station_key,
    normalize_key,
    resolve_station_key,
)
from v3_route_identity import canonical_route_line


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"

MAP_PATH = DATA_DIR / "v3_tokyo_phase1_service_views.json"
UNIFIED_TRAINS_PATH = DATA_DIR / "v3_trains_unified.json.gz"
N02_STATION_PATH = DATA_DIR / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = DATA_DIR / "v3_tokyo_bundle.json.gz"

SPECIAL_STATION_IDS = {
    "東京": "TOKYO",
    "新宿": "SHINJUKU",
    "渋谷": "SHIBUYA",
    "池袋": "IKEBUKURO",
    "上野": "UENO",
    "品川": "SHINAGAWA",
}

OPERATOR_NAME_TO_ID = {
    "東日本旅客鉄道": "jr_east",
    "jr east": "jr_east",
    "東海旅客鉄道": "jr_central",
    "jr central": "jr_central",
    "西日本旅客鉄道": "jr_west",
    "jr west": "jr_west",
    "北海道旅客鉄道": "jr_hokkaido",
    "jr hokkaido": "jr_hokkaido",
    "九州旅客鉄道": "jr_kyushu",
    "jr kyushu": "jr_kyushu",
    "東京地下鉄": "tokyo_metro",
    "tokyo metro": "tokyo_metro",
    "東京都": "toei",
    "東京都交通局": "toei",
    "toei": "toei",
    "京王電鉄": "keio",
    "keio": "keio",
    "東京急行電鉄": "tokyu",
    "東急電鉄": "tokyu",
    "tokyu": "tokyu",
    "西武鉄道": "seibu",
    "seibu": "seibu",
    "相模鉄道": "sotetsu",
    "相鉄": "sotetsu",
    "sotetsu": "sotetsu",
    "京成電鉄": "keisei",
    "keisei": "keisei",
    "京浜急行電鉄": "keikyu",
    "京急電鉄": "keikyu",
    "keikyu": "keikyu",
    "小田急電鉄": "odakyu",
    "odakyu": "odakyu",
    "東武鉄道": "tobu",
    "tobu": "tobu",
    "東京臨海高速鉄道": "rinkai",
    "rinkai": "rinkai",
    "ゆりかもめ": "yurikamome",
    "yurikamome": "yurikamome",
    "東京モノレール": "tokyo_monorail",
    "tokyo monorail": "tokyo_monorail",
    "多摩都市モノレール": "tama_monorail",
    "tama monorail": "tama_monorail",
    "首都圏新都市鉄道": "tsukuba_express",
    "つくばエクスプレス": "tsukuba_express",
    "tsukuba express": "tsukuba_express",
    "埼玉高速鉄道": "saitama_railway",
    "saitama railway": "saitama_railway",
    "saitama rapid railway": "saitama_railway",
}

PHYSICAL_ALIAS_ROUTE_SPECS = {
    "みなとみらい21線": {
        "operator_id": "tokyo_metro",
        "operator_label": "横浜高速鉄道",
        "color": "#09357F",
        "station_names": ["横浜", "新高島", "みなとみらい", "馬車道", "日本大通り", "元町・中華街"],
    },
    "埼玉高速鉄道線": {
        "operator_id": "saitama_railway",
        "operator_label": "埼玉高速鉄道",
        "color": "#00A6E9",
        "station_names": ["赤羽岩淵", "川口元郷", "南鳩ヶ谷", "鳩ヶ谷", "新井宿", "戸塚安行", "東川口", "浦和美園"],
    },
    "相鉄本線": {
        "operator_id": "sotetsu",
        "operator_label": "相鉄",
        "color": "#003C8F",
        "station_names": [
            "平沼橋", "西横浜", "天王町", "星川", "和田町", "上星川",
            "西谷", "鶴ヶ峰", "二俣川", "希望ヶ丘", "三ツ境", "瀬谷",
            "大和", "相模大塚", "さがみ野", "かしわ台", "海老名",
        ],
    },
    "相鉄いずみ野線": {
        "operator_id": "sotetsu",
        "operator_label": "相鉄",
        "color": "#003C8F",
        "station_names": ["二俣川", "南万騎が原", "緑園都市", "弥生台", "いずみ野", "いずみ中央", "ゆめが丘", "湘南台"],
    },
    "相鉄新横浜線": {
        "operator_id": "sotetsu",
        "operator_label": "相鉄",
        "color": "#003C8F",
        "station_names": ["西谷", "羽沢横浜国大", "新横浜"],
    },
}


def load_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write(text)
        return
    path.write_text(text, encoding="utf-8")


def stable_id(prefix: str, value: Any) -> str:
    raw = str(value or "unknown")
    special = SPECIAL_STATION_IDS.get(raw)
    if special:
        return f"{prefix}_{special}"
    cleaned = unicodedata.normalize("NFKC", raw).upper()
    cleaned = re.sub(r"[^A-Z0-9]+", "_", cleaned).strip("_")
    if cleaned and re.search(r"[A-Z]", cleaned):
        return f"{prefix}_{cleaned[:48]}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}_{digest}"


def route_id_for(line: Any, operator_id: str) -> str:
    base = str(line or operator_id or "unknown")
    digest = hashlib.sha1(f"{operator_id}|{base}".encode("utf-8")).hexdigest()[:8].upper()
    return f"R_{digest}"


def normalize_hex_color(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}", text):
        return f"#{text.upper()}"
    return None


def text_color_for_background(color: str | None) -> str:
    normalized = normalize_hex_color(color)
    if not normalized:
        return "#ffffff"
    r = int(normalized[1:3], 16)
    g = int(normalized[3:5], 16)
    b = int(normalized[5:7], 16)
    # W3C relative luminance approximation is enough for route chips.
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#1f2a37" if luminance >= 0.62 else "#ffffff"


def operator_id_for(value: Any) -> str:
    text = str(value or "").strip()
    key = normalize_key(text)
    return OPERATOR_NAME_TO_ID.get(text) or OPERATOR_NAME_TO_ID.get(key) or key or "tokyo"


def hhmm_to_sec(value: Any) -> int | None:
    match = re.match(r"^(\d{1,2}):(\d{2})$", str(value or ""))
    if not match:
        return None
    return (int(match.group(1)) * 60 + int(match.group(2))) * 60


def seconds_or_none(*values: Any) -> int | None:
    for value in values:
        sec = hhmm_to_sec(value)
        if sec is not None:
            return sec
    return None


def station_geometry_point(geometry: dict[str, Any]) -> tuple[float, float] | None:
    coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if not coords:
        return None
    if geometry.get("type") == "Point" and len(coords) >= 2:
        return float(coords[1]), float(coords[0])
    if geometry.get("type") == "LineString":
        points = [point for point in coords if isinstance(point, list) and len(point) >= 2]
        if not points:
            return None
        lon = sum(float(point[0]) for point in points) / len(points)
        lat = sum(float(point[1]) for point in points) / len(points)
        return lat, lon
    return None


def mode_for_operator(operator_id: str) -> str:
    if operator_id == "shinkansen":
        return "shinkansen"
    if operator_id in {"tokyo_metro", "toei"}:
        return "subway"
    return "private_rail" if operator_id not in {"jr_east", "jr_central"} else "rail"


ROUTE_COLOR_ALIASES = {
    "JR_EAST_CHUO_RAPID": "中央線",
    "JR_EAST_CHUO_SOBU_LOCAL": "総武線",
    "JR_EAST_JOBAN_RAPID": "常磐線",
    "JR_CHUO": "中央線",
    "JR_JOBAN": "常磐線",
    "JR_KAWAGOE": "川越線",
    "JR_NARITA": "成田線",
    "JR_OME": "青梅線",
    "JR_TOHOKU": "東北線",
    "JR_UCHIBO": "内房線",
    "JR_SOTOBO": "外房線",
    "JR_TOGANE": "東金線",
    "JR_KASHIMA": "鹿島線",
    "JR_ITO": "伊東線",
    "JR_JOETSU_LOCAL": "上越線",
    "JR_RYOMO": "両毛線",
    "JR_SENSEKI": "仙石線",
    "JR_EAST_KEIHIN_TOHOKU_NEGISHI": "根岸線",
    "JR_EAST_KEIYO_MUSASHINO": "京葉線",
    "JR_EAST_SAIKYO_KAWAGOE": "川越線",
    "JR_EAST_SOBU_RAPID": "横須賀線",
    "JR_EAST_TOKAIDO": "東海道線",
    "JR_EAST_YOKOSUKA": "横須賀線",
    "JR_YAMANOTE": "山手線",
    "TOEI_ARAKAWA": "荒川線",
    "TOEI_ASAKUSA": "1号線浅草線",
    "TOEI_MITA": "6号線三田線",
    "TOEI_NIPPORI_TONERI": "日暮里・舎人ライナー",
    "TOEI_OEDO": "12号線大江戸線",
    "TOEI_SHINJUKU": "10号線新宿線",
    "小田急小田原線": "小田原線",
    "小田急小田原線通勤": "小田原線",
    "小田急江ノ島線": "江ノ島線",
    "小田急多摩線": "多摩線",
    "RINKAI": "臨海副都心線",
    "TOKYO_MONORAIL_HANEDA": "東京モノレール羽田線",
    "TAMA_MONORAIL": "多摩都市モノレール線",
    "YURIKAMOME": "東京臨海新交通臨海線",
    "SHINKANSEN_TOKAIDO_SANYO": "東海道新幹線",
    "SHINKANSEN_TOHOKU_HOKKAIDO": "東北新幹線",
    "SHINKANSEN_JOETSU": "上越新幹線",
    "SHINKANSEN_HOKURIKU": "北陸新幹線",
    "SHINKANSEN_KYUSHU": "九州新幹線",
    "SHINKANSEN_NISHI_KYUSHU": "西九州新幹線",
}


MANUAL_ROUTE_COLORS = {
    "JR_EAST_SHONAN_SHINJUKU": "#E21F26",
    "JR_EAST_UENO_TOKYO": "#7A4FB3",
    "SHINKANSEN_AKITA": "#D54A96",
    "SHINKANSEN_YAMAGATA": "#F09B20",
    "Tokyu": "#D9485F",
}


OPERATOR_DEFAULT_COLORS = {
    "jr_central": "#F77321",
    "jr_east": "#8AA4C8",
    "keikyu": "#D63339",
    "keio": "#F18A00",
    "keisei": "#2457C5",
    "odakyu": "#2B78D0",
    "rinkai": "#1F5AA6",
    "saitama_railway": "#00A6E9",
    "seibu": "#00A15F",
    "shinkansen": "#1F78FF",
    "tama_monorail": "#54C0D8",
    "tobu": "#1F78FF",
    "toei": "#0067B0",
    "tokyo_metro": "#009BBF",
    "tokyo_monorail": "#4CC3E6",
    "tokyu": "#D9485F",
    "tsukuba_express": "#2BB673",
    "yurikamome": "#4BBDDF",
}


def line_color_lookup(map_payload: dict[str, Any]) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
    by_operator_line: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    by_line: dict[str, Counter[str]] = defaultdict(Counter)
    for line in map_payload.get("physicalLines", []):
        color = normalize_hex_color(line.get("color"))
        line_name = str(line.get("line_name_ja") or line.get("label") or "").strip()
        if not color or not line_name:
            continue
        operator_id = operator_id_for(line.get("operator_ja"))
        by_operator_line[(operator_id, line_name)][color] += 1
        by_line[line_name][color] += 1
    return (
        {key: counter.most_common(1)[0][0] for key, counter in by_operator_line.items()},
        {key: counter.most_common(1)[0][0] for key, counter in by_line.items()},
    )


def route_color_for(line: Any, operator_id: str, color_by_operator_line: dict[tuple[str, str], str], color_by_line: dict[str, str]) -> str:
    line_text = str(line or "").strip()
    if line_text in MANUAL_ROUTE_COLORS:
        return MANUAL_ROUTE_COLORS[line_text]
    alias = ROUTE_COLOR_ALIASES.get(line_text, line_text)
    if (operator_id, alias) in color_by_operator_line:
        return color_by_operator_line[(operator_id, alias)]
    if alias in color_by_line:
        return color_by_line[alias]
    if (operator_id, line_text) in color_by_operator_line:
        return color_by_operator_line[(operator_id, line_text)]
    if line_text in color_by_line:
        return color_by_line[line_text]
    return OPERATOR_DEFAULT_COLORS.get(operator_id, "#667487")


def collect_station_identity(map_payload: dict[str, Any], trains: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    alias_index = build_station_alias_index(map_payload.get("visibleStations", []))
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    counts: Counter[str] = Counter()
    train_display: dict[str, str] = {}

    for station in map_payload.get("visibleStations", []):
        name = station.get("name_ja") or station.get("name_en")
        key = canonical_station_key(name)
        if not key:
            continue
        group_key = canonical_group_key(key)
        candidate = {
            "station_key": key,
            "group_key": group_key,
            "display_ja": name or key,
            "display_en": station.get("name_en") or name or key,
            "lat": station.get("lat"),
            "lon": station.get("lon"),
            "is_priority": bool(station.get("is_priority")),
            "operator_ja": station.get("operator_ja"),
            "line_name_ja": station.get("line_name_ja"),
        }
        groups[group_key].append(candidate)

    for train in trains:
        for stop in train.get("stops", []):
            key = resolve_station_key(stop.get("station_key") or stop.get("station_name"), alias_index)
            if key:
                counts[key] += 1
                train_display.setdefault(key, stop.get("station_name") or key)

    if N02_STATION_PATH.exists():
        n02_payload = load_json(N02_STATION_PATH)
        existing_station_keys = {
            station["station_key"]
            for stations in groups.values()
            for station in stations
        }
        n02_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for feature in n02_payload.get("features", []):
            props = feature.get("properties", {})
            name = props.get("N02_005")
            key = canonical_station_key(name)
            if not key:
                continue
            point = station_geometry_point(feature.get("geometry", {}))
            if point is None:
                continue
            n02_by_key[key].append({
                "station_key": key,
                "group_key": canonical_group_key(key),
                "display_ja": name,
                "display_en": name,
                "lat": point[0],
                "lon": point[1],
                "is_priority": False,
                "source": "n02_2024",
                "operator_ja": props.get("N02_004"),
                "line_name_ja": props.get("N02_003"),
            })

        for train_key, count in counts.items():
            if train_key in existing_station_keys:
                continue
            for candidate in n02_by_key.get(train_key, []):
                candidate = dict(candidate)
                candidate["traffic_count"] = count
                groups[candidate["group_key"]].append(candidate)

    for group_key, stations in groups.items():
        for station in stations:
            station["traffic_count"] = counts.get(station["station_key"], 0)

    return groups, alias_index


def build_routes(map_payload: dict[str, Any], trains: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    route_meta: dict[str, dict[str, Any]] = {}
    color_by_operator_line, color_by_line = line_color_lookup(map_payload)

    for train in trains:
        line = canonical_route_line(train)
        operator_id = train.get("operator_id") or "tokyo"
        route_id = route_id_for(line, operator_id)
        route_color = route_color_for(line, operator_id, color_by_operator_line, color_by_line)
        route_meta.setdefault(route_id, {
            "id": route_id,
            "operatorId": operator_id,
            "shortName": str(line or train.get("operator") or route_id),
            "longName": f"{train.get('operator') or 'Tokyo'} / {line or train.get('service_name') or route_id}",
            "color": route_color,
            "textColor": text_color_for_background(route_color),
            "mode": mode_for_operator(operator_id),
        })
    for line, spec in PHYSICAL_ALIAS_ROUTE_SPECS.items():
        operator_id = str(spec["operator_id"])
        route_id = route_id_for(line, operator_id)
        route_color = normalize_hex_color(spec.get("color")) or route_color_for(line, operator_id, color_by_operator_line, color_by_line)
        route_meta.setdefault(route_id, {
            "id": route_id,
            "operatorId": operator_id,
            "shortName": line,
            "longName": f"{spec.get('operator_label') or operator_id} / {line}",
            "color": route_color,
            "textColor": text_color_for_background(route_color),
            "mode": mode_for_operator(operator_id),
        })

    # Physical-only routes stay out of serviceRoutes; otherwise thousands of
    # map fragments appear as empty route cards in the gameplay UI.
    routes = sorted(route_meta.values(), key=lambda item: (item["operatorId"], item["shortName"]))
    return routes, route_meta


def service_route_ids_for_physical_line(line_name: str, operator_id: str, route_meta: dict[str, dict[str, Any]]) -> set[str]:
    route_ids = {route_id_for(line_name, operator_id)}
    for route_id, route in route_meta.items():
        route_operator_id = str(route.get("operatorId") or "")
        short_name = str(route.get("shortName") or "")
        alias = ROUTE_COLOR_ALIASES.get(short_name, short_name)
        if alias != line_name and short_name != line_name:
            continue
        if route_operator_id == operator_id or route_operator_id == "shinkansen":
            route_ids.add(route_id)
    return route_ids


def build_bundle() -> dict[str, Any]:
    map_payload = load_json(MAP_PATH)
    train_payload = load_json(UNIFIED_TRAINS_PATH)
    source_trains = train_payload.get("trains", [])
    station_groups_by_key, station_alias_index = collect_station_identity(map_payload, source_trains)
    service_routes, route_meta = build_routes(map_payload, source_trains)

    physical_stations = []
    station_groups = []
    label_representations = []
    game_nodes = []

    station_key_to_group: dict[str, str] = {}

    def add_station_group_lookup(value: Any, station_group_id: str) -> None:
        for key in {
            str(value or "").strip(),
            canonical_station_key(value),
            canonical_group_key(value),
        }:
            if key:
                station_key_to_group[key] = station_group_id

    def representative(stations: list[dict[str, Any]]) -> dict[str, Any]:
        return sorted(
            stations,
            key=lambda item: (not item.get("is_priority"), -int(item.get("traffic_count", 0)), item.get("display_ja") or ""),
        )[0]

    for group_key, stations in sorted(station_groups_by_key.items(), key=lambda item: item[0]):
        valid_stations = [
            station for station in stations
            if isinstance(station.get("lat"), (int, float)) and isinstance(station.get("lon"), (int, float))
        ]
        if not valid_stations:
            continue
        rep = representative(valid_stations)
        sgid = stable_id("SG", group_key)
        physical_ids = []
        traffic_count = sum(int(station.get("traffic_count", 0)) for station in valid_stations)
        label_rank = 100 if any(station.get("is_priority") for station in valid_stations) else 92 if traffic_count >= 1000 else 72
        tags = ["tokyo", "v3"]
        for index, coord in enumerate(valid_stations):
            psid = stable_id("PS", f"{coord['station_key']}|{coord['lat']:.7f}|{coord['lon']:.7f}|{index}")
            physical_ids.append(psid)
            add_station_group_lookup(coord["station_key"], sgid)
            add_station_group_lookup(coord.get("display_ja"), sgid)
            add_station_group_lookup(coord.get("display_en"), sgid)
            physical_stations.append({
                "id": psid,
                "name": coord["display_en"],
                "names": {"en": coord["display_en"], "ja": coord["display_ja"], "zh_hans": coord["display_ja"]},
                "operatorIds": [operator_id_for(coord.get("operator_ja"))] if coord.get("operator_ja") else [],
                "lat": coord["lat"],
                "lon": coord["lon"],
                "sourceStopIds": [coord["station_key"]],
                "stationGroupId": sgid,
                "tags": tags,
            })
        station_groups.append({
            "id": sgid,
            "primaryName": rep["display_en"],
            "names": {"en": rep["display_en"], "ja": rep["display_ja"], "zh_hans": rep["display_ja"]},
            "physicalStationIds": physical_ids,
            "centroid": {
                "lat": sum(station["lat"] for station in valid_stations) / len(valid_stations),
                "lon": sum(station["lon"] for station in valid_stations) / len(valid_stations),
            },
            "category": "hub" if label_rank >= 100 else "normal",
            "labelRank": label_rank,
            "tags": tags,
        })
        label_representations.append({
            "stationGroupId": sgid,
            "minZoom": 3 if label_rank >= 100 else 5,
            "maxZoom": 24,
            "labelRank": label_rank,
            "displayNameJa": rep["display_ja"],
            "displayNameEn": rep["display_en"],
            "labelPoint": {"lat": rep["lat"], "lon": rep["lon"]},
        })
        game_nodes.append({
            "id": stable_id("GN", group_key),
            "stationGroupIds": [sgid],
            "primaryStationGroupId": sgid,
            "category": "hub" if label_rank >= 100 else "normal",
            "revealName": rep["display_en"],
            "tags": tags,
        })

    for source_key, target_key in station_alias_index.items():
        if target_key in station_key_to_group:
            station_key_to_group[source_key] = station_key_to_group[target_key]

    station_group_set = set(station_key_to_group.values())
    default_runner = station_key_to_group.get("東京") or next(iter(station_group_set), None)
    default_hunter = station_key_to_group.get("新宿") or default_runner

    track_centerlines = []
    service_geometry = []
    for index, line in enumerate(map_payload.get("physicalLines", [])):
        coords = line.get("coordinates") or []
        if len(coords) < 2:
            continue
        map_operator_id = operator_id_for(line.get("operator_ja"))
        line_name = line.get("line_name_ja") or line.get("label") or ""
        route_ids = service_route_ids_for_physical_line(str(line_name), map_operator_id, route_meta)
        line_color = normalize_hex_color(line.get("color")) or OPERATOR_DEFAULT_COLORS.get(map_operator_id, "#8aa4c8")
        polyline = [{"lat": lat, "lon": lon} for lon, lat in coords]
        track_centerlines.append({
            "id": f"TRACK_TOKYO_{index:04d}",
            "operatorId": map_operator_id,
            "lineName": line_name or next(iter(route_ids)),
            "mode": "rail" if line.get("kind") == "jr" else line.get("kind") or "rail",
            "color": line_color,
            "polyline": polyline,
            "stationGroupIds": [],
            "tags": ["tokyo", "track_centerline"],
        })
        for route_index, route_id in enumerate(sorted(route_ids)):
            service_geometry.append({
                "id": f"GEOM_TOKYO_{index:04d}_{route_index:02d}",
                "routeId": route_id,
                "representation": "service_path",
                "minZoom": 0,
                "maxZoom": 24,
                "offsetRank": 0,
                "color": line_color,
                "lineName": line_name or route_id,
                "operatorId": map_operator_id,
                "polyline": polyline,
            })

    trip_instances = []
    skipped_trains = 0
    for train in source_trains:
        route_id = route_id_for(canonical_route_line(train), train.get("operator_id", "tokyo"))
        stop_times = []
        for stop in train.get("stops", []):
            resolved_station_key = resolve_station_key(stop.get("station_key") or stop.get("station_name"), station_alias_index)
            sgid = station_key_to_group.get(resolved_station_key)
            if not sgid:
                continue
            arr = seconds_or_none(stop.get("arrival"), stop.get("departure"))
            dep = seconds_or_none(stop.get("departure"), stop.get("arrival"))
            if arr is None and dep is None:
                continue
            stop_times.append({
                "sequence": len(stop_times) + 1,
                "stationGroupId": sgid,
                "arrivalTimeSec": arr if arr is not None else dep,
                "departureTimeSec": dep if dep is not None else arr,
            })
        if len(stop_times) < 2:
            skipped_trains += 1
            continue
        public_service_number = train.get("service_number") or train.get("public_service_number") or train.get("train_number") or ""
        trip_instances.append({
            "id": train.get("id"),
            "routeId": route_id,
            "serviceName": train.get("service_name") or train.get("operator") or "Train",
            "serviceNumber": public_service_number,
            "operatingNumber": train.get("operating_number") or train.get("train_number") or "",
            "stopTimes": stop_times,
        })

    route_station_sets: dict[str, set[str]] = defaultdict(set)
    for trip in trip_instances:
        route_station_sets[trip["routeId"]].update(stop["stationGroupId"] for stop in trip["stopTimes"])
    for line, spec in PHYSICAL_ALIAS_ROUTE_SPECS.items():
        route_id = route_id_for(line, str(spec["operator_id"]))
        for station_name in spec["station_names"]:
            station_group_id = station_key_to_group.get(station_name)
            if station_group_id:
                route_station_sets[route_id].add(station_group_id)

    service_patterns = [{
        "id": f"PATTERN_{route['id']}",
        "routeId": route["id"],
        "label": route["shortName"],
        "stationGroupIds": sorted(route_station_sets.get(route["id"], station_group_set)),
        "shapeId": None,
        "tags": ["tokyo"],
    } for route in service_routes]

    return {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "metadata": {
            "label": "OniChase V3 Tokyo bundle for V2 UI",
            "datasetId": "v3_tokyo_v2_ui_bundle_v0_1",
            "sourceTrainIndex": str(UNIFIED_TRAINS_PATH.relative_to(ROOT)),
            "sourceMap": str(MAP_PATH.relative_to(ROOT)),
            "bundleFormat": "json.gz",
            "skippedTrainCount": skipped_trains,
            "defaultRunnerStartStationId": default_runner,
            "defaultHunterStartStationId": default_hunter,
        },
        "physicalStations": physical_stations,
        "stationGroups": station_groups,
        "trackCenterlines": track_centerlines,
        "pathways": [],
        "serviceRoutes": service_routes,
        "servicePatterns": service_patterns,
        "tripInstances": trip_instances,
        "serviceGeometry": service_geometry,
        "labelRepresentations": label_representations,
        "gameNodes": game_nodes,
    }


def main() -> int:
    bundle = build_bundle()
    write_json(OUTPUT_PATH, bundle)
    write_json(DOCS_DATA_DIR / OUTPUT_PATH.name, bundle)
    print(json.dumps({
        "bundle": str(OUTPUT_PATH.relative_to(ROOT)),
        "physicalStations": len(bundle["physicalStations"]),
        "serviceRoutes": len(bundle["serviceRoutes"]),
        "trackCenterlines": len(bundle["trackCenterlines"]),
        "tripInstances": len(bundle["tripInstances"]),
        "skippedTrainCount": bundle["metadata"]["skippedTrainCount"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
