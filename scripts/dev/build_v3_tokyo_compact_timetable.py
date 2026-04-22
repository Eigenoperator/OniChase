#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "data" / "v3_tokyo_timetable_bundle.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v3_tokyo_timetable_compact.json.gz"


def load_json(path: Path) -> dict[str, Any]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_gz(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with path.open("wb") as raw_handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as handle:
            handle.write(raw)


def intern_index(values: list[str], value: str) -> int:
    values.append(value)
    return len(values) - 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = load_json(args.source)
    station_ids: list[str] = []
    route_ids: list[str] = []
    service_names: list[str] = []
    station_index: dict[str, int] = {}
    route_index: dict[str, int] = {}
    service_name_index: dict[str, int] = {}
    trips: list[list[Any]] = []

    for trip in payload.get("tripInstances", []):
        route_id = str(trip.get("routeId") or "")
        service_name = str(trip.get("serviceName") or "")
        route_idx = route_index.setdefault(route_id, intern_index(route_ids, route_id) if route_id not in route_index else route_index[route_id])
        service_idx = service_name_index.setdefault(
            service_name,
            intern_index(service_names, service_name) if service_name not in service_name_index else service_name_index[service_name],
        )
        stops: list[list[int | None]] = []
        for stop in trip.get("stopTimes", []):
            station_group_id = str(stop.get("stationGroupId") or "")
            station_idx = station_index.setdefault(
                station_group_id,
                intern_index(station_ids, station_group_id) if station_group_id not in station_index else station_index[station_group_id],
            )
            stops.append([
                station_idx,
                stop.get("arrivalTimeSec"),
                stop.get("departureTimeSec"),
            ])
        trips.append([
            trip.get("id") or "",
            route_idx,
            service_idx,
            trip.get("serviceNumber") or "",
            stops,
        ])

    compact = {
        "format": "v3-timetable-compact-v1",
        "version": payload.get("version"),
        "generatedAt": payload.get("generatedAt"),
        "sourceBundle": payload.get("sourceBundle"),
        "stationGroupIds": station_ids,
        "routeIds": route_ids,
        "serviceNames": service_names,
        "trips": trips,
    }
    write_json_gz(args.output, compact)
    print(json.dumps({
        "source": str(args.source.relative_to(ROOT)) if args.source.is_relative_to(ROOT) else str(args.source),
        "output": str(args.output.relative_to(ROOT)) if args.output.is_relative_to(ROOT) else str(args.output),
        "trip_instances": len(trips),
        "station_groups": len(station_ids),
        "routes": len(route_ids),
        "bytes": args.output.stat().st_size,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
