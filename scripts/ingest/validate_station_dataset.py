#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate a station dataset JSON file.")
    parser.add_argument("--input", required=True, help="Path to the station dataset JSON file.")
    parser.add_argument("--expected-line-id", required=True, help="Expected line id.")
    parser.add_argument("--expected-line-color", required=True, help="Expected line color.")
    parser.add_argument("--expected-count", type=int, required=True, help="Expected station count.")
    parser.add_argument("--expected-loop-start", required=True, help="Expected first station id in loop reference.")
    args = parser.parse_args()

    data = load_json(Path(args.input))
    errors: list[str] = []

    require(bool(data.get("id")), "Dataset id is missing.", errors)
    require(bool(data.get("version")), "Dataset version is missing.", errors)

    line = data.get("line", {})
    require(line.get("id") == args.expected_line_id, f"Line id must be {args.expected_line_id}.", errors)
    require(line.get("color") == args.expected_line_color, f"Line color must be {args.expected_line_color}.", errors)

    stations = data.get("stations", [])
    require(len(stations) == args.expected_count, f"Expected {args.expected_count} stations, got {len(stations)}.", errors)

    station_ids: set[str] = set()
    seen_orders: set[int] = set()

    for station in stations:
        station_id = station.get("id")
        order = station.get("order")
        names = station.get("names")

        require(bool(station_id), "Station id is missing.", errors)
        if station_id:
            require(station_id not in station_ids, f"Duplicate station id {station_id}.", errors)
            station_ids.add(station_id)

        require(isinstance(order, int), f"Station {station_id} order must be int.", errors)
        if isinstance(order, int):
            require(order not in seen_orders, f"Duplicate station order {order}.", errors)
            seen_orders.add(order)

        require(isinstance(names, dict), f"Station {station_id} names must be an object.", errors)
        if isinstance(names, dict):
            for key in ("en", "ja", "zh_hans"):
                require(bool(names.get(key)), f"Station {station_id} missing names.{key}.", errors)

    expected_orders = set(range(1, args.expected_count + 1))
    require(
        seen_orders == expected_orders,
        f"Station orders must be a complete sequence from 1 to {args.expected_count}.",
        errors,
    )

    loop = data.get("loop", {}).get("clockwise_reference_from_osaki", [])
    require(len(loop) == args.expected_count, f"Loop reference must contain {args.expected_count} station ids, got {len(loop)}.", errors)
    require(set(loop) == station_ids, "Loop reference station ids must match station ids exactly.", errors)
    require(bool(loop) and loop[0] == args.expected_loop_start, f"Loop reference must start at {args.expected_loop_start}.", errors)

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Dataset: {data['id']} v{data['version']}")
    print(f"Stations: {len(stations)}")
    print(f"Line: {line['names']['en']} ({line['names']['ja']} / {line['names']['zh_hans']})")
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
