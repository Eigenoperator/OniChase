#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import audit_v3_map_timetable_coverage
import audit_v3_planner_departures
import audit_v3_tokyo_bundle
from audit_v3_train_datasets import dataset_report


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DEFAULT_OUTPUT_PATH = DATA_DIR / "v3_data_quality_audit.json"
UNIFIED_TRAINS_PATH = DATA_DIR / "v3_trains_unified.json.gz"

CHECKS = ("coverage", "planner-departures", "unified", "bundle", "raw-datasets")


def load_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def hhmm_to_minutes(value: Any) -> int | None:
    if not isinstance(value, str) or ":" not in value:
        return None
    hour, minute = value.split(":", 1)
    try:
        total = int(hour) * 60 + int(minute)
    except ValueError:
        return None
    return total


def check_status(failures: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> str:
    if failures:
        return "fail"
    if warnings:
        return "warn"
    return "pass"


def make_check(
    check_id: str,
    title: str,
    metrics: dict[str, Any],
    failures: list[dict[str, Any]] | None = None,
    warnings: list[dict[str, Any]] | None = None,
    samples: dict[str, Any] | None = None,
    artifacts: dict[str, str] | None = None,
) -> dict[str, Any]:
    failure_items = failures or []
    warning_items = warnings or []
    return {
        "id": check_id,
        "title": title,
        "status": check_status(failure_items, warning_items),
        "metrics": metrics,
        "failures": failure_items,
        "warnings": warning_items,
        "samples": samples or {},
        "artifacts": artifacts or {},
    }


def first_items(items: list[Any], limit: int) -> list[Any]:
    return items[: max(0, limit)]


def run_coverage_check(max_samples: int) -> dict[str, Any]:
    report = audit_v3_map_timetable_coverage.build_audit()
    audit_v3_map_timetable_coverage.write_json(audit_v3_map_timetable_coverage.OUTPUT_PATH, report)
    summary = report["summary"]
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if summary["zero_stop_station_membership_count"]:
        failures.append(
            {
                "code": "rendered_station_without_regular_timetable_stop",
                "count": summary["zero_stop_station_membership_count"],
                "message": "Some rendered station memberships have no timetable stop.",
            }
        )
    if summary["rendered_line_without_trip_count"]:
        failures.append(
            {
                "code": "rendered_line_without_timetable_trip",
                "count": summary["rendered_line_without_trip_count"],
                "message": "Some rendered lines have no matching timetable trip after alias/equivalence rules.",
            }
        )
    if summary.get("non_regular_zero_station_membership_count", 0):
        warnings.append(
            {
                "code": "non_regular_station_without_current_weekday_service",
                "count": summary["non_regular_zero_station_membership_count"],
                "message": "Known seasonal/event stations have no regular weekday service in the current source timetable.",
            }
        )

    zero_lines = [
        line
        for line in report.get("line_reports", [])
        if line.get("zero_stop_station_count") or line.get("unresolved_station_count")
    ]
    non_regular_lines = [
        {
            "operator_id": line.get("operator_id"),
            "line_name_ja": line.get("line_name_ja"),
            "stations": line.get("non_regular_zero_station_samples", []),
        }
        for line in report.get("line_reports", [])
        if line.get("non_regular_zero_station_count")
    ]

    return make_check(
        "coverage",
        "Rendered map/timetable coverage",
        metrics=summary,
        failures=failures,
        warnings=warnings,
        samples={
            "zero_or_unresolved_lines": first_items(zero_lines, max_samples),
            "non_regular_zero_lines": first_items(non_regular_lines, max_samples),
        },
        artifacts={
            "legacy_component_report": relative(audit_v3_map_timetable_coverage.OUTPUT_PATH),
        },
    )


def run_planner_departure_check(max_samples: int) -> dict[str, Any]:
    report = audit_v3_planner_departures.build_audit()
    audit_v3_planner_departures.write_json(audit_v3_planner_departures.OUTPUT_PATH, report)
    summary = report["summary"]
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if summary["forbidden_same_operator_borrow_count"]:
        failures.append(
            {
                "code": "forbidden_same_operator_borrowing",
                "count": summary["forbidden_same_operator_borrow_count"],
                "message": "JR East / Tokyo Metro / Toei lines should not borrow same-operator departures across unrelated physical lines.",
            }
        )
    if summary["unsurfaced_boardable_trip_stop_count"]:
        warnings.append(
            {
                "code": "unsurfaced_boardable_trip_stop",
                "count": summary["unsurfaced_boardable_trip_stop_count"],
                "message": "Some trips have downstream boardable stops that surface under no planner line at all.",
            }
        )
    if summary["no_boardable_station_route_pair_count"]:
        warnings.append(
            {
                "code": "visible_station_route_without_boardable_departure",
                "count": summary["no_boardable_station_route_pair_count"],
                "message": "Some visible station/route pairs never surface a boardable departure and should be checked against planner expectations.",
            }
        )

    return make_check(
        "planner-departures",
        "Planner-facing line/train departure visibility",
        metrics=summary,
        failures=failures,
        warnings=warnings,
        samples={
            "forbidden_same_operator_borrow": first_items(report.get("samples", {}).get("forbiddenSameOperatorBorrow", []), max_samples),
            "unsurfaced_boardable_trip_stops": first_items(report.get("samples", {}).get("unsurfacedBoardableTripStops", []), max_samples),
            "focus_operator_route_reports": first_items(report.get("samples", {}).get("focusOperatorRouteReports", []), max_samples),
        },
        artifacts={
            "planner_departure_report": relative(audit_v3_planner_departures.OUTPUT_PATH),
        },
    )


def unified_signature(train: dict[str, Any]) -> tuple[Any, ...]:
    stops = train.get("stops") or []
    return (
        train.get("operator_id"),
        train.get("line"),
        train.get("service_name"),
        train.get("direction"),
        tuple(
            (
                stop.get("station_key"),
                stop.get("arrival"),
                stop.get("departure"),
                stop.get("line"),
            )
            for stop in stops
        ),
    )


def train_time_sequence_issues(train: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    previous = None
    rollover_offset = 0
    for stop in train.get("stops") or []:
        minutes = hhmm_to_minutes(stop.get("departure") or stop.get("arrival"))
        if minutes is None:
            continue
        adjusted = minutes + rollover_offset
        if previous is not None and adjusted < previous:
            if previous >= 21 * 60 and minutes <= 3 * 60:
                rollover_offset += 24 * 60
                adjusted = minutes + rollover_offset
            else:
                issues.append(
                    {
                        "sequence": stop.get("sequence"),
                        "station_key": stop.get("station_key"),
                        "time": stop.get("departure") or stop.get("arrival"),
                    }
                )
        previous = adjusted
    return issues


def run_unified_check(max_samples: int) -> dict[str, Any]:
    payload = load_json(UNIFIED_TRAINS_PATH)
    trains = payload.get("trains", [])

    id_counts: Counter[str] = Counter()
    signature_counts: Counter[tuple[Any, ...]] = Counter()
    trains_without_stops = []
    missing_station_key_stops = []
    time_order_issues = []

    for train in trains:
        train_id = str(train.get("id") or "")
        id_counts[train_id] += 1
        signature_counts[unified_signature(train)] += 1
        stops = train.get("stops") or []
        if not stops:
            trains_without_stops.append(
                {
                    "train_id": train.get("id"),
                    "operator_id": train.get("operator_id"),
                    "line": train.get("line"),
                    "train_number": train.get("train_number"),
                }
            )
            continue
        for stop in stops:
            if not stop.get("station_key"):
                missing_station_key_stops.append(
                    {
                        "train_id": train.get("id"),
                        "operator_id": train.get("operator_id"),
                        "line": train.get("line"),
                        "sequence": stop.get("sequence"),
                        "station_name": stop.get("station_name"),
                    }
                )
        issues = train_time_sequence_issues(train)
        if issues:
            time_order_issues.append(
                {
                    "train_id": train.get("id"),
                    "operator_id": train.get("operator_id"),
                    "line": train.get("line"),
                    "train_number": train.get("train_number"),
                    "issues": issues[:5],
                }
            )

    duplicate_id_groups = {key: count for key, count in id_counts.items() if key and count > 1}
    duplicate_signature_rows = sum(count - 1 for count in signature_counts.values() if count > 1)
    duplicate_signature_groups = sum(1 for count in signature_counts.values() if count > 1)

    failures = []
    if duplicate_id_groups:
        failures.append(
            {
                "code": "duplicate_unified_train_ids",
                "count": len(duplicate_id_groups),
                "message": "Unified train ids must be unique because the web client indexes trips by id.",
            }
        )
    if duplicate_signature_groups:
        failures.append(
            {
                "code": "duplicate_unified_train_signatures",
                "count": duplicate_signature_groups,
                "rows": duplicate_signature_rows,
                "message": "Unified train signatures should be deduped before gameplay bundle generation.",
            }
        )
    if trains_without_stops:
        failures.append(
            {
                "code": "unified_trains_without_stops",
                "count": len(trains_without_stops),
                "message": "Every unified train needs at least two usable stops before gameplay.",
            }
        )
    if missing_station_key_stops:
        failures.append(
            {
                "code": "unified_stops_without_station_key",
                "count": len(missing_station_key_stops),
                "message": "Every unified stop must have a station_key for station-group lookup.",
            }
        )
    if time_order_issues:
        failures.append(
            {
                "code": "unified_train_time_goes_backwards",
                "count": len(time_order_issues),
                "message": "Some train stop sequences go backwards in time outside the allowed midnight rollover.",
            }
        )

    metrics = {
        "unified_train_count": len(trains),
        "duplicate_id_group_count": len(duplicate_id_groups),
        "duplicate_signature_group_count": duplicate_signature_groups,
        "duplicate_signature_row_count": duplicate_signature_rows,
        "train_without_stop_count": len(trains_without_stops),
        "missing_station_key_stop_count": len(missing_station_key_stops),
        "time_order_issue_train_count": len(time_order_issues),
    }
    return make_check(
        "unified",
        "Unified gameplay timetable integrity",
        metrics=metrics,
        failures=failures,
        samples={
            "duplicate_train_ids": first_items(
                [{"train_id": key, "count": count} for key, count in duplicate_id_groups.items()],
                max_samples,
            ),
            "trains_without_stops": first_items(trains_without_stops, max_samples),
            "missing_station_key_stops": first_items(missing_station_key_stops, max_samples),
            "time_order_issues": first_items(time_order_issues, max_samples),
        },
        artifacts={"unified_trains": relative(UNIFIED_TRAINS_PATH)},
    )


def run_bundle_check(max_samples: int) -> dict[str, Any]:
    report = audit_v3_tokyo_bundle.build_audit()
    audit_v3_tokyo_bundle.write_json(audit_v3_tokyo_bundle.REPORT_PATH, report)
    summary = report["summary"]
    failures = []
    warnings = []

    if summary["train_stations_without_map_count"]:
        failures.append(
            {
                "code": "train_station_without_map_group",
                "count": summary["train_stations_without_map_count"],
                "message": "Some timetable stations do not map to any v3 station group.",
            }
        )
    if summary["collapsed_duplicate_map_name_count"]:
        failures.append(
            {
                "code": "collapsed_distinct_same_name_stations",
                "count": summary["collapsed_duplicate_map_name_count"],
                "message": "Some physically distinct same-name stations were collapsed in the bundle.",
            }
        )
    if summary["trains_with_unmapped_stops_count"]:
        failures.append(
            {
                "code": "trains_with_unmapped_stops",
                "count": summary["trains_with_unmapped_stops_count"],
                "message": "Some unified train stops could not be resolved into the visible station layer.",
            }
        )
    if summary["tiny_route_count"]:
        warnings.append(
            {
                "code": "tiny_or_empty_routes",
                "count": summary["tiny_route_count"],
                "message": "Some routes are tiny fragments or through-service aliases and should be reviewed.",
            }
        )
    if summary["huge_route_count"]:
        warnings.append(
            {
                "code": "huge_routes",
                "count": summary["huge_route_count"],
                "message": "Some routes are broad service families and should be checked for over-merge risk.",
            }
        )

    station_quality = report.get("station_quality", {})
    route_quality = report.get("route_quality", {})
    return make_check(
        "bundle",
        "Generated v3 bundle station/route integrity",
        metrics=summary,
        failures=failures,
        warnings=warnings,
        samples={
            "train_stations_without_map": first_items(station_quality.get("train_stations_without_map", []), max_samples),
            "collapsed_duplicate_map_names": first_items(station_quality.get("collapsed_duplicate_map_names", []), max_samples),
            "tiny_or_empty_routes": first_items(route_quality.get("tiny_or_empty_routes", []), max_samples),
            "huge_routes": first_items(route_quality.get("huge_routes", []), max_samples),
        },
        artifacts={"legacy_component_report": relative(audit_v3_tokyo_bundle.REPORT_PATH)},
    )


def raw_dataset_paths() -> list[Path]:
    paths = sorted(DATA_DIR.glob("v3_tokyo_*weekday_train_instances.json*"))
    shinkansen_path = DATA_DIR / "shinkansen_v2_weekday_train_instances_merged.json"
    if shinkansen_path.exists():
        paths.append(shinkansen_path)
    return paths


def run_raw_dataset_check(max_samples: int) -> dict[str, Any]:
    reports = [dataset_report(path) for path in raw_dataset_paths()]
    write_json(DATA_DIR / "v3_timetable_audit_report.json", reports)
    failures = []
    warnings = []
    empty_reports = [report for report in reports if report["train_count"] <= 0 or report["unique_signature_count"] <= 0]
    duplicate_signature_reports = [report for report in reports if report["duplicate_signature_groups"] > 0]
    duplicate_number_reports = [report for report in reports if report["duplicate_train_number_groups"] > 0]

    if empty_reports:
        failures.append(
            {
                "code": "empty_raw_train_dataset",
                "count": len(empty_reports),
                "message": "Raw train datasets must not be empty.",
            }
        )
    if duplicate_signature_reports:
        warnings.append(
            {
                "code": "raw_dataset_duplicate_signatures",
                "count": len(duplicate_signature_reports),
                "message": "Raw collectors still contain source duplicates; this is allowed if the unified index dedupes them.",
            }
        )
    if duplicate_number_reports:
        warnings.append(
            {
                "code": "raw_dataset_duplicate_train_numbers",
                "count": len(duplicate_number_reports),
                "message": "Some operators reuse train numbers or expose duplicate source entries; check unified id/signature results for gameplay safety.",
            }
        )

    metrics = {
        "dataset_count": len(reports),
        "raw_train_count": sum(report["train_count"] for report in reports),
        "raw_unique_signature_count": sum(report["unique_signature_count"] for report in reports),
        "datasets_with_duplicate_signatures": len(duplicate_signature_reports),
        "datasets_with_duplicate_train_numbers": len(duplicate_number_reports),
        "empty_dataset_count": len(empty_reports),
    }
    return make_check(
        "raw-datasets",
        "Raw collected timetable dataset health",
        metrics=metrics,
        failures=failures,
        warnings=warnings,
        samples={
            "empty_datasets": first_items(empty_reports, max_samples),
            "duplicate_signature_datasets": first_items(
                sorted(duplicate_signature_reports, key=lambda item: -item["duplicate_signature_groups"]),
                max_samples,
            ),
            "duplicate_train_number_datasets": first_items(
                sorted(duplicate_number_reports, key=lambda item: -item["duplicate_train_number_groups"]),
                max_samples,
            ),
        },
        artifacts={"legacy_component_report": relative(DATA_DIR / "v3_timetable_audit_report.json")},
    )


RUNNERS = {
    "coverage": run_coverage_check,
    "planner-departures": run_planner_departure_check,
    "unified": run_unified_check,
    "bundle": run_bundle_check,
    "raw-datasets": run_raw_dataset_check,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run standardized reusable v3 data-quality audits for map/timetable/gameplay data.",
    )
    parser.add_argument(
        "--checks",
        nargs="+",
        default=["all"],
        choices=("all", *CHECKS),
        help="Checks to run. Default: all.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path for the normalized JSON report.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=20,
        help="Maximum sample rows per check section.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full normalized JSON report instead of a compact summary.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on warnings as well as failures.",
    )
    return parser.parse_args()


def selected_checks(raw_checks: list[str]) -> list[str]:
    if "all" in raw_checks:
        return list(CHECKS)
    return list(dict.fromkeys(raw_checks))


def overall_status(checks: list[dict[str, Any]]) -> str:
    if any(check["status"] == "fail" for check in checks):
        return "fail"
    if any(check["status"] == "warn" for check in checks):
        return "warn"
    return "pass"


def build_report(check_names: list[str], max_samples: int) -> dict[str, Any]:
    checks = [RUNNERS[name](max_samples) for name in check_names]
    status_counts = Counter(check["status"] for check in checks)
    return {
        "id": "v3_data_quality_audit_v0_1",
        "schema_version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": overall_status(checks),
        "checks_requested": check_names,
        "summary": {
            "check_count": len(checks),
            "pass_count": status_counts.get("pass", 0),
            "warn_count": status_counts.get("warn", 0),
            "fail_count": status_counts.get("fail", 0),
        },
        "checks": checks,
    }


def print_summary(report: dict[str, Any], output_path: Path) -> None:
    lines = [
        f"v3 data quality: {report['status'].upper()}",
        f"report: {relative(output_path)}",
    ]
    for check in report["checks"]:
        metrics = check.get("metrics", {})
        important = []
        for key in (
            "zero_stop_station_membership_count",
            "rendered_line_without_trip_count",
            "forbidden_same_operator_borrow_count",
            "unsurfaced_boardable_trip_stop_count",
            "no_boardable_station_route_pair_count",
            "duplicate_id_group_count",
            "duplicate_signature_group_count",
            "train_stations_without_map_count",
            "collapsed_duplicate_map_name_count",
            "raw_train_count",
        ):
            if key in metrics:
                important.append(f"{key}={metrics[key]}")
        suffix = f" ({', '.join(important)})" if important else ""
        lines.append(f"- {check['id']}: {check['status']}{suffix}")
    print("\n".join(lines))


def main() -> int:
    args = parse_args()
    check_names = selected_checks(args.checks)
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    report = build_report(check_names, args.max_samples)
    write_json(output_path, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_summary(report, output_path)
    if report["status"] == "fail":
        return 1
    if args.strict and report["status"] == "warn":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
