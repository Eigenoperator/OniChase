from __future__ import annotations

from copy import deepcopy
from typing import Any


def _minutes(value: str | None) -> int:
    if not value or ":" not in value:
        return 99_999
    hour, minute = value.split(":", 1)
    try:
        total = int(hour) * 60 + int(minute)
    except ValueError:
        return 99_999
    if total < 3 * 60:
        total += 24 * 60
    return total


def _stop_score(stop: dict[str, Any]) -> int:
    keys = ("arrival_hhmm", "departure_hhmm", "platform", "line_id", "station_name_raw")
    return sum(1 for key in keys if stop.get(key))


def _stop_sort_key(stop: dict[str, Any]) -> tuple[int, int, str]:
    time_value = stop.get("arrival_hhmm") or stop.get("departure_hhmm")
    return (_minutes(time_value), int(stop.get("sequence") or 0), str(stop.get("station_id") or ""))


def merge_stop_times(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge partial stop lists for the same train into a fuller stop list."""
    by_station: dict[str, dict[str, Any]] = {}
    for stop in existing + incoming:
        station_id = stop.get("station_id")
        if not station_id:
            continue
        current = by_station.get(station_id)
        if current is None or _stop_score(stop) > _stop_score(current):
            by_station[station_id] = deepcopy(stop)

    merged = sorted(by_station.values(), key=_stop_sort_key)
    for index, stop in enumerate(merged, start=1):
        stop["sequence"] = index
    return merged


def upsert_train_instance(
    train_instances: list[dict[str, Any]],
    instance_index: dict[str, dict[str, Any]],
    incoming: dict[str, Any],
) -> str:
    service_instance_id = incoming.get("service_instance_id")
    if not service_instance_id:
        train_instances.append(incoming)
        return "added"

    existing = instance_index.get(service_instance_id)
    if existing is None:
        train_instances.append(incoming)
        instance_index[service_instance_id] = incoming
        return "added"

    old_stop_times = existing.get("stop_times", [])
    new_stop_times = incoming.get("stop_times", [])
    merged_stop_times = merge_stop_times(old_stop_times, new_stop_times)
    if len(merged_stop_times) <= len(old_stop_times):
        return "unchanged"

    # Keep the richer metadata from the source that exposed the fuller train.
    if len(new_stop_times) > len(old_stop_times):
        for key, value in incoming.items():
            if key != "stop_times":
                existing[key] = value
    existing["stop_times"] = merged_stop_times
    return "updated"


def index_train_instances(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    train_instances: list[dict[str, Any]] = []
    instance_index: dict[str, dict[str, Any]] = {}
    for item in items:
        if not item.get("stop_times"):
            continue
        upsert_train_instance(train_instances, instance_index, item)
    return train_instances, instance_index
