#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_INPUT = ROOT / "data" / "v4_gameplay_map_bundle.json.gz"
DEFAULT_TIMETABLE_INPUT = ROOT / "data" / "v4_gameplay_timetable_compact.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_room_server_bundle.json.gz"
DEFAULT_TRIP_STORE_OUTPUT = ROOT / "data" / "v4_room_server_trips.sqlite"


def load_json(path: Path) -> dict[str, Any]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    else:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def minimal_station_groups(map_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    groups = []
    for group in map_bundle.get("stationGroups", []):
        groups.append(
            {
                "id": group["id"],
                "primaryName": group.get("primaryName") or group["id"],
            }
        )
    return groups


def write_trip_store(path: Path, compact_timetable: dict[str, Any]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode = OFF")
    connection.execute("PRAGMA synchronous = OFF")
    connection.execute(
        """
        CREATE TABLE trips (
          id TEXT PRIMARY KEY,
          route_index INTEGER NOT NULL,
          service_index INTEGER NOT NULL,
          service_number TEXT NOT NULL,
          stops_json TEXT NOT NULL
        )
        """
    )
    count = 0
    for trip in compact_timetable.get("trips", []):
        stops = [
            [
                stop[0],
                stop[1],
                stop[2],
                sequence,
            ]
            for sequence, stop in enumerate(trip[4], start=1)
        ]
        connection.execute(
            "INSERT OR REPLACE INTO trips (id, route_index, service_index, service_number, stops_json) VALUES (?, ?, ?, ?, ?)",
            (trip[0], trip[1], trip[2], trip[3] or "", json.dumps(stops, separators=(",", ":"))),
        )
        count += 1
    connection.execute("CREATE INDEX idx_trips_id ON trips(id)")
    connection.commit()
    connection.close()
    return count


def build_room_server_bundle(
    map_bundle: dict[str, Any],
    compact_timetable: dict[str, Any],
    map_input: Path,
    timetable_input: Path,
    trip_store_output: Path,
    trip_count: int,
) -> dict[str, Any]:
    metadata = dict(map_bundle.get("metadata", {}))
    metadata.update(
        {
            "bundleFormat": "v4-room-server-slim",
            "roomServerSlim": True,
            "sourceMapBundle": str(map_input.relative_to(ROOT)),
            "sourceCompactTimetable": str(timetable_input.relative_to(ROOT)),
            "tripStorePath": str(trip_store_output.relative_to(ROOT)),
            "deferredTimetable": False,
            "deferredTripCount": trip_count,
            "notes": [
                "Room-server slim bundle for multiplayer state, planning, live simulation, and capture checks.",
                "Map geometry remains deployed as static MapLibre data and is intentionally not loaded by the room server.",
            ],
        }
    )
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "version": "v4.room_server.1",
        "generatedAt": generated_at,
        "metadata": metadata,
        "stationGroups": minimal_station_groups(map_bundle),
        "compactTimetable": {
            "format": "v4-room-server-compact-v1",
            "version": compact_timetable.get("version", "v4.gameplay.1"),
            "generatedAt": compact_timetable.get("generatedAt"),
            "stationGroupIds": compact_timetable.get("stationGroupIds", []),
            "serviceNames": compact_timetable.get("serviceNames", []),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a small v4 bundle for the online room server.")
    parser.add_argument("--map-input", type=Path, default=DEFAULT_MAP_INPUT)
    parser.add_argument("--timetable-input", type=Path, default=DEFAULT_TIMETABLE_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--trip-store-output", type=Path, default=DEFAULT_TRIP_STORE_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    compact_timetable = load_json(args.timetable_input)
    trip_count = write_trip_store(args.trip_store_output, compact_timetable)
    map_bundle = load_json(args.map_input)
    payload = build_room_server_bundle(
        map_bundle,
        compact_timetable,
        args.map_input,
        args.timetable_input,
        args.trip_store_output,
        trip_count,
    )
    write_json(args.output, payload)
    print(
        f"Wrote {args.output} with "
        f"{len(payload['stationGroups'])} station groups and "
        f"{trip_count} SQLite trips at {args.trip_store_output}"
    )


if __name__ == "__main__":
    main()
