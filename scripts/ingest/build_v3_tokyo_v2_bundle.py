#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"

MAP_PATH = DATA_DIR / "v3_tokyo_phase1_service_views.json"
UNIFIED_TRAINS_PATH = DATA_DIR / "v3_trains_unified.json.gz"
OUTPUT_PATH = DATA_DIR / "v3_tokyo_bundle.json"

SPECIAL_STATION_IDS = {
    "東京": "TOKYO",
    "新宿": "SHINJUKU",
    "渋谷": "SHIBUYA",
    "池袋": "IKEBUKURO",
    "上野": "UENO",
    "品川": "SHINAGAWA",
}


def load_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def normalize_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"[\s\-‐‑‒–—ー・･'’`]", "", text)
    return text


def stable_id(prefix: str, value: Any) -> str:
    raw = str(value or "unknown")
    special = SPECIAL_STATION_IDS.get(raw)
    if special:
        return f"{prefix}_{special}"
    cleaned = unicodedata.normalize("NFKC", raw).upper()
    cleaned = re.sub(r"[^A-Z0-9]+", "_", cleaned).strip("_")
    if cleaned:
        return f"{prefix}_{cleaned[:48]}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}_{digest}"


def route_id_for(line: Any, operator_id: str) -> str:
    base = str(line or operator_id or "unknown")
    digest = hashlib.sha1(f"{operator_id}|{base}".encode("utf-8")).hexdigest()[:8].upper()
    return f"R_{digest}"


def hhmm_to_sec(value: Any) -> int | None:
    match = re.match(r"^(\d{1,2}):(\d{2})$", str(value or ""))
    if not match:
        return None
    return (int(match.group(1)) * 60 + int(match.group(2))) * 60


def seconds_or_none(*values: Any) -> int | None:
    for value in values:
        sec = hhmm_to_sec(value)
        if sec is not None:
            return sec
    return None


def mode_for_operator(operator_id: str) -> str:
    if operator_id == "shinkansen":
        return "shinkansen"
    if operator_id in {"tokyo_metro", "toei"}:
        return "subway"
    return "private_rail" if operator_id not in {"jr_east"} else "rail"


def collect_station_coordinates(map_payload: dict[str, Any], trains: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    coords: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()

    for station in map_payload.get("visibleStations", []):
        key = normalize_key(station.get("name_ja") or station.get("name_en"))
        if not key:
            continue
        current = coords.get(key)
        candidate = {
            "station_key": key,
            "display_ja": station.get("name_ja") or station.get("name_en") or key,
            "display_en": station.get("name_en") or station.get("name_ja") or key,
            "lat": station.get("lat"),
            "lon": station.get("lon"),
            "is_priority": bool(station.get("is_priority")),
        }
        if current is None or (candidate["is_priority"] and not current.get("is_priority")):
            coords[key] = candidate

    for train in trains:
        for stop in train.get("stops", []):
            key = stop.get("station_key")
            if key:
                counts[key] += 1

    # Prefer high-traffic named points when the map has duplicate same-name physical stations.
    for key, coord in coords.items():
        coord["traffic_count"] = counts.get(key, 0)

    return coords


def build_routes(map_payload: dict[str, Any], trains: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    route_meta: dict[str, dict[str, Any]] = {}

    for line in map_payload.get("physicalLines", []):
        route_id = route_id_for(line.get("line_name_ja") or line.get("label"), normalize_key(line.get("operator_ja")))
        route_meta.setdefault(route_id, {
            "id": route_id,
            "operatorId": normalize_key(line.get("operator_ja")) or "tokyo",
            "shortName": line.get("line_name_ja") or line.get("label") or route_id,
            "longName": line.get("label") or line.get("line_name_ja") or route_id,
            "color": line.get("color") or "#1565c0",
            "textColor": "#ffffff",
            "mode": "rail" if line.get("kind") == "jr" else line.get("kind") or "rail",
        })

    for train in trains:
        line = train.get("line") or train.get("service_name") or train.get("operator")
        route_id = route_id_for(line, train.get("operator_id", "tokyo"))
        route_meta.setdefault(route_id, {
            "id": route_id,
            "operatorId": train.get("operator_id") or "tokyo",
            "shortName": str(line or train.get("operator") or route_id),
            "longName": f"{train.get('operator') or 'Tokyo'} / {line or train.get('service_name') or route_id}",
            "color": "#1565c0",
            "textColor": "#ffffff",
            "mode": mode_for_operator(train.get("operator_id", "")),
        })

    routes = sorted(route_meta.values(), key=lambda item: (item["operatorId"], item["shortName"]))
    return routes, route_meta


def build_bundle() -> dict[str, Any]:
    map_payload = load_json(MAP_PATH)
    train_payload = load_json(UNIFIED_TRAINS_PATH)
    source_trains = train_payload.get("trains", [])
    coord_map = collect_station_coordinates(map_payload, source_trains)
    service_routes, route_meta = build_routes(map_payload, source_trains)

    physical_stations = []
    station_groups = []
    label_representations = []
    game_nodes = []

    for key, coord in sorted(coord_map.items(), key=lambda item: (bool(item[1].get("is_priority")), item[1].get("traffic_count", 0), item[0])):
        if not (isinstance(coord.get("lat"), (int, float)) and isinstance(coord.get("lon"), (int, float))):
            continue
        sgid = stable_id("SG", key)
        psid = stable_id("PS", key)
        label_rank = 100 if coord.get("is_priority") else 92 if coord.get("traffic_count", 0) >= 1000 else 72
        tags = ["tokyo", "v3"]
        physical_stations.append({
            "id": psid,
            "name": coord["display_en"],
            "names": {"en": coord["display_en"], "ja": coord["display_ja"], "zh_hans": coord["display_ja"]},
            "operatorIds": [],
            "lat": coord["lat"],
            "lon": coord["lon"],
            "sourceStopIds": [key],
            "stationGroupId": sgid,
            "tags": tags,
        })
        station_groups.append({
            "id": sgid,
            "primaryName": coord["display_en"],
            "names": {"en": coord["display_en"], "ja": coord["display_ja"], "zh_hans": coord["display_ja"]},
            "physicalStationIds": [psid],
            "centroid": {"lat": coord["lat"], "lon": coord["lon"]},
            "category": "hub" if label_rank >= 100 else "normal",
            "labelRank": label_rank,
            "tags": tags,
        })
        label_representations.append({
            "stationGroupId": sgid,
            "minZoom": 3 if label_rank >= 100 else 5,
            "maxZoom": 24,
            "labelRank": label_rank,
            "displayNameJa": coord["display_ja"],
            "displayNameEn": coord["display_en"],
            "labelPoint": {"lat": coord["lat"], "lon": coord["lon"]},
        })
        game_nodes.append({
            "id": stable_id("GN", key),
            "stationGroupIds": [sgid],
            "primaryStationGroupId": sgid,
            "category": "hub" if label_rank >= 100 else "normal",
            "revealName": coord["display_en"],
            "tags": tags,
        })

    station_key_to_group = {station["sourceStopIds"][0]: station["stationGroupId"] for station in physical_stations}
    station_group_set = set(station_key_to_group.values())
    default_runner = station_key_to_group.get("東京") or next(iter(station_group_set), None)
    default_hunter = station_key_to_group.get("新宿") or default_runner

    track_centerlines = []
    service_geometry = []
    for index, line in enumerate(map_payload.get("physicalLines", [])):
        coords = line.get("coordinates") or []
        if len(coords) < 2:
            continue
        route_id = route_id_for(line.get("line_name_ja") or line.get("label"), normalize_key(line.get("operator_ja")))
        polyline = [{"lat": lat, "lon": lon} for lon, lat in coords]
        track_centerlines.append({
            "id": f"TRACK_TOKYO_{index:04d}",
            "operatorId": route_meta.get(route_id, {}).get("operatorId", "tokyo"),
            "lineName": line.get("line_name_ja") or line.get("label") or route_id,
            "mode": route_meta.get(route_id, {}).get("mode", "rail"),
            "polyline": polyline,
            "stationGroupIds": [],
            "tags": ["tokyo", "track_centerline"],
        })
        service_geometry.append({
            "id": f"GEOM_TOKYO_{index:04d}",
            "routeId": route_id,
            "representation": "service_path",
            "minZoom": 0,
            "maxZoom": 24,
            "offsetRank": 0,
            "polyline": polyline,
        })

    trip_instances = []
    skipped_trains = 0
    for train in source_trains:
        route_id = route_id_for(train.get("line") or train.get("service_name") or train.get("operator"), train.get("operator_id", "tokyo"))
        stop_times = []
        for stop in train.get("stops", []):
            sgid = station_key_to_group.get(stop.get("station_key"))
            if not sgid:
                continue
            arr = seconds_or_none(stop.get("arrival"), stop.get("departure"))
            dep = seconds_or_none(stop.get("departure"), stop.get("arrival"))
            if arr is None and dep is None:
                continue
            stop_times.append({
                "sequence": len(stop_times) + 1,
                "stationGroupId": sgid,
                "arrivalTimeSec": arr if arr is not None else dep,
                "departureTimeSec": dep if dep is not None else arr,
            })
        if len(stop_times) < 2:
            skipped_trains += 1
            continue
        trip_instances.append({
            "id": train.get("id"),
            "routeId": route_id,
            "serviceName": train.get("service_name") or train.get("operator") or "Train",
            "serviceNumber": train.get("train_number") or "",
            "stopTimes": stop_times,
        })

    route_station_sets: dict[str, set[str]] = defaultdict(set)
    for trip in trip_instances:
        route_station_sets[trip["routeId"]].update(stop["stationGroupId"] for stop in trip["stopTimes"])

    service_patterns = [{
        "id": f"PATTERN_{route['id']}",
        "routeId": route["id"],
        "label": route["shortName"],
        "stationGroupIds": sorted(route_station_sets.get(route["id"], station_group_set)),
        "shapeId": None,
        "tags": ["tokyo"],
    } for route in service_routes]

    return {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "metadata": {
            "label": "OniChase V3 Tokyo bundle for V2 UI",
            "datasetId": "v3_tokyo_v2_ui_bundle_v0_1",
            "sourceTrainIndex": str(UNIFIED_TRAINS_PATH.relative_to(ROOT)),
            "sourceMap": str(MAP_PATH.relative_to(ROOT)),
            "skippedTrainCount": skipped_trains,
            "defaultRunnerStartStationId": default_runner,
            "defaultHunterStartStationId": default_hunter,
        },
        "physicalStations": physical_stations,
        "stationGroups": station_groups,
        "trackCenterlines": track_centerlines,
        "pathways": [],
        "serviceRoutes": service_routes,
        "servicePatterns": service_patterns,
        "tripInstances": trip_instances,
        "serviceGeometry": service_geometry,
        "labelRepresentations": label_representations,
        "gameNodes": game_nodes,
    }


def main() -> int:
    bundle = build_bundle()
    write_json(OUTPUT_PATH, bundle)
    write_json(DOCS_DATA_DIR / OUTPUT_PATH.name, bundle)
    print(json.dumps({
        "bundle": str(OUTPUT_PATH.relative_to(ROOT)),
        "physicalStations": len(bundle["physicalStations"]),
        "serviceRoutes": len(bundle["serviceRoutes"]),
        "trackCenterlines": len(bundle["trackCenterlines"]),
        "tripInstances": len(bundle["tripInstances"]),
        "skippedTrainCount": bundle["metadata"]["skippedTrainCount"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
