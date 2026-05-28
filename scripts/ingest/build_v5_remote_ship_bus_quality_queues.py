#!/usr/bin/env python3
"""Build small review queues for V5 remote ship-bus quality cleanup."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
READINESS_PATH = ROOT / "data/v5_remote_ship_bus_readiness_audit.json"
TRANSFER_PATH = ROOT / "data/v5_remote_ship_bus_transfer_window_audit.json"
SOURCE_PATH = ROOT / "data/v5_remote_small_island_bus_source.json"
OUTPUT_PATH = ROOT / "data/v5_remote_ship_bus_quality_review_queue.json"
DOCS_OUTPUT_PATH = ROOT / "docs/data/v5_remote_ship_bus_quality_review_queue.json"


def route_index(routes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(route.get("routeCode")): route for route in routes}


def main() -> None:
    readiness = json.loads(READINESS_PATH.read_text(encoding="utf-8"))
    transfer = json.loads(TRANSFER_PATH.read_text(encoding="utf-8"))
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    routes = route_index(source.get("routes", []))

    coordinate_items = []
    for item in readiness.get("manualCoordinateStopRefs", []):
        route = routes.get(str(item.get("routeCode")), {})
        coordinate_items.append(
            {
                "priority": "coordinate_refinement",
                "routeCode": item.get("routeCode"),
                "routeName": route.get("routeName"),
                "stopName": item.get("stopName"),
                "operatorName": route.get("operatorName"),
                "sourceUrls": route.get("sourceUrls") or [route.get("sourceUrl")],
                "reviewGoal": "Replace manual approximate coordinates with official stop, operator, or map-confirmed coordinates.",
            }
        )

    weak_transfer_items = []
    transfer_policy = transfer.get("policy") or {}
    min_transfer = transfer_policy.get("minTransferMinutes")
    max_transfer = transfer_policy.get("maxTransferMinutes")
    for item in transfer.get("weakRoutes", []):
        route = routes.get(str(item.get("routeCode")), {})
        weak_transfer_items.append(
            {
                "priority": "transfer_window_review",
                "routeCode": item.get("routeCode"),
                "routeName": route.get("routeName"),
                "portNames": item.get("portNames"),
                "operatorName": route.get("operatorName"),
                "sourceUrls": route.get("sourceUrls") or [route.get("sourceUrl")],
                "shipArrivalCount": item.get("shipArrivalCount"),
                "shipDepartureCount": item.get("shipDepartureCount"),
                "fromPortBusTripCount": item.get("fromPortBusTripCount"),
                "toPortBusTripCount": item.get("toPortBusTripCount"),
                "reviewGoal": f"Confirm whether a real {min_transfer}-{max_transfer} minute ship-bus transfer exists, or mark as weak/onward-only access.",
            }
        )

    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "policy": {
            "gameCalendarDefault": "weekday",
            "calendarPrecision": "weekday_weekend",
            "transferWindowMinutes": transfer_policy,
            "demandResponsiveTransport": "excluded_from_auto_planning",
        },
        "summary": {
            "coordinateReviewCount": len(coordinate_items),
            "weakTransferReviewCount": len(weak_transfer_items),
        },
        "coordinateReviewQueue": coordinate_items,
        "weakTransferReviewQueue": weak_transfer_items,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOCS_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OK remote ship-bus quality queue:", payload["summary"])


if __name__ == "__main__":
    main()
