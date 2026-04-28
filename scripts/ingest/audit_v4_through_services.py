#!/usr/bin/env python3
"""Audit v4 through-service representation and browser stitch coverage.

The audit is intentionally data-driven:

- trips whose own lineTrace route ids change are route-transition observations
  inside one timetable trip, useful for reviewing already-unified direct trains
  and suspicious segment identity;
- split-trip candidates are terminal/origin pairs at the same station group
  within a short time gap with compatible public train numbers;
- browser-stitchable candidates are the stricter subset that matches the
  current v4 browser stitch heuristic.

This is not an official railway encyclopedia.  It is a reusable guardrail that
keeps direct-train handling visible across all loaded v4 timetable sources.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_BUNDLE = ROOT / "data" / "v4_gameplay_map_bundle.json.gz"
DEFAULT_TIMETABLE = ROOT / "data" / "v4_gameplay_timetable_bundle.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_through_service_audit.json"
SAMPLE_LIMIT = 80
DEFAULT_MAX_GAP_SEC = 300


JR_YOKOSUKA_SOBU_RAPID_CORRIDOR_LABEL = "横須賀線・総武快速線"
YOKOSUKA_SOBU_RAPID_SIGNATURE_STATIONS = {
    "久里浜", "衣笠", "横須賀", "田浦", "東逗子", "逗子", "鎌倉", "北鎌倉",
    "大船", "戸塚", "東戸塚", "保土ヶ谷", "横浜", "新川崎", "武蔵小杉",
    "西大井", "品川", "新橋", "東京", "新日本橋", "馬喰町", "錦糸町",
    "新小岩", "市川", "船橋", "津田沼", "稲毛", "千葉",
}
SOBU_RAPID_UNDERGROUND_BRANCH_STATIONS = {"東京", "新日本橋", "馬喰町"}
CONFIRMED_SPLIT_THROUGH_RULES = [
    {"station": "東室蘭", "routes": ("函館線", "室蘭線"), "classification": "confirmed_direct"},
    {"station": "札幌", "routes": ("千歳線", "函館線"), "classification": "confirmed_direct"},
    {"station": "旭川", "routes": ("函館線", "宗谷線"), "classification": "confirmed_direct"},
    {"station": "旭川", "routes": ("石北線", "函館線"), "classification": "confirmed_direct"},
    {"station": "会津高原尾瀬口", "routes": ("会津鬼怒川線", "会津線"), "classification": "confirmed_direct"},
    {"station": "太秦天神川", "routes": ("京津線", "東西線"), "classification": "confirmed_direct"},
]
LIKELY_FALSE_POSITIVE_SPLIT_RULES = [
    {"station": "渋谷", "routes": ("東横線", "田園都市線"), "classification": "likely_reused_number_or_data_context"},
    {"station": "柏", "routes": ("東上本線", "野田線"), "classification": "likely_reused_number_or_data_context"},
    {"station": "柏", "routes": ("伊勢崎線", "野田線"), "classification": "likely_reused_number_or_data_context"},
    {"station": "浅草", "routes": ("野田線", "伊勢崎線"), "classification": "likely_reused_number_or_data_context"},
    {"station": "新宿", "routes": ("10号線新宿線", "東北線"), "classification": "likely_reused_number_or_data_context"},
    {"station": "新宿", "routes": ("川越線", "10号線新宿線"), "classification": "likely_reused_number_or_data_context"},
]


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def seconds_to_hhmm(value: int | None) -> str:
    if not isinstance(value, int):
        return ""
    minutes = value // 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def add_sample(samples: list[dict[str, Any]], sample: dict[str, Any]) -> None:
    if len(samples) < SAMPLE_LIMIT:
        samples.append(sample)


def station_title(group: dict[str, Any] | None, station_group_id: str = "") -> str:
    names = (group or {}).get("names") or {}
    return str(names.get("ja") or (group or {}).get("primaryName") or station_group_id)


def route_title(route: dict[str, Any] | None, route_id: str = "") -> str:
    if not route:
        return route_id
    tags = route.get("tags") or {}
    short_name = str(route.get("shortName") or "")
    if short_name == "JR_EAST_YOKOSUKA_SOBU_RAPID":
        return JR_YOKOSUKA_SOBU_RAPID_CORRIDOR_LABEL
    return str(tags.get("lineName") or short_name or route.get("longName") or route_id)


def route_key(routes: dict[str, dict[str, Any]], route_id: str) -> str:
    route = routes.get(route_id) or {}
    return f"{route.get('operatorId') or route.get('operatorName') or '?'}:{route_title(route, route_id)}"


def route_name_tokens(routes: dict[str, dict[str, Any]], route_id: str) -> set[str]:
    route = routes.get(route_id) or {}
    tags = route.get("tags") or {}
    return {
        str(value)
        for value in (route.get("shortName"), tags.get("lineName"), route_title(route, route_id))
        if value
    }


def route_matches_name(routes: dict[str, dict[str, Any]], route_id: str, name: str) -> bool:
    return name in route_name_tokens(routes, route_id)


def source_key(trip: dict[str, Any]) -> str:
    return str(trip.get("sourceFeedKey") or trip.get("sourceTripId") or trip.get("id") or "unknown").split(":")[0]


def stop_station_name(station_groups: dict[str, dict[str, Any]], stop: dict[str, Any] | None) -> str:
    station_group_id = str((stop or {}).get("stationGroupId") or "")
    return station_title(station_groups.get(station_group_id), station_group_id)


def stop_time_sec(stop: dict[str, Any] | None, preferred: str) -> int | None:
    if not stop:
        return None
    if preferred == "arrival":
        value = stop.get("arrivalTimeSec", stop.get("departureTimeSec"))
    else:
        value = stop.get("departureTimeSec", stop.get("arrivalTimeSec"))
    return value if isinstance(value, int) else None


def normalize_train_number(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().upper())


def public_train_number(trip: dict[str, Any]) -> str:
    return normalize_train_number(
        trip.get("publicServiceNumber")
        or trip.get("serviceNumber")
        or trip.get("operatingNumber")
        or ""
    )


def through_run_code(trip: dict[str, Any]) -> str:
    raw = public_train_number(trip)
    match = re.search(r"(\d{3,4})([A-Z]{1,2})[A-Z0]*$", raw)
    if not match:
        return ""
    return f"{int(match.group(1))}{match.group(2)[0]}"


def through_run_code_parts(trip: dict[str, Any]) -> dict[str, Any] | None:
    raw = public_train_number(trip)
    match = re.search(r"(\d{3,4})([A-Z]{1,2})[A-Z0]*$", raw)
    if not match:
        return None
    return {"number": int(match.group(1)), "suffix": match.group(2)[0]}


def route_operator(routes: dict[str, dict[str, Any]], trip: dict[str, Any]) -> str:
    route = routes.get(str(trip.get("routeId") or "")) or {}
    return str(route.get("operatorId") or "")


def trip_station_names(station_groups: dict[str, dict[str, Any]], trip: dict[str, Any]) -> list[str]:
    return [stop_station_name(station_groups, stop) for stop in trip.get("stopTimes") or []]


def trip_trace_route_names(routes: dict[str, dict[str, Any]], trip: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for trace in trip.get("lineTrace") or []:
        route_id = str(trace.get("routeId") or "")
        route = routes.get(route_id) or {}
        names.append(str(trace.get("lineName") or route.get("shortName") or (route.get("tags") or {}).get("lineName") or ""))
    return [name for name in names if name]


def terminal_trace_has_any(routes: dict[str, dict[str, Any]], trip: dict[str, Any], terminal: str, names: set[str]) -> bool:
    traces = trip.get("lineTrace") or []
    if not traces:
        return False
    trace = traces[0] if terminal == "first" else traces[-1]
    route_id = str(trace.get("routeId") or "")
    route = routes.get(route_id) or {}
    trace_names = {
        str(trace.get("lineName") or ""),
        str(route.get("shortName") or ""),
        str((route.get("tags") or {}).get("lineName") or ""),
    }
    return any(name in trace_names for name in names)


def is_yokosuka_sobu_rapid_trip(
    station_groups: dict[str, dict[str, Any]],
    routes: dict[str, dict[str, Any]],
    trip: dict[str, Any],
) -> bool:
    if route_operator(routes, trip) != "jr_east":
        return False
    route = routes.get(str(trip.get("routeId") or "")) or {}
    route_name = str(route.get("shortName") or "")
    trace_names = trip_trace_route_names(routes, trip)
    station_names = trip_station_names(station_groups, trip)
    has_yokosuka_trace = route_name == "横須賀線" or "横須賀線" in trace_names
    has_sobu_trace = route_name == "総武線" or "総武線" in trace_names
    uses_sobu_underground = any(name in SOBU_RAPID_UNDERGROUND_BRANCH_STATIONS for name in station_names)
    if not has_yokosuka_trace and not (has_sobu_trace and uses_sobu_underground):
        return False
    signature_count = sum(1 for name in station_names if name in YOKOSUKA_SOBU_RAPID_SIGNATURE_STATIONS)
    return signature_count >= (1 if uses_sobu_underground else 2)


def is_yokosuka_sobu_rapid_stitch_pair(
    station_groups: dict[str, dict[str, Any]],
    routes: dict[str, dict[str, Any]],
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    left_stop = (left.get("stopTimes") or [])[-1] if left.get("stopTimes") else None
    right_stop = (right.get("stopTimes") or [None])[0]
    if stop_station_name(station_groups, left_stop) != "東京" or stop_station_name(station_groups, right_stop) != "東京":
        return False
    corridor_names = {"横須賀線", "総武線"}
    return terminal_trace_has_any(routes, left, "last", corridor_names) and terminal_trace_has_any(routes, right, "first", corridor_names)


def browser_codes_can_continue(
    station_groups: dict[str, dict[str, Any]],
    routes: dict[str, dict[str, Any]],
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    left_code = through_run_code(left)
    if left_code and left_code == through_run_code(right):
        return True
    if not is_yokosuka_sobu_rapid_stitch_pair(station_groups, routes, left, right):
        return False
    left_parts = through_run_code_parts(left)
    right_parts = through_run_code_parts(right)
    if not left_parts or not right_parts:
        return False
    return right_parts["number"] == left_parts["number"] + 1 and (
        (left_parts["suffix"] == "S" and right_parts["suffix"] == "F")
        or (left_parts["suffix"] == "F" and right_parts["suffix"] == "S")
    )


def split_candidate_strength(
    station_groups: dict[str, dict[str, Any]],
    routes: dict[str, dict[str, Any]],
    left: dict[str, Any],
    right: dict[str, Any],
) -> str:
    if public_train_number(left) and public_train_number(left) == public_train_number(right):
        return "same_public_number"
    if browser_codes_can_continue(station_groups, routes, left, right):
        return "browser_code"
    left_code = through_run_code(left)
    if left_code and left_code == through_run_code(right):
        return "same_through_code"
    return ""


def is_browser_stitch_candidate(
    station_groups: dict[str, dict[str, Any]],
    routes: dict[str, dict[str, Any]],
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    left_operator = route_operator(routes, left)
    right_operator = route_operator(routes, right)
    if not left_operator or left_operator == "shinkansen" or not right_operator or right_operator == "shinkansen":
        return False
    if left_operator == right_operator:
        return (
            is_yokosuka_sobu_rapid_stitch_pair(station_groups, routes, left, right)
            and browser_codes_can_continue(station_groups, routes, left, right)
        ) or reviewed_split_rule(station_groups, routes, left, right, CONFIRMED_SPLIT_THROUGH_RULES) is not None
    if reviewed_split_rule(station_groups, routes, left, right, CONFIRMED_SPLIT_THROUGH_RULES) is not None:
        return public_train_number(left) == public_train_number(right) or browser_codes_can_continue(station_groups, routes, left, right)
    if not browser_codes_can_continue(station_groups, routes, left, right):
        return False
    left_route = routes.get(str(left.get("routeId") or "")) or {}
    right_route = routes.get(str(right.get("routeId") or "")) or {}
    names = {str(left_route.get("shortName") or ""), str(right_route.get("shortName") or "")}
    operators = {left_operator, right_operator}
    if names == {"RINKAI", "JR_EAST_SAIKYO_KAWAGOE"}:
        return True
    if "TOEI_ASAKUSA" in names or "1号線浅草線" in names:
        return "keikyu" in operators or "keisei" in operators
    return False


def reviewed_split_rule(
    station_groups: dict[str, dict[str, Any]],
    routes: dict[str, dict[str, Any]],
    left: dict[str, Any],
    right: dict[str, Any],
    rules: list[dict[str, Any]],
) -> dict[str, Any] | None:
    left_stops = left.get("stopTimes") or []
    right_stops = right.get("stopTimes") or []
    if not left_stops or not right_stops:
        return None
    station_name = stop_station_name(station_groups, left_stops[-1])
    left_route = str(left.get("routeId") or "")
    right_route = str(right.get("routeId") or "")
    for rule in rules:
        route_names = tuple(rule.get("routes") or ())
        if rule.get("station") != station_name or len(route_names) != 2:
            continue
        first, second = route_names
        direct = route_matches_name(routes, left_route, first) and route_matches_name(routes, right_route, second)
        reverse = route_matches_name(routes, left_route, second) and route_matches_name(routes, right_route, first)
        if direct or reverse:
            return rule
    return None


def route_transition_label(routes: dict[str, dict[str, Any]], left_route_id: str, right_route_id: str) -> str:
    return f"{route_key(routes, left_route_id)} -> {route_key(routes, right_route_id)}"


def audit_internal_through_trips(
    station_groups: dict[str, dict[str, Any]],
    routes: dict[str, dict[str, Any]],
    trips: list[dict[str, Any]],
) -> tuple[Counter[str], Counter[str], list[dict[str, Any]], int, Counter[str], list[dict[str, Any]]]:
    route_pair_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    through_trip_ids: set[str] = set()
    stop_display_pair_counts: Counter[str] = Counter()
    stop_display_samples: list[dict[str, Any]] = []

    for trip in trips:
        stops = trip.get("stopTimes") or []
        for index in range(1, len(stops) - 1):
            stop = stops[index]
            incoming = str(stop.get("incomingRouteId") or "")
            outgoing = str(stop.get("outgoingRouteId") or "")
            if not incoming or not outgoing or incoming == outgoing:
                continue
            pair = route_transition_label(routes, incoming, outgoing)
            stop_display_pair_counts[pair] += 1
            add_sample(
                stop_display_samples,
                {
                    "kind": "stop_display_route_change",
                    "tripId": trip.get("id"),
                    "sourceFeedKey": trip.get("sourceFeedKey"),
                    "serviceNumber": public_train_number(trip),
                    "station": stop_station_name(station_groups, stop),
                    "time": seconds_to_hhmm(stop_time_sec(stop, "departure")),
                    "fromRoute": route_title(routes.get(incoming), incoming),
                    "toRoute": route_title(routes.get(outgoing), outgoing),
                },
            )

        traces = sorted(trip.get("lineTrace") or [], key=lambda item: int(item.get("fromSequence") or 0))
        for left, right in zip(traces, traces[1:]):
            left_route = str(left.get("routeId") or "")
            right_route = str(right.get("routeId") or "")
            if not left_route or not right_route or left_route == right_route:
                continue
            pair = route_transition_label(routes, left_route, right_route)
            route_pair_counts[pair] += 1
            source_counts[source_key(trip)] += 1
            through_trip_ids.add(str(trip.get("id") or ""))
            boundary_sequence = int(right.get("fromSequence") or left.get("toSequence") or 0)
            boundary_stop = next((stop for stop in stops if int(stop.get("sequence") or 0) == boundary_sequence), None)
            add_sample(
                samples,
                {
                    "kind": "line_trace_route_change",
                    "tripId": trip.get("id"),
                    "sourceFeedKey": trip.get("sourceFeedKey"),
                    "serviceNumber": public_train_number(trip),
                    "station": stop_station_name(station_groups, boundary_stop),
                    "time": seconds_to_hhmm(stop_time_sec(boundary_stop, "departure")),
                    "fromRoute": route_title(routes.get(left_route), left_route),
                    "toRoute": route_title(routes.get(right_route), right_route),
                },
            )

    return route_pair_counts, source_counts, samples, len(through_trip_ids), stop_display_pair_counts, stop_display_samples


def audit_split_candidates(
    station_groups: dict[str, dict[str, Any]],
    routes: dict[str, dict[str, Any]],
    trips: list[dict[str, Any]],
    max_gap_sec: int,
) -> dict[str, Any]:
    starts_by_station: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trip in trips:
        stops = trip.get("stopTimes") or []
        if len(stops) < 2:
            continue
        first = stops[0]
        if first.get("stationGroupId"):
            starts_by_station[str(first["stationGroupId"])].append(trip)

    for station_trips in starts_by_station.values():
        station_trips.sort(key=lambda trip: stop_time_sec((trip.get("stopTimes") or [{}])[0], "departure") or -1)

    candidate_count = 0
    browser_candidate_count = 0
    uncovered_candidate_count = 0
    route_pair_counts: Counter[str] = Counter()
    browser_pair_counts: Counter[str] = Counter()
    uncovered_pair_counts: Counter[str] = Counter()
    station_counts: Counter[str] = Counter()
    strength_counts: Counter[str] = Counter()
    classification_counts: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    uncovered_samples: list[dict[str, Any]] = []

    for left in trips:
        left_stops = left.get("stopTimes") or []
        if len(left_stops) < 2:
            continue
        last = left_stops[-1]
        station_group_id = str(last.get("stationGroupId") or "")
        if not station_group_id:
            continue
        left_arrival = stop_time_sec(last, "arrival")
        if left_arrival is None:
            continue
        left_route = str(left.get("routeId") or "")
        for right in starts_by_station.get(station_group_id, []):
            if left.get("id") == right.get("id"):
                continue
            right_stops = right.get("stopTimes") or []
            first = right_stops[0] if right_stops else None
            right_departure = stop_time_sec(first, "departure")
            if right_departure is None:
                continue
            gap = right_departure - left_arrival
            if gap < 0:
                continue
            if gap > max_gap_sec:
                break
            right_route = str(right.get("routeId") or "")
            if not left_route or not right_route or left_route == right_route:
                continue
            strength = split_candidate_strength(station_groups, routes, left, right)
            if not strength:
                continue
            candidate_count += 1
            route_pair = route_transition_label(routes, left_route, right_route)
            station_name = station_title(station_groups.get(station_group_id), station_group_id)
            route_pair_counts[route_pair] += 1
            station_counts[station_name] += 1
            strength_counts[strength] += 1
            confirmed_rule = reviewed_split_rule(station_groups, routes, left, right, CONFIRMED_SPLIT_THROUGH_RULES)
            false_positive_rule = reviewed_split_rule(station_groups, routes, left, right, LIKELY_FALSE_POSITIVE_SPLIT_RULES)
            if confirmed_rule:
                classification = str(confirmed_rule.get("classification") or "confirmed_direct")
            elif false_positive_rule:
                classification = str(false_positive_rule.get("classification") or "likely_false_positive")
            else:
                classification = "needs_review"
            classification_counts[classification] += 1
            browser_candidate = is_browser_stitch_candidate(station_groups, routes, left, right)
            if browser_candidate:
                browser_candidate_count += 1
                browser_pair_counts[route_pair] += 1
            else:
                uncovered_candidate_count += 1
                uncovered_pair_counts[route_pair] += 1

            sample = {
                "station": station_name,
                "gapSec": gap,
                "strength": strength,
                "classification": classification,
                "browserStitchable": browser_candidate,
                "left": {
                    "tripId": left.get("id"),
                    "sourceFeedKey": left.get("sourceFeedKey"),
                    "serviceNumber": public_train_number(left),
                    "route": route_title(routes.get(left_route), left_route),
                    "origin": stop_station_name(station_groups, left_stops[0]),
                    "terminal": station_name,
                    "arrival": seconds_to_hhmm(left_arrival),
                },
                "right": {
                    "tripId": right.get("id"),
                    "sourceFeedKey": right.get("sourceFeedKey"),
                    "serviceNumber": public_train_number(right),
                    "route": route_title(routes.get(right_route), right_route),
                    "origin": station_name,
                    "terminal": stop_station_name(station_groups, right_stops[-1]),
                    "departure": seconds_to_hhmm(right_departure),
                },
            }
            add_sample(samples, sample)
            if not browser_candidate:
                add_sample(uncovered_samples, sample)

    return {
        "counts": {
            "splitCandidateCount": candidate_count,
            "browserStitchableCandidateCount": browser_candidate_count,
            "uncoveredSplitCandidateCount": uncovered_candidate_count,
        },
        "topRoutePairs": dict(route_pair_counts.most_common(100)),
        "topBrowserStitchableRoutePairs": dict(browser_pair_counts.most_common(100)),
        "topUncoveredRoutePairs": dict(uncovered_pair_counts.most_common(100)),
        "topBoundaryStations": dict(station_counts.most_common(100)),
        "byStrength": dict(sorted(strength_counts.items())),
        "byClassification": dict(sorted(classification_counts.items())),
        "samples": samples,
        "uncoveredSamples": uncovered_samples,
    }


def add_virtual_corridor_routes(routes: dict[str, dict[str, Any]]) -> None:
    routes.setdefault(
        "VIRTUAL_JR_EAST_YOKOSUKA_SOBU_RAPID",
        {
            "id": "VIRTUAL_JR_EAST_YOKOSUKA_SOBU_RAPID",
            "operatorId": "jr_east",
            "operatorName": "東日本旅客鉄道",
            "shortName": "JR_EAST_YOKOSUKA_SOBU_RAPID",
            "tags": {"lineName": "JR_EAST_YOKOSUKA_SOBU_RAPID"},
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-bundle", type=Path, default=DEFAULT_MAP_BUNDLE)
    parser.add_argument("--timetable", type=Path, default=DEFAULT_TIMETABLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-gap-sec", type=int, default=DEFAULT_MAX_GAP_SEC)
    args = parser.parse_args()

    map_bundle = load_json(args.map_bundle)
    timetable = load_json(args.timetable)
    station_groups = {str(group["id"]): group for group in map_bundle.get("stationGroups", [])}
    routes = {str(route["id"]): route for route in map_bundle.get("serviceRoutes", [])}
    add_virtual_corridor_routes(routes)
    trips = list(timetable.get("tripInstances") or [])
    if not trips:
        raise SystemExit(f"{rel(args.timetable)} does not contain tripInstances; use the full v4 timetable bundle")

    (
        internal_route_pairs,
        internal_sources,
        internal_samples,
        internal_trip_count,
        stop_display_pairs,
        stop_display_samples,
    ) = audit_internal_through_trips(
        station_groups, routes, trips
    )
    split = audit_split_candidates(station_groups, routes, trips, args.max_gap_sec)

    audit = {
        "schema": "onichase.v4.through_service_audit.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "inputs": {
            "mapBundle": rel(args.map_bundle),
            "timetable": rel(args.timetable),
            "maxGapSec": args.max_gap_sec,
        },
        "counts": {
            "tripCount": len(trips),
            "internalLineTraceTransitionTripCount": internal_trip_count,
            "internalLineTraceRouteTransitionCount": sum(internal_route_pairs.values()),
            **split["counts"],
        },
        "internalLineTraceTransitions": {
            "topRoutePairs": dict(internal_route_pairs.most_common(100)),
            "bySource": dict(sorted(internal_sources.items())),
            "samples": internal_samples,
            "note": "Review-oriented. A route transition inside one trip may be a real through/corridor movement, a branch movement, or a segment-identity issue depending on source quality.",
        },
        "stopDisplayRouteChanges": {
            "count": sum(stop_display_pairs.values()),
            "topRoutePairs": dict(stop_display_pairs.most_common(100)),
            "samples": stop_display_samples,
            "note": "Diagnostic only. Stop-level display route changes can include UI corridor classification at transfer-rich stations and are not treated as proof of one physical direct train.",
        },
        "splitTripCandidates": {
            key: value
            for key, value in split.items()
            if key != "counts"
        },
        "notes": [
            "internalLineTraceTransitionTripCount means the timetable has one trip with changing segment route ids; review top pairs before treating them as confirmed direct-service rules.",
            "splitCandidateCount means two different trips terminate/start at the same station within maxGapSec and have compatible train-number evidence.",
            "uncoveredSplitCandidateCount is intentionally review-oriented: it may include real direct services not yet covered by browser stitching, plus false positives from reused train numbers.",
        ],
    }
    write_json(args.output, audit)

    print(
        "v4 through-service audit: "
        f"{len(trips)} trips, "
        f"{internal_trip_count} internal lineTrace-transition trips, "
        f"{split['counts']['splitCandidateCount']} split candidates, "
        f"{split['counts']['browserStitchableCandidateCount']} browser-stitchable, "
        f"{split['counts']['uncoveredSplitCandidateCount']} uncovered candidates"
    )
    print(f"wrote {rel(args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
