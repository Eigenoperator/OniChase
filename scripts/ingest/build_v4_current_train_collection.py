#!/usr/bin/env python3
"""Build the current best v4 train collection from available sources.

The collection currently combines:
- frozen v3 timetable data rematched to v4 station_identity_v2;
- v4 JR company collectors, where available, for nationwide JR expansion;
- new v4 public GTFS/GTFS-JP feeds for operators not already covered by v3.

This avoids double-counting sources such as Toei, which exists in both the v3
release corpus and the public ODPT GTFS collector.  JR company collector
service ids are source-prefixed, so they can coexist with the frozen v3 Tokyo
and Shinkansen corpus while filling the nationwide conventional-line gaps.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_V3_ADAPTED = ROOT / "data" / "v4_existing_v3_weekday_train_instances.json.gz"
DEFAULT_V4_GTFS = ROOT / "data" / "v4_gtfs_weekday_train_instances.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_current_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_current_train_collection_audit.json"
MAX_STOP_MATCH_DISTANCE_M = 1500.0
MAX_DIRECT_CONTEXT_MATCH_DISTANCE_M = 30000.0
DEFAULT_EXTRA_COLLECTIONS = [
    ROOT / "data" / "v4_jreast_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_jreast_tohoku_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_jreast_joban_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_jreast_core_gap_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_jreast_residual_gap_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_jrcentral_navitime_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_jrwest_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_jrhokkaido_vtime_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_jrshikoku_navitime_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_jrkyushu_navitime_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_kintetsu_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_meitetsu_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_yuirail_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_hankyu_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_nankai_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_osaka_metro_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_iyotetsu_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_keihan_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_nagoya_subway_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_hiroden_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_shintetsu_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_kobe_subway_official_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_navitime_non_jr_weekday_train_instances.json.gz",
    ROOT / "data" / "v4_special_manual_weekday_train_instances.json.gz",
]

V3_COVERED_OPERATOR_NAMES = {
    "JR Shinkansen",
    "ゆりかもめ",
    "京成電鉄",
    "京浜急行電鉄",
    "京王電鉄",
    "多摩都市モノレール",
    "小田急電鉄",
    "東京都",
    "東京地下鉄",
    "東京モノレール",
    "東京臨海高速鉄道",
    "東急電鉄",
    "東日本旅客鉄道",
    "東武鉄道",
    "東海旅客鉄道",
    "西武鉄道",
    "首都圏新都市鉄道",
}


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collection_label(path: Path, payload: dict[str, Any]) -> str:
    return str(payload.get("id") or path.stem.replace("_weekday_train_instances", ""))


def stop_station_key(stop: dict[str, Any]) -> str:
    return str(
        stop.get("station_group_id")
        or stop.get("stationGroupId")
        or stop.get("station_id")
        or stop.get("stationId")
        or stop.get("station_name")
        or stop.get("stationName")
        or stop.get("name")
        or ""
    )


ROUTE_LIKE_TRAIN_IDENTITY_RE = re.compile(
    r"^(?:普通|各停|各駅停車|快速|新快速|区間快速|通勤快速|直通快速|急行|準急|特急|快特|快速特急|通勤特急)?"
    r".*(?:線|本線|鉄道|電鉄|系統|行き|方面)(?:[（(].+[）)])?$"
)
ORDINARY_TRAIN_IDENTITY_LABELS = {
    "普通", "各停", "各駅停車", "快速", "新快速", "区間快速", "通勤快速", "直通快速",
    "急行", "準急", "特急", "快特", "快速特急", "通勤特急",
}


def normalize_train_identity_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", "", text)
    return text.replace("（", "(").replace("）", ")")


def public_train_identity(train: dict[str, Any]) -> str:
    """Return the source-independent identity passengers would use for this train.

    NAVITIME and official sources often assign different internal train numbers
    to the same cross-line physical train.  The public display name is more
    stable for those rows, while ordinary route-like labels still fall back to
    the source train number to avoid collapsing unrelated local services.
    """

    for key in ("display_name", "service_name_detail", "displayName"):
        value = normalize_train_identity_text(train.get(key))
        if not value:
            continue
        route_like_values = {
            normalize_train_identity_text(train.get("operator_name")),
            normalize_train_identity_text(train.get("operator_id")),
            normalize_train_identity_text(train.get("line_name")),
            normalize_train_identity_text(train.get("service_name")),
        }
        if (
            value in ORDINARY_TRAIN_IDENTITY_LABELS
            or
            value in route_like_values
            or ROUTE_LIKE_TRAIN_IDENTITY_RE.match(value)
        ) and not re.search(r"\d{1,4}号", value):
            continue
        return value
    return normalize_train_identity_text(
        train.get("train_number")
        or train.get("service_number")
        or train.get("service_name")
        or train.get("line_name")
    )


def train_signature(train: dict[str, Any]) -> str:
    """A source-independent signature for one real train movement.

    Service ids intentionally differ between collectors, so current collection
    dedupe must compare the operator, train number/name, station sequence, and
    stop times instead.
    """

    hasher = hashlib.sha1()
    display_name = str(train.get("display_name") or train.get("service_name_detail") or "")
    if reviewed_direct_service_allowed_context_stops(train) is not None:
        for part in (
            train.get("operator_id") or train.get("operator_name") or "",
            public_train_identity(train),
        ):
            hasher.update(str(part).encode("utf-8"))
            hasher.update(b"\0")
        return hasher.hexdigest()
    parts = (
        train.get("operator_id") or train.get("operator_name") or "",
        public_train_identity(train),
    )
    for part in parts:
        hasher.update(str(part).encode("utf-8"))
        hasher.update(b"\0")
    for stop in train.get("stop_times") or []:
        hasher.update(stop_station_key(stop).encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(stop.get("arrival_hhmm") or stop.get("arrival_time") or stop.get("arrivalTime") or "").encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(stop.get("departure_hhmm") or stop.get("departure_time") or stop.get("departureTime") or "").encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def source_priority(source_collection: str) -> int:
    if source_collection.startswith("v4_jr"):
        return 0
    if source_collection == "v3_rematched_to_v4":
        return 1
    if source_collection == "v4_public_gtfs":
        return 2
    return 3


def stop_has_time(stop: dict[str, Any]) -> bool:
    return bool(
        stop.get("arrival_time")
        or stop.get("arrivalTime")
        or stop.get("arrival_hhmm")
        or stop.get("departure_time")
        or stop.get("departureTime")
        or stop.get("departure_hhmm")
    )


def excessive_match_distance_ref(stop: dict[str, Any]) -> float | None:
    value = stop.get("match_distance_m")
    if value in (None, ""):
        return None
    try:
        distance = float(value)
    except (TypeError, ValueError):
        return None
    if distance > MAX_STOP_MATCH_DISTANCE_M:
        return distance
    return None


def unresolved_station_ref(stop: dict[str, Any]) -> str | None:
    for key in ("physical_station_id", "station_id", "stationId", "station_group_id", "stationGroupId"):
        value = stop.get(key)
        if isinstance(value, str) and value.startswith(("JREAST_UNMATCHED", "UNMATCHED")):
            return value
    return None


def invalid_train_reason(train: dict[str, Any]) -> str | None:
    stops = train.get("stop_times") or []
    if len(stops) < 2:
        return "short_train"
    if is_known_v3_synthetic_tail_duplicate(train):
        return "v3_synthetic_tail_duplicate"
    if has_reviewed_closed_operator_foreign_stops(train):
        return "closed_operator_foreign_physical_stop"
    if is_probable_navitime_source_pollution(train):
        return "source_pollution_low_target_line_touch"
    if any(unresolved_station_ref(stop) for stop in stops):
        return "unmatched_station_ref"
    if any(excessive_match_distance_ref(stop) is not None for stop in stops) and not is_valid_direct_service_context_match(train):
        return "excessive_station_match_distance"
    if not any(stop_has_time(stop) for stop in stops):
        return "all_stop_times_missing"
    return None


def stop_display_name(stop: dict[str, Any]) -> str:
    return str(stop.get("station_name_raw") or stop.get("station_name") or stop.get("stationName") or stop.get("name") or "")


def is_known_v3_synthetic_tail_duplicate(train: dict[str, Any]) -> bool:
    if train.get("source_collection") != "v3_rematched_to_v4":
        return False
    if train.get("operator_id") != "jr_east":
        return False
    if train.get("line_name") not in {"JR_NARITA", "JR_SOTOBO"}:
        return False
    station_names = {stop_display_name(stop) for stop in train.get("stop_times") or []}
    return bool(station_names) and station_names <= {"津田沼", "稲毛", "千葉"}


def normalize_reviewed_current_line_fields(train: dict[str, Any]) -> None:
    if train.get("source_collection") != "v3_rematched_to_v4":
        return
    if train.get("operator_name") == "JR Shinkansen" and train.get("line_name") == "SHINKANSEN_AKITA":
        service_name = str(train.get("service_name") or train.get("display_name") or "")
        if service_name.lower() == "hayabusa":
            train["line_name"] = "SHINKANSEN_TOHOKU_HOKKAIDO"
            train["line_id"] = "SHINKANSEN_TOHOKU_HOKKAIDO"


def train_target_line_touch_count(train: dict[str, Any]) -> int:
    line_name = str(train.get("line_name") or train.get("service_name") or "")
    touch_counts = train.get("service_line_touch_counts") or {}
    if isinstance(touch_counts, dict) and line_name in touch_counts:
        try:
            return int(touch_counts[line_name] or 0)
        except (TypeError, ValueError):
            pass
    operator_name = str(train.get("operator_name") or train.get("operator_id") or "")
    touched_ids = {
        str(stop.get("physical_station_id") or "")
        for stop in train.get("stop_times") or []
        if str(stop.get("physical_operator_name") or "") == operator_name
        and (not line_name or str(stop.get("physical_line_name") or "") == line_name)
        and stop.get("physical_station_id")
    }
    if touched_ids:
        return len(touched_ids)
    return sum(
        1
        for stop in train.get("stop_times") or []
        if str(stop.get("match_method") or "").startswith(("operator_line_", "operator_name_"))
    )


def train_target_line_touch_ratio(train: dict[str, Any]) -> float:
    stop_count = len(train.get("stop_times") or [])
    if stop_count <= 0:
        return 0.0
    return train_target_line_touch_count(train) / stop_count


def train_has_foreign_physical_operator(train: dict[str, Any]) -> bool:
    operator_name = str(train.get("operator_name") or train.get("operator_id") or "")
    return any(
        stop.get("physical_operator_name")
        and str(stop.get("physical_operator_name")) != operator_name
        for stop in train.get("stop_times") or []
    )


def is_probable_navitime_source_pollution(train: dict[str, Any]) -> bool:
    """Reject nationwide NAVITIME fallback rows that barely touch the target line.

    NAVITIME pages for generic names such as "本線" can leak trains from nearby
    or similarly named companies into another operator's scrape.  A real
    through-service should have a meaningful footprint on the target line; a
    polluted row usually only matches one or two duplicate station names.
    """

    if not str(train.get("source_collection") or train.get("source_feed_key") or "").startswith("v4_navitime_non_jr"):
        return False
    if not train_has_foreign_physical_operator(train):
        return False
    if train_target_line_touch_count(train) <= 2:
        service_text = str(train.get("service_name_detail") or train.get("display_name") or "")
        if service_text and not any(token in service_text for token in (str(train.get("line_name") or ""), str(train.get("operator_name") or ""))):
            return True
    if train_target_line_touch_count(train) >= 2 and train_target_line_touch_ratio(train) >= 0.18:
        return False
    return True


def is_valid_direct_service_context_match(train: dict[str, Any]) -> bool:
    if is_known_direct_service_context_match(train):
        return True
    return is_probable_through_service_context_match(train)


def is_probable_through_service_context_match(train: dict[str, Any]) -> bool:
    """Allow nationwide direct services whose boundary stops are context-matched."""

    source_collection = str(train.get("source_collection") or "")
    excessive_stops = [
        stop for stop in train.get("stop_times") or []
        if excessive_match_distance_ref(stop) is not None
    ]
    if not excessive_stops:
        return False
    if max(float(excessive_match_distance_ref(stop) or 0) for stop in excessive_stops) > MAX_DIRECT_CONTEXT_MATCH_DISTANCE_M:
        return False
    context_matches = all(
        stop.get("match_method") == "context_nearest_group"
        and stop.get("station_group_id")
        for stop in excessive_stops
    )
    if not context_matches:
        return False
    if source_collection.startswith("v4_jr") and not train_has_foreign_physical_operator(train):
        return True
    if train_target_line_touch_count(train) < 2:
        return False
    if train_target_line_touch_ratio(train) < 0.18:
        return False
    if not train_has_foreign_physical_operator(train) and not source_collection.startswith("v4_jr"):
        return False
    return True


def has_reviewed_closed_operator_foreign_stops(train: dict[str, Any]) -> bool:
    """Reject reviewed closed-network trains that matched stops on foreign rails."""

    operator_name = str(train.get("operator_name") or train.get("operator_id") or "")
    line_name = str(train.get("line_name") or train.get("service_name") or "")
    reviewed_closed_lines = {
        ("横浜市", "1号線"),
        ("横浜市", "3号線"),
        ("横浜市", "4号線"),
    }
    if (operator_name, line_name) not in reviewed_closed_lines:
        return False
    return any(
        stop.get("physical_operator_name")
        and stop.get("physical_operator_name") != operator_name
        for stop in train.get("stop_times") or []
    )


def is_known_direct_service_context_match(train: dict[str, Any]) -> bool:
    """Allow reviewed JR East direct services whose boundary stops are context-matched.

    JR East official pages for named limited express services can be collected
    under one physical line while still stopping at reviewed boundary stations
    on another physical line.  Those boundary stops are resolved by neighboring
    context and can carry a large match distance.  That is a legitimate
    direct-service stop, not a bad station match.
    """

    allowed_stops = reviewed_direct_service_allowed_context_stops(train)
    if not allowed_stops:
        return False
    return all(
        excessive_match_distance_ref(stop) is None
        or (
            stop.get("match_method") == "context_nearest_group"
            and stop.get("station_name_raw") in allowed_stops
            and stop.get("station_group_id")
        )
        for stop in train.get("stop_times") or []
    )


def reviewed_direct_service_allowed_context_stops(train: dict[str, Any]) -> set[str] | None:
    if train.get("operator_id") != "jr_east":
        return None
    display_name = str(train.get("display_name") or train.get("service_name_detail") or "")
    rules = {
        "ひたち ": {"品川", "東京", "上野"},
        "ときわ ": {"品川", "東京", "上野"},
        "成田エクスプレス ": {"東京", "武蔵小杉"},
        "あずさ ": {"東京"},
        "かいじ ": {"東京"},
        "わかしお ": {"東京"},
        "さざなみ ": {"東京"},
        "踊り子 ": {"東京"},
        "サフィール踊り子 ": {"東京"},
        "しらゆき ": {"新井", "高田"},
    }
    for prefix, allowed_stops in rules.items():
        if display_name.startswith(prefix):
            return allowed_stops
    return None


def choose_best_train(current: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
    if current is None:
        return candidate
    current_priority = source_priority(str(current.get("source_collection") or ""))
    candidate_priority = source_priority(str(candidate.get("source_collection") or ""))
    if candidate_priority != current_priority:
        return candidate if candidate_priority < current_priority else current
    current_stop_count = len(current.get("stop_times") or [])
    candidate_stop_count = len(candidate.get("stop_times") or [])
    if candidate_stop_count != current_stop_count:
        return candidate if candidate_stop_count > current_stop_count else current
    return min([current, candidate], key=lambda item: str(item.get("service_instance_id") or ""))


def dedupe_trains(trains: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_signature: dict[str, dict[str, Any]] = {}
    signature_counts: Counter[str] = Counter()
    duplicate_groups_by_signature: dict[str, list[str]] = {}
    for train in trains:
        signature = train_signature(train)
        signature_counts[signature] += 1
        if signature_counts[signature] == 2:
            duplicate_groups_by_signature[signature] = [
                str(by_signature[signature].get("service_instance_id") or "")
            ]
        if signature in duplicate_groups_by_signature and len(duplicate_groups_by_signature[signature]) < 20:
            duplicate_groups_by_signature[signature].append(str(train.get("service_instance_id") or ""))
        by_signature[signature] = choose_best_train(by_signature.get(signature), train)

    duplicate_group_count = sum(1 for count in signature_counts.values() if count > 1)
    duplicate_row_count = sum(count - 1 for count in signature_counts.values() if count > 1)
    deduped = sorted(by_signature.values(), key=lambda item: item["service_instance_id"])
    return deduped, {
        "duplicateSignatureGroupCount": duplicate_group_count,
        "duplicateSignatureRowCount": duplicate_row_count,
        "duplicateSignatureSample": list(duplicate_groups_by_signature.values())[:20],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v3-adapted", type=Path, default=DEFAULT_V3_ADAPTED)
    parser.add_argument("--v4-gtfs", type=Path, default=DEFAULT_V4_GTFS)
    parser.add_argument(
        "--extra-collection",
        type=Path,
        action="append",
        default=None,
        help=(
            "Additional train collection to merge. Can be provided multiple times. "
            "Defaults to the current v4 JR company collectors."
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    v3_data = load_json(args.v3_adapted)
    gtfs_data = load_json(args.v4_gtfs)
    extra_paths = args.extra_collection if args.extra_collection is not None else DEFAULT_EXTRA_COLLECTIONS
    trains: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    dropped_invalid_counts: Counter[str] = Counter()
    dropped_invalid_by_source: Counter[str] = Counter()
    dropped_invalid_by_source_reason: Counter[str] = Counter()
    dropped_invalid_samples: list[dict[str, str]] = []
    excluded_gtfs_counts: Counter[str] = Counter()
    skipped_extra_collections: list[str] = []

    def record_invalid_train(item: dict[str, Any], label: str, reason: str) -> None:
        dropped_invalid_counts[reason] += 1
        dropped_invalid_by_source[label] += 1
        dropped_invalid_by_source_reason[f"{label}|{reason}"] += 1
        if len(dropped_invalid_samples) < 40:
            sample = {
                "serviceInstanceId": str(item.get("service_instance_id")),
                "sourceCollection": label,
                "reason": reason,
            }
            excessive_distances = [
                float(stop.get("match_distance_m"))
                for stop in item.get("stop_times", [])
                if excessive_match_distance_ref(stop) is not None
            ]
            if excessive_distances:
                sample["maxMatchDistanceM"] = f"{max(excessive_distances):.1f}"
            dropped_invalid_samples.append(sample)

    for train in v3_data["train_instances"]:
        item = dict(train)
        item["source_collection"] = "v3_rematched_to_v4"
        normalize_reviewed_current_line_fields(item)
        reason = invalid_train_reason(item)
        if reason:
            record_invalid_train(item, "v3_rematched_to_v4", reason)
        else:
            trains.append(item)
            source_counts["v3_rematched_to_v4"] += 1

    for path in extra_paths:
        if not path.exists():
            skipped_extra_collections.append(str(path))
            continue
        payload = load_json(path)
        label = collection_label(path, payload)
        for train in payload["train_instances"]:
            item = dict(train)
            item["source_collection"] = label
            normalize_reviewed_current_line_fields(item)
            reason = invalid_train_reason(item)
            if reason:
                record_invalid_train(item, label, reason)
            else:
                trains.append(item)
                source_counts[label] += 1

    for train in gtfs_data["train_instances"]:
        operator_name = train.get("operator_name")
        if operator_name in V3_COVERED_OPERATOR_NAMES:
            excluded_gtfs_counts[str(operator_name)] += 1
            continue
        item = dict(train)
        item["source_collection"] = "v4_public_gtfs"
        normalize_reviewed_current_line_fields(item)
        reason = invalid_train_reason(item)
        if reason:
            record_invalid_train(item, "v4_public_gtfs", reason)
        else:
            trains.append(item)
            source_counts["v4_public_gtfs"] += 1

    raw_train_count = len(trains)
    trains, signature_audit = dedupe_trains(trains)

    ids = [train["service_instance_id"] for train in trains]
    id_counts = Counter(ids)
    duplicate_ids = sorted(train_id for train_id, count in id_counts.items() if count > 1)
    operator_counts = Counter(str(train.get("operator_name")) for train in trains)
    short_count = sum(1 for train in trains if len(train.get("stop_times") or []) < 2)

    output = {
        "id": "v4_current_weekday_train_instances_v0_1",
        "label": "Current best v4 weekday train collection",
        "version": "0.1.0",
        "sources": [
            str(args.v3_adapted),
            *[str(path) for path in extra_paths],
            str(args.v4_gtfs),
        ],
        "train_instances": sorted(trains, key=lambda item: item["service_instance_id"]),
    }
    audit = {
        "schema": "onichase.v4.current_train_collection_audit.v1",
        "sourceCounts": dict(sorted(source_counts.items())),
        "droppedInvalidTrainCounts": dict(sorted(dropped_invalid_counts.items())),
        "droppedInvalidTrainCountsBySource": dict(sorted(dropped_invalid_by_source.items())),
        "droppedInvalidTrainCountsBySourceReason": dict(sorted(dropped_invalid_by_source_reason.items())),
        "droppedInvalidTrainSamples": dropped_invalid_samples,
        "rawTrainInstanceCount": raw_train_count,
        "trainInstanceCount": len(trains),
        "operatorTrainCounts": dict(sorted(operator_counts.items())),
        "excludedGtfsOperatorCounts": dict(sorted(excluded_gtfs_counts.items())),
        "skippedExtraCollections": skipped_extra_collections,
        "duplicateServiceInstanceIdCount": len(duplicate_ids),
        "duplicateServiceInstanceIdsSample": duplicate_ids[:20],
        **signature_audit,
        "shortTrainInstanceCount": short_count,
    }
    write_json(args.output, output)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(trains)} trains")
    print(
        f"Wrote {args.audit_output}: duplicate_ids={len(duplicate_ids)} "
        f"duplicate_signatures={signature_audit['duplicateSignatureGroupCount']} short={short_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
