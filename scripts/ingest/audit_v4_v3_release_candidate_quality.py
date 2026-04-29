#!/usr/bin/env python3
"""Audit v3_release_candidate train data that still participates in v4.

The frozen v3 corpus is useful coverage, but it came from a Tokyo-era station
identity model with broader station groups.  This audit highlights old-source
lines that remain in the current v4 collection and catches obvious rematch
pollution, such as a Tokyo Metro Chiyoda train starting at the v3 Shinjuku group
after being rematched onto the Marunouchi physical station.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_V3_ADAPTED = ROOT / "data" / "v4_existing_v3_weekday_train_instances.json.gz"
DEFAULT_CURRENT = ROOT / "data" / "v4_current_weekday_train_instances.json.gz"
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_v3_release_candidate_quality_audit.json"


EXPECTED_FIRST_STOP_LINE_NAMES: dict[tuple[str, str], set[str]] = {
    ("東京地下鉄", "9号線千代田線"): {"9号線千代田線", "小田原線", "常磐線"},
    ("東京地下鉄", "13号線副都心線"): {"13号線副都心線", "東横線", "みなとみらい21線", "東急新横浜線", "相鉄本線", "相鉄新横浜線", "池袋線", "東上本線"},
    ("東京地下鉄", "8号線有楽町線"): {"8号線有楽町線", "東横線", "みなとみらい21線", "西武有楽町線", "池袋線", "東上本線"},
    ("東京地下鉄", "7号線南北線"): {"7号線南北線", "目黒線", "埼玉高速鉄道線", "東急新横浜線", "相鉄本線", "相鉄新横浜線"},
    ("東京都", "6号線三田線"): {"6号線三田線", "目黒線", "東急新横浜線", "相鉄本線", "相鉄新横浜線"},
    ("東京都", "1号線浅草線"): {"1号線浅草線", "京急本線", "押上線", "京成本線", "北総線"},
    ("小田急電鉄", "小田急小田原線"): {"小田原線", "小田急小田原線", "9号線千代田線"},
    ("東日本旅客鉄道", "JR_EAST_SHONAN_SHINJUKU"): {"山手線", "東海道線", "横須賀線", "東北線", "高崎線"},
}

KNOWN_V3_REMATCH_ANOMALIES: dict[tuple[str, str, str, str], str] = {
    ("東京地下鉄", "9号線千代田線", "新宿", "4号線丸ノ内線"):
        "Chiyoda/Odakyu through-service inherited the broad v3 Shinjuku group and rematched onto the Marunouchi physical station.",
}

REVIEW_SAMPLE_LIMIT = 80


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def train_source(train: dict[str, Any]) -> str:
    return str(train.get("source_feed_key") or train.get("source_collection") or "")


def train_line_key(train: dict[str, Any]) -> tuple[str, str]:
    return str(train.get("operator_name") or ""), str(train.get("line_name") or "")


def stop_name(stop: dict[str, Any], station_group_names: dict[str, str]) -> str:
    return str(
        stop.get("station_name_raw")
        or station_group_names.get(str(stop.get("station_group_id") or stop.get("station_id") or ""))
        or stop.get("station_group_id")
        or stop.get("station_id")
        or ""
    )


def stop_departure(stop: dict[str, Any]) -> str:
    return str(stop.get("departure_hhmm") or stop.get("departure_time") or stop.get("arrival_hhmm") or "")


def summarize_train(train: dict[str, Any], station_group_names: dict[str, str]) -> dict[str, Any]:
    stops = train.get("stop_times") or []
    return {
        "serviceInstanceId": train.get("service_instance_id"),
        "operator": train.get("operator_name"),
        "line": train.get("line_name"),
        "service": train.get("service_name"),
        "headsign": train.get("headsign"),
        "sourceFeedKey": train.get("source_feed_key"),
        "sourceCollection": train.get("source_collection"),
        "firstDeparture": stop_departure(stops[0]) if stops else "",
        "firstStop": stop_name(stops[0], station_group_names) if stops else "",
        "firstStopLine": stops[0].get("line_name") if stops else "",
        "stopCount": len(stops),
        "stopSample": [
            {
                "station": stop_name(stop, station_group_names),
                "line": stop.get("line_name"),
                "departure": stop_departure(stop),
                "matchMethod": stop.get("match_method"),
                "matchDistanceM": stop.get("match_distance_m"),
                "sourceV3StationGroupId": stop.get("source_v3_station_group_id"),
            }
            for stop in stops[:12]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v3-adapted", type=Path, default=DEFAULT_V3_ADAPTED)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    v3_payload = load_json(args.v3_adapted)
    current_payload = load_json(args.current)
    physical_map = load_json(args.physical_map)
    station_group_names = {
        str(group["id"]): str(group.get("nameJa") or group.get("primaryName") or group["id"])
        for group in physical_map["stationGroups"]
    }

    v3_trains = [
        train for train in v3_payload["train_instances"]
        if train_source(train) == "v3_release_candidate"
    ]
    current_v3_trains = [
        train for train in current_payload["train_instances"]
        if train_source(train) == "v3_release_candidate" or train.get("source_collection") == "v3_rematched_to_v4"
    ]
    current_newer_trains = [
        train for train in current_payload["train_instances"]
        if not (train_source(train) == "v3_release_candidate" or train.get("source_collection") == "v3_rematched_to_v4")
    ]

    v3_by_line: Counter[tuple[str, str]] = Counter(train_line_key(train) for train in v3_trains)
    current_v3_by_line: Counter[tuple[str, str]] = Counter(train_line_key(train) for train in current_v3_trains)
    newer_by_operator: Counter[str] = Counter(str(train.get("operator_name") or "") for train in current_newer_trains)
    newer_by_line: Counter[tuple[str, str]] = Counter(train_line_key(train) for train in current_newer_trains)

    line_summaries = []
    for line_key, adapted_count in sorted(v3_by_line.items(), key=lambda item: (-item[1], item[0])):
        operator, line = line_key
        line_summaries.append({
            "operator": operator,
            "line": line,
            "adaptedV3TrainCount": adapted_count,
            "retainedInCurrentCount": current_v3_by_line.get(line_key, 0),
            "newerSameLineCurrentCount": newer_by_line.get(line_key, 0),
            "newerSameOperatorCurrentCount": newer_by_operator.get(operator, 0),
            "retentionReasonHint": (
                "covered_by_newer_same_line" if newer_by_line.get(line_key, 0)
                else "same_operator_has_newer_collection" if newer_by_operator.get(operator, 0)
                else "v3_only_current_coverage"
            ),
        })

    first_stop_anomalies = []
    first_stop_review_counts: Counter[str] = Counter()
    first_stop_review_samples: list[dict[str, Any]] = []
    downstream_wrong_origin_counts: Counter[str] = Counter()
    downstream_wrong_origin_samples: list[dict[str, Any]] = []
    for train in current_v3_trains:
        stops = train.get("stop_times") or []
        if not stops:
            continue
        operator, line = train_line_key(train)
        first = stops[0]
        first_station = stop_name(first, station_group_names)
        first_line = str(first.get("line_name") or "")
        anomaly_key = (operator, line, first_station, first_line)
        if anomaly_key in KNOWN_V3_REMATCH_ANOMALIES:
            first_stop_anomalies.append({
                "reason": KNOWN_V3_REMATCH_ANOMALIES[anomaly_key],
                **summarize_train(train, station_group_names),
            })
            continue
        expected_first_lines = EXPECTED_FIRST_STOP_LINE_NAMES.get((operator, line))
        if expected_first_lines and first_line and first_line not in expected_first_lines:
            first_stop_review_counts[f"{operator}|{line}|{first_station}|{first_line}"] += 1
            if len(first_stop_review_samples) < REVIEW_SAMPLE_LIMIT:
                first_stop_review_samples.append({
                    "reason": "first_stop_line_outside_expected_set",
                    "expectedFirstStopLines": sorted(expected_first_lines),
                    **summarize_train(train, station_group_names),
                })

        stop_names = [stop_name(stop, station_group_names) for stop in stops]
        if operator == "東京地下鉄" and line == "9号線千代田線" and "新宿" in stop_names:
            downstream_wrong_origin_counts["tokyo_metro_chiyoda_contains_shinjuku"] += 1
            if len(downstream_wrong_origin_samples) < REVIEW_SAMPLE_LIMIT:
                downstream_wrong_origin_samples.append({
                    "reason": "tokyo_metro_chiyoda_contains_shinjuku",
                    **summarize_train(train, station_group_names),
                })

    hard_anomaly_count = len(first_stop_anomalies) + sum(downstream_wrong_origin_counts.values())
    output = {
        "schema": "onichase.v4.v3_release_candidate_quality_audit.v1",
        "inputs": {
            "v3Adapted": str(args.v3_adapted),
            "current": str(args.current),
            "physicalMap": str(args.physical_map),
        },
        "summary": {
            "v3AdaptedTrainCount": len(v3_trains),
            "v3RetainedInCurrentCount": len(current_v3_trains),
            "v3LineCount": len(v3_by_line),
            "hardAnomalyCount": hard_anomaly_count,
            "firstStopReviewPatternCount": len(first_stop_review_counts),
        },
        "lineSummaries": line_summaries,
        "hardAnomalies": {
            "firstStopKnownBadCount": len(first_stop_anomalies),
            "firstStopKnownBadSamples": first_stop_anomalies[:REVIEW_SAMPLE_LIMIT],
            "wrongOriginCounts": dict(sorted(downstream_wrong_origin_counts.items())),
            "wrongOriginSamples": downstream_wrong_origin_samples,
        },
        "reviewFindings": {
            "firstStopReviewCounts": dict(sorted(first_stop_review_counts.items())),
            "firstStopReviewSamples": first_stop_review_samples,
        },
    }
    write_json(args.output, output)
    print(f"Wrote {args.output}: hardAnomalyCount={hard_anomaly_count} v3Retained={len(current_v3_trains)} lines={len(v3_by_line)}")
    return 1 if hard_anomaly_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
