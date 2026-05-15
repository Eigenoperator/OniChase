#!/usr/bin/env python3
"""Build a lightweight V5 domestic flight map layer.

The gameplay bundle stores scheduled physical flights. The map layer aggregates
those records into airport points and directional airport-pair arcs so MapLibre
can render the air network without drawing thousands of duplicate lines.
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FLIGHT_BUNDLE = ROOT / "data/v5_domestic_flights_current_bundle.json"
AIRPORTS_CSV = ROOT / "data/v5_flight_source_cache/ourairports_airports.csv"
OUTPUT = ROOT / "docs/data/v5_flight_map.geojson"


def arc_coordinates(start: list[float], end: list[float], steps: int = 28) -> list[list[float]]:
    lon1, lat1 = start
    lon2, lat2 = end
    dx = lon2 - lon1
    dy = lat2 - lat1
    distance = math.hypot(dx, dy)
    if distance <= 0:
        return [start, end]
    normal_x = -dy / distance
    normal_y = dx / distance
    # Keep domestic arcs readable without pretending to be a precise airway.
    bow = min(1.8, max(0.18, distance * 0.12))
    coordinates = []
    for index in range(steps + 1):
        t = index / steps
        curve = math.sin(math.pi * t) * bow
        coordinates.append([
            lon1 + dx * t + normal_x * curve,
            lat1 + dy * t + normal_y * curve,
        ])
    return coordinates


def load_airports() -> dict[str, dict]:
    with AIRPORTS_CSV.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return {
            row["iata_code"]: row
            for row in rows
            if row.get("iso_country") == "JP" and row.get("iata_code")
        }


def main() -> None:
    bundle = json.loads(FLIGHT_BUNDLE.read_text(encoding="utf-8"))
    airports = load_airports()
    flights = bundle.get("flights", [])
    airport_counts = Counter()
    pair_counts = Counter()
    carrier_counts_by_pair: dict[tuple[str, str], Counter] = {}

    for flight in flights:
        origin = flight.get("originAirport")
        dest = flight.get("destinationAirport")
        carrier = flight.get("operatingCarrier")
        if not origin or not dest:
            continue
        airport_counts[origin] += 1
        airport_counts[dest] += 1
        pair_counts[(origin, dest)] += 1
        carrier_counts_by_pair.setdefault((origin, dest), Counter())[carrier] += 1

    missing = sorted(code for code in airport_counts if code not in airports)
    if missing:
        raise SystemExit(f"Missing airport coordinates for: {', '.join(missing)}")

    features = []
    for code, count in sorted(airport_counts.items()):
        row = airports[code]
        lon = float(row["longitude_deg"])
        lat = float(row["latitude_deg"])
        features.append({
            "type": "Feature",
            "id": f"airport-{code}",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "kind": "airport",
                "iata": code,
                "icao": row.get("icao_code") or "",
                "name": row.get("name") or code,
                "municipality": row.get("municipality") or "",
                "flightCount": count,
                "rank": min(10, 1 + math.log10(max(1, count)) * 3),
            },
        })

    for (origin, dest), count in sorted(pair_counts.items()):
        origin_row = airports[origin]
        dest_row = airports[dest]
        start = [float(origin_row["longitude_deg"]), float(origin_row["latitude_deg"])]
        end = [float(dest_row["longitude_deg"]), float(dest_row["latitude_deg"])]
        carriers = carrier_counts_by_pair[(origin, dest)]
        features.append({
            "type": "Feature",
            "id": f"flight-route-{origin}-{dest}",
            "geometry": {"type": "LineString", "coordinates": arc_coordinates(start, end)},
            "properties": {
                "kind": "flight-route",
                "origin": origin,
                "destination": dest,
                "flightCount": count,
                "carrierCount": len(carriers),
                "carriers": ",".join(sorted(carriers)),
                "dominantCarrier": carriers.most_common(1)[0][0] if carriers else "",
            },
        })

    payload = {
        "type": "FeatureCollection",
        "metadata": {
            "schemaVersion": 1,
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sourceFlightBundle": str(FLIGHT_BUNDLE.relative_to(ROOT)),
            "sourceAirportCoordinates": str(AIRPORTS_CSV.relative_to(ROOT)),
            "airportCount": len(airport_counts),
            "directionalRouteCount": len(pair_counts),
            "physicalFlightCount": len(flights),
            "domesticOnly": True,
        },
        "features": features,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["metadata"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
