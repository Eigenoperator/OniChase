#!/usr/bin/env python3
"""Build the current best v4 train collection from available sources.

The collection currently combines:
- frozen v3 timetable data rematched to v4 station_identity_v2;
- new v4 public GTFS/GTFS-JP feeds for operators not already covered by v3.

This avoids double-counting sources such as Toei, which exists in both the v3
release corpus and the public ODPT GTFS collector.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_V3_ADAPTED = ROOT / "data" / "v4_existing_v3_weekday_train_instances.json.gz"
DEFAULT_V4_GTFS = ROOT / "data" / "v4_gtfs_weekday_train_instances.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_current_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_current_train_collection_audit.json"

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
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v3-adapted", type=Path, default=DEFAULT_V3_ADAPTED)
    parser.add_argument("--v4-gtfs", type=Path, default=DEFAULT_V4_GTFS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    v3_data = load_json(args.v3_adapted)
    gtfs_data = load_json(args.v4_gtfs)
    trains: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    excluded_gtfs_counts: Counter[str] = Counter()

    for train in v3_data["train_instances"]:
        item = dict(train)
        item["source_collection"] = "v3_rematched_to_v4"
        trains.append(item)
        source_counts["v3_rematched_to_v4"] += 1

    for train in gtfs_data["train_instances"]:
        operator_name = train.get("operator_name")
        if operator_name in V3_COVERED_OPERATOR_NAMES:
            excluded_gtfs_counts[str(operator_name)] += 1
            continue
        item = dict(train)
        item["source_collection"] = "v4_public_gtfs"
        trains.append(item)
        source_counts["v4_public_gtfs"] += 1

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
            str(args.v4_gtfs),
        ],
        "train_instances": sorted(trains, key=lambda item: item["service_instance_id"]),
    }
    audit = {
        "schema": "onichase.v4.current_train_collection_audit.v1",
        "sourceCounts": dict(sorted(source_counts.items())),
        "trainInstanceCount": len(trains),
        "operatorTrainCounts": dict(sorted(operator_counts.items())),
        "excludedGtfsOperatorCounts": dict(sorted(excluded_gtfs_counts.items())),
        "duplicateServiceInstanceIdCount": len(duplicate_ids),
        "duplicateServiceInstanceIdsSample": duplicate_ids[:20],
        "shortTrainInstanceCount": short_count,
    }
    write_json(args.output, output)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(trains)} trains")
    print(f"Wrote {args.audit_output}: duplicate_ids={len(duplicate_ids)} short={short_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
