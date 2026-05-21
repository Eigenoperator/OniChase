#!/usr/bin/env python3
"""Promote the next verified V5 ship gameplay batch."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_priority_100_batch_official.json")


def hm(value: str) -> int:
    next_day = value.startswith("翌")
    value = value.replace("翌", "")
    hour, minute = value.split(":")
    total = int(hour) * 60 + int(minute)
    if next_day:
        total += 24 * 60
    return total


def hhmm(total: int) -> str:
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def route(route_id, group_id, operator, origin, destination, fare, sources, note, route_class="regional_public_ferry", reveal="no_reveal"):
    return {
        "routeId": route_id,
        "routeGroupId": group_id,
        "operator": operator,
        "routeName": f"{origin}-{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": route_class,
        "revealPolicy": reveal,
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": sources,
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": sources,
    }


def trip(route_id, operator, service_no, vessel, origin, destination, dep, arr, calendar, source):
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_{calendar}_{service_no}",
        "routeId": route_id,
        "operator": operator,
        "serviceNo": str(service_no),
        "vessel": vessel,
        "origin": origin,
        "destination": destination,
        "departure": hhmm(dep_min),
        "arrival": hhmm(arr_min),
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": calendar},
        "sourceUrl": source,
    }


def add_sunflower(routes, trips):
    operator = "商船三井さんふらわあ"
    base = "https://www.ferry-sunflower.co.jp/"
    specs = [
        ("mol_osaka_beppu_006_out", "mol_osaka_beppu", "大阪南港", "別府港", 13990, "https://www.ferry-sunflower.co.jp/route/osaka-beppu/time/", "https://www.ferry-sunflower.co.jp/route/osaka-beppu/fee/", "19:05", "翌06:55", "sunday_to_thursday", "くれない/むらさき"),
        ("mol_osaka_beppu_007_back", "mol_osaka_beppu", "別府港", "大阪南港", 13990, "https://www.ferry-sunflower.co.jp/route/osaka-beppu/time/", "https://www.ferry-sunflower.co.jp/route/osaka-beppu/fee/", "18:45", "翌06:35", "sunday_to_thursday", "くれない/むらさき"),
        ("mol_kobe_oita_008_out", "mol_kobe_oita", "神戸港", "大分港", 13990, "https://www.ferry-sunflower.co.jp/route/kobe-oita/time/", "https://www.ferry-sunflower.co.jp/route/kobe-oita/fee/", "19:00", "翌06:20", "sunday_to_thursday", "ごーるど/ぱーる"),
        ("mol_kobe_oita_009_back", "mol_kobe_oita", "大分港", "神戸港", 13990, "https://www.ferry-sunflower.co.jp/route/kobe-oita/time/", "https://www.ferry-sunflower.co.jp/route/kobe-oita/fee/", "19:20", "翌06:40", "sunday_to_thursday", "ごーるど/ぱーる"),
        ("mol_osaka_shibushi_010_out", "mol_osaka_shibushi", "大阪南港", "志布志港", 17870, "https://www.ferry-sunflower.co.jp/route/osaka-shibushi/time/", "https://www.ferry-sunflower.co.jp/route/osaka-shibushi/fee/", "17:55", "翌08:55", "monday_to_thursday", "さつま/きりしま"),
        ("mol_osaka_shibushi_011_back", "mol_osaka_shibushi", "志布志港", "大阪南港", 17870, "https://www.ferry-sunflower.co.jp/route/osaka-shibushi/time/", "https://www.ferry-sunflower.co.jp/route/osaka-shibushi/fee/", "17:55", "翌07:40", "monday_to_friday", "さつま/きりしま"),
    ]
    note = (
        "Official MOL Sunflower route pages list explicit departure/arrival times by weekday pattern. "
        "Fare uses the 2026 Apr-Jun A-period adult passenger base fare; room upgrades, vehicles, discounts, and disruption notices are excluded."
    )
    for i, (route_id, group_id, origin, dest, fare, time_url, fare_url, dep, arr, calendar, vessel) in enumerate(specs, 1):
        routes.append(route(route_id, group_id, operator, origin, dest, fare, [time_url, fare_url, base], note, "long_distance_public_ferry", "long_distance_reveal"))
        trips.append(trip(route_id, operator, i, vessel, origin, dest, dep, arr, calendar, time_url))


def add_orange(routes, trips):
    operator = "四国開発フェリー"
    note = (
        "Official Orange Ferry pages list the Kansai routes and fares. "
        "Toyo-Osaka uses the official nightly 22:00-06:00 sailing and 2026 Apr-Jun C-period adult single fare. "
        "Niihama-Kobe uses the official 16:20-23:40 / 01:20-08:20 weekday cargo-passenger ferry pattern and 2026 Apr-Jun C-period adult single fare."
    )
    specs = [
        ("orange_toyo_osaka_056_out", "orange_toyo_osaka", "東予港", "大阪南港", 8600, "https://www.orange-ferry.co.jp/en/osaka.html", "https://www.orange-ferry.co.jp/fare-price/kansai/toyo-osaka/index.html", "22:00", "翌06:00", "daily", "おれんじえひめ/おれんじおおさか"),
        ("orange_toyo_osaka_057_back", "orange_toyo_osaka", "大阪南港", "東予港", 8600, "https://www.orange-ferry.co.jp/en/osaka.html", "https://www.orange-ferry.co.jp/fare-price/kansai/toyo-osaka/index.html", "22:00", "翌06:00", "daily", "おれんじえひめ/おれんじおおさか"),
        ("orange_niihama_kobe_058_out", "orange_niihama_kobe", "新居浜東港", "神戸港", 8600, "https://www.orange-ferry.co.jp/time-table/kansai/niihama-kobe/", "https://www.orange-ferry.co.jp/fare-price/kansai/niihama-kobe/index.html", "16:20", "23:40", "monday_to_thursday", "おれんじホープ"),
        ("orange_niihama_kobe_059_back", "orange_niihama_kobe", "神戸港", "新居浜東港", 8600, "https://www.orange-ferry.co.jp/time-table/kansai/niihama-kobe/", "https://www.orange-ferry.co.jp/fare-price/kansai/niihama-kobe/index.html", "01:20", "08:20", "tuesday_to_friday", "おれんじホープ"),
    ]
    for i, (route_id, group_id, origin, dest, fare, time_url, fare_url, dep, arr, calendar, vessel) in enumerate(specs, 1):
        routes.append(route(route_id, group_id, operator, origin, dest, fare, [time_url, fare_url], note, "long_distance_public_ferry", "long_distance_reveal"))
        trips.append(trip(route_id, operator, i, vessel, origin, dest, dep, arr, calendar, time_url))


def add_anei(routes, trips):
    operator = "安栄観光"
    time_url = "https://prod.aneikankou.co.jp/condition/index"
    fare_url = "https://aneikankou.co.jp/timetable"
    note = (
        "Official Anei Kanko operation page for 2026-05-22 lists current departure times and normal-operation status by Yaeyama route. "
        "Official timetable/fare page lists one-way adult fares including fuel adjustment. "
        "Arrival times are computed from the published/standard route running times used for the same public timetable display; discounts, tours, and disruption changes are excluded."
    )
    specs = [
        ("anei_ishigaki_yaeyama_086_out", "anei_ishigaki_yaeyama", "石垣港", "竹富港", 970, ["07:30", "09:00", "10:00", "12:30", "15:30"], 15),
        ("anei_ishigaki_yaeyama_087_back", "anei_ishigaki_yaeyama", "竹富港", "石垣港", 970, ["09:20", "10:20", "12:50", "14:50", "17:00"], 15),
        ("anei_ishigaki_yaeyama_088_out", "anei_ishigaki_yaeyama", "石垣港", "小浜港", 1720, ["09:15", "14:50", "16:20"], 30),
        ("anei_ishigaki_yaeyama_089_back", "anei_ishigaki_yaeyama", "小浜港", "石垣港", 1720, ["09:55", "15:30", "17:00"], 30),
        ("anei_ishigaki_yaeyama_090_out", "anei_ishigaki_yaeyama", "石垣港", "黒島港", 1850, ["07:30", "13:30", "15:30"], 35),
        ("anei_ishigaki_yaeyama_091_back", "anei_ishigaki_yaeyama", "黒島港", "石垣港", 1850, ["08:25", "14:10", "16:25"], 35),
        ("anei_ishigaki_yaeyama_092_out", "anei_ishigaki_yaeyama", "石垣港", "西表大原港", 2520, ["08:30", "13:00", "16:00"], 45),
        ("anei_ishigaki_yaeyama_093_back", "anei_ishigaki_yaeyama", "西表大原港", "石垣港", 2520, ["09:30", "14:00", "17:00"], 45),
        ("anei_ishigaki_yaeyama_094_out", "anei_ishigaki_yaeyama", "石垣港", "西表上原港", 3290, ["07:00", "08:30", "13:30", "16:30"], 50),
        ("anei_ishigaki_yaeyama_095_back", "anei_ishigaki_yaeyama", "西表上原港", "石垣港", 3290, ["08:00", "09:30", "14:30", "17:45"], 50),
        ("anei_ishigaki_yaeyama_096_out", "anei_ishigaki_yaeyama", "石垣港", "波照間港", 4990, ["08:00", "11:45", "15:00"], 75),
        ("anei_ishigaki_yaeyama_097_back", "anei_ishigaki_yaeyama", "波照間港", "石垣港", 4990, ["09:50", "13:00", "16:50"], 75),
        ("anei_ishigaki_yaeyama_098_out", "anei_ishigaki_yaeyama", "石垣港", "鳩間港", 3290, ["08:30", "16:30"], 45),
        ("anei_ishigaki_yaeyama_099_back", "anei_ishigaki_yaeyama", "鳩間港", "石垣港", 3290, ["09:45", "17:25"], 45),
    ]
    for route_id, group_id, origin, dest, fare, deps, duration in specs:
        routes.append(route(route_id, group_id, operator, origin, dest, fare, [time_url, fare_url], note))
        for idx, dep in enumerate(deps, 1):
            trips.append(trip(route_id, operator, idx, "高速船", origin, dest, dep, hhmm(hm(dep) + duration), "daily", time_url))


def main() -> None:
    routes = []
    trips = []
    add_sunflower(routes, trips)
    add_orange(routes, trips)
    add_anei(routes, trips)
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "priority_batch_100",
        "operatorId": "priority_batch_100",
        "retrievedAt": retrieved_at,
        "sourceUrls": sorted({url for r in routes for url in r.get("sourceUrls", [])}),
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": len({r["routeGroupId"] for r in routes}),
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
