#!/usr/bin/env python3
"""Build the V5 playable ship timetable bundle.

Only promotes routes that already have explicit official trip times and a
known adult passenger fare. Map-visible-only MLIT discoveries remain visible
on the Ship Map but are intentionally excluded from gameplay until their
precise timetable/fare/connector data is collected.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILES = [
    ROOT / "data/v5_ship_seikan_ferry_official.json",
    ROOT / "data/v5_ship_priority_batch_official.json",
    ROOT / "data/v5_ship_long_distance_batch_official.json",
    ROOT / "data/v5_ship_expansion_to_70_official.json",
    ROOT / "data/v5_ship_expansion_150_map_batch1_official.json",
    ROOT / "data/v5_ship_map_to_193_official.json",
    ROOT / "data/v5_ship_playable_400_batch_official.json",
    ROOT / "data/v5_ship_playable_500_batch_official.json",
    ROOT / "data/v5_ship_playable_omishima_batch_official.json",
    ROOT / "data/v5_ship_playable_sanyo_batch_official.json",
    ROOT / "data/v5_ship_playable_kume_batch_official.json",
    ROOT / "data/v5_ship_playable_sakura_kaiun_batch_official.json",
    ROOT / "data/v5_ship_playable_sanwa_batch_official.json",
    ROOT / "data/v5_ship_playable_kiguchi_batch_official.json",
    ROOT / "data/v5_ship_playable_local_ferries_batch_official.json",
    ROOT / "data/v5_ship_playable_short_ferries_batch_official.json",
    ROOT / "data/v5_ship_playable_geiyo_batch_official.json",
    ROOT / "data/v5_ship_playable_shikoku_kisen_batch_official.json",
    ROOT / "data/v5_ship_playable_municipal_short_batch_official.json",
    ROOT / "data/v5_ship_playable_tarumi_batch_official.json",
    ROOT / "data/v5_ship_playable_shikoku_ferry_batch_official.json",
    ROOT / "data/v5_ship_playable_tsugaru_batch_official.json",
    ROOT / "data/v5_ship_playable_heartland_batch_official.json",
    ROOT / "data/v5_ship_playable_haboro_batch_official.json",
    ROOT / "data/v5_ship_playable_kerama_batch_official.json",
    ROOT / "data/v5_ship_playable_silver_ferry_batch_official.json",
    ROOT / "data/v5_ship_playable_shinshin_batch_official.json",
    ROOT / "data/v5_ship_playable_oki_kisen_batch_official.json",
    ROOT / "data/v5_ship_playable_verified_short_batch_official.json",
    ROOT / "data/v5_ship_playable_kyodo_ferry_batch_official.json",
    ROOT / "data/v5_ship_playable_tsuyoshi_batch_official.json",
    ROOT / "data/v5_ship_playable_tencho_batch_official.json",
    ROOT / "data/v5_ship_playable_shima_marine_batch_official.json",
    ROOT / "data/v5_ship_playable_public_batch2_official.json",
    ROOT / "data/v5_ship_playable_ieshima_liner_batch_official.json",
    ROOT / "data/v5_ship_playable_sakito_batch_official.json",
    ROOT / "data/v5_ship_playable_saikai_engan_batch_official.json",
    ROOT / "data/v5_ship_playable_orange_jumbo_batch_official.json",
    ROOT / "data/v5_ship_playable_teshima_ferry_batch_official.json",
    ROOT / "data/v5_ship_playable_suo_oshima_batch_official.json",
    ROOT / "data/v5_ship_playable_orita_yakushima_batch_official.json",
    ROOT / "data/v5_ship_playable_tane_yaku_jetfoil_batch_official.json",
]
SHIP_MAP_PATH = ROOT / "docs/data/v5_ship_map.geojson"
OUT_PATH = ROOT / "docs/data/v5_ship_timetable_current_bundle.json"
AUDIT_OUT_PATH = ROOT / "data/v5_ship_playable_promotion_audit.json"

PORT_ALIASES = {
    "関西空港": "関西空港ポートターミナル",
    "桜島": "桜島港",
    "高松": "高松港",
    "土庄": "土庄港",
    "岡山": "岡山港",
    "宇野": "宇野港",
    "博多": "博多港",
    "三津浜": "三津浜港",
    "広島": "広島港宇品",
    "丸亀": "丸亀港",
    "多比良": "多比良港",
    "長洲": "長洲港",
}

OPERATOR_ALIASES = {
    "こうべ未来都市機構": "神戸-関空ベイ・シャトル",
    "鹿児島市船舶局（桜島フェリー）": "鹿児島市船舶局",
    "有明海自動車航送船組合（有明フェリー）": "有明フェリー",
}


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def route_group_key(route: dict) -> str:
    return route.get("routeGroupId") or route.get("routeId") or f"{route.get('origin')}->{route.get('destination')}"


def adult_fare_yen(route: dict) -> int | None:
    fare = route.get("fare") or {}
    adult = fare.get("adultPassengerFare") or {}
    for key in ("amount", "normalSeason", "peakSeason"):
        value = adult.get(key)
        if isinstance(value, dict):
            value = value.get("amount")
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
    for key in ("fareAdultJpy", "fareNormalAdultJpy", "farePeakAdultJpy"):
        value = route.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
    return None


def normalized_text(value: object) -> str:
    text = str(value or "")
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", "", text)
    return text


def normalize_operator(value: object) -> str:
    text = normalized_text(value)
    return OPERATOR_ALIASES.get(text, text)


def normalize_port(value: object) -> str:
    text = normalized_text(value)
    text = PORT_ALIASES.get(text, text)
    if text and not text.endswith(("港", "ターミナル", "桟橋", "島", "駅")):
        text = PORT_ALIASES.get(f"{text}港", text)
    return text


def route_coverage_keys(route: dict) -> set[tuple[str, str, str] | tuple[str, str]]:
    origin = normalize_port(route.get("origin") or route.get("originPort"))
    destination = normalize_port(route.get("destination") or route.get("destinationPort"))
    operator = normalize_operator(route.get("operator"))
    keys: set[tuple[str, str, str] | tuple[str, str]] = set()
    if origin and destination:
        keys.add((origin, destination))
        if operator:
            keys.add((operator, origin, destination))
    return keys


def calendar_type(trip: dict) -> str:
    calendar = trip.get("calendar") or {}
    return str(calendar.get("type") or "daily")


def main() -> None:
    ship_map = read_json(SHIP_MAP_PATH)
    ports = {
        feature["properties"]["name"]: {
            "name": feature["properties"]["name"],
            "city": feature["properties"].get("city"),
            "lon": feature["geometry"]["coordinates"][0],
            "lat": feature["geometry"]["coordinates"][1],
            "coordinateStatus": feature["properties"].get("coordinateStatus"),
            "coordinateSource": feature["properties"].get("coordinateSource"),
        }
        for feature in ship_map.get("features", [])
        if feature.get("properties", {}).get("kind") == "port"
    }

    routes_by_id: dict[str, dict] = {}
    trips_by_source_route: dict[str, list[dict]] = {}
    source_route_group_ids: set[str] = set()
    source_route_ids: set[str] = set()

    for source_path in SOURCE_FILES:
        if not source_path.exists():
            continue
        payload = read_json(source_path)
        for route in payload.get("routes", []):
            route_id = route.get("routeId")
            if not route_id:
                continue
            source_route_ids.add(route_id)
            source_route_group_ids.add(route_group_key(route))
            existing = routes_by_id.get(route_id)
            if not existing or adult_fare_yen(route) is not None:
                routes_by_id[route_id] = {**route, "_sourceFile": str(source_path.relative_to(ROOT))}
        for trip in payload.get("trips", []):
            route_id = trip.get("routeId")
            if route_id:
                trips_by_source_route.setdefault(route_id, []).append(trip)

    promoted_routes = []
    sailings = []
    skipped = []
    duplicate_candidates = []
    for route_id, route in sorted(routes_by_id.items()):
        route_trips = sorted(
            trips_by_source_route.get(route_id, []),
            key=lambda row: (int(row.get("departureMinute", 99999)), str(row.get("tripId", ""))),
        )
        fare_yen = adult_fare_yen(route)
        origin = route.get("origin")
        destination = route.get("destination")
        missing = []
        if not route_trips:
            missing.append("missing_explicit_trip_times")
        if fare_yen is None:
            missing.append("missing_adult_fare")
        if origin not in ports:
            missing.append("missing_origin_port_coordinate")
        if destination not in ports:
            missing.append("missing_destination_port_coordinate")
        if missing:
            duplicate_candidates.append({
                "routeId": route_id,
                "routeGroupId": route_group_key(route),
                "operator": route.get("operator"),
                "origin": origin,
                "destination": destination,
                "missing": missing,
                "sourceFile": route.get("_sourceFile"),
                "_coverageKeys": sorted(route_coverage_keys(route), key=str),
            })
            continue

        route_group_id = route_group_key(route)
        promoted_routes.append({
            "routeId": route_id,
            "routeGroupId": route_group_id,
            "operator": route.get("operator"),
            "routeName": route.get("routeName") or f"{origin} -> {destination}",
            "originPort": origin,
            "destinationPort": destination,
            "distanceKm": route.get("distanceKm"),
            "routeClass": route.get("routeClass"),
            "revealPolicy": route.get("revealPolicy") or "no_reveal",
            "fare": {
                "currency": "JPY",
                "total_yen": fare_yen,
                "fare_known": True,
                "source": "official_adult_passenger_fare",
            },
            "sourceFile": route.get("_sourceFile"),
        })
        for trip in route_trips:
            departure_minute = int(trip.get("departureMinute"))
            arrival_minute = int(trip.get("arrivalMinute"))
            if arrival_minute < departure_minute:
                arrival_minute += 24 * 60
            sailings.append({
                "sailingId": trip.get("tripId") or f"{route_id}_{departure_minute}",
                "routeId": route_id,
                "routeGroupId": route_group_id,
                "operator": trip.get("operator") or route.get("operator"),
                "routeName": route.get("routeName") or f"{origin} -> {destination}",
                "serviceNo": trip.get("serviceNo"),
                "vessel": trip.get("vessel"),
                "originPort": origin,
                "destinationPort": destination,
                "departureMinute": departure_minute,
                "arrivalMinute": arrival_minute,
                "departureHhmm": trip.get("departure"),
                "arrivalHhmm": trip.get("arrival"),
                "durationMinutes": int(trip.get("durationMinutes") or (arrival_minute - departure_minute)),
                "calendar": calendar_type(trip),
                "fare": {
                    "currency": "JPY",
                    "total_yen": fare_yen,
                    "fare_known": True,
                    "source": "official_adult_passenger_fare",
                },
                "sourceUrl": trip.get("sourceUrl"),
            })

    promoted_route_groups = {route["routeGroupId"] for route in promoted_routes}
    promoted_keys: dict[tuple[str, str, str] | tuple[str, str], dict] = {}
    for route in promoted_routes:
        for key in route_coverage_keys(route):
            promoted_keys.setdefault(key, route)

    covered_duplicates = []
    for item in duplicate_candidates:
        matched_route = None
        for key in item.pop("_coverageKeys", []):
            key_tuple = tuple(key)
            if key_tuple in promoted_keys:
                matched_route = promoted_keys[key_tuple]
                break
        if matched_route:
            covered_duplicates.append({
                **item,
                "coveredByRouteId": matched_route["routeId"],
                "coveredByOperator": matched_route["operator"],
                "coverageReason": "same_normalized_direction_already_has_explicit_official_timetable_and_fare",
            })
        else:
            skipped.append(item)

    audit = {
        "schema": "onichase.v5.ship_playable_promotion_audit.1",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sourceFiles": [str(path.relative_to(ROOT)) for path in SOURCE_FILES if path.exists()],
        "mapRouteGroupCount": ship_map.get("metadata", {}).get("routeGroupCount"),
        "sourceRouteGroupCount": len(source_route_group_ids),
        "sourceRouteCount": len(source_route_ids),
        "promotedRouteGroupCount": len(promoted_route_groups),
        "promotedRouteCount": len(promoted_routes),
        "promotedSailingCount": len(sailings),
        "coveredDuplicateRouteCount": len(covered_duplicates),
        "coveredDuplicateRoutes": covered_duplicates,
        "skippedRouteCount": len(skipped),
        "skippedReasonCounts": {},
        "skippedRoutes": skipped,
    }
    for item in skipped:
        for reason in item["missing"]:
            audit["skippedReasonCounts"][reason] = audit["skippedReasonCounts"].get(reason, 0) + 1

    bundle = {
        "schema": "onichase.v5.ship_timetable.1",
        "generatedAt": audit["generatedAt"],
        "source": "official_ship_sources_promoted_for_gameplay",
        "promotionPolicy": "explicit_official_trip_times_and_known_adult_fare_only",
        "ports": {name: ports[name] for name in sorted({r["originPort"] for r in promoted_routes} | {r["destinationPort"] for r in promoted_routes})},
        "routes": promoted_routes,
        "sailings": sorted(sailings, key=lambda row: (row["departureMinute"], row["originPort"], row["destinationPort"], row["sailingId"])),
        "metadata": {
            "routeGroupCount": len(promoted_route_groups),
            "routeCount": len(promoted_routes),
            "sailingCount": len(sailings),
            "mapRouteGroupCount": ship_map.get("metadata", {}).get("routeGroupCount"),
        },
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    AUDIT_OUT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(bundle["metadata"], ensure_ascii=False, indent=2))
    print(json.dumps({k: audit[k] for k in ("skippedRouteCount", "skippedReasonCounts")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
