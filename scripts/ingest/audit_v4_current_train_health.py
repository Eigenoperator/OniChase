#!/usr/bin/env python3
"""Audit the merged v4 train collection for reusable data-health checks."""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "v4_current_weekday_train_instances.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_current_train_health_audit.json"


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_label(train: dict[str, Any]) -> str:
    return str(train.get("source_collection") or train.get("source_feed_key") or "unknown")


def station_group_ref(stop: dict[str, Any]) -> str:
    return str(
        stop.get("station_group_id")
        or stop.get("stationGroupId")
        or stop.get("station_id")
        or stop.get("stationId")
        or ""
    )


def physical_station_ref(stop: dict[str, Any]) -> str:
    return str(stop.get("physical_station_id") or stop.get("physicalStationId") or "")


def is_missing_ref(value: str) -> bool:
    return not value or value.startswith(("UNMATCHED", "JREAST_UNMATCHED"))


def stop_time_minutes(stop: dict[str, Any]) -> int | None:
    value = (
        stop.get("departure_hhmm")
        or stop.get("departure_time")
        or stop.get("departureTime")
        or stop.get("arrival_hhmm")
        or stop.get("arrival_time")
        or stop.get("arrivalTime")
    )
    if not isinstance(value, str) or ":" not in value:
        return None
    hour_text, minute_text = value.split(":", 1)
    try:
        total = int(hour_text) * 60 + int(minute_text[:2])
    except ValueError:
        return None
    if total < 3 * 60:
        total += 24 * 60
    return total


def stop_station_key(stop: dict[str, Any]) -> str:
    return station_group_ref(stop) or str(
        stop.get("station_name_raw")
        or stop.get("station_name")
        or stop.get("stationName")
        or ""
    )


def train_signature(train: dict[str, Any]) -> tuple[Any, ...]:
    return (
        train.get("operator_id") or train.get("operator_name") or "",
        train.get("train_number") or train.get("service_name") or train.get("display_name") or "",
        tuple(
            (
                stop_station_key(stop),
                stop.get("arrival_hhmm") or stop.get("arrival_time") or stop.get("arrivalTime") or "",
                stop.get("departure_hhmm") or stop.get("departure_time") or stop.get("departureTime") or "",
            )
            for stop in train.get("stop_times") or []
        ),
    )


def add_sample(samples: list[dict[str, Any]], sample: dict[str, Any], limit: int = 40) -> None:
    if len(samples) < limit:
        samples.append(sample)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = load_json(args.input)
    trains: list[dict[str, Any]] = list(payload.get("train_instances") or [])
    service_id_counts = Counter(str(train.get("service_instance_id") or "") for train in trains)
    signature_counts = Counter(train_signature(train) for train in trains)

    short_samples: list[dict[str, Any]] = []
    missing_group_samples: list[dict[str, Any]] = []
    missing_physical_samples: list[dict[str, Any]] = []
    bad_time_samples: list[dict[str, Any]] = []
    missing_group_by_source: Counter[str] = Counter()
    missing_physical_by_source: Counter[str] = Counter()
    bad_time_by_source: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    operator_counts: Counter[str] = Counter()
    line_counts: dict[str, Counter[str]] = defaultdict(Counter)
    short_count = 0
    missing_group_stop_count = 0
    missing_physical_stop_count = 0
    bad_time_train_count = 0

    for train in trains:
        source = source_label(train)
        source_counts[source] += 1
        operator = str(train.get("operator_name") or train.get("operator_id") or "")
        line = str(train.get("line_name") or train.get("service_name") or "")
        operator_counts[operator] += 1
        line_counts[operator][line] += 1
        stops = list(train.get("stop_times") or [])
        if len(stops) < 2:
            short_count += 1
            add_sample(short_samples, {"serviceInstanceId": train.get("service_instance_id"), "source": source})

        for stop in stops:
            if is_missing_ref(station_group_ref(stop)):
                missing_group_stop_count += 1
                missing_group_by_source[source] += 1
                add_sample(
                    missing_group_samples,
                    {
                        "serviceInstanceId": train.get("service_instance_id"),
                        "source": source,
                        "stationName": stop.get("station_name_raw") or stop.get("station_name"),
                        "operatorName": stop.get("operator_name") or train.get("operator_name"),
                        "lineName": stop.get("line_name") or train.get("line_name"),
                    },
                )
            if is_missing_ref(physical_station_ref(stop)):
                missing_physical_stop_count += 1
                missing_physical_by_source[source] += 1
                add_sample(
                    missing_physical_samples,
                    {
                        "serviceInstanceId": train.get("service_instance_id"),
                        "source": source,
                        "stationName": stop.get("station_name_raw") or stop.get("station_name"),
                        "stationGroupId": station_group_ref(stop),
                        "operatorName": stop.get("operator_name") or train.get("operator_name"),
                        "lineName": stop.get("line_name") or train.get("line_name"),
                    },
                )

        previous: int | None = None
        for stop in stops:
            current = stop_time_minutes(stop)
            if current is None:
                continue
            if previous is not None and current < previous:
                bad_time_train_count += 1
                bad_time_by_source[source] += 1
                add_sample(
                    bad_time_samples,
                    {
                        "serviceInstanceId": train.get("service_instance_id"),
                        "source": source,
                        "operatorName": train.get("operator_name"),
                        "lineName": train.get("line_name"),
                    },
                )
                break
            previous = current

    duplicate_service_ids = [item for item, count in service_id_counts.items() if item and count > 1]
    duplicate_signature_count = sum(1 for count in signature_counts.values() if count > 1)
    audit = {
        "schema": "onichase.v4.current_train_health_audit.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "input": str(args.input.relative_to(ROOT) if args.input.is_relative_to(ROOT) else args.input),
        "counts": {
            "trainInstanceCount": len(trains),
            "duplicateServiceInstanceIdCount": len(duplicate_service_ids),
            "duplicateSignatureGroupCount": duplicate_signature_count,
            "shortTrainInstanceCount": short_count,
            "missingStationGroupStopCount": missing_group_stop_count,
            "missingPhysicalStationStopCount": missing_physical_stop_count,
            "badTimeOrderTrainCount": bad_time_train_count,
            "sourceCount": len(source_counts),
            "operatorCount": len(operator_counts),
        },
        "sourceTrainCounts": dict(sorted(source_counts.items())),
        "operatorTrainCounts": dict(sorted(operator_counts.items())),
        "operatorLineTrainCounts": {
            operator: dict(sorted(counter.items()))
            for operator, counter in sorted(line_counts.items())
        },
        "missingStationGroupStopCountsBySource": dict(sorted(missing_group_by_source.items())),
        "missingPhysicalStationStopCountsBySource": dict(sorted(missing_physical_by_source.items())),
        "badTimeOrderTrainCountsBySource": dict(sorted(bad_time_by_source.items())),
        "duplicateServiceInstanceIdSample": duplicate_service_ids[:40],
        "shortTrainSample": short_samples,
        "missingStationGroupStopSample": missing_group_samples,
        "missingPhysicalStationStopSample": missing_physical_samples,
        "badTimeOrderTrainSample": bad_time_samples,
    }
    write_json(args.output, audit)
    print(
        f"Wrote {args.output}: trains={len(trains)} duplicate_ids={len(duplicate_service_ids)} "
        f"missing_groups={missing_group_stop_count} bad_time={bad_time_train_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
