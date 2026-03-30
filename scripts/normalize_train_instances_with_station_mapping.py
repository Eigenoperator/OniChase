#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from train_instance_normalization import normalize_train_instances

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Normalize train-instance stop times with canonical station ids.")
    parser.add_argument("--stations", required=True, help="Path to the station dataset JSON file.")
    parser.add_argument("--input", required=True, help="Path to the raw train-instance JSON file.")
    parser.add_argument("--output", required=True, help="Path to write the normalized train-instance JSON file.")
    args = parser.parse_args()

    stations_data = load_json(Path(args.stations))
    seed_data = load_json(Path(args.input))
    normalized_instances, unresolved = normalize_train_instances(seed_data["train_instances"], stations_data)

    if unresolved:
        print("Unresolved station names:")
        for name in sorted(unresolved):
            print(f"- {name}")
        return 1

    output = {
        **{k: v for k, v in seed_data.items() if k != "train_instances"},
        "train_instances": normalized_instances,
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(normalized_instances)} normalized train instances to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
