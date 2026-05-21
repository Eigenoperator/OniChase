#!/usr/bin/env python3
"""Add the next official ferry timetable batch after the 400-sailing gate."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_500_batch_official.json")


def hm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def hhmm(minutes: int) -> str:
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


def trip(operator: str, route_id: str, no: int, origin: str, destination: str, dep: str, duration: int, source: str, calendar: str = "daily") -> dict:
    dep_min = hm_to_minutes(dep)
    arr_min = dep_min + duration
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": operator,
        "serviceNo": str(no),
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": hhmm(arr_min),
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": duration,
        "calendar": {"type": calendar},
        "sourceUrl": source,
    }


def route(route_id: str, operator: str, route_name: str, origin: str, destination: str, fare: int, source_urls: list[str], *, distance_km: float | None = None, route_class: str = "urban_public_ferry", notes: str = "") -> dict:
    return {
        "routeId": route_id,
        "operator": operator,
        "routeName": route_name,
        "origin": origin,
        "destination": destination,
        "distanceKm": distance_km,
        "routeClass": route_class,
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": source_urls,
            "notes": notes or "Adult normal passenger fare only; excludes discounts, vehicle fares, baggage, and special tickets.",
        },
        "servicePatterns": [],
    }


def add_trips(trips: list[dict], operator: str, route_id: str, origin: str, destination: str, departures: list[str], duration: int, source: str, calendar: str = "daily") -> None:
    for index, dep in enumerate(departures, 1):
        trips.append(trip(operator, route_id, index, origin, destination, dep, duration, source, calendar))


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    routes: list[dict] = []
    trips: list[dict] = []
    sources: list[str] = []

    fukuoka_pdf = "https://www.city.fukuoka.lg.jp/kowan/kyakusen/hakata-port/documents/time_schedule_J.pdf"
    fukuoka_page = "https://www.city.fukuoka.lg.jp/kowan/kyakusen/hakata-port/hyo.html"
    sources += [fukuoka_pdf, fukuoka_page]
    routes += [
        route("mlit_map_193_086_福岡市_博多_志賀島_玄界島_博多_能古_姪浜_小呂島_姪浜_000_out", "福岡市", "博多・志賀島", "博多港", "志賀島", 680, [fukuoka_page, fukuoka_pdf], distance_km=14, notes="Adult one-way fare 博多-志賀島 ¥680 from the official Fukuoka municipal ferry fare table."),
        route("mlit_map_193_086_福岡市_博多_志賀島_玄界島_博多_能古_姪浜_小呂島_姪浜_000_back", "福岡市", "志賀島・博多", "志賀島", "博多港", 680, [fukuoka_page, fukuoka_pdf], distance_km=14, notes="Adult one-way fare 志賀島-博多 ¥680 from the official Fukuoka municipal ferry fare table."),
        route("mlit_map_193_086_福岡市_博多_志賀島_玄界島_博多_能古_姪浜_小呂島_姪浜_001_out", "福岡市", "玄界島・博多", "玄界島", "博多港", 870, [fukuoka_page, fukuoka_pdf], distance_km=18, notes="Adult one-way fare 玄界島-博多 ¥870 from the official Fukuoka municipal ferry fare table."),
        route("mlit_map_193_086_福岡市_博多_志賀島_玄界島_博多_能古_姪浜_小呂島_姪浜_001_back", "福岡市", "博多・玄界島", "博多港", "玄界島", 870, [fukuoka_page, fukuoka_pdf], distance_km=18, notes="Adult one-way fare 博多-玄界島 ¥870 from the official Fukuoka municipal ferry fare table."),
        route("mlit_map_193_086_福岡市_博多_志賀島_玄界島_博多_能古_姪浜_小呂島_姪浜_002_out", "福岡市", "能古・姪浜", "能古", "姪浜", 230, [fukuoka_page, fukuoka_pdf], distance_km=2, notes="Adult one-way fare 能古-姪浜 ¥230 from the official Fukuoka municipal ferry fare table."),
        route("mlit_map_193_086_福岡市_博多_志賀島_玄界島_博多_能古_姪浜_小呂島_姪浜_002_back", "福岡市", "姪浜・能古", "姪浜", "能古", 230, [fukuoka_page, fukuoka_pdf], distance_km=2, notes="Adult one-way fare 姪浜-能古 ¥230 from the official Fukuoka municipal ferry fare table."),
        route("mlit_map_193_086_福岡市_博多_志賀島_玄界島_博多_能古_姪浜_小呂島_姪浜_003_out", "福岡市", "小呂島・姪浜", "小呂島", "姪浜", 1790, [fukuoka_page, fukuoka_pdf], distance_km=39, notes="Adult one-way fare 小呂島-姪浜 ¥1,790 from the official Fukuoka municipal ferry fare table."),
        route("mlit_map_193_086_福岡市_博多_志賀島_玄界島_博多_能古_姪浜_小呂島_姪浜_003_back", "福岡市", "姪浜・小呂島", "姪浜", "小呂島", 1790, [fukuoka_page, fukuoka_pdf], distance_km=39, notes="Adult one-way fare 姪浜-小呂島 ¥1,790 from the official Fukuoka municipal ferry fare table."),
    ]
    # V5 service day is Friday, so use the official weekday/Monday-Saturday tables.
    add_trips(trips, "福岡市", routes[0]["routeId"], "博多港", "志賀島", ["07:05", "07:20", "08:15", "09:40", "10:15", "11:40", "12:30", "13:10", "13:55", "14:30", "16:20", "18:30", "20:00", "21:15", "23:00"], 30, fukuoka_pdf, "weekday")
    add_trips(trips, "福岡市", routes[1]["routeId"], "志賀島", "博多港", ["06:25", "06:45", "07:35", "08:00", "09:00", "10:20", "11:00", "12:20", "13:15", "13:50", "15:40", "17:00", "19:20", "20:35", "22:20"], 30, fukuoka_pdf, "weekday")
    add_trips(trips, "福岡市", routes[2]["routeId"], "玄界島", "博多港", ["06:20", "08:00", "09:40", "12:10", "14:30", "17:35", "19:45"], 35, fukuoka_pdf)
    add_trips(trips, "福岡市", routes[3]["routeId"], "博多港", "玄界島", ["07:10", "08:50", "11:20", "13:30", "16:45", "18:30", "21:00"], 35, fukuoka_pdf)
    add_trips(trips, "福岡市", routes[4]["routeId"], "能古", "姪浜", ["05:00", "06:00", "06:30", "07:00", "07:30", "08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "17:30", "18:00", "18:30", "19:30", "20:15", "20:45", "21:45", "22:45"], 10, fukuoka_pdf)
    add_trips(trips, "福岡市", routes[5]["routeId"], "姪浜", "能古", ["05:15", "06:15", "06:45", "07:15", "07:45", "08:15", "09:15", "10:15", "11:15", "12:15", "13:15", "14:15", "15:15", "16:15", "17:15", "17:45", "18:15", "18:45", "19:45", "20:30", "21:00", "22:00", "23:00"], 10, fukuoka_pdf)
    add_trips(trips, "福岡市", routes[6]["routeId"], "小呂島", "姪浜", ["06:45"], 65, fukuoka_pdf, "monday_wednesday_friday")
    add_trips(trips, "福岡市", routes[7]["routeId"], "姪浜", "小呂島", ["15:00"], 65, fukuoka_pdf, "monday_wednesday_friday")

    shodoshima = "https://www.shikokuferry.com/route2"
    sources.append(shodoshima)
    routes += [
        route("shodoshima_takamatsu_tonosho_064_out", "小豆島フェリー", "高松・土庄", "高松港", "土庄港", 700, [shodoshima], distance_km=22, route_class="regional_shortcut_ferry", notes="Adult one-way passenger fare ¥700 from the official Shikoku Ferry route page."),
        route("shodoshima_takamatsu_tonosho_065_back", "小豆島フェリー", "土庄・高松", "土庄港", "高松港", 700, [shodoshima], distance_km=22, route_class="regional_shortcut_ferry", notes="Adult one-way passenger fare ¥700 from the official Shikoku Ferry route page."),
    ]
    add_trips(trips, "小豆島フェリー", "shodoshima_takamatsu_tonosho_064_out", "高松港", "土庄港", ["06:25", "07:20", "08:02", "09:00", "10:00", "10:40", "11:35", "12:45", "13:40", "16:10", "17:20", "17:50", "18:50", "20:20"], 60, shodoshima)
    add_trips(trips, "小豆島フェリー", "shodoshima_takamatsu_tonosho_065_back", "土庄港", "高松港", ["06:36", "07:35", "08:35", "09:25", "10:20", "11:25", "12:20", "13:55", "14:45", "15:45", "16:30", "17:30", "18:40", "20:10"], 60, shodoshima)

    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "playable_500_batch",
        "operatorId": "playable_ship_500_batch_1",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted(set(sources)),
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 5,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
