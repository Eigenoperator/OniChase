#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def hhmm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def build_station_order_lookup(stations_data: dict[str, Any]) -> dict[str, int]:
    stations = stations_data["stations"] if isinstance(stations_data, dict) else stations_data
    return {station["id"]: station["order"] for station in stations if "order" in station}


def validate_train_instance(
    train: dict[str, Any],
    station_ids: set[str],
    station_order_lookup: dict[str, int],
    errors: list[str],
) -> None:
    train_number = train.get("train_number")
    stop_times = train.get("stop_times", [])

    require(bool(train_number), "Train instance missing train_number.", errors)
    require(bool(stop_times), f"Train {train_number} has no stop_times.", errors)
    if not stop_times:
        return

    previous_sequence = None
    previous_time = None
    visit_counts: dict[str, int] = {}

    for stop in stop_times:
        sequence = stop.get("sequence")
        station_id = stop.get("station_id")
        arrival = stop.get("arrival_hhmm")
        departure = stop.get("departure_hhmm")
        loop_pass_index = stop.get("loop_pass_index")

        require(isinstance(sequence, int), f"Train {train_number} has non-int sequence.", errors)
        if isinstance(sequence, int) and previous_sequence is not None:
            require(sequence > previous_sequence, f"Train {train_number} sequence is not strictly increasing.", errors)
        if isinstance(sequence, int):
            previous_sequence = sequence

        require(station_id in station_ids, f"Train {train_number} references unknown station_id {station_id}.", errors)
        if station_id in station_ids:
            visit_counts[station_id] = visit_counts.get(station_id, 0) + 1
            require(
                loop_pass_index == visit_counts[station_id],
                f"Train {train_number} has invalid loop_pass_index at {station_id}: expected {visit_counts[station_id]}, got {loop_pass_index}.",
                errors,
            )

        require(arrival or departure, f"Train {train_number} stop {sequence} has neither arrival nor departure time.", errors)

        candidate_times = []
        if arrival:
            candidate_times.append(hhmm_to_minutes(arrival))
        if departure:
            candidate_times.append(hhmm_to_minutes(departure))

        if arrival and departure:
            require(
                hhmm_to_minutes(arrival) <= hhmm_to_minutes(departure),
                f"Train {train_number} has arrival after departure at sequence {sequence}.",
                errors,
            )

        if candidate_times:
            current_time = max(candidate_times)
            if previous_time is not None:
                require(
                    current_time >= previous_time,
                    f"Train {train_number} time goes backwards at sequence {sequence}.",
                    errors,
                )
            previous_time = current_time

        if station_id in station_order_lookup and previous_sequence == 1:
            # first station exists in canonical dataset; nothing else needed here
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a train-instances dataset for game-logic consistency.")
    parser.add_argument("--input", required=True, help="Path to the train-instances dataset JSON file.")
    parser.add_argument("--stations", required=True, help="Path to the canonical station dataset JSON file.")
    args = parser.parse_args()

    dataset = load_json(Path(args.input))
    stations_data = load_json(Path(args.stations))
    errors: list[str] = []

    require(bool(dataset.get("id")), "Dataset id is missing.", errors)
    require(bool(dataset.get("version")), "Dataset version is missing.", errors)
    require(bool(dataset.get("train_instances")), "Dataset has no train_instances.", errors)

    stations = stations_data["stations"] if isinstance(stations_data, dict) else stations_data
    station_ids = {station["id"] for station in stations}
    station_order_lookup = build_station_order_lookup(stations_data)
    seen_train_numbers: set[str] = set()

    for train in dataset.get("train_instances", []):
        train_number = train.get("train_number")
        require(bool(train_number), "Train instance missing train_number.", errors)
        if train_number:
            require(train_number not in seen_train_numbers, f"Duplicate train_number {train_number}.", errors)
            seen_train_numbers.add(train_number)
        validate_train_instance(train, station_ids, station_order_lookup, errors)

    if errors:
        print("Validation failed:")
        for error in errors[:200]:
            print(f"- {error}")
        if len(errors) > 200:
            print(f"... and {len(errors) - 200} more errors")
        return 1

    print(f"Dataset: {dataset['id']} v{dataset['version']}")
    print(f"Train instances: {len(dataset['train_instances'])}")
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
