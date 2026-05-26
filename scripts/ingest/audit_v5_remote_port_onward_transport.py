#!/usr/bin/env python3
"""Triage remote V5 ship ports into no-onward-collection vs island-bus work.

This is the layer after remote-port identity audit:

1. Fix suspicious identities first.
2. Confirm ports that do not need onward public-transport collection.
3. Only then collect island bus systems for the remaining ports.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IDENTITY_AUDIT = ROOT / "data" / "v5_remote_port_identity_audit.json"
DEFAULT_OUTPUT = ROOT / "data" / "v5_remote_port_onward_transport_audit.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_remote_port_onward_transport_audit.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "v5_remote_port_onward_transport_audit.md"


# These are not "no bus exists" facts.  They are islands/ports where a bus-like
# system is plausible enough that we should search official sources before
# marking the port as terminal-only.
KNOWN_OR_PLAUSIBLE_ISLAND_BUS_HINTS = [
    "西表",
    "竹富",
    "小浜",
    "黒島",
    "波照間",
    "鳩間",
    "座間味",
    "阿嘉",
    "渡嘉敷",
    "粟国",
    "久米",
    "八丈",
    "母島",
    "父島",
    "利島",
    "新島",
    "式根島",
    "神津",
    "三宅",
    "佐渡",
    "隠岐",
    "礼文",
    "利尻",
    "奥尻",
    "奄美",
    "加計呂麻",
    "徳之島",
    "与論",
    "屋久島",
    "種子島",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def plausible_bus_hint(port_name: str, operators: list[str]) -> bool:
    text = " ".join([port_name, *operators])
    return any(hint in text for hint in KNOWN_OR_PLAUSIBLE_ISLAND_BUS_HINTS)


def classify(row: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    port_name = str(row["portName"])
    operators = row.get("operatorContexts") or []
    sailings = int(row.get("playableSailingCount") or 0)
    bus_distance = (row.get("nearestBusStop") or {}).get("distanceMeters")
    rail_distance = (row.get("nearestRail") or {}).get("distanceMeters")

    if row.get("severity") == "needs_identity_review":
        return "identity_review_first", ["port identity or coordinate is not trusted enough for onward triage"]

    if sailings == 0:
        return "type2_no_collection_needed_now", ["not used by current playable ship sailings"]

    if plausible_bus_hint(port_name, operators):
        reasons.append("island/bus hint exists; collect or verify official island bus before terminal-only decision")
        return "type1_collect_island_bus", reasons

    if isinstance(bus_distance, int) and bus_distance <= 10_000:
        reasons.append(f"bus source exists within {bus_distance}m but outside 2km; likely needs local access review")
        return "type1_collect_island_bus", reasons

    if isinstance(rail_distance, int) and rail_distance <= 10_000:
        reasons.append(f"rail exists within {rail_distance}m but outside 2km; likely needs local access review")
        return "type1_collect_island_bus", reasons

    # This is deliberately a candidate bucket.  We still need a source check
    # before permanently marking a playable port as terminal-only.
    if (bus_distance is None or bus_distance > 20_000) and (rail_distance is None or rail_distance > 20_000):
        reasons.append("no known rail/bus source nearby; candidate terminal-only remote port")
        return "type2_candidate_confirm_no_onward_collection", reasons

    reasons.append("remote record, but nearby access signal is ambiguous")
    return "type1_collect_island_bus", reasons


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# V5 Remote Port Onward Transport Audit",
        "",
        "This audit applies the gameplay rule that true terminal-only remote ports do",
        "not need bus collection.  It does not collect bus data.  It decides what to",
        "review first.",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- `{key}`: {value}")
    for category in [
        "identity_review_first",
        "type2_no_collection_needed_now",
        "type2_candidate_confirm_no_onward_collection",
        "type1_collect_island_bus",
    ]:
        lines.extend(["", f"## {category}", ""])
        rows = [row for row in payload["ports"] if row["category"] == category]
        if not rows:
            lines.append("- None.")
            continue
        for row in rows[:80]:
            reason = "; ".join(row["reasons"])
            lines.append(f"- **{row['portName']}** ({row['playableSailingCount']} sailings): {reason}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-audit", type=Path, default=DEFAULT_IDENTITY_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()

    identity = read_json(args.identity_audit)
    rows = []
    for source_row in identity.get("ports") or []:
        category, reasons = classify(source_row)
        rows.append({
            "portName": source_row["portName"],
            "category": category,
            "reasons": reasons,
            "identitySeverity": source_row.get("severity"),
            "identityReasons": source_row.get("reasons") or [],
            "identityWarnings": source_row.get("warnings") or [],
            "coordinate": source_row.get("coordinate"),
            "operatorContexts": source_row.get("operatorContexts") or [],
            "playableSailingCount": source_row.get("playableSailingCount", 0),
            "nearestRail": source_row.get("nearestRail"),
            "nearestBusStop": source_row.get("nearestBusStop"),
            "sampleSailings": source_row.get("sampleSailings") or [],
            "searchQueries": [
                f"{source_row['portName']} 島内 バス 時刻表 公式",
                f"{source_row['portName']} 港 交通 アクセス 公式",
                f"{source_row['portName']} 公共交通 バス",
            ],
        })

    order = {
        "identity_review_first": 0,
        "type2_no_collection_needed_now": 1,
        "type2_candidate_confirm_no_onward_collection": 2,
        "type1_collect_island_bus": 3,
    }
    rows.sort(key=lambda row: (order.get(row["category"], 9), -int(row["playableSailingCount"] or 0), row["portName"]))
    counts = Counter(row["category"] for row in rows)
    payload = {
        "schemaVersion": "v5_remote_port_onward_transport_audit_v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "sourceIdentityAudit": str(args.identity_audit.relative_to(ROOT)),
        "summary": {
            "remotePortCount": len(rows),
            "identityReviewFirst": counts.get("identity_review_first", 0),
            "type2NoCollectionNeededNow": counts.get("type2_no_collection_needed_now", 0),
            "type2CandidateConfirmNoOnwardCollection": counts.get("type2_candidate_confirm_no_onward_collection", 0),
            "type1CollectIslandBus": counts.get("type1_collect_island_bus", 0),
        },
        "rules": {
            "identityReviewFirst": "Do not decide terminal-only or bus collection until the port identity/coordinate is fixed.",
            "type2NoCollectionNeededNow": "No current playable sailing uses this port; no bus collection is needed for current gameplay.",
            "type2CandidateConfirmNoOnwardCollection": "Looks like terminal-only remote port, but needs a source check before permanent no-collection classification.",
            "type1CollectIslandBus": "Likely has or needs island/local access bus review after type2 candidates are cleared.",
        },
        "ports": rows,
    }
    write_json(args.output, payload)
    write_json(args.docs_output, payload)
    write_markdown(args.markdown, payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(json.dumps(rows[:30], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
