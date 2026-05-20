#!/usr/bin/env python3
"""Collect the next V5 ship/ferry official source batch up to 150 candidates.

This batch intentionally stores MLIT-discovered official source entries only.
Many remaining local and municipal ferry records use island/city route text
rather than precise port names, so they must not be promoted into the map until
ports, coordinates, calendars, fares, and duplicate handling are reviewed.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


MLIT_DISCOVERY = Path("data/v5_ship_mlit_discovery.json")
OUT = Path("data/v5_ship_expansion_to_150_source_inventory.json")
EXISTING_SOURCE_FILES = [
    Path("data/v5_ship_seikan_ferry_official.json"),
    Path("data/v5_ship_priority_batch_official.json"),
    Path("data/v5_ship_long_distance_batch_official.json"),
    Path("data/v5_ship_expansion_to_70_official.json"),
]
TARGET_ADDITIONAL_SOURCE_ENTRIES = 80


def slugify(text: str) -> str:
    normalized = re.sub(r"https?://", "", text)
    normalized = re.sub(r"[^0-9A-Za-z一-龥ぁ-んァ-ヶー]+", "_", normalized)
    normalized = normalized.strip("_").lower()
    return normalized[:90] or "ship_source"


def load_existing_identity() -> tuple[set[str], set[str]]:
    urls: set[str] = set()
    operators: set[str] = set()
    for path in EXISTING_SOURCE_FILES:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        urls.update(payload.get("sourceUrls") or [])
        for route in payload.get("routes") or []:
            operator = route.get("operator")
            if operator:
                operators.add(operator)
    return urls, operators


def is_transport_candidate(item: dict) -> bool:
    return item.get("candidateClass") in {
        "scheduled_public_candidate",
        "municipal_scheduled_candidate",
    }


def main() -> None:
    mlit = json.loads(MLIT_DISCOVERY.read_text(encoding="utf-8"))
    existing_urls, existing_operators = load_existing_identity()
    selected: list[dict] = []
    skipped_existing: list[dict] = []
    skipped_review: list[dict] = []

    for item in mlit.get("items") or []:
        if not is_transport_candidate(item):
            skipped_review.append(item)
            continue
        if item.get("url") in existing_urls or item.get("operator") in existing_operators:
            skipped_existing.append(item)
            continue
        selected.append(item)
        if len(selected) >= TARGET_ADDITIONAL_SOURCE_ENTRIES:
            break

    if len(selected) != TARGET_ADDITIONAL_SOURCE_ENTRIES:
        raise RuntimeError(
            f"expected {TARGET_ADDITIONAL_SOURCE_ENTRIES} new source entries, got {len(selected)}"
        )

    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    items = []
    for index, item in enumerate(selected, 1):
        source_id = f"ship_source_150_{index:03d}_{slugify(item['operator'] + '_' + item['routeText'])}"
        items.append(
            {
                "id": source_id,
                "operator": item["operator"],
                "routeText": item["routeText"],
                "region": item["region"],
                "candidateClass": item["candidateClass"],
                "officialUrl": item["url"],
                "mlitSuffix": item.get("mlitSuffix", ""),
                "collectionStage": "official_source_collected_port_route_timetable_calendar_fare_pending",
                "mapPromotionStatus": "blocked_until_precise_ports_and_coordinates_are_verified",
                "playablePromotionStatus": "blocked_until_timetable_calendar_fare_and_connectors_are_verified",
                "notes": [
                    "Collected from the MLIT scheduled passenger/ferry operator discovery baseline.",
                    "Do not generate fake port nodes from routeText; promote only after official port names and coordinates are verified.",
                ],
            }
        )

    payload = {
        "schema": "onichase.v5.ship.sourceInventoryBatch.v1",
        "batchId": "ship_expansion_to_150_sources",
        "retrievedAt": retrieved_at,
        "sourceDiscoveryFile": str(MLIT_DISCOVERY),
        "targetTotalCollectedSourceEntries": 150,
        "currentMapRouteGroupBaseline": 70,
        "newSourceEntryCount": len(items),
        "skippedExistingCount": len(skipped_existing),
        "skippedReviewCountBeforeSelection": len(skipped_review),
        "selectionRule": "First 80 MLIT public/municipal scheduled transport candidates not already represented by exact source URL or operator in the promoted ship map sources.",
        "items": items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT} newSourceEntryCount={len(items)} "
        f"targetTotalCollectedSourceEntries=150 retrievedAt={retrieved_at}"
    )


if __name__ == "__main__":
    main()
