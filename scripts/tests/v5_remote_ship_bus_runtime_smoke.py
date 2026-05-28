#!/usr/bin/env python3
"""Smoke-check remote ship-port bus source routes in the V5 runtime bus bundle."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "data/v5_remote_small_island_bus_source.json"
BUNDLE_PATH = ROOT / "docs/data/v5_bus_gtfs_current_bundle.json.gz"
OUTPUT_PATH = ROOT / "data/v5_remote_ship_bus_runtime_smoke.json"
DOCS_OUTPUT_PATH = ROOT / "docs/data/v5_remote_ship_bus_runtime_smoke.json"
WEEKDAY_KEYS = ("monday", "tuesday", "wednesday", "thursday", "friday")


def load_bundle() -> dict[str, Any]:
    with gzip.open(BUNDLE_PATH, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    bundle = load_bundle()
    source_route_codes = {route.get("routeCode") for route in source.get("routes", [])}
    runtime_routes = {
        route.get("sourceRouteId"): route
        for route in bundle.get("routes", [])
        if route.get("sourceRouteId") in source_route_codes
    }
    route_id_to_code = {route.get("busRouteId"): code for code, route in runtime_routes.items()}
    calendars = {calendar.get("busServiceCalendarId"): calendar for calendar in bundle.get("calendars", [])}
    trip_counts = {code: 0 for code in source_route_codes}
    weekday_trip_counts = {code: 0 for code in source_route_codes}
    for trip in bundle.get("trips", []):
        code = route_id_to_code.get(trip.get("busRouteId"))
        if not code:
            continue
        trip_counts[code] += 1
        calendar = calendars.get(trip.get("busServiceCalendarId"), {})
        if any(int(calendar.get(day, 0) or 0) for day in WEEKDAY_KEYS):
            weekday_trip_counts[code] += 1
    missing_routes = sorted(code for code in source_route_codes if code not in runtime_routes)
    no_weekday_trips = sorted(code for code in source_route_codes if weekday_trip_counts.get(code, 0) == 0)
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "bundlePath": str(BUNDLE_PATH.relative_to(ROOT)),
        "summary": {
            "sourceRouteCount": len(source_route_codes),
            "runtimeRouteCount": len(runtime_routes),
            "missingRuntimeRouteCount": len(missing_routes),
            "noWeekdayTripRouteCount": len(no_weekday_trips),
        },
        "missingRuntimeRoutes": missing_routes,
        "noWeekdayTripRoutes": no_weekday_trips,
        "routeTripCounts": {
            code: {"allTrips": trip_counts.get(code, 0), "weekdayTrips": weekday_trip_counts.get(code, 0)}
            for code in sorted(source_route_codes)
        },
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOCS_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OK remote ship-bus runtime smoke:", payload["summary"])


if __name__ == "__main__":
    main()
