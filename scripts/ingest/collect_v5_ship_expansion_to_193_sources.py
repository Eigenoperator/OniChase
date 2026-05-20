#!/usr/bin/env python3
"""Collect every remaining MLIT public/municipal ship candidate source entry.

The 150-source batch intentionally stopped early. This batch completes the
MLIT public-transport discovery baseline so every scheduled public or municipal
candidate has a tracked official source record. It is source inventory only:
remaining entries still require precise port, coordinate, timetable, calendar,
fare, and connector review before map or playable promotion.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


MLIT_DISCOVERY = Path("data/v5_ship_mlit_discovery.json")
PREVIOUS_SOURCE_INVENTORIES = [
    Path("data/v5_ship_expansion_to_150_source_inventory.json"),
]
PROMOTED_SOURCE_FILES = [
    Path("data/v5_ship_seikan_ferry_official.json"),
    Path("data/v5_ship_priority_batch_official.json"),
    Path("data/v5_ship_long_distance_batch_official.json"),
    Path("data/v5_ship_expansion_to_70_official.json"),
    Path("data/v5_ship_expansion_150_map_batch1_official.json"),
]
OUT = Path("data/v5_ship_expansion_to_193_source_inventory.json")


def slugify(text: str) -> str:
    normalized = re.sub(r"https?://", "", text)
    normalized = re.sub(r"[^0-9A-Za-z一-龥ぁ-んァ-ヶー]+", "_", normalized)
    normalized = normalized.strip("_").lower()
    return normalized[:90] or "ship_source"


def is_transport_candidate(item: dict) -> bool:
    return item.get("candidateClass") in {
        "scheduled_public_candidate",
        "municipal_scheduled_candidate",
    }


def load_collected_identity() -> tuple[set[str], set[str]]:
    urls: set[str] = set()
    operators: set[str] = set()
    for path in PROMOTED_SOURCE_FILES:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        urls.update(payload.get("sourceUrls") or [])
        for route in payload.get("routes") or []:
            operator = route.get("operator")
            if operator:
                operators.add(operator)
    for path in PREVIOUS_SOURCE_INVENTORIES:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("items") or []:
            urls.add(item["officialUrl"])
            operators.add(item["operator"])
    return urls, operators


def main() -> None:
    mlit = json.loads(MLIT_DISCOVERY.read_text(encoding="utf-8"))
    collected_urls, collected_operators = load_collected_identity()
    transport_items = [item for item in mlit.get("items") or [] if is_transport_candidate(item)]
    remaining = [
        item
        for item in transport_items
        if item.get("url") not in collected_urls and item.get("operator") not in collected_operators
    ]

    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    items = []
    for index, item in enumerate(remaining, 1):
        source_id = f"ship_source_193_{index:03d}_{slugify(item['operator'] + '_' + item['routeText'])}"
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
                    "This completes source coverage for the current MLIT public/municipal candidate set.",
                    "Do not generate fake port nodes from routeText; promote only after official port names and coordinates are verified.",
                ],
            }
        )

    payload = {
        "schema": "onichase.v5.ship.sourceInventoryBatch.v1",
        "batchId": "ship_expansion_to_193_sources",
        "retrievedAt": retrieved_at,
        "sourceDiscoveryFile": str(MLIT_DISCOVERY),
        "mlitPublicMunicipalCandidateCount": len(transport_items),
        "newSourceEntryCount": len(items),
        "representedBeforeThisBatchCount": len(transport_items) - len(items),
        "representedAfterThisBatchCount": len(transport_items),
        "reviewCandidateCountExcluded": sum(
            1 for item in mlit.get("items") or [] if item.get("candidateClass") == "review_transport_or_sightseeing"
        ),
        "selectionRule": "All remaining MLIT public/municipal scheduled transport candidates not already represented by exact source URL or operator in promoted ship sources or previous source inventory.",
        "items": items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT} newSourceEntryCount={len(items)} "
        f"representedAfterThisBatchCount={len(transport_items)} retrievedAt={retrieved_at}"
    )


if __name__ == "__main__":
    main()
