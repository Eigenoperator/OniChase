#!/usr/bin/env python3
"""Adapt the frozen v3 timetable corpus onto v4 station_identity_v2.

v3 already contains a large verified Tokyo/Shinkansen timetable corpus, but its
station groups predate v4's stricter real-location identity rules.  This script
does not copy v3 station ids.  It rematches every stop to the v4 nationwide
station groups using station name, line/operator hints, and real coordinates.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_V3_BUNDLE = ROOT / "data" / "v3_tokyo_bundle.json.gz"
DEFAULT_V3_UNIFIED = ROOT / "data" / "v3_trains_unified.json.gz"
DEFAULT_V4_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_existing_v3_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_existing_v3_train_instances_audit.json"


V3_OPERATOR_TO_V4: dict[str, str | None] = {
    "jr_central": "東海旅客鉄道",
    "jr_east": "東日本旅客鉄道",
    "keikyu": "京浜急行電鉄",
    "keio": "京王電鉄",
    "keisei": "京成電鉄",
    "odakyu": "小田急電鉄",
    "rinkai": "東京臨海高速鉄道",
    "saitama_railway": "埼玉高速鉄道",
    "seibu": "西武鉄道",
    "shinkansen": None,
    "sotetsu": "相模鉄道",
    "tama_monorail": "多摩都市モノレール",
    "tobu": "東武鉄道",
    "toei": "東京都",
    "tokyo_metro": "東京地下鉄",
    "tokyo_monorail": "東京モノレール",
    "tokyu": "東急電鉄",
    "tsukuba_express": "首都圏新都市鉄道",
    "yurikamome": "ゆりかもめ",
}


def normalize_name(value: str | None) -> str:
    text = (value or "").strip().lower()
    replacements = {
        "　": "",
        " ": "",
        "-": "",
        "‐": "",
        "ー": "",
        "・": "",
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
        "塚": "塚",
        "ヶ": "ケ",
        "が": "ガ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def normalize_line(value: str | None) -> str:
    text = normalize_name(value)
    aliases = {
        "rinkai": "りんかい線",
        "yurikamome": "東京臨海新交通臨海線",
        "tokyomonorailhaneda": "東京モノレール羽田線",
        "tamamonorail": "多摩都市モノレール線",
    }
    return normalize_name(aliases.get(text, text))


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


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def seconds_to_hhmm(value: int | None) -> str | None:
    if value is None:
        return None
    minutes = int(value) // 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_ext_n02_station_id(value: str | None) -> tuple[str | None, str | None]:
    if not value or not value.startswith("EXT_N02_"):
        return None, None
    parts = value.split("_")
    if len(parts) < 5:
        return None, None
    return parts[2], parts[3]


class V4StopMatcher:
    def __init__(self, v4_map: dict[str, Any], v3_bundle: dict[str, Any]) -> None:
        self.v4_groups_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.v4_groups_by_id = {group["id"]: group for group in v4_map["stationGroups"]}
        self.v4_physical_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for group in v4_map["stationGroups"]:
            keys = set(group.get("nameKeys") or [])
            keys.add(group.get("nameJa") or "")
            for key in keys:
                normalized = normalize_name(key)
                if normalized:
                    self.v4_groups_by_name[normalized].append(group)
        for station in v4_map["physicalStations"]:
            self.v4_physical_by_group[str(station.get("stationGroupId") or "")].append(station)

        self.v3_groups_by_id = {group["id"]: group for group in v3_bundle["stationGroups"]}
        self.v3_physical_by_id = {station["id"]: station for station in v3_bundle["physicalStations"]}

    def v3_reference_points(self, v3_group: dict[str, Any], desired_operator: str | None) -> list[dict[str, Any]]:
        physicals = [
            self.v3_physical_by_id[station_id]
            for station_id in v3_group.get("physicalStationIds", [])
            if station_id in self.v3_physical_by_id
        ]
        if desired_operator:
            matching = [
                station
                for station in physicals
                if desired_operator in {V3_OPERATOR_TO_V4.get(op, op) for op in station.get("operatorIds", [])}
            ]
            if matching:
                return matching
        return physicals

    def choose_physical_station(
        self,
        group: dict[str, Any],
        desired_operator: str | None,
        desired_line: str | None,
        reference_points: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        stations = self.v4_physical_by_group.get(str(group.get("id") or ""), [])
        if not stations:
            return None
        desired_line_key = normalize_line(desired_line)
        ranked: list[tuple[float, dict[str, Any]]] = []
        for station in stations:
            score = 0.0
            if desired_operator and station.get("operatorName") == desired_operator:
                score += 5_000
            if desired_line_key and normalize_line(station.get("lineName")) == desired_line_key:
                score += 10_000
            if reference_points:
                distance = min(
                    haversine_m(
                        float(point["lat"]),
                        float(point["lon"]),
                        float(station["lat"]),
                        float(station["lon"]),
                    )
                    for point in reference_points
                )
                score -= min(distance, 100_000) / 10
            ranked.append((score, station))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked[0][1]

    def match_stop(
        self,
        v3_station_group_id: str,
        stop_hint: dict[str, Any],
        route_operator_id: str | None,
    ) -> dict[str, Any]:
        v3_group = self.v3_groups_by_id.get(v3_station_group_id)
        if not v3_group:
            return {"matched": False, "method": "missing_v3_group"}

        station_name = v3_group.get("primaryName") or (v3_group.get("names") or {}).get("ja") or stop_hint.get("station_name")
        name_key = normalize_name(station_name)
        candidates = self.v4_groups_by_name.get(name_key, [])
        if not candidates:
            return {
                "matched": False,
                "method": "no_v4_name_candidate",
                "stationName": station_name,
                "candidateCount": 0,
            }

        ext_operator, ext_line = parse_ext_n02_station_id(stop_hint.get("station_id"))
        desired_operator = ext_operator or V3_OPERATOR_TO_V4.get(route_operator_id or "")
        desired_line = ext_line or stop_hint.get("line")
        desired_line_key = normalize_line(desired_line)
        reference_points = self.v3_reference_points(v3_group, desired_operator)
        if not reference_points and v3_group.get("centroid"):
            reference_points = [{"lat": v3_group["centroid"]["lat"], "lon": v3_group["centroid"]["lon"]}]

        ranked: list[tuple[float, dict[str, Any], float | None, bool, bool]] = []
        for candidate in candidates:
            line_match = bool(
                desired_line_key
                and desired_line_key in {normalize_line(line) for line in candidate.get("lineNames", [])}
            )
            operator_match = bool(desired_operator and desired_operator in set(candidate.get("operatorNames", [])))
            distance = None
            if reference_points:
                distance = min(
                    haversine_m(
                        float(point["lat"]),
                        float(point["lon"]),
                        float(candidate["centroid"]["lat"]),
                        float(candidate["centroid"]["lon"]),
                    )
                    for point in reference_points
                )
            score = 0.0
            if line_match:
                score += 10_000
            if operator_match:
                score += 5_000
            if distance is not None:
                score -= min(distance, 100_000) / 10
            ranked.append((score, candidate, distance, line_match, operator_match))

        ranked.sort(key=lambda item: item[0], reverse=True)
        _score, best, distance, line_match, operator_match = ranked[0]
        if distance is not None and distance > 3_000 and not (line_match or operator_match):
            return {
                "matched": False,
                "method": "name_candidate_too_far",
                "stationName": station_name,
                "candidateCount": len(candidates),
                "distanceMeters": round(distance, 1),
                "bestCandidateId": best["id"],
                "bestCandidateName": best["nameJa"],
                "bestCandidateLocation": best.get("locationNote"),
            }

        if line_match and operator_match:
            method = "name_line_operator_distance"
        elif line_match:
            method = "name_line_distance"
        elif operator_match:
            method = "name_operator_distance"
        else:
            method = "name_distance"
        physical_station = self.choose_physical_station(best, desired_operator, desired_line, reference_points)
        return {
            "matched": True,
            "method": method,
            "stationGroupId": best["id"],
            "physicalStationId": physical_station.get("id") if physical_station else None,
            "stationName": best["nameJa"],
            "candidateCount": len(candidates),
            "distanceMeters": round(distance, 1) if distance is not None else None,
            "lineMatch": line_match,
            "operatorMatch": operator_match,
            "lineName": desired_line,
        }


def adapt_trains(v3_bundle: dict[str, Any], v3_unified: dict[str, Any], v4_map: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    routes_by_id = {route["id"]: route for route in v3_bundle["serviceRoutes"]}
    unified_by_id = {train["id"]: train for train in v3_unified["trains"]}
    matcher = V4StopMatcher(v4_map, v3_bundle)
    train_instances: list[dict[str, Any]] = []
    skipped_trains: list[dict[str, Any]] = []
    unmatched_stops: list[dict[str, Any]] = []
    match_methods: Counter[str] = Counter()
    operator_counts: Counter[str] = Counter()

    for trip in v3_bundle["tripInstances"]:
        route = routes_by_id.get(trip["routeId"], {})
        route_operator_id = route.get("operatorId")
        unified = unified_by_id.get(trip["id"], {})
        unified_stops = unified.get("stops") or []
        normalized_stops: list[dict[str, Any]] = []
        has_unmatched = False

        for index, stop in enumerate(trip["stopTimes"]):
            hint = unified_stops[index] if index < len(unified_stops) else {}
            match = matcher.match_stop(stop["stationGroupId"], hint, route_operator_id)
            match_methods[match.get("method", "unknown")] += 1
            if not match.get("matched"):
                has_unmatched = True
                unmatched_stops.append(
                    {
                        "trainId": trip["id"],
                        "sequence": stop.get("sequence"),
                        "v3StationGroupId": stop.get("stationGroupId"),
                        "v3StationName": (matcher.v3_groups_by_id.get(stop.get("stationGroupId")) or {}).get("primaryName"),
                        "hintStationName": hint.get("station_name"),
                        "hintLine": hint.get("line"),
                        "hintStationId": hint.get("station_id"),
                        "routeOperatorId": route_operator_id,
                        "match": match,
                    }
                )
                continue
            normalized_stops.append(
                {
                    "sequence": stop.get("sequence"),
                    "station_name_raw": match["stationName"],
                    "station_id": match["stationGroupId"],
                    "station_group_id": match["stationGroupId"],
                    "physical_station_id": match.get("physicalStationId"),
                    "line_id": route.get("shortName") or hint.get("line"),
                    "line_name": match.get("lineName") or route.get("shortName") or hint.get("line"),
                    "arrival_hhmm": seconds_to_hhmm(stop.get("arrivalTimeSec")),
                    "departure_hhmm": seconds_to_hhmm(stop.get("departureTimeSec")),
                    "platform": hint.get("platform"),
                    "loop_pass_index": hint.get("loop_pass_index"),
                    "match_method": match["method"],
                    "match_distance_m": match.get("distanceMeters"),
                    "source_v3_station_group_id": stop.get("stationGroupId"),
                }
            )

        if has_unmatched or len(normalized_stops) < 2:
            skipped_trains.append(
                {
                    "id": trip["id"],
                    "reason": "unmatched_stop" if has_unmatched else "short_train_after_matching",
                    "routeId": trip["routeId"],
                    "routeOperatorId": route_operator_id,
                }
            )
            continue

        operator_name = V3_OPERATOR_TO_V4.get(route_operator_id or "") or route.get("longName", "").split(" / ")[0] or route_operator_id
        train_number = trip.get("operatingNumber") or trip.get("serviceNumber") or trip["id"]
        train_instances.append(
            {
                "train_number": str(train_number),
                "service_instance_id": trip["id"],
                "source_trip_id": trip["id"],
                "operator_id": route_operator_id,
                "operator_name": operator_name,
                "service_name": trip.get("serviceName") or route.get("shortName"),
                "service_number": trip.get("serviceNumber"),
                "headsign": unified.get("direction") or "",
                "train_type": None,
                "route_color": (route.get("color") or "").lstrip("#") or None,
                "line_id": route.get("id"),
                "line_name": route.get("shortName"),
                "source_feed_key": "v3_release_candidate",
                "stop_times": normalized_stops,
            }
        )
        operator_counts[str(route_operator_id)] += 1

    output = {
        "id": "v4_existing_v3_weekday_train_instances_v0_1",
        "label": "Frozen v3 timetable corpus rematched to v4 station_identity_v2",
        "version": "0.1.0",
        "source_bundle": "data/v3_tokyo_bundle.json.gz",
        "source_unified_trains": "data/v3_trains_unified.json.gz",
        "station_identity": v4_map.get("identityVersion"),
        "train_instances": sorted(train_instances, key=lambda item: item["service_instance_id"]),
    }
    audit = {
        "schema": "onichase.v4.existing_v3_train_instances_audit.v1",
        "sourceTripCount": len(v3_bundle["tripInstances"]),
        "adaptedTrainInstanceCount": len(train_instances),
        "skippedTrainCount": len(skipped_trains),
        "unmatchedStopCount": len(unmatched_stops),
        "operatorTrainCounts": dict(sorted(operator_counts.items())),
        "matchMethods": dict(sorted(match_methods.items())),
        "skippedTrainsSample": skipped_trains[:50],
        "unmatchedStopsSample": unmatched_stops[:100],
    }
    return output, audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v3-bundle", type=Path, default=DEFAULT_V3_BUNDLE)
    parser.add_argument("--v3-unified", type=Path, default=DEFAULT_V3_UNIFIED)
    parser.add_argument("--v4-physical-map", type=Path, default=DEFAULT_V4_PHYSICAL_MAP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    v3_bundle = load_json(args.v3_bundle)
    v3_unified = load_json(args.v3_unified)
    v4_map = load_json(args.v4_physical_map)
    output, audit = adapt_trains(v3_bundle, v3_unified, v4_map)
    write_json(args.output, output)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {audit['adaptedTrainInstanceCount']} adapted trains")
    print(f"Wrote {args.audit_output}: {audit['unmatchedStopCount']} unmatched stops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
