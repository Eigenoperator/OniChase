#!/usr/bin/env python3
from __future__ import annotations

import argparse
import builtins
import gzip
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
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
    ("名古屋市", "3号線鶴舞線"): "鶴舞線",
    ("名古屋市", "3号線(鶴舞線)"): "鶴舞線",
}

JR_WEST_LETTERED_RAPID_LABEL_RE = re.compile(
    r"^(?:普通|快速|新快速|区間快速|通勤快速|直通快速|みやこ路快速|大和路快速|丹波路快速|関空快速|紀州路快速)?"
    r"[A-ZＡ-Ｚ](?:快速|新快速|区間快速|通勤快速|直通快速|みやこ路快速|大和路快速|丹波路快速|関空快速|紀州路快速)\d+号$"
)

KINTETSU_LIMITED_EXPRESS_BRAND_RE = re.compile(
    r"^(?:特急|観光特急)?\s*"
    r"(しまかぜ|ひのとり|あをによし|青の交響曲|アーバンライナー|伊勢志摩ライナー|さくらライナー|ビスタカー)"
)

NAMED_LIMITED_EXPRESS_LABEL_RE = re.compile(
    r"(?:メトロ)?(?:はこね|えのしま|ホームウェイ|モーニングウェイ|ふじさん|さがみ)\d*号?|"
    r"(?:サンダーバード|はるか|くろしお|こうのとり|きのさき|はしだて|まいづる|しらさぎ|"
    r"成田エクスプレス|あずさ|かいじ|富士回遊|ひたち|ときわ|わかしお|さざなみ|しおさい|"
    r"リバティ|けごん|きぬ|会津|りょうもう|スペーシア|サンライズ|踊り子|ひだ)\d*号?"
)

SHINKANSEN_SERVICE_LABEL_RE = re.compile(
    r"(はやぶさ|はやて|やまびこ|なすの|こまち|つばさ|とき|たにがわ|かがやき|はくたか|あさま|つるぎ|"
    r"のぞみ|ひかり|こだま|みずほ|さくら|つばめ|かもめ)(\d{1,4})?号?"
)

SHINKANSEN_PUBLIC_SERVICE_NAMES = {
    "あさま": "Asama",
    "かがやき": "Kagayaki",
    "かもめ": "Kamome",
    "こだま": "Kodama",
    "こまち": "Komachi",
    "さくら": "Sakura",
    "つばさ": "Tsubasa",
    "つばめ": "Tsubame",
    "つるぎ": "Tsurugi",
    "とき": "Toki",
    "なすの": "Nasuno",
    "のぞみ": "Nozomi",
    "はくたか": "Hakutaka",
    "はやて": "Hayate",
    "はやぶさ": "Hayabusa",
    "ひかり": "Hikari",
    "みずほ": "Mizuho",
    "やまびこ": "Yamabiko",
    "たにがわ": "Tanigawa",
}

SHINKANSEN_SERVICE_CORRIDORS = {
    "あさま": "SHINKANSEN_HOKURIKU",
    "かがやき": "SHINKANSEN_HOKURIKU",
    "こだま": "SHINKANSEN_TOKAIDO_SANYO",
    "こまち": "SHINKANSEN_AKITA",
    "さくら": "SHINKANSEN_KYUSHU",
    "つばさ": "SHINKANSEN_YAMAGATA",
    "つばめ": "SHINKANSEN_KYUSHU",
    "つるぎ": "SHINKANSEN_HOKURIKU",
    "とき": "SHINKANSEN_JOETSU",
    "なすの": "SHINKANSEN_TOHOKU_HOKKAIDO",
    "のぞみ": "SHINKANSEN_TOKAIDO_SANYO",
    "はくたか": "SHINKANSEN_HOKURIKU",
    "はやて": "SHINKANSEN_TOHOKU_HOKKAIDO",
    "はやぶさ": "SHINKANSEN_TOHOKU_HOKKAIDO",
    "ひかり": "SHINKANSEN_TOKAIDO_SANYO",
    "みずほ": "SHINKANSEN_KYUSHU",
    "やまびこ": "SHINKANSEN_TOHOKU_HOKKAIDO",
    "たにがわ": "SHINKANSEN_JOETSU",
}

NISHI_KYUSHU_SHINKANSEN_STATION_NAMES = {"武雄温泉", "嬉野温泉", "新大村", "諫早", "長崎"}

PHYSICAL_TRACE_WINS_LINE_NAMES = {
    "内房線",
    "外房線",
    "東金線",
    "成田線",
    "鹿島線",
}

REVIEWED_PHYSICAL_SEGMENT_LINE_OVERRIDES = {
    frozenset(("大網", "蘇我")): ("jr_east", "外房線"),
    frozenset(("京都", "敦賀")): ("jr_west", "湖西線"),
    frozenset(("京都", "近江今津")): ("jr_west", "湖西線"),
    frozenset(("京都", "堅田")): ("jr_west", "湖西線"),
    frozenset(("敦賀", "近江今津")): ("jr_west", "湖西線"),
    frozenset(("敦賀", "堅田")): ("jr_west", "湖西線"),
    frozenset(("長崎", "諫早")): ("jr_kyushu", "長崎線"),
    frozenset(("諫早", "新大村")): ("jr_kyushu", "大村線"),
    frozenset(("諫早", "大村")): ("jr_kyushu", "大村線"),
}

REVIEWED_THROUGH_STOP_GROUP_REMAPS = [
    {
        "operator_id": "tobu",
        "service_name_prefixes": ("THライナー",),
        "station_name": "霞ヶ関",
        "wrong_lines": {("tobu", "東上本線")},
        "target_lines": {("tokyo_metro", "2号線日比谷線")},
        "anchor_station_names": {"久喜", "東武動物公園", "春日部", "せんげん台", "新越谷"},
    },
]

REVIEWED_THROUGH_PHYSICAL_STATION_REMAPS = [
    {
        "operator_id": "tokyo_metro",
        "service_name_prefixes": ("メトロはこね", "メトロホームウェイ", "メトロえのしま"),
        "station_names": {"北千住", "大手町", "霞ヶ関", "表参道"},
        "target_line": ("tokyo_metro", "9号線千代田線"),
        "anchor_station_names": {"成城学園前", "新百合ヶ丘", "町田", "本厚木", "箱根湯本"},
    },
]

REMOTE_THROUGH_SOURCE_LINE_NAMES = {
    "横須賀線",
    "総武線",
    "総武快速線",
    "湘南新宿ライン",
    "上野東京ライン",
    "中央線",
    "京葉線",
}

PASSENGER_TRACE_WINS_LINE_NAMES = {
    "山手線",
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


def normalized_train_label(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", "", text)
    return text.replace("（", "(").replace("）", ")")


def gameplay_trip_signature(trip: dict[str, Any]) -> str:
    hasher = hashlib.sha1()
    label = normalized_train_label(trip.get("displayName") or trip.get("serviceName") or "")
    for part in (
        label,
        trip.get("origin") or "",
        trip.get("destination") or "",
    ):
        hasher.update(str(part).encode("utf-8"))
        hasher.update(b"\0")
    for stop in trip.get("stopTimes") or []:
        for part in (
            stop.get("stationGroupId") or "",
            stop.get("arrivalTimeSec") if isinstance(stop.get("arrivalTimeSec"), int) else "",
            stop.get("departureTimeSec") if isinstance(stop.get("departureTimeSec"), int) else "",
        ):
            hasher.update(str(part).encode("utf-8"))
            hasher.update(b"\0")
    return hasher.hexdigest()


def gameplay_trip_operational_signature(trip: dict[str, Any]) -> str:
    hasher = hashlib.sha1()
    for stop in trip.get("stopTimes") or []:
        for part in (
            stop.get("stationGroupId") or "",
            stop.get("arrivalTimeSec") if isinstance(stop.get("arrivalTimeSec"), int) else "",
            stop.get("departureTimeSec") if isinstance(stop.get("departureTimeSec"), int) else "",
        ):
            hasher.update(str(part).encode("utf-8"))
            hasher.update(b"\0")
    return hasher.hexdigest()


def gameplay_trip_source_priority(trip_id: str) -> tuple[int, str]:
    text = str(trip_id or "")
    if text.startswith("shinkansen:"):
        return (0, text)
    if "_official:" in text or text.startswith("jr_west_official:") or text.startswith("jr_east_official:"):
        return (0, text)
    if text.startswith("special_manual:") or "_special_manual:" in text:
        return (1, text)
    if "_navitime:" in text or "navitime" in text:
        return (5, text)
    return (3, text)


def choose_best_gameplay_trip(current: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
    if current is None:
        return candidate
    current_priority = gameplay_trip_source_priority(str(current.get("id") or ""))[0]
    candidate_priority = gameplay_trip_source_priority(str(candidate.get("id") or ""))[0]
    if candidate_priority != current_priority:
        return candidate if candidate_priority < current_priority else current
    current_trace_count = len(current.get("lineTrace") or [])
    candidate_trace_count = len(candidate.get("lineTrace") or [])
    if candidate_trace_count != current_trace_count:
        return candidate if candidate_trace_count > current_trace_count else current
    return min([current, candidate], key=lambda item: str(item.get("id") or ""))


def dedupe_gameplay_trip_instances(trip_instances: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_signature: dict[str, dict[str, Any]] = {}
    signature_counts: Counter[str] = Counter()
    for trip in trip_instances:
        signature = gameplay_trip_signature(trip)
        signature_counts[signature] += 1
        by_signature[signature] = choose_best_gameplay_trip(by_signature.get(signature), trip)
    duplicate_count = sum(count - 1 for count in signature_counts.values() if count > 1)
    return sorted(by_signature.values(), key=lambda item: str(item.get("id") or "")), duplicate_count


def trip_source_family(trip: dict[str, Any]) -> str:
    text = str(trip.get("id") or trip.get("sourceFeedKey") or "")
    if text.startswith("shinkansen:"):
        return "curated"
    if "_official:" in text or "_official" in text:
        return "official"
    if "_navitime:" in text or "navitime" in text:
        return "navitime"
    return "other"


ROUTE_LIKE_SERVICE_LABEL_RE = re.compile(
    r"(?:線|本線|支線|ライン|鉄道|鐵道|電鉄|電鐵|電車|軌道|ケーブル|鋼索)$"
)


def is_plain_route_label_trip(trip: dict[str, Any]) -> bool:
    if trip.get("displayName") or trip.get("routeName") or trip.get("coupledRouteNames"):
        return False
    service_name = str(trip.get("serviceName") or trip.get("serviceNameJa") or "").strip()
    if not service_name:
        return True
    return bool(ROUTE_LIKE_SERVICE_LABEL_RE.search(service_name))


def dedupe_overlapping_source_trip_instances(trip_instances: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_signature: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trip in trip_instances:
        by_signature[gameplay_trip_operational_signature(trip)].append(trip)
    deduped: list[dict[str, Any]] = []
    duplicate_count = 0
    for trips in by_signature.values():
        families = {trip_source_family(trip) for trip in trips}
        if len(trips) > 1 and "navitime" in families and len(families) > 1:
            best: dict[str, Any] | None = None
            for trip in trips:
                best = choose_best_gameplay_trip(best, trip)
            assert best is not None
            deduped.append(best)
            duplicate_count += len(trips) - 1
        elif len(trips) > 1 and families == {"navitime"} and all(is_plain_route_label_trip(trip) for trip in trips):
            best = None
            for trip in trips:
                best = choose_best_gameplay_trip(best, trip)
            assert best is not None
            deduped.append(best)
            duplicate_count += len(trips) - 1
        else:
            deduped.extend(trips)
    return sorted(deduped, key=lambda item: str(item.get("id") or "")), duplicate_count


def named_limited_express_label(value: Any) -> str:
    text = re.sub(r"\s+", "", str(value or "").strip())
    if not text:
        return ""
    match = NAMED_LIMITED_EXPRESS_LABEL_RE.search(text)
    if not match:
        return ""
    return match.group(0)


def named_limited_express_family(value: Any) -> str:
    label = named_limited_express_label(value)
    if not label:
        return ""
    return re.sub(r"\d+号$", "", label)


def shinkansen_service_match_for_train(train: dict[str, Any]) -> re.Match[str] | None:
    text = "".join(
        re.sub(r"\s+", "", str(train.get(field) or ""))
        for field in ("service_name_detail", "display_name", "service_name", "route_name")
    )
    if not text:
        return None
    return SHINKANSEN_SERVICE_LABEL_RE.search(text)


def train_has_shinkansen_physical_evidence(
    train: dict[str, Any],
    physical_station_by_id: dict[str, dict[str, Any]],
) -> bool:
    evidence_count = 0
    for stop in train.get("stop_times") or []:
        physical_station = physical_station_by_id.get(stop.get("physical_station_id") or stop.get("physicalStationId") or "")
        line_text = " ".join(
            str(value or "")
            for value in (
                stop.get("line_name"),
                stop.get("physical_line_name"),
                (physical_station or {}).get("lineName"),
            )
        )
        if "新幹線" in line_text:
            evidence_count += 1
    if evidence_count >= 2:
        return True
    station_names = {
        str(stop.get("station_name_raw") or stop.get("station_name") or "").strip()
        for stop in train.get("stop_times") or []
    }
    return len(station_names & NISHI_KYUSHU_SHINKANSEN_STATION_NAMES) >= 2


def reviewed_shinkansen_route_override_for_train(
    train: dict[str, Any],
    physical_station_by_id: dict[str, dict[str, Any]],
) -> dict[str, str] | None:
    match = shinkansen_service_match_for_train(train)
    if not match:
        return None
    service_name_ja = match.group(1)
    line_name = SHINKANSEN_SERVICE_CORRIDORS.get(service_name_ja)
    if service_name_ja == "かもめ":
        stop_names = {
            str(stop.get("station_name_raw") or stop.get("station_name") or "").strip()
            for stop in train.get("stop_times") or []
        }
        if len(stop_names & NISHI_KYUSHU_SHINKANSEN_STATION_NAMES) >= 2:
            line_name = "SHINKANSEN_KYUSHU"
    if not line_name:
        return None
    raw_operator_id = str(train.get("operator_id") or "").strip()
    original_line_name = str(train.get("line_name") or "").strip()
    if raw_operator_id == "shinkansen" and original_line_name.startswith("SHINKANSEN_"):
        return None
    if not train_has_shinkansen_physical_evidence(train, physical_station_by_id):
        return None
    service_number = match.group(2) or ""
    return {
        "operator_id": "shinkansen",
        "operator_name": "JR Shinkansen",
        "line_name": line_name,
        "service_name": SHINKANSEN_PUBLIC_SERVICE_NAMES.get(service_name_ja, service_name_ja),
        "service_number": service_number,
        "display_name": f"{service_name_ja}{service_number}号" if service_number else service_name_ja,
        "train_type": "新幹線",
    }


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
    inferred_limited_name = named_limited_express_family(service_detail) or named_limited_express_family(display_name)
    if inferred_limited_name:
        return inferred_limited_name
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
    if service_name and service_name != original_line_name and re.search(
        r"(?:メトロ)?(?:はこね|えのしま|ホームウェイ|モーニングウェイ|ふじさん|さがみ)\d+号|"
        r"(?:リバティ|けごん|きぬ|会津|りょうもう|スペーシア|サンライズ|踊り子|ひだ)\d*号?",
        service_name,
    ):
        return service_name
    return public_line_name


def public_line_name_for_route(operator_id: str, line_name: str, id_to_name: dict[str, str]) -> str:
    operator_name = id_to_name.get(operator_id, operator_id)
    return PUBLIC_LINE_NAME_OVERRIDES.get((operator_name, line_name), line_name)


def is_limited_train_type(train_type: str) -> bool:
    text = str(train_type or "").strip()
    return bool(text and "特急" in text)


def is_jr_west_lettered_rapid_label(value: str) -> bool:
    text = re.sub(r"\s+", "", str(value or "").strip())
    if not text:
        return False
    return bool(JR_WEST_LETTERED_RAPID_LABEL_RE.match(text))


def normalize_kintetsu_limited_express_label(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return ""
    text = re.sub(r"^特急\s*", "", text)
    text = re.sub(r"^観光特急\s*", "", text)
    text = re.sub(r"（[^）]*(?:車いす|車イス|対応車両|車内販売|禁煙|喫煙)[^）]*）", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    brand_match = KINTETSU_LIMITED_EXPRESS_BRAND_RE.match(text)
    if brand_match:
        return brand_match.group(1)
    return text


def gameplay_display_name_for_train(train: dict[str, Any], operator_name: str) -> str:
    display_name = str(train.get("display_name") or train.get("displayName") or "").strip()
    train_type = str(train.get("train_type") or "").strip()
    if not display_name:
        return ""
    if not is_limited_train_type(train_type) and not named_limited_express_label(display_name):
        return ""
    if operator_name == "近畿日本鉄道" and is_limited_train_type(train_type):
        return normalize_kintetsu_limited_express_label(display_name)
    if operator_name == "西日本旅客鉄道" and is_jr_west_lettered_rapid_label(display_name):
        return ""
    return display_name


def gameplay_route_name_for_train(train: dict[str, Any], operator_name: str) -> str:
    route_name = str(train.get("route_name") or train.get("routeName") or "").strip()
    train_type = str(train.get("train_type") or "").strip()
    if not route_name:
        return ""
    if not is_limited_train_type(train_type) and not named_limited_express_label(route_name):
        return ""
    if operator_name == "西日本旅客鉄道" and is_jr_west_lettered_rapid_label(route_name):
        return ""
    return route_name


def through_destination_service_name(
    service_name: str,
    operator_id: str,
    line_name: str,
    line_trace: list[dict[str, Any]],
    id_to_name: dict[str, str],
) -> str:
    operator_name = id_to_name.get(operator_id, operator_id)
    if operator_name != "名古屋鉄道" or not line_trace:
        return service_name
    destination_trace = line_trace[-1]
    destination_line = str(destination_trace.get("lineName") or "").strip()
    destination_operator_id = str(destination_trace.get("operatorId") or operator_id)
    if not destination_line or destination_line == line_name:
        return service_name
    return public_line_name_for_route(destination_operator_id, destination_line, id_to_name)


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
        raw_operator_id = builtins.str(raw_operator_id)
    if raw_operator_name is not None:
        raw_operator_name = builtins.str(raw_operator_name)
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
    value = builtins.str(line_name or "").strip()
    return SYNTHETIC_LINE_NAME_OVERRIDES.get(value, value)


def normalize_station_name(value: str | None) -> str:
    text = builtins.str(value or "").strip()
    replacements = {
        "　": "",
        " ": "",
        "-": "",
        "‐": "",
        "ー": "",
        "・": "",
        "（": "",
        "）": "",
        "(": "",
        ")": "",
        "駅": "",
        "停留場": "",
        "電停": "",
        "塚": "塚",
        "ヶ": "ケ",
        "が": "ガ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


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
    train_line_name = canonical_line_name(train.get("line_name"))
    if str(train.get("operator_id") or "") == "shinkansen" and is_synthetic_line_name(train.get("line_name")):
        raw_line_name = train_line_name
    raw_operator_id = resolve_operator_id(
        train.get("operator_id"),
        train.get("operator_name") or stop.get("operator_name"),
        name_to_id,
        id_to_name,
    )
    physical_key = physical_route_key_for_stop(stop, train, physical_station_by_id, name_to_id, id_to_name)
    if raw_line_name in PASSENGER_TRACE_WINS_LINE_NAMES:
        return (raw_operator_id, raw_line_name)
    if raw_line_name and (is_synthetic_line_name(stop.get("line_name")) or is_synthetic_line_name(train.get("line_name"))):
        if (
            physical_key
            and raw_operator_id == physical_key[0]
            and raw_line_name in PHYSICAL_TRACE_WINS_LINE_NAMES
            and physical_key[1] in PHYSICAL_TRACE_WINS_LINE_NAMES
        ):
            return physical_key
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
    shinkansen_override = reviewed_shinkansen_route_override_for_train(train, physical_station_by_id)
    if shinkansen_override:
        return shinkansen_override["operator_id"], shinkansen_override["line_name"]
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
    reviewed_physical_lines_by_group: dict[str, set[tuple[str, str]]],
    physical_name_by_group: dict[str, str],
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
        segment_key_from_adjacent_physical = False
        left_group_id = normalized_stops[index]["stationGroupId"]
        right_group_id = normalized_stops[index + 1]["stationGroupId"]
        station_pair = frozenset((
            physical_name_by_group.get(left_group_id, ""),
            physical_name_by_group.get(right_group_id, ""),
        ))
        if station_pair in REVIEWED_PHYSICAL_SEGMENT_LINE_OVERRIDES:
            segment_key = REVIEWED_PHYSICAL_SEGMENT_LINE_OVERRIDES[station_pair]
            segment_key_from_adjacent_physical = True
        else:
            left_lines = reviewed_physical_lines_by_group.get(left_group_id, set())
            right_lines = reviewed_physical_lines_by_group.get(right_group_id, set())
            shared_lines = left_lines & right_lines
            same_operator_shared_lines = {
                line_key for line_key in shared_lines
                if line_key[0] == segment_key[0]
            }
            unique_shared_line = next(iter(shared_lines)) if len(shared_lines) == 1 else None
            shared_line_override = unique_shared_line or (next(iter(same_operator_shared_lines)) if len(same_operator_shared_lines) == 1 else None)
            if (
                segment_key[1] not in PASSENGER_TRACE_WINS_LINE_NAMES
                and
                unique_shared_line
                and segment_key != unique_shared_line
            ):
                # A single common physical line between adjacent station groups is
                # the most reliable identity for that track segment, especially at
                # cross-operator boundary stations.
                segment_key = unique_shared_line
                segment_key_from_adjacent_physical = True
            elif (
                segment_key[1] not in PASSENGER_TRACE_WINS_LINE_NAMES
                and
                shared_line_override
                and segment_key != shared_line_override
                and (
                    is_synthetic_line_name(raw_by_source_sequence.get(int(normalized_stops[index].get("sourceSequence") or 0), {}).get("line_name"))
                    or segment_key[1] in REMOTE_THROUGH_SOURCE_LINE_NAMES
                )
            ):
                # Route choices are physical boarding lines. Source labels for a through service
                # can still appear later as train labels, but they must not overwrite the segment.
                segment_key = shared_line_override
                segment_key_from_adjacent_physical = True
        next_stop_key = stop_keys[index + 1] if index + 1 < len(stop_keys) else None
        if (
            next_stop_key
            and segment_key != next_stop_key
            and segment_key[0] == next_stop_key[0]
            and segment_key[1] in PHYSICAL_TRACE_WINS_LINE_NAMES
            and next_stop_key[1] in PHYSICAL_TRACE_WINS_LINE_NAMES
        ):
            left_lines = reviewed_physical_lines_by_group.get(left_group_id, set())
            right_lines = reviewed_physical_lines_by_group.get(right_group_id, set())
            left_unique = len(left_lines) == 1 and segment_key in left_lines
            right_unique = len(right_lines) == 1 and next_stop_key in right_lines
            if right_unique and not left_unique:
                segment_key = next_stop_key
        previous_key = stop_keys[index - 1] if index > 0 and index - 1 < len(stop_keys) else None
        next_key = stop_keys[index + 1] if index + 1 < len(stop_keys) else None
        if (
            not segment_key_from_adjacent_physical
            and previous_key
            and next_key
            and previous_key == next_key
            and segment_key != previous_key
        ):
            segment_key = next_key
        segment_keys.append(segment_key)
    if segment_keys:
        # Keep short terminal tails on the train's source line when the
        # timetable itself labels those endpoint stops with that source line.
        preserve_source_line_terminal_tails = not is_limited_train_type(str(train.get("train_type") or ""))
        def segment_has_non_fallback_unique_physical_line(index: int) -> bool:
            if index < 0 or index >= len(normalized_stops) - 1:
                return False
            left_group_id = normalized_stops[index]["stationGroupId"]
            right_group_id = normalized_stops[index + 1]["stationGroupId"]
            shared_lines = (
                reviewed_physical_lines_by_group.get(left_group_id, set()) &
                reviewed_physical_lines_by_group.get(right_group_id, set())
            )
            if len(shared_lines) != 1:
                return False
            unique_line = next(iter(shared_lines))
            return unique_line != fallback_key

        if preserve_source_line_terminal_tails:
            first_fallback_index = next((index for index, key in enumerate(segment_keys) if key == fallback_key), None)
            if first_fallback_index is not None and 0 < first_fallback_index <= 2:
                raw_lines = [
                    canonical_line_name(
                        raw_by_source_sequence.get(int(stop.get("sourceSequence") or 0), {}).get("line_name")
                    )
                    for stop in normalized_stops[: first_fallback_index + 1]
                ]
                if (
                    raw_lines and
                    all(line == fallback_line_name for line in raw_lines) and
                    not any(segment_has_non_fallback_unique_physical_line(index) for index in range(first_fallback_index))
                ):
                    for index in range(first_fallback_index):
                        segment_keys[index] = fallback_key
            last_fallback_index = next(
                (index for index in range(len(segment_keys) - 1, -1, -1) if segment_keys[index] == fallback_key),
                None,
            )
            trailing_count = len(segment_keys) - 1 - last_fallback_index if last_fallback_index is not None else 0
            if last_fallback_index is not None and 0 < trailing_count <= 2:
                raw_lines = [
                    canonical_line_name(
                        raw_by_source_sequence.get(int(stop.get("sourceSequence") or 0), {}).get("line_name")
                    )
                    for stop in normalized_stops[last_fallback_index + 1 :]
                ]
                if (
                    raw_lines and
                    all(line == fallback_line_name for line in raw_lines) and
                    not any(segment_has_non_fallback_unique_physical_line(index) for index in range(last_fallback_index + 1, len(segment_keys)))
                ):
                    for index in range(last_fallback_index + 1, len(segment_keys)):
                        segment_keys[index] = fallback_key
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


def rematch_ambiguous_stop_groups(
    raw_stops: list[dict[str, Any]],
    groups_by_station_name: dict[str, set[str]],
    physical_station_by_group: dict[str, list[dict[str, Any]]],
    reviewed_physical_lines_by_group: dict[str, set[tuple[str, str]]],
) -> tuple[list[dict[str, Any]], int]:
    stops = [dict(stop) for stop in sorted(raw_stops or [], key=lambda item: item.get("sequence", 0))]
    rematched_count = 0

    def stop_group_id(stop: dict[str, Any] | None) -> str:
        return str((stop or {}).get("station_group_id") or (stop or {}).get("station_id") or "")

    def best_physical_station_id(group_id: str, preferred_lines: set[tuple[str, str]]) -> str:
        stations = physical_station_by_group.get(group_id) or []
        if not stations:
            return ""
        for operator_id, line_name in preferred_lines:
            for station in stations:
                if (str(station.get("operatorId") or ""), str(station.get("lineName") or "")) == (operator_id, line_name):
                    return str(station.get("id") or "")
        return str(stations[0].get("id") or "")

    for index, stop in enumerate(stops):
        station_name = stop.get("station_name_raw") or stop.get("station_name")
        candidate_group_ids = groups_by_station_name.get(normalize_station_name(station_name), set())
        if len(candidate_group_ids) < 2:
            continue
        current_group_id = stop_group_id(stop)
        if current_group_id not in candidate_group_ids:
            continue
        adjacent_group_ids = [
            stop_group_id(stops[index - 1] if index > 0 else None),
            stop_group_id(stops[index + 1] if index + 1 < len(stops) else None),
        ]
        adjacent_line_sets = [
            reviewed_physical_lines_by_group.get(group_id, set())
            for group_id in adjacent_group_ids
            if group_id
        ]
        if not adjacent_line_sets:
            continue

        scored: list[tuple[int, str, set[tuple[str, str]]]] = []
        for candidate_group_id in candidate_group_ids:
            candidate_lines = reviewed_physical_lines_by_group.get(candidate_group_id, set())
            shared_lines: set[tuple[str, str]] = set()
            score = 0
            for adjacent_lines in adjacent_line_sets:
                overlap = candidate_lines & adjacent_lines
                if overlap:
                    score += 100
                    shared_lines.update(overlap)
            if candidate_group_id == current_group_id:
                score += 1
            scored.append((score, candidate_group_id, shared_lines))
        scored.sort(key=lambda item: (-item[0], item[1]))
        best_score, best_group_id, best_shared_lines = scored[0]
        current_score = next((score for score, group_id, _shared in scored if group_id == current_group_id), 0)
        if best_group_id == current_group_id or best_score <= current_score or best_score < 100:
            continue

        stop["station_group_id"] = best_group_id
        stop["station_id"] = best_group_id
        physical_station_id = best_physical_station_id(best_group_id, best_shared_lines)
        if physical_station_id:
            stop["physical_station_id"] = physical_station_id
        stop["match_method"] = f"{stop.get('match_method') or 'matched'}+context_line"
        rematched_count += 1

    return stops, rematched_count


def rematch_reviewed_through_stop_groups(
    raw_stops: list[dict[str, Any]],
    train: dict[str, Any],
    groups_by_station_name: dict[str, set[str]],
    physical_station_by_group: dict[str, list[dict[str, Any]]],
    reviewed_physical_lines_by_group: dict[str, set[tuple[str, str]]],
) -> tuple[list[dict[str, Any]], int]:
    stops = [dict(stop) for stop in sorted(raw_stops or [], key=lambda item: item.get("sequence", 0))]
    if not stops:
        return stops, 0

    def stop_group_id(stop: dict[str, Any] | None) -> str:
        return str((stop or {}).get("station_group_id") or (stop or {}).get("station_id") or "")

    def stop_name(stop: dict[str, Any] | None) -> str:
        return str((stop or {}).get("station_name_raw") or (stop or {}).get("station_name") or "").strip()

    def best_physical_station_id(group_id: str, preferred_lines: set[tuple[str, str]]) -> str:
        stations = physical_station_by_group.get(group_id) or []
        for operator_id, line_name in preferred_lines:
            for station in stations:
                if (str(station.get("operatorId") or ""), str(station.get("lineName") or "")) == (operator_id, line_name):
                    return str(station.get("id") or "")
        return str(stations[0].get("id") or "") if stations else ""

    operator_id = str(train.get("operator_id") or "").strip()
    service_name = str(train.get("service_name") or train.get("display_name") or "").strip()
    train_station_names = {stop_name(stop) for stop in stops}
    rematched_count = 0

    for rule in REVIEWED_THROUGH_STOP_GROUP_REMAPS:
        if operator_id != rule["operator_id"]:
            continue
        if not any(service_name.startswith(prefix) for prefix in rule["service_name_prefixes"]):
            continue
        if not (train_station_names & set(rule["anchor_station_names"])):
            continue
        candidate_group_ids = groups_by_station_name.get(normalize_station_name(rule["station_name"]), set())
        if not candidate_group_ids:
            continue
        target_group_id = next(
            (
                group_id
                for group_id in sorted(candidate_group_ids)
                if reviewed_physical_lines_by_group.get(group_id, set()) & set(rule["target_lines"])
            ),
            "",
        )
        if not target_group_id:
            continue
        target_physical_station_id = best_physical_station_id(target_group_id, set(rule["target_lines"]))
        for stop in stops:
            if normalize_station_name(stop_name(stop)) != normalize_station_name(rule["station_name"]):
                continue
            current_group_id = stop_group_id(stop)
            current_lines = reviewed_physical_lines_by_group.get(current_group_id, set())
            if not (current_lines & set(rule["wrong_lines"])) or current_group_id == target_group_id:
                continue
            stop["station_group_id"] = target_group_id
            stop["station_id"] = target_group_id
            if target_physical_station_id:
                stop["physical_station_id"] = target_physical_station_id
            stop["line_name"] = next(iter(rule["target_lines"]))[1]
            stop["match_method"] = f"{stop.get('match_method') or 'matched'}+reviewed_through_group"
            rematched_count += 1

    return stops, rematched_count


def rematch_reviewed_through_physical_stations(
    raw_stops: list[dict[str, Any]],
    train: dict[str, Any],
    physical_station_by_group: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], int]:
    stops = [dict(stop) for stop in sorted(raw_stops or [], key=lambda item: item.get("sequence", 0))]
    if not stops:
        return stops, 0

    def stop_group_id(stop: dict[str, Any] | None) -> str:
        return str((stop or {}).get("station_group_id") or (stop or {}).get("station_id") or "")

    def stop_name(stop: dict[str, Any] | None) -> str:
        return str((stop or {}).get("station_name_raw") or (stop or {}).get("station_name") or "").strip()

    def physical_station_id_for_line(group_id: str, line_key: tuple[str, str]) -> str:
        operator_id, line_name = line_key
        for station in physical_station_by_group.get(group_id) or []:
            if (str(station.get("operatorId") or ""), str(station.get("lineName") or "")) == (operator_id, line_name):
                return str(station.get("id") or "")
        return ""

    operator_id = str(train.get("operator_id") or "").strip()
    service_name = str(train.get("service_name") or train.get("display_name") or "").strip()
    train_station_names = {stop_name(stop) for stop in stops}
    rematched_count = 0

    for rule in REVIEWED_THROUGH_PHYSICAL_STATION_REMAPS:
        if operator_id != rule["operator_id"]:
            continue
        if not any(service_name.startswith(prefix) for prefix in rule["service_name_prefixes"]):
            continue
        if not (train_station_names & set(rule["anchor_station_names"])):
            continue
        target_line = rule["target_line"]
        for stop in stops:
            if stop_name(stop) not in rule["station_names"]:
                continue
            group_id = stop_group_id(stop)
            physical_station_id = physical_station_id_for_line(group_id, target_line)
            if not physical_station_id or stop.get("physical_station_id") == physical_station_id:
                continue
            stop["physical_station_id"] = physical_station_id
            stop["line_name"] = target_line[1]
            stop["match_method"] = f"{stop.get('match_method') or 'matched'}+reviewed_through_physical"
            rematched_count += 1

    return stops, rematched_count


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
    stats = {
        "skipped_short": 0,
        "skipped_no_route": 0,
        "skipped_mislabeled_foreign_train": 0,
        "rematched_ambiguous_stop_group": 0,
        "rematched_reviewed_through_stop_group": 0,
        "rematched_reviewed_through_physical_station": 0,
        "remapped_shinkansen_labelled_trip": 0,
    }
    seen_ids: set[str] = set()
    reviewed_physical_lines_by_group: dict[str, set[tuple[str, str]]] = defaultdict(set)
    physical_station_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    physical_name_by_group: dict[str, str] = {}
    groups_by_station_name: dict[str, set[str]] = defaultdict(set)
    for station in physical_station_by_id.values():
        group_id = station.get("stationGroupId")
        if group_id:
            physical_station_by_group[str(group_id)].append(station)
        if group_id and station.get("nameJa"):
            physical_name_by_group.setdefault(group_id, station.get("nameJa"))
            groups_by_station_name[normalize_station_name(station.get("nameJa"))].add(str(group_id))
        line_name = station.get("lineName")
        if not group_id or not line_name:
            continue
        physical_operator_id = str(station.get("operatorId") or name_to_id.get(station.get("operatorName") or "") or "")
        if physical_operator_id:
            reviewed_physical_lines_by_group[group_id].add((physical_operator_id, line_name))
    for index, train in enumerate(trains):
        if should_skip_mislabeled_foreign_train(train):
            stats["skipped_mislabeled_foreign_train"] += 1
            continue
        raw_stop_times, rematched_count = rematch_ambiguous_stop_groups(
            train.get("stop_times") or [],
            groups_by_station_name,
            physical_station_by_group,
            reviewed_physical_lines_by_group,
        )
        stats["rematched_ambiguous_stop_group"] += rematched_count
        raw_stop_times, reviewed_rematched_count = rematch_reviewed_through_stop_groups(
            raw_stop_times,
            train,
            groups_by_station_name,
            physical_station_by_group,
            reviewed_physical_lines_by_group,
        )
        stats["rematched_reviewed_through_stop_group"] += reviewed_rematched_count
        raw_stop_times, reviewed_physical_rematched_count = rematch_reviewed_through_physical_stations(
            raw_stop_times,
            train,
            physical_station_by_group,
        )
        stats["rematched_reviewed_through_physical_station"] += reviewed_physical_rematched_count
        train_for_build = {**train, "stop_times": raw_stop_times}
        shinkansen_override = reviewed_shinkansen_route_override_for_train(train_for_build, physical_station_by_id)
        if shinkansen_override:
            train_for_build.update(shinkansen_override)
            stats["remapped_shinkansen_labelled_trip"] += 1
        operator_id, line_name = route_key_for_train(train_for_build, name_to_id, id_to_name, physical_station_by_id)
        if not operator_id or not line_name:
            stats["skipped_no_route"] += 1
            continue
        route_id = route_id_for(operator_id, line_name)
        stop_times = collapse_consecutive_duplicate_stops(
            normalize_trip_stop_times(raw_stop_times, valid_station_group_ids, physical_station_by_id)
        )
        if len(stop_times) < 2:
            stats["skipped_short"] += 1
            continue
        base_id = train.get("service_instance_id") or train.get("source_trip_id") or f"v4-trip-{index}"
        trip_id = str(base_id)
        if trip_id in seen_ids:
            trip_id = f"{trip_id}#{stable_hash(str(index), 6)}"
        seen_ids.add(trip_id)
        station_group_ids = [stop["stationGroupId"] for stop in stop_times]
        line_trace, line_sequence = build_line_trace(
            raw_stop_times,
            stop_times,
            train_for_build,
            physical_station_by_id,
            name_to_id,
            id_to_name,
            operator_id,
            line_name,
            reviewed_physical_lines_by_group,
            physical_name_by_group,
        )
        service_name = public_service_name_for_train(train_for_build, line_name)
        service_name = through_destination_service_name(service_name, operator_id, line_name, line_trace, id_to_name)
        attach_stop_route_identity(stop_times, line_trace, route_id)
        if not line_trace:
            route_station_groups[route_id].update(station_group_ids)
            line_station_groups[(operator_id, line_name)].update(station_group_ids)
        for trace in line_trace:
            trace_route_id = trace["routeId"]
            traced_station_ids = [
                stop["stationGroupId"]
                for stop in stop_times
                if trace["fromSequence"] <= stop["sequence"] <= trace["toSequence"]
            ]
            route_station_groups[trace_route_id].update(traced_station_ids)
            line_station_groups[(trace["operatorId"], trace["lineName"])].update(traced_station_ids)
        for stop in raw_stop_times:
            station_group_id = stop.get("station_group_id") or stop.get("station_id")
            stop_operator_id, stop_line_name = physical_route_key_for_stop(
                stop,
                train_for_build,
                physical_station_by_id,
                name_to_id,
                id_to_name,
            ) or (operator_id, line_name)
            if station_group_id and station_group_id in valid_station_group_ids:
                if not line_trace or (stop_operator_id, stop_line_name) == (operator_id, line_name):
                    line_station_groups[(operator_id, line_name)].add(station_group_id)
                line_station_groups[(stop_operator_id, stop_line_name)].add(station_group_id)
        trip_instances.append(
            {
                "id": trip_id,
                "routeId": route_id,
                "serviceName": service_name,
                "serviceNameJa": service_name,
                "displayName": gameplay_display_name_for_train(train_for_build, id_to_name.get(operator_id, operator_id)),
                "routeName": gameplay_route_name_for_train(train_for_build, id_to_name.get(operator_id, operator_id)),
                "coupledRouteNames": train_for_build.get("coupled_route_names") or train_for_build.get("coupledRouteNames") or [],
                "serviceNumber": train_for_build.get("service_number") or train_for_build.get("train_number") or "",
                "publicServiceNumber": train_for_build.get("service_number") or train_for_build.get("train_number") or "",
                "operatingNumber": train_for_build.get("train_number") or train_for_build.get("service_number") or "",
                "headsign": train_for_build.get("headsign") or train_for_build.get("destination") or "",
                "origin": train_for_build.get("origin"),
                "destination": train_for_build.get("destination"),
                "sourceTripId": train_for_build.get("source_trip_id"),
                "sourceFeedKey": train_for_build.get("source_feed_key"),
                "lineTrace": line_trace,
                "lineSequence": line_sequence,
                "stopTimes": stop_times,
            }
        )
    trip_instances, deduped_duplicate_count = dedupe_gameplay_trip_instances(trip_instances)
    stats["deduped_duplicate_trip"] = deduped_duplicate_count
    trip_instances, deduped_overlapping_source_count = dedupe_overlapping_source_trip_instances(trip_instances)
    stats["deduped_overlapping_source_trip"] = deduped_overlapping_source_count
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
    route_names = sorted({trip.get("routeName") or "" for trip in trip_instances})
    coupled_route_names = sorted(
        {
            name
            for trip in trip_instances
            for name in (trip.get("coupledRouteNames") or [])
            if name
        }
    )
    station_index = {value: index for index, value in enumerate(station_group_ids)}
    route_index = {value: index for index, value in enumerate(route_ids)}
    service_index = {value: index for index, value in enumerate(service_names)}
    display_index = {value: index for index, value in enumerate(display_names)}
    headsign_index = {value: index for index, value in enumerate(headsigns)}
    route_name_index = {value: index for index, value in enumerate(route_names)}
    coupled_route_name_index = {value: index for index, value in enumerate(coupled_route_names)}
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
                route_name_index[trip.get("routeName") or ""],
                [coupled_route_name_index[name] for name in (trip.get("coupledRouteNames") or []) if name in coupled_route_name_index],
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
        "routeNames": route_names,
        "coupledRouteNames": coupled_route_names,
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
    skipped_train_count = sum(
        count
        for key, count in train_stats.items()
        if key.startswith("skipped_")
    )
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
            "skippedTrainCount": skipped_train_count,
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
