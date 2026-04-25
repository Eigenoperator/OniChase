#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import argparse
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REPORT_PATH = DATA_DIR / "v3_timetable_audit_report.json"


def load_json(path: Path) -> dict:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict) -> None:
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sort_key(item: dict) -> tuple:
    stop_times = item.get("stop_times", [])
    first = stop_times[0] if stop_times else {}
    return (
        first.get("departure_hhmm", ""),
        item.get("service_name", ""),
        item.get("train_number", ""),
        item.get("service_instance_id", ""),
    )


def signature_key(item: dict) -> tuple:
    stop_times = item.get("stop_times", [])
    return (
        item.get("service_name", ""),
        item.get("headsign", ""),
        item.get("train_type", ""),
        stop_times[0].get("departure_hhmm", "") if stop_times else "",
        stop_times[-1].get("arrival_hhmm", "") if stop_times else "",
        tuple(
            (s.get("station_id"), s.get("arrival_hhmm"), s.get("departure_hhmm"))
            for s in stop_times
        ),
    )


def choose_best(current: dict | None, candidate: dict) -> dict:
    if current is None:
        return candidate
    cur_stops = current.get("stop_times", [])
    cand_stops = candidate.get("stop_times", [])
    if len(cand_stops) > len(cur_stops):
        return candidate
    if len(cand_stops) < len(cur_stops):
        return current
    if candidate.get("train_number", "") < current.get("train_number", ""):
        return candidate
    return current


def dataset_report(path: Path) -> dict:
    payload = load_json(path)
    key = "train_instances" if "train_instances" in payload else "trains"
    trains = payload.get(key, [])

    by_sig: dict[tuple, dict] = {}
    train_number_groups: Counter[str] = Counter()
    for train in trains:
        train_number_groups[train.get("train_number", "")] += 1
        sig = signature_key(train)
        by_sig[sig] = choose_best(by_sig.get(sig), train)

    deduped = sorted(by_sig.values(), key=sort_key)
    deduped_num_groups: Counter[str] = Counter()
    for train in deduped:
        deduped_num_groups[train.get("train_number", "")] += 1

    return {
        "path": str(path.relative_to(ROOT)),
        "dataset_id": payload.get("id"),
        "service_day": payload.get("service_day"),
        "train_count": len(trains),
        "source_report_count": len(payload.get("source_reports", [])),
        "unique_train_number_count": len(train_number_groups),
        "unique_signature_count": len(by_sig),
        "duplicate_train_number_groups": sum(1 for c in train_number_groups.values() if c > 1),
        "duplicate_signature_groups": len(trains) - len(deduped),
        "signature_deduped_train_count": len(deduped),
        "post_signature_duplicate_train_number_groups": sum(1 for c in deduped_num_groups.values() if c > 1),
    }


def default_targets(include_shinkansen: bool = True) -> list[Path]:
    targets = sorted(DATA_DIR.glob("v3_tokyo_*weekday_train_instances.json*"))
    shinkansen_path = DATA_DIR / "shinkansen_v2_weekday_train_instances_merged.json"
    if include_shinkansen and shinkansen_path.exists():
        targets.append(shinkansen_path)
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit raw v3 train datasets for duplicate signatures and duplicate train numbers.")
    parser.add_argument("--output", type=Path, default=REPORT_PATH, help="Path for the component JSON report.")
    parser.add_argument(
        "--path",
        action="append",
        type=Path,
        default=[],
        help="Specific dataset path to audit. Can be repeated. Defaults to all v3 Tokyo raw train datasets plus Shinkansen.",
    )
    parser.add_argument(
        "--no-shinkansen",
        action="store_true",
        help="When using the default dataset list, skip the Shinkansen merged dataset.",
    )
    args = parser.parse_args()

    targets = args.path or default_targets(include_shinkansen=not args.no_shinkansen)
    targets = [path if path.is_absolute() else ROOT / path for path in targets]
    missing = [path for path in targets if not path.exists()]
    if missing:
        for path in missing:
            print(f"Missing dataset: {path}")
        return 1
    report = [dataset_report(path) for path in targets]
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
