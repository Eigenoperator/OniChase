#!/usr/bin/env python3
"""Aggregate reusable v4 data-quality audits.

This script is the broad first pass for the three recurring data-error classes:

* collection coverage holes: source/registry says data should exist, but current
  or gameplay has little/no service.
* train/route display mistakes: missing train numbers, raw numbered line labels,
  or labels that violate reviewed display axioms.
* transfer-equivalence mistakes: station groups that should/should not behave as
  direct transfers before a walking-time model exists.

It intentionally emits a report rather than trying to fix anything.  Add new
permanent checks here whenever a screenshot or manual inspection finds a bug.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_BUNDLE = ROOT / "docs" / "data" / "v4_gameplay_map_bundle.json.gz"
DEFAULT_TIMETABLE = ROOT / "docs" / "data" / "v4_gameplay_timetable_compact.json.gz"
DEFAULT_CURRENT = ROOT / "data" / "v4_current_weekday_train_instances.json.gz"
DEFAULT_SOURCE_REGISTRY = ROOT / "data" / "v4_timetable_source_registry.json"
DEFAULT_TRANSFER_REVIEW = ROOT / "data" / "v4_transfer_equivalence_review.json"
DEFAULT_DROPPED_DIRECT = ROOT / "data" / "v4_dropped_direct_service_audit.json"
DEFAULT_TRANSFER_CANDIDATES = ROOT / "data" / "v4_transfer_equivalence_candidate_audit.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_data_quality_audit.json"

REQUIRED_DIRECT_TRANSFER_NAME_SETS: set[frozenset[str]] = set()
REVIEWED_NOT_DIRECT_TRANSFER_NAME_SETS: set[frozenset[str]] = set()

EXPECTED_STATION_SERVICE_COUNTS = [
    {"station": "東京", "service": "ひたち", "minimum": 30},
    {"station": "東京", "service": "ときわ", "minimum": 35},
    {"station": "東京", "service": "成田エクスプレス", "minimum": 35},
    {"station": "東京", "service": "あずさ", "minimum": 5},
    {"station": "東京", "service": "かいじ", "minimum": 8},
    {"station": "東京", "service": "わかしお", "minimum": 10},
    {"station": "東京", "service": "さざなみ", "minimum": 4},
    {"station": "上野", "service": "ひたち", "minimum": 30},
    {"station": "上野", "service": "ときわ", "minimum": 35},
    {"station": "八王子", "service": "あずさ", "minimum": 45},
    {"station": "八王子", "service": "かいじ", "minimum": 20},
    {"station": "八王子", "service": "富士回遊", "minimum": 10},
    {"station": "八王子", "service": "むさしの号", "minimum": 2},
    {"station": "蒲田", "service": "京急", "minimum": 1, "transferEquivalent": True},
    {"station": "名古屋", "service": "近鉄", "minimum": 1, "transferEquivalent": True},
    {"station": "名古屋", "service": "名鉄", "minimum": 1, "transferEquivalent": True},
]

TRANSFER_PREFIX_RE = re.compile(
    r"^(?:JR|ＪＲ|東京メトロ|都営|東京モノレール|モノレール|京急|京成|京王|小田急|東急|東武|西武|相鉄|近鉄|名鉄|阪急|阪神|京阪|南海|西鉄|京福|叡山|りんかい|ゆりかもめ)"
)
RAW_NUMBERED_LINE_RE = re.compile(r"^\d+\s*号線$")
TRAIN_NUMBER_RE = re.compile(r"\d{1,4}\s*(?:号|列車)?")
LIMITED_OR_LINER_RE = re.compile(r"(?:特急|ライナー|新幹線)")


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def maybe_load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return load_json(path)


def load_transfer_review(path: Path) -> tuple[set[frozenset[str]], set[frozenset[str]]]:
    if not path.exists():
        return set(), set()
    payload = load_json(path)
    return (
        {frozenset(item) for item in payload.get("reviewedDirectNameSets", [])},
        {frozenset(item) for item in payload.get("reviewedNotDirectNameSets", [])},
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def station_group_name(group: dict[str, Any]) -> str:
    return str((group.get("names") or {}).get("ja") or group.get("primaryName") or group.get("nameJa") or group.get("id") or "")


def normalized_transfer_name(name: str) -> str:
    normalized = re.sub(r"\s+", "", str(name or ""))
    normalized = TRANSFER_PREFIX_RE.sub("", normalized)
    return re.sub(r"駅$", "", normalized)


def coordinate_distance_meters(left: tuple[float, float] | None, right: tuple[float, float] | None) -> float:
    if not left or not right:
        return math.inf
    lon1, lat1 = map(math.radians, left)
    lon2, lat2 = map(math.radians, right)
    d_lon = lon2 - lon1
    d_lat = lat2 - lat1
    a = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def group_coordinate(group: dict[str, Any]) -> tuple[float, float] | None:
    centroid = group.get("centroid") or {}
    lon = centroid.get("lon")
    lat = centroid.get("lat")
    if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
        return float(lon), float(lat)
    return None


def decode_compact_timetable(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("format") != "v3-timetable-compact-v1":
        return payload.get("tripInstances", [])
    station_group_ids = payload.get("stationGroupIds", [])
    route_ids = payload.get("routeIds", [])
    service_names = payload.get("serviceNames", [])
    display_names = payload.get("displayNames", [])
    headsigns = payload.get("headsigns", [])
    trips: list[dict[str, Any]] = []
    for row in payload.get("trips", []):
        display_name_index = row[6] if len(row) > 6 else 0
        headsign_index = row[7] if len(row) > 7 else 0
        trips.append(
            {
                "id": row[0],
                "routeId": route_ids[row[1]] if row[1] < len(route_ids) else "",
                "serviceName": service_names[row[2]] if row[2] < len(service_names) else "",
                "serviceNumber": row[3] or "",
                "displayName": display_names[display_name_index] if display_name_index < len(display_names) else "",
                "headsign": headsigns[headsign_index] if headsign_index < len(headsigns) else "",
                "lineTrace": [
                    {
                        "fromSequence": trace[0],
                        "toSequence": trace[1],
                        "routeId": route_ids[trace[2]] if trace[2] < len(route_ids) else "",
                    }
                    for trace in (row[5] if len(row) > 5 else []) or []
                ],
                "stopTimes": [
                    {
                        "sequence": index + 1,
                        "stationGroupId": station_group_ids[stop[0]] if stop[0] < len(station_group_ids) else "",
                        "arrivalTimeSec": stop[1],
                        "departureTimeSec": stop[2],
                        "boardRouteId": route_ids[stop[3]] if len(stop) > 3 and stop[3] is not None and stop[3] < len(route_ids) else "",
                        "alightRouteId": route_ids[stop[5]] if len(stop) > 5 and stop[5] is not None and stop[5] < len(route_ids) else "",
                    }
                    for index, stop in enumerate(row[4] or [])
                ],
            }
        )
    return trips


def route_title(route: dict[str, Any], route_id: str = "") -> str:
    for key in ("shortName", "longName", "id"):
        value = route.get(key)
        if value:
            return str(value)
    return route_id or "路線"


def current_train_line_key(train: dict[str, Any]) -> tuple[str, str]:
    return (
        str(train.get("operator_name") or train.get("operator_id") or ""),
        str(train.get("line_name") or train.get("service_name") or ""),
    )


def audit_collection_coverage(
    registry: dict[str, Any] | None,
    current_payload: dict[str, Any],
    routes: dict[str, dict[str, Any]],
    trips: list[dict[str, Any]],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    current_counts_by_line: Counter[tuple[str, str]] = Counter(current_train_line_key(train) for train in current_payload.get("train_instances", []))
    trip_counts_by_route: Counter[str] = Counter(trip.get("routeId") or "" for trip in trips)

    no_trip_routes = []
    for route_id, route in routes.items():
        if route.get("tags", {}).get("source") == "v4_virtual_corridor":
            continue
        if trip_counts_by_route.get(route_id, 0):
            continue
        no_trip_routes.append(
            {
                "routeId": route_id,
                "title": route_title(route, route_id),
                "operatorName": route.get("operatorName") or route.get("operatorId") or "",
                "mode": route.get("mode") or "",
            }
        )
    warnings.extend({"kind": "route_has_no_gameplay_trips", **item} for item in no_trip_routes[:120])

    registry_zero_known = []
    if registry:
        for operator in registry.get("operators", []):
            known_count = int(operator.get("knownTrainInstanceCount") or 0)
            source_status = str(operator.get("sourceStatus") or "")
            high_conf_leads = [
                lead
                for lead in operator.get("sourceLeads", [])
                if lead.get("candidateStatus") == "high_confidence"
            ]
            if known_count == 0 and high_conf_leads:
                registry_zero_known.append(
                    {
                        "operatorId": operator.get("operatorId"),
                        "operatorName": operator.get("operatorName"),
                        "lineNames": operator.get("lineNames", [])[:12],
                        "sourceStatus": source_status,
                        "leadCount": len(operator.get("sourceLeads", [])),
                        "sampleLead": {
                            "title": high_conf_leads[0].get("title"),
                            "url": high_conf_leads[0].get("url"),
                            "score": high_conf_leads[0].get("score"),
                        },
                    }
                )
        warnings.extend({"kind": "registry_high_confidence_source_but_no_known_trains", **item} for item in registry_zero_known[:120])

    suspicious_low_current_lines = [
        {
            "operatorName": operator,
            "lineName": line,
            "currentTrainCount": count,
        }
        for (operator, line), count in current_counts_by_line.items()
        if line and 0 < count <= 2 and not any(token in line for token in ("鋼索", "ケーブル", "ロープウェイ"))
    ]
    suspicious_low_current_lines.sort(key=lambda item: (item["currentTrainCount"], item["operatorName"], item["lineName"]))
    warnings.extend({"kind": "line_has_very_few_current_trains", **item} for item in suspicious_low_current_lines[:80])

    return {
        "summary": {
            "currentLineCount": len(current_counts_by_line),
            "gameplayRouteCount": len(routes),
            "gameplayTripRouteCount": len(trip_counts_by_route),
            "routeWithoutGameplayTripCount": len(no_trip_routes),
            "registryHighConfidenceNoKnownTrainCount": len(registry_zero_known),
            "veryLowCurrentLineCount": len(suspicious_low_current_lines),
            "issueCount": len(issues),
            "warningCount": len(warnings),
        },
        "issues": issues,
        "warnings": warnings,
    }


def public_train_label(trip: dict[str, Any]) -> str:
    for key in ("displayName", "serviceName", "serviceNumber"):
        value = str(trip.get(key) or "").strip()
        if value:
            return value
    return ""


def audit_train_display(routes: dict[str, dict[str, Any]], trips: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    for trip in trips:
        route = routes.get(trip.get("routeId") or "", {})
        title = route_title(route, trip.get("routeId") or "")
        label = public_train_label(trip)
        service_name = str(trip.get("serviceName") or "")
        combined = " ".join(str(trip.get(key) or "") for key in ("displayName", "serviceName", "serviceNumber"))
        sample = {
            "tripId": trip.get("id"),
            "route": title,
            "operatorName": route.get("operatorName") or route.get("operatorId") or "",
            "serviceName": service_name,
            "serviceNumber": trip.get("serviceNumber") or "",
            "displayName": trip.get("displayName") or "",
            "headsign": trip.get("headsign") or "",
        }
        if not label:
            counts["empty_train_label"] += 1
            if counts["empty_train_label"] <= 80:
                issues.append({"kind": "empty_train_label", **sample})
        if RAW_NUMBERED_LINE_RE.match(label):
            counts["raw_numbered_line_label"] += 1
            if counts["raw_numbered_line_label"] <= 80:
                issues.append({"kind": "raw_numbered_line_label", **sample})
        if (LIMITED_OR_LINER_RE.search(combined) or route.get("mode") == "shinkansen") and not TRAIN_NUMBER_RE.search(combined):
            counts["limited_or_shinkansen_missing_number"] += 1
            if counts["limited_or_shinkansen_missing_number"] <= 80:
                issues.append({"kind": "limited_or_shinkansen_missing_number", **sample})
        if "名鉄" in str(route.get("operatorName") or route.get("operatorId") or ""):
            # Raw compact data should preserve enough information for the front-end
            # to render the reviewed 名鉄（○○線） label.
            if "名鉄" not in combined and "名鉄" not in title:
                counts["meitetsu_label_missing_operator_context"] += 1
                if counts["meitetsu_label_missing_operator_context"] <= 80:
                    warnings.append({"kind": "meitetsu_label_missing_operator_context", **sample})

    hard_issue_count = (
        counts["empty_train_label"]
        + counts["raw_numbered_line_label"]
        + counts["limited_or_shinkansen_missing_number"]
    )
    return {
        "summary": {
            "checkedTripCount": len(trips),
            "issueCount": hard_issue_count,
            "issueSampleCount": len(issues),
            "warningCount": len(warnings),
            "countsByKind": dict(sorted(counts.items())),
        },
        "issues": issues,
        "warnings": warnings,
    }


def audit_trip_integrity(station_groups: dict[str, dict[str, Any]], routes: dict[str, dict[str, Any]], trips: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    seen_trip_ids: set[str] = set()

    for trip in trips:
        trip_id = str(trip.get("id") or "")
        stops = trip.get("stopTimes") or []
        sample = {
            "tripId": trip_id,
            "route": route_title(routes.get(trip.get("routeId") or "", {}), trip.get("routeId") or ""),
            "serviceName": trip.get("serviceName") or "",
            "displayName": trip.get("displayName") or "",
        }
        if trip_id in seen_trip_ids:
            counts["duplicate_trip_id"] += 1
            if counts["duplicate_trip_id"] <= 80:
                issues.append({"kind": "duplicate_trip_id", **sample})
        seen_trip_ids.add(trip_id)
        if len(stops) < 2:
            counts["trip_has_fewer_than_two_stops"] += 1
            if counts["trip_has_fewer_than_two_stops"] <= 80:
                issues.append({"kind": "trip_has_fewer_than_two_stops", "stopCount": len(stops), **sample})
        missing_stops = [
            stop.get("stationGroupId")
            for stop in stops
            if stop.get("stationGroupId") not in station_groups
        ]
        if missing_stops:
            counts["trip_references_missing_station_group"] += 1
            if counts["trip_references_missing_station_group"] <= 80:
                issues.append({"kind": "trip_references_missing_station_group", "missingStationGroupIds": missing_stops[:10], **sample})
        missing_route_refs = [
            route_id
            for route_id in {trip.get("routeId"), *(trace.get("routeId") for trace in trip.get("lineTrace") or [])}
            if route_id and route_id not in routes
        ]
        if missing_route_refs:
            counts["trip_references_missing_route"] += 1
            if counts["trip_references_missing_route"] <= 80:
                issues.append({"kind": "trip_references_missing_route", "missingRouteIds": sorted(missing_route_refs), **sample})

    return {
        "summary": {
            "checkedTripCount": len(trips),
            "issueCount": len(issues),
            "warningCount": len(warnings),
            "countsByKind": dict(sorted(counts.items())),
        },
        "issues": issues,
        "warnings": warnings,
    }


def trip_service_text(trip: dict[str, Any], route: dict[str, Any]) -> str:
    return " ".join(
        str(value or "")
        for value in (
            trip.get("displayName"),
            trip.get("serviceName"),
            trip.get("serviceNumber"),
            trip.get("headsign"),
            route.get("shortName"),
            route.get("longName"),
            route.get("operatorName"),
        )
    )


def transfer_equivalent_group_ids(map_bundle: dict[str, Any]) -> dict[str, set[str]]:
    groups = map_bundle.get("stationGroups", [])
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    equivalents: dict[str, set[str]] = {group["id"]: {group["id"]} for group in groups}
    for group in groups:
        by_key[normalized_transfer_name(station_group_name(group))].append(group)
    for same_name_groups in by_key.values():
        for left_index, left in enumerate(same_name_groups):
            for right in same_name_groups[left_index + 1 :]:
                left_name = station_group_name(left)
                right_name = station_group_name(right)
                reviewed_direct = frozenset((left_name, right_name)) in REQUIRED_DIRECT_TRANSFER_NAME_SETS
                reviewed_not_direct = frozenset((left_name, right_name)) in REVIEWED_NOT_DIRECT_TRANSFER_NAME_SETS
                distance = coordinate_distance_meters(group_coordinate(left), group_coordinate(right))
                if reviewed_direct or (distance <= 700 and not reviewed_not_direct):
                    equivalents[left["id"]].add(right["id"])
                    equivalents[right["id"]].add(left["id"])
    return equivalents


def audit_known_station_coverage(map_bundle: dict[str, Any], routes: dict[str, dict[str, Any]], trips: list[dict[str, Any]]) -> dict[str, Any]:
    station_groups = {group["id"]: group for group in map_bundle.get("stationGroups", [])}
    group_ids_by_name: dict[str, list[str]] = defaultdict(list)
    for group_id, group in station_groups.items():
        group_ids_by_name[station_group_name(group)].append(group_id)
    equivalents = transfer_equivalent_group_ids(map_bundle)
    trips_by_station_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trip in trips:
        seen = set()
        for stop in trip.get("stopTimes") or []:
            station_group_id = stop.get("stationGroupId")
            if station_group_id and station_group_id not in seen:
                trips_by_station_group[station_group_id].append(trip)
                seen.add(station_group_id)

    issues = []
    rows = []
    for expected in EXPECTED_STATION_SERVICE_COUNTS:
        station_name = expected["station"]
        base_group_ids = set(group_ids_by_name.get(station_name, []))
        search_group_ids = set(base_group_ids)
        if expected.get("transferEquivalent"):
            for group_id in list(base_group_ids):
                search_group_ids.update(equivalents.get(group_id, {group_id}))
        matching_trip_ids: set[str] = set()
        sample_trips = []
        for group_id in search_group_ids:
            for trip in trips_by_station_group.get(group_id, []):
                route = routes.get(trip.get("routeId") or "", {})
                if expected["service"] not in trip_service_text(trip, route):
                    continue
                trip_id = str(trip.get("id") or "")
                if trip_id in matching_trip_ids:
                    continue
                matching_trip_ids.add(trip_id)
                if len(sample_trips) < 8:
                    sample_trips.append(
                        {
                            "tripId": trip_id,
                            "route": route_title(route, trip.get("routeId") or ""),
                            "serviceName": trip.get("serviceName") or "",
                            "displayName": trip.get("displayName") or "",
                            "serviceNumber": trip.get("serviceNumber") or "",
                            "headsign": trip.get("headsign") or "",
                        }
                    )
        row = {
            "station": station_name,
            "service": expected["service"],
            "minimum": expected["minimum"],
            "actual": len(matching_trip_ids),
            "transferEquivalent": bool(expected.get("transferEquivalent")),
            "stationGroupIds": sorted(base_group_ids),
            "searchedStationGroupIds": sorted(search_group_ids),
            "samples": sample_trips,
        }
        rows.append(row)
        if row["actual"] < row["minimum"]:
            issues.append({"kind": "known_station_service_underfilled", **row})

    return {
        "summary": {
            "checkedExpectationCount": len(EXPECTED_STATION_SERVICE_COUNTS),
            "issueCount": len(issues),
            "warningCount": 0,
        },
        "issues": issues,
        "warnings": [],
        "checks": rows,
    }


def audit_transfers(map_bundle: dict[str, Any], transfer_candidate_audit: dict[str, Any] | None) -> dict[str, Any]:
    groups = map_bundle.get("stationGroups", [])
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        by_name[station_group_name(group)].append(group)

    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for name_set in sorted(REQUIRED_DIRECT_TRANSFER_NAME_SETS, key=lambda value: sorted(value)):
        left_name, right_name = sorted(name_set)
        left_groups = by_name.get(left_name, [])
        right_groups = by_name.get(right_name, [])
        if not left_groups or not right_groups:
            issues.append({"kind": "required_transfer_station_missing", "names": [left_name, right_name]})
            continue
        best: tuple[float, dict[str, Any], dict[str, Any]] | None = None
        for left in left_groups:
            for right in right_groups:
                distance = coordinate_distance_meters(group_coordinate(left), group_coordinate(right))
                if best is None or distance < best[0]:
                    best = (distance, left, right)
        distance, left, right = best or (math.inf, {}, {})
        if normalized_transfer_name(left_name) != normalized_transfer_name(right_name):
            issues.append({"kind": "required_transfer_names_do_not_normalize_together", "names": [left_name, right_name]})
        if distance > 1600:
            warnings.append(
                {
                    "kind": "required_transfer_pair_far_apart",
                    "names": [left_name, right_name],
                    "distanceM": round(distance, 1),
                    "leftStationGroupId": left.get("id"),
                    "rightStationGroupId": right.get("id"),
                }
            )

    if transfer_candidate_audit:
        for candidate in transfer_candidate_audit.get("candidates", []):
            if candidate.get("decision") == "active_unreviewed_direct":
                warnings.append({"kind": "active_unreviewed_transfer_equivalence", **candidate})

    return {
        "summary": {
            "requiredPairCount": len(REQUIRED_DIRECT_TRANSFER_NAME_SETS),
            "issueCount": len(issues),
            "warningCount": len(warnings),
        },
        "issues": issues,
        "warnings": warnings[:160],
    }


def audit_dropped_direct_services(dropped_direct_audit: dict[str, Any] | None) -> dict[str, Any]:
    if not dropped_direct_audit:
        return {"summary": {"available": False, "issueCount": 0, "warningCount": 0}, "issues": [], "warnings": []}
    warnings = []
    for group in dropped_direct_audit.get("suspiciousGroups", []):
        missing_count = int(group.get("missingFromCurrentServiceKeyCount") or 0)
        if missing_count <= 0:
            continue
        warnings.append(
            {
                "kind": "dropped_named_or_limited_service_missing_from_current",
                "source": group.get("source"),
                "operatorName": group.get("operatorName"),
                "lineName": group.get("lineName"),
                "baseName": group.get("baseName"),
                "missingFromCurrentServiceKeyCount": missing_count,
                "missingFromCurrentServiceKeys": group.get("missingFromCurrentServiceKeys", [])[:20],
                "excessiveStopNames": group.get("excessiveStopNames", {}),
                "samples": group.get("samples", [])[:3],
            }
        )
    return {
        "summary": {
            "available": True,
            "sourceSuspiciousGroupCount": dropped_direct_audit.get("counts", {}).get("suspiciousGroupCount", 0),
            "missingCurrentSuspiciousGroupCount": len(warnings),
            "issueCount": 0,
            "warningCount": len(warnings),
        },
        "issues": [],
        "warnings": warnings[:160],
    }


def merge_browser_audit(browser_audit: dict[str, Any] | None) -> dict[str, Any]:
    if not browser_audit:
        return {"summary": {"available": False, "issueCount": 0, "warningCount": 0}, "issues": [], "warnings": []}
    issues = []
    if int(browser_audit.get("anomalyCount") or 0):
        issues.extend({"kind": "browser_route_choice_anomaly", **item} for item in browser_audit.get("anomalies", []))
    return {
        "summary": {
            "available": True,
            "stationCount": browser_audit.get("stationCount"),
            "tripCount": browser_audit.get("tripCount"),
            "anomalyCount": browser_audit.get("anomalyCount", 0),
            "issueCount": len(issues),
            "warningCount": 0,
        },
        "issues": issues,
        "warnings": [],
        "globalChoiceScan": browser_audit.get("globalChoiceScan", {}),
        "globalTrainLabelScan": browser_audit.get("globalTrainLabelScan", {}),
        "knownStationChoices": browser_audit.get("knownStationChoices", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-bundle", type=Path, default=DEFAULT_MAP_BUNDLE)
    parser.add_argument("--timetable", type=Path, default=DEFAULT_TIMETABLE)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--source-registry", type=Path, default=DEFAULT_SOURCE_REGISTRY)
    parser.add_argument("--transfer-review", type=Path, default=DEFAULT_TRANSFER_REVIEW)
    parser.add_argument("--dropped-direct-audit", type=Path, default=DEFAULT_DROPPED_DIRECT)
    parser.add_argument("--transfer-candidate-audit", type=Path, default=DEFAULT_TRANSFER_CANDIDATES)
    parser.add_argument("--browser-audit-json", type=Path, help="Optional JSON output from scripts/tests/v4_route_choice_audit.js.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args()
    global REQUIRED_DIRECT_TRANSFER_NAME_SETS, REVIEWED_NOT_DIRECT_TRANSFER_NAME_SETS
    REQUIRED_DIRECT_TRANSFER_NAME_SETS, REVIEWED_NOT_DIRECT_TRANSFER_NAME_SETS = load_transfer_review(args.transfer_review)

    map_bundle = load_json(args.map_bundle)
    timetable_payload = load_json(args.timetable)
    current_payload = load_json(args.current)
    source_registry = maybe_load_json(args.source_registry)
    dropped_direct = maybe_load_json(args.dropped_direct_audit)
    transfer_candidates = maybe_load_json(args.transfer_candidate_audit)
    browser_audit = maybe_load_json(args.browser_audit_json) if args.browser_audit_json else None

    station_groups = {group["id"]: group for group in map_bundle.get("stationGroups", [])}
    routes = {route["id"]: route for route in map_bundle.get("serviceRoutes", [])}
    trips = decode_compact_timetable(timetable_payload)

    sections = {
        "collectionCoverage": audit_collection_coverage(source_registry, current_payload, routes, trips),
        "tripIntegrity": audit_trip_integrity(station_groups, routes, trips),
        "trainDisplay": audit_train_display(routes, trips),
        "knownStationCoverage": audit_known_station_coverage(map_bundle, routes, trips),
        "transferEquivalence": audit_transfers(map_bundle, transfer_candidates),
        "droppedDirectServices": audit_dropped_direct_services(dropped_direct),
        "browserRouteChoices": merge_browser_audit(browser_audit),
    }
    error_count = sum(int(section.get("summary", {}).get("issueCount") or 0) for section in sections.values())
    warning_count = sum(int(section.get("summary", {}).get("warningCount") or 0) for section in sections.values())
    payload = {
        "schema": "onichase.v4.data_quality_audit.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "inputs": {
            "mapBundle": rel(args.map_bundle),
            "timetable": rel(args.timetable),
            "current": rel(args.current),
            "sourceRegistry": rel(args.source_registry),
            "transferReview": rel(args.transfer_review),
            "droppedDirectAudit": rel(args.dropped_direct_audit),
            "transferCandidateAudit": rel(args.transfer_candidate_audit),
            "browserAuditJson": rel(args.browser_audit_json) if args.browser_audit_json else None,
        },
        "summary": {
            "errorCount": error_count,
            "warningCount": warning_count,
            "sections": {
                name: {
                    "issueCount": section.get("summary", {}).get("issueCount", 0),
                    "warningCount": section.get("summary", {}).get("warningCount", 0),
                }
                for name, section in sections.items()
            },
        },
        **sections,
    }
    write_json(args.output, payload)
    print(f"Wrote {args.output}: errors={error_count} warnings={warning_count}")
    return 1 if args.fail_on_error and error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
