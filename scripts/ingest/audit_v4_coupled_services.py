#!/usr/bin/env python3
"""Audit split/join coupled train services in the v4 gameplay timetable.

This audit is intentionally separate from ordinary through-running checks.
Through-running is one train continuing across route identities; coupled
services are two named portions that run together for a shared segment and
split or join at a station, such as Hayabusa+Komachi or Kanku+Kishuji Rapid.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_BUNDLE = ROOT / "data" / "v4_gameplay_map_bundle.json.gz"
DEFAULT_TIMETABLE = ROOT / "data" / "v4_gameplay_timetable_compact.json.gz"
DEFAULT_REGISTRY = ROOT / "data" / "v4_coupled_service_registry.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_coupled_service_audit.json"
DEFAULT_MAX_GAP_SEC = 420
SAMPLE_LIMIT = 30


KNOWN_COUPLED_SERVICE_SEEDS = [
    {
        "id": "hayabusa_komachi_morioka",
        "label": "はやぶさ+こまち",
        "splitJoinStation": "盛岡",
        "servicePortions": [["Hayabusa", "はやぶさ"], ["Komachi", "こまち"]],
        "expectedSharedSegment": "東京-盛岡",
        "confidence": "confirmed",
    },
    {
        "id": "yamabiko_tsubasa_fukushima",
        "label": "やまびこ+つばさ",
        "splitJoinStation": "福島",
        "servicePortions": [["Yamabiko", "やまびこ"], ["Tsubasa", "つばさ"]],
        "expectedSharedSegment": "東京-福島",
        "confidence": "confirmed",
    },
    {
        "id": "kanku_kishuji_hineno",
        "label": "関空快速+紀州路快速",
        "splitJoinStation": "日根野",
        "servicePortions": [["関空快速", "Kanku Rapid"], ["紀州路快速", "Kishuji Rapid"]],
        "expectedSharedSegment": "大阪環状線/阪和線-日根野",
        "confidence": "confirmed",
    },
    {
        "id": "shiokaze_ishizuchi_utazu_tadotsu",
        "label": "しおかぜ+いしづち",
        "splitJoinStation": "宇多津",
        "alternateSplitJoinStations": ["多度津"],
        "servicePortions": [["しおかぜ", "Shiokaze"], ["いしづち", "Ishizuchi"]],
        "expectedSharedSegment": "岡山/高松-宇多津/多度津",
        "confidence": "confirmed",
    },
    {
        "id": "sunrise_seto_izumo_okayama",
        "label": "サンライズ瀬戸+サンライズ出雲",
        "splitJoinStation": "岡山",
        "servicePortions": [["サンライズ瀬戸", "Sunrise Seto"], ["サンライズ出雲", "Sunrise Izumo"]],
        "expectedSharedSegment": "東京-岡山",
        "confidence": "confirmed",
    },
    {
        "id": "narita_express_tokyo",
        "label": "成田エクスプレス",
        "splitJoinStation": "東京",
        "servicePortions": [["成田エクスプレス", "Narita Express"]],
        "expectedSharedSegment": "東京-成田空港",
        "confidence": "confirmed",
    },
    {
        "id": "nanpu_shimanto_shikoku",
        "label": "南風+しまんと",
        "splitJoinStation": "宇多津",
        "alternateSplitJoinStations": ["多度津", "高松"],
        "servicePortions": [["南風", "Nanpu"], ["しまんと", "Shimanto"]],
        "expectedSharedSegment": "岡山/高松-宇多津/多度津",
        "confidence": "needs_official_current_review",
    },
    {
        "id": "kyoto_north_limited_express",
        "label": "きのさき/まいづる/はしだて",
        "splitJoinStation": "綾部",
        "servicePortions": [["きのさき", "Kinosaki"], ["まいづる", "Maizuru"], ["はしだて", "Hashidate"]],
        "expectedSharedSegment": "京都-綾部",
        "confidence": "needs_official_current_review",
    },
    {
        "id": "hida_gifu",
        "label": "ひだ",
        "splitJoinStation": "岐阜",
        "servicePortions": [["ひだ", "Hida"]],
        "expectedSharedSegment": "名古屋/大阪-岐阜",
        "confidence": "needs_official_current_review",
    },
]

SEED_DIAGNOSES = {
    "kanku_kishuji_hineno": {
        "diagnosis": "JR West official timetable rows exist for Kansai Airport/Hanwa/Osaka Loop rapid trains, but current data does not preserve Kanku Rapid/Kishuji Rapid portion labels. The JR West parser currently flattens multi-column train detail metadata.",
        "nextAction": "Teach the JR West collector/parser to preserve multi-column route/train-type portions around Hineno, then create Kanku/Kishuji coupled portions.",
    },
    "sunrise_seto_izumo_okayama": {
        "diagnosis": "Both Sunrise Seto and Sunrise Izumo are present, but they are split across JR Central/JR East/JR West source slices and do not form an Okayama same-time pair in the gameplay timetable.",
        "nextAction": "Add a cross-source Sunrise stitch/coupled rule keyed by 5031M/5032M and Okayama.",
    },
    "narita_express_tokyo": {
        "diagnosis": "N'EX exists as one named family, but the current data does not model Tokyo split/join portions as separate coupled portions.",
        "nextAction": "Infer portions from Tokyo-side branch signatures, such as Shinjuku/Ikebukuro/Omiya versus Yokohama/Ofuna.",
    },
    "kinosaki_maizuru_ayabe": {
        "diagnosis": "Kinosaki exists at Ayabe, but Maizuru is absent from the current gameplay timetable.",
        "nextAction": "Check JR West Kyoto/northern limited-express collection coverage for Maizuru and add missing source rows if available.",
    },
    "hashidate_maizuru_ayabe": {
        "diagnosis": "Hashidate exists at Ayabe, but Maizuru is absent from the current gameplay timetable.",
        "nextAction": "Check JR West Kyoto/northern limited-express collection coverage for Maizuru and add missing source rows if available.",
    },
    "hida_gifu": {
        "diagnosis": "Hida exists as one named family around Gifu, but the current data does not model Osaka/Nagoya/Takayama/Toyama portions.",
        "nextAction": "Review Hida branch signatures around Gifu and add a portion model only for trains with real split/join behavior.",
    },
    "odoriko_izu_shuzenji_atami": {
        "diagnosis": "Odoriko exists as one named family, but the current data does not distinguish the Izukyu-Shimoda and Shuzenji portions.",
        "nextAction": "Infer portions from branch signatures around Atami and preserve them as coupled portions.",
    },
    "yamatoji_wakayama_gojo_oji": {
        "diagnosis": "The current data has Oji/Wakayama Line evidence, but the source labels are broad ordinary rapid labels rather than explicit coupled portion names.",
        "nextAction": "Review Oji split signatures and avoid accepting broad 快速 labels as final portion names without timetable-detail confirmation.",
    },
}


def registry_entries_to_seeds(registry: dict[str, Any]) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    for entry in registry.get("entries", []):
        split_join_stations = list(entry.get("splitJoinStations") or [])
        portions = []
        for portion in entry.get("portions") or []:
            terms = [portion.get("label"), *(portion.get("aliases") or [])]
            portions.append([str(term) for term in terms if term])
        if not split_join_stations or not portions:
            continue
        seeds.append(
            {
                "id": entry.get("id"),
                "label": entry.get("label"),
                "splitJoinStation": split_join_stations[0],
                "alternateSplitJoinStations": split_join_stations[1:],
                "servicePortions": portions,
                "expectedSharedSegment": entry.get("sharedSegment"),
                "confidence": entry.get("confidence", "needs_review"),
                "system": entry.get("system"),
            }
        )
    return seeds


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


def route_title(route: dict[str, Any] | None, route_id: str = "") -> str:
    if not route:
        return route_id
    tags = route.get("tags") or {}
    return str(tags.get("lineName") or route.get("shortName") or route.get("longName") or route_id)


def station_title(group: dict[str, Any] | None, station_group_id: str = "") -> str:
    names = (group or {}).get("names") or {}
    return str(names.get("ja") or (group or {}).get("primaryName") or station_group_id)


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
                        "displayRouteId": route_ids[stop[3]] if len(stop) > 3 and stop[3] is not None and stop[3] < len(route_ids) else "",
                        "incomingRouteId": route_ids[stop[5]] if len(stop) > 5 and stop[5] is not None and stop[5] < len(route_ids) else "",
                    }
                    for index, stop in enumerate(row[4] or [])
                ],
            }
        )
    return trips


def service_label(trip: dict[str, Any]) -> str:
    return str(trip.get("displayName") or trip.get("serviceName") or "")


def service_blob(trip: dict[str, Any]) -> str:
    return " ".join(
        str(trip.get(key) or "")
        for key in ("id", "serviceName", "displayName", "serviceNumber", "headsign")
    )


def normalized_number(value: Any) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or "")).upper())


def number_digits(value: Any) -> str:
    match = re.search(r"\d+", normalized_number(value))
    return match.group(0) if match else ""


def stop_time_sec(stop: dict[str, Any], preferred: str) -> int | None:
    if preferred == "arrival":
        value = stop.get("arrivalTimeSec")
        if not isinstance(value, int):
            value = stop.get("departureTimeSec")
    else:
        value = stop.get("departureTimeSec")
        if not isinstance(value, int):
            value = stop.get("arrivalTimeSec")
    return value if isinstance(value, int) else None


def seconds_to_hhmm(value: int | None) -> str:
    if not isinstance(value, int):
        return ""
    minutes = value // 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def stop_index_at_station(
    station_groups: dict[str, dict[str, Any]],
    trip: dict[str, Any],
    station_name: str,
) -> int | None:
    for index, stop in enumerate(trip.get("stopTimes") or []):
        if station_title(station_groups.get(str(stop.get("stationGroupId") or ""))) == station_name:
            return index
    return None


def trip_terminal_names(station_groups: dict[str, dict[str, Any]], trip: dict[str, Any]) -> tuple[str, str]:
    stops = trip.get("stopTimes") or []
    if not stops:
        return "", ""
    return (
        station_title(station_groups.get(str(stops[0].get("stationGroupId") or ""))),
        station_title(station_groups.get(str(stops[-1].get("stationGroupId") or ""))),
    )


def neighbor_names_at_index(
    station_groups: dict[str, dict[str, Any]],
    trip: dict[str, Any],
    index: int,
) -> tuple[str, str]:
    stops = trip.get("stopTimes") or []
    previous_name = ""
    next_name = ""
    if index > 0:
        previous_name = station_title(station_groups.get(str(stops[index - 1].get("stationGroupId") or "")))
    if index + 1 < len(stops):
        next_name = station_title(station_groups.get(str(stops[index + 1].get("stationGroupId") or "")))
    return previous_name, next_name


def branch_signatures_at_seed_station(
    station_groups: dict[str, dict[str, Any]],
    routes: dict[str, dict[str, Any]],
    trips: list[dict[str, Any]],
    station_names: list[str],
) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, str, str, str]] = Counter()
    samples: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for trip in trips:
        for station_name in station_names:
            index = stop_index_at_station(station_groups, trip, station_name)
            if index is None:
                continue
            stop = trip["stopTimes"][index]
            previous_name, next_name = neighbor_names_at_index(station_groups, trip, index)
            origin, destination = trip_terminal_names(station_groups, trip)
            key = (
                station_name,
                previous_name,
                next_name,
                origin,
                destination,
            )
            counts[key] += 1
            samples.setdefault(
                key,
                {
                    "tripId": trip.get("id"),
                    "service": service_label(trip),
                    "number": trip.get("serviceNumber"),
                    "route": route_name_at_stop(routes, trip, stop),
                },
            )
    return [
        {
            "station": station,
            "previous": previous,
            "next": next_name,
            "origin": origin,
            "destination": destination,
            "count": count,
            "sample": samples[key],
        }
        for key, count in counts.most_common(20)
        for station, previous, next_name, origin, destination in [key]
    ]


def route_name_at_stop(routes: dict[str, dict[str, Any]], trip: dict[str, Any], stop: dict[str, Any]) -> str:
    route_id = str(stop.get("displayRouteId") or stop.get("incomingRouteId") or trip.get("routeId") or "")
    return route_title(routes.get(route_id), route_id)


def add_sample(samples: list[dict[str, Any]], sample: dict[str, Any]) -> None:
    if len(samples) < SAMPLE_LIMIT:
        samples.append(sample)


def flatten_portions(portions: list[list[str]]) -> list[str]:
    return [term for portion in portions for term in portion]


def matching_portion_indexes(trip: dict[str, Any], portions: list[list[str]]) -> set[int]:
    blob = service_blob(trip)
    return {
        index
        for index, portion in enumerate(portions)
        if any(term and term in blob for term in portion)
    }


def seed_term_counts(trips: list[dict[str, Any]], terms: list[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for trip in trips:
        blob = service_blob(trip)
        for term in terms:
            if term and term in blob:
                counts[term] += 1
    return dict(counts)


def audit_known_seeds(
    station_groups: dict[str, dict[str, Any]],
    routes: dict[str, dict[str, Any]],
    trips: list[dict[str, Any]],
    seeds: list[dict[str, Any]],
    *,
    max_gap_sec: int,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for seed in seeds:
        portions = [list(portion) for portion in seed["servicePortions"]]
        terms = flatten_portions(portions)
        station_names = [seed["splitJoinStation"], *seed.get("alternateSplitJoinStations", [])]
        matching_trips = [trip for trip in trips if matching_portion_indexes(trip, portions)]
        by_term = seed_term_counts(trips, terms)
        by_portion = {
            "+".join(portion): sum(1 for trip in trips if matching_portion_indexes(trip, [portion]))
            for portion in portions
        }
        station_touch_counts = {
            station_name: sum(1 for trip in matching_trips if stop_index_at_station(station_groups, trip, station_name) is not None)
            for station_name in station_names
        }
        pair_samples: list[dict[str, Any]] = []
        pair_count = 0
        for station_name in station_names:
            station_trips = [
                (trip, stop_index_at_station(station_groups, trip, station_name))
                for trip in matching_trips
            ]
            station_trips = [(trip, index) for trip, index in station_trips if index is not None]
            for left_index, (left, left_stop_index) in enumerate(station_trips):
                left_label = service_label(left)
                left_stop = left["stopTimes"][left_stop_index]
                left_time = stop_time_sec(left_stop, "arrival") or stop_time_sec(left_stop, "departure")
                left_terms = matching_portion_indexes(left, portions)
                for right, right_stop_index in station_trips[left_index + 1:]:
                    right_terms = matching_portion_indexes(right, portions)
                    if not left_terms or not right_terms or left_terms == right_terms:
                        continue
                    right_stop = right["stopTimes"][right_stop_index]
                    right_time = stop_time_sec(right_stop, "arrival") or stop_time_sec(right_stop, "departure")
                    if left_time is None or right_time is None or abs(left_time - right_time) > max_gap_sec:
                        continue
                    pair_count += 1
                    left_origin, left_destination = trip_terminal_names(station_groups, left)
                    right_origin, right_destination = trip_terminal_names(station_groups, right)
                    add_sample(
                        pair_samples,
                        {
                            "station": station_name,
                            "timeLeft": seconds_to_hhmm(left_time),
                            "timeRight": seconds_to_hhmm(right_time),
                            "left": {
                                "id": left.get("id"),
                                "service": left_label,
                                "number": left.get("serviceNumber"),
                                "route": route_name_at_stop(routes, left, left_stop),
                                "origin": left_origin,
                                "destination": left_destination,
                            },
                            "right": {
                                "id": right.get("id"),
                                "service": service_label(right),
                                "number": right.get("serviceNumber"),
                                "route": route_name_at_stop(routes, right, right_stop),
                                "origin": right_origin,
                                "destination": right_destination,
                            },
                        },
                    )
        missing_portions = [portion for portion, count in by_portion.items() if count == 0]
        if missing_portions:
            status = "missing_service_portions"
        elif pair_count:
            status = "pair_evidence_found"
        elif len(portions) >= 2 and len({tuple(portion) for portion in portions}) == 1:
            status = "single_named_family_found_needs_portion_model"
        elif len(portions) >= 2 and all(set(portion) & set(portions[0]) for portion in portions[1:]):
            status = "single_named_family_found_needs_portion_model"
        elif len(portions) == 1 and matching_trips:
            status = "single_named_family_found_needs_portion_model"
        elif any(station_touch_counts.values()):
            status = "service_terms_found_no_pair"
        else:
            status = "service_terms_found_no_split_station_touch"
        findings.append(
            {
                "id": seed["id"],
                "label": seed["label"],
                "system": seed.get("system"),
                "confidence": seed["confidence"],
                "splitJoinStations": station_names,
                "expectedSharedSegment": seed["expectedSharedSegment"],
                "status": status,
                "termCounts": by_term,
                "portionCounts": by_portion,
                "matchingTripCount": len(matching_trips),
                "stationTouchCounts": station_touch_counts,
                "branchSignatures": branch_signatures_at_seed_station(
                    station_groups,
                    routes,
                    matching_trips,
                    station_names,
                ),
                "pairedNearTimeEventCount": pair_count,
                "samples": pair_samples,
                **SEED_DIAGNOSES.get(seed["id"], {}),
            }
        )
    return findings


def candidate_number_score(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_number = normalized_number(left.get("serviceNumber"))
    right_number = normalized_number(right.get("serviceNumber"))
    if ":" in left_number or ":" in right_number or "_" in left_number or "_" in right_number:
        return ""
    if left_number and left_number == right_number:
        return "same_number"
    return ""


def is_named_service_candidate(label: str) -> bool:
    if not label:
        return False
    if re.fullmatch(r".*(?:線|号線|本線|ライン|系統)$", label):
        return False
    if re.fullmatch(r"(?:普通|各停|準急|急行|快速|特急|全車特別車|全車一般車).+行き", label):
        return False
    if re.fullmatch(r"[A-Z0-9_:-]+", label):
        return False
    return True


def audit_generic_candidates(
    station_groups: dict[str, dict[str, Any]],
    routes: dict[str, dict[str, Any]],
    trips: list[dict[str, Any]],
    *,
    max_gap_sec: int,
) -> list[dict[str, Any]]:
    events_by_station: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trip in trips:
        stops = trip.get("stopTimes") or []
        if len(stops) < 2:
            continue
        label = service_label(trip)
        if not is_named_service_candidate(label):
            continue
        for index, stop in enumerate(stops):
            station_group_id = str(stop.get("stationGroupId") or "")
            station_name = station_title(station_groups.get(station_group_id), station_group_id)
            if not station_name:
                continue
            time_sec = stop_time_sec(stop, "arrival") or stop_time_sec(stop, "departure")
            if time_sec is None:
                continue
            previous_name, next_name = neighbor_names_at_index(station_groups, trip, index)
            origin, destination = trip_terminal_names(station_groups, trip)
            events_by_station[station_name].append(
                {
                    "trip": trip,
                    "stop": stop,
                    "timeSec": time_sec,
                    "service": label,
                    "route": route_name_at_stop(routes, trip, stop),
                    "previous": previous_name,
                    "next": next_name,
                    "origin": origin,
                    "destination": destination,
                }
            )

    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for station_name, events in events_by_station.items():
        if len(events) < 2:
            continue
        events.sort(key=lambda item: item["timeSec"])
        for left_index, left in enumerate(events):
            for right in events[left_index + 1:]:
                gap = right["timeSec"] - left["timeSec"]
                if gap > max_gap_sec:
                    break
                if left["trip"]["id"] == right["trip"]["id"]:
                    continue
                if left["service"] == right["service"]:
                    continue
                if left["origin"] == right["origin"] and left["destination"] == right["destination"]:
                    continue
                shared_previous = left["previous"] and left["previous"] == right["previous"]
                shared_next = left["next"] and left["next"] == right["next"]
                diverges_after = shared_previous and left["next"] and right["next"] and left["next"] != right["next"]
                converges_before = shared_next and left["previous"] and right["previous"] and left["previous"] != right["previous"]
                number_score = candidate_number_score(left["trip"], right["trip"])
                if not number_score:
                    continue
                if not (diverges_after or converges_before):
                    continue
                confidence = "high" if (number_score and (diverges_after or converges_before)) else "medium"
                services = tuple(sorted([left["service"], right["service"]]))
                routes_pair = tuple(sorted([left["route"], right["route"]]))
                key = (station_name, services[0], services[1], "|".join(routes_pair))
                entry = grouped.setdefault(
                    key,
                    {
                        "station": station_name,
                        "services": list(services),
                        "routes": list(routes_pair),
                        "confidence": "needs_review",
                        "eventCount": 0,
                        "evidenceCounts": Counter(),
                        "samples": [],
                    },
                )
                entry["eventCount"] += 1
                if diverges_after:
                    entry["evidenceCounts"]["same_previous_diverges_after"] += 1
                if converges_before:
                    entry["evidenceCounts"]["different_previous_converges_after"] += 1
                if number_score:
                    entry["evidenceCounts"][number_score] += 1
                add_sample(
                    entry["samples"],
                    {
                        "timeLeft": seconds_to_hhmm(left["timeSec"]),
                        "timeRight": seconds_to_hhmm(right["timeSec"]),
                        "gapSec": gap,
                        "left": {
                            "id": left["trip"].get("id"),
                            "service": left["service"],
                            "number": left["trip"].get("serviceNumber"),
                            "route": left["route"],
                            "origin": left["origin"],
                            "destination": left["destination"],
                            "previous": left["previous"],
                            "next": left["next"],
                        },
                        "right": {
                            "id": right["trip"].get("id"),
                            "service": right["service"],
                            "number": right["trip"].get("serviceNumber"),
                            "route": right["route"],
                            "origin": right["origin"],
                            "destination": right["destination"],
                            "previous": right["previous"],
                            "next": right["next"],
                        },
                    },
                )

    candidates = []
    for entry in grouped.values():
        entry["evidenceCounts"] = dict(entry["evidenceCounts"])
        if entry["eventCount"] >= 3 and entry["evidenceCounts"].get("same_number", 0) >= 3:
            entry["confidence"] = "high"
        candidates.append(entry)
    candidates.sort(key=lambda item: (item["confidence"] != "high", -item["eventCount"], item["station"], item["services"]))
    return candidates[:200]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit v4 coupled split/join train service candidates.")
    parser.add_argument("--map-bundle", type=Path, default=DEFAULT_MAP_BUNDLE)
    parser.add_argument("--timetable", type=Path, default=DEFAULT_TIMETABLE)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-gap-sec", type=int, default=DEFAULT_MAX_GAP_SEC)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    map_bundle = load_json(args.map_bundle)
    timetable = load_json(args.timetable)
    registry = load_json(args.registry)
    routes = {route["id"]: route for route in map_bundle.get("serviceRoutes", [])}
    station_groups = {group["id"]: group for group in map_bundle.get("stationGroups", [])}
    trips = decode_compact_timetable(timetable)
    seeds = registry_entries_to_seeds(registry) or KNOWN_COUPLED_SERVICE_SEEDS

    known_seed_findings = audit_known_seeds(station_groups, routes, trips, seeds, max_gap_sec=args.max_gap_sec)
    generic_candidates = audit_generic_candidates(station_groups, routes, trips, max_gap_sec=args.max_gap_sec)
    audit = {
        "schema": "onichase.v4.coupled_service_audit.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "inputs": {
            "mapBundle": rel(args.map_bundle),
            "timetable": rel(args.timetable),
            "registry": rel(args.registry),
            "maxGapSec": args.max_gap_sec,
        },
        "policy": registry.get("policy", {}),
        "methodology": {
            "knownSeeds": "Check known Japanese split/join coupled-service families from reviewed research notes.",
            "genericScan": [
                "Index all timetable stops by station group and stop time.",
                "Pair different service labels at the same station within maxGapSec.",
                "Keep candidates when they share the previous station and diverge after, converge to the same next station from different previous stations, or have matching train-number evidence.",
            ],
            "limitation": "This audit finds candidates and gaps; it does not yet create coupledServiceGroups for gameplay.",
        },
        "counts": {
            "tripCount": len(trips),
            "knownSeedCount": len(known_seed_findings),
            "knownSeedsWithPairEvidence": sum(1 for item in known_seed_findings if item["status"] == "pair_evidence_found"),
            "knownSeedsMissingServicePortions": sum(1 for item in known_seed_findings if item["status"] == "missing_service_portions"),
            "genericCandidateCount": len(generic_candidates),
            "genericHighConfidenceCandidateCount": sum(1 for item in generic_candidates if item["confidence"] == "high"),
        },
        "knownSeedFindings": known_seed_findings,
        "genericCandidates": generic_candidates,
    }
    write_json(args.output, audit)
    print(
        f"Wrote {rel(args.output)}: "
        f"known={audit['counts']['knownSeedCount']} "
        f"known_pair={audit['counts']['knownSeedsWithPairEvidence']} "
        f"known_missing={audit['counts']['knownSeedsMissingServicePortions']} "
        f"generic={audit['counts']['genericCandidateCount']} "
        f"high={audit['counts']['genericHighConfidenceCandidateCount']}"
    )


if __name__ == "__main__":
    main()
