#!/usr/bin/env python3
"""Audit boundary stations that must belong to every adjacent physical line.

Route choices are built from service pattern station membership.  If a boundary
station is only counted on one side of a physical line boundary, the player can
lose the other side's route choice or see a through-service label instead.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from build_v4_gameplay_bundle import route_id_for


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_GAMEPLAY_MAP = ROOT / "docs" / "data" / "v4_gameplay_map_bundle.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_boundary_station_line_membership_audit.json"


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def station_group_name(groups: dict[str, dict[str, Any]], group_id: str) -> str:
    group = groups.get(group_id) or {}
    return str((group.get("names") or {}).get("ja") or group.get("primaryName") or group_id)


def route_title(route: dict[str, Any] | None, route_id: str) -> str:
    route = route or {}
    return str(route.get("shortName") or (route.get("tags") or {}).get("lineName") or route_id)


def audit_boundary_membership(physical_map: dict[str, Any], gameplay_map: dict[str, Any]) -> dict[str, Any]:
    physical_groups = {group["id"]: group for group in physical_map.get("stationGroups", []) if group.get("id")}
    gameplay_groups = {group["id"]: group for group in gameplay_map.get("stationGroups", []) if group.get("id")}
    groups = gameplay_groups or physical_groups
    routes = {route["id"]: route for route in gameplay_map.get("serviceRoutes", []) if route.get("id")}
    pattern_station_ids = {
        pattern.get("routeId"): set(pattern.get("stationGroupIds") or [])
        for pattern in gameplay_map.get("servicePatterns", [])
        if pattern.get("routeId")
    }

    lines_by_group_operator: dict[tuple[str, str], set[str]] = defaultdict(set)
    operator_names: dict[str, str] = {}
    for station in physical_map.get("physicalStations", []):
        group_id = station.get("stationGroupId")
        operator_id = station.get("operatorId")
        line_name = station.get("lineName")
        if not group_id or not operator_id or not line_name:
            continue
        lines_by_group_operator[(str(group_id), str(operator_id))].add(str(line_name))
        operator_names[str(operator_id)] = str(station.get("operatorName") or operator_id)

    boundary_groups = [
        (group_id, operator_id, sorted(line_names))
        for (group_id, operator_id), line_names in lines_by_group_operator.items()
        if len(line_names) >= 2
    ]
    missing: list[dict[str, Any]] = []
    missing_gameplay_route: list[dict[str, Any]] = []
    reviewed_examples: list[dict[str, Any]] = []
    for group_id, operator_id, line_names in sorted(boundary_groups, key=lambda item: (station_group_name(groups, item[0]), item[1])):
        line_results = []
        for line_name in line_names:
            route_id = route_id_for(operator_id, line_name)
            route = routes.get(route_id)
            in_pattern = group_id in pattern_station_ids.get(route_id, set())
            line_results.append(
                {
                    "lineName": line_name,
                    "routeId": route_id,
                    "routeTitle": route_title(route, route_id),
                    "routeExists": bool(route),
                    "stationInServicePattern": in_pattern,
                }
            )
            finding = {
                "kind": "boundary_station_missing_line_membership",
                "station": station_group_name(groups, group_id),
                "stationGroupId": group_id,
                "operatorId": operator_id,
                "operatorName": operator_names.get(operator_id, operator_id),
                "lineName": line_name,
                "routeId": route_id,
                "routeExists": bool(route),
                "stationInServicePattern": in_pattern,
                "allBoundaryLinesForOperator": line_names,
            }
            if route and not in_pattern:
                missing.append(finding)
            elif not route:
                missing_gameplay_route.append({**finding, "kind": "boundary_line_not_in_current_gameplay_routes"})
        reviewed_examples.append(
            {
                "station": station_group_name(groups, group_id),
                "stationGroupId": group_id,
                "operatorId": operator_id,
                "operatorName": operator_names.get(operator_id, operator_id),
                "lineCount": len(line_names),
                "lines": line_results,
            }
        )

    return {
        "schema": "onichase.v4.boundary_station_line_membership_audit.v1",
        "summary": {
            "boundaryStationOperatorGroupCount": len(boundary_groups),
            "missingMembershipCount": len(missing),
            "missingGameplayRouteCount": len(missing_gameplay_route),
            "policy": "If a station group is a physical boundary for multiple lines of the same operator and that line exists in the current gameplay route set, every adjacent line must include that station group in its gameplay service pattern. Lines not present in gameplay routes are reported separately as source/scope gaps, not display-membership failures.",
        },
        "missingMembership": missing[:300],
        "missingGameplayRoutes": missing_gameplay_route[:300],
        "reviewedBoundaryExamples": reviewed_examples,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--gameplay-map", type=Path, default=DEFAULT_GAMEPLAY_MAP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    physical_map = load_json(args.physical_map)
    gameplay_map = load_json(args.gameplay_map)
    payload = {
        "inputs": {
            "physicalMap": rel(args.physical_map),
            "gameplayMap": rel(args.gameplay_map),
        },
        **audit_boundary_membership(physical_map, gameplay_map),
    }
    write_json(args.output, payload)
    print(
        f"Wrote {rel(args.output)}: "
        f"boundary_groups={payload['summary']['boundaryStationOperatorGroupCount']} "
        f"missing={payload['summary']['missingMembershipCount']}"
    )


if __name__ == "__main__":
    main()
