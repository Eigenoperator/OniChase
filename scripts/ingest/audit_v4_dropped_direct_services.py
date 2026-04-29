#!/usr/bin/env python3
"""Audit trains dropped by the current v4 merge as possible direct services.

The current collection intentionally rejects trains with unresolved station
refs or very large station-match distances.  Some reviewed direct services,
however, cross physical-line boundaries and can have legitimate context
matches at boundary stations.  This audit makes those drops visible and groups
them by train name/line so we can add narrow exceptions instead of discovering
coverage holes from screenshots.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ingest"))

import build_v4_current_train_collection as current_merge  # noqa: E402


DEFAULT_OUTPUT = ROOT / "data" / "v4_dropped_direct_service_audit.json"

GENERIC_SERVICE_WORDS = {
    "",
    "普通",
    "快速",
    "急行",
    "特急",
    "準急",
    "区間急行",
    "区間準急",
    "各停",
    "各駅停車",
}


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collection_label(path: Path, payload: dict[str, Any]) -> str:
    return current_merge.collection_label(path, payload)


def display_name(train: dict[str, Any]) -> str:
    return str(train.get("display_name") or train.get("service_name_detail") or train.get("service_name") or "").strip()


def service_base_name(train: dict[str, Any]) -> str:
    text = display_name(train)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(?:特急|快速特急|通勤特急|急行|快速|普通|各停|各駅停車)\s*", "", text)
    text = re.sub(r"\s*\d{1,4}(?:号|列車)?(?:\s|$).*$", "", text).strip()
    text = re.sub(r"\s+.+行き$", "", text).strip()
    return text


def is_named_or_limited(train: dict[str, Any]) -> bool:
    train_type = str(train.get("train_type") or "")
    base = service_base_name(train)
    if "特急" in train_type or "ライナー" in train_type:
        return True
    if base and base not in GENERIC_SERVICE_WORDS and not base.endswith("線"):
        return True
    return False


def stop_name(stop: dict[str, Any]) -> str:
    return str(stop.get("station_name_raw") or stop.get("station_name") or stop.get("stationName") or "")


def first_last(train: dict[str, Any]) -> tuple[str, str]:
    stops = train.get("stop_times") or []
    if not stops:
        return "", ""
    return stop_name(stops[0]), stop_name(stops[-1])


def excessive_stops(train: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for stop in train.get("stop_times") or []:
        distance = current_merge.excessive_match_distance_ref(stop)
        if distance is None:
            continue
        rows.append(
            {
                "station": stop_name(stop),
                "stationGroupId": stop.get("station_group_id") or stop.get("stationGroupId"),
                "matchMethod": stop.get("match_method"),
                "distanceMeters": round(distance, 1),
            }
        )
    return rows


def train_number(train: dict[str, Any]) -> str:
    return str(train.get("train_number") or train.get("service_number") or "")


def service_key(train: dict[str, Any]) -> str:
    text = display_name(train)
    match = re.search(r"(.+?\s*\d{1,4}(?:号|列車)?)", text)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    base = service_base_name(train)
    number = train_number(train)
    return f"{base} {number}".strip()


def add_sample(samples: list[dict[str, Any]], sample: dict[str, Any], limit: int = 20) -> None:
    if len(samples) < limit:
        samples.append(sample)


def current_base_stats(current_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    counts: Counter[str] = Counter()
    keys_by_base: dict[str, set[str]] = defaultdict(set)
    for train in current_payload.get("train_instances") or []:
        base = service_base_name(train)
        if base and base not in GENERIC_SERVICE_WORDS:
            counts[base] += 1
            key = service_key(train)
            if key:
                keys_by_base[base].add(key)
    return {
        base: {
            "count": counts[base],
            "serviceKeys": sorted(keys_by_base.get(base, set())),
        }
        for base in sorted(counts)
    }


def source_paths(args: argparse.Namespace) -> list[Path]:
    if args.source:
        return args.source
    return [
        args.v3_adapted,
        *current_merge.DEFAULT_EXTRA_COLLECTIONS,
        args.v4_gtfs,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, default=current_merge.DEFAULT_OUTPUT)
    parser.add_argument("--v3-adapted", type=Path, default=current_merge.DEFAULT_V3_ADAPTED)
    parser.add_argument("--v4-gtfs", type=Path, default=current_merge.DEFAULT_V4_GTFS)
    parser.add_argument("--source", type=Path, action="append", help="Audit a specific source collection. Repeatable.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    current_payload = load_json(args.current)
    current_stats = current_base_stats(current_payload)

    dropped_reason_counts: Counter[str] = Counter()
    excessive_by_source: Counter[str] = Counter()
    excessive_by_group: dict[str, dict[str, Any]] = {}
    named_excessive_count = 0
    suspicious_groups: list[dict[str, Any]] = []
    dropped_samples: list[dict[str, Any]] = []

    for path in source_paths(args):
        if not path.exists():
            continue
        payload = load_json(path)
        label = collection_label(path, payload) if isinstance(payload, dict) else str(path)
        for raw_train in payload.get("train_instances") or []:
            train = dict(raw_train)
            train["source_collection"] = label
            reason = current_merge.invalid_train_reason(train)
            if not reason:
                continue
            dropped_reason_counts[reason] += 1
            if reason != "excessive_station_match_distance":
                continue
            excessive_by_source[label] += 1
            base = service_base_name(train)
            named_or_limited = is_named_or_limited(train)
            if named_or_limited:
                named_excessive_count += 1
            first, last = first_last(train)
            group_key = "|".join(
                [
                    label,
                    str(train.get("operator_name") or train.get("operator_id") or ""),
                    str(train.get("line_name") or train.get("service_name") or ""),
                    base or "(no named base)",
                ]
            )
            group = excessive_by_group.setdefault(
                group_key,
                {
                    "source": label,
                    "operatorName": train.get("operator_name") or train.get("operator_id"),
                    "lineName": train.get("line_name") or train.get("service_name"),
                    "baseName": base,
                    "count": 0,
                    "namedOrLimitedCount": 0,
                    "currentBaseCount": current_stats.get(base, {}).get("count", 0),
                    "sourceServiceKeys": set(),
                    "firstLastPairs": Counter(),
                    "excessiveStopNames": Counter(),
                    "samples": [],
                },
            )
            group["count"] += 1
            if named_or_limited:
                group["namedOrLimitedCount"] += 1
            group["firstLastPairs"][f"{first}->{last}"] += 1
            key = service_key(train)
            if key:
                group["sourceServiceKeys"].add(key)
            for stop in excessive_stops(train):
                group["excessiveStopNames"][stop["station"]] += 1
            add_sample(
                group["samples"],
                {
                    "serviceInstanceId": train.get("service_instance_id"),
                    "displayName": display_name(train),
                    "trainNumber": train_number(train),
                    "firstStation": first,
                    "lastStation": last,
                    "excessiveStops": excessive_stops(train)[:5],
                },
            )
            add_sample(
                dropped_samples,
                {
                    "source": label,
                    "serviceInstanceId": train.get("service_instance_id"),
                    "displayName": display_name(train),
                    "baseName": base,
                    "operatorName": train.get("operator_name") or train.get("operator_id"),
                    "lineName": train.get("line_name") or train.get("service_name"),
                    "firstStation": first,
                    "lastStation": last,
                    "excessiveStops": excessive_stops(train)[:5],
                },
                limit=80,
            )

    for group in excessive_by_group.values():
        source_keys = sorted(group.pop("sourceServiceKeys"))
        current_keys = set(current_stats.get(group["baseName"], {}).get("serviceKeys", []))
        missing_keys = [key for key in source_keys if key not in current_keys]
        group["sourceServiceKeyCount"] = len(source_keys)
        group["missingFromCurrentServiceKeyCount"] = len(missing_keys)
        group["missingFromCurrentServiceKeys"] = missing_keys[:80]
        group["firstLastPairs"] = dict(group["firstLastPairs"].most_common(20))
        group["excessiveStopNames"] = dict(group["excessiveStopNames"].most_common(20))
        if group["namedOrLimitedCount"] and group["baseName"]:
            suspicious_groups.append(group)

    suspicious_groups.sort(
        key=lambda item: (
            -int(item["namedOrLimitedCount"]),
            -int(item["count"]),
            str(item["source"]),
            str(item["baseName"]),
        )
    )

    audit = {
        "schema": "onichase.v4.dropped_direct_service_audit.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "current": str(args.current.relative_to(ROOT) if args.current.is_relative_to(ROOT) else args.current),
        "counts": {
            "droppedTrainCount": sum(dropped_reason_counts.values()),
            "excessiveStationMatchDroppedTrainCount": sum(excessive_by_source.values()),
            "namedOrLimitedExcessiveDroppedTrainCount": named_excessive_count,
            "suspiciousGroupCount": len(suspicious_groups),
        },
        "droppedReasonCounts": dict(sorted(dropped_reason_counts.items())),
        "excessiveStationMatchDroppedCountsBySource": dict(sorted(excessive_by_source.items())),
        "suspiciousGroups": suspicious_groups[:120],
        "samples": dropped_samples,
    }
    write_json(args.output, audit)
    print(
        f"Wrote {args.output}: excessive={audit['counts']['excessiveStationMatchDroppedTrainCount']} "
        f"named_or_limited={named_excessive_count} suspicious_groups={len(suspicious_groups)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
