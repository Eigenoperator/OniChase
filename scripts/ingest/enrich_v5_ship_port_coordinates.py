#!/usr/bin/env python3
"""Resolve V5 ship port coordinates from online geocoding sources.

The ship source files may contain manually seeded coordinates. This script
creates an auditable online-coordinate override layer using OpenStreetMap
Nominatim. The map builder prefers this layer when a port is resolved.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


SOURCE_FILES = [
    Path("data/v5_ship_seikan_ferry_official.json"),
    Path("data/v5_ship_priority_batch_official.json"),
    Path("data/v5_ship_long_distance_batch_official.json"),
    Path("data/v5_ship_expansion_to_70_official.json"),
    Path("data/v5_ship_expansion_150_map_batch1_official.json"),
    Path("data/v5_ship_map_to_193_official.json"),
]
OUT = Path("data/v5_ship_port_coordinates.json")
CACHE = Path("data/v5_ship_port_geocode_cache.json")
USER_AGENT = "OniChase/0.5 ship-port-geocoder"

ONLINE_VERIFIED_COORDINATES = {
    # Nominatim does not always index ferry terminals under the Japanese port
    # names we store. These coordinates are still online-sourced, but manually
    # extracted from map/terminal pages so we do not pretend they were automatic
    # geocoder hits.
    "中部国際空港高速船のりば": {
        "lat": 34.8581,
        "lon": 136.8154,
        "source": "https://www.starflyer.jp/int_jp/checkin/centrair/access.html",
        "note": "Centrair access page confirms high-speed boat terminal; coordinate seed is the port-side terminal position.",
    },
    "八丈島底土港": {
        "lat": 33.1236155,
        "lon": 139.8212331,
        "source": "https://nominatim.openstreetmap.org/",
        "note": "Resolved by OSM/Nominatim query 'Sokodo ferry terminal Hachijo'.",
    },
    "名古屋港": {
        "lat": 35.0600946,
        "lon": 136.8450267,
        "source": "https://mapfan.com/spots/SC3IH%2CJ%2C6U",
        "note": "MapFan coordinate for 名古屋港FT（太平洋フェリー）.",
    },
    "名瀬港": {
        "lat": 28.387977,
        "lon": 129.494832,
        "source": "https://www.navitime.co.jp/poi?spot=00004-46168500011",
        "note": "NAVITIME coordinate for 名瀬新港フェリーターミナル.",
    },
    "多比良港": {
        "lat": 32.8758499,
        "lon": 130.3092539,
        "source": "https://mapfan.com/spots/SCAQC%2CJ%2CU9BHU0",
        "note": "MapFan coordinate for 多比良港FT（有明海自動車航送船組合）.",
    },
    "長洲港": {
        "lat": 32.9281797,
        "lon": 130.443245,
        "source": "https://mapfan.com/spots/SC3IH%2CJ%2CS5",
        "note": "MapFan coordinate for 長洲港FT（有明海自動車航送船組合）.",
    },
    "敦賀港": {
        "lat": 35.6786218,
        "lon": 136.0723443,
        "source": "https://mapfan.com/spots/SC3IH%2CJ%2CKU",
        "note": "MapFan coordinate for 敦賀港FT（新日本海フェリー）.",
    },
    "新潟佐渡汽船ターミナル": {
        "lat": 37.930659,
        "lon": 139.058536,
        "source": "https://www.yakei-kabegami.com/k00031095/",
        "note": "Online photo/map page coordinate for 佐渡汽船新潟港旅客ターミナル.",
    },
    "父島二見港": {
        "lat": 27.084755,
        "lon": 142.1986423,
        "source": "https://nominatim.openstreetmap.org/",
        "note": "Resolved by OSM/Nominatim query 'Ogasawara Futami Port'.",
    },
    "苫小牧東港": {
        "lat": 42.6130,
        "lon": 141.8020,
        "source": "https://tsurispot.com/spots/tomakomai-east-ferry",
        "note": "Online map coordinate for 苫小牧東港フェリーターミナル周辺.",
    },
    "鳥羽港": {
        "lat": 34.490033,
        "lon": 136.844942,
        "source": "https://www.navitime.co.jp/poi?spot=02301-4400049",
        "note": "NAVITIME coordinate for 鳥羽マリンターミナル.",
    },
    "鹿児島新港": {
        "lat": 31.58044245,
        "lon": 130.56871406,
        "source": "https://www.mapion.co.jp/m2/31.58044245%2C130.56871406%2C16/poi%3DILSP0000032344_ipclm",
        "note": "Mapion coordinate for 鹿児島新港FT（マルエーフェリー）.",
    },
    "東予港": {
        "lat": 33.9298724,
        "lon": 133.1183542,
        "source": "https://nominatim.openstreetmap.org/",
        "note": "Resolved by OSM/Nominatim query 'Toyo Port ferry terminal Saijo Ehime'.",
    },
    "新居浜東港": {
        "lat": 33.9873309,
        "lon": 133.3322321,
        "source": "https://mapfan.com/spots/SC3IH%2CJ%2CQR",
        "note": "MapFan coordinate for 新居浜東港FT（四国開発フェリー）.",
    },
    "坂手港": {
        "lat": 34.4559104,
        "lon": 134.3207403,
        "source": "https://mapfan.com/spots/SC3IH%2CJ%2C46",
        "note": "MapFan coordinate for 坂手港FT（ジャンボフェリー）.",
    },
    "高松東港": {
        "lat": 34.3543047,
        "lon": 134.0745442,
        "source": "https://mapfan.com/spots/SC3IH%2CJ%2C2Y",
        "note": "MapFan coordinate for 高松東港FT（ジャンボフェリー）.",
    },
    "高松港": {
        "lat": 34.3540829,
        "lon": 134.0486568,
        "source": "https://mapfan.com/spots/SC3IH%2CJ%2CRY",
        "note": "MapFan coordinate for 高松港FT（四国フェリー）.",
    },
    "土庄港": {
        "lat": 34.4892524,
        "lon": 134.1717904,
        "source": "https://nominatim.openstreetmap.org/",
        "note": "Resolved by OSM/Nominatim query '土庄港フェリーターミナル'.",
    },
    "広島港": {
        "lat": 34.3524545,
        "lon": 132.4550554,
        "source": "https://nominatim.openstreetmap.org/",
        "note": "Resolved by OSM/Nominatim query '広島港宇品旅客ターミナル'.",
    },
    "呉港": {
        "lat": 34.2406728,
        "lon": 132.5564154,
        "source": "https://nominatim.openstreetmap.org/",
        "note": "Resolved by OSM/Nominatim query '呉中央桟橋ターミナル'.",
    },
    "松山観光港": {
        "lat": 33.888602,
        "lon": 132.704287,
        "source": "https://www.navitime.co.jp/poi?spot=00004-38168500016",
        "note": "NAVITIME coordinate for 松山観光港ターミナル.",
    },
}

ALIASES = {
    "青森フェリーターミナル": ["Aomori Seikan Ferry Terminal", "Aomori Ferry Terminal"],
    "函館フェリーターミナル": ["Hakodate Seikan Ferry Terminal", "Hakodate Ferry Terminal"],
    "青森港": ["Aomori Ferry Terminal", "Tsugaru Kaikyo Ferry Aomori Terminal"],
    "函館港": ["Tsugaru Kaikyo Ferry Hakodate Terminal", "Hakodate Ferry Terminal"],
    "津なぎさまち": ["Tsu Nagisamachi", "Tsu Ferry Terminal"],
    "中部国際空港高速船のりば": ["Centrair Ferry Terminal", "Chubu Centrair International Airport ferry terminal"],
    "神戸空港海上アクセスターミナル": ["Kobe Airport Marine Access Terminal"],
    "関西空港ポートターミナル": ["Kansai Airport Port Terminal", "Kansai International Airport ferry terminal"],
    "和歌山港": ["Wakayama Port ferry terminal"],
    "徳島港": ["Tokushima Port ferry terminal"],
    "鳥羽港": ["Toba Ferry Terminal"],
    "伊良湖港": ["Irago Ferry Terminal", "Irago Crystal Port"],
    "鹿児島港": ["Kagoshima Sakurajima Ferry Terminal"],
    "桜島港": ["Sakurajima Ferry Terminal"],
    "多比良港": ["Taira Port Ferry Terminal Nagasaki", "Taira Ferry Terminal Unzen"],
    "長洲港": ["Nagasu Port Ferry Terminal Kumamoto"],
    "名古屋港": ["Nagoya Ferry Terminal", "Nagoya Port Ferry Terminal"],
    "仙台港": ["Sendai Port Ferry Terminal"],
    "苫小牧西港": ["Tomakomai West Port Ferry Terminal", "Tomakomai Ferry Terminal"],
    "大洗港": ["Oarai Ferry Terminal"],
    "大阪南港": ["Osaka Nanko Ferry Terminal", "Osaka South Port Ferry Terminal"],
    "別府港": ["Beppu Kanko Port Ferry Terminal", "Beppu Ferry Terminal"],
    "神戸港": ["Kobe Ferry Terminal"],
    "大分港": ["Oita Ferry Terminal"],
    "志布志港": ["Shibushi Port Ferry Terminal"],
    "舞鶴港": ["Maizuru Ferry Terminal"],
    "小樽港": ["Otaru Ferry Terminal"],
    "敦賀港": ["Tsuruga Ferry Terminal"],
    "苫小牧東港": ["Tomakomai East Port Ferry Terminal"],
    "新潟港": ["Niigata Ferry Terminal"],
    "秋田港": ["Akita Ferry Terminal"],
    "泉大津港": ["Izumiotsu Ferry Terminal"],
    "新門司港": ["Shin Moji Ferry Terminal", "Shinmoji Ferry Terminal"],
    "横須賀港": ["Yokosuka Ferry Terminal"],
    "東京港": ["Tokyo Ferry Terminal Ariake", "Tokyo Port Ferry Terminal"],
    "宮崎港": ["Miyazaki Ferry Terminal"],
    "八戸港": ["Hachinohe Ferry Terminal"],
    "大間港": ["Oma Ferry Terminal"],
    "室蘭港": ["Muroran Ferry Terminal"],
    "新潟佐渡汽船ターミナル": ["Sado Kisen Niigata Ferry Terminal"],
    "両津港": ["Ryotsu Port Ferry Terminal"],
    "直江津港": ["Naoetsu Port Ferry Terminal"],
    "小木港": ["Ogi Port Ferry Terminal Sado"],
    "竹芝": ["Takeshiba Passenger Ship Terminal"],
    "父島二見港": ["Futami Port Chichijima"],
    "大島岡田港": ["Okada Port Oshima"],
    "八丈島底土港": ["Sokodo Port Hachijojima"],
    "博多港": ["Hakata Port Ferry Terminal"],
    "郷ノ浦港": ["Gonoura Port Ferry Terminal"],
    "厳原港": ["Izuhara Port Ferry Terminal"],
    "鹿児島新港": ["Kagoshima New Port Ferry Terminal"],
    "名瀬港": ["Naze Port Ferry Terminal"],
    "那覇泊港": ["Tomari Port Naha"],
}


def load_ports() -> dict[str, dict]:
    ports: dict[str, dict] = {}
    for path in SOURCE_FILES:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for name, port in (payload.get("ports") or {}).items():
            ports[name] = port
    return ports


def load_cache() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def score_result(result: dict, port_name: str) -> int:
    text = f"{result.get('display_name', '')} {result.get('class', '')} {result.get('type', '')}".lower()
    score = 0
    if "ferry" in text or "フェリー" in text:
        score += 5
    if "terminal" in text or "ターミナル" in text:
        score += 4
    if "port" in text or "港" in text:
        score += 3
    if result.get("class") == "amenity" and result.get("type") == "ferry_terminal":
        score += 10
    if port_name[:2] and port_name[:2] in result.get("display_name", ""):
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
    time.sleep(1.1)
    return data


def resolve_port(name: str, fallback: dict, cache: dict) -> dict:
    verified = ONLINE_VERIFIED_COORDINATES.get(name)
    if verified:
        return {
            "name": name,
            "lat": verified["lat"],
            "lon": verified["lon"],
            "status": "online_verified_manual_extract",
            "score": 100,
            "source": verified["source"],
            "note": verified["note"],
        }

    coordinate_source = fallback.get("coordinateSource") or ""
    if coordinate_source.startswith("online_verified:"):
        return {
            "name": name,
            "lat": fallback.get("lat"),
            "lon": fallback.get("lon"),
            "status": "online_verified_source_seed",
            "score": 90,
            "source": coordinate_source,
            "note": "Coordinate seed is from the route expansion collection pass; keep it instead of accepting weak geocoder matches.",
        }

    queries = ALIASES.get(name, []) + [f"{name} ferry terminal Japan", f"{name} port Japan"]
    candidates = []
    errors = []
    for query in queries:
        try:
            for result in query_nominatim(query, cache):
                candidates.append((score_result(result, name), query, result))
        except Exception as exc:  # pragma: no cover - online failure path
            errors.append(f"{query}: {exc}")
    candidates.sort(key=lambda item: item[0], reverse=True)
    if candidates and candidates[0][0] >= 5:
        score, query, result = candidates[0]
        return {
            "name": name,
            "lat": float(result["lat"]),
            "lon": float(result["lon"]),
            "status": "online_resolved",
            "score": score,
            "source": "nominatim.openstreetmap.org",
            "query": query,
            "osm": {
                "displayName": result.get("display_name"),
                "class": result.get("class"),
                "type": result.get("type"),
                "osmType": result.get("osm_type"),
                "osmId": result.get("osm_id"),
                "placeRank": result.get("place_rank"),
                "importance": result.get("importance"),
            },
        }
    return {
        "name": name,
        "lat": fallback.get("lat"),
        "lon": fallback.get("lon"),
        "status": "manual_fallback_unresolved_online",
        "score": candidates[0][0] if candidates else 0,
        "source": fallback.get("coordinateSource", "manual_fallback"),
        "queries": queries,
        "errors": errors,
        "bestCandidate": candidates[0][2] if candidates else None,
    }


def main() -> None:
    ports = load_ports()
    cache = load_cache()
    generated_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    resolved = {name: resolve_port(name, port, cache) for name, port in sorted(ports.items())}
    summary = {
        "portCount": len(resolved),
        "onlineResolvedCount": sum(1 for item in resolved.values() if item["status"] == "online_resolved"),
        "onlineVerifiedManualCount": sum(
            1 for item in resolved.values() if item["status"] == "online_verified_manual_extract"
        ),
        "onlineVerifiedSourceSeedCount": sum(
            1 for item in resolved.values() if item["status"] == "online_verified_source_seed"
        ),
        "manualFallbackCount": sum(1 for item in resolved.values() if item["status"].startswith("manual_")),
    }
    payload = {
        "schema": "onichase.v5.ship.portCoordinates.v1",
        "generatedAt": generated_at,
        "geocoder": "Nominatim / OpenStreetMap",
        "geocoderPolicy": "Prefer online ferry_terminal/port POIs. Keep manual fallback only when online result is unresolved; such ports remain audit red lights.",
        "summary": summary,
        "ports": resolved,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} {summary} generatedAt={generated_at}")


if __name__ == "__main__":
    main()
