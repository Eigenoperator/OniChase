#!/usr/bin/env python3
"""Audit remote/small-island ship ports for suspicious identity or coordinates.

This is intentionally narrower than audit_v5_ship_port_access_priority.py:
it only reviews ports already classified as remote/small-island no-access
records, and asks whether their current port identity is trustworthy enough to
leave them as remote records.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRIORITY_AUDIT = ROOT / "data" / "v5_ship_port_access_priority_audit.json"
DEFAULT_SHIP_MAP = ROOT / "docs" / "data" / "v5_ship_map.geojson"
DEFAULT_OUTPUT = ROOT / "data" / "v5_remote_port_identity_audit.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_remote_port_identity_audit.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "v5_remote_port_identity_audit.md"


GENERIC_PORT_NAMES = {
    "中島",
    "久賀",
    "大島",
    "姫島",
    "青島",
    "黒島",
    "馬島",
    "湊",
    "西ノ島",
    "高島",
    "神浦",
    "柳",
    "明石",
}
DISTANT_REVIEW_METERS = 20_000
NEAR_MAINLAND_REVIEW_METERS = 10_000


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_coord(coord: dict[str, Any]) -> str:
    return f"{float(coord['lat']):.6f},{float(coord['lon']):.6f}"


def score_from_source(source: str) -> int | None:
    match = re.search(r"\bscore=(\d+)\b", source)
    return int(match.group(1)) if match else None


def display_overlaps_name(port_name: str, display: str | None) -> bool:
    if not display:
        return False
    tokens = {port_name}
    for suffix in ("フェリーターミナル", "ターミナル", "港"):
        if port_name.endswith(suffix) and len(port_name) > len(suffix):
            tokens.add(port_name[: -len(suffix)])
    # Common official abbreviations in map/geocoder display names.
    if "岡田" in port_name:
        tokens.add("岡田")
    if "仁斗田" in port_name:
        tokens.add("仁斗田")
    return any(len(token) >= 2 and token in display for token in tokens)


def ship_map_ports(ship_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {}
    for feature in ship_map.get("features") or []:
        props = feature.get("properties") or {}
        if props.get("kind") != "port":
            continue
        name = props.get("name")
        if name:
            rows[str(name)] = props
    return rows


def classify_row(row: dict[str, Any], duplicate_names: list[str], props: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    source = str(row.get("coordinateSource") or props.get("coordinateSource") or "")
    display = row.get("coordinateDisplayName") or props.get("coordinateDisplayName")
    port_name = str(row["portName"])
    nearest_rail = row.get("nearestRail") or {}
    nearest_bus = row.get("nearestBusStop") or {}
    rail_distance = nearest_rail.get("distanceMeters")
    bus_distance = nearest_bus.get("distanceMeters")
    operators = row.get("operatorContexts") or []

    if len(duplicate_names) >= 2:
        reasons.append(f"same coordinate shared by {len(duplicate_names)} port names: {', '.join(duplicate_names[:6])}")
    if "needs_precise_port_review" in source:
        source_score = score_from_source(source)
        if source_score is None or source_score < 30:
            reasons.append("weak geocoder source still marked needs_precise_port_review")
        else:
            warnings.append("geocoder source still marked needs_precise_port_review")
    if source.startswith("online_verified:OSM/Nominatim") and not display_overlaps_name(port_name, display):
        reasons.append("OSM/Nominatim display does not clearly overlap the port name")
    if port_name in GENERIC_PORT_NAMES and not source.startswith("manual_verified:"):
        reasons.append("generic same-name port is not manually verified")
    if len(operators) >= 2 and not source.startswith("manual_verified:"):
        warnings.append(f"multiple operator contexts: {', '.join(operators[:5])}")
    if isinstance(rail_distance, int) and rail_distance <= NEAR_MAINLAND_REVIEW_METERS:
        warnings.append(f"rail is nearby at {rail_distance}m; confirm this is truly an island/no-access case")
    if isinstance(bus_distance, int) and bus_distance <= NEAR_MAINLAND_REVIEW_METERS:
        warnings.append(f"bus stop is nearby at {bus_distance}m but outside 2km")
    if isinstance(rail_distance, int) and isinstance(bus_distance, int):
        if rail_distance >= DISTANT_REVIEW_METERS and bus_distance >= DISTANT_REVIEW_METERS and not source.startswith("manual_verified:"):
            warnings.append("both nearest rail and bus are far; coordinate may still need map spot-check")

    severity = "ok"
    if reasons:
        severity = "needs_identity_review"
    elif warnings:
        severity = "watch"

    return {
        "portName": port_name,
        "severity": severity,
        "reasons": reasons,
        "warnings": warnings,
        "coordinate": row.get("coordinate"),
        "coordinateSource": source or None,
        "coordinateDisplayName": display,
        "operatorContexts": operators,
        "playableSailingCount": row.get("playableSailingCount", 0),
        "nearestRail": row.get("nearestRail"),
        "nearestBusStop": row.get("nearestBusStop"),
        "sampleSailings": row.get("sampleSailings") or [],
        "searchQueries": row.get("searchQueries") or [],
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# V5 Remote Port Identity Audit",
        "",
        "This audit reviews the ports that are already classified as remote/small-island",
        "2 km access gaps. It does not add connectors. It only flags cases where",
        "the port identity or coordinate still looks risky.",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Needs Identity Review", ""])
    review_rows = [row for row in payload["ports"] if row["severity"] == "needs_identity_review"]
    if not review_rows:
        lines.append("- None.")
    for row in review_rows[:50]:
        reason = "; ".join(row["reasons"])
        coord = row.get("coordinate") or {}
        lines.append(
            f"- **{row['portName']}** ({coord.get('lat')}, {coord.get('lon')}), "
            f"{row['playableSailingCount']} sailings: {reason}"
        )
    lines.extend(["", "## Watch", ""])
    watch_rows = [row for row in payload["ports"] if row["severity"] == "watch"]
    if not watch_rows:
        lines.append("- None.")
    for row in watch_rows[:50]:
        warning = "; ".join(row["warnings"])
        lines.append(f"- **{row['portName']}**, {row['playableSailingCount']} sailings: {warning}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--priority-audit", type=Path, default=DEFAULT_PRIORITY_AUDIT)
    parser.add_argument("--ship-map", type=Path, default=DEFAULT_SHIP_MAP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()

    priority = read_json(args.priority_audit)
    ship_map = read_json(args.ship_map)
    props_by_name = ship_map_ports(ship_map)
    remote_rows = [
        row
        for row in priority.get("ports") or []
        if row.get("category") == "record_remote_or_small_island"
    ]
    coord_to_names: dict[str, list[str]] = defaultdict(list)
    for row in remote_rows:
        coord_to_names[normalize_coord(row["coordinate"])].append(row["portName"])

    reviewed = [
        classify_row(row, coord_to_names[normalize_coord(row["coordinate"])], props_by_name.get(row["portName"], {}))
        for row in remote_rows
    ]
    severity_order = {"needs_identity_review": 0, "watch": 1, "ok": 2}
    reviewed.sort(
        key=lambda row: (
            severity_order.get(row["severity"], 9),
            -int(row.get("playableSailingCount") or 0),
            row["portName"],
        )
    )
    summary = {
        "remotePortCount": len(reviewed),
        "needsIdentityReview": sum(1 for row in reviewed if row["severity"] == "needs_identity_review"),
        "watch": sum(1 for row in reviewed if row["severity"] == "watch"),
        "ok": sum(1 for row in reviewed if row["severity"] == "ok"),
        "duplicateCoordinateGroups": sum(1 for names in coord_to_names.values() if len(names) >= 2),
        "playableAffectedNeedsReview": sum(
            1
            for row in reviewed
            if row["severity"] == "needs_identity_review" and int(row.get("playableSailingCount") or 0) > 0
        ),
    }
    payload = {
        "schemaVersion": "v5_remote_port_identity_audit_v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "sourcePriorityAudit": str(args.priority_audit.relative_to(ROOT)),
        "summary": summary,
        "rules": {
            "needsIdentityReview": "Coordinate/name/source signals are risky enough that this port should be checked before it is accepted as a remote island record.",
            "watch": "Probably acceptable as a remote island record, but has a non-blocking signal such as nearby source coverage or non-manual geocoder provenance.",
            "ok": "No current identity red flag from this static audit.",
        },
        "ports": reviewed,
    }
    write_json(args.output, payload)
    write_json(args.docs_output, payload)
    write_markdown(args.markdown, payload)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(reviewed[:20], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
