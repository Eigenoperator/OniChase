#!/usr/bin/env python3
"""Lightweight readiness audit for V5 remote ship-port bus source data."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "data/v5_remote_small_island_bus_source.json"
ACCESS_PATH = ROOT / "data/v5_remote_small_island_access_records.json"
AUDIT_PATH = ROOT / "data/v5_remote_ship_bus_readiness_audit.json"
DOCS_AUDIT_PATH = ROOT / "docs/data/v5_remote_ship_bus_readiness_audit.json"


def has_trips(route: dict[str, Any]) -> bool:
    return any(direction.get("trips") for direction in route.get("directions", []))


def stop_names(route: dict[str, Any]) -> set[str]:
    names = {str(stop.get("name")) for stop in route.get("busStops", []) if stop.get("name")}
    for direction in route.get("directions", []):
        for trip in direction.get("trips", []):
            names.update(str(stop.get("stopName")) for stop in trip.get("stopTimes", []) if stop.get("stopName"))
    return names


def route_has_port_anchor(route: dict[str, Any]) -> bool:
    if not route.get("portNames"):
        return True
    if route.get("connectorAnchorStopNames"):
        return True
    names = stop_names(route)
    names.update(str(name) for name in route.get("connectorAnchorStopNames", []) if name)
    for port in route.get("portNames", []):
        port_text = str(port)
        if port_text in names:
            return True
        normalized_port = port_text.replace("ノ", "の")
        normalized_names = {name.replace("ノ", "の") for name in names}
        if normalized_port in normalized_names:
            return True
        if port_text.endswith("港") and any(port_text[:-1] in name for name in names):
            return True
        if any(port_text in name for name in names):
            return True
    return False


def main() -> None:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    access = json.loads(ACCESS_PATH.read_text(encoding="utf-8"))
    routes = source.get("routes", [])
    access_records = access.get("records", [])

    no_trip = [route.get("routeCode") for route in routes if not has_trips(route)]
    missing_profile = [route.get("routeCode") for route in routes if not route.get("serviceProfile")]
    missing_port_anchor = [route.get("routeCode") for route in routes if not route_has_port_anchor(route)]
    manual_stop_refs = [
        {"routeCode": route.get("routeCode"), "stopName": stop.get("name")}
        for route in routes
        for stop in route.get("busStops", [])
        if "manual approximate" in str(stop.get("coordinateSource", ""))
    ]
    pending_ports = [
        port
        for record in access_records
        if record.get("status") == "remote_access_review_pending"
        for port in record.get("portNames", [])
    ]
    no_bus_without_source = [
        record.get("recordId")
        for record in access_records
        if record.get("status") == "no_scheduled_public_bus" and not record.get("sourceUrls")
    ]

    service_profiles = Counter(
        tuple(route.get("serviceProfile", {}).get("supportedDayTypes", [])) for route in routes
    )
    audit = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "summary": {
            "routeCount": len(routes),
            "noTripRouteCount": len(no_trip),
            "missingServiceProfileRouteCount": len(missing_profile),
            "missingPortAnchorRouteCount": len(missing_port_anchor),
            "manualCoordinateStopRefCount": len(manual_stop_refs),
            "pendingPortCount": len(pending_ports),
            "noBusWithoutSourceCount": len(no_bus_without_source),
            "serviceProfileCounts": {"|".join(key): value for key, value in sorted(service_profiles.items())},
        },
        "noTripRouteCodes": no_trip,
        "missingServiceProfileRouteCodes": missing_profile,
        "missingPortAnchorRouteCodes": missing_port_anchor,
        "manualCoordinateStopRefs": manual_stop_refs,
        "pendingPorts": pending_ports,
        "noBusWithoutSourceRecordIds": no_bus_without_source,
    }
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOCS_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OK remote ship-bus readiness:", audit["summary"])


if __name__ == "__main__":
    main()
