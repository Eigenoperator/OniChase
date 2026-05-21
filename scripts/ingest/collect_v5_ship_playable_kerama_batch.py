#!/usr/bin/env python3
"""Promote current ferry-only Kerama routes for Tokashiki and Zamami villages."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path("data/v5_ship_playable_kerama_batch_official.json")


def hm(value: str) -> int:
    hour, minute = value.replace("：", ":").split(":")
    return int(hour) * 60 + int(minute)


def route(route_id: str, operator: str, origin: str, destination: str, fare: int, source_urls: list[str], note: str) -> dict:
    return {
        "routeId": route_id,
        "operator": operator,
        "routeName": f"{origin}・{destination}",
        "origin": origin,
        "destination": destination,
        "distanceKm": None,
        "routeClass": "island_public_ferry",
        "revealPolicy": "no_reveal",
        "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        "fare": {
            "currency": "JPY",
            "adultPassengerFare": {"amount": fare},
            "sourceUrls": source_urls,
            "notes": note,
        },
        "servicePatterns": [],
    }


def trip(route_id: str, operator: str, no: int, vessel: str, origin: str, destination: str, dep: str, arr: str, source_url: str) -> dict:
    dep_min = hm(dep)
    arr_min = hm(arr)
    return {
        "tripId": f"{route_id}_{no:03d}",
        "routeId": route_id,
        "operator": operator,
        "serviceNo": str(no),
        "vessel": vessel,
        "origin": origin,
        "destination": destination,
        "departure": dep,
        "arrival": arr,
        "departureMinute": dep_min,
        "arrivalMinute": arr_min,
        "durationMinutes": arr_min - dep_min,
        "calendar": {"type": "daily"},
        "sourceUrl": source_url,
    }


def main() -> None:
    retrieved_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    tokashiki_page = "https://www.vill.tokashiki.okinawa.jp/soshiki/sitekanri/5/2/1365.html"
    tokashiki_pdf = "https://www.vill.tokashiki.okinawa.jp/material/files/group/1/20260408.pdf"
    zamami_pdf = "https://www.vill.zamami.okinawa.jp/ship/2026/05/?action_web_ferry_export_pdf=1&month=5&year=2026"
    zamami_fare = "https://www.vill.zamami.okinawa.jp/userfiles/files/sempaku/fee_20260101.pdf"
    tokashiki_note = "Official Tokashiki Village timetable/fare page and May 2026 operation PDF. Current V5 collection date 2026-05-21 has Marine Liner Tokashiki suspended for cleaning dock, so this batch promotes only Ferry Tokashiki. Adult one-way fare is 1,690 JPY plus the 100 JPY environmental cooperation tax collected from adult/high-school-and-older passengers. Child/group/discount fares, cargo, vehicles, disruption decisions, and non-current monthly exceptions are excluded."
    zamami_note = "Official Zamami Village May 2026 ship schedule and 2026-01-01 fare revision PDF. Current V5 collection date 2026-05-21 uses the 7-31 May Ferry Zamami schedule. This batch promotes Ferry Zamami only because Queen Zamami has a different vessel fare and the current ship bundle supports one fare per directional route. Child/group/disabled/resident fares, vehicles, express-vessel fares, baggage, and disruption decisions are excluded."
    routes = [
        route("tokashiki_naha_tokashiki_082_out", "渡嘉敷村", "那覇泊港", "渡嘉敷港", 1790, [tokashiki_page, tokashiki_pdf], tokashiki_note),
        route("tokashiki_naha_tokashiki_083_back", "渡嘉敷村", "渡嘉敷港", "那覇泊港", 1790, [tokashiki_page, tokashiki_pdf], tokashiki_note),
        route("zamami_naha_zamami_aka_078_out", "座間味村", "那覇泊港", "座間味港", 2900, [zamami_pdf, zamami_fare], zamami_note),
        route("zamami_naha_zamami_aka_079_back", "座間味村", "座間味港", "那覇泊港", 2900, [zamami_pdf, zamami_fare], zamami_note),
        route("zamami_naha_zamami_aka_080_out", "座間味村", "座間味港", "阿嘉港", 400, [zamami_pdf, zamami_fare], zamami_note),
        route("zamami_naha_zamami_aka_081_back", "座間味村", "阿嘉港", "座間味港", 400, [zamami_pdf, zamami_fare], zamami_note),
    ]
    trips = [
        trip(routes[0]["routeId"], "渡嘉敷村", 1, "フェリーとかしき", "那覇泊港", "渡嘉敷港", "10:00", "11:10", tokashiki_pdf),
        trip(routes[1]["routeId"], "渡嘉敷村", 2, "フェリーとかしき", "渡嘉敷港", "那覇泊港", "16:00", "17:10", tokashiki_pdf),
        trip(routes[2]["routeId"], "座間味村", 3, "フェリーざまみ", "那覇泊港", "座間味港", "10:00", "12:00", zamami_pdf),
        trip(routes[5]["routeId"], "座間味村", 4, "フェリーざまみ", "阿嘉港", "座間味港", "11:45", "12:00", zamami_pdf),
        trip(routes[4]["routeId"], "座間味村", 5, "フェリーざまみ", "座間味港", "阿嘉港", "15:00", "15:15", zamami_pdf),
        trip(routes[3]["routeId"], "座間味村", 6, "フェリーざまみ", "座間味港", "那覇泊港", "15:00", "17:00", zamami_pdf),
    ]
    payload = {
        "schema": "onichase.v5.ship.officialSource.v1",
        "operator": "慶良間諸島村営船",
        "operatorId": "kerama_village_ferries",
        "retrievedAt": retrieved_at,
        "sourceUrls": [tokashiki_page, tokashiki_pdf, zamami_pdf, zamami_fare],
        "ports": {},
        "routes": routes,
        "trips": trips,
        "summary": {
            "routeGroupCount": 2,
            "directionalRouteCount": len(routes),
            "explicitTripCount": len(trips),
            "playablePromotionStatus": "timetable_fare_ports_collected_connectors_pending",
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} routes={len(routes)} trips={len(trips)} retrievedAt={retrieved_at}")


if __name__ == "__main__":
    main()
