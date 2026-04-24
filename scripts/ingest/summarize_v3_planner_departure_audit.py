#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.ingest.audit_v3_planner_departures import OUTPUT_PATH as DEFAULT_AUDIT_PATH
except ModuleNotFoundError:
    from audit_v3_planner_departures import OUTPUT_PATH as DEFAULT_AUDIT_PATH


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = ROOT / "data" / "v3_planner_departure_summary.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def row_label(row: dict[str, Any]) -> str:
    parts = []
    if row.get("route"):
        parts.append(str(row["route"]))
    if row.get("station"):
        parts.append(str(row["station"]))
    if row.get("operatorId") and not parts:
        parts.append(str(row["operatorId"]))
    return " / ".join(parts) or "Unknown"


def markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], limit: int) -> str:
    visible = rows[:limit]
    if not visible:
        return "_None._\n"
    header = "| " + " | ".join(title for title, _ in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in visible:
        values = []
        for _, key in columns:
            if key == "label":
                values.append(row_label(row))
            else:
                values.append(str(row.get(key, "")))
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, divider, *body]) + "\n"


def build_summary(report: dict[str, Any], limit: int = 10) -> str:
    summary = report.get("summary", {})
    aggregates = report.get("aggregates", {})
    lines = [
        "# v3 Planner Departure Audit Summary",
        "",
        "## Headline",
        "",
        f"- forbidden_same_operator_borrow_count: `{summary.get('forbidden_same_operator_borrow_count', 'n/a')}`",
        f"- unsurfaced_boardable_trip_stop_count: `{summary.get('unsurfaced_boardable_trip_stop_count', 'n/a')}`",
        f"- no_boardable_station_route_pair_count: `{summary.get('no_boardable_station_route_pair_count', 'n/a')}`",
        f"- terminal_only_station_route_pair_count: `{summary.get('terminal_only_station_route_pair_count', 'n/a')}`",
        "",
        "## Unsurfaced Boardable Trip Stops By Operator",
        "",
        markdown_table(
            aggregates.get("unsurfacedBoardableTripStopsByOperator", []),
            [("Operator", "operatorId"), ("Count", "count")],
            limit,
        ),
        "## Unsurfaced Boardable Trip Stops By Trip Route",
        "",
        markdown_table(
            aggregates.get("unsurfacedBoardableTripStopsByTripRoute", []),
            [("Route", "label"), ("Operator", "operatorId"), ("Count", "count")],
            limit,
        ),
        "## Unsurfaced Boardable Trip Stops By Route And Station",
        "",
        markdown_table(
            aggregates.get("unsurfacedBoardableTripStopsByTripRouteStation", []),
            [("Route / Station", "label"), ("Operator", "operatorId"), ("Count", "count")],
            limit,
        ),
        "## Visible Station/Route Pairs With No Boardable Departure",
        "",
        markdown_table(
            aggregates.get("noBoardableStationRoutePairsByOperator", []),
            [("Operator", "operatorId"), ("Count", "count")],
            limit,
        ),
        "## No-Boardable Pairs By Route",
        "",
        markdown_table(
            aggregates.get("noBoardableStationRoutePairsByRoute", []),
            [("Route", "label"), ("Operator", "operatorId"), ("Count", "count")],
            limit,
        ),
        "## Terminal-Only Pairs By Route",
        "",
        markdown_table(
            aggregates.get("terminalOnlyStationRoutePairsByRoute", []),
            [("Route", "label"), ("Operator", "operatorId"), ("Count", "count")],
            limit,
        ),
    ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize v3 planner departure audit warning families.")
    parser.add_argument("--input", type=Path, default=DEFAULT_AUDIT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    input_path = args.input if args.input.is_absolute() else ROOT / args.input
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    report = load_json(input_path)
    if "aggregates" not in report:
        raise SystemExit("Audit report has no aggregates. Rerun scripts/ingest/audit_v3_planner_departures.py first.")
    summary = build_summary(report, limit=args.limit)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary, encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
