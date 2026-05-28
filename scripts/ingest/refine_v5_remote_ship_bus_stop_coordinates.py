#!/usr/bin/env python3
"""Refine manual coordinates for V5 remote ship-bus source stops."""

from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "data/v5_remote_small_island_bus_source.json"
DOCS_SOURCE_PATH = ROOT / "docs/data/v5_remote_small_island_bus_source.json"
CACHE_PATH = ROOT / "data/v5_bus_official_cache/remote_ship_bus_stop_geocode_cache.json"
REVIEW_PATH = ROOT / "data/v5_remote_ship_bus_stop_coordinate_refinement.json"
DOCS_REVIEW_PATH = ROOT / "docs/data/v5_remote_ship_bus_stop_coordinate_refinement.json"
USER_AGENT = "ChaseV5RemoteShipBusCoordinateRefine/1.0"
MAX_ACCEPT_METERS = 5000


ROUTE_CONTEXT = {
    "aguni_village_bus_port_line": "粟国村 沖縄県",
    "goto_city_community_kaizu_candidate": "五島市 三井楽町 長崎県",
    "iki_kotsu_indouji_ashibe": "壱岐市 長崎県",
    "kagoshima_city_sakurajima_island_view": "桜島 鹿児島市 鹿児島県",
    "kumejima_town_bus_kanegusuku_honnomori": "久米島町 沖縄県",
    "minamitane_community_bus_shimama_candidate": "南種子町 鹿児島県",
    "miyakou_ayukawa_line_port_to_ishinomaki": "石巻市 宮城県",
    "nakajima_kisen_island_bus_candidate": "中島 松山市 愛媛県",
    "niijima_fureai_bus_b_pier_to_honson": "新島村 東京都",
    "nishinoshima_town_bus_beppu_urago": "西ノ島町 島根県",
    "okamura_tobishima_kona_mitarai_hiro": "呉市 豊町 広島県",
    "saihi_gounokubi_bus_candidate": "新上五島町 長崎県",
    "setonaikai_kotsu_munakata_miyaura": "大三島 今治市 愛媛県",
    "shinkamigoto_saihi_arikawa_candidate": "新上五島町 長崎県",
    "shinkamigoto_saihi_route_bus_source_candidate": "新上五島町 長崎県",
    "suo_oshima_town_bus_ihota_hirano": "周防大島町 山口県",
    "teshima_shuttle_ieura_karato": "豊島 土庄町 香川県",
    "tokashiki_bus_port_aharen": "渡嘉敷村 沖縄県",
}


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_cache() -> dict[str, Any]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def query_nominatim(query: str) -> dict[str, Any]:
    params = urllib.parse.urlencode({"q": query, "format": "jsonv2", "limit": "1", "countrycodes": "jp"})
    request = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/search?{params}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload:
        return {"status": "not_found"}
    item = payload[0]
    return {
        "status": "ok",
        "lat": float(item["lat"]),
        "lon": float(item["lon"]),
        "displayName": item.get("display_name", ""),
        "class": item.get("class", ""),
        "type": item.get("type", ""),
    }


def geocode_stop(route_code: str, stop_name: str, cache: dict[str, Any]) -> dict[str, Any]:
    query = f"{stop_name} {ROUTE_CONTEXT.get(route_code, '')} 日本".strip()
    if query in cache:
        return cache[query]
    result = query_nominatim(query)
    result["query"] = query
    result["resolvedAt"] = datetime.now(UTC).isoformat()
    cache[query] = result
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    time.sleep(1.1)
    return result


def main() -> None:
    payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    cache = load_cache()
    reviewed: list[dict[str, Any]] = []
    updated = 0
    rejected = 0
    for route in payload.get("routes", []):
        route_code = str(route.get("routeCode"))
        for stop in route.get("busStops", []):
            source = str(stop.get("coordinateSource", ""))
            if "manual approximate" not in source:
                continue
            current_lat = float(stop.get("lat"))
            current_lon = float(stop.get("lon"))
            result = geocode_stop(route_code, str(stop.get("name")), cache)
            review = {
                "routeCode": route_code,
                "stopName": stop.get("name"),
                "currentLat": current_lat,
                "currentLon": current_lon,
                "result": result,
                "accepted": False,
            }
            if result.get("status") == "ok":
                distance = distance_meters(current_lat, current_lon, float(result["lat"]), float(result["lon"]))
                review["distanceMeters"] = round(distance)
                if distance <= MAX_ACCEPT_METERS:
                    stop["lat"] = round(float(result["lat"]), 7)
                    stop["lon"] = round(float(result["lon"]), 7)
                    stop["coordinateSource"] = (
                        "nominatim_stop_geocode_refined_20260527: "
                        f"{result.get('displayName', '')}"
                    )
                    review["accepted"] = True
                    updated += 1
                else:
                    rejected += 1
            else:
                rejected += 1
            reviewed.append(review)

    SOURCE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOCS_SOURCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_SOURCE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "policy": {"maxAcceptMeters": MAX_ACCEPT_METERS},
        "summary": {"reviewed": len(reviewed), "updated": updated, "rejectedOrUnchanged": rejected},
        "reviews": reviewed,
    }
    REVIEW_PATH.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOCS_REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_REVIEW_PATH.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OK coordinate refine:", review_payload["summary"])


if __name__ == "__main__":
    main()
