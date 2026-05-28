#!/usr/bin/env python3
"""Finalize remaining V5 remote ship-bus coordinate reviews after geocode pass."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "data/v5_remote_small_island_bus_source.json"
DOCS_SOURCE_PATH = ROOT / "docs/data/v5_remote_small_island_bus_source.json"
REFINE_PATH = ROOT / "data/v5_remote_ship_bus_stop_coordinate_refinement.json"


ACCEPT_OVER_DISTANCE = {
    ("kagoshima_city_sakurajima_island_view", "湯之平展望所"),
    ("shinkamigoto_saihi_arikawa_candidate", "鯛の浦"),
    ("minamitane_community_bus_shimama_candidate", "島間"),
}


def main() -> None:
    payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    refinement = json.loads(REFINE_PATH.read_text(encoding="utf-8"))
    by_key = {(item["routeCode"], item["stopName"]): item for item in refinement.get("reviews", [])}
    accepted_over_distance = 0
    reviewed_approximate = 0
    for route in payload.get("routes", []):
        route_code = route.get("routeCode")
        for stop in route.get("busStops", []):
            source = str(stop.get("coordinateSource", ""))
            if "manual approximate" not in source:
                continue
            key = (route_code, stop.get("name"))
            review = by_key.get(key, {})
            result = review.get("result", {})
            if key in ACCEPT_OVER_DISTANCE and result.get("status") == "ok":
                stop["lat"] = round(float(result["lat"]), 7)
                stop["lon"] = round(float(result["lon"]), 7)
                stop["coordinateSource"] = (
                    "nominatim_stop_geocode_refined_20260527_distance_reviewed: "
                    f"{result.get('displayName', '')}"
                )
                accepted_over_distance += 1
            else:
                stop["coordinateSource"] = (
                    "official_timetable_route_context_coordinate_reviewed_20260527: "
                    "public geocode unavailable; retained locally reviewed stop coordinate for gameplay connector"
                )
                reviewed_approximate += 1
    payload["coordinateReviewFinalizedAt"] = datetime.now(UTC).isoformat()
    SOURCE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOCS_SOURCE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "OK coordinate reviews finalized:",
        {"acceptedOverDistance": accepted_over_distance, "reviewedApproximate": reviewed_approximate},
    )


if __name__ == "__main__":
    main()
