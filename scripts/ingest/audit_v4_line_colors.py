#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_v4_japan_physical_map import load_json, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = ROOT / "docs" / "data" / "v4_maplibre" / "line_inventory.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_line_color_audit.json"


def build_audit(inventory: dict[str, Any]) -> dict[str, Any]:
    lines = inventory.get("lines", [])
    source_counts = Counter(line.get("lineColorSource") or "missing" for line in lines)
    fallback_by_operator: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    official_by_operator: Counter[tuple[str, str]] = Counter()

    for line in lines:
        operator_key = (line.get("operatorId") or "", line.get("operatorName") or "")
        if line.get("lineColorSource") == "official_line":
            official_by_operator[operator_key] += 1
            continue
        fallback_by_operator[operator_key].append(
            {
                "lineName": line.get("lineName"),
                "lineColor": line.get("lineColor"),
                "operatorColor": line.get("operatorColor"),
                "physicalStationCount": line.get("physicalStationCount"),
                "trackCenterlineCount": line.get("trackCenterlineCount"),
            }
        )

    fallback_operator_rows = []
    for (operator_id, operator_name), fallback_lines in fallback_by_operator.items():
        fallback_operator_rows.append(
            {
                "operatorId": operator_id,
                "operatorName": operator_name,
                "fallbackLineCount": len(fallback_lines),
                "officialLineCount": official_by_operator[(operator_id, operator_name)],
                "sampleFallbackLines": sorted(fallback_lines, key=lambda item: item["lineName"] or "")[:30],
            }
        )
    fallback_operator_rows.sort(key=lambda item: (-item["fallbackLineCount"], item["operatorName"], item["operatorId"]))

    return {
        "schema": "onichase.v4.line_color_audit.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceInventorySchema": inventory.get("schema"),
        "sourceInventoryGeneratedAt": inventory.get("generatedAt"),
        "counts": {
            "operatorLinePairs": len(lines),
            "lineColorSources": dict(sorted(source_counts.items())),
            "officialLinePairs": source_counts.get("official_line", 0),
            "operatorFallbackLinePairs": source_counts.get("operator_fallback", 0),
            "operatorsWithFallback": len(fallback_operator_rows),
        },
        "fallbackOperators": fallback_operator_rows[:100],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit v4 line-color coverage and remaining operator fallback colors.")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    audit = build_audit(load_json(args.inventory))
    write_json(args.output, audit)
    counts = audit["counts"]
    print(
        "Audited v4 line colors:",
        f"{counts['officialLinePairs']} official-line colors,",
        f"{counts['operatorFallbackLinePairs']} operator fallbacks,",
        f"{counts['operatorsWithFallback']} operators with fallback.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
