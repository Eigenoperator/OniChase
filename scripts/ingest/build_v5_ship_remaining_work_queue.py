#!/usr/bin/env python3
"""Build a prioritized queue for remaining V5 playable ship route promotion."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = ROOT / "data/v5_ship_playable_promotion_audit.json"
SOURCE_AUDIT_PATH = ROOT / "data/v5_ship_source_parse_candidates.json"
OUT_PATH = ROOT / "data/v5_ship_remaining_500_work_queue.json"


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def priority_for_group(group: dict) -> int:
    if group.get("recommendedNextStep") == "candidate_for_parser":
        return 0
    if group.get("timeSignalCount", 0) >= 4:
        return 1
    if group.get("fareSignalCount", 0) >= 2:
        return 2
    if group.get("fetchErrors"):
        return 4
    return 3


def main() -> None:
    audit = read_json(AUDIT_PATH)
    source_audit = read_json(SOURCE_AUDIT_PATH)
    routes_by_id = {item["routeId"]: item for item in audit.get("skippedRoutes", [])}

    queue = []
    for group in source_audit.get("sourceGroups", []):
        group_priority = priority_for_group(group)
        for route_id in group.get("routeIds", []):
            route = routes_by_id.get(route_id)
            if not route:
                continue
            queue.append({
                "routeId": route_id,
                "operator": route.get("operator"),
                "origin": route.get("origin"),
                "destination": route.get("destination"),
                "missing": route.get("missing", []),
                "sourceUrl": group.get("sourceUrl"),
                "sourceOperators": group.get("operators", []),
                "sourceRouteCount": group.get("routeCount"),
                "timeSignalCount": group.get("timeSignalCount"),
                "fareSignalCount": group.get("fareSignalCount"),
                "recommendedNextStep": group.get("recommendedNextStep"),
                "priorityClass": group_priority,
                "fetchErrors": group.get("fetchErrors", []),
            })
    queue.sort(key=lambda item: (
        item["priorityClass"],
        -(item.get("sourceRouteCount") or 0),
        str(item.get("operator") or ""),
        str(item.get("origin") or ""),
        str(item.get("destination") or ""),
    ))

    payload = {
        "schema": "onichase.v5.ship_remaining_work_queue.1",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "policy": "Only promote after official explicit trip times and adult passenger fare are parsed or manually verified.",
        "remainingRouteCount": len(queue),
        "targetBatchSize": min(500, len(queue)),
        "priorityCounts": {},
        "items": queue[:500],
    }
    for item in queue:
        key = f"class_{item['priorityClass']}"
        payload["priorityCounts"][key] = payload["priorityCounts"].get(key, 0) + 1
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "remainingRouteCount": payload["remainingRouteCount"],
        "targetBatchSize": payload["targetBatchSize"],
        "priorityCounts": payload["priorityCounts"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
