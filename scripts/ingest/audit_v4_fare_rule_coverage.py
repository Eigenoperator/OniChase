#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_BUNDLE = ROOT / "docs" / "data" / "v4_gameplay_map_bundle.json.gz"
DEFAULT_FARE_RULES = ROOT / "docs" / "data" / "v4_fare_rules.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_fare_rule_coverage_audit.json"


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def known_operator_and_route_ids(fare_rules: dict[str, Any]) -> tuple[set[str], set[str]]:
    operators: set[str] = set()
    routes: set[str] = set()
    for table in (fare_rules.get("ordinaryFareTables") or {}).values():
        if table.get("routeIds"):
            routes.update(table.get("routeIds") or [])
        else:
            operators.update(table.get("operatorIds") or [])
    for table in (fare_rules.get("stationPairFareTables") or {}).values():
        if table.get("routeIds"):
            routes.update(table.get("routeIds") or [])
        else:
            operators.update(table.get("operatorIds") or [])
    for mapping in (fare_rules.get("operatorFareMappings") or []):
        operators.update(mapping.get("operatorIds") or [])
    if {"jr_hokkaido", "jr_east", "jr_central", "jr_west", "jr_kyushu"} & operators:
        operators.add("shinkansen")
    return operators, routes


def audit(map_bundle: dict[str, Any], fare_rules: dict[str, Any]) -> dict[str, Any]:
    covered_operator_ids, covered_route_ids = known_operator_and_route_ids(fare_rules)
    by_operator: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "operatorId": "",
        "operatorNames": set(),
        "routeCount": 0,
        "routeIds": [],
        "routeNames": [],
    })
    route_covered_by_rule: dict[str, bool] = {}
    for route in map_bundle.get("serviceRoutes") or []:
        operator_id = route.get("operatorId") or ""
        route_id = route.get("id") or ""
        item = by_operator[operator_id]
        item["operatorId"] = operator_id
        item["operatorNames"].add(route.get("operatorName") or operator_id)
        item["routeCount"] += 1
        item["routeIds"].append(route_id)
        item["routeNames"].append(route.get("shortName") or route.get("longName") or route.get("id"))
        route_covered_by_rule[route_id] = operator_id in covered_operator_ids or route_id in covered_route_ids

    operators = []
    for operator_id, item in by_operator.items():
        covered_route_count = sum(1 for route_id in item["routeIds"] if route_covered_by_rule.get(route_id))
        covered = covered_route_count == item["routeCount"]
        operators.append({
            "operatorId": operator_id,
            "operatorNames": sorted(item["operatorNames"]),
            "routeCount": item["routeCount"],
            "coveredRouteCount": covered_route_count,
            "coveredByRealFareRule": covered,
            "routeIds": item["routeIds"],
            "routeNames": sorted(set(item["routeNames"])),
        })
    operators.sort(key=lambda item: (not item["coveredByRealFareRule"], -item["routeCount"], item["operatorId"]))
    missing = [item for item in operators if not item["coveredByRealFareRule"]]
    covered = [item for item in operators if item["coveredByRealFareRule"]]
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "fareRulesModelVersion": fare_rules.get("modelVersion"),
        "operatorCount": len(operators),
        "coveredOperatorCount": len(covered),
        "missingOperatorCount": len(missing),
        "routeCount": sum(item["routeCount"] for item in operators),
        "coveredRouteCount": sum(item["coveredRouteCount"] for item in operators),
        "missingRouteCount": sum(item["routeCount"] - item["coveredRouteCount"] for item in operators),
        "failureCount": len(missing),
        "operators": operators,
        "missingOperators": missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map-bundle", type=Path, default=DEFAULT_MAP_BUNDLE)
    parser.add_argument("--fare-rules", type=Path, default=DEFAULT_FARE_RULES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = audit(load_json(args.map_bundle), load_json(args.fare_rules))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output.relative_to(ROOT)),
        "coveredOperatorCount": payload["coveredOperatorCount"],
        "missingOperatorCount": payload["missingOperatorCount"],
        "coveredRouteCount": payload["coveredRouteCount"],
        "missingRouteCount": payload["missingRouteCount"],
        "failureCount": payload["failureCount"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
