#!/usr/bin/env python3
"""Collect the first V5 ship/ferry priority batch after Seikan Ferry."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_priority_batch_official.json")

PORTS = {
    "津なぎさまち": {"lat": 34.7199, "lon": 136.5274, "city": "津", "coordinateSource": "manual_geocode:津なぎさまち"},
    "中部国際空港高速船のりば": {"lat": 34.8581, "lon": 136.8154, "city": "常滑", "coordinateSource": "manual_geocode:セントレア高速船のりば"},
    "神戸空港海上アクセスターミナル": {"lat": 34.6334, "lon": 135.2288, "city": "神戸", "coordinateSource": "manual_geocode:神戸空港海上アクセスターミナル"},
    "関西空港ポートターミナル": {"lat": 34.4356, "lon": 135.2435, "city": "泉佐野", "coordinateSource": "manual_geocode:関西空港ポートターミナル"},
    "和歌山港": {"lat": 34.2158, "lon": 135.1454, "city": "和歌山", "coordinateSource": "manual_geocode:和歌山港フェリーターミナル"},
    "徳島港": {"lat": 34.0627, "lon": 134.5916, "city": "徳島", "coordinateSource": "manual_geocode:徳島港フェリーターミナル"},
    "鳥羽港": {"lat": 34.4862, "lon": 136.8460, "city": "鳥羽", "coordinateSource": "manual_geocode:鳥羽フェリーターミナル"},
    "伊良湖港": {"lat": 34.5802, "lon": 137.0242, "city": "田原", "coordinateSource": "manual_geocode:伊良湖港"},
    "鹿児島港": {"lat": 31.5960, "lon": 130.5636, "city": "鹿児島", "coordinateSource": "manual_geocode:鹿児島港桜島フェリーターミナル"},
    "桜島港": {"lat": 31.5937, "lon": 130.6014, "city": "鹿児島", "coordinateSource": "manual_geocode:桜島港フェリーターミナル"},
    "多比良港": {"lat": 32.8751, "lon": 130.2457, "city": "雲仙", "coordinateSource": "manual_geocode:多比良港ターミナル"},
    "長洲港": {"lat": 32.9280, "lon": 130.4472, "city": "長洲", "coordinateSource": "manual_geocode:長洲港ターミナル"},
}


def hm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def trip(operator: str, route_id: str, no: int, origin: str, destination: str, dep: str, arr: str, source: str) -> dict:
    dep_min = hm_to_minutes(dep)
    arr_min = hm_to_minutes(arr)
    if arr_min <= dep_min:
        arr_min += 1440
    return {
        "tripId": f"{route_id}_{no:02d}",
        "routeId": route_id,
        "operator": operator,
        "serviceNo": str(no),
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": source,
    }


def directional_route(route_id: str, operator: str, route_name: str, origin: str, destination: str, fare: int, source_urls: list[str], *,
                      distance_km: float | None = None, route_class: str = "short_intercity_ferry",
                      playable_status: str = "timetable_fare_ports_collected_connectors_pending",
                      service_patterns: list[dict] | None = None) -> dict:
    return {
        "routeId": route_id,
        "operator": operator,
        "routeName": route_name,
        "origin": origin,
        "destination": destination,
        "distanceKm": distance_km,
        "routeClass": route_class,
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": playable_status,
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": source_urls,
            "notes": "Adult normal passenger fare only; excludes discounts, vehicles, special rooms, hand luggage, and special campaigns.",
        },
        "servicePatterns": service_patterns or [],
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes = []
    trips = []
    sources = []

    # 津エアポートライン: official Centrair page gives all daily departure times and 45 min duration.
    tsu_source = "https://www.centrair.jp/access/ship.html"
    tsu_fare = "https://tsu-airportline.co.jp/fare/"
    sources += [tsu_source, tsu_fare]
    routes += [
        directional_route("tsu_airportline_tsu_centrair", "津エアポートライン", "津・中部国際空港", "津なぎさまち", "中部国際空港高速船のりば", 2980, [tsu_source, tsu_fare], distance_km=43, route_class="airport_sea_access"),
        directional_route("tsu_airportline_centrair_tsu", "津エアポートライン", "中部国際空港・津", "中部国際空港高速船のりば", "津なぎさまち", 2980, [tsu_source, tsu_fare], distance_km=43, route_class="airport_sea_access"),
    ]
    for i, dep in enumerate(["06:00", "08:00", "11:00", "14:00", "16:00", "18:00", "20:00"], 1):
        trips.append(trip("津エアポートライン", "tsu_airportline_tsu_centrair", i, "津なぎさまち", "中部国際空港高速船のりば", dep, f"{int(dep[:2]):02d}:{int(dep[3:])+45:02d}" if int(dep[3:]) + 45 < 60 else f"{int(dep[:2])+1:02d}:{int(dep[3:])-15:02d}", tsu_source))
    for i, dep in enumerate(["07:00", "10:00", "12:00", "15:00", "17:00", "19:00", "22:00"], 1):
        trips.append(trip("津エアポートライン", "tsu_airportline_centrair_tsu", i, "中部国際空港高速船のりば", "津なぎさまち", dep, f"{int(dep[:2]):02d}:{int(dep[3:])+45:02d}" if int(dep[3:]) + 45 < 60 else f"{int(dep[:2])+1:02d}:{int(dep[3:])-15:02d}", tsu_source))

    # 神戸-関空ベイ・シャトル: official page gives timetable and fare.
    bay_time = "https://www.kobe-access.jp/time"
    bay_ticket = "https://www.kobe-access.jp/ticket"
    sources += [bay_time, bay_ticket]
    routes += [
        directional_route("bay_shuttle_kobe_kix", "神戸-関空ベイ・シャトル", "神戸空港・関西空港", "神戸空港海上アクセスターミナル", "関西空港ポートターミナル", 1880, [bay_time, bay_ticket], distance_km=22, route_class="airport_sea_access"),
        directional_route("bay_shuttle_kix_kobe", "神戸-関空ベイ・シャトル", "関西空港・神戸空港", "関西空港ポートターミナル", "神戸空港海上アクセスターミナル", 1880, [bay_time, bay_ticket], distance_km=22, route_class="airport_sea_access"),
    ]
    for i, dep in enumerate(["05:30", "06:30", "07:15", "08:00", "09:00", "10:00", "11:00", "12:30", "14:00", "15:30", "17:00", "18:00", "19:00", "20:00", "21:00", "22:45"], 1):
        arr_min = hm_to_minutes(dep) + 31
        trips.append(trip("神戸-関空ベイ・シャトル", "bay_shuttle_kobe_kix", i, "神戸空港海上アクセスターミナル", "関西空港ポートターミナル", dep, f"{arr_min//60%24:02d}:{arr_min%60:02d}", bay_time))
    for i, dep in enumerate(["06:30", "07:15", "08:00", "09:00", "10:00", "11:00", "12:00", "13:15", "14:45", "16:30", "18:00", "19:00", "20:00", "21:00", "22:00", "00:00"], 1):
        duration = 36 if dep in {"12:00", "16:30"} else 31
        arr_min = hm_to_minutes(dep) + duration
        trips.append(trip("神戸-関空ベイ・シャトル", "bay_shuttle_kix_kobe", i, "関西空港ポートターミナル", "神戸空港海上アクセスターミナル", dep, f"{arr_min//60%24:02d}:{arr_min%60:02d}", bay_time))

    # 南海フェリー: official pages expose fare and current timetable rows.
    nankai_time = "https://nankai-ferry.co.jp/timetable"
    nankai_fare = "https://nankai-ferry.co.jp/price/"
    sources += [nankai_time, nankai_fare]
    routes += [
        directional_route("nankai_ferry_wakayama_tokushima", "南海フェリー", "和歌山・徳島", "和歌山港", "徳島港", 2500, [nankai_time, nankai_fare], distance_km=61, route_class="regional_shortcut_ferry"),
        directional_route("nankai_ferry_tokushima_wakayama", "南海フェリー", "徳島・和歌山", "徳島港", "和歌山港", 2500, [nankai_time, nankai_fare], distance_km=61, route_class="regional_shortcut_ferry"),
    ]

    # 伊勢湾フェリー: fare is official PDF; timetable needs current-calendar parser before boarding.
    ise_fare = "https://www.isewanferry.co.jp/relays/download/1/1122/1946/11101/?file=%2Ffiles%2Flibs%2F11101%2F%2F202207061812533860.pdf"
    ise_home = "https://www.isewanferry.co.jp/"
    sources += [ise_fare, ise_home]
    routes += [
        directional_route("ise_wan_ferry_toba_irago", "伊勢湾フェリー", "鳥羽・伊良湖", "鳥羽港", "伊良湖港", 1800, [ise_home, ise_fare], distance_km=21, route_class="regional_shortcut_ferry", playable_status="fare_ports_collected_timetable_parser_pending"),
        directional_route("ise_wan_ferry_irago_toba", "伊勢湾フェリー", "伊良湖・鳥羽", "伊良湖港", "鳥羽港", 1800, [ise_home, ise_fare], distance_km=21, route_class="regional_shortcut_ferry", playable_status="fare_ports_collected_timetable_parser_pending"),
    ]

    # 桜島フェリー: official page gives frequency count and duration; detailed PDFs remain to parse.
    sakura_time = "https://www.city.kagoshima.lg.jp/sakurajima-ferry/koro-jikoku/timetable.html"
    sakura_fare = "https://www.city.kagoshima.lg.jp/sakurajima-ferry/unchin/unchin.html"
    sources += [sakura_time, sakura_fare]
    pattern = [
        {"calendar": "weekday", "dailyRoundTripCount": 47, "dailyDirectionalTripCount": 47, "sourceNote": "Official page states 94 total weekday sailings."},
        {"calendar": "weekend_holiday", "dailyRoundTripCount": 52, "dailyDirectionalTripCount": 52, "sourceNote": "Official page states 104 total weekend/holiday sailings."},
    ]
    routes += [
        directional_route("sakurajima_ferry_kagoshima_sakurajima", "鹿児島市船舶局", "鹿児島・桜島", "鹿児島港", "桜島港", 250, [sakura_time, sakura_fare], distance_km=4, route_class="urban_public_ferry", playable_status="frequency_fare_ports_collected_pdf_timetable_pending", service_patterns=pattern),
        directional_route("sakurajima_ferry_sakurajima_kagoshima", "鹿児島市船舶局", "桜島・鹿児島", "桜島港", "鹿児島港", 250, [sakura_time, sakura_fare], distance_km=4, route_class="urban_public_ferry", playable_status="frequency_fare_ports_collected_pdf_timetable_pending", service_patterns=pattern),
    ]

    # 有明フェリー: official site confirms route and active service; exact timetable is on dynamic official booking page.
    ariake = "https://www.ariake-ferry.com/"
    sources.append(ariake)
    routes += [
        directional_route("ariake_ferry_taira_nagasu", "有明フェリー", "多比良・長洲", "多比良港", "長洲港", 450, [ariake], distance_km=14, route_class="regional_shortcut_ferry", playable_status="ports_collected_dynamic_timetable_and_fare_review_pending"),
        directional_route("ariake_ferry_nagasu_taira", "有明フェリー", "長洲・多比良", "長洲港", "多比良港", 450, [ariake], distance_km=14, route_class="regional_shortcut_ferry", playable_status="ports_collected_dynamic_timetable_and_fare_review_pending"),
    ]

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "priority_batch_after_seikan",
        "operatorId": "priority_ship_batch_1",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted(set(sources)),
        "ports": PORTS,
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 6,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "portCount": len(PORTS),
            "playablePromotionStatus": "mixed_explicit_trip_and_service_pattern_sources",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routeGroups=6 routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
