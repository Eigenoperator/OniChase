#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def merge_datasets(datasets: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    merged: dict[str, dict[str, Any]] = {}
    merge_report: list[dict[str, Any]] = []

    for dataset in datasets:
        dataset_id = dataset.get("id")
        dataset_direction = dataset.get("direction_label")

        for train in dataset.get("train_instances", []):
            train_number = train["train_number"]
            candidate = dict(train)
            candidate.setdefault("service_instance_id", train_number)
            if dataset_direction and not candidate.get("direction_label"):
                candidate["direction_label"] = dataset_direction

            if train_number not in merged:
                merged[train_number] = candidate
                continue

            current = merged[train_number]
            current_len = len(current.get("stop_times", []))
            candidate_len = len(candidate.get("stop_times", []))

            if candidate_len > current_len:
                merged[train_number] = candidate
                merge_report.append(
                    {
                        "train_number": train_number,
                        "resolution": "replaced_with_longer_stop_list",
                        "kept_stop_count": candidate_len,
                        "dropped_stop_count": current_len,
                        "source_dataset_id": dataset_id,
                    }
                )
            else:
                merge_report.append(
                    {
                        "train_number": train_number,
                        "resolution": "kept_existing_longer_or_equal_stop_list",
                        "kept_stop_count": current_len,
                        "dropped_stop_count": candidate_len,
                        "source_dataset_id": dataset_id,
                    }
                )

    return merged, merge_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge multiple train-instance datasets into one deduplicated dataset.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Input train-instance dataset JSON files.")
    parser.add_argument("--output", required=True, help="Output JSON path for merged dataset.")
    parser.add_argument("--dataset-id", required=True, help="Merged dataset id.")
    parser.add_argument("--label", required=True, help="Merged dataset label.")
    parser.add_argument("--version", default="0.1.0", help="Merged dataset version.")
    args = parser.parse_args()

    input_paths = [Path(value) for value in args.inputs]
    datasets = [load_json(path) for path in input_paths]
    merged_instances_by_number, merge_report = merge_datasets(datasets)

    output = {
        "id": args.dataset_id,
        "label": args.label,
        "version": args.version,
        "source_dataset_ids": [dataset.get("id") for dataset in datasets],
        "source_paths": [str(path) for path in input_paths],
        "merge_report": merge_report,
        "train_instances": sorted(
            merged_instances_by_number.values(),
            key=lambda train: (
                train.get("stop_times", [{}])[0].get("departure_hhmm")
                or train.get("stop_times", [{}])[0].get("arrival_hhmm")
                or "99:99",
                train["train_number"],
            ),
        ),
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Merged datasets: {len(datasets)}")
    print(f"Train instances: {len(output['train_instances'])}")
    print(f"Duplicate resolutions: {len(merge_report)}")
    print(f"Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
