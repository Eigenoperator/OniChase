#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    stations_path = DATA_DIR / "shinkansen_v2_stations.json"
    routes_path = DATA_DIR / "shinkansen_v2_routes.json"

    stations = load(stations_path)
    routes = load(routes_path)
    by_id = {station["id"]: station for station in stations}

    updated = 0
    changed = True
    while changed:
        changed = False
        for route in routes:
            ids = route["station_ids"]
            n = len(ids)
            for i, station_id in enumerate(ids):
                station = by_id[station_id]
                if station.get("lat") is not None and station.get("lon") is not None:
                    continue

                prev_index = None
                next_index = None
                for j in range(i - 1, -1, -1):
                    prev_station = by_id[ids[j]]
                    if prev_station.get("lat") is not None and prev_station.get("lon") is not None:
                        prev_index = j
                        break
                for j in range(i + 1, n):
                    next_station = by_id[ids[j]]
                    if next_station.get("lat") is not None and next_station.get("lon") is not None:
                        next_index = j
                        break

                if prev_index is not None and next_index is not None:
                    prev_station = by_id[ids[prev_index]]
                    next_station = by_id[ids[next_index]]
                    span = next_index - prev_index
                    ratio = (i - prev_index) / span
                    station["lat"] = prev_station["lat"] + (next_station["lat"] - prev_station["lat"]) * ratio
                    station["lon"] = prev_station["lon"] + (next_station["lon"] - prev_station["lon"]) * ratio
                    station["latlon_status"] = "estimated"
                    updated += 1
                    changed = True

    stations_path.write_text(json.dumps(stations, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    remaining = [station["id"] for station in stations if station.get("lat") is None or station.get("lon") is None]
    print(f"Estimated lat/lon for {updated} stations")
    if remaining:
        print("Still missing:")
        for station_id in remaining:
            print(station_id)


if __name__ == "__main__":
    main()
