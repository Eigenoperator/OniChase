#!/usr/bin/env python3
"""Audit named-train departure time distributions in the v4 gameplay timetable.

This is a review-oriented audit for a subtle data-collection failure mode:
the service is present, but only in one time band because one direction, source
slice, or day part was missed.  It intentionally reports candidates rather than
hard errors because some real trains are legitimately time-band services.
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
DEFAULT_OUTPUT = ROOT / "data" / "v4_named_train_time_distribution_audit.json"

DEFAULT_MIN_DEPARTURES = 5
DEFAULT_MAX_SPAN_MINUTES = 360
DEFAULT_MIN_TOUCH_TO_DEPARTURE_RATIO = 1.75
SAMPLE_LIMIT = 12

ROUTE_LIKE_RE = re.compile(r"(?:線|本線|ライン|Line|系統)$", re.I)
ROUTE_SERVICE_TYPE_RE = re.compile(r"(?:線|本線|鉄道).*(?:各停|普通|特急|急行|快速|準急)$")
LETTERED_RAPID_RE = re.compile(r"^[A-ZＡ-Ｚ]快速$")
SERVICE_NUMBER_RE = re.compile(r"\s*\d+\s*(?:号|M|A|B|D|F|K|S|H)?\b", re.I)
TRAIN_NUMBER_RE = re.compile(r"\d+\s*号")
ORDINARY_SERVICE_NAMES = {
    "普通", "各停", "各駅停車", "快速", "急行", "準急", "区間急行", "区間快速",
    "特急", "通勤急行", "通勤快速", "直通特急", "新快速", "快速急行",
    "全車特別車", "全車一般車",
}
ORDINARY_DESTINATION_LABEL_RE = re.compile(
    r"^(?:普通|各停|各駅停車|快速|急行|準急|快速急行|区間急行|区間快速|通勤急行|通勤快速|"
    r"特急(?:\(.+?\)|（.+?）)?|直通特急|全車特別車|全車一般車)\s*.+行き$"
)


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


def station_name(group: dict[str, Any], fallback: str = "") -> str:
    names = group.get("names") or {}
    return str(names.get("ja") or group.get("primaryName") or group.get("nameJa") or fallback)


def group_coordinate(group: dict[str, Any]) -> tuple[float, float] | None:
    centroid = group.get("centroid") or {}
    lat = centroid.get("lat")
    lon = centroid.get("lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)
    return None


def coordinate_distance_meters(left: tuple[float, float] | None, right: tuple[float, float] | None) -> float:
    if not left or not right:
        return float("inf")
    lat1, lon1 = left
    lat2, lon2 = right
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    hav = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))


def station_cluster_ids(station_groups: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Merge same-name station groups that the game treats as a direct transfer."""
    parent = {group_id: group_id for group_id in station_groups}

    def find(group_id: str) -> str:
        while parent[group_id] != group_id:
            parent[group_id] = parent[parent[group_id]]
            group_id = parent[group_id]
        return group_id

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        parent[max(left_root, right_root)] = min(left_root, right_root)

    by_name: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for group_id, group in station_groups.items():
        by_name[station_name(group, group_id)].append((group_id, group))
    for same_name_groups in by_name.values():
        for left_index, (left_id, left) in enumerate(same_name_groups):
            for right_id, right in same_name_groups[left_index + 1 :]:
                if coordinate_distance_meters(group_coordinate(left), group_coordinate(right)) <= 700:
                    union(left_id, right_id)
    return {group_id: find(group_id) for group_id in station_groups}


def route_title(route: dict[str, Any] | None, route_id: str = "") -> str:
    route = route or {}
    tags = route.get("tags") or {}
    return str(tags.get("lineName") or route.get("shortName") or route.get("longName") or route_id)


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
                "stopTimes": [
                    {
                        "sequence": index + 1,
                        "stationGroupId": station_group_ids[stop[0]] if stop[0] < len(station_group_ids) else "",
                        "arrivalTimeSec": stop[1],
                        "departureTimeSec": stop[2],
                    }
                    for index, stop in enumerate(row[4] or [])
                ],
            }
        )
    return trips


def stop_time_minutes(stop: dict[str, Any]) -> int | None:
    value = stop.get("departureTimeSec")
    if not isinstance(value, int):
        value = stop.get("arrivalTimeSec")
    return value // 60 if isinstance(value, int) else None


def hhmm(minutes: int | None) -> str:
    if not isinstance(minutes, int):
        return ""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def trip_terminal_names(station_groups: dict[str, dict[str, Any]], trip: dict[str, Any]) -> tuple[str, str]:
    stops = trip.get("stopTimes") or []
    if not stops:
        return "", ""
    return (
        station_name(station_groups.get(stops[0].get("stationGroupId") or "", {}), stops[0].get("stationGroupId") or ""),
        station_name(station_groups.get(stops[-1].get("stationGroupId") or "", {}), stops[-1].get("stationGroupId") or ""),
    )


def service_blob(trip: dict[str, Any]) -> str:
    return " ".join(str(trip.get(key) or "") for key in ("displayName", "serviceName", "serviceNumber"))


def service_family(trip: dict[str, Any], routes: dict[str, dict[str, Any]]) -> str:
    for key in ("displayName", "serviceName"):
        value = str(trip.get(key) or "").strip()
        if value:
            value = SERVICE_NUMBER_RE.sub("", value).strip()
            value = re.sub(r"\s+", "", value)
            if value:
                return value
    return route_title(routes.get(trip.get("routeId") or ""), trip.get("routeId") or "")


def is_named_train_family(family: str, trip: dict[str, Any], routes: dict[str, dict[str, Any]]) -> bool:
    if not family or family in ORDINARY_SERVICE_NAMES:
        return False
    if LETTERED_RAPID_RE.match(family):
        return False
    if ORDINARY_DESTINATION_LABEL_RE.match(str(trip.get("displayName") or "").strip()):
        return False
    if ROUTE_LIKE_RE.search(family):
        return False
    if ROUTE_SERVICE_TYPE_RE.search(family):
        return False
    route_name = route_title(routes.get(trip.get("routeId") or ""), trip.get("routeId") or "")
    if family == route_name:
        return False
    blob = service_blob(trip)
    return bool(TRAIN_NUMBER_RE.search(blob) or family not in ORDINARY_SERVICE_NAMES)


def add_sample(samples: list[dict[str, Any]], sample: dict[str, Any]) -> None:
    if len(samples) < SAMPLE_LIMIT:
        samples.append(sample)


def audit_time_distribution(
    map_bundle: dict[str, Any],
    trips: list[dict[str, Any]],
    *,
    min_departures: int,
    max_span_minutes: int,
    min_touch_to_departure_ratio: float,
) -> dict[str, Any]:
    station_groups = {group["id"]: group for group in map_bundle.get("stationGroups", [])}
    routes = {route["id"]: route for route in map_bundle.get("serviceRoutes", [])}
    cluster_ids = station_cluster_ids(station_groups)
    groups: dict[tuple[str, str], dict[str, Any]] = {}

    for trip in trips:
        family = service_family(trip, routes)
        if not is_named_train_family(family, trip, routes):
            continue
        origin, destination = trip_terminal_names(station_groups, trip)
        stops = trip.get("stopTimes") or []
        for index, stop in enumerate(stops):
            station_group_id = str(stop.get("stationGroupId") or "")
            name = station_name(station_groups.get(station_group_id, {}), station_group_id)
            if not name:
                continue
            cluster_id = cluster_ids.get(station_group_id, station_group_id)
            key = (cluster_id, family)
            item = groups.setdefault(
                key,
                {
                    "station": name,
                    "stationGroupId": cluster_id,
                    "stationGroupIds": set(),
                    "serviceFamily": family,
                    "touchCount": 0,
                    "departureTimes": [],
                    "seenTouchKeys": set(),
                    "seenDepartureKeys": set(),
                    "touchSamples": [],
                    "departureSamples": [],
                },
            )
            item["stationGroupIds"].add(station_group_id)
            minute = stop_time_minutes(stop)
            event_key = (
                minute,
                str(trip.get("displayName") or ""),
                str(trip.get("serviceNumber") or ""),
                origin,
                destination,
            )
            if event_key not in item["seenTouchKeys"]:
                item["seenTouchKeys"].add(event_key)
                item["touchCount"] += 1
                add_sample(
                    item["touchSamples"],
                    {
                        "time": hhmm(minute),
                        "tripId": trip.get("id"),
                        "serviceName": trip.get("serviceName") or "",
                        "displayName": trip.get("displayName") or "",
                        "serviceNumber": trip.get("serviceNumber") or "",
                        "origin": origin,
                        "destination": destination,
                    },
                )
            if index + 1 >= len(stops):
                continue
            next_station = station_name(station_groups.get(stops[index + 1].get("stationGroupId") or "", {}), stops[index + 1].get("stationGroupId") or "")
            departure_key = (*event_key, next_station)
            if departure_key in item["seenDepartureKeys"]:
                continue
            item["seenDepartureKeys"].add(departure_key)
            item["departureTimes"].append(minute)
            add_sample(
                item["departureSamples"],
                {
                    "time": hhmm(minute),
                    "tripId": trip.get("id"),
                    "serviceName": trip.get("serviceName") or "",
                    "displayName": trip.get("displayName") or "",
                    "serviceNumber": trip.get("serviceNumber") or "",
                    "origin": origin,
                    "destination": destination,
                    "nextStation": next_station,
                },
            )

    findings = []
    reviewed_examples = []
    for item in groups.values():
        times = sorted(minute for minute in item["departureTimes"] if isinstance(minute, int))
        departure_count = len(times)
        if not departure_count:
            continue
        hour_counts = Counter(minute // 60 for minute in times)
        active_hours = sorted(hour_counts)
        span = times[-1] - times[0] if len(times) >= 2 else 0
        largest_gap = max((right - left for left, right in zip(times, times[1:])), default=0)
        touch_count = int(item["touchCount"])
        touch_to_departure_ratio = touch_count / departure_count if departure_count else 0
        summary = {
            "station": item["station"],
            "stationGroupId": item["stationGroupId"],
            "stationGroupIds": sorted(item["stationGroupIds"]),
            "serviceFamily": item["serviceFamily"],
            "touchCount": touch_count,
            "departureCount": departure_count,
            "touchToDepartureRatio": round(touch_to_departure_ratio, 2),
            "firstDeparture": hhmm(times[0]),
            "lastDeparture": hhmm(times[-1]),
            "spanMinutes": span,
            "largestGapMinutes": largest_gap,
            "activeHourCount": len(active_hours),
            "hourCounts": {str(hour): hour_counts[hour] for hour in active_hours},
            "departureSamples": item["departureSamples"],
            "touchSamples": item["touchSamples"],
        }
        reasons = []
        if departure_count >= min_departures and span <= max_span_minutes:
            reasons.append("departures_concentrated_in_short_span")
        if departure_count >= min_departures and departure_count <= 12 and touch_to_departure_ratio >= min_touch_to_departure_ratio:
            reasons.append("many_touches_but_few_boardable_departures")
        if reasons:
            findings.append({"kind": "named_train_time_distribution_candidate", "reasons": reasons, **summary})
        elif item["station"] in {"東京", "新宿", "八王子", "上野", "品川"} and departure_count >= min_departures:
            reviewed_examples.append(summary)

    findings.sort(
        key=lambda item: (
            item["station"] != "東京",
            item["serviceFamily"] != "あずさ",
            item["spanMinutes"],
            -item["touchToDepartureRatio"],
            item["station"],
            item["serviceFamily"],
        )
    )
    return {
        "summary": {
            "namedStationServiceGroupCount": len(groups),
            "candidateCount": len(findings),
            "reviewedExampleCount": len(reviewed_examples),
            "minDepartures": min_departures,
            "maxSpanMinutes": max_span_minutes,
            "minTouchToDepartureRatio": min_touch_to_departure_ratio,
            "dedupeKey": "minute + displayName + serviceNumber + origin + destination + nextStation",
            "stationGrouping": "same-name station groups within 700m are merged to match direct-transfer gameplay assumptions",
        },
        "candidates": findings[:300],
        "reviewedExamples": reviewed_examples[:80],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-bundle", type=Path, default=DEFAULT_MAP_BUNDLE)
    parser.add_argument("--timetable", type=Path, default=DEFAULT_TIMETABLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-departures", type=int, default=DEFAULT_MIN_DEPARTURES)
    parser.add_argument("--max-span-minutes", type=int, default=DEFAULT_MAX_SPAN_MINUTES)
    parser.add_argument("--min-touch-to-departure-ratio", type=float, default=DEFAULT_MIN_TOUCH_TO_DEPARTURE_RATIO)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    map_bundle = load_json(args.map_bundle)
    timetable = load_json(args.timetable)
    trips = decode_compact_timetable(timetable)
    audit = {
        "schema": "onichase.v4.named_train_time_distribution_audit.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "inputs": {
            "mapBundle": rel(args.map_bundle),
            "timetable": rel(args.timetable),
            "minDepartures": args.min_departures,
            "maxSpanMinutes": args.max_span_minutes,
            "minTouchToDepartureRatio": args.min_touch_to_departure_ratio,
        },
        **audit_time_distribution(
            map_bundle,
            trips,
            min_departures=args.min_departures,
            max_span_minutes=args.max_span_minutes,
            min_touch_to_departure_ratio=args.min_touch_to_departure_ratio,
        ),
    }
    write_json(args.output, audit)
    print(
        f"Wrote {rel(args.output)}: "
        f"groups={audit['summary']['namedStationServiceGroupCount']} "
        f"candidates={audit['summary']['candidateCount']}"
    )


if __name__ == "__main__":
    main()
