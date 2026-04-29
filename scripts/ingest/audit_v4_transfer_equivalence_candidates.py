#!/usr/bin/env python3
"""Audit v4 transfer-equivalence candidates created by branded station prefixes.

The browser keeps physical station groups separate, then lets selected nearby
groups behave as transfer-equivalent for gameplay.  This audit focuses on the
dangerous class where two different station names only match after stripping a
railway/company prefix, e.g. 名古屋 / 名鉄名古屋 or 蒲田 / 京急蒲田.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_TRANSFER_REVIEW = ROOT / "data" / "v4_transfer_equivalence_review.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_transfer_equivalence_candidate_audit.json"

DIRECT_TRANSFER_RADIUS_M = 700
REVIEW_CANDIDATE_RADIUS_M = 1200
PREFIX_RE = re.compile(
    r"^(?:JR|ＪＲ|東京メトロ|都営|東京モノレール|モノレール|京急|京成|京王|小田急|東急|東武|西武|相鉄|近鉄|名鉄|阪急|阪神|京阪|南海|西鉄|京福|叡山|りんかい|ゆりかもめ)"
)

REVIEWED_DIRECT_NAME_SETS: set[frozenset[str]] = set()
REVIEWED_NOT_DIRECT_NAME_SETS: set[frozenset[str]] = set()


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_transfer_review(path: Path) -> tuple[set[frozenset[str]], set[frozenset[str]]]:
    if not path.exists():
        return set(), set()
    payload = load_json(path)
    return (
        {frozenset(item) for item in payload.get("reviewedDirectNameSets", [])},
        {frozenset(item) for item in payload.get("reviewedNotDirectNameSets", [])},
    )


def display_name(group: dict[str, Any]) -> str:
    return str((group.get("names") or {}).get("ja") or group.get("nameJa") or group.get("primaryName") or group["id"])


def normalized_transfer_name(name: str) -> str:
    normalized = re.sub(r"\s+", "", str(name or ""))
    normalized = PREFIX_RE.sub("", normalized)
    return re.sub(r"駅$", "", normalized)


def station_group_coordinate(group: dict[str, Any]) -> tuple[float, float] | None:
    centroid = group.get("centroid") or {}
    lon = centroid.get("lon")
    lat = centroid.get("lat")
    if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
        return float(lon), float(lat)
    return None


def coordinate_distance_meters(left: tuple[float, float] | None, right: tuple[float, float] | None) -> float:
    if not left or not right:
        return math.inf
    lon1, lat1 = map(math.radians, left)
    lon2, lat2 = map(math.radians, right)
    d_lon = lon2 - lon1
    d_lat = lat2 - lat1
    a = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def pair_key(left_name: str, right_name: str) -> frozenset[str]:
    return frozenset((left_name, right_name))


def classify_pair(left_name: str, right_name: str, distance_m: float, direct_radius_m: float) -> str:
    key = pair_key(left_name, right_name)
    if key in REVIEWED_DIRECT_NAME_SETS:
        return "reviewed_direct"
    if key in REVIEWED_NOT_DIRECT_NAME_SETS:
        return "reviewed_not_direct"
    if distance_m <= direct_radius_m:
        return "active_unreviewed_direct"
    return "nearby_needs_review"


def summarize_group(group: dict[str, Any]) -> dict[str, Any]:
    centroid = group.get("centroid") or {}
    name = display_name(group)
    return {
        "stationGroupId": group["id"],
        "name": name,
        "normalizedName": normalized_transfer_name(name),
        "lon": centroid.get("lon"),
        "lat": centroid.get("lat"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--transfer-review", type=Path, default=DEFAULT_TRANSFER_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--direct-radius-m", type=float, default=DIRECT_TRANSFER_RADIUS_M)
    parser.add_argument("--review-radius-m", type=float, default=REVIEW_CANDIDATE_RADIUS_M)
    args = parser.parse_args()
    global REVIEWED_DIRECT_NAME_SETS, REVIEWED_NOT_DIRECT_NAME_SETS
    REVIEWED_DIRECT_NAME_SETS, REVIEWED_NOT_DIRECT_NAME_SETS = load_transfer_review(args.transfer_review)

    payload = load_json(args.physical_map)
    groups = payload["stationGroups"]
    by_normalized_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        name = display_name(group)
        normalized = normalized_transfer_name(name)
        if not normalized:
            continue
        by_normalized_name[normalized].append(group)

    candidates: list[dict[str, Any]] = []
    counts: defaultdict[str, int] = defaultdict(int)
    for normalized_name, normalized_groups in sorted(by_normalized_name.items()):
        if len(normalized_groups) < 2:
            continue
        for left_index, left in enumerate(normalized_groups):
            left_name = display_name(left)
            left_stripped = normalized_transfer_name(left_name) != re.sub(r"駅$", "", re.sub(r"\s+", "", left_name))
            for right in normalized_groups[left_index + 1 :]:
                right_name = display_name(right)
                if left_name == right_name:
                    continue
                right_stripped = normalized_transfer_name(right_name) != re.sub(r"駅$", "", re.sub(r"\s+", "", right_name))
                if not (left_stripped or right_stripped):
                    continue
                distance_m = coordinate_distance_meters(station_group_coordinate(left), station_group_coordinate(right))
                if distance_m > args.review_radius_m:
                    continue
                decision = classify_pair(left_name, right_name, distance_m, args.direct_radius_m)
                is_currently_direct = (
                    decision == "reviewed_direct"
                    or (distance_m <= args.direct_radius_m and decision != "reviewed_not_direct")
                )
                counts[decision] += 1
                candidates.append({
                    "decision": decision,
                    "currentlyDirectUnderRuntimeRule": is_currently_direct,
                    "normalizedName": normalized_name,
                    "distanceM": round(distance_m, 1),
                    "left": summarize_group(left),
                    "right": summarize_group(right),
                })

    candidates.sort(key=lambda item: (
        {
            "active_unreviewed_direct": 0,
            "nearby_needs_review": 1,
            "reviewed_not_direct": 2,
            "reviewed_direct": 3,
        }.get(item["decision"], 9),
        item["distanceM"],
        item["left"]["name"],
        item["right"]["name"],
    ))
    hard_anomaly_count = counts["active_unreviewed_direct"]
    output = {
        "schema": "onichase.v4.transfer_equivalence_candidate_audit.v1",
        "inputs": {"physicalMap": str(args.physical_map), "transferReview": str(args.transfer_review)},
        "rules": {
            "directRadiusM": args.direct_radius_m,
            "reviewCandidateRadiusM": args.review_radius_m,
            "reviewedDirectNameSets": [sorted(item) for item in sorted(REVIEWED_DIRECT_NAME_SETS, key=lambda value: sorted(value))],
            "reviewedNotDirectNameSets": [sorted(item) for item in sorted(REVIEWED_NOT_DIRECT_NAME_SETS, key=lambda value: sorted(value))],
        },
        "summary": {
            "candidateCount": len(candidates),
            "hardAnomalyCount": hard_anomaly_count,
            "countsByDecision": dict(sorted(counts.items())),
        },
        "candidates": candidates,
    }
    write_json(args.output, output)
    print(
        f"Wrote {args.output}: candidates={len(candidates)} "
        f"active_unreviewed_direct={hard_anomaly_count}"
    )
    return 1 if hard_anomaly_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
