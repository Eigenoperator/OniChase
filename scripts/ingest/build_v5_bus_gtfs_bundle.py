#!/usr/bin/env python3
"""Build a V5 bus bundle from real GTFS/GTFS-JP feeds.

The first source layer is the public GTFS data repository index already used by
the rail pipeline.  This script intentionally keeps GTFS provenance and does
not invent schedules, fares, stops, or route geometry.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import re
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GTFS_INDEX = ROOT / "data" / "v4_gtfs_repository_route_index.json"
DEFAULT_MAP_BUNDLE = ROOT / "data" / "v4_gameplay_map_bundle.json.gz"
DEFAULT_AIRPORT_MAP = ROOT / "docs" / "data" / "v5_flight_map.geojson"
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_gtfs_cache"
DEFAULT_OUTPUT = ROOT / "data" / "v5_bus_gtfs_current_bundle.json.gz"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_bus_gtfs_audit.json"
EARTH_RADIUS_METERS = 6_371_008.8
BUS_ROUTE_TYPES = {3}
AIRPORT_TEXT_RE = re.compile(r"空港|airport|リムジン|limousine", re.IGNORECASE)
LONG_DISTANCE_TEXT_RE = re.compile(r"高速|夜行|深夜|長距離|express|highway|night", re.IGNORECASE)


def read_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stable_slug(*parts: object) -> str:
    text = ":".join(str(part or "") for part in parts)
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_").lower()
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{cleaned[:70] or 'feed'}_{digest}"


def prefixed(feed_key: str, raw_id: str | None, namespace: str) -> str:
    raw = str(raw_id or "").strip() or "blank"
    return f"bus:{namespace}:{feed_key}:{raw}"


def parse_time_seconds(value: str | None) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError:
        return None
    return hours * 3600 + minutes * 60 + seconds


def parse_float(value: str | None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: str | None) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def csv_rows(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    try:
        with archive.open(name) as member:
            text = io.TextIOWrapper(member, encoding="utf-8-sig")
            return list(csv.DictReader(text))
    except KeyError:
        return []


def fetch_feed_zip(feed: dict[str, Any], cache_dir: Path, *, refresh: bool, timeout: int) -> bytes:
    feed_key = feed["feedKey"]
    cache_path = cache_dir / f"{feed_key}.zip"
    if cache_path.exists() and not refresh:
        return cache_path.read_bytes()
    url = feed.get("fileUrl")
    if not url:
        raise ValueError("missing fileUrl")
    request = urllib.request.Request(
        str(url),
        headers={
            "Accept": "application/zip,*/*",
            "User-Agent": "OniChase-v5-bus-gtfs-ingest/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(raw)
    return raw


def feed_source_ref(feed: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceKind": "gtfs_jp_repository",
        "organizationId": feed.get("organizationId"),
        "organizationName": feed.get("organizationName"),
        "feedId": feed.get("feedId"),
        "feedName": feed.get("feedName"),
        "feedPrefId": feed.get("feedPrefId"),
        "feedPageUrl": feed.get("feedPageUrl"),
        "fileUrl": feed.get("fileUrl"),
        "fileFromDate": feed.get("fileFromDate"),
        "fileToDate": feed.get("fileToDate"),
        "fileLastUpdatedAt": feed.get("fileLastUpdatedAt"),
        "licenseId": feed.get("licenseId"),
    }


def classify_bus_route(feed: dict[str, Any], agency_name: str, route: dict[str, Any], stop_names: list[str]) -> str:
    text = " ".join(
        [
            str(feed.get("organizationName") or ""),
            str(feed.get("feedName") or ""),
            agency_name,
            str(route.get("shortName") or ""),
            str(route.get("longName") or ""),
            str(route.get("routeDesc") or ""),
            " ".join(stop_names[:80]),
        ]
    )
    if AIRPORT_TEXT_RE.search(text):
        return "bus_airport"
    if LONG_DISTANCE_TEXT_RE.search(text):
        return "bus_long_distance"
    return "bus_local"


def compact_agencies(feed_key: str, rows: list[dict[str, str]], source_ref: dict[str, Any]) -> list[dict[str, Any]]:
    agencies = []
    for row in rows:
        agency_id = row.get("agency_id") or row.get("agency_name") or "default"
        agencies.append(
            {
                "busAgencyId": prefixed(feed_key, agency_id, "agency"),
                "sourceAgencyId": agency_id,
                "agencyName": row.get("agency_name") or "",
                "agencyUrl": row.get("agency_url") or "",
                "agencyTimezone": row.get("agency_timezone") or "",
                "agencyLang": row.get("agency_lang") or "",
                "sourceRefs": [source_ref],
            }
        )
    return agencies


def compact_stops(feed_key: str, rows: list[dict[str, str]], source_ref: dict[str, Any]) -> list[dict[str, Any]]:
    stops = []
    for row in rows:
        stop_id = row.get("stop_id")
        lat = parse_float(row.get("stop_lat"))
        lon = parse_float(row.get("stop_lon"))
        location_type = parse_int(row.get("location_type")) or 0
        stops.append(
            {
                "busStopId": prefixed(feed_key, stop_id, "stop"),
                "sourceStopId": stop_id,
                "name": row.get("stop_name") or "",
                "lat": lat,
                "lon": lon,
                "locationType": location_type,
                "parentBusStopId": prefixed(feed_key, row.get("parent_station"), "stop") if row.get("parent_station") else None,
                "platformCode": row.get("platform_code") or "",
                "wheelchairBoarding": parse_int(row.get("wheelchair_boarding")),
                "sourceRefs": [source_ref],
            }
        )
    return stops


def compact_routes(
    feed_key: str,
    rows: list[dict[str, str]],
    agency_by_source_id: dict[str, dict[str, Any]],
    stop_names_by_route_id: dict[str, list[str]],
    feed: dict[str, Any],
    source_ref: dict[str, Any],
) -> list[dict[str, Any]]:
    routes = []
    for row in rows:
        route_type = parse_int(row.get("route_type"))
        if route_type not in BUS_ROUTE_TYPES:
            continue
        source_route_id = row.get("route_id")
        source_agency_id = row.get("agency_id") or "default"
        agency = agency_by_source_id.get(source_agency_id) or next(iter(agency_by_source_id.values()), {})
        service_class = classify_bus_route(feed, agency.get("agencyName", ""), {
            "shortName": row.get("route_short_name"),
            "longName": row.get("route_long_name"),
            "routeDesc": row.get("route_desc"),
        }, stop_names_by_route_id.get(source_route_id or "", []))
        routes.append(
            {
                "busRouteId": prefixed(feed_key, source_route_id, "route"),
                "sourceRouteId": source_route_id,
                "busAgencyId": agency.get("busAgencyId"),
                "agencyName": agency.get("agencyName", ""),
                "routeShortName": row.get("route_short_name") or "",
                "routeLongName": row.get("route_long_name") or "",
                "routeDesc": row.get("route_desc") or "",
                "routeType": route_type,
                "serviceClass": service_class,
                "routeColor": row.get("route_color") or "",
                "routeTextColor": row.get("route_text_color") or "",
                "sourceRefs": [source_ref],
            }
        )
    return routes


def compact_calendar(feed_key: str, rows: list[dict[str, str]], date_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        service_id = row.get("service_id")
        output.append(
            {
                "busServiceCalendarId": prefixed(feed_key, service_id, "calendar"),
                "rowKind": "calendar",
                "sourceServiceId": service_id,
                "monday": parse_int(row.get("monday")),
                "tuesday": parse_int(row.get("tuesday")),
                "wednesday": parse_int(row.get("wednesday")),
                "thursday": parse_int(row.get("thursday")),
                "friday": parse_int(row.get("friday")),
                "saturday": parse_int(row.get("saturday")),
                "sunday": parse_int(row.get("sunday")),
                "startDate": row.get("start_date") or "",
                "endDate": row.get("end_date") or "",
            }
        )
    for row in date_rows:
        service_id = row.get("service_id")
        output.append(
            {
                "busServiceCalendarId": prefixed(feed_key, service_id, "calendar"),
                "rowKind": "calendar_date",
                "sourceServiceId": service_id,
                "date": row.get("date") or "",
                "exceptionType": parse_int(row.get("exception_type")),
            }
        )
    return output


def compact_trips(feed_key: str, rows: list[dict[str, str]], route_class_by_source_id: dict[str, str]) -> list[dict[str, Any]]:
    trips = []
    for row in rows:
        route_id = row.get("route_id")
        trip_id = row.get("trip_id")
        trips.append(
            {
                "busTripId": prefixed(feed_key, trip_id, "trip"),
                "sourceTripId": trip_id,
                "busRouteId": prefixed(feed_key, route_id, "route"),
                "busServiceCalendarId": prefixed(feed_key, row.get("service_id"), "calendar"),
                "sourceServiceId": row.get("service_id") or "",
                "tripHeadsign": row.get("trip_headsign") or "",
                "directionId": parse_int(row.get("direction_id")),
                "blockId": row.get("block_id") or "",
                "busShapeId": prefixed(feed_key, row.get("shape_id"), "shape") if row.get("shape_id") else None,
                "wheelchairAccessible": parse_int(row.get("wheelchair_accessible")),
                "bikesAllowed": parse_int(row.get("bikes_allowed")),
                "serviceClass": route_class_by_source_id.get(route_id or "", "bus_local"),
            }
        )
    return trips


def compact_stop_times(feed_key: str, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    stop_times = []
    for row in rows:
        stop_times.append(
            {
                "busTripId": prefixed(feed_key, row.get("trip_id"), "trip"),
                "busStopId": prefixed(feed_key, row.get("stop_id"), "stop"),
                "arrivalTimeSec": parse_time_seconds(row.get("arrival_time")),
                "departureTimeSec": parse_time_seconds(row.get("departure_time")),
                "stopSequence": parse_int(row.get("stop_sequence")),
                "stopHeadsign": row.get("stop_headsign") or "",
                "pickupType": parse_int(row.get("pickup_type")),
                "dropOffType": parse_int(row.get("drop_off_type")),
                "shapeDistTraveled": parse_float(row.get("shape_dist_traveled")),
                "timepoint": parse_int(row.get("timepoint")),
            }
        )
    stop_times.sort(key=lambda item: (item["busTripId"], item["stopSequence"] if item["stopSequence"] is not None else 10**9))
    return stop_times


def compact_fares(feed_key: str, fare_rows: list[dict[str, str]], fare_rule_rows: list[dict[str, str]]) -> dict[str, Any]:
    attributes = []
    for row in fare_rows:
        attributes.append(
            {
                "busFareId": prefixed(feed_key, row.get("fare_id"), "fare"),
                "sourceFareId": row.get("fare_id") or "",
                "price": parse_float(row.get("price")),
                "currencyType": row.get("currency_type") or "",
                "paymentMethod": parse_int(row.get("payment_method")),
                "transfers": parse_int(row.get("transfers")),
                "transferDurationSec": parse_int(row.get("transfer_duration")),
            }
        )
    rules = []
    for row in fare_rule_rows:
        rules.append(
            {
                "busFareId": prefixed(feed_key, row.get("fare_id"), "fare"),
                "busRouteId": prefixed(feed_key, row.get("route_id"), "route") if row.get("route_id") else None,
                "originId": row.get("origin_id") or "",
                "destinationId": row.get("destination_id") or "",
                "containsId": row.get("contains_id") or "",
            }
        )
    return {"fareAttributes": attributes, "fareRules": rules}


def compact_shapes(feed_key: str, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_shape: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        source_shape_id = row.get("shape_id")
        if not source_shape_id:
            continue
        lat = parse_float(row.get("shape_pt_lat"))
        lon = parse_float(row.get("shape_pt_lon"))
        sequence = parse_int(row.get("shape_pt_sequence"))
        if lat is None or lon is None or sequence is None:
            continue
        by_shape[source_shape_id].append(
            {
                "lat": lat,
                "lon": lon,
                "sequence": sequence,
                "shapeDistTraveled": parse_float(row.get("shape_dist_traveled")),
            }
        )
    output = []
    for source_shape_id, points in by_shape.items():
        points.sort(key=lambda item: item["sequence"])
        output.append(
            {
                "busShapeId": prefixed(feed_key, source_shape_id, "shape"),
                "sourceShapeId": source_shape_id,
                "pointCount": len(points),
                "points": points,
            }
        )
    return output


def compact_transfers(feed_key: str, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    transfers = []
    for row in rows:
        transfers.append(
            {
                "fromBusStopId": prefixed(feed_key, row.get("from_stop_id"), "stop"),
                "toBusStopId": prefixed(feed_key, row.get("to_stop_id"), "stop"),
                "transferType": parse_int(row.get("transfer_type")),
                "minTransferTimeSec": parse_int(row.get("min_transfer_time")),
            }
        )
    return transfers


def stop_names_by_route(stop_times: list[dict[str, str]], trips: list[dict[str, str]], stops_by_id: dict[str, str]) -> dict[str, list[str]]:
    route_by_trip = {row.get("trip_id") or "": row.get("route_id") or "" for row in trips}
    names: dict[str, list[str]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for row in stop_times[:300_000]:
        route_id = route_by_trip.get(row.get("trip_id") or "")
        stop_name = stops_by_id.get(row.get("stop_id") or "")
        if not route_id or not stop_name:
            continue
        key = (route_id, stop_name)
        if key in seen:
            continue
        seen.add(key)
        names[route_id].append(stop_name)
    return names


def inspect_and_compact_feed(feed: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any] | None]:
    feed_key = feed["feedKey"]
    source_ref = feed_source_ref(feed)
    item = {
        "feedKey": feed_key,
        "organizationName": feed.get("organizationName"),
        "feedName": feed.get("feedName"),
        "fileUrl": feed.get("fileUrl"),
        "status": "pending",
    }
    try:
        raw = fetch_feed_zip(feed, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            agencies_raw = csv_rows(archive, "agency.txt")
            stops_raw = csv_rows(archive, "stops.txt")
            routes_raw = csv_rows(archive, "routes.txt")
            trips_raw = csv_rows(archive, "trips.txt")
            stop_times_raw = csv_rows(archive, "stop_times.txt")
            calendar_raw = csv_rows(archive, "calendar.txt")
            calendar_dates_raw = csv_rows(archive, "calendar_dates.txt")
            fare_attributes_raw = csv_rows(archive, "fare_attributes.txt")
            fare_rules_raw = csv_rows(archive, "fare_rules.txt")
            transfers_raw = csv_rows(archive, "transfers.txt")
            shapes_raw = [] if args.skip_shapes else csv_rows(archive, "shapes.txt")
    except (OSError, urllib.error.URLError, zipfile.BadZipFile, ValueError) as exc:
        item.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
        return item, None

    agencies = compact_agencies(feed_key, agencies_raw, source_ref)
    agency_by_source_id = {
        agency["sourceAgencyId"] or "default": agency
        for agency in agencies
    }
    if agencies and "default" not in agency_by_source_id:
        agency_by_source_id["default"] = agencies[0]

    stops_by_source_id = {row.get("stop_id") or "": row.get("stop_name") or "" for row in stops_raw}
    route_stop_names = stop_names_by_route(stop_times_raw, trips_raw, stops_by_source_id)
    stops = compact_stops(feed_key, stops_raw, source_ref)
    routes = compact_routes(feed_key, routes_raw, agency_by_source_id, route_stop_names, feed, source_ref)
    route_class_by_source_id = {route["sourceRouteId"] or "": route["serviceClass"] for route in routes}
    trips = compact_trips(feed_key, trips_raw, route_class_by_source_id)
    stop_times = compact_stop_times(feed_key, stop_times_raw)
    calendar = compact_calendar(feed_key, calendar_raw, calendar_dates_raw)
    fares = compact_fares(feed_key, fare_attributes_raw, fare_rules_raw)
    shapes = compact_shapes(feed_key, shapes_raw)
    transfers = compact_transfers(feed_key, transfers_raw)

    class_counts = Counter(route["serviceClass"] for route in routes)
    item.update(
        {
            "status": "ok",
            "agencyCount": len(agencies),
            "routeCount": len(routes),
            "stopCount": len(stops),
            "tripCount": len(trips),
            "stopTimeCount": len(stop_times),
            "calendarRowCount": len(calendar),
            "fareAttributeCount": len(fares["fareAttributes"]),
            "fareRuleCount": len(fares["fareRules"]),
            "shapeCount": len(shapes),
            "transferCount": len(transfers),
            "serviceClassCounts": dict(sorted(class_counts.items())),
        }
    )
    payload = {
        "feed": source_ref | {"feedKey": feed_key},
        "agencies": agencies,
        "stops": stops,
        "routes": routes,
        "trips": trips,
        "stopTimes": stop_times,
        "calendars": calendar,
        "fares": fares,
        "shapes": shapes,
        "transfers": transfers,
    }
    return item, payload


def haversine_meters(left: dict[str, float], right: dict[str, float]) -> float:
    lat1 = math.radians(left["lat"])
    lon1 = math.radians(left["lon"])
    lat2 = math.radians(right["lat"])
    lon2 = math.radians(right["lon"])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_METERS * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def build_grid(nodes: list[dict[str, Any]], cell_degrees: float) -> dict[tuple[int, int], list[int]]:
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, node in enumerate(nodes):
        grid[(math.floor(node["lat"] / cell_degrees), math.floor(node["lon"] / cell_degrees))].append(index)
    return grid


def nearby_nodes(
    origin: dict[str, Any],
    nodes: list[dict[str, Any]],
    grid: dict[tuple[int, int], list[int]],
    *,
    max_distance_meters: int,
    cell_degrees: float,
) -> list[dict[str, Any]]:
    lat_cell = math.floor(origin["lat"] / cell_degrees)
    lon_cell = math.floor(origin["lon"] / cell_degrees)
    radius_cells = max(1, math.ceil((max_distance_meters / 111_320) / cell_degrees) + 1)
    output = []
    for dlat in range(-radius_cells, radius_cells + 1):
        for dlon in range(-radius_cells, radius_cells + 1):
            for index in grid.get((lat_cell + dlat, lon_cell + dlon), []):
                target = nodes[index]
                distance = haversine_meters(origin, target)
                if distance <= max_distance_meters:
                    output.append(target | {"distanceMeters": int(round(distance))})
    output.sort(key=lambda item: (item["distanceMeters"], item["name"], item["id"]))
    return output


def rail_reference_nodes(map_bundle_path: Path) -> list[dict[str, Any]]:
    bundle = read_json(map_bundle_path)
    nodes = []
    for group in bundle.get("stationGroups") or []:
        centroid = group.get("centroid") or {}
        lat = centroid.get("lat")
        lon = centroid.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        nodes.append(
            {
                "id": group["id"],
                "targetMode": "rail_station_group",
                "name": group.get("primaryName") or group.get("names", {}).get("ja") or group["id"],
                "lat": float(lat),
                "lon": float(lon),
            }
        )
    return nodes


def airport_reference_nodes(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    collection = read_json(path)
    nodes = []
    for feature in collection.get("features") or []:
        if feature.get("geometry", {}).get("type") != "Point":
            continue
        coords = feature.get("geometry", {}).get("coordinates") or []
        props = feature.get("properties") or {}
        iata = props.get("iata")
        if len(coords) < 2 or not iata:
            continue
        nodes.append(
            {
                "id": f"airport:{iata}",
                "targetMode": "airport",
                "name": str(iata),
                "lat": float(coords[1]),
                "lon": float(coords[0]),
            }
        )
    return nodes


def build_connectors(
    stops: list[dict[str, Any]],
    *,
    rail_nodes: list[dict[str, Any]],
    airport_nodes: list[dict[str, Any]],
    max_distance_meters: int,
    max_rail_per_stop: int,
    max_airport_per_stop: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible_stops = [
        {
            "id": stop["busStopId"],
            "name": stop.get("name") or stop["busStopId"],
            "lat": stop["lat"],
            "lon": stop["lon"],
        }
        for stop in stops
        if isinstance(stop.get("lat"), (int, float)) and isinstance(stop.get("lon"), (int, float)) and (stop.get("locationType") in (0, None))
    ]
    rail_grid = build_grid(rail_nodes, 0.05)
    airport_grid = build_grid(airport_nodes, 0.05)
    connectors = []
    rail_connected = 0
    airport_connected = 0
    for stop in eligible_stops:
        rail_matches = nearby_nodes(stop, rail_nodes, rail_grid, max_distance_meters=max_distance_meters, cell_degrees=0.05)
        airport_matches = nearby_nodes(stop, airport_nodes, airport_grid, max_distance_meters=max_distance_meters, cell_degrees=0.05)
        if max_rail_per_stop > 0:
            rail_matches = rail_matches[:max_rail_per_stop]
        if max_airport_per_stop > 0:
            airport_matches = airport_matches[:max_airport_per_stop]
        if rail_matches:
            rail_connected += 1
        if airport_matches:
            airport_connected += 1
        for target in [*rail_matches, *airport_matches]:
            connectors.append(
                {
                    "fromNodeId": stop["id"],
                    "fromMode": "bus_stop",
                    "fromName": stop["name"],
                    "toNodeId": target["id"],
                    "toMode": target["targetMode"],
                    "toName": target["name"],
                    "distanceMeters": target["distanceMeters"],
                    "source": "generated_haversine_bus_stop_connector_v1",
                }
            )
    connector_counts = Counter(connector["toMode"] for connector in connectors)
    return connectors, {
        "eligibleBusStopCount": len(eligible_stops),
        "busStopWithRailConnectorCount": rail_connected,
        "busStopWithAirportConnectorCount": airport_connected,
        "connectorCounts": dict(sorted(connector_counts.items())),
        "maxConnectorMeters": max_distance_meters,
        "maxRailConnectorsPerStop": max_rail_per_stop,
        "maxAirportConnectorsPerStop": max_airport_per_stop,
    }


def selected_bus_feeds(index_path: Path, max_feeds: int, feed_keys: set[str]) -> list[dict[str, Any]]:
    data = read_json(index_path)
    feeds = []
    for feed in data.get("feeds") or []:
        if feed.get("status") != "ok" or not feed.get("isBusOnly"):
            continue
        feed_key = stable_slug(feed.get("organizationId"), feed.get("feedId"), feed.get("fileUrl"))
        enriched = dict(feed)
        enriched["feedKey"] = feed_key
        if feed_keys and feed_key not in feed_keys:
            continue
        feeds.append(enriched)
    feeds.sort(key=lambda item: (str(item.get("feedPrefId")), str(item.get("organizationName")), str(item.get("feedName"))))
    if max_feeds:
        feeds = feeds[:max_feeds]
    return feeds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gtfs-index", type=Path, default=DEFAULT_GTFS_INDEX)
    parser.add_argument("--map-bundle", type=Path, default=DEFAULT_MAP_BUNDLE)
    parser.add_argument("--airport-map", type=Path, default=DEFAULT_AIRPORT_MAP)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--max-feeds", type=int, default=0)
    parser.add_argument("--feed-key", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--skip-shapes", action="store_true")
    parser.add_argument("--max-connector-meters", type=int, default=2000)
    parser.add_argument("--max-rail-connectors-per-stop", type=int, default=12)
    parser.add_argument("--max-airport-connectors-per-stop", type=int, default=4)
    args = parser.parse_args()

    feeds = selected_bus_feeds(args.gtfs_index, args.max_feeds, set(args.feed_key))
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    all_agencies: list[dict[str, Any]] = []
    all_stops: list[dict[str, Any]] = []
    all_routes: list[dict[str, Any]] = []
    all_trips: list[dict[str, Any]] = []
    all_stop_times: list[dict[str, Any]] = []
    all_calendars: list[dict[str, Any]] = []
    all_shapes: list[dict[str, Any]] = []
    all_transfers: list[dict[str, Any]] = []
    all_fare_attributes: list[dict[str, Any]] = []
    all_fare_rules: list[dict[str, Any]] = []
    feed_audits: list[dict[str, Any]] = []
    source_feeds: list[dict[str, Any]] = []

    for index, feed in enumerate(feeds, start=1):
        print(f"[{index}/{len(feeds)}] {feed.get('organizationName')} / {feed.get('feedName')}", flush=True)
        audit, payload = inspect_and_compact_feed(feed, args)
        feed_audits.append(audit)
        if not payload:
            continue
        source_feeds.append(payload["feed"])
        all_agencies.extend(payload["agencies"])
        all_stops.extend(payload["stops"])
        all_routes.extend(payload["routes"])
        all_trips.extend(payload["trips"])
        all_stop_times.extend(payload["stopTimes"])
        all_calendars.extend(payload["calendars"])
        all_fare_attributes.extend(payload["fares"]["fareAttributes"])
        all_fare_rules.extend(payload["fares"]["fareRules"])
        all_shapes.extend(payload["shapes"])
        all_transfers.extend(payload["transfers"])

    rail_nodes = rail_reference_nodes(args.map_bundle)
    airport_nodes = airport_reference_nodes(args.airport_map)
    connectors, connector_summary = build_connectors(
        all_stops,
        rail_nodes=rail_nodes,
        airport_nodes=airport_nodes,
        max_distance_meters=args.max_connector_meters,
        max_rail_per_stop=args.max_rail_connectors_per_stop,
        max_airport_per_stop=args.max_airport_connectors_per_stop,
    )

    service_class_counts = Counter(route["serviceClass"] for route in all_routes)
    status_counts = Counter(item.get("status", "unknown") for item in feed_audits)
    payload = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "modelVersion": "v5_bus_gtfs_jp_bundle_v1",
        "sourceIndex": str(args.gtfs_index.relative_to(ROOT)) if args.gtfs_index.is_relative_to(ROOT) else str(args.gtfs_index),
        "rules": {
            "sourcePolicy": "Only real GTFS/GTFS-JP bus feeds are ingested. No bus timetable, fare, or stop is fabricated.",
            "sourceClass": "GTFS route_type=3 bus feeds from the public GTFS data repository index.",
            "serviceClassHeuristic": "airport text -> bus_airport; highway/night text -> bus_long_distance; otherwise bus_local. This is gameplay metadata only; source route data is unchanged.",
            "connectorPolicy": "Walking connectors are generated from coordinates and can be regenerated when rail, airport, port, or bus stop nodes change.",
            "portConnectorStatus": "Ports are reserved in the connector schema and will be added when ferry/port nodes exist.",
        },
        "summary": {
            "sourceFeedCount": len(source_feeds),
            "agencyCount": len(all_agencies),
            "stopCount": len(all_stops),
            "routeCount": len(all_routes),
            "tripCount": len(all_trips),
            "stopTimeCount": len(all_stop_times),
            "calendarRowCount": len(all_calendars),
            "shapeCount": len(all_shapes),
            "transferCount": len(all_transfers),
            "fareAttributeCount": len(all_fare_attributes),
            "fareRuleCount": len(all_fare_rules),
            "serviceClassCounts": dict(sorted(service_class_counts.items())),
            "feedStatusCounts": dict(sorted(status_counts.items())),
            "connectorSummary": connector_summary,
        },
        "sourceFeeds": source_feeds,
        "agencies": all_agencies,
        "stops": all_stops,
        "routes": all_routes,
        "trips": all_trips,
        "stopTimes": all_stop_times,
        "calendars": all_calendars,
        "fareAttributes": all_fare_attributes,
        "fareRules": all_fare_rules,
        "shapes": all_shapes,
        "transfers": all_transfers,
        "walkingConnectors": connectors,
    }
    write_json(args.output, payload)

    audit = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "modelVersion": payload["modelVersion"],
        "sourceIndex": payload["sourceIndex"],
        "selectedFeedCount": len(feeds),
        "summary": payload["summary"],
        "feedAudits": feed_audits,
        "notes": [
            "This audit verifies ingestion shape and connector generation, not every operator's service completeness.",
            "Airport and long-distance bus classes are heuristic tags; official source fields are preserved for later route-by-route audits.",
            "Dense local bus feeds can be very large. Use --max-feeds for smoke tests and no limit for release builds.",
        ],
    }
    write_json(args.audit_output, audit)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
