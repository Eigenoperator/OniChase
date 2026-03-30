#!/usr/bin/env python3

from __future__ import annotations

import re
from typing import Any


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_station_lookup(stations_data: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for station in stations_data["stations"]:
        station_id = station["id"]
        english_name = station["names"]["en"]
        lookup[normalize_name(english_name)] = station_id

    lookup.update(
        {
            "takanawagateway": "TAKANAWA_GATEWAY",
            "shinokubo": "SHIN_OKUBO",
            "nishinippori": "NISHI_NIPPORI",
        }
    )
    return lookup


def normalize_train_instances(
    raw_instances: list[dict[str, Any]],
    stations_data: dict[str, Any],
) -> tuple[list[dict[str, Any]], set[str]]:
    station_lookup = build_station_lookup(stations_data)
    unresolved: set[str] = set()
    normalized_instances: list[dict[str, Any]] = []

    for train in raw_instances:
        normalized_stop_times: list[dict[str, Any]] = []
        station_visit_counts: dict[str, int] = {}

        for stop_time in train.get("stop_times", []):
            raw_name = stop_time["station_name_raw"]
            station_id = station_lookup.get(normalize_name(raw_name))
            if station_id is None:
                unresolved.add(raw_name)
                continue

            normalized_stop_time = dict(stop_time)
            normalized_stop_time["station_id"] = station_id
            station_visit_counts[station_id] = station_visit_counts.get(station_id, 0) + 1
            normalized_stop_time["loop_pass_index"] = station_visit_counts[station_id]
            normalized_stop_times.append(normalized_stop_time)

        normalized_train = dict(train)
        normalized_train["service_instance_id"] = train.get("service_instance_id") or train["train_number"]
        normalized_train["stop_times"] = normalized_stop_times
        normalized_instances.append(normalized_train)

    return normalized_instances, unresolved
