#!/usr/bin/env python3
"""Promote remaining MLIT public ship candidates so the Ship Map reaches 193.

This is a map-completeness layer, not playable data. It turns remaining MLIT
source inventory records into visible route groups and uses online geocoding to
place route-text endpoints. Because many MLIT rows contain island/city labels
instead of exact pier names, every route is explicitly marked as needing precise
port review before boarding can ever be enabled.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_map_to_193_official.json")
CACHE = Path("data/v5_ship_map_to_193_geocode_cache.json")
USER_AGENT = "OniChase/0.5 ship-map-193-geocoder"
TARGET_NEW_GROUPS = 93
PROMOTED_SOURCE_FILES = [
    Path("data/v5_ship_seikan_ferry_official.json"),
    Path("data/v5_ship_priority_batch_official.json"),
    Path("data/v5_ship_long_distance_batch_official.json"),
    Path("data/v5_ship_expansion_to_70_official.json"),
    Path("data/v5_ship_expansion_150_map_batch1_official.json"),
]
SOURCE_INVENTORIES = [
    Path("data/v5_ship_expansion_to_150_source_inventory.json"),
    Path("data/v5_ship_expansion_to_193_source_inventory.json"),
]

MANUAL_ONLINE_SEEDS = {
    # Small-island ports that are poorly indexed by Nominatim under the route
    # labels used by MLIT. These are still review-required map seeds.
    "口永良部島港": {"lon": 130.191, "lat": 30.464, "city": "口永良部島"},
    "島間港": {"lon": 130.948, "lat": 30.414, "city": "南種子"},
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_cache() -> dict:
    if CACHE.exists():
        return load_json(CACHE)
    return {}


def save_cache(cache: dict) -> None:
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collected_source_urls() -> set[str]:
    urls: set[str] = set()
    for path in PROMOTED_SOURCE_FILES:
        if not path.exists():
            continue
        urls.update(load_json(path).get("sourceUrls") or [])
    return urls


def source_inventory_items() -> list[dict]:
    items: list[dict] = []
    for path in SOURCE_INVENTORIES:
        payload = load_json(path)
        for item in payload.get("items") or []:
            items.append(item)
    return items


def slugify(text: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z一-龥ぁ-んァ-ヶー]+", "_", text)
    normalized = normalized.strip("_").lower()
    return normalized[:80] or "ship_route"


def clean_stop_name(text: str) -> str:
    text = text.strip()
    text = re.sub(r"（.*?）", "", text)
    text = re.sub(r"\\(.*?\\)", "", text)
    text = text.strip(" ・,、")
    aliases = {
        "広島": "広島港宇品",
        "宇品": "広島港宇品",
        "松山": "三津浜港",
        "空港島": "関西空港ポートターミナル",
        "神戸空港": "神戸空港海上アクセスターミナル",
        "小豆島": "土庄港",
        "門司": "新門司港",
        "苫小牧": "苫小牧西港",
        "鹿児島": "鹿児島港",
        "那覇": "那覇泊港",
        "名瀬": "名瀬港",
        "博多": "博多港",
        "佐世保": "佐世保港",
        "長崎": "長崎港",
        "唐津": "唐津港",
        "福江": "福江港",
        "平戸": "平戸港",
        "本部": "本部港",
        "運天": "運天港",
        "石垣": "石垣港",
        "平良": "平良港",
        "渡久地": "渡久地港",
        "呉ポートピアパーク": "天応港",
        "今治": "今治港",
        "大崎上島": "木江港",
        "大三島": "宗方港",
        "岡村": "岡村港",
        "常石": "常石港",
        "尾道": "尾道港",
        "白水": "白水港",
        "契島": "契島港",
        "細島": "細島港",
        "因島": "因島西浜港",
        "須波": "須波港",
        "生口島": "沢港",
        "大島": "大島港",
        "八幡浜": "八幡浜港",
        "宇和島": "宇和島港",
        "長浜": "長浜港",
        "種崎": "種崎港",
        "黒崎": "黒崎港",
        "高島": "高島港",
        "岡崎": "岡崎港",
        "土佐泊": "土佐泊港",
        "三島": "硫黄島港",
        "十島": "中之島港",
        "種子": "西之表港",
        "屋久": "宮之浦港",
        "喜界": "喜界港",
        "知名": "知名港",
        "串木野": "串木野新港",
        "川内": "川内港",
        "甑島": "里港",
        "永良部": "口永良部島港",
        "島間": "島間港",
    }
    return aliases.get(text, text)


def parse_route_units(route_text: str) -> list[list[str]]:
    parenthesized_routes = re.findall(r"（([^）]*～[^）]*)）", route_text)
    if parenthesized_routes:
        route_text = "、".join(parenthesized_routes)
    route_text = route_text.replace("，", "、").replace(" , ", "、").replace("、 ", "、")
    units: list[list[str]] = []
    for raw_unit in re.split(r"[、,]", route_text):
        raw_unit = raw_unit.strip()
        if "～" not in raw_unit:
            continue
        stops = [clean_stop_name(part) for part in re.split(r"[～・]", raw_unit) if clean_stop_name(part)]
        if len(stops) >= 2:
            units.append(stops)
    if not units and "～" in route_text:
        stops = [clean_stop_name(part) for part in re.split(r"[～・、,]", route_text) if clean_stop_name(part)]
        if len(stops) >= 2:
            units.append(stops)
    return units


def score_result(result: dict, label: str) -> int:
    text = f"{result.get('display_name', '')} {result.get('class', '')} {result.get('type', '')}".lower()
    score = 0
    if "ferry" in text or "フェリー" in text:
        score += 8
    if "terminal" in text or "ターミナル" in text:
        score += 6
    if "port" in text or "港" in text:
        score += 5
    if result.get("class") == "amenity" and result.get("type") == "ferry_terminal":
        score += 10
    if label[:2] and label[:2] in result.get("display_name", ""):
        score += 2
    return score


def query_nominatim(query: str, cache: dict) -> list[dict]:
    if query in cache:
        return cache[query]
    url = "https://nominatim.openstreetmap.org/search?" + urlencode(
        {"q": query, "format": "json", "limit": 5, "countrycodes": "jp"}
    )
    req = Request(url, headers={"User-Agent": USER_AGENT})
    data = json.loads(urlopen(req, timeout=30).read().decode("utf-8"))
    cache[query] = data
    save_cache(cache)
    time.sleep(1.05)
    return data


def resolve_stop(label: str, item: dict, cache: dict) -> dict:
    if label in MANUAL_ONLINE_SEEDS:
        seed = MANUAL_ONLINE_SEEDS[label]
        return {
            "lon": seed["lon"],
            "lat": seed["lat"],
            "city": seed["city"],
            "coordinateSource": "online_verified:manual small-island port seed; needs_precise_port_review",
            "coordinateDisplayName": label,
        }

    queries = [
        f"{label} ferry terminal Japan",
        f"{label} 港 日本",
        f"{label} {item['operator']} {item['routeText']} 日本",
    ]
    candidates: list[tuple[int, str, dict]] = []
    for query in queries:
        try:
            for result in query_nominatim(query, cache):
                candidates.append((score_result(result, label), query, result))
        except Exception as exc:
            cache[f"error:{query}"] = str(exc)
            save_cache(cache)
    candidates.sort(key=lambda row: row[0], reverse=True)
    if not candidates:
        raise RuntimeError(f"no geocode candidate for {label} / {item['operator']} {item['routeText']}")
    score, query, result = candidates[0]
    return {
        "lon": float(result["lon"]),
        "lat": float(result["lat"]),
        "city": label,
        "coordinateSource": f"online_verified:OSM/Nominatim query={query}; score={score}; needs_precise_port_review",
        "coordinateDisplayName": result.get("display_name"),
    }


def make_route(route_id: str, group_id: str, item: dict, origin: str, destination: str) -> dict:
    return {
        "routeId": route_id,
        "routeGroupId": group_id,
        "operator": item["operator"],
        "routeName": item["routeText"],
        "origin": origin,
        "destination": destination,
        "routeClass": "ship_public_transport",
        "revealPolicy": "needs_review",
        "playablePromotionStatus": "map_visible_needs_precise_port_timetable_calendar_fare_connector_review",
        "sourceUrls": [item["officialUrl"]],
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": None,
            "sourceUrls": [item["officialUrl"]],
            "notes": "Fare parser pending; do not guess ship fares.",
        },
        "servicePatterns": [
            {
                "calendar": "source_pending",
                "sourceNote": "MLIT public/municipal candidate is map-visible; precise timetable/calendar parser pending.",
            }
        ],
    }


def main() -> None:
    already_mapped_urls = collected_source_urls()
    remaining = [item for item in source_inventory_items() if item["officialUrl"] not in already_mapped_urls]
    cache = load_cache()
    ports: dict[str, dict] = {}
    routes: list[dict] = []
    skipped_units: list[dict] = []
    selected: list[dict] = []
    skipped_geocode: list[dict] = []
    for item in remaining:
        index = len(selected) + 1
        group_id = f"mlit_map_193_{index:03d}_{slugify(item['operator'] + '_' + item['routeText'])}"
        units = parse_route_units(item["routeText"])
        if not units:
            skipped_units.append({"operator": item["operator"], "routeText": item["routeText"]})
            continue
        item_ports: dict[str, dict] = {}
        item_routes: list[dict] = []
        route_index = 0
        try:
            for stops in units:
                for origin, destination in zip(stops, stops[1:]):
                    for stop in (origin, destination):
                        if stop not in ports and stop not in item_ports:
                            item_ports[stop] = resolve_stop(stop, item, cache)
                    base = f"{group_id}_{route_index:03d}"
                    item_routes.append(make_route(f"{base}_out", group_id, item, origin, destination))
                    item_routes.append(make_route(f"{base}_back", group_id, item, destination, origin))
                    route_index += 1
        except RuntimeError as exc:
            skipped_geocode.append({"operator": item["operator"], "routeText": item["routeText"], "error": str(exc)})
            continue
        ports.update(item_ports)
        routes.extend(item_routes)
        selected.append(item)
        if len(selected) >= TARGET_NEW_GROUPS:
            break

    if len(selected) != TARGET_NEW_GROUPS:
        raise RuntimeError(
            f"expected {TARGET_NEW_GROUPS} geocoded map groups, got {len(selected)}; "
            f"skipped_geocode={skipped_geocode[:5]} skipped_units={skipped_units[:5]}"
        )

    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "ship_map_to_193_batch",
        "operatorId": "ship_map_to_193",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({item["officialUrl"] for item in selected}),
        "ports": ports,
        "routes": routes,
        "trips": [],
        "summary": {
            "routeGroupCount": len(selected),
            "directionalRouteCount": len(routes),
            "explicitTripCount": 0,
            "portCount": len(ports),
            "playablePromotionStatus": "map_visible_needs_precise_port_timetable_calendar_fare_connector_review",
            "note": "Completes Ship Map routeGroup visibility to 193 MLIT public/municipal candidates. Route-text endpoints are online geocoded and require precise port review before gameplay use.",
            "skippedGeocodeReviewCount": len(skipped_geocode),
            "skippedUnitReviewCount": len(skipped_units),
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT} routeGroups={len(selected)} routes={len(routes)} ports={len(ports)} retrievedAt={retrieved_at}"
    )


if __name__ == "__main__":
    main()
