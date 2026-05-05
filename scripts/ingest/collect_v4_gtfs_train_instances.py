#!/usr/bin/env python3
"""Collect v4 train instances from GTFS/GTFS-JP timetable feeds.

This collector intentionally starts with structured GTFS feeds before tackling
operator-specific HTML/PDF timetable pages.  It writes one combined v4 dataset
plus an audit so station matching can be improved without hiding uncertainty.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
import re
import unicodedata
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "data" / "v4_timetable_source_registry.json"
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_gtfs_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_gtfs_train_instances_audit.json"
DEFAULT_ODPT_RESOURCE_AUDIT = ROOT / "data" / "v4_odpt_gtfs_resource_audit.json"
DEFAULT_MANUAL_GTFS_OVERRIDES = ROOT / "data" / "v4_manual_gtfs_feed_overrides.json"
DEFAULT_SERVICE_DATE = "2026-04-27"


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").strip().lower()
    replacements = {
        "　": "",
        " ": "",
        "-": "",
        "‐": "",
        "ー": "",
        "・": "",
        "ヶ": "ケ",
        "ヵ": "カ",
        "挾": "挟",
        "祇": "祗",
        "（": "",
        "）": "",
        "(": "",
        ")": "",
        "〈": "",
        "〉": "",
        "「": "",
        "」": "",
        "駅": "",
        "停留場": "",
        "電停": "",
        "前": "前",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def normalize_name_variants(value: str) -> list[str]:
    raw = value or ""
    normalized_raw = normalize_name(raw)
    variants = {normalized_raw}
    if normalized_raw.endswith(("の", "ノ")) and len(normalized_raw) > 1:
        variants.add(normalized_raw[:-1])
    without_parentheses = re_sub_parenthetical(raw)
    variants.add(normalize_name(without_parentheses))
    # Some tram GTFS feeds include sponsor prefixes before the actual stop name,
    # e.g. "TEKリサイクルセンター高岡 新吉久".  The official N02 station name
    # remains the trailing stop name.
    for separator in (" ", "　"):
        if separator in raw:
            variants.add(normalize_name(raw.split(separator)[-1]))
    return [variant for variant in variants if variant]


def re_sub_parenthetical(value: str) -> str:
    text = value or ""
    text = re_sub(r"（[^）]*）", "", text)
    text = re_sub(r"\([^)]*\)", "", text)
    return text


def re_sub(pattern: str, repl: str, value: str) -> str:
    import re

    return re.sub(pattern, repl, value)


def normalize_line(value: str) -> str:
    text = normalize_name(value)
    for suffix in ("行き", "行", "止", "方面", "ゆき"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_bytes(url: str, timeout: int = 90) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "OniChase-v4-gtfs-collector/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def read_gtfs_csv(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    try:
        with archive.open(name) as handle:
            return list(csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig")))
    except KeyError:
        return []


def parse_service_date(value: str) -> date:
    return date.fromisoformat(value)


def active_service_ids(
    calendar_rows: list[dict[str, str]],
    calendar_dates_rows: list[dict[str, str]],
    service_day: date,
) -> set[str]:
    day_key = service_day.strftime("%A").lower()
    day_str = service_day.strftime("%Y%m%d")
    active = {
        row["service_id"]
        for row in calendar_rows
        if row.get(day_key) == "1"
        and row.get("start_date", "") <= day_str <= row.get("end_date", "")
    }
    for row in calendar_dates_rows:
        if row.get("date") != day_str:
            continue
        if row.get("exception_type") == "1":
            active.add(row["service_id"])
        elif row.get("exception_type") == "2":
            active.discard(row["service_id"])
    return active


def hhmm_from_gtfs_time(value: str | None) -> str | None:
    if not value:
        return None
    parts = value.split(":")
    if len(parts) < 2:
        return None
    return f"{int(parts[0]):02d}:{int(parts[1]):02d}"


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class V4StationMatcher:
    def __init__(self, physical_map: dict[str, Any]) -> None:
        self.physical_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.physical_by_operator: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        self.physical_by_operator_name: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        self.physical_by_operator_line_name: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        self.groups_by_id = {group["id"]: group for group in physical_map["stationGroups"]}
        for station in physical_map["physicalStations"]:
            operator_key = normalize_name(station.get("operatorName") or "")
            line_key = normalize_line(station.get("lineName") or "")
            for name_key in normalize_name_variants(station.get("nameJa") or ""):
                self.physical_by_name[name_key].append(station)
                self.physical_by_operator[operator_key].append((name_key, station))
                self.physical_by_operator_name[(operator_key, name_key)].append(station)
                self.physical_by_operator_line_name[(operator_key, line_key, name_key)].append(station)

    def match(
        self,
        operator_name: str,
        line_name: str | None,
        stop_name: str,
        stop_lat: str | None,
        stop_lon: str | None,
    ) -> dict[str, Any]:
        operator_key = normalize_name(operator_name)
        line_key = normalize_line(line_name or "")
        candidates: list[dict[str, Any]] = []
        method = "unmatched"

        for name_key in normalize_name_variants(stop_name):
            if line_key:
                candidates = self.physical_by_operator_line_name.get((operator_key, line_key, name_key), [])
                if candidates:
                    method = "operator_line_name"
                    break
            candidates = self.physical_by_operator_name.get((operator_key, name_key), [])
            if candidates:
                method = "operator_name"
                break
            candidates = self.physical_by_name.get(name_key, [])
            if candidates:
                method = "name_only"
                break

        if not candidates:
            for name_key in normalize_name_variants(stop_name):
                if len(name_key) < 3:
                    continue
                suffix_candidates = [
                    station
                    for station_key, station in self.physical_by_operator.get(operator_key, [])
                    if (
                        station_key.endswith(name_key)
                        or name_key.endswith(station_key)
                        or station_key.startswith(name_key)
                        or name_key.startswith(station_key)
                    )
                ]
                if suffix_candidates:
                    candidates = suffix_candidates
                    method = "operator_name_suffix"
                    break

        if not candidates:
            return {
                "matched": False,
                "method": method,
                "stationGroupId": None,
                "physicalStationId": None,
                "distanceMeters": None,
                "candidateCount": 0,
            }

        lat = float(stop_lat) if stop_lat else None
        lon = float(stop_lon) if stop_lon else None
        if lat is not None and lon is not None:
            ranked = sorted(
                candidates,
                key=lambda station: haversine_m(lat, lon, float(station["lat"]), float(station["lon"])),
            )
            best = ranked[0]
            distance = haversine_m(lat, lon, float(best["lat"]), float(best["lon"]))
            if method == "name_only" and distance > 1_500:
                return {
                    "matched": False,
                    "method": "name_only_too_far",
                    "stationGroupId": None,
                    "physicalStationId": None,
                    "distanceMeters": round(distance, 1),
                    "candidateCount": len(candidates),
                }
            return {
                "matched": True,
                "method": method + "_nearest",
                "stationGroupId": best["stationGroupId"],
                "physicalStationId": best["id"],
                "distanceMeters": round(distance, 1),
                "candidateCount": len(candidates),
            }

        group_ids = sorted({station["stationGroupId"] for station in candidates})
        if len(group_ids) == 1:
            station = candidates[0]
            return {
                "matched": True,
                "method": method + "_unique_group",
                "stationGroupId": group_ids[0],
                "physicalStationId": station["id"],
                "distanceMeters": None,
                "candidateCount": len(candidates),
            }
        return {
            "matched": False,
            "method": method + "_ambiguous_without_coordinates",
            "stationGroupId": None,
            "physicalStationId": None,
            "distanceMeters": None,
            "candidateCount": len(candidates),
        }


def build_line_lookup(inventory: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_operator: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in inventory["lines"]:
        by_operator[line["operatorName"]].append(line)
    return by_operator


def match_line(operator_lines: list[dict[str, Any]], route: dict[str, str]) -> dict[str, Any]:
    route_names = [
        route.get("route_long_name") or "",
        route.get("route_short_name") or "",
        route.get("route_desc") or "",
    ]
    normalized_routes = [normalize_line(name) for name in route_names if name]
    best: tuple[int, dict[str, Any] | None] = (0, None)
    for line in operator_lines:
        line_key = normalize_line(line["lineName"])
        score = 0
        for route_key in normalized_routes:
            if not route_key:
                continue
            if route_key == line_key:
                score = max(score, 100)
            elif line_key and line_key in route_key:
                score = max(score, 80)
            elif route_key and route_key in line_key:
                score = max(score, 70)
        if score > best[0]:
            best = (score, line)
    if best[1]:
        return {
            "lineId": best[1]["id"],
            "lineName": best[1]["lineName"],
            "lineMatchScore": best[0],
        }
    return {
        "lineId": f"GTFS_ROUTE_{route.get('route_id')}",
        "lineName": route.get("route_long_name") or route.get("route_short_name") or route.get("route_id"),
        "lineMatchScore": 0,
    }


def collect_gtfs_feed(
    feed: dict[str, Any],
    service_day: date,
    matcher: V4StationMatcher,
    line_lookup: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    raw = fetch_bytes(feed["fileUrl"])
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        routes = {row["route_id"]: row for row in read_gtfs_csv(archive, "routes.txt")}
        trips = read_gtfs_csv(archive, "trips.txt")
        stops = {row["stop_id"]: row for row in read_gtfs_csv(archive, "stops.txt")}
        stop_times = read_gtfs_csv(archive, "stop_times.txt")
        calendar_rows = read_gtfs_csv(archive, "calendar.txt")
        calendar_dates_rows = read_gtfs_csv(archive, "calendar_dates.txt")
        agency_rows = read_gtfs_csv(archive, "agency.txt")

    active_services = active_service_ids(calendar_rows, calendar_dates_rows, service_day)
    trip_by_id = {trip["trip_id"]: trip for trip in trips}
    trip_stop_times: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in stop_times:
        trip_stop_times[row["trip_id"]].append(row)
    for rows in trip_stop_times.values():
        rows.sort(key=lambda item: int(item.get("stop_sequence") or 0))

    operator_name = feed["operatorName"]
    operator_id = feed["operatorId"]
    feed_key = feed["feedKey"]
    operator_lines = line_lookup.get(operator_name, [])
    route_match_cache = {route_id: match_line(operator_lines, route) for route_id, route in routes.items()}

    train_instances: list[dict[str, Any]] = []
    unmatched_stops: dict[tuple[str, str, str], dict[str, Any]] = {}
    match_methods: Counter[str] = Counter()
    line_match_scores: Counter[int] = Counter()
    skipped_inactive = 0
    skipped_no_stops = 0

    for trip in trips:
        if trip.get("service_id") not in active_services:
            skipped_inactive += 1
            continue
        rows = trip_stop_times.get(trip["trip_id"], [])
        if len(rows) < 2:
            skipped_no_stops += 1
            continue
        route = routes.get(trip.get("route_id"))
        if not route:
            continue
        line_match = route_match_cache[trip["route_id"]]
        line_match_scores[int(line_match["lineMatchScore"])] += 1
        route_color = route.get("route_color") or None
        normalized_stop_times: list[dict[str, Any]] = []
        visit_counts: Counter[str] = Counter()

        for row in rows:
            stop = stops.get(row.get("stop_id", ""), {})
            stop_name = stop.get("stop_name") or row.get("stop_id") or ""
            match = matcher.match(
                operator_name=operator_name,
                line_name=line_match.get("lineName"),
                stop_name=stop_name,
                stop_lat=stop.get("stop_lat"),
                stop_lon=stop.get("stop_lon"),
            )
            match_methods[match["method"]] += 1
            if match["matched"]:
                station_id = match["stationGroupId"]
                visit_counts[station_id] += 1
            else:
                fallback_key = f"GTFS_{operator_id}_{row.get('stop_id') or stop_name}"
                station_id = fallback_key
                unmatched_stops.setdefault(
                    (operator_name, str(row.get("stop_id")), stop_name),
                    {
                        "operatorName": operator_name,
                        "feedName": feed.get("feedName"),
                        "stopId": row.get("stop_id"),
                        "stopName": stop_name,
                        "stopLat": stop.get("stop_lat"),
                        "stopLon": stop.get("stop_lon"),
                        "lineName": line_match.get("lineName"),
                        "matchMethod": match["method"],
                        "candidateCount": match["candidateCount"],
                        "distanceMeters": match["distanceMeters"],
                    },
                )
                visit_counts[station_id] += 1

            normalized_stop_times.append(
                {
                    "sequence": int(row.get("stop_sequence") or len(normalized_stop_times) + 1),
                    "station_name_raw": stop_name,
                    "station_id": station_id,
                    "station_group_id": match["stationGroupId"],
                    "physical_station_id": match["physicalStationId"],
                    "gtfs_stop_id": row.get("stop_id"),
                    "line_id": line_match["lineId"],
                    "line_name": line_match["lineName"],
                    "arrival_hhmm": hhmm_from_gtfs_time(row.get("arrival_time")),
                    "departure_hhmm": hhmm_from_gtfs_time(row.get("departure_time")),
                    "platform": stop.get("platform_code") or stop.get("stop_code") or None,
                    "loop_pass_index": visit_counts[station_id],
                    "match_method": match["method"],
                    "match_distance_m": match["distanceMeters"],
                }
            )

        service_name = line_match["lineName"] or route.get("route_long_name") or route.get("route_short_name") or route.get("route_id")
        train_number = f"{operator_id}:{feed_key}:{trip['trip_id']}"
        train_instances.append(
            {
                "train_number": train_number,
                "service_instance_id": train_number,
                "source_trip_id": trip["trip_id"],
                "source_route_id": trip.get("route_id"),
                "operator_id": operator_id,
                "operator_name": operator_name,
                "service_name": service_name,
                "headsign": trip.get("trip_headsign") or "",
                "train_type": route.get("route_short_name") or None,
                "route_color": route_color,
                "line_id": line_match["lineId"],
                "line_name": line_match["lineName"],
                "source_feed_key": feed_key,
                "stop_times": normalized_stop_times,
            }
        )

    audit = {
        "operatorId": operator_id,
        "operatorName": operator_name,
        "feedName": feed.get("feedName"),
        "feedKey": feed_key,
        "fileUrl": feed.get("fileUrl"),
        "agencyNames": [row.get("agency_name") for row in agency_rows if row.get("agency_name")],
        "routeCount": len(routes),
        "tripCount": len(trips),
        "activeServiceIds": sorted(active_services),
        "trainInstanceCount": len(train_instances),
        "skippedInactiveTrips": skipped_inactive,
        "skippedNoStopTrips": skipped_no_stops,
        "stopTimeCount": sum(len(train["stop_times"]) for train in train_instances),
        "unmatchedStopCount": len(unmatched_stops),
        "matchMethods": dict(sorted(match_methods.items())),
        "lineMatchScores": dict(sorted(line_match_scores.items())),
    }
    return train_instances, audit, sorted(unmatched_stops.values(), key=lambda item: (item["operatorName"], item["stopName"]))


def collect_feed_leads(registry: dict[str, Any]) -> list[dict[str, Any]]:
    leads_by_url: dict[str, dict[str, Any]] = {}
    for operator in registry["operators"]:
        for lead in operator.get("sourceLeads", []):
            if lead.get("candidateStatus") != "rail_gtfs_candidate":
                continue
            file_url = lead.get("fileUrl")
            if not file_url:
                continue
            key = file_url.split("?uid=")[0]
            if key in leads_by_url:
                continue
            leads_by_url[key] = {
                "operatorId": operator["operatorId"],
                "operatorName": operator["operatorName"],
                "feedName": lead.get("feedName") or lead.get("title") or operator["operatorName"],
                "feedKey": (lead.get("feedName") or lead.get("organizationName") or operator["operatorName"]).replace(" ", "_"),
                "fileUrl": file_url,
                "sourceKind": lead.get("sourceKind"),
            }
    return sorted(leads_by_url.values(), key=lambda item: (item["operatorName"], item["feedName"]))


def safe_feed_key(value: str) -> str:
    text = re.sub(r"[^0-9A-Za-z一-龥ぁ-んァ-ヶー]+", "_", value).strip("_")
    return text or "feed"


def collect_odpt_public_feed_leads(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    audit = load_json(path)
    leads: list[dict[str, Any]] = []
    for operator in audit.get("operators", []):
        for download in operator.get("publicDownloads", []):
            if not download.get("url"):
                continue
            date_key = download.get("detectedDate") or "undated"
            leads.append(
                {
                    "operatorId": operator["operatorId"],
                    "operatorName": operator["operatorName"],
                    "feedName": f"{operator.get('title') or operator['operatorName']} {date_key}",
                    "feedKey": safe_feed_key("ODPT_" + operator["operatorName"] + "_" + date_key),
                    "fileUrl": download["url"],
                    "sourceKind": "odpt_public_gtfs_discovered",
                    "catalogUrl": operator.get("catalogUrl"),
                }
            )
    return sorted(leads, key=lambda item: (item["operatorName"], item["feedName"], item["fileUrl"]))


def collect_manual_feed_overrides(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = load_json(path)
    leads: list[dict[str, Any]] = []
    for feed in data.get("feeds", []):
        if not feed.get("fileUrl"):
            continue
        leads.append(
            {
                "operatorId": feed["operatorId"],
                "operatorName": feed["operatorName"],
                "feedName": feed.get("feedName") or feed["operatorName"],
                "feedKey": feed.get("feedKey") or safe_feed_key("manual_" + feed["operatorName"]),
                "fileUrl": feed["fileUrl"],
                "sourceKind": feed.get("sourceKind") or "manual_gtfs_feed_override",
            }
        )
    return sorted(leads, key=lambda item: (item["operatorName"], item["feedName"], item["fileUrl"]))


def dedupe_feeds(feeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for feed in feeds:
        key = feed["fileUrl"].split("?uid=")[0]
        if key in seen:
            continue
        seen.add(key)
        output.append(feed)
    return output


def minutes_from_hhmm(value: str | None) -> int | None:
    if not value:
        return None
    parts = value.split(":")
    if len(parts) < 2:
        return None
    return int(parts[0]) * 60 + int(parts[1])


def audit_train_integrity(train_instances: list[dict[str, Any]], physical_map: dict[str, Any]) -> dict[str, Any]:
    groups = {group["id"] for group in physical_map["stationGroups"]}
    id_counts = Counter(train["train_number"] for train in train_instances)
    duplicate_ids = sorted(train_id for train_id, count in id_counts.items() if count > 1)
    operator_counts = Counter(train["operator_name"] for train in train_instances)
    missing_station_refs: list[dict[str, Any]] = []
    bad_time_order: list[dict[str, Any]] = []
    short_trains: list[str] = []

    for train in train_instances:
        stop_times = train.get("stop_times") or []
        if len(stop_times) < 2:
            short_trains.append(train["train_number"])
        previous_minutes = -1
        for stop in stop_times:
            station_id = stop.get("station_id")
            if station_id not in groups:
                missing_station_refs.append(
                    {
                        "trainNumber": train["train_number"],
                        "stationId": station_id,
                        "stationNameRaw": stop.get("station_name_raw"),
                    }
                )
            current_minutes = minutes_from_hhmm(stop.get("departure_hhmm") or stop.get("arrival_hhmm"))
            if current_minutes is None:
                continue
            if current_minutes < previous_minutes:
                bad_time_order.append(
                    {
                        "trainNumber": train["train_number"],
                        "previousMinutes": previous_minutes,
                        "currentMinutes": current_minutes,
                        "stationNameRaw": stop.get("station_name_raw"),
                    }
                )
            previous_minutes = max(previous_minutes, current_minutes)

    return {
        "operatorTrainCounts": dict(sorted(operator_counts.items())),
        "duplicateTrainIdCount": len(duplicate_ids),
        "duplicateTrainIdsSample": duplicate_ids[:20],
        "missingStationReferenceCount": len(missing_station_refs),
        "missingStationReferencesSample": missing_station_refs[:20],
        "badTimeOrderCount": len(bad_time_order),
        "badTimeOrderSample": bad_time_order[:20],
        "shortTrainInstanceCount": len(short_trains),
        "shortTrainInstancesSample": short_trains[:20],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--line-inventory", type=Path, default=ROOT / "docs" / "data" / "v4_maplibre" / "line_inventory.json")
    parser.add_argument("--service-date", default=DEFAULT_SERVICE_DATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--odpt-resource-audit", type=Path, default=DEFAULT_ODPT_RESOURCE_AUDIT)
    parser.add_argument("--manual-gtfs-overrides", type=Path, default=DEFAULT_MANUAL_GTFS_OVERRIDES)
    parser.add_argument("--max-feeds", type=int, default=0)
    args = parser.parse_args()

    registry = load_json(args.registry)
    physical_map = load_json(args.physical_map)
    line_inventory = load_json(args.line_inventory)
    service_day = parse_service_date(args.service_date)
    matcher = V4StationMatcher(physical_map)
    line_lookup = build_line_lookup(line_inventory)
    feeds = dedupe_feeds(
        collect_feed_leads(registry)
        + collect_odpt_public_feed_leads(args.odpt_resource_audit)
        + collect_manual_feed_overrides(args.manual_gtfs_overrides)
    )
    if args.max_feeds:
        feeds = feeds[: args.max_feeds]

    all_trains: list[dict[str, Any]] = []
    feed_audits: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for index, feed in enumerate(feeds, start=1):
        print(f"[{index}/{len(feeds)}] {feed['operatorName']} / {feed['feedName']}", flush=True)
        trains, audit, unmatched_stops = collect_gtfs_feed(feed, service_day, matcher, line_lookup)
        all_trains.extend(trains)
        feed_audits.append(audit)
        unmatched.extend(unmatched_stops)
        print(
            f"  trains={audit['trainInstanceCount']} unmatched_stops={audit['unmatchedStopCount']} "
            f"active_services={len(audit['activeServiceIds'])}",
            flush=True,
        )

    output = {
        "id": "v4_gtfs_weekday_train_instances_v0_1",
        "label": "V4 weekday train instances collected from structured GTFS/GTFS-JP feeds",
        "version": "0.1.0",
        "service_day": service_day.isoformat(),
        "source_registry": str(args.registry.relative_to(ROOT) if args.registry.is_relative_to(ROOT) else args.registry),
        "station_identity": physical_map.get("identityVersion"),
        "feed_count": len(feeds),
        "train_instances": sorted(all_trains, key=lambda item: item["train_number"]),
    }
    integrity = audit_train_integrity(all_trains, physical_map)
    audit = {
        "schema": "onichase.v4.gtfs_train_instances_audit.v1",
        "serviceDay": service_day.isoformat(),
        "feedCount": len(feeds),
        "trainInstanceCount": len(all_trains),
        "stopTimeCount": sum(len(train["stop_times"]) for train in all_trains),
        "unmatchedStopCount": len(unmatched),
        "duplicateTrainIdCount": integrity["duplicateTrainIdCount"],
        "missingStationReferenceCount": integrity["missingStationReferenceCount"],
        "badTimeOrderCount": integrity["badTimeOrderCount"],
        "shortTrainInstanceCount": integrity["shortTrainInstanceCount"],
        "integrity": integrity,
        "feedAudits": feed_audits,
        "unmatchedStops": unmatched,
    }
    write_json(args.output, output)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(all_trains)} train instances")
    print(f"Wrote {args.audit_output}: {len(unmatched)} unmatched stops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
