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


ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILES = [
    ROOT / "data/v5_ship_seikan_ferry_official.json",
    ROOT / "data/v5_ship_priority_batch_official.json",
    ROOT / "data/v5_ship_long_distance_batch_official.json",
    ROOT / "data/v5_ship_expansion_to_70_official.json",
    ROOT / "data/v5_ship_expansion_150_map_batch1_official.json",
    ROOT / "data/v5_ship_map_to_193_official.json",
]
SHIP_MAP_PATH = ROOT / "docs/data/v5_ship_map.geojson"
OUT_PATH = ROOT / "docs/data/v5_ship_timetable_current_bundle.json"
AUDIT_OUT_PATH = ROOT / "data/v5_ship_playable_promotion_audit.json"


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
            skipped.append({
                "routeId": route_id,
                "routeGroupId": route_group_key(route),
                "operator": route.get("operator"),
                "origin": origin,
                "destination": destination,
                "missing": missing,
                "sourceFile": route.get("_sourceFile"),
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
