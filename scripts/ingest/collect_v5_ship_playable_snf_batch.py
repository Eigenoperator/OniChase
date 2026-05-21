#!/usr/bin/env python3
"""Promote verified Shin Nihonkai Ferry route batch for V5 ships."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_snf_batch_official.json")
SCHEDULE_URL = "https://www.snf.jp/guide/list/"
FARE_URL = "https://www.snf.jp/guide/fare/"
OPERATOR = "新日本海フェリー"
OPERATOR_ID = "shin_nihonkai_ferry"


def hm(value: str) -> int:
    next_day = value.startswith("翌")
    value = value.replace("翌", "")
    hour, minute = value.split(":")
    total = int(hour) * 60 + int(minute)
    if next_day:
        total += 24 * 60
    return total


def display_hm(total_minutes: int) -> str:
    minute_of_day = total_minutes % (24 * 60)
    return f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}"


def route(
    route_id: str,
    group_id: str,
    origin: str,
    destination: str,
    fare_yen: int,
    route_class: str = "long_distance_public_ferry",
) -> dict:
    note = (
        "Official Shin Nihonkai Ferry timetable page lists explicit departure and arrival times for this direction. "
        "Fare uses the official adult passenger Period A base fare (ツーリストA) from the 2026-06-01 fare table as the current V5 gameplay fare. "
        "Cabin upgrades, vehicles, motorcycles, discounts, fuel or seasonal differences outside that published table, and disruption notices are excluded."
    )
    return {
        "routeId": route_id,
        "routeGroupId": group_id,
        "operator": OPERATOR,
        "routeName": f"{origin}-{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": route_class,
        "revealPolicy": "long_distance_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare_yen},
            "sourceUrls": [SCHEDULE_URL, FARE_URL],
            "notes": note,
        },
        "servicePatterns": [],
        "sourceUrls": [SCHEDULE_URL, FARE_URL],
    }


def trip(
    route_id: str,
    service_no: str,
    origin: str,
    destination: str,
    dep: str,
    arr: str,
    calendar: str,
    vessel: str,
) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_{calendar}_{service_no}",
        "routeId": route_id,
        "operator": OPERATOR,
        "serviceNo": service_no,
        "vessel": vessel,
        "origin": origin,
        "destination": destination,
        "departure": display_hm(dep_min),
        "arrival": display_hm(arr_min),
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": calendar},
        "sourceUrl": SCHEDULE_URL,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    route_specs = [
        ("snf_maizuru_otaru_012_out", "snf_maizuru_otaru", "舞鶴港", "小樽港", 12000),
        ("snf_maizuru_otaru_013_back", "snf_maizuru_otaru", "小樽港", "舞鶴港", 12000),
        ("snf_tsuruga_tomakomai_014_out", "snf_tsuruga_tomakomai", "敦賀港", "苫小牧東港", 12000),
        ("snf_tsuruga_tomakomai_015_back", "snf_tsuruga_tomakomai", "苫小牧東港", "敦賀港", 12000),
        ("snf_niigata_otaru_016_out", "snf_niigata_otaru", "新潟港", "小樽港", 8900),
        ("snf_niigata_otaru_017_back", "snf_niigata_otaru", "小樽港", "新潟港", 8900),
        ("snf_tsuruga_niigata_akita_tomakomai_018_out", "snf_tsuruga_niigata_akita_tomakomai", "敦賀港", "新潟港", 8600),
        ("snf_tsuruga_niigata_akita_tomakomai_019_back", "snf_tsuruga_niigata_akita_tomakomai", "新潟港", "敦賀港", 8600),
        ("snf_tsuruga_niigata_akita_tomakomai_020_out", "snf_tsuruga_niigata_akita_tomakomai", "新潟港", "秋田港", 6400),
        ("snf_tsuruga_niigata_akita_tomakomai_021_back", "snf_tsuruga_niigata_akita_tomakomai", "秋田港", "新潟港", 6400),
        ("snf_tsuruga_niigata_akita_tomakomai_022_out", "snf_tsuruga_niigata_akita_tomakomai", "秋田港", "苫小牧東港", 7400),
        ("snf_tsuruga_niigata_akita_tomakomai_023_back", "snf_tsuruga_niigata_akita_tomakomai", "苫小牧東港", "秋田港", 7400),
    ]
    trip_specs = [
        ("snf_maizuru_otaru_012_out", "maizuru_otaru", "舞鶴港", "小樽港", "23:50", "翌20:45", "daily", "はまなす/あかしあ"),
        ("snf_maizuru_otaru_013_back", "otaru_maizuru", "小樽港", "舞鶴港", "23:30", "翌21:15", "daily", "はまなす/あかしあ"),
        ("snf_tsuruga_tomakomai_014_out", "tsuruga_tomakomai", "敦賀港", "苫小牧東港", "23:55", "翌20:30", "daily", "すいせん/すずらん"),
        ("snf_tsuruga_tomakomai_015_back", "tomakomai_tsuruga", "苫小牧東港", "敦賀港", "23:30", "翌20:30", "daily", "すいせん/すずらん"),
        ("snf_niigata_otaru_016_out", "niigata_otaru", "新潟港", "小樽港", "12:00", "翌04:30", "daily", "らべんだあ/あざれあ"),
        ("snf_niigata_otaru_017_back", "otaru_niigata", "小樽港", "新潟港", "16:45", "翌09:15", "daily", "らべんだあ/あざれあ"),
        ("snf_tsuruga_niigata_akita_tomakomai_018_out", "tsuruga_niigata", "敦賀港", "新潟港", "09:30", "21:30", "monday", "ゆうかり/らいらっく"),
        ("snf_tsuruga_niigata_akita_tomakomai_019_back", "niigata_tsuruga", "新潟港", "敦賀港", "16:30", "翌05:30", "sunday", "ゆうかり/らいらっく"),
        ("snf_tsuruga_niigata_akita_tomakomai_020_out", "niigata_akita", "新潟港", "秋田港", "22:30", "翌05:05", "monday_to_saturday", "ゆうかり/らいらっく"),
        ("snf_tsuruga_niigata_akita_tomakomai_021_back", "akita_niigata", "秋田港", "新潟港", "08:35", "15:30", "tuesday_to_sunday", "ゆうかり/らいらっく"),
        ("snf_tsuruga_niigata_akita_tomakomai_022_out", "akita_tomakomai", "秋田港", "苫小牧東港", "06:15", "16:45", "tuesday", "ゆうかり/らいらっく"),
        ("snf_tsuruga_niigata_akita_tomakomai_023_back", "tomakomai_akita", "苫小牧東港", "秋田港", "19:30", "翌07:35", "saturday", "ゆうかり/らいらっく"),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": OPERATOR,
        "operatorId": OPERATOR_ID,
        "retrievedAt": retrieved_at,
        "sourceUrls": [SCHEDULE_URL, FARE_URL],
        "ports": {},
        "routes": [route(*spec) for spec in route_specs],
        "trips": [trip(*spec) for spec in trip_specs],
        "summary": {
            "routeGroupCount": len({spec[1] for spec in route_specs}),
            "directionalRouteCount": len(route_specs),
            "explicitTripCount": len(trip_specs),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
            "excludedDirections": [],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(payload['routes'])} trips={len(payload['trips'])} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
