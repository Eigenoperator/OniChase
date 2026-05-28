#!/usr/bin/env python3
"""Collect official Amami/Kakeroma port-connector bus timetable slices."""

from __future__ import annotations

import argparse
import json
import shutil
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "port_connector"
DEFAULT_OUTPUT = ROOT / "data" / "v5_amami_port_connector_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_amami_port_connector_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_amami_port_connector_official_bus_audit.json"

KAKEROMA_URL = "https://kakeroma-bus.com/jikokuhyou.html"
SHIMABUS_KONIYA_PDF_URL = "https://shimabus.co.jp/wp-content/uploads/2024/09/r61001_koniya_sumiyo.pdf"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_if_needed(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dst.resolve():
        shutil.copyfile(src, dst)


def fetch(url: str, path: Path, *, refresh: bool) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not refresh:
        return False
    request = urllib.request.Request(url, headers={"User-Agent": "OniChase-v5-bus-collector/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        path.write_bytes(response.read())
    return True


def trip(trip_id: str, *pairs: tuple[str, str], service_days: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tripId": trip_id,
        "stopTimes": [{"stopName": name, "time": time} for name, time in pairs],
    }
    if service_days:
        payload["serviceDays"] = service_days
    return payload


def base_route(route_code: str, route_name: str, operator: str, source_url: str, notes: list[str]) -> dict[str, Any]:
    return {
        "sourceKind": "official_port_connector_timetable",
        "feedKind": "official_port_connector_bus",
        "serviceClass": "bus_local",
        "routeColor": "0f766e",
        "operatorName": operator,
        "routeCode": route_code,
        "routeName": route_name,
        "sourceUrl": source_url,
        "serviceStart": "2026-05-27",
        "serviceEnd": "2027-03-31",
        "serviceDays": "daily",
        "sourceNotes": notes,
    }


def build_routes() -> list[dict[str, Any]]:
    return [
        base_route(
            "shimabus_koniya_naze_seatouchi_uminomichi",
            "古仁屋線（せとうち海の駅 ⇔ しまバス本社前）",
            "しまバス",
            SHIMABUS_KONIYA_PDF_URL,
            [
                "Shimabus official Koniya/Sumiyo timetable PDF, revised 2024-10-01, states the Koniya line runs daily.",
                "This imports the complete せとうち海の駅 ⇔ しまバス本社前 stop-time pairs needed to connect 古仁屋 port to the Amami bus/airport network.",
                "The official PDF lists a longer stop sequence; intermediate stops remain source-visible in the PDF but are omitted here until stop coordinates are reviewed.",
            ],
        )
        | {
            "busStops": [
                {"name": "せとうち海の駅", "lat": 28.1456875, "lon": 129.3086902, "coordinateSource": "docs/data/v5_ship_map.geojson:古仁屋"},
                {"name": "しまバス本社前", "lat": 28.3821, "lon": 129.4943, "coordinateSource": "manual_from_official_shimabus_naze_terminal_spot_check"},
            ],
            "directions": [
                {
                    "direction": "to_koniya",
                    "trips": [
                        trip("shimabus_koniya_to_koniya_001", ("しまバス本社前", "6:31"), ("せとうち海の駅", "7:44")),
                        trip("shimabus_koniya_to_koniya_002", ("しまバス本社前", "7:59"), ("せとうち海の駅", "9:14")),
                        trip("shimabus_koniya_to_koniya_003", ("しまバス本社前", "10:49"), ("せとうち海の駅", "12:04")),
                        trip("shimabus_koniya_to_koniya_004", ("しまバス本社前", "12:19"), ("せとうち海の駅", "13:34")),
                        trip("shimabus_koniya_to_koniya_005", ("しまバス本社前", "13:49"), ("せとうち海の駅", "15:04")),
                        trip("shimabus_koniya_to_koniya_006", ("しまバス本社前", "15:19"), ("せとうち海の駅", "16:34")),
                        trip("shimabus_koniya_to_koniya_007", ("しまバス本社前", "16:49"), ("せとうち海の駅", "18:04")),
                        trip("shimabus_koniya_to_koniya_008", ("しまバス本社前", "18:54"), ("せとうち海の駅", "20:09")),
                    ],
                },
                {
                    "direction": "to_naze",
                    "trips": [
                        trip("shimabus_koniya_to_naze_001", ("せとうち海の駅", "6:40"), ("しまバス本社前", "8:04")),
                        trip("shimabus_koniya_to_naze_002", ("せとうち海の駅", "8:22"), ("しまバス本社前", "9:41")),
                        trip("shimabus_koniya_to_naze_003", ("せとうち海の駅", "9:52"), ("しまバス本社前", "11:11")),
                        trip("shimabus_koniya_to_naze_004", ("せとうち海の駅", "12:42"), ("しまバス本社前", "14:01")),
                        trip("shimabus_koniya_to_naze_005", ("せとうち海の駅", "14:12"), ("しまバス本社前", "15:31")),
                        trip("shimabus_koniya_to_naze_006", ("せとうち海の駅", "15:42"), ("しまバス本社前", "17:01")),
                        trip("shimabus_koniya_to_naze_007", ("せとうち海の駅", "17:12"), ("しまバス本社前", "18:31")),
                        trip("shimabus_koniya_to_naze_008", ("せとうち海の駅", "18:42"), ("しまバス本社前", "20:01")),
                    ],
                },
            ],
        },
        base_route(
            "kakeroma_bus_sesou_mikkyo",
            "瀬相～実久",
            "加計呂麻バス",
            KAKEROMA_URL,
            [
                "Kakeroma Bus official timetable page lists the current 瀬相～実久 daily rows.",
                "This route connects 瀬相港 to western Kakeroma settlements using official stop-time rows.",
            ],
        )
        | {
            "busStops": [
                {"name": "瀬相", "lat": 28.1375, "lon": 129.2617, "coordinateSource": "docs/data/v5_ship_map.geojson:瀬相"},
                {"name": "実久", "lat": 28.1271, "lon": 129.2118, "coordinateSource": "manual_from_official_kakeroma_bus_route_spot_check"},
            ],
            "directions": [
                {"direction": "to_sesou", "trips": [
                    trip("kakeroma_mikkyo_to_sesou_001", ("実久", "6:22"), ("瀬相", "7:10")),
                    trip("kakeroma_mikkyo_to_sesou_002", ("実久", "9:35"), ("瀬相", "10:25")),
                    trip("kakeroma_mikkyo_to_sesou_003", ("実久", "13:20"), ("瀬相", "14:05")),
                    trip("kakeroma_mikkyo_to_sesou_004", ("実久", "16:45"), ("瀬相", "17:33")),
                ]},
                {"direction": "to_mikkyo", "trips": [
                    trip("kakeroma_sesou_to_mikkyo_001", ("瀬相", "7:25"), ("実久", "8:15")),
                    trip("kakeroma_sesou_to_mikkyo_002", ("瀬相", "10:45"), ("実久", "11:35")),
                    trip("kakeroma_sesou_to_mikkyo_003", ("瀬相", "14:25"), ("実久", "15:15")),
                    trip("kakeroma_sesou_to_mikkyo_004", ("瀬相", "18:00"), ("実久", "18:50")),
                ]},
            ],
        },
        base_route(
            "kakeroma_bus_sesou_ikenma_oshikaku",
            "瀬相～押角～生間",
            "加計呂麻バス",
            KAKEROMA_URL,
            [
                "Kakeroma Bus official timetable page lists 瀬相～押角～生間 rows and marks part of the route as demand-operation.",
                "For gameplay this keeps only complete public timetable rows between the two ferry-port bus stops.",
            ],
        )
        | {
            "busStops": [
                {"name": "瀬相", "lat": 28.1375, "lon": 129.2617, "coordinateSource": "docs/data/v5_ship_map.geojson:瀬相"},
                {"name": "生間", "lat": 28.1016, "lon": 129.3322, "coordinateSource": "docs/data/v5_ship_map.geojson:生間"},
            ],
            "directions": [
                {"direction": "to_sesou", "trips": [
                    trip("kakeroma_oshikaku_to_sesou_001", ("生間", "8:30"), ("瀬相", "10:25")),
                    trip("kakeroma_oshikaku_to_sesou_002", ("生間", "12:00"), ("瀬相", "14:05")),
                    trip("kakeroma_oshikaku_to_sesou_003", ("生間", "16:25"), ("瀬相", "17:35")),
                ]},
                {"direction": "to_ikenma", "trips": [
                    trip("kakeroma_oshikaku_to_ikenma_001", ("瀬相", "7:25"), ("生間", "8:10")),
                    trip("kakeroma_oshikaku_to_ikenma_002", ("瀬相", "10:45"), ("生間", "11:40")),
                    trip("kakeroma_oshikaku_to_ikenma_003", ("瀬相", "14:25"), ("生間", "15:55")),
                    trip("kakeroma_oshikaku_to_ikenma_004", ("瀬相", "17:55"), ("生間", "18:31")),
                ]},
            ],
        },
        base_route(
            "kakeroma_bus_sesou_nishiamuro",
            "瀬相～西阿室",
            "加計呂麻バス",
            KAKEROMA_URL,
            [
                "Kakeroma Bus official timetable page lists the current 瀬相～西阿室 daily rows.",
                "This route connects 瀬相港 to nearby west-side settlements using official stop-time rows.",
            ],
        )
        | {
            "busStops": [
                {"name": "瀬相", "lat": 28.1375, "lon": 129.2617, "coordinateSource": "docs/data/v5_ship_map.geojson:瀬相"},
                {"name": "西阿室", "lat": 28.1378, "lon": 129.2455, "coordinateSource": "manual_from_official_kakeroma_bus_route_spot_check"},
            ],
            "directions": [
                {"direction": "to_sesou", "trips": [
                    trip("kakeroma_nishiamuro_to_sesou_001", ("西阿室", "6:55"), ("瀬相", "7:10")),
                    trip("kakeroma_nishiamuro_to_sesou_002", ("西阿室", "10:15"), ("瀬相", "10:30")),
                    trip("kakeroma_nishiamuro_to_sesou_003", ("西阿室", "13:55"), ("瀬相", "14:10")),
                    trip("kakeroma_nishiamuro_to_sesou_004", ("西阿室", "17:20"), ("瀬相", "17:35")),
                ]},
                {"direction": "to_nishiamuro", "trips": [
                    trip("kakeroma_sesou_to_nishiamuro_001", ("瀬相", "7:25"), ("西阿室", "7:40")),
                    trip("kakeroma_sesou_to_nishiamuro_002", ("瀬相", "10:45"), ("西阿室", "11:00")),
                    trip("kakeroma_sesou_to_nishiamuro_003", ("瀬相", "14:25"), ("西阿室", "14:40")),
                    trip("kakeroma_sesou_to_nishiamuro_004", ("瀬相", "18:00"), ("西阿室", "18:15")),
                ]},
            ],
        },
        base_route(
            "kakeroma_bus_ikenma_tokuhama",
            "生間～徳浜",
            "加計呂麻バス",
            KAKEROMA_URL,
            [
                "Kakeroma Bus official timetable page lists the current 生間～徳浜 daily rows.",
                "This route connects 生間港 to east-side Kakeroma settlements using official stop-time rows.",
            ],
        )
        | {
            "busStops": [
                {"name": "生間", "lat": 28.1016, "lon": 129.3322, "coordinateSource": "docs/data/v5_ship_map.geojson:生間"},
                {"name": "徳浜", "lat": 28.1031, "lon": 129.3503, "coordinateSource": "manual_from_official_kakeroma_bus_route_spot_check"},
            ],
            "directions": [
                {"direction": "to_ikenma", "trips": [
                    trip("kakeroma_tokuhama_to_ikenma_001", ("徳浜", "7:35"), ("生間", "8:10")),
                    trip("kakeroma_tokuhama_to_ikenma_002", ("徳浜", "11:15"), ("生間", "11:47")),
                    trip("kakeroma_tokuhama_to_ikenma_003", ("徳浜", "15:30"), ("生間", "16:00")),
                ]},
                {"direction": "to_tokuhama", "trips": [
                    trip("kakeroma_ikenma_to_tokuhama_001", ("生間", "8:35"), ("徳浜", "9:08")),
                    trip("kakeroma_ikenma_to_tokuhama_002", ("生間", "12:05"), ("徳浜", "12:37")),
                    trip("kakeroma_ikenma_to_tokuhama_003", ("生間", "16:25"), ("徳浜", "16:55")),
                ]},
            ],
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    fetched = {
        "kakeromaHtml": fetch(KAKEROMA_URL, args.cache_dir / "kakeroma_bus_jikokuhyou.html", refresh=args.refresh),
        "shimabusKoniyaPdf": fetch(SHIMABUS_KONIYA_PDF_URL, args.cache_dir / "shimabus_koniya_sumiyo_20241001.pdf", refresh=args.refresh),
    }
    routes = build_routes()
    generated_at = datetime.now(UTC).isoformat()
    payload = {
        "schemaVersion": "v5_port_connector_official_bus_source_v1",
        "generatedAt": generated_at,
        "sourcePolicy": {
            "sourceType": "official_operator_timetable",
            "normalization": "manual_table_normalization_from_cached_official_sources",
            "coordinatePolicy": "port endpoints reuse reviewed ship-map coordinates; non-port endpoints use manual spot-check coordinates pending full stop inventory",
        },
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_port_connector_official_bus_source_audit_v1",
        "generatedAt": generated_at,
        "summary": {
            "routeCount": len(routes),
            "tripCount": sum(len(direction.get("trips") or []) for route in routes for direction in route.get("directions") or []),
            "stopCount": sum(len(route.get("busStops") or []) for route in routes),
            "cachedSourceCount": 2,
        },
        "fetched": fetched,
        "sources": [KAKEROMA_URL, SHIMABUS_KONIYA_PDF_URL],
    }
    write_json(args.output, payload)
    copy_if_needed(args.output, args.docs_output)
    write_json(args.audit_output, audit)
    print(json.dumps(audit["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
