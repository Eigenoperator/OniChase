#!/usr/bin/env python3
"""Apply public-source coordinate fixes for V5 remote ship-bus stops."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "data/v5_remote_small_island_bus_source.json"
DOCS_SOURCE_PATH = ROOT / "docs/data/v5_remote_small_island_bus_source.json"
REVIEW_PATH = ROOT / "data/v5_remote_ship_bus_public_coordinate_fixes.json"
DOCS_REVIEW_PATH = ROOT / "docs/data/v5_remote_ship_bus_public_coordinate_fixes.json"


FIXES = {
    ("niijima_fureai_bus_b_pier_to_honson", "本村診療所"): {
        "lat": 34.370576,
        "lon": 139.257118,
        "source": "NAVITIME bus stop direction coordinate",
        "url": "https://www.navitime.co.jp/bus/diagram/direction/00565805/",
    },
    ("niijima_fureai_bus_b_pier_to_honson", "住民センター"): {
        "lat": 34.376901,
        "lon": 139.256794,
        "source": "NAVITIME bus stop direction coordinate",
        "url": "https://www.navitime.co.jp/bus/diagram/direction/00565804/",
    },
    ("niijima_fureai_bus_b_pier_to_honson", "健康センター"): {
        "lat": 34.372416,
        "lon": 139.259704,
        "source": "NAVITIME bus stop direction coordinate",
        "url": "https://www.navitime.co.jp/bus/diagram/direction/00565800/",
    },
    ("shinkamigoto_saihi_route_bus_source_candidate", "青方港相河ターミナル"): {
        "lat": 32.9782698,
        "lon": 129.0532033,
        "source": "busmap.info bus stop coordinate",
        "url": "https://busmap.info/busstop/1245514/",
    },
    ("shinkamigoto_saihi_route_bus_source_candidate", "有川港ターミナル"): {
        "lat": 32.986563,
        "lon": 129.1133744,
        "source": "busmap.info bus stop coordinate",
        "url": "https://busmap.info/busstop/1245490/",
    },
    ("shinkamigoto_saihi_route_bus_source_candidate", "新上五島町役場前"): {
        "lat": 32.9850806,
        "lon": 129.0732177,
        "source": "busmap.info bus stop coordinate",
        "url": "https://busmap.info/busstop/1245496/",
    },
    ("kumejima_town_bus_kanegusuku_honnomori", "ほんのもり前"): {
        "lat": 26.341079,
        "lon": 126.763143,
        "source": "busmaps.com bus stop coordinate",
        "url": "https://busmaps.com/en/japan/public_transit-stop-%E3%81%BB%E3%82%93%E3%81%AE%E3%82%82%E3%82%8A%E5%89%8D-8389423237127998178",
    },
    ("kagoshima_city_sakurajima_island_view", "ビジターセンター"): {
        "lat": 31.586871,
        "lon": 130.595948,
        "source": "NAVITIME bus stop timetable coordinate",
        "url": "https://www.navitime.co.jp/diagram/bus/00259766/00050787/1/",
    },
    ("aguni_village_bus_port_line", "浜コミュニティー"): {
        "lat": 26.579878,
        "lon": 127.23548,
        "source": "bus-routes.net GTFS stop detail coordinate",
        "url": "https://bus-routes.net/gtfs_stop.php?stid=87994",
    },
    ("shinkamigoto_saihi_arikawa_candidate", "有川港ターミナル"): {
        "lat": 32.986563,
        "lon": 129.1133744,
        "source": "busmap.info bus stop coordinate",
        "url": "https://busmap.info/busstop/1245490/",
    },
    ("minamitane_community_bus_shimama_candidate", "州崎港前"): {
        "lat": 30.4390896,
        "lon": 130.855711,
        "source": "Mapion bus stop coordinate for 洲崎港前",
        "url": "https://www.mapion.co.jp/phonebook/M12001/46502/BS4603091/",
    },
    ("minamitane_community_bus_shimama_candidate", "河内温泉"): {
        "lat": 30.4060242,
        "lon": 130.9182628,
        "source": "busmap.info bus stop coordinate",
        "url": "https://busmap.info/busstop/246458/",
    },
    ("goto_city_community_kaizu_candidate", "貝津港待合所前"): {
        "lat": 32.7142323,
        "lon": 128.6532677,
        "source": "OSM/Nominatim ferry-terminal proximity coordinate for 貝津港",
        "url": "https://nominatim.openstreetmap.org/search?format=json&q=%E9%95%B7%E5%B4%8E%E7%9C%8C%E4%BA%94%E5%B3%B6%E5%B8%82%E4%B8%89%E4%BA%95%E6%A5%BD%E7%94%BA%E8%B2%9D%E6%B4%A5%20%E8%B2%9D%E6%B4%A5%E6%B8%AF",
    },
    ("goto_city_community_kaizu_candidate", "三井楽タクシー"): {
        "lat": 32.7473121,
        "lon": 128.6932864,
        "source": "Mapion taxi place coordinate",
        "url": "https://www.mapion.co.jp/phonebook/M12002/42211/24230113022/",
    },
    ("goto_city_community_kaizu_candidate", "竹山公園前"): {
        "lat": 32.7217322,
        "lon": 128.6607592,
        "source": "Mapion bus stop weather coordinate",
        "url": "https://www.mapion.co.jp/weather/spot/BS4203255/",
    },
    ("saihi_gounokubi_bus_candidate", "有川港ターミナル"): {
        "lat": 32.986563,
        "lon": 129.1133744,
        "source": "busmap.info bus stop coordinate",
        "url": "https://busmap.info/busstop/1245490/",
    },
    ("saihi_gounokubi_bus_candidate", "郷の首"): {
        "lat": 32.9262556,
        "lon": 129.0375127,
        "source": "busmap.info bus stop coordinate",
        "url": "https://busmap.info/busstop/1245557/",
    },
    ("saihi_gounokubi_bus_candidate", "奈良尾車庫前"): {
        "lat": 32.8374352,
        "lon": 129.0654859,
        "source": "busmap.info bus stop coordinate",
        "url": "https://busmap.info/busstop/1245612/",
    },
}


def main() -> None:
    payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    applied = []
    missing = []

    for route in payload.get("routes", []):
        route_code = route.get("routeCode")
        for stop in route.get("busStops", []):
            key = (route_code, stop.get("name"))
            fix = FIXES.get(key)
            if not fix:
                continue
            before = {
                "lat": stop.get("lat"),
                "lon": stop.get("lon"),
                "coordinateSource": stop.get("coordinateSource"),
            }
            stop["lat"] = fix["lat"]
            stop["lon"] = fix["lon"]
            stop["coordinateSource"] = (
                f"public_coordinate_refined_20260527: {fix['source']}; {fix['url']}"
            )
            applied.append(
                {
                    "routeCode": route_code,
                    "stopName": stop.get("name"),
                    "before": before,
                    "after": {
                        "lat": stop["lat"],
                        "lon": stop["lon"],
                        "coordinateSource": stop["coordinateSource"],
                    },
                }
            )

    applied_keys = {(item["routeCode"], item["stopName"]) for item in applied}
    for route_code, stop_name in FIXES:
        if (route_code, stop_name) not in applied_keys:
            missing.append({"routeCode": route_code, "stopName": stop_name})

    payload["publicCoordinateFixesAppliedAt"] = datetime.now(UTC).isoformat()
    SOURCE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOCS_SOURCE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    review = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "appliedCount": len(applied),
        "missingCount": len(missing),
        "applied": applied,
        "missing": missing,
    }
    REVIEW_PATH.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOCS_REVIEW_PATH.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OK public coordinate fixes:", {"applied": len(applied), "missing": len(missing)})


if __name__ == "__main__":
    main()
