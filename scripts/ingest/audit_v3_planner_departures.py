#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

MAP_BUNDLE_PATH = DATA_DIR / "v3_tokyo_map_bundle.json.gz"
TIMETABLE_BUNDLE_PATH = DATA_DIR / "v3_tokyo_timetable_bundle.json.gz"
OUTPUT_PATH = DATA_DIR / "v3_planner_departure_audit.json"

FOCUS_OPERATORS = ("jr_east", "tokyo_metro", "keikyu")
PHYSICAL_ROUTE_STATION_DISTANCE_SQ = 0.000018

PHYSICAL_ALIAS_OPERATOR_LABELS = {
    "みなとみらい21線": "横浜高速鉄道",
    "埼玉高速鉄道線": "埼玉高速鉄道",
    "相鉄いずみ野線": "相鉄",
    "相鉄本線": "相鉄",
}
PHYSICAL_ALIAS_STATION_OPERATORS = {
    "みなとみらい21線": ["横浜高速鉄道"],
    "埼玉高速鉄道線": ["saitama_railway", "埼玉高速鉄道"],
    "相鉄いずみ野線": ["sotetsu", "相模鉄道", "相鉄"],
    "相鉄本線": ["sotetsu", "相模鉄道", "相鉄"],
}
PHYSICAL_ALIAS_ROUTE_NAMES = set(PHYSICAL_ALIAS_OPERATOR_LABELS)
TOKYO_METRO_PHYSICAL_ROUTE_NAMES = {
    "3号線銀座線",
    "4号線丸ノ内線",
    "4号線丸ノ内線分岐線",
    "2号線日比谷線",
    "5号線東西線",
    "9号線千代田線",
    "8号線有楽町線",
    "11号線半蔵門線",
    "7号線南北線",
    "13号線副都心線",
}
ROUTE_JA_LABELS = {
    "JR_EAST_CHUO_RAPID": "中央線快速",
    "JR_EAST_CHUO_SOBU_LOCAL": "中央・総武線各駅停車",
    "JR_EAST_JOBAN_RAPID": "常磐線快速",
    "JR_NARITA": "成田線",
    "JR_OME": "青梅線",
    "JR_UCHIBO": "内房線",
    "JR_SOTOBO": "外房線",
    "JR_TOGANE": "東金線",
    "JR_KASHIMA": "鹿島線",
    "JR_ITO": "伊東線",
    "JR_JOETSU_LOCAL": "上越線",
    "JR_RYOMO": "両毛線",
    "JR_EAST_KEIHIN_TOHOKU_NEGISHI": "京浜東北線・根岸線",
    "JR_EAST_KEIYO_MUSASHINO": "京葉線・武蔵野線",
    "JR_EAST_SAIKYO_KAWAGOE": "埼京線・川越線",
    "JR_EAST_SHONAN_SHINJUKU": "湘南新宿ライン",
    "JR_EAST_SOBU_RAPID": "総武快速線",
    "JR_EAST_TOKAIDO": "東海道線",
    "JR_EAST_UENO_TOKYO": "上野東京ライン",
    "JR_EAST_YOKOSUKA": "横須賀線",
    "JR_YAMANOTE": "山手線",
    "RINKAI": "りんかい線",
    "SHINKANSEN_AKITA": "秋田新幹線",
    "SHINKANSEN_HOKURIKU": "北陸新幹線",
    "SHINKANSEN_JOETSU": "上越新幹線",
    "SHINKANSEN_KYUSHU": "九州新幹線",
    "SHINKANSEN_NISHI_KYUSHU": "西九州新幹線",
    "SHINKANSEN_TOHOKU_HOKKAIDO": "東北・北海道新幹線",
    "SHINKANSEN_TOKAIDO_SANYO": "東海道・山陽新幹線",
    "SHINKANSEN_YAMAGATA": "山形新幹線",
    "TAMA_MONORAIL": "多摩モノレール線",
    "TOEI_ARAKAWA": "都電荒川線",
    "TOEI_ASAKUSA": "都営浅草線",
    "TOEI_MITA": "都営三田線",
    "TOEI_NIPPORI_TONERI": "日暮里・舎人ライナー",
    "TOEI_OEDO": "都営大江戸線",
    "TOEI_SHINJUKU": "都営新宿線",
    "TOKYO_MONORAIL_HANEDA": "東京モノレール羽田空港線",
    "Tokyu": "東急線",
    "YURIKAMOME": "ゆりかもめ",
    "2号線日比谷線": "日比谷線",
    "3号線銀座線": "銀座線",
    "4号線丸ノ内線": "丸ノ内線",
    "4号線丸ノ内線分岐線": "丸ノ内線方南町支線",
    "5号線東西線": "東西線",
    "6号線三田線": "三田線",
    "7号線南北線": "南北線",
    "8号線有楽町線": "有楽町線",
    "9号線千代田線": "千代田線",
    "10号線新宿線": "新宿線",
    "11号線半蔵門線": "半蔵門線",
    "12号線大江戸線": "大江戸線",
    "13号線副都心線": "副都心線",
}
ROUTE_TRACK_LINE_ALIASES = {
    "JR_EAST_CHUO_RAPID": ["中央線", "青梅線"],
    "JR_EAST_CHUO_SOBU_LOCAL": ["中央線", "総武線"],
    "JR_EAST_JOBAN_RAPID": ["常磐線", "成田線"],
    "JR_NARITA": ["成田線", "常磐線"],
    "JR_OME": ["青梅線", "中央線"],
    "JR_UCHIBO": ["内房線"],
    "JR_SOTOBO": ["外房線"],
    "JR_TOGANE": ["東金線", "外房線"],
    "JR_KASHIMA": ["鹿島線", "成田線"],
    "JR_ITO": ["伊東線", "東海道線"],
    "JR_JOETSU_LOCAL": ["上越線", "高崎線"],
    "JR_RYOMO": ["両毛線", "上越線", "高崎線"],
    "JR_EAST_KEIHIN_TOHOKU_NEGISHI": ["東北線", "東海道線", "根岸線"],
    "JR_EAST_KEIYO_MUSASHINO": ["京葉線", "武蔵野線", "外房線", "内房線", "東金線"],
    "JR_EAST_SAIKYO_KAWAGOE": ["山手線", "赤羽線", "東北線", "川越線", "相鉄本線"],
    "JR_EAST_SHONAN_SHINJUKU": ["東海道線", "山手線", "東北線", "高崎線", "上越線", "両毛線", "横須賀線"],
    "JR_EAST_SOBU_RAPID": ["総武線", "成田線", "内房線", "外房線", "鹿島線"],
    "JR_EAST_TOKAIDO": ["東海道線", "伊東線", "高崎線", "上越線", "両毛線", "東北線", "常磐線", "成田線"],
    "JR_EAST_UENO_TOKYO": ["常磐線", "成田線", "東北線", "高崎線", "上越線", "両毛線", "東海道線", "伊東線"],
    "JR_EAST_YOKOSUKA": ["横須賀線", "東海道線", "総武線", "成田線", "内房線", "外房線", "鹿島線"],
    "JR_YAMANOTE": ["山手線"],
    "RINKAI": ["臨海副都心線", "りんかい線"],
    "SHINKANSEN_AKITA": ["東北新幹線", "田沢湖線", "奥羽線"],
    "SHINKANSEN_HOKURIKU": ["北陸新幹線"],
    "SHINKANSEN_JOETSU": ["上越新幹線"],
    "SHINKANSEN_KYUSHU": ["九州新幹線"],
    "SHINKANSEN_NISHI_KYUSHU": ["西九州新幹線"],
    "SHINKANSEN_TOHOKU_HOKKAIDO": ["東北新幹線", "北海道新幹線"],
    "SHINKANSEN_TOKAIDO_SANYO": ["東海道新幹線", "山陽新幹線"],
    "SHINKANSEN_YAMAGATA": ["東北新幹線", "奥羽線"],
    "TAMA_MONORAIL": ["多摩都市モノレール線"],
    "TOEI_ARAKAWA": ["荒川線", "都電荒川線"],
    "TOEI_ASAKUSA": ["1号線浅草線", "都営浅草線"],
    "TOEI_MITA": ["6号線三田線", "都営三田線", "相鉄本線"],
    "TOEI_NIPPORI_TONERI": ["日暮里・舎人ライナー"],
    "TOEI_OEDO": ["12号線大江戸線", "都営大江戸線"],
    "TOEI_SHINJUKU": ["10号線新宿線", "都営新宿線"],
    "TOKYO_MONORAIL_HANEDA": ["東京モノレール羽田線", "東京モノレール羽田空港線"],
    "東急新横浜線": ["東急新横浜線", "東横線", "目黒線"],
    "Tokyu": ["東横線", "目黒線", "田園都市線", "大井町線", "池上線", "東急多摩川線", "世田谷線", "こどもの国線", "東急新横浜線"],
    "YURIKAMOME": ["東京臨海新交通臨海線", "ゆりかもめ東京臨海新交通臨海線", "ゆりかもめ"],
    "小田急多摩線": ["多摩線", "小田原線"],
    "小田急小田原線": ["小田原線"],
    "小田急小田原線通勤": ["小田原線"],
    "小田急江ノ島線": ["江ノ島線"],
    "7号線南北線": ["7号線南北線", "南北線", "埼玉高速鉄道線", "相鉄本線"],
    "8号線有楽町線": ["8号線有楽町線", "有楽町線", "みなとみらい21線", "相鉄本線"],
    "13号線副都心線": ["13号線副都心線", "副都心線", "東横線", "みなとみらい21線", "相鉄本線"],
    "埼玉高速鉄道線": ["埼玉高速鉄道線", "南北線"],
    "相鉄本線": ["相鉄本線", "相鉄いずみ野線", "目黒線", "東横線", "東急新横浜線"],
    "相鉄いずみ野線": ["相鉄いずみ野線", "相鉄本線", "目黒線", "東横線", "東急新横浜線"],
    "みなとみらい21線": ["みなとみらい21線", "東横線", "池袋線", "西武有楽町線", "副都心線"],
    "会津鬼怒川線": ["鬼怒川線"],
}
TRACK_LINE_ALIAS_PREFIXES = (
    "JR",
    "ＪＲ",
    "東京メトロ",
    "都営",
    "東京モノレール",
    "モノレール",
    "京急",
    "京成",
    "京王",
    "小田急",
    "東急",
    "東武",
    "西武",
    "相鉄",
    "横浜高速鉄道",
    "埼玉高速鉄道",
    "東京臨海高速鉄道",
    "首都圏新都市鉄道",
    "多摩都市モノレール",
    "ゆりかもめ",
)


def load_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def route_title(route: dict[str, Any] | None) -> str:
    if not route:
        return "Unknown"
    for candidate in (route.get("shortName"), route.get("longName"), route.get("id")):
        if candidate in ROUTE_JA_LABELS:
            return ROUTE_JA_LABELS[candidate]
    return str(route.get("shortName") or route.get("longName") or route.get("id") or "Unknown")


def display_name_for_group(group: dict[str, Any] | None, station: dict[str, Any] | None = None) -> str:
    if group and group.get("names", {}).get("ja"):
        return str(group["names"]["ja"])
    if station and station.get("names", {}).get("ja"):
        return str(station["names"]["ja"])
    if group and group.get("primaryName"):
        return str(group["primaryName"])
    return str((group or {}).get("id") or (station or {}).get("stationGroupId") or "Unknown")


def top_counter_items(counter: Counter[Any], limit: int = 20) -> list[tuple[Any, int]]:
    return counter.most_common(limit)


def normalized_transfer_station_name(name: Any) -> str:
    text = str(name or "").strip()
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace(" ", "")
    normalized = normalized.replace("　", "")
    prefixes = ("JR", "ＪＲ", "東京メトロ", "都営", "東京モノレール", "モノレール", "京急", "京成", "京王", "小田急", "東急", "東武", "西武", "相鉄", "りんかい", "ゆりかもめ")
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    if normalized.endswith("駅"):
        normalized = normalized[:-1]
    return normalized


def point_segment_distance_sq(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) * (px - ax)) + ((py - ay) * (py - ay))
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / ((dx * dx) + (dy * dy))))
    cx = ax + t * dx
    cy = ay + t * dy
    return ((px - cx) * (px - cx)) + ((py - cy) * (py - cy))


def polyline_distance_sq_to_point(polyline: list[dict[str, Any]], coordinate: tuple[float, float]) -> float:
    if not polyline or coordinate is None:
        return float("inf")
    best = float("inf")
    for index in range(1, len(polyline)):
        start = (polyline[index - 1].get("lon"), polyline[index - 1].get("lat"))
        end = (polyline[index].get("lon"), polyline[index].get("lat"))
        if not all(isinstance(value, (int, float)) for value in (*start, *end)):
            continue
        best = min(best, point_segment_distance_sq(coordinate, start, end))
    if best < float("inf"):
        return best
    first = polyline[0]
    if not isinstance(first.get("lon"), (int, float)) or not isinstance(first.get("lat"), (int, float)):
        return best
    return ((coordinate[0] - first["lon"]) * (coordinate[0] - first["lon"])) + ((coordinate[1] - first["lat"]) * (coordinate[1] - first["lat"]))


class PlannerDepartureAudit:
    def __init__(self, map_bundle: dict[str, Any], timetable_bundle: dict[str, Any]) -> None:
        self.map_bundle = map_bundle
        self.timetable_bundle = timetable_bundle
        self.route_by_id = {str(route["id"]): route for route in map_bundle.get("serviceRoutes", []) if route.get("id")}
        self.station_group_by_id = {str(group["id"]): group for group in map_bundle.get("stationGroups", []) if group.get("id")}
        self.station_by_group_id: dict[str, dict[str, Any]] = {}
        self.physical_stations_by_group_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for station in map_bundle.get("physicalStations", []):
            station_group_id = str(station.get("stationGroupId") or "")
            if not station_group_id:
                continue
            self.physical_stations_by_group_id[station_group_id].append(station)
            self.station_by_group_id.setdefault(station_group_id, station)
        self.service_geometry_by_route_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for geometry in map_bundle.get("serviceGeometry", []):
            route_id = str(geometry.get("routeId") or "")
            if route_id:
                self.service_geometry_by_route_id[route_id].append(geometry)
        self.track_geometries_by_line_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for track in map_bundle.get("trackCenterlines", []):
            line_name = str(track.get("lineName") or "")
            if line_name and track.get("polyline"):
                self.track_geometries_by_line_name[line_name].append(track)

        self.route_station_set_by_id: dict[str, set[str]] = defaultdict(set)
        self.station_route_ids_by_group_id: dict[str, set[str]] = defaultdict(set)
        for pattern in map_bundle.get("servicePatterns", []):
            route_id = str(pattern.get("routeId") or "")
            if not route_id:
                continue
            for station_group_id in pattern.get("stationGroupIds", []):
                station_group_id = str(station_group_id or "")
                if not station_group_id:
                    continue
                self.route_station_set_by_id[route_id].add(station_group_id)
                self.station_route_ids_by_group_id[station_group_id].add(route_id)

        self.station_group_ids_by_transfer_key: dict[str, set[str]] = defaultdict(set)
        for station_group_id, group in self.station_group_by_id.items():
            key = self.transfer_key_for_group(station_group_id)
            if key:
                self.station_group_ids_by_transfer_key[key].add(station_group_id)

        self.route_distance_sq_cache: dict[tuple[str, str], float] = {}
        self.route_physical_serve_cache: dict[tuple[str, str], bool] = {}
        self.route_can_represent_cache: dict[tuple[str, int, str], bool] = {}
        self.boardable_route_ids_cache: dict[tuple[str, int, str], list[str]] = {}

        self.physical_route_ids_by_group_id: dict[str, set[str]] = defaultdict(set)
        for station_group_id, route_ids in self.station_route_ids_by_group_id.items():
            for route_id in route_ids:
                route = self.route_by_id.get(route_id)
                if not route:
                    continue
                pattern_serves = self.route_pattern_serves_boarding_station(route_id, station_group_id)
                geometry_serves = route.get("shortName") not in PHYSICAL_ALIAS_ROUTE_NAMES and self.route_physically_serves_station_group(route_id, station_group_id)
                if pattern_serves or geometry_serves:
                    self.physical_route_ids_by_group_id[station_group_id].add(route_id)

        self.trips = [self.normalize_trip_for_gameplay(trip) for trip in timetable_bundle.get("tripInstances", [])]

    def normalize_trip_for_gameplay(self, trip: dict[str, Any]) -> dict[str, Any]:
        route_id = str(trip.get("routeId") or "")
        if not self.is_circular_route(route_id):
            return trip
        stops = list(trip.get("stopTimes") or [])
        if len(stops) < 4:
            return trip
        first = stops[0]
        last = stops[-1]
        if first.get("stationGroupId") != last.get("stationGroupId"):
            return trip
        first_sec = first.get("departureTimeSec", first.get("arrivalTimeSec"))
        last_sec = last.get("arrivalTimeSec", last.get("departureTimeSec"))
        if not isinstance(first_sec, (int, float)) or not isinstance(last_sec, (int, float)) or last_sec <= first_sec:
            return trip
        loop_duration = int(last_sec - first_sec)
        max_sequence = max(int(stop.get("sequence") or 0) for stop in stops)
        extra_stops = []
        for index, stop in enumerate(stops[1:]):
            extra_stops.append(
                {
                    **stop,
                    "sequence": max_sequence + index + 1,
                    "arrivalTimeSec": (stop.get("arrivalTimeSec") + loop_duration) if isinstance(stop.get("arrivalTimeSec"), (int, float)) else stop.get("arrivalTimeSec"),
                    "departureTimeSec": (stop.get("departureTimeSec") + loop_duration) if isinstance(stop.get("departureTimeSec"), (int, float)) else stop.get("departureTimeSec"),
                }
            )
        return {**trip, "stopTimes": [*stops, *extra_stops], "circularExtended": True}

    def is_circular_route(self, route_id: str) -> bool:
        route = self.route_by_id.get(route_id)
        return str(route.get("shortName") or "") == "JR_YAMANOTE" if route else False

    def transfer_key_for_group(self, station_group_id: str) -> str:
        group = self.station_group_by_id.get(station_group_id)
        station = self.station_by_group_id.get(station_group_id)
        name = (
            (group or {}).get("names", {}).get("ja")
            or (group or {}).get("primaryName")
            or (station or {}).get("names", {}).get("ja")
            or (station or {}).get("name")
            or station_group_id
        )
        return normalized_transfer_station_name(name)

    def equivalent_station_group_ids(self, station_group_id: str) -> list[str]:
        if not station_group_id:
            return []
        key = self.transfer_key_for_group(station_group_id)
        ids = list(self.station_group_ids_by_transfer_key.get(key, set())) if key else []
        if station_group_id not in ids:
            ids.insert(0, station_group_id)
        return ids

    def route_track_line_aliases(self, route_id: str) -> list[str]:
        route = self.route_by_id.get(route_id)
        if not route:
            return []
        short_name = str(route.get("shortName") or "")
        operator_id = str(route.get("operatorId") or "")
        if operator_id == "keikyu":
            if short_name == "本線":
                return ["京急本線", "本線"]
            if short_name == "空港線":
                return ["空港線", "京急本線", "本線"]
            if short_name == "久里浜線":
                return ["久里浜線", "京急本線", "本線"]
            if short_name == "逗子線":
                return ["逗子線", "京急本線", "本線"]
            return [short_name]
        configured = ROUTE_TRACK_LINE_ALIASES.get(short_name)
        if configured:
            return list(configured)
        title = route_title(route)
        return [title] if title and title != "Unknown" else []

    def route_track_geometries(self, route_id: str) -> list[dict[str, Any]]:
        geometries: list[dict[str, Any]] = []
        for line_name in self.route_track_line_aliases(route_id):
            geometries.extend(self.track_geometries_by_line_name.get(line_name, []))
        return geometries

    def route_distance_sq_to_station(self, route_id: str, station: dict[str, Any]) -> float:
        station_id = str(station.get("id") or f"{station.get('lon')},{station.get('lat')}")
        cache_key = (route_id, station_id)
        if cache_key in self.route_distance_sq_cache:
            return self.route_distance_sq_cache[cache_key]
        if not isinstance(station.get("lon"), (int, float)) or not isinstance(station.get("lat"), (int, float)):
            return float("inf")
        coordinate = (station["lon"], station["lat"])
        distance = float("inf")
        for geometry in self.service_geometry_by_route_id.get(route_id, []):
            distance = min(distance, polyline_distance_sq_to_point(geometry.get("polyline") or [], coordinate))
        for geometry in self.route_track_geometries(route_id):
            distance = min(distance, polyline_distance_sq_to_point(geometry.get("polyline") or [], coordinate))
        self.route_distance_sq_cache[cache_key] = distance
        return distance

    def route_operator_matches_station(self, route: dict[str, Any] | None, station: dict[str, Any] | None) -> bool:
        route_operator = str((route or {}).get("operatorId") or "")
        station_operators = [str(item) for item in (station or {}).get("operatorIds") or [] if item]
        if not route_operator or not station_operators:
            return True
        alias_operators = PHYSICAL_ALIAS_STATION_OPERATORS.get(str((route or {}).get("shortName") or ""), [])
        if alias_operators:
            return any(alias in station_operators for alias in alias_operators)
        if route_operator in station_operators:
            return True
        if route_operator == "shinkansen":
            return any(operator_id.startswith("jr_") for operator_id in station_operators)
        if route_operator.startswith("jr_"):
            return route_operator in station_operators
        return False

    def route_physically_serves_station_group(self, route_id: str, station_group_id: str) -> bool:
        cache_key = (route_id, station_group_id)
        if cache_key in self.route_physical_serve_cache:
            return self.route_physical_serve_cache[cache_key]
        stations = self.physical_stations_by_group_id.get(station_group_id, [])
        if not stations:
            result = station_group_id in self.route_station_set_by_id.get(route_id, set())
            self.route_physical_serve_cache[cache_key] = result
            return result
        best = float("inf")
        for station in stations:
            best = min(best, self.route_distance_sq_to_station(route_id, station))
        result = best <= PHYSICAL_ROUTE_STATION_DISTANCE_SQ if best < float("inf") else False
        self.route_physical_serve_cache[cache_key] = result
        return result

    def is_through_service_transfer_alias(self, route_id: str) -> bool:
        route = self.route_by_id.get(route_id)
        if not route:
            return True
        short_name = str(route.get("shortName") or "")
        if short_name in PHYSICAL_ALIAS_ROUTE_NAMES:
            return False
        if route.get("operatorId") == "tokyo_metro" and short_name not in TOKYO_METRO_PHYSICAL_ROUTE_NAMES:
            return True
        return False

    def route_pattern_serves_boarding_station(self, route_id: str, station_group_id: str) -> bool:
        if not route_id or not station_group_id or self.is_through_service_transfer_alias(route_id):
            return False
        route = self.route_by_id.get(route_id)
        if not route or station_group_id not in self.route_station_set_by_id.get(route_id, set()):
            return False
        operator_id = str(route.get("operatorId") or "")
        if (
            operator_id != "shinkansen"
            and not operator_id.startswith("jr_")
            and operator_id != "tokyo_metro"
            and operator_id != "toei"
            and str(route.get("shortName") or "") not in PHYSICAL_ALIAS_ROUTE_NAMES
        ):
            return False
        stations = self.physical_stations_by_group_id.get(station_group_id, [])
        return (not stations) or any(self.route_operator_matches_station(route, station) for station in stations)

    def route_pattern_serves_planner_boarding_station(self, route_id: str, station_group_id: str) -> bool:
        if not route_id or not station_group_id or self.is_through_service_transfer_alias(route_id):
            return False
        route = self.route_by_id.get(route_id)
        if not route or station_group_id not in self.route_station_set_by_id.get(route_id, set()):
            return False
        stations = self.physical_stations_by_group_id.get(station_group_id, [])
        return (not stations) or any(self.route_operator_matches_station(route, station) for station in stations)

    def route_ids_for_station_and_transfers(self, station_group_id: str, physical_only: bool = False) -> set[str]:
        route_ids: set[str] = set()
        for group_id in self.equivalent_station_group_ids(station_group_id):
            source = self.physical_route_ids_by_group_id.get(group_id, set()) if physical_only else self.station_route_ids_by_group_id.get(group_id, set())
            route_ids.update(source)
        return route_ids

    def normalized_track_line_alias(self, value: Any) -> str:
        return str(value or "").strip().replace(" ", "").replace("　", "")

    def track_line_alias_tokens_for_route(self, route_id: str) -> set[str]:
        route = self.route_by_id.get(route_id)
        tokens: set[str] = set()

        def add_token(value: Any) -> None:
            normalized = self.normalized_track_line_alias(value)
            if not normalized:
                return
            tokens.add(normalized)
            without_prefix = normalized
            for prefix in TRACK_LINE_ALIAS_PREFIXES:
                if without_prefix.startswith(prefix):
                    without_prefix = without_prefix[len(prefix):]
                    break
            if without_prefix:
                tokens.add(without_prefix)

        for alias in self.route_track_line_aliases(route_id):
            add_token(alias)
        add_token((route or {}).get("shortName"))
        add_token(ROUTE_JA_LABELS.get(str((route or {}).get("shortName") or "")))
        return tokens

    def route_aliases_overlap(self, left_route_id: str, right_route_id: str) -> bool:
        left_aliases = self.track_line_alias_tokens_for_route(left_route_id)
        right_aliases = self.track_line_alias_tokens_for_route(right_route_id)
        return bool(left_aliases.intersection(right_aliases))

    def routes_share_boarding_operator(self, left_route_id: str, right_route_id: str) -> bool:
        left = self.route_by_id.get(left_route_id)
        right = self.route_by_id.get(right_route_id)
        if not left or not right:
            return False
        return str(left.get("operatorId") or "") == str(right.get("operatorId") or "")

    def can_borrow_trip_for_boarding_line(self, trip_route_id: str, selected_route_id: str) -> bool:
        if not trip_route_id or not selected_route_id or trip_route_id == selected_route_id:
            return False
        trip_route = self.route_by_id.get(trip_route_id)
        selected_route = self.route_by_id.get(selected_route_id)
        if not trip_route or not selected_route:
            return False
        same_operator = str(trip_route.get("operatorId") or "") == str(selected_route.get("operatorId") or "")
        involves_physical_alias = (
            str(trip_route.get("shortName") or "") in PHYSICAL_ALIAS_ROUTE_NAMES
            or str(selected_route.get("shortName") or "") in PHYSICAL_ALIAS_ROUTE_NAMES
        )
        if same_operator and str(trip_route.get("operatorId") or "") in {"jr_east", "tokyo_metro", "toei"} and not involves_physical_alias:
            return False
        return self.route_aliases_overlap(selected_route_id, trip_route_id)

    def has_downstream_stop(self, trip: dict[str, Any], board_stop: dict[str, Any]) -> bool:
        board_sequence = int(board_stop.get("sequence") or 0)
        return any(int(stop.get("sequence") or 0) > board_sequence for stop in (trip.get("stopTimes") or []))

    def next_stop_after(self, trip: dict[str, Any], board_stop: dict[str, Any]) -> dict[str, Any] | None:
        board_sequence = int(board_stop.get("sequence") or 0)
        for stop in trip.get("stopTimes") or []:
            if int(stop.get("sequence") or 0) > board_sequence:
                return stop
        return None

    def route_can_represent_trip_departure(self, trip: dict[str, Any], board_stop: dict[str, Any], route_id: str) -> bool:
        trip_id = str(trip.get("id") or "")
        sequence = int(board_stop.get("sequence") or 0)
        cache_key = (trip_id, sequence, route_id)
        if cache_key in self.route_can_represent_cache:
            return self.route_can_represent_cache[cache_key]
        trip_route_id = str(trip.get("routeId") or "")
        station_group_id = str(board_stop.get("stationGroupId") or "")
        if not trip_route_id or not station_group_id or not route_id:
            return False
        if self.is_through_service_transfer_alias(route_id):
            return False
        if not self.routes_share_boarding_operator(trip_route_id, route_id) and not self.route_aliases_overlap(trip_route_id, route_id):
            return False
        route = self.route_by_id.get(route_id)
        if not route:
            return False
        boarding_stations = self.physical_stations_by_group_id.get(station_group_id, [])
        operator_matches_boarding_station = (not boarding_stations) or any(self.route_operator_matches_station(route, station) for station in boarding_stations)
        next_stop = self.next_stop_after(trip, board_stop)
        result = False
        if route_id == trip_route_id:
            result = operator_matches_boarding_station and (
                self.route_physically_serves_station_group(route_id, station_group_id)
                or self.route_pattern_serves_planner_boarding_station(route_id, station_group_id)
            )
        elif (
            operator_matches_boarding_station
            and next_stop is not None
            and self.can_borrow_trip_for_boarding_line(trip_route_id, route_id)
            and self.route_pattern_serves_planner_boarding_station(route_id, station_group_id)
        ):
            result = self.route_pattern_serves_planner_boarding_station(route_id, str(next_stop.get("stationGroupId") or ""))
        self.route_can_represent_cache[cache_key] = result
        return result

    def boardable_route_ids_for_stop(self, trip: dict[str, Any], board_stop: dict[str, Any]) -> list[str]:
        trip_id = str(trip.get("id") or "")
        station_group_id = str(board_stop.get("stationGroupId") or "")
        sequence = int(board_stop.get("sequence") or 0)
        cache_key = (trip_id, sequence, station_group_id)
        if cache_key in self.boardable_route_ids_cache:
            return self.boardable_route_ids_cache[cache_key]
        route_ids: list[str] = []
        seen: set[str] = set()
        trip_route_id = str(trip.get("routeId") or "")
        physical_route_ids = sorted(self.route_ids_for_station_and_transfers(station_group_id, physical_only=True))
        if self.route_can_represent_trip_departure(trip, board_stop, trip_route_id):
            route_ids.append(trip_route_id)
            seen.add(trip_route_id)
        for route_id in physical_route_ids:
            if route_id in seen:
                continue
            if self.route_can_represent_trip_departure(trip, board_stop, route_id):
                route_ids.append(route_id)
                seen.add(route_id)
        if not route_ids and not physical_route_ids and not self.is_through_service_transfer_alias(trip_route_id):
            route_ids.append(trip_route_id)
        self.boardable_route_ids_cache[cache_key] = route_ids
        return route_ids

    def build_report(self, focus_operators: tuple[str, ...] = FOCUS_OPERATORS, sample_limit: int = 40) -> dict[str, Any]:
        pair_boardable_counts: Counter[tuple[str, str]] = Counter()
        pair_terminal_only_counts: Counter[tuple[str, str]] = Counter()
        pair_own_counts: Counter[tuple[str, str]] = Counter()
        pair_borrowed_counts: Counter[tuple[str, str]] = Counter()
        route_boardable_counts: Counter[str] = Counter()
        route_borrowed_counts: Counter[str] = Counter()
        route_own_counts: Counter[str] = Counter()
        route_forbidden_same_operator_borrow_counts: Counter[str] = Counter()
        operator_boardable_counts: Counter[str] = Counter()
        operator_borrowed_counts: Counter[str] = Counter()
        operator_own_counts: Counter[str] = Counter()
        operator_forbidden_same_operator_borrow_counts: Counter[str] = Counter()
        unsurfaced_by_operator: Counter[str] = Counter()
        unsurfaced_by_trip_route: Counter[str] = Counter()
        unsurfaced_by_station: Counter[str] = Counter()
        unsurfaced_by_trip_route_station: Counter[tuple[str, str]] = Counter()

        forbidden_borrow_samples: list[dict[str, Any]] = []
        unsurfaced_boardable_stop_samples: list[dict[str, Any]] = []
        unsurfaced_boardable_stop_count = 0

        for trip in self.trips:
            trip_route_id = str(trip.get("routeId") or "")
            trip_route = self.route_by_id.get(trip_route_id)
            trip_operator_id = str((trip_route or {}).get("operatorId") or "")
            for stop in trip.get("stopTimes") or []:
                station_group_id = str(stop.get("stationGroupId") or "")
                if not station_group_id:
                    continue
                equivalent_groups = self.equivalent_station_group_ids(station_group_id)
                if self.has_downstream_stop(trip, stop):
                    route_ids = self.boardable_route_ids_for_stop(trip, stop)
                    if not route_ids:
                        unsurfaced_boardable_stop_count += 1
                        unsurfaced_by_operator[trip_operator_id] += 1
                        unsurfaced_by_trip_route[trip_route_id] += 1
                        unsurfaced_by_station[station_group_id] += 1
                        unsurfaced_by_trip_route_station[(trip_route_id, station_group_id)] += 1
                        if len(unsurfaced_boardable_stop_samples) < sample_limit:
                            group = self.station_group_by_id.get(station_group_id)
                            station = self.station_by_group_id.get(station_group_id)
                            unsurfaced_boardable_stop_samples.append(
                                {
                                    "tripId": trip.get("id"),
                                    "tripRouteId": trip_route_id,
                                    "tripRoute": route_title(trip_route),
                                    "stationGroupId": station_group_id,
                                    "station": display_name_for_group(group, station),
                                    "sequence": stop.get("sequence"),
                                }
                            )
                        continue
                    for selected_group_id in equivalent_groups:
                        for route_id in route_ids:
                            pair_boardable_counts[(selected_group_id, route_id)] += 1
                            route_boardable_counts[route_id] += 1
                            route = self.route_by_id.get(route_id)
                            operator_id = str((route or {}).get("operatorId") or "")
                            operator_boardable_counts[operator_id] += 1
                            if route_id == trip_route_id:
                                pair_own_counts[(selected_group_id, route_id)] += 1
                                route_own_counts[route_id] += 1
                                operator_own_counts[operator_id] += 1
                            else:
                                pair_borrowed_counts[(selected_group_id, route_id)] += 1
                                route_borrowed_counts[route_id] += 1
                                operator_borrowed_counts[operator_id] += 1
                                same_operator = operator_id and operator_id == trip_operator_id
                                route_short_name = str((route or {}).get("shortName") or "")
                                trip_route_short_name = str((trip_route or {}).get("shortName") or "")
                                forbidden_same_operator_borrow = (
                                    same_operator
                                    and operator_id in {"jr_east", "tokyo_metro", "toei"}
                                    and route_short_name not in PHYSICAL_ALIAS_ROUTE_NAMES
                                    and trip_route_short_name not in PHYSICAL_ALIAS_ROUTE_NAMES
                                )
                                if forbidden_same_operator_borrow:
                                    route_forbidden_same_operator_borrow_counts[route_id] += 1
                                    operator_forbidden_same_operator_borrow_counts[operator_id] += 1
                                    if len(forbidden_borrow_samples) < sample_limit:
                                        group = self.station_group_by_id.get(selected_group_id)
                                        station = self.station_by_group_id.get(selected_group_id)
                                        forbidden_borrow_samples.append(
                                            {
                                                "selectedStationGroupId": selected_group_id,
                                                "selectedStation": display_name_for_group(group, station),
                                                "selectedRouteId": route_id,
                                                "selectedRoute": route_title(route),
                                                "tripId": trip.get("id"),
                                                "tripRouteId": trip_route_id,
                                                "tripRoute": route_title(trip_route),
                                                "tripOperatorId": trip_operator_id,
                                            }
                                        )
                else:
                    for selected_group_id in equivalent_groups:
                        pair_terminal_only_counts[(selected_group_id, trip_route_id)] += 1

        route_reports = []
        no_boardable_pair_samples = []
        terminal_only_pair_samples = []
        invisible_pair_samples = []
        for station_group_id, visible_route_ids in self.physical_route_ids_by_group_id.items():
            # no-op placeholder: physical-only per direct group is still useful through equivalent groups below
            if not visible_route_ids:
                continue

        all_selected_groups = sorted(self.station_group_by_id)
        for station_group_id in all_selected_groups:
            visible_route_ids = sorted(self.route_ids_for_station_and_transfers(station_group_id, physical_only=True))
            if not visible_route_ids:
                continue
            group = self.station_group_by_id.get(station_group_id)
            station = self.station_by_group_id.get(station_group_id)
            for route_id in visible_route_ids:
                route = self.route_by_id.get(route_id)
                pair_key = (station_group_id, route_id)
                boardable_count = pair_boardable_counts[pair_key]
                terminal_count = pair_terminal_only_counts[pair_key]
                own_count = pair_own_counts[pair_key]
                borrowed_count = pair_borrowed_counts[pair_key]
                route_reports.append(
                    {
                        "stationGroupId": station_group_id,
                        "station": display_name_for_group(group, station),
                        "routeId": route_id,
                        "route": route_title(route),
                        "operatorId": (route or {}).get("operatorId"),
                        "boardableCount": boardable_count,
                        "ownBoardableCount": own_count,
                        "borrowedBoardableCount": borrowed_count,
                        "terminalOnlyCount": terminal_count,
                    }
                )
                if boardable_count:
                    continue
                sample = {
                    "stationGroupId": station_group_id,
                    "station": display_name_for_group(group, station),
                    "routeId": route_id,
                    "route": route_title(route),
                    "operatorId": (route or {}).get("operatorId"),
                    "terminalOnlyCount": terminal_count,
                }
                if terminal_count:
                    if len(terminal_only_pair_samples) < sample_limit:
                        terminal_only_pair_samples.append(sample)
                else:
                    if len(no_boardable_pair_samples) < sample_limit:
                        no_boardable_pair_samples.append(sample)
                    if len(invisible_pair_samples) < sample_limit:
                        invisible_pair_samples.append(sample)

        operator_reports = []
        for operator_id in sorted({str(route.get("operatorId") or "") for route in self.route_by_id.values()}):
            route_ids = [route_id for route_id, route in self.route_by_id.items() if str(route.get("operatorId") or "") == operator_id]
            if not route_ids:
                continue
            visible_pairs = sum(1 for report in route_reports if report["operatorId"] == operator_id)
            boardable_pairs = sum(1 for report in route_reports if report["operatorId"] == operator_id and report["boardableCount"] > 0)
            terminal_only_pairs = sum(1 for report in route_reports if report["operatorId"] == operator_id and report["boardableCount"] == 0 and report["terminalOnlyCount"] > 0)
            no_boardable_pairs = sum(1 for report in route_reports if report["operatorId"] == operator_id and report["boardableCount"] == 0 and report["terminalOnlyCount"] == 0)
            operator_reports.append(
                {
                    "operatorId": operator_id,
                    "routeCount": len(route_ids),
                    "visibleStationRoutePairCount": visible_pairs,
                    "boardableStationRoutePairCount": boardable_pairs,
                    "terminalOnlyStationRoutePairCount": terminal_only_pairs,
                    "noBoardableStationRoutePairCount": no_boardable_pairs,
                    "boardableDepartureCount": operator_boardable_counts[operator_id],
                    "ownBoardableDepartureCount": operator_own_counts[operator_id],
                    "borrowedBoardableDepartureCount": operator_borrowed_counts[operator_id],
                    "forbiddenSameOperatorBorrowCount": operator_forbidden_same_operator_borrow_counts[operator_id],
                }
            )

        no_boardable_by_operator: Counter[str] = Counter()
        no_boardable_by_route: Counter[str] = Counter()
        terminal_only_by_operator: Counter[str] = Counter()
        terminal_only_by_route: Counter[str] = Counter()
        for report in route_reports:
            operator_id = str(report.get("operatorId") or "")
            route_id = str(report.get("routeId") or "")
            if report["boardableCount"] == 0 and report["terminalOnlyCount"] > 0:
                terminal_only_by_operator[operator_id] += 1
                terminal_only_by_route[route_id] += 1
            elif report["boardableCount"] == 0:
                no_boardable_by_operator[operator_id] += 1
                no_boardable_by_route[route_id] += 1

        focus_route_reports = [
            report
            for report in route_reports
            if report["operatorId"] in set(focus_operators)
        ]
        focus_route_reports.sort(
            key=lambda report: (
                report["operatorId"],
                report["boardableCount"] == 0,
                report["station"],
                report["route"],
            )
        )

        summary = {
            "station_group_count": len(self.station_group_by_id),
            "route_count": len(self.route_by_id),
            "trip_count": len(self.trips),
            "visible_station_route_pair_count": len(route_reports),
            "boardable_station_route_pair_count": sum(1 for report in route_reports if report["boardableCount"] > 0),
            "terminal_only_station_route_pair_count": sum(1 for report in route_reports if report["boardableCount"] == 0 and report["terminalOnlyCount"] > 0),
            "no_boardable_station_route_pair_count": sum(1 for report in route_reports if report["boardableCount"] == 0 and report["terminalOnlyCount"] == 0),
            "boardable_departure_count": int(sum(pair_boardable_counts.values())),
            "borrowed_departure_count": int(sum(pair_borrowed_counts.values())),
            "forbidden_same_operator_borrow_count": int(sum(route_forbidden_same_operator_borrow_counts.values())),
            "unsurfaced_boardable_trip_stop_count": unsurfaced_boardable_stop_count,
        }

        def route_row(route_id: str, count: int, field_name: str = "routeId") -> dict[str, Any]:
            route = self.route_by_id.get(route_id)
            return {
                field_name: route_id,
                "route": route_title(route),
                "operatorId": (route or {}).get("operatorId"),
                "count": count,
            }

        def station_row(station_group_id: str, count: int) -> dict[str, Any]:
            group = self.station_group_by_id.get(station_group_id)
            station = self.station_by_group_id.get(station_group_id)
            return {
                "stationGroupId": station_group_id,
                "station": display_name_for_group(group, station),
                "count": count,
            }

        aggregates = {
            "unsurfacedBoardableTripStopsByOperator": [
                {"operatorId": operator_id, "count": count}
                for operator_id, count in top_counter_items(unsurfaced_by_operator, sample_limit)
            ],
            "unsurfacedBoardableTripStopsByTripRoute": [
                route_row(route_id, count, "tripRouteId")
                for route_id, count in top_counter_items(unsurfaced_by_trip_route, sample_limit)
            ],
            "unsurfacedBoardableTripStopsByStation": [
                station_row(station_group_id, count)
                for station_group_id, count in top_counter_items(unsurfaced_by_station, sample_limit)
            ],
            "unsurfacedBoardableTripStopsByTripRouteStation": [
                {
                    **route_row(route_id, count, "tripRouteId"),
                    **station_row(station_group_id, count),
                }
                for (route_id, station_group_id), count in top_counter_items(unsurfaced_by_trip_route_station, sample_limit)
            ],
            "noBoardableStationRoutePairsByOperator": [
                {"operatorId": operator_id, "count": count}
                for operator_id, count in top_counter_items(no_boardable_by_operator, sample_limit)
            ],
            "noBoardableStationRoutePairsByRoute": [
                route_row(route_id, count)
                for route_id, count in top_counter_items(no_boardable_by_route, sample_limit)
            ],
            "terminalOnlyStationRoutePairsByOperator": [
                {"operatorId": operator_id, "count": count}
                for operator_id, count in top_counter_items(terminal_only_by_operator, sample_limit)
            ],
            "terminalOnlyStationRoutePairsByRoute": [
                route_row(route_id, count)
                for route_id, count in top_counter_items(terminal_only_by_route, sample_limit)
            ],
        }

        return {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "source": {
                "map_bundle": str(MAP_BUNDLE_PATH.relative_to(ROOT)),
                "timetable_bundle": str(TIMETABLE_BUNDLE_PATH.relative_to(ROOT)),
            },
            "summary": summary,
            "aggregates": aggregates,
            "focusOperators": list(focus_operators),
            "operatorReports": operator_reports,
            "samples": {
                "forbiddenSameOperatorBorrow": forbidden_borrow_samples,
                "unsurfacedBoardableTripStops": unsurfaced_boardable_stop_samples,
                "terminalOnlyStationRoutePairs": terminal_only_pair_samples,
                "noBoardableStationRoutePairs": no_boardable_pair_samples,
                "focusOperatorRouteReports": focus_route_reports[:sample_limit],
            },
        }


def build_audit(focus_operators: tuple[str, ...] = FOCUS_OPERATORS) -> dict[str, Any]:
    map_bundle = load_json(MAP_BUNDLE_PATH)
    timetable_bundle = load_json(TIMETABLE_BUNDLE_PATH)
    return PlannerDepartureAudit(map_bundle, timetable_bundle).build_report(focus_operators=focus_operators)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit planner-facing line -> train departure visibility for v3 Tokyo.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--focus-operator", action="append", dest="focus_operators", default=[])
    args = parser.parse_args()
    focus = tuple(args.focus_operators) if args.focus_operators else FOCUS_OPERATORS
    report = build_audit(focus)
    write_json(args.output, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
