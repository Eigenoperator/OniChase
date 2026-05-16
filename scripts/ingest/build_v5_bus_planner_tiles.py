#!/usr/bin/env python3
"""Build tiled V5 bus gameplay data from the real GTFS bus bundle."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUS_BUNDLE = ROOT / "data" / "v5_bus_gtfs_current_bundle.json.gz"
DEFAULT_TILE_DIR = ROOT / "data" / "v5_bus_planner_tiles"
DEFAULT_DOCS_TILE_DIR = ROOT / "docs" / "data" / "v5_bus_planner_tiles"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_bus_planner_tiles_audit.json"
DEFAULT_DOCS_AUDIT_OUTPUT = ROOT / "docs" / "data" / "v5_bus_planner_tiles_audit.json"
DEFAULT_TILE_SIZE_DEGREES = 0.25
DEFAULT_SERVICE_DATE = "20260516"

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def read_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_service_date(value: str) -> date:
    return date(int(value[:4]), int(value[4:6]), int(value[6:8]))


def tile_key_for_lon_lat(lon: float, lat: float, tile_size_degrees: float) -> str:
    ix = math.floor(lon / tile_size_degrees)
    iy = math.floor(lat / tile_size_degrees)
    return f"z0_x{ix}_y{iy}"


def minutes_from_seconds(value: Any) -> int | None:
    if not isinstance(value, (int, float)):
        return None
    return int(value) // 60


def route_label(route: dict[str, Any]) -> str:
    return (
        route.get("routeLongName")
        or route.get("routeShortName")
        or route.get("routeDesc")
        or route.get("sourceRouteId")
        or route.get("busRouteId")
        or "Bus route"
    )


def compact_stop(stop: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": stop["busStopId"],
        "name": stop.get("name") or stop["busStopId"],
        "lat": stop.get("lat"),
        "lon": stop.get("lon"),
    }


def compact_route(route: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": route["busRouteId"],
        "name": route_label(route),
        "shortName": route.get("routeShortName") or "",
        "longName": route.get("routeLongName") or "",
        "agencyName": route.get("agencyName") or "",
        "serviceClass": route.get("serviceClass") or "bus_local",
        "color": f"#{route.get('routeColor')}" if route.get("routeColor") and not str(route.get("routeColor")).startswith("#") else (route.get("routeColor") or ""),
    }


def build_service_active_set(bundle: dict[str, Any], service_date: str) -> tuple[set[str], dict[str, Any]]:
    target = parse_service_date(service_date)
    day_key = DAYS[target.weekday()]
    calendar_rows: dict[str, dict[str, Any]] = {}
    added_by_exception: set[str] = set()
    removed_by_exception: set[str] = set()
    row_counts = Counter()
    for row in bundle.get("calendars") or []:
        service_id = row.get("busServiceCalendarId")
        if not service_id:
            continue
        row_kind = row.get("rowKind") or "calendar"
        row_counts[row_kind] += 1
        if row_kind == "calendar":
            calendar_rows[service_id] = row
            continue
        if row_kind == "calendar_date" and str(row.get("date") or "") == service_date:
            if int(row.get("exceptionType") or 0) == 1:
                added_by_exception.add(service_id)
            elif int(row.get("exceptionType") or 0) == 2:
                removed_by_exception.add(service_id)

    active: set[str] = set()
    for service_id, row in calendar_rows.items():
        start = str(row.get("startDate") or "")
        end = str(row.get("endDate") or "")
        in_range = (not start or start <= service_date) and (not end or service_date <= end)
        if in_range and int(row.get(day_key) or 0) == 1:
            active.add(service_id)
    active.update(added_by_exception)
    active.difference_update(removed_by_exception)
    return active, {
        "serviceDate": service_date,
        "weekday": day_key,
        "calendarRowCounts": dict(sorted(row_counts.items())),
        "calendarServices": len(calendar_rows),
        "exceptionAdds": len(added_by_exception),
        "exceptionRemoves": len(removed_by_exception),
        "activeServices": len(active),
    }


def build_route_fares(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fares = {fare.get("busFareId"): fare for fare in bundle.get("fareAttributes") or [] if fare.get("busFareId")}
    prices_by_route: dict[str, list[float]] = defaultdict(list)
    for rule in bundle.get("fareRules") or []:
        route_id = rule.get("busRouteId")
        fare = fares.get(rule.get("busFareId"))
        price = fare.get("price") if fare else None
        currency = fare.get("currencyType") if fare else None
        if route_id and isinstance(price, (int, float)) and (currency in (None, "", "JPY")):
            prices_by_route[route_id].append(float(price))
    result: dict[str, dict[str, Any]] = {}
    for route_id, prices in prices_by_route.items():
        unique = sorted(set(int(round(price)) for price in prices))
        if not unique:
            continue
        if len(unique) == 1:
            result[route_id] = {"fareKnown": True, "fareYen": unique[0], "fareType": "flat"}
        else:
            result[route_id] = {"fareKnown": True, "fareYen": max(unique), "fareType": "route_max", "fareRangeYen": [min(unique), max(unique)]}
    return result


def build_tiles(bundle: dict[str, Any], *, tile_size_degrees: float, service_date: str) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    active_services, service_audit = build_service_active_set(bundle, service_date)
    stops_by_id = {stop["busStopId"]: stop for stop in bundle.get("stops") or [] if stop.get("busStopId")}
    routes_by_id = {route["busRouteId"]: route for route in bundle.get("routes") or [] if route.get("busRouteId")}
    trips_all = [trip for trip in bundle.get("trips") or [] if trip.get("busTripId") and trip.get("busRouteId")]
    if active_services:
        trips = [trip for trip in trips_all if trip.get("busServiceCalendarId") in active_services]
    else:
        trips = trips_all
    active_trip_ids = {trip["busTripId"] for trip in trips}
    trip_route = {trip["busTripId"]: trip.get("busRouteId") for trip in trips}
    trip_headsign = {trip["busTripId"]: trip.get("tripHeadsign") or "" for trip in trips}
    route_fares = build_route_fares(bundle)

    stop_tiles: dict[str, str] = {}
    tile_payloads: dict[str, dict[str, Any]] = {}
    for stop_id, stop in stops_by_id.items():
        lat = stop.get("lat")
        lon = stop.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        key = tile_key_for_lon_lat(float(lon), float(lat), tile_size_degrees)
        stop_tiles[stop_id] = key
        tile_payloads.setdefault(key, {"stops": {}, "routes": {}, "trips": {}, "departuresByStop": defaultdict(list), "connectors": []})
        tile_payloads[key]["stops"][stop_id] = compact_stop(stop)

    stop_times_by_trip: dict[str, list[dict[str, Any]]] = defaultdict(list)
    departures_by_tile_stop: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    stop_time_count = 0
    for stop_time in bundle.get("stopTimes") or []:
        trip_id = stop_time.get("busTripId")
        stop_id = stop_time.get("busStopId")
        if trip_id not in active_trip_ids or stop_id not in stop_tiles:
            continue
        dep = minutes_from_seconds(stop_time.get("departureTimeSec"))
        arr = minutes_from_seconds(stop_time.get("arrivalTimeSec"))
        seq = int(stop_time.get("stopSequence") or 0)
        compact = {
            "stopId": stop_id,
            "seq": seq,
            "arr": arr if arr is not None else dep,
            "dep": dep if dep is not None else arr,
        }
        stop_times_by_trip[trip_id].append(compact)
        route_id = trip_route.get(trip_id)
        if route_id and (dep is not None or arr is not None):
            tile_key = stop_tiles[stop_id]
            departures_by_tile_stop[(tile_key, stop_id)].append({
                "tripId": trip_id,
                "routeId": route_id,
                "stopSequence": seq,
                "departureMinute": dep if dep is not None else arr,
                "arrivalMinute": arr if arr is not None else dep,
                "headsign": stop_time.get("stopHeadsign") or trip_headsign.get(trip_id) or "",
            })
        stop_time_count += 1

    for trip_id, stop_times in stop_times_by_trip.items():
        stop_times.sort(key=lambda item: item.get("seq") or 0)

    for (key, stop_id), rows in departures_by_tile_stop.items():
        rows.sort(key=lambda item: (item.get("departureMinute") if item.get("departureMinute") is not None else 10**9, item.get("routeId") or "", item.get("tripId") or ""))
        tile_payloads[key]["departuresByStop"][stop_id].extend(rows)
        for row in rows:
            trip_id = row["tripId"]
            route_id = row["routeId"]
            route = routes_by_id.get(route_id)
            if route:
                tile_payloads[key]["routes"][route_id] = compact_route(route)
                if route_id in route_fares:
                    tile_payloads[key]["routes"][route_id]["fare"] = route_fares[route_id]
            if trip_id not in tile_payloads[key]["trips"]:
                compact_stops: list[dict[str, Any]] = []
                for item in stop_times_by_trip.get(trip_id, []):
                    stop = stops_by_id.get(item["stopId"])
                    if not stop:
                        continue
                    compact_stops.append({
                        "stopId": item["stopId"],
                        "name": stop.get("name") or item["stopId"],
                        "lat": stop.get("lat"),
                        "lon": stop.get("lon"),
                        "seq": item["seq"],
                        "arr": item["arr"],
                        "dep": item["dep"],
                    })
                minutes = [item.get("arr") for item in compact_stops if item.get("arr") is not None] + [item.get("dep") for item in compact_stops if item.get("dep") is not None]
                tile_payloads[key]["trips"][trip_id] = {
                    "id": trip_id,
                    "routeId": route_id,
                    "headsign": trip_headsign.get(trip_id) or "",
                    "serviceClass": (route or {}).get("serviceClass") or "bus_local",
                    "stops": compact_stops,
                    "firstMinute": min(minutes) if minutes else None,
                    "lastMinute": max(minutes) if minutes else None,
                }

    connector_count = 0
    for connector in bundle.get("walkingConnectors") or []:
        stop_id = connector.get("fromNodeId")
        key = stop_tiles.get(stop_id or "")
        if not key:
            continue
        tile_payloads[key]["connectors"].append({
            "fromStopId": stop_id,
            "fromName": connector.get("fromName") or "",
            "toNodeId": connector.get("toNodeId") or "",
            "toMode": connector.get("toMode") or "",
            "toName": connector.get("toName") or "",
            "distanceMeters": connector.get("distanceMeters"),
            "source": connector.get("source") or "",
        })
        connector_count += 1

    manifest_tiles: dict[str, Any] = {}
    for key in sorted(tile_payloads):
        payload = tile_payloads[key]
        departures_by_stop = {stop_id: rows for stop_id, rows in payload["departuresByStop"].items()}
        compact_payload = {
            "schemaVersion": "v5_bus_planner_tile_v1",
            "generatedAt": generated_at,
            "tileKey": key,
            "serviceDate": service_date,
            "stops": list(payload["stops"].values()),
            "routes": list(payload["routes"].values()),
            "trips": list(payload["trips"].values()),
            "departuresByStop": departures_by_stop,
            "connectors": payload["connectors"],
        }
        payload["compact"] = compact_payload
        class_counts = Counter(route.get("serviceClass") or "bus_local" for route in payload["routes"].values())
        manifest_tiles[key] = {
            "url": f"./data/v5_bus_planner_tiles/{key}.json.gz",
            "stopCount": len(payload["stops"]),
            "routeCount": len(payload["routes"]),
            "tripCount": len(payload["trips"]),
            "departureCount": sum(len(rows) for rows in departures_by_stop.values()),
            "connectorCount": len(payload["connectors"]),
            "serviceClassCounts": dict(sorted(class_counts.items())),
        }

    manifest = {
        "schemaVersion": "v5_bus_planner_tile_manifest_v1",
        "generatedAt": generated_at,
        "tileSizeDegrees": tile_size_degrees,
        "serviceDate": service_date,
        "sourceBundle": str(DEFAULT_BUS_BUNDLE.relative_to(ROOT)),
        "tileCount": len(manifest_tiles),
        "tiles": manifest_tiles,
    }
    audit = {
        "schemaVersion": "v5_bus_planner_tiles_audit_v1",
        "generatedAt": generated_at,
        "service": service_audit,
        "summary": {
            "sourceStops": len(stops_by_id),
            "sourceRoutes": len(routes_by_id),
            "sourceTrips": len(trips_all),
            "activeTrips": len(trips),
            "indexedStopTimes": stop_time_count,
            "connectorCount": connector_count,
            "tileCount": len(manifest_tiles),
            "routeFareCount": len(route_fares),
        },
        "largestTiles": sorted(
            (
                {"tileKey": key, **{k: v for k, v in meta.items() if k != "url"}}
                for key, meta in manifest_tiles.items()
            ),
            key=lambda item: item["departureCount"],
            reverse=True,
        )[:20],
    }
    return {"manifest": manifest, "tiles": tile_payloads}, audit


def write_tiles(tile_dir: Path, tile_result: dict[str, Any]) -> None:
    if tile_dir.exists():
        shutil.rmtree(tile_dir)
    tile_dir.mkdir(parents=True, exist_ok=True)
    for key, payload in tile_result["tiles"].items():
        write_json(tile_dir / f"{key}.json.gz", payload["compact"])
    write_json(tile_dir / "manifest.json", tile_result["manifest"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bus-bundle", type=Path, default=DEFAULT_BUS_BUNDLE)
    parser.add_argument("--tile-dir", type=Path, default=DEFAULT_TILE_DIR)
    parser.add_argument("--docs-tile-dir", type=Path, default=DEFAULT_DOCS_TILE_DIR)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--docs-audit-output", type=Path, default=DEFAULT_DOCS_AUDIT_OUTPUT)
    parser.add_argument("--tile-size-degrees", type=float, default=DEFAULT_TILE_SIZE_DEGREES)
    parser.add_argument("--service-date", default=DEFAULT_SERVICE_DATE)
    args = parser.parse_args()

    bundle = read_json(args.bus_bundle)
    tile_result, audit = build_tiles(bundle, tile_size_degrees=args.tile_size_degrees, service_date=args.service_date)
    write_tiles(args.tile_dir, tile_result)
    write_tiles(args.docs_tile_dir, tile_result)
    write_json(args.audit_output, audit)
    write_json(args.docs_audit_output, audit)
    print(json.dumps(audit["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
