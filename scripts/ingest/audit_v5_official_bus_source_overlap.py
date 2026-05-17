#!/usr/bin/env python3
"""Audit overlap between official V5 bus sources and the current GTFS layer."""

from __future__ import annotations

import argparse
import gzip
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUS_BUNDLE = ROOT / "data" / "v5_bus_gtfs_current_bundle.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v5_official_bus_source_overlap_audit.json"

OFFICIAL_SOURCES = [
    ROOT / "data" / "v5_kate_official_airport_bus_source.json",
    ROOT / "data" / "v5_keikyu_haneda_official_bus_source.json",
    ROOT / "data" / "v5_chuo_cts_official_bus_source.json",
    ROOT / "data" / "v5_hokuto_cts_official_bus_source.json",
    ROOT / "data" / "v5_miyazaki_airport_official_bus_source.json",
    ROOT / "data" / "v5_kagoshima_airport_official_bus_tables.json",
    ROOT / "data" / "v5_ukb_nishinihonjr_official_bus_source.json",
    ROOT / "data" / "v5_nagasaki_airport_official_bus_source.json",
    ROOT / "data" / "v5_ishigaki_airport_official_bus_source.json",
]

OPERATOR_HINTS = {
    "Kansai Airport Transportation Enterprise": ["関西空港交通", "Kansai Airport", "KATE"],
    "Keikyu Bus": ["京急", "Keikyu"],
    "Hokkaido Chuo Bus": ["北海道中央", "中央バス", "Chuo"],
    "Hokuto Kotsu": ["北都", "Hokuto"],
    "Miyazaki Kotsu": ["宮崎交通", "Miyazaki"],
    "Kagoshima Kotsu": ["鹿児島交通", "Kagoshima"],
    "Nishinihon JR Bus": ["西日本JR", "西日本", "Nishinihon"],
    "Nagasaki Airport Bus Operators": ["長崎", "Nagasaki", "県営", "長崎バス"],
    "カリー観光": ["カリー", "Karry"],
}


def read_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize(value: str) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[\s　・/／（）()［］\\[\\]「」『』,，.。:：™®-]+", "", text)
    text = text.replace("station", "駅").replace("airport", "空港")
    return text


def route_label(route: dict[str, Any]) -> str:
    return " ".join(
        str(route.get(key) or "")
        for key in ["agencyName", "routeShortName", "routeLongName", "routeDesc", "sourceRouteId"]
    )


def official_route_stop_names(route: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for direction in route.get("directions") or []:
        for stop in direction.get("stops") or []:
            if isinstance(stop, str):
                names.append(stop)
            elif stop.get("name"):
                names.append(stop["name"])
        for trip in direction.get("trips") or []:
            for stop_time in trip.get("stopTimes") or []:
                if stop_time.get("stopName"):
                    names.append(stop_time["stopName"])
    for timetable in route.get("timetables") or []:
        for stop in timetable.get("stops") or []:
            if stop.get("name"):
                names.append(stop["name"])
        for trip in timetable.get("trips") or []:
            for stop_time in trip.get("stopTimes") or []:
                if stop_time.get("stopName"):
                    names.append(stop_time["stopName"])
    for segment in route.get("segments") or []:
        names.extend(segment.get("stops") or [])
        for trip in segment.get("trips") or []:
            for stop_time in trip.get("stopTimes") or []:
                if stop_time.get("stopName"):
                    names.append(stop_time["stopName"])
    if route.get("stopNames"):
        names.extend(route["stopNames"])
    if route.get("routeStopNames"):
        names.extend(route["routeStopNames"])
    output = []
    seen = set()
    for name in names:
        clean = str(name).strip()
        key = normalize(clean)
        if clean and key not in seen:
            output.append(clean)
            seen.add(key)
    return output


def official_routes(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    source = read_json(path)
    routes = []
    for route in source.get("routes") or []:
        trip_count = int(route.get("tripCount") or 0)
        operator = route.get("operatorName") or source.get("operatorName") or ""
        routes.append(
            {
                "sourcePath": str(path.relative_to(ROOT)),
                "operatorName": operator,
                "airportIata": route.get("airportIata") or source.get("airportIata") or "",
                "routeCode": route.get("routeCode") or route.get("routePath") or route.get("routeName") or "",
                "routeName": route.get("routeName") or "",
                "sourceUrl": route.get("sourceUrl") or "",
                "tripCount": trip_count,
                "stopNames": official_route_stop_names(route),
            }
        )
    return routes


def build_gtfs_index(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    stops_by_id = {stop["busStopId"]: stop for stop in bundle.get("stops") or [] if stop.get("busStopId")}
    routes_by_id = {route["busRouteId"]: route for route in bundle.get("routes") or [] if route.get("busRouteId")}
    route_stop_names: dict[str, set[str]] = defaultdict(set)
    trip_route = {trip["busTripId"]: trip.get("busRouteId") for trip in bundle.get("trips") or [] if trip.get("busTripId")}
    for stop_time in bundle.get("stopTimes") or []:
        route_id = trip_route.get(stop_time.get("busTripId") or "")
        stop = stops_by_id.get(stop_time.get("busStopId") or "")
        if route_id and stop and stop.get("name"):
            route_stop_names[route_id].add(stop["name"])
    rows = []
    for route_id, route in routes_by_id.items():
        names = sorted(route_stop_names.get(route_id, set()))
        rows.append(
            {
                "busRouteId": route_id,
                "label": route_label(route),
                "labelNorm": normalize(route_label(route)),
                "serviceClass": route.get("serviceClass") or "",
                "stopNames": names,
                "stopNameNorms": {normalize(name) for name in names},
            }
        )
    return rows


def score_candidate(official: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    operator = official["operatorName"]
    hints = OPERATOR_HINTS.get(operator, [operator])
    label_norm = candidate["labelNorm"]
    operator_hit = any(normalize(hint) and normalize(hint) in label_norm for hint in hints)
    official_stop_norms = {normalize(name) for name in official["stopNames"] if normalize(name)}
    overlap = official_stop_norms & candidate["stopNameNorms"]
    airport_hit = normalize(official["airportIata"]) in label_norm or any("空港" in name for name in overlap)
    score = len(overlap) + (3 if operator_hit else 0) + (2 if airport_hit else 0)
    return {
        "busRouteId": candidate["busRouteId"],
        "label": candidate["label"],
        "serviceClass": candidate["serviceClass"],
        "score": score,
        "operatorHit": operator_hit,
        "airportHit": airport_hit,
        "overlapStopCount": len(overlap),
        "overlapStops": sorted(overlap)[:12],
    }


def audit(args: argparse.Namespace) -> dict[str, Any]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    bundle = read_json(args.bus_bundle)
    gtfs = build_gtfs_index(bundle)
    official = []
    for path in args.sources:
        official.extend(official_routes(path))

    rows = []
    status_counts = Counter()
    for route in official:
        if route["tripCount"] <= 0:
            status = "official_no_active_trips"
            matches: list[dict[str, Any]] = []
        else:
            scored = [score_candidate(route, candidate) for candidate in gtfs]
            matches = sorted((item for item in scored if item["score"] >= 4), key=lambda item: (-item["score"], item["label"]))[:8]
            status = "possible_gtfs_overlap" if matches else "no_gtfs_overlap_found"
        status_counts[status] += 1
        rows.append(route | {"status": status, "candidateMatches": matches})
    return {
        "schemaVersion": "v5_official_bus_source_overlap_audit.v1",
        "generatedAt": generated_at,
        "sourceBusBundle": str(args.bus_bundle.relative_to(ROOT)) if args.bus_bundle.is_relative_to(ROOT) else str(args.bus_bundle),
        "sourcePaths": [str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path) for path in args.sources],
        "summary": {
            "officialRouteCount": len(rows),
            "officialTripCount": sum(row["tripCount"] for row in rows),
            "statusCounts": dict(sorted(status_counts.items())),
        },
        "routes": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bus-bundle", type=Path, default=DEFAULT_BUS_BUNDLE)
    parser.add_argument("--sources", type=Path, nargs="*", default=OFFICIAL_SOURCES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = audit(args)
    write_json(args.output, payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
