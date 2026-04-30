#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_v4_maplibre_sources import v3_label_rank_for_group
from v4_visual_identity import color_for_operator, color_for_operator_line


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_INPUT = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_TRAINS_INPUT = ROOT / "data" / "v4_current_weekday_train_instances.json.gz"
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_DOCS_DATA_DIR = ROOT / "docs" / "data"


MAJOR_STATION_FALLBACKS = {
    "runner": ["東京", "新宿", "大阪", "札幌"],
    "hunter": ["新宿", "大阪", "新大阪", "横浜"],
}

SYNTHETIC_LINE_NAME_OVERRIDES = {
    "JR_EAST_CHUO_RAPID": "中央線",
    "JR_EAST_CHUO_SOBU_LOCAL": "中央線",
    "JR_EAST_KEIHIN_TOHOKU_NEGISHI": "京浜東北線",
    "JR_EAST_KEIYO_MUSASHINO": "京葉線",
    "JR_EAST_SAIKYO_KAWAGOE": "埼京線",
    "JR_EAST_SHONAN_SHINJUKU": "湘南新宿ライン",
    "JR_EAST_SOBU_RAPID": "総武線",
    "JR_EAST_TOKAIDO": "東海道線",
    "JR_EAST_UENO_TOKYO": "上野東京ライン",
    "JR_EAST_YOKOSUKA": "横須賀線",
    "JR_JOBAN": "常磐線",
    "JR_EAST_JOBAN_RAPID": "常磐線",
    "JR_KAWAGOE": "川越線",
    "JR_NARITA": "成田線",
    "JR_OME": "青梅線",
    "JR_UCHIBO": "内房線",
    "JR_SOTOBO": "外房線",
    "JR_TOGANE": "東金線",
    "JR_KASHIMA": "鹿島線",
    "JR_ITO": "伊東線",
    "JR_JOETSU_LOCAL": "上越線",
    "JR_RYOMO": "両毛線",
    "JR_TOHOKU": "東北線",
    "JR_YAMANOTE": "山手線",
    "RINKAI": "りんかい線",
}

PUBLIC_LINE_NAME_OVERRIDES = {
    ("横浜市", "1号線"): "横浜市営地下鉄ブルーライン",
    ("横浜市", "3号線"): "横浜市営地下鉄ブルーライン",
    ("横浜市", "4号線"): "横浜市営地下鉄グリーンライン",
}


def load_json(path: Path) -> dict[str, Any]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    else:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stable_hash(value: str, length: int = 14) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length].upper()


def route_id_for(operator_id: str, line_name: str) -> str:
    return f"V4_ROUTE_{stable_hash(f'{operator_id}|{line_name}')}"


def pattern_id_for(route_id: str) -> str:
    return f"V4_PATTERN_{route_id.removeprefix('V4_ROUTE_')}"


def polyline_from_points(points: list[list[float]]) -> list[dict[str, float]]:
    polyline = []
    for point in points or []:
        if len(point) < 2:
            continue
        lon, lat = point[0], point[1]
        if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
            polyline.append({"lon": lon, "lat": lat})
    return polyline


def parse_hhmm_minutes(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    hour_text, minute_text = value.split(":", 1)
    try:
        return int(hour_text) * 60 + int(minute_text)
    except ValueError:
        return None


def normalize_trip_stop_times(
    raw_stops: list[dict[str, Any]],
    valid_station_group_ids: set[str],
    physical_station_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized = []
    previous_minute: int | None = None
    day_offset = 0
    for index, stop in enumerate(sorted(raw_stops or [], key=lambda item: item.get("sequence", 0))):
        station_group_id = stop.get("station_group_id") or stop.get("station_id")
        if not station_group_id or station_group_id not in valid_station_group_ids:
            continue
        arrival = parse_hhmm_minutes(stop.get("arrival_hhmm"))
        departure = parse_hhmm_minutes(stop.get("departure_hhmm"))
        if arrival is None and departure is None:
            continue
        if arrival is None:
            arrival = departure
        if departure is None:
            departure = arrival
        assert arrival is not None and departure is not None
        if departure < arrival:
            departure += 24 * 60
        candidate = arrival + day_offset
        if previous_minute is not None:
            while candidate + 3 * 60 < previous_minute:
                day_offset += 24 * 60
                candidate = arrival + day_offset
        arrival += day_offset
        departure += day_offset
        if previous_minute is not None and arrival < previous_minute:
            arrival = previous_minute
            if departure < arrival:
                departure = arrival
        previous_minute = departure
        physical_station = physical_station_by_id.get(stop.get("physical_station_id") or stop.get("physicalStationId") or "")
        normalized.append(
            {
                "sequence": len(normalized) + 1,
                "sourceSequence": int(stop.get("sequence") or index + 1),
                "stationGroupId": station_group_id,
                "arrivalTimeSec": arrival * 60,
                "departureTimeSec": departure * 60,
                "physicalStationId": stop.get("physical_station_id"),
                "sourceLineId": stop.get("line_id"),
                "sourceLineName": physical_station.get("lineName") if physical_station else stop.get("line_name"),
                "sourceOperatorName": physical_station.get("operatorName") if physical_station else stop.get("operator_name"),
            }
        )
    return normalized


def collapse_consecutive_duplicate_stops(stop_times: list[dict[str, Any]]) -> list[dict[str, Any]]:
    collapsed: list[dict[str, Any]] = []
    for stop in stop_times:
        if collapsed and collapsed[-1]["stationGroupId"] == stop["stationGroupId"]:
            previous = collapsed[-1]
            previous["departureTimeSec"] = max(previous.get("departureTimeSec") or 0, stop.get("departureTimeSec") or 0)
            previous["arrivalTimeSec"] = min(previous.get("arrivalTimeSec") or previous["departureTimeSec"], stop.get("arrivalTimeSec") or stop.get("departureTimeSec") or previous["arrivalTimeSec"])
            previous["sourceSequence"] = stop.get("sourceSequence") or previous.get("sourceSequence")
            previous["physicalStationId"] = stop.get("physicalStationId") or previous.get("physicalStationId")
            previous["sourceLineId"] = stop.get("sourceLineId") or previous.get("sourceLineId")
            previous["sourceLineName"] = stop.get("sourceLineName") or previous.get("sourceLineName")
            previous["sourceOperatorName"] = stop.get("sourceOperatorName") or previous.get("sourceOperatorName")
            continue
        collapsed.append(dict(stop))
    for sequence, stop in enumerate(collapsed, start=1):
        stop["sequence"] = sequence
    return collapsed


def public_service_name_for_train(train: dict[str, Any], line_name: str) -> str:
    service_detail = str(train.get("service_name_detail") or "").strip()
    train_type = str(train.get("train_type") or "").strip()
    service_name = str(train.get("service_name") or "").strip()
    display_name = str(train.get("display_name") or "").strip()
    route_name = str(train.get("route_name") or "").strip()
    operator_id = str(train.get("operator_id") or "").strip()
    operator_name = str(train.get("operator_name") or "").strip()
    original_line_name = str(train.get("line_name") or "").strip()
    public_line_name = PUBLIC_LINE_NAME_OVERRIDES.get((operator_name or operator_id, original_line_name), line_name)
    stop_names = [
        str(stop.get("station_name_raw") or stop.get("station_name") or "")
        for stop in train.get("stop_times") or []
    ]
    if operator_id == "shinkansen" or original_line_name.startswith("SHINKANSEN_"):
        return service_name or train_type or public_line_name
    if route_name and "・" in route_name and ("号" in route_name or "寝台特急" in route_name):
        return route_name.replace("寝台特急 ", "")
    if service_detail and train_type == "特急":
        return service_detail
    if display_name and train_type == "特急":
        return display_name
    if train_type == "特急":
        return service_name or train_type or public_line_name
    if train_type in {"関空快速", "紀州路快速"}:
        return train_type
    if (
        operator_name == "西日本旅客鉄道"
        and train_type == "快速"
        and original_line_name in {"阪和線", "紀勢線"}
        and "日根野" in stop_names
        and "和歌山" in stop_names
    ):
        return "紀州路快速"
    if service_name and service_name != original_line_name and re.search(r"(?:はこね|えのしま|リバティ|けごん|きぬ|会津|りょうもう|スペーシア|サンライズ|踊り子|ひだ)\d*号?", service_name):
        return service_name
    return public_line_name


def operator_maps(physical_map: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    id_to_name: dict[str, str] = {}
    name_to_id: dict[str, str] = {}
    for operator in physical_map.get("operators", []):
        operator_id = operator.get("operatorId")
        name = operator.get("nameJa")
        if not operator_id:
            continue
        id_to_name[operator_id] = name or operator_id
        if name:
            name_to_id.setdefault(name, operator_id)
    return id_to_name, name_to_id


def resolve_operator_id(
    raw_operator_id: str | None,
    raw_operator_name: str | None,
    name_to_id: dict[str, str],
    id_to_name: dict[str, str],
) -> str:
    if raw_operator_id is not None:
        raw_operator_id = str(raw_operator_id)
    if raw_operator_name is not None:
        raw_operator_name = str(raw_operator_name)
    if raw_operator_id and raw_operator_id in id_to_name:
        return raw_operator_id
    if raw_operator_name and raw_operator_name in name_to_id:
        return name_to_id[raw_operator_name]
    if raw_operator_id and raw_operator_id not in {"", "unknown_operator"}:
        return raw_operator_id
    return raw_operator_name or raw_operator_id or "unknown_operator"


def is_synthetic_line_name(line_name: str | None) -> bool:
    value = str(line_name or "")
    return value.startswith(("JR_", "SHINKANSEN_", "TOEI_", "TOKYO_", "YURIKAMOME"))


def canonical_line_name(line_name: str | None) -> str:
    value = str(line_name or "").strip()
    return SYNTHETIC_LINE_NAME_OVERRIDES.get(value, value)


def line_names_match(left: str | None, right: str | None) -> bool:
    left_value = canonical_line_name(left).replace(" ", "")
    right_value = canonical_line_name(right).replace(" ", "")
    if not left_value or not right_value:
        return False
    return left_value == right_value or left_value.endswith(right_value) or right_value.endswith(left_value)


def physical_route_key_for_stop(
    stop: dict[str, Any],
    train: dict[str, Any],
    physical_station_by_id: dict[str, dict[str, Any]],
    name_to_id: dict[str, str],
    id_to_name: dict[str, str],
) -> tuple[str, str] | None:
    physical_station = physical_station_by_id.get(stop.get("physical_station_id") or stop.get("physicalStationId") or "")
    if physical_station and physical_station.get("lineName"):
        return (
            resolve_operator_id(
                physical_station.get("operatorId"),
                physical_station.get("operatorName"),
                name_to_id,
                id_to_name,
            ),
            physical_station.get("lineName") or "未設定路線",
        )
    physical_line_name = stop.get("physical_line_name")
    if physical_line_name:
        return (
            resolve_operator_id(
                None if stop.get("physical_operator_name") else train.get("operator_id"),
                stop.get("physical_operator_name") or stop.get("operator_name") or train.get("operator_name"),
                name_to_id,
                id_to_name,
            ),
            SYNTHETIC_LINE_NAME_OVERRIDES.get(physical_line_name, physical_line_name),
        )
    return None


def trace_route_key_for_stop(
    stop: dict[str, Any],
    train: dict[str, Any],
    physical_station_by_id: dict[str, dict[str, Any]],
    name_to_id: dict[str, str],
    id_to_name: dict[str, str],
) -> tuple[str, str] | None:
    raw_line_name = canonical_line_name(stop.get("line_name"))
    raw_operator_id = resolve_operator_id(
        train.get("operator_id"),
        train.get("operator_name") or stop.get("operator_name"),
        name_to_id,
        id_to_name,
    )
    physical_key = physical_route_key_for_stop(stop, train, physical_station_by_id, name_to_id, id_to_name)
    if raw_line_name and (is_synthetic_line_name(stop.get("line_name")) or is_synthetic_line_name(train.get("line_name"))):
        return (
            raw_operator_id,
            raw_line_name,
        )
    if raw_line_name and physical_key and "新幹線" in physical_key[1] and "新幹線" not in raw_line_name:
        return (raw_operator_id, raw_line_name)
    if raw_line_name and physical_key and line_names_match(physical_key[1], raw_line_name):
        return physical_key
    if physical_key:
        return physical_key
    if raw_line_name:
        return (raw_operator_id, raw_line_name)
    return None


def ensure_route_export(
    routes_by_id: dict[str, dict[str, Any]],
    operator_id: str,
    line_name: str,
    operator_name: str,
    color: str | None = None,
    source: str = "v4_timetable",
) -> None:
    route_id = route_id_for(operator_id, line_name)
    routes_by_id.setdefault(
        route_id,
        {
            "id": route_id,
            "operatorId": operator_id,
            "operatorName": operator_name or operator_id,
            "shortName": line_name,
            "longName": f"{operator_name or operator_id} {line_name}",
            "color": color or color_for_operator_line(operator_id, line_name),
            "textColor": "#102033",
            "mode": "shinkansen" if "新幹線" in line_name or str(line_name).startswith("SHINKANSEN_") else "rail",
            "tags": {"source": source, "sourceOperatorId": operator_id, "lineName": line_name},
        },
    )


def route_key_for_train(
    train: dict[str, Any],
    name_to_id: dict[str, str],
    id_to_name: dict[str, str],
    physical_station_by_id: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    raw_operator_id = resolve_operator_id(train.get("operator_id"), train.get("operator_name"), name_to_id, id_to_name)
    original_line_name = train.get("line_name") or (train.get("stop_times") or [{}])[0].get("line_name") or "未設定路線"
    raw_line_was_synthetic = is_synthetic_line_name(original_line_name)
    raw_line_name = canonical_line_name(original_line_name)
    physical_counts: dict[tuple[str, str], int] = defaultdict(int)
    physical_operator_counts: dict[str, int] = defaultdict(int)
    for stop in train.get("stop_times") or []:
        physical_key = physical_route_key_for_stop(stop, train, physical_station_by_id, name_to_id, id_to_name)
        if not physical_key:
            continue
        physical_counts[physical_key] += 1
        physical_operator_counts[physical_key[0]] += 1
    if physical_counts:
        dominant_key, dominant_count = max(physical_counts.items(), key=lambda item: item[1])
        stop_count = max(1, len(train.get("stop_times") or []))
        raw_key = (raw_operator_id, raw_line_name)
        if raw_line_was_synthetic and str(original_line_name).startswith("SHINKANSEN_"):
            return raw_key
        if raw_key not in physical_counts and dominant_count >= 2:
            return dominant_key
        if raw_line_was_synthetic and dominant_count >= 2:
            return dominant_key
        if raw_operator_id in {"", "unknown_operator"} and dominant_count >= 3 and dominant_count / stop_count >= 0.55:
            return dominant_key
        dominant_operator_id, dominant_operator_count = max(physical_operator_counts.items(), key=lambda item: item[1])
        if raw_operator_id in {"", "unknown_operator"} and dominant_operator_count / stop_count >= 0.55:
            operator_lines = {
                key: count
                for key, count in physical_counts.items()
                if key[0] == dominant_operator_id
            }
            return max(operator_lines.items(), key=lambda item: item[1])[0]
    return raw_operator_id, raw_line_name


def build_line_trace(
    raw_stops: list[dict[str, Any]],
    normalized_stops: list[dict[str, Any]],
    train: dict[str, Any],
    physical_station_by_id: dict[str, dict[str, Any]],
    name_to_id: dict[str, str],
    id_to_name: dict[str, str],
    fallback_operator_id: str,
    fallback_line_name: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_by_group_sequence: dict[tuple[str, int], dict[str, Any]] = {}
    raw_by_source_sequence: dict[int, dict[str, Any]] = {}
    raw_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw_stop in sorted(raw_stops or [], key=lambda item: item.get("sequence", 0)):
        station_group_id = raw_stop.get("station_group_id") or raw_stop.get("station_id")
        if not station_group_id:
            continue
        sequence = int(raw_stop.get("sequence") or len(raw_by_group[station_group_id]) + 1)
        raw_by_group_sequence[(station_group_id, sequence)] = raw_stop
        raw_by_source_sequence[sequence] = raw_stop
        raw_by_group[station_group_id].append(raw_stop)

    stop_keys: list[tuple[str, str]] = []
    group_seen: dict[str, int] = defaultdict(int)
    fallback_key = (fallback_operator_id, fallback_line_name)
    for normalized_stop in normalized_stops:
        station_group_id = normalized_stop["stationGroupId"]
        group_seen[station_group_id] += 1
        raw_stop = raw_by_source_sequence.get(int(normalized_stop.get("sourceSequence") or 0))
        if raw_stop is None:
            raw_stop = raw_by_group_sequence.get((station_group_id, group_seen[station_group_id]))
        if raw_stop is None and raw_by_group.get(station_group_id):
            raw_stop = raw_by_group[station_group_id].pop(0)
        key = trace_route_key_for_stop(raw_stop or {}, train, physical_station_by_id, name_to_id, id_to_name) or fallback_key
        stop_keys.append(key)

    line_trace: list[dict[str, Any]] = []
    if len(normalized_stops) < 2:
        return line_trace, []

    segment_keys: list[tuple[str, str]] = []
    for index in range(len(normalized_stops) - 1):
        segment_key = stop_keys[index] if index < len(stop_keys) else fallback_key
        previous_key = stop_keys[index - 1] if index > 0 and index - 1 < len(stop_keys) else None
        next_key = stop_keys[index + 1] if index + 1 < len(stop_keys) else None
        if previous_key and next_key and previous_key == next_key and segment_key != previous_key:
            segment_key = next_key
        segment_keys.append(segment_key)
    for index in range(1, len(segment_keys) - 1):
        if segment_keys[index - 1] == segment_keys[index + 1] and segment_keys[index] != segment_keys[index - 1]:
            segment_keys[index] = segment_keys[index - 1]

    current_key: tuple[str, str] | None = None
    current_start_index = 0
    for index, segment_key in enumerate(segment_keys):
        if not segment_key[0] or not segment_key[1]:
            segment_key = fallback_key
        if current_key is None:
            current_key = segment_key
            current_start_index = index
            continue
        if segment_key == current_key:
            continue
        line_trace.append(
            line_trace_entry(current_key, normalized_stops, current_start_index, index - 1, id_to_name)
        )
        current_key = segment_key
        current_start_index = index
    if current_key is not None:
        line_trace.append(
            line_trace_entry(current_key, normalized_stops, current_start_index, len(normalized_stops) - 2, id_to_name)
        )

    seen_lines: set[str] = set()
    line_sequence = []
    for entry in line_trace:
        route_id = entry["routeId"]
        if route_id in seen_lines:
            continue
        seen_lines.add(route_id)
        line_sequence.append(
            {
                "operatorId": entry["operatorId"],
                "operatorName": entry["operatorName"],
                "lineName": entry["lineName"],
                "routeId": route_id,
            }
        )
    return line_trace, line_sequence


def route_id_for_trip_segment(trip_line_trace: list[dict[str, Any]], current_stop: dict[str, Any], next_stop: dict[str, Any]) -> str:
    current_sequence = current_stop["sequence"]
    next_sequence = next_stop["sequence"]
    exact = [
        trace["routeId"]
        for trace in trip_line_trace
        if trace.get("routeId") and current_sequence >= trace["fromSequence"] and next_sequence <= trace["toSequence"]
    ]
    if len(exact) == 1:
        return exact[0]
    boundary = [
        trace["routeId"]
        for trace in trip_line_trace
        if trace.get("routeId") and current_sequence >= trace["fromSequence"] and current_sequence < trace["toSequence"]
    ]
    return boundary[0] if len(boundary) == 1 else ""


def attach_stop_route_identity(stop_times: list[dict[str, Any]], line_trace: list[dict[str, Any]], trip_route_id: str) -> None:
    for index, stop in enumerate(stop_times):
        previous_stop = stop_times[index - 1] if index > 0 else None
        next_stop = stop_times[index + 1] if index + 1 < len(stop_times) else None
        incoming_route_id = route_id_for_trip_segment(line_trace, previous_stop, stop) if previous_stop else ""
        outgoing_route_id = route_id_for_trip_segment(line_trace, stop, next_stop) if next_stop else ""
        stop["incomingRouteId"] = incoming_route_id
        stop["outgoingRouteId"] = outgoing_route_id
        stop["displayRouteId"] = outgoing_route_id or incoming_route_id or trip_route_id


def should_skip_mislabeled_foreign_train(train: dict[str, Any]) -> bool:
    operator_id = str(train.get("operator_id") or "").strip()
    operator_name = str(train.get("operator_name") or "").strip()
    line_name = str(train.get("line_name") or "").strip()
    service_name = str(train.get("service_name") or train.get("display_name") or "").strip()
    stop_names = {
        str(stop.get("station_name_raw") or stop.get("station_name") or "").strip()
        for stop in train.get("stop_times") or []
    }
    return (
        (operator_id == "tobu" or operator_name == "東武")
        and line_name == "東上本線"
        and (service_name.startswith("ＪＲ") or "大宮" in stop_names)
    )


def line_trace_entry(
    key: tuple[str, str],
    normalized_stops: list[dict[str, Any]],
    start_segment_index: int,
    end_segment_index: int,
    id_to_name: dict[str, str],
) -> dict[str, Any]:
    operator_id, line_name = key
    from_stop = normalized_stops[start_segment_index]
    to_stop = normalized_stops[end_segment_index + 1]
    return {
        "fromSequence": from_stop["sequence"],
        "toSequence": to_stop["sequence"],
        "fromStationGroupId": from_stop["stationGroupId"],
        "toStationGroupId": to_stop["stationGroupId"],
        "operatorId": operator_id,
        "operatorName": id_to_name.get(operator_id, operator_id),
        "lineName": line_name,
        "routeId": route_id_for(operator_id, line_name),
    }


def choose_default_group(station_groups: list[dict[str, Any]], names: list[str], fallback_index: int = 0) -> str:
    by_name = defaultdict(list)
    for group in station_groups:
        by_name[group.get("nameJa")].append(group)
    for name in names:
        candidates = by_name.get(name) or []
        if candidates:
            candidates.sort(
                key=lambda group: (
                    -int(group.get("physicalStationCount", 0)),
                    -len(group.get("operatorIds", [])),
                    group.get("id", ""),
                )
            )
            return candidates[0]["id"]
    if not station_groups:
        raise ValueError("No station groups available")
    return sorted(station_groups, key=lambda group: group.get("id", ""))[fallback_index]["id"]


def build_physical_station_exports(physical_map: dict[str, Any]) -> list[dict[str, Any]]:
    stations = []
    for station in physical_map.get("physicalStations", []):
        stations.append(
            {
                "id": station["id"],
                "name": station.get("nameJa") or station["id"],
                "names": {
                    "ja": station.get("nameJa") or station["id"],
                    "en": station.get("nameJa") or station["id"],
                },
                "operatorIds": [station.get("operatorId") or "unknown_operator"],
                "lat": station.get("lat"),
                "lon": station.get("lon"),
                "sourceStopIds": [value for value in [station.get("sourceStationCode")] if value],
                "stationGroupId": station.get("stationGroupId"),
                "tags": {
                    "operatorName": station.get("operatorName"),
                    "lineName": station.get("lineName"),
                    "prefectureNameJa": station.get("prefectureNameJa"),
                    "prefectureNameEn": station.get("prefectureNameEn"),
                    "locationNote": station.get("locationNote"),
                    "identityVersion": station.get("identityVersion"),
                },
            }
        )
    return stations


def build_station_group_exports(physical_map: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    station_groups = []
    labels = []
    for group in physical_map.get("stationGroups", []):
        name = group.get("nameJa") or group["id"]
        rank = v3_label_rank_for_group(group)
        centroid = group.get("centroid") or {}
        station_groups.append(
            {
                "id": group["id"],
                "primaryName": name,
                "names": {"ja": name, "en": name},
                "physicalStationIds": group.get("physicalStationIds", []),
                "centroid": {"lat": centroid.get("lat"), "lon": centroid.get("lon")},
                "category": "hub" if rank >= 90 else "normal",
                "labelRank": rank,
                "tags": {
                    "nameKeys": group.get("nameKeys", []),
                    "operatorIds": group.get("operatorIds", []),
                    "operatorNames": group.get("operatorNames", []),
                    "lineNames": group.get("lineNames", []),
                    "prefectureNamesJa": group.get("prefectureNamesJa", []),
                    "prefectureNamesEn": group.get("prefectureNamesEn", []),
                    "locationNote": group.get("locationNote"),
                    "identityVersion": group.get("identityVersion"),
                    "groupingMethod": group.get("groupingMethod"),
                },
            }
        )
        labels.append(
            {
                "stationGroupId": group["id"],
                "minZoom": 4 if rank >= 95 else 6 if rank >= 90 else 8 if rank >= 80 else 10,
                "maxZoom": 24,
                "labelRank": rank,
                "displayNameJa": name,
                "displayNameEn": name,
                "labelPoint": {"lat": centroid.get("lat"), "lon": centroid.get("lon")},
            }
        )
    return station_groups, labels


def build_track_exports(
    physical_map: dict[str, Any],
    line_station_groups: dict[tuple[str, str], set[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    tracks = []
    service_geometry = []
    routes_by_id: dict[str, dict[str, Any]] = {}
    for track in physical_map.get("trackCenterlines", []):
        operator_id = track.get("operatorId") or "unknown_operator"
        operator_name = track.get("operatorName") or operator_id
        line_name = track.get("lineName") or "未設定路線"
        route_id = route_id_for(operator_id, line_name)
        color = color_for_operator_line(operator_id, line_name)
        routes_by_id.setdefault(
            route_id,
            {
                "id": route_id,
                "operatorId": operator_id,
                "operatorName": operator_name,
                "shortName": line_name,
                "longName": f"{operator_name} {line_name}",
                "color": color,
                "textColor": "#102033",
                "mode": "shinkansen" if "新幹線" in line_name else "rail",
                "tags": {"source": "v4_physical_map", "sourceOperatorId": operator_id, "lineName": line_name},
            },
        )
        polyline = polyline_from_points(track.get("points", []))
        if len(polyline) < 2:
            continue
        track_export = {
            "id": track["id"],
            "operatorId": operator_id,
            "lineName": line_name,
            "mode": "shinkansen" if "新幹線" in line_name else "rail",
            "color": color,
            "polyline": polyline,
            "tags": {
                "operatorName": operator_name,
                "railwayClass": track.get("railwayClass"),
                "railwayType": track.get("railwayType"),
                "routeId": route_id,
            },
        }
        tracks.append(track_export)
        # The website can derive service geometry from trackCenterlines via
        # tags.routeId. Keeping a second copy here made the initial map bundle
        # much larger without adding independent geometry.
    return tracks, service_geometry, routes_by_id


def enrich_routes_from_trains(
    trains: list[dict[str, Any]],
    routes_by_id: dict[str, dict[str, Any]],
    line_station_groups: dict[tuple[str, str], set[str]],
    id_to_name: dict[str, str],
    name_to_id: dict[str, str],
    physical_station_by_id: dict[str, dict[str, Any]],
) -> None:
    for train in trains:
        operator_id, line_name = route_key_for_train(train, name_to_id, id_to_name, physical_station_by_id)
        operator_name = train.get("operator_name") or id_to_name.get(operator_id) or operator_id
        operator_name = id_to_name.get(operator_id, operator_name)
        route_id = route_id_for(operator_id, line_name)
        color = f"#{str(train.get('route_color') or '').lstrip('#')}" if train.get("route_color") else color_for_operator_line(operator_id, line_name)
        ensure_route_export(routes_by_id, operator_id, line_name, operator_name, color)
        stop_keys_seen: set[tuple[str, str]] = set()
        for stop in train.get("stop_times", []):
            station_group_id = stop.get("station_group_id") or stop.get("station_id")
            trace_key = trace_route_key_for_stop(stop, train, physical_station_by_id, name_to_id, id_to_name)
            if trace_key and trace_key not in stop_keys_seen:
                trace_operator_id, trace_line_name = trace_key
                trace_operator_name = id_to_name.get(trace_operator_id, trace_operator_id)
                ensure_route_export(routes_by_id, trace_operator_id, trace_line_name, trace_operator_name)
                stop_keys_seen.add(trace_key)
            if station_group_id:
                line_station_groups[(operator_id, line_name)].add(station_group_id)


def build_timetable(
    trains: list[dict[str, Any]],
    name_to_id: dict[str, str],
    id_to_name: dict[str, str],
    valid_station_group_ids: set[str],
    physical_station_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, set[str]], dict[tuple[str, str], set[str]], dict[str, int]]:
    trip_instances = []
    route_station_groups: dict[str, set[str]] = defaultdict(set)
    line_station_groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    stats = {"skipped_short": 0, "skipped_no_route": 0, "skipped_mislabeled_foreign_train": 0}
    seen_ids: set[str] = set()
    for index, train in enumerate(trains):
        if should_skip_mislabeled_foreign_train(train):
            stats["skipped_mislabeled_foreign_train"] += 1
            continue
        operator_id, line_name = route_key_for_train(train, name_to_id, id_to_name, physical_station_by_id)
        if not operator_id or not line_name:
            stats["skipped_no_route"] += 1
            continue
        route_id = route_id_for(operator_id, line_name)
        stop_times = collapse_consecutive_duplicate_stops(
            normalize_trip_stop_times(train.get("stop_times") or [], valid_station_group_ids, physical_station_by_id)
        )
        if len(stop_times) < 2:
            stats["skipped_short"] += 1
            continue
        service_name = public_service_name_for_train(train, line_name)
        base_id = train.get("service_instance_id") or train.get("source_trip_id") or f"v4-trip-{index}"
        trip_id = str(base_id)
        if trip_id in seen_ids:
            trip_id = f"{trip_id}#{stable_hash(str(index), 6)}"
        seen_ids.add(trip_id)
        station_group_ids = [stop["stationGroupId"] for stop in stop_times]
        route_station_groups[route_id].update(station_group_ids)
        line_trace, line_sequence = build_line_trace(
            train.get("stop_times") or [],
            stop_times,
            train,
            physical_station_by_id,
            name_to_id,
            id_to_name,
            operator_id,
            line_name,
        )
        attach_stop_route_identity(stop_times, line_trace, route_id)
        for trace in line_trace:
            trace_route_id = trace["routeId"]
            traced_station_ids = [
                stop["stationGroupId"]
                for stop in stop_times
                if trace["fromSequence"] <= stop["sequence"] <= trace["toSequence"]
            ]
            route_station_groups[trace_route_id].update(traced_station_ids)
            line_station_groups[(trace["operatorId"], trace["lineName"])].update(traced_station_ids)
        for stop in train.get("stop_times", []):
            station_group_id = stop.get("station_group_id") or stop.get("station_id")
            stop_operator_id, stop_line_name = physical_route_key_for_stop(
                stop,
                train,
                physical_station_by_id,
                name_to_id,
                id_to_name,
            ) or (operator_id, line_name)
            if station_group_id and station_group_id in valid_station_group_ids:
                line_station_groups[(operator_id, line_name)].add(station_group_id)
                line_station_groups[(stop_operator_id, stop_line_name)].add(station_group_id)
        trip_instances.append(
            {
                "id": trip_id,
                "routeId": route_id,
                "serviceName": service_name,
                "serviceNameJa": service_name,
                "displayName": train.get("display_name") or train.get("displayName") or "",
                "serviceNumber": train.get("service_number") or train.get("train_number") or "",
                "publicServiceNumber": train.get("service_number") or train.get("train_number") or "",
                "operatingNumber": train.get("train_number") or train.get("service_number") or "",
                "headsign": train.get("headsign") or train.get("destination") or "",
                "origin": train.get("origin"),
                "destination": train.get("destination"),
                "sourceTripId": train.get("source_trip_id"),
                "sourceFeedKey": train.get("source_feed_key"),
                "lineTrace": line_trace,
                "lineSequence": line_sequence,
                "stopTimes": stop_times,
            }
        )
    return trip_instances, route_station_groups, line_station_groups, stats


def compact_timetable(trip_instances: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    station_group_ids = sorted({stop["stationGroupId"] for trip in trip_instances for stop in trip.get("stopTimes", [])})
    route_ids = sorted(
        {trip["routeId"] for trip in trip_instances}
        | {trace["routeId"] for trip in trip_instances for trace in trip.get("lineTrace", [])}
        | {stop["displayRouteId"] for trip in trip_instances for stop in trip.get("stopTimes", []) if stop.get("displayRouteId")}
        | {stop["outgoingRouteId"] for trip in trip_instances for stop in trip.get("stopTimes", []) if stop.get("outgoingRouteId")}
        | {stop["incomingRouteId"] for trip in trip_instances for stop in trip.get("stopTimes", []) if stop.get("incomingRouteId")}
    )
    service_names = sorted({trip.get("serviceName") or "" for trip in trip_instances})
    display_names = sorted({trip.get("displayName") or "" for trip in trip_instances})
    headsigns = sorted({trip.get("headsign") or "" for trip in trip_instances})
    station_index = {value: index for index, value in enumerate(station_group_ids)}
    route_index = {value: index for index, value in enumerate(route_ids)}
    service_index = {value: index for index, value in enumerate(service_names)}
    display_index = {value: index for index, value in enumerate(display_names)}
    headsign_index = {value: index for index, value in enumerate(headsigns)}
    rows = []
    for trip in trip_instances:
        rows.append(
            [
                trip["id"],
                route_index[trip["routeId"]],
                service_index[trip.get("serviceName") or ""],
                trip.get("serviceNumber") or "",
                [
                    [
                        station_index[stop["stationGroupId"]],
                        stop.get("arrivalTimeSec"),
                        stop.get("departureTimeSec"),
                        route_index[stop["displayRouteId"]] if stop.get("displayRouteId") in route_index else None,
                        route_index[stop["outgoingRouteId"]] if stop.get("outgoingRouteId") in route_index else None,
                        route_index[stop["incomingRouteId"]] if stop.get("incomingRouteId") in route_index else None,
                    ]
                    for stop in trip.get("stopTimes", [])
                ],
                [
                    [
                        trace.get("fromSequence"),
                        trace.get("toSequence"),
                        route_index[trace["routeId"]],
                    ]
                    for trace in trip.get("lineTrace", [])
                    if trace.get("routeId") in route_index
                ],
                display_index[trip.get("displayName") or ""],
                headsign_index[trip.get("headsign") or ""],
            ]
        )
    return {
        "format": "v3-timetable-compact-v1",
        "version": "v4.gameplay.1",
        "generatedAt": generated_at,
        "sourceBundle": "v4_gameplay_map_bundle.json.gz",
        "lineTraceEncoding": "sequence-route-ranges-v1",
        "stationGroupIds": station_group_ids,
        "routeIds": route_ids,
        "serviceNames": service_names,
        "displayNames": display_names,
        "headsigns": headsigns,
        "trips": rows,
    }


def build_bundle(
    map_input: Path,
    trains_input: Path,
    *,
    include_full_timetable: bool = False,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any], dict[str, Any]]:
    physical_map = load_json(map_input)
    trains_payload = load_json(trains_input)
    trains = trains_payload.get("train_instances", [])
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    id_to_name, name_to_id = operator_maps(physical_map)
    valid_station_group_ids = {group["id"] for group in physical_map.get("stationGroups", [])}
    physical_station_by_id = {station["id"]: station for station in physical_map.get("physicalStations", [])}
    physical_line_station_groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for station in physical_map.get("physicalStations", []):
        operator_id = station.get("operatorId") or "unknown_operator"
        line_name = station.get("lineName") or "未設定路線"
        station_group_id = station.get("stationGroupId")
        if station_group_id:
            physical_line_station_groups[(operator_id, line_name)].add(station_group_id)

    trip_instances, route_station_groups, train_line_station_groups, train_stats = build_timetable(
        trains,
        name_to_id,
        id_to_name,
        valid_station_group_ids,
        physical_station_by_id,
    )
    line_station_groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for key, value in physical_line_station_groups.items():
        line_station_groups[key].update(value)
    for key, value in train_line_station_groups.items():
        line_station_groups[key].update(value)

    track_centerlines, service_geometry, routes_by_id = build_track_exports(physical_map, line_station_groups)
    enrich_routes_from_trains(trains, routes_by_id, line_station_groups, id_to_name, name_to_id, physical_station_by_id)
    for route_id, station_ids in route_station_groups.items():
        route = routes_by_id.get(route_id)
        if not route:
            continue
        line_station_groups[(route["operatorId"], route["shortName"])].update(station_ids)

    service_patterns = []
    for route_id, route in sorted(routes_by_id.items()):
        if route_id not in route_station_groups:
            continue
        key = (route.get("operatorId") or "unknown_operator", route.get("shortName") or "未設定路線")
        station_group_ids = sorted(line_station_groups.get(key, set()) | route_station_groups.get(route_id, set()))
        if not station_group_ids:
            continue
        service_patterns.append(
            {
                "id": pattern_id_for(route_id),
                "routeId": route_id,
                "label": route.get("shortName") or route_id,
                "stationGroupIds": station_group_ids,
                "shapeId": route_id,
                "tags": {"source": "v4_gameplay_builder"},
            }
        )

    station_groups, label_representations = build_station_group_exports(physical_map)
    runner_start = choose_default_group(physical_map.get("stationGroups", []), MAJOR_STATION_FALLBACKS["runner"], 0)
    hunter_start = choose_default_group(physical_map.get("stationGroups", []), MAJOR_STATION_FALLBACKS["hunter"], 1)
    map_bundle = {
        "version": "v4.gameplay.1",
        "generatedAt": generated_at,
        "metadata": {
            "label": "OniChase V4 Japan Gameplay",
            "datasetId": "v4_nationwide",
            "sourceMap": str(map_input.relative_to(ROOT)),
            "sourceTimetable": str(trains_input.relative_to(ROOT)),
            "bundleFormat": "v3-compatible-maplibre-gameplay",
            "defaultRunnerStartStationId": runner_start,
            "defaultHunterStartStationId": hunter_start,
            "deferredTimetable": True,
            "deferredTripCount": len(trip_instances),
            "skippedTrainCount": sum(train_stats.values()),
            "notes": [
                "Generated from v4 nationwide physical map and weekday timetable.",
                "Gameplay rules intentionally reuse the v3/v2 planning/live/capture shell.",
            ],
        },
        "physicalStations": build_physical_station_exports(physical_map),
        "stationGroups": station_groups,
        "trackCenterlines": track_centerlines,
        "pathways": [],
        "serviceRoutes": sorted(routes_by_id.values(), key=lambda route: (route.get("operatorId", ""), route.get("shortName", ""))),
        "servicePatterns": service_patterns,
        "tripInstances": [],
        "serviceGeometry": service_geometry,
        "labelRepresentations": label_representations,
        "gameNodes": [],
    }
    service_route_ids = {pattern["routeId"] for pattern in service_patterns}
    map_bundle["serviceRoutes"] = [
        route
        for route in map_bundle["serviceRoutes"]
        if route["id"] in service_route_ids
    ]
    compact = compact_timetable(trip_instances, generated_at)
    trip_count = len(trip_instances)
    full_timetable = None
    if include_full_timetable:
        full_timetable = {
            "version": "v4.gameplay.1",
            "generatedAt": generated_at,
            "sourceBundle": "v4_gameplay_map_bundle.json.gz",
            "tripInstances": trip_instances,
        }
    else:
        trip_instances.clear()
    manifest = {
        "dataset": "v4_nationwide_gameplay",
        "generatedAt": generated_at,
        "sourceMap": str(map_input.relative_to(ROOT)),
        "sourceTimetable": str(trains_input.relative_to(ROOT)),
        "outputs": {
            "mapBundle": "v4_gameplay_map_bundle.json.gz",
            "fullTimetable": "v4_gameplay_timetable_bundle.json.gz",
            "compactTimetable": "v4_gameplay_timetable_compact.json.gz",
        },
        "counts": {
            "physicalStations": len(map_bundle["physicalStations"]),
            "stationGroups": len(map_bundle["stationGroups"]),
            "trackCenterlines": len(map_bundle["trackCenterlines"]),
            "serviceRoutes": len(map_bundle["serviceRoutes"]),
            "servicePatterns": len(map_bundle["servicePatterns"]),
            "serviceGeometry": len(map_bundle["serviceGeometry"]),
            "tripInstances": trip_count,
            "compactTrips": len(compact["trips"]),
            "skippedTrainCount": sum(train_stats.values()),
        },
        "defaults": {
            "runnerStartStationId": runner_start,
            "hunterStartStationId": hunter_start,
        },
        "trainStats": train_stats,
    }
    return map_bundle, full_timetable, compact, manifest


def write_outputs(
    payloads: tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any], dict[str, Any]],
    output_dirs: list[Path],
    *,
    write_full_timetable: bool = False,
) -> None:
    map_bundle, full_timetable, compact, manifest = payloads
    names = {
        "v4_gameplay_map_bundle.json.gz": map_bundle,
        "v4_gameplay_timetable_compact.json.gz": compact,
        "v4_gameplay_manifest.json": manifest,
    }
    if write_full_timetable:
        if full_timetable is None:
            raise ValueError("full timetable was not built")
        names["v4_gameplay_timetable_bundle.json.gz"] = full_timetable
    if not output_dirs:
        return

    primary_dir = output_dirs[0]
    for filename, payload in names.items():
        write_json(primary_dir / filename, payload)

    for output_dir in output_dirs[1:]:
        output_dir.mkdir(parents=True, exist_ok=True)
        for filename in names:
            shutil.copyfile(primary_dir / filename, output_dir / filename)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build v4 nationwide data as a v3-compatible gameplay bundle.")
    parser.add_argument("--map-input", type=Path, default=DEFAULT_MAP_INPUT)
    parser.add_argument("--trains-input", type=Path, default=DEFAULT_TRAINS_INPUT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--docs-data-dir", type=Path, default=DEFAULT_DOCS_DATA_DIR)
    parser.add_argument(
        "--write-full-timetable",
        action="store_true",
        help="Also write the legacy full timetable bundle. The website uses the compact bundle.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payloads = build_bundle(args.map_input, args.trains_input, include_full_timetable=args.write_full_timetable)
    write_outputs(payloads, [args.data_dir, args.docs_data_dir], write_full_timetable=args.write_full_timetable)
    manifest = payloads[3]
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
