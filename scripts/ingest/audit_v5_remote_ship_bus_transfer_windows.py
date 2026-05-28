#!/usr/bin/env python3
"""Lightweight ship-bus transfer-window audit for remote V5 port connectors."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BUS_SOURCE_PATH = ROOT / "data/v5_remote_small_island_bus_source.json"
SHIP_BUNDLE_PATH = ROOT / "docs/data/v5_ship_timetable_current_bundle.json"
AUDIT_PATH = ROOT / "data/v5_remote_ship_bus_transfer_window_audit.json"
DOCS_AUDIT_PATH = ROOT / "docs/data/v5_remote_ship_bus_transfer_window_audit.json"
MIN_TRANSFER = 5
MAX_TRANSFER = 180


def hhmm_to_minute(value: str) -> int | None:
    if not value or ":" not in value:
        return None
    hour, minute = value.split(":", 1)
    try:
        return int(hour) * 60 + int(minute)
    except ValueError:
        return None


def route_anchor_names(route: dict[str, Any]) -> set[str]:
    names = set(str(name) for name in route.get("connectorAnchorStopNames", []) if name)
    port_names = [str(name) for name in route.get("portNames", []) if name]
    names.update(port_names)
    for port in port_names:
        if port.endswith("港"):
            names.add(port[:-1])
    names.update(name.replace("ノ", "の") for name in list(names))
    return names


def route_bus_anchor_times(route: dict[str, Any]) -> tuple[list[int], list[int]]:
    anchors = route_anchor_names(route)
    from_port: list[int] = []
    to_port: list[int] = []
    for direction in route.get("directions", []):
        for trip in direction.get("trips", []):
            stop_times = trip.get("stopTimes", [])
            matched = [
                (index, hhmm_to_minute(str(stop.get("time"))))
                for index, stop in enumerate(stop_times)
                if any(anchor and anchor in str(stop.get("stopName", "")).replace("ノ", "の") for anchor in anchors)
            ]
            matched = [(index, minute) for index, minute in matched if minute is not None]
            if not matched:
                continue
            first_index, first_minute = matched[0]
            last_index, last_minute = matched[-1]
            if first_index < len(stop_times) - 1:
                from_port.append(first_minute)
            if last_index > 0:
                to_port.append(last_minute)
    return from_port, to_port


def ship_times_by_port(sailings: list[dict[str, Any]]) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    arrivals: dict[str, list[int]] = {}
    departures: dict[str, list[int]] = {}
    for sailing in sailings:
        origin = str(sailing.get("originPort") or "")
        destination = str(sailing.get("destinationPort") or "")
        dep = sailing.get("departureMinute")
        arr = sailing.get("arrivalMinute")
        if origin and isinstance(dep, int):
            departures.setdefault(origin, []).append(dep)
        if destination and isinstance(arr, int):
            arrivals.setdefault(destination, []).append(arr)
    return arrivals, departures


def has_window(earlier: list[int], later: list[int]) -> bool:
    for start in earlier:
        for end in later:
            delta = end - start
            if MIN_TRANSFER <= delta <= MAX_TRANSFER:
                return True
    return False


def main() -> None:
    bus_source = json.loads(BUS_SOURCE_PATH.read_text(encoding="utf-8"))
    ship_bundle = json.loads(SHIP_BUNDLE_PATH.read_text(encoding="utf-8"))
    arrivals, departures = ship_times_by_port(ship_bundle.get("sailings", []))
    checked = []
    for route in bus_source.get("routes", []):
        if not route.get("portNames"):
            continue
        from_port_bus, to_port_bus = route_bus_anchor_times(route)
        port_names = [str(port) for port in route.get("portNames", [])]
        ship_arrivals = [minute for port in port_names for minute in arrivals.get(port, [])]
        ship_departures = [minute for port in port_names for minute in departures.get(port, [])]
        checked.append(
            {
                "routeCode": route.get("routeCode"),
                "portNames": port_names,
                "shipToBusWindow": has_window(ship_arrivals, from_port_bus),
                "busToShipWindow": has_window(to_port_bus, ship_departures),
                "shipArrivalCount": len(ship_arrivals),
                "shipDepartureCount": len(ship_departures),
                "fromPortBusTripCount": len(from_port_bus),
                "toPortBusTripCount": len(to_port_bus),
            }
        )
    weak = [
        item
        for item in checked
        if item["shipArrivalCount"] or item["shipDepartureCount"]
        if not item["shipToBusWindow"] and not item["busToShipWindow"]
    ]
    audit = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "policy": {"minTransferMinutes": MIN_TRANSFER, "maxTransferMinutes": MAX_TRANSFER},
        "summary": {
            "checkedRouteCount": len(checked),
            "routesWithShipToBusWindow": sum(1 for item in checked if item["shipToBusWindow"]),
            "routesWithBusToShipWindow": sum(1 for item in checked if item["busToShipWindow"]),
            "routesWithNoWindowButShipTimes": len(weak),
        },
        "weakRoutes": weak,
        "routes": checked,
    }
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOCS_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OK remote ship-bus transfer windows:", audit["summary"])


if __name__ == "__main__":
    main()
