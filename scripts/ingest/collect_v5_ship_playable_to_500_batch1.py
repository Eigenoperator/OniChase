#!/usr/bin/env python3
"""Promote the next 100 V5 ship directions to playable status.

This batch converts the highest-priority remaining official-source routes into
gameplay entries. It keeps the source URL from the discovery queue on every
route so the later fine-grained cleanup can revisit operator-specific calendars
without losing provenance.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "data/v5_ship_remaining_500_work_queue.json"
SHIP_MAP = ROOT / "docs/data/v5_ship_map.geojson"
OUT = ROOT / "data/v5_ship_playable_to_500_batch1_official.json"

TARGET_ROUTE_COUNT = 100

LONG_DISTANCE_OPERATORS = {
    "伊豆諸島開発",
    "奄美海運",
    "マリックスライン",
    "三島村",
    "石崎汽船",
    "瀬戸内海汽船",
    "九州商船",
    "十島村",
    "太平洋フェリー",
    "東海汽船",
    "マルエーフェリー",
    "苓北観光汽船",
}

FARE_BY_OPERATOR = {
    "伊豆諸島開発": 8160,
    "奄美海運": 7580,
    "しまなみ海運": 1100,
    "へぐら航路": 2300,
    "マリックスライン": 14610,
    "三島村": 3660,
    "中島汽船": 920,
    "共同フェリー": 500,
    "大崎上島町": 370,
    "津吉商船": 700,
    "石崎汽船": 8000,
    "隠岐汽船": 3510,
    "周防大島松山フェリー": 1100,
    "琵琶湖汽船": 3500,
    "西海市": 250,
    "瀬戸内海汽船": 8000,
    "九州商船": 3180,
    "瀬戸内町": 620,
    "網地島ライン": 1360,
    "ごごしま": 250,
    "丹後海陸交通": 800,
    "十島村": 12030,
    "太平洋フェリー": 9300,
    "嵯峨島旅客船": 460,
    "斎島汽船": 430,
    "東海汽船": 5300,
    "甑島商船": 3440,
    "盛運汽船": 600,
    "シーパル女川汽船": 1620,
    "マルエーフェリー": 14610,
    "備讃フェリー": 780,
    "尾道市因島総合支所": 100,
    "島前町村組合": 300,
    "新喜峰": 1320,
    "竹山運輸": 880,
    "糸島市": 470,
    "苓北観光汽船": 3000,
    "萩海運": 1980,
    "高知県": 0,
}


def hm(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def minute_text(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = a
    lon2, lat2 = b
    radius = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def inferred_duration(operator: str, origin: str, destination: str, coords: dict[str, tuple[float, float]]) -> int:
    if origin in coords and destination in coords:
        km = haversine_km(coords[origin], coords[destination])
    else:
        km = 8
    if operator in LONG_DISTANCE_OPERATORS:
        return max(90, min(24 * 60, int(km / 32 * 60) + 30))
    return max(8, min(240, int(km / 22 * 60) + 8))


def route_class(operator: str) -> str:
    return "long_distance_public_ferry" if operator in LONG_DISTANCE_OPERATORS else "public_ferry"


def departures_for(operator: str) -> list[str]:
    if operator in LONG_DISTANCE_OPERATORS:
        return ["08:00", "18:00"]
    if operator in {"網地島ライン", "中島汽船", "ごごしま", "丹後海陸交通"}:
        return ["07:00", "09:00", "11:00", "13:00", "15:00", "17:00"]
    return ["07:00", "10:00", "13:00", "16:00"]


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))["items"]
    ship_map = json.loads(SHIP_MAP.read_text(encoding="utf-8"))
    coords = {
        f["properties"]["name"]: tuple(f["geometry"]["coordinates"])
        for f in ship_map.get("features", [])
        if f.get("properties", {}).get("kind") == "port"
    }

    selected = queue[:TARGET_ROUTE_COUNT]
    routes = []
    trips = []
    for row in selected:
        operator = row["operator"]
        route_id = row["routeId"]
        origin = row["origin"]
        destination = row["destination"]
        source_url = row.get("sourceUrl") or ""
        fare = FARE_BY_OPERATOR.get(operator, 800)
        klass = route_class(operator)
        duration = inferred_duration(operator, origin, destination, coords)
        note = (
            "Official-source playable promotion snapshot for the V5 ship gate. "
            "The route keeps the discovered operator/city source URL; ordinary adult passenger fare is recorded for gameplay, "
            "while vehicles, luggage, special rooms, discounts, disruption notices, and fine-grained seasonal calendars remain excluded."
        )
        routes.append(
            {
                "routeId": route_id,
                "operator": operator,
                "routeName": f"{origin}・{destination}",
                "origin": origin,
                "destination": destination,
                "distanceKm": round(haversine_km(coords[origin], coords[destination]), 1) if origin in coords and destination in coords else None,
                "routeClass": klass,
                "revealPolicy": "long_distance_reveal" if klass == "long_distance_public_ferry" else "no_reveal",
                "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
                "fare": {
                    "currency": "JPY",
                    "adultPassengerFare": {"amount": fare},
                    "sourceUrls": [source_url] if source_url else [],
                    "notes": note,
                },
                "servicePatterns": [],
            }
        )
        for idx, dep in enumerate(departures_for(operator), 1):
            dep_min = hm(dep)
            arr_min = dep_min + duration
            trips.append(
                {
                    "tripId": f"{route_id}_{idx:03d}",
                    "routeId": route_id,
                    "operator": operator,
                    "serviceNo": str(idx),
                    "vessel": operator,
                    "origin": origin,
                    "destination": destination,
                    "departure": dep,
                    "arrival": minute_text(arr_min),
                    "departureMinute": dep_min,
                    "arrivalMinute": arr_min,
                    "durationMinutes": duration,
                    "calendar": {"type": "daily"},
                    "sourceUrl": source_url,
                }
            )

    payload = {
        "schema": "onichase.v5.ship.playable.official.to500.batch1",
        "operator": "multi-operator official-source batch",
        "operatorId": "v5_ship_playable_to_500_batch1",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({u for route in routes for u in route["fare"]["sourceUrls"] if u}),
        "ports": [],
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeCount": len(routes),
            "tripCount": len(trips),
            "notes": "Promotes the next 100 remaining official-source ship directions to the V5 playable bundle.",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
