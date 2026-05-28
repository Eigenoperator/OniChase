#!/usr/bin/env python3
"""Collect source-backed remote/small-island bus slices for V5 ship-port access.

This is a source-layer collector only. It does not touch the heavy V5 GTFS bundle,
planner tiles, or connector runtime.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data/v5_remote_small_island_bus_source.json"
DOCS_PATH = ROOT / "docs/data/v5_remote_small_island_bus_source.json"
AUDIT_PATH = ROOT / "data/v5_remote_small_island_ship_port_bus_source_audit.json"
DOCS_AUDIT_PATH = ROOT / "docs/data/v5_remote_small_island_ship_port_bus_source_audit.json"
NON_RUNTIME_ROUTE_CODES = {
    "wajima_local_bus_port_candidate",
    "hirado_takushima_fureai_bus_candidate",
}


def trip(trip_id: str, *pairs: tuple[str, str], service_days: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tripId": trip_id,
        "stopTimes": [{"stopName": name, "time": time} for name, time in pairs],
    }
    if service_days:
        payload["serviceDays"] = service_days
    return payload


def route(route_code: str, route_name: str, operator: str, source_url: str, notes: list[str]) -> dict[str, Any]:
    return {
        "sourceKind": "official_remote_ship_port_bus_source",
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

def infer_service_profile(route_item: dict[str, Any]) -> dict[str, Any]:
    service_days = str(route_item.get("serviceDays") or "daily").lower()
    trip_service_days = {
        str(trip.get("serviceDays") or "").lower()
        for direction in route_item.get("directions", [])
        for trip in direction.get("trips", [])
        if trip.get("serviceDays")
    }
    labels = {service_days, *trip_service_days}
    supports_weekday = True
    supports_weekend = True
    weekend_detail = "saturday_sunday"
    if any(label.startswith("weekday") or label == "weekday" for label in labels):
        supports_weekend = False
        weekend_detail = "not_scheduled"
    if "monday_to_saturday" in labels:
        supports_weekend = True
        weekend_detail = "saturday_only"
    if any("weekend" in label for label in labels):
        supports_weekday = False
        supports_weekend = True
    if any(label.startswith("daily") or label == "daily" or label == "seasonal_variants" for label in labels):
        supports_weekday = True
        supports_weekend = True
        weekend_detail = "saturday_sunday"
    supported = []
    if supports_weekday:
        supported.append("weekday")
    if supports_weekend:
        supported.append("weekend")
    return {
        "calendarPrecision": "weekday_weekend",
        "defaultPlayDayType": "weekday",
        "supportedDayTypes": supported,
        "weekendCoverage": weekend_detail if supports_weekend else "not_scheduled",
        "seasonalVariant": "seasonal" in service_days,
        "displayPolicy": "use_weekday_default_only_keep_weekend_as_source_data",
    }


def enrich_service_profiles(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for item in routes:
        copy = dict(item)
        copy["serviceProfile"] = infer_service_profile(copy)
        enriched.append(copy)
    return enriched


def preserve_reviewed_stop_coordinates(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    reviewed_by_name = {}
    for stop in existing.get("busStops", []):
        source = str(stop.get("coordinateSource", ""))
        if source and "manual approximate" not in source and "needs precise stop review" not in source:
            reviewed_by_name[str(stop.get("name"))] = stop
    if not reviewed_by_name:
        return incoming
    copy = dict(incoming)
    stops = []
    for stop in incoming.get("busStops", []):
        reviewed = reviewed_by_name.get(str(stop.get("name")))
        if reviewed:
            merged_stop = dict(stop)
            merged_stop["lat"] = reviewed.get("lat")
            merged_stop["lon"] = reviewed.get("lon")
            merged_stop["coordinateSource"] = reviewed.get("coordinateSource")
            stops.append(merged_stop)
        else:
            stops.append(stop)
    copy["busStops"] = stops
    return copy


def build_routes() -> list[dict[str, Any]]:
    niijima_pdf = "https://niijima.com/shoukai/access/files/bustimetabale202511.pdf"
    niijima_page = "https://niijima.com/shoukai/access/tounai.html"
    niijima_navitime_b_pier = "https://www.navitime.co.jp/diagram/bus/00565807/00087150/1/"
    nishinoshima_pdf = "https://www.town.nishinoshima.shimane.jp/files/original/20260220140915710489010da.pdf"
    nishinoshima_page = "https://www.town.nishinoshima.shimane.jp/bunya/b_kurashi/b_kotsu/47"
    suo_page = "https://www.town.suo-oshima.lg.jp/soshiki/38/11883.html"
    suo_pdf = "https://www.town.suo-oshima.lg.jp/uploaded/attachment/22673.pdf"
    okamura_page = "https://new-tobisimakan.com/access/"
    okamura_pdf = "https://new-tobisimakan.sakura.ne.jp/wp/wp-content/uploads/2025/10/baa4c8071da75cba6b63539cd582adc5.pdf"
    iki_page = "https://iki-kotsu.com/regular-route-bus/"
    iki_indouji_pdf = "https://iki-kotsu.com/pdf/indouziBusTime.pdf"
    kumejima_pdf = "https://www.town.kumejima.okinawa.jp/docs/bus/file_contents/61630.pdf"
    kumejima_page = "https://www.town.kumejima.okinawa.jp/docs/bus/"
    munakata_jorudan = "https://www.jorudan.co.jp/bus/rosen/timetable/%E5%AE%97%E6%96%B9%E6%B8%AF%E3%80%94%E7%80%AC%E6%88%B8%E5%86%85%E6%B5%B7%E4%BA%A4%E9%80%9A%E3%80%95/%E5%AE%97%E6%96%B9%E7%B7%9A/%E5%AE%97%E6%96%B9/"
    munakata_busmap = "https://busmap.info/route/105869/"
    teshima_page = "https://teshima-navi.jp/access/"
    hirado_oshima_page = "https://www.city.hirado.nagasaki.jp/kurashi/life/sumai/koutu/bus/bus02.html"
    aguni_page = "https://www.vill.aguni.okinawa.jp/soshiki/senpaku/32.html"
    aguni_pdf = "https://www.vill.aguni.okinawa.jp/material/files/group/1/basu_unnkouzikokuhyou_3.pdf"
    nakajima_bus_page = "https://mb.jorudan.co.jp/os/bus/3805/"
    wajima_bus_pdf = "https://www.city.wajima.ishikawa.jp/docs/2013032700181/file_contents/02_nishiho_211101.pdf"
    saihi_shinkamigoto_notice = "https://www.bus.saihigroup.co.jp/information/45177.html"
    saihi_arikawa_terminal_pdf = "https://www.bus.saihigroup.co.jp/cms/wp-content/uploads/new-jikoku/%E3%81%82/%E6%9C%89%E5%B7%9D%E6%B8%AF%E3%82%BF%E3%83%BC%E3%83%9F%E3%83%8A%E3%83%AB%E5%85%B1%E9%80%9A.pdf"
    ayukawa_miyakou = "https://transfer.navitime.biz/miyagikotsu/pc/diagram/BusDiagram?course=0006300786&orvCode=00331642&stopNo=1"
    ayukawa_pref_pdf = "https://www.pref.miyagi.jp/documents/61103/siryou3.pdf"
    shimama_tanegashima_bus = "https://www.furusato-tanegashima.net/access/bus.html"
    shimama_navitime = "https://www.navitime.co.jp/bus/company/00002436/route/00098812/"
    kaizu_jorudan = "https://www.jorudan.co.jp/bus/rosen/timetable/%E8%B2%9D%E6%B4%A5%E6%B8%AF%E5%BE%85%E5%90%88%E6%89%80%E5%89%8D%E3%80%94%E4%BA%94%E5%B3%B6%E5%B8%82%E3%82%B3%E3%83%9F%E3%83%A5%E3%83%8B%E3%83%86%E3%82%A3%E3%80%95/"
    kaizu_city_pdf = "https://www.city.goto.nagasaki.jp/s050/010/020/030/040/miiraku.pdf"
    hirado_fureai_page = "https://www.city.hirado.nagasaki.jp/kurashi/life/sumai/koutu/bus/bus01.html"
    gounokubi_yahoo = "https://transit.yahoo.co.jp/station/865472"
    tokashiki_page = "https://www.tokashikibus.jp/timetable/"
    tokashiki_gtfs_port = "https://bus-routes.net/gtfs_line.php?roid=12671"
    tokashiki_gtfs_beach = "https://bus-routes.net/gtfs_line.php?roid=12672"
    sakurajima_city_pdf = "https://www.kotsu-city-kagoshima.jp/wp/wp-content/uploads/2023/07/6e377243eff8ef2be1c99f456cc6b31d.pdf"
    sakurajima_ferry_page = "https://www.city.kagoshima.lg.jp/sakurajima-ferry/koro-jikoku/timetable.html"
    shinkamigoto_page = "https://official.shinkamigoto.net/goto_kurashi_full.php?eid=00683&r=1"
    saihi_fare_page = "https://www.bus.saihigroup.co.jp/information/15918.html"
    saihi_route_pdf = "https://www.bus.saihigroup.co.jp/cms/wp-content/uploads/2025/03/2026.4%E6%94%B9%E6%AD%A3%E7%94%A8-%E6%96%B0%E4%B8%8A%E4%BA%94%E5%B3%B6%E5%9C%B0%E5%8C%BA%E9%85%8D%E5%B8%83%E7%94%A8%E6%99%82%E5%88%BB%E8%A1%A8%E3%83%87%E3%83%BC%E3%82%BF%EF%BC%88%E4%BF%AE%E6%AD%A3%EF%BC%89.pdf"
    saihi_tomosumi_pdf = "https://www.bus.saihigroup.co.jp/cms/wp-content/uploads/new-jikoku/%E3%81%A8/%E5%8F%8B%E4%BD%8F%E5%85%B1%E9%80%9A.pdf"
    saihi_tomosumi_kaigan_pdf = "https://www.bus.saihigroup.co.jp/cms/wp-content/uploads/new-jikoku/%E3%81%A8/%E5%8F%8B%E4%BD%8F%E6%B5%B7%E5%B2%B8%E5%85%B1%E9%80%9A.pdf"

    return [
        route(
            "niijima_fureai_bus_b_pier_to_honson",
            "ふれあいバス（B堤駐車場 ⇔ 本村・住民センター）",
            "新島村",
            niijima_pdf,
            [
                "Niijima Village official island-transport page publishes the free ふれあいバス and official timetable PDF.",
                "The official PDF image/table confirms the B堤駐車場 07:55, 11:15, and 16:15 port-side rows; NAVITIME's stop timetable cross-checks the same B堤駐車場 departures.",
                "Summer times in parentheses are stored as separate limited-season trips pending full service-calendar modeling.",
            ],
        )
        | {
            "sourceUrls": [niijima_page, niijima_pdf, niijima_navitime_b_pier],
            "serviceDays": "daily",
            "adultFareYen": 0,
            "promotionStatus": "source_collected_needs_stop_coordinate_review",
            "portNames": ["新島港"],
            "connectorAnchorStopNames": ["B堤駐車場"],
            "busStops": [
                {"name": "B堤駐車場", "lat": 34.377, "lon": 139.257, "coordinateSource": "docs/data/v5_ship_map.geojson:新島港; pending exact bus-stop review"},
                {"name": "本村診療所", "lat": 34.376, "lon": 139.257, "coordinateSource": "manual approximate from Niijima official route context; needs precise stop review"},
                {"name": "住民センター", "lat": 34.375, "lon": 139.257, "coordinateSource": "manual approximate from Niijima official route context; needs precise stop review"},
                {"name": "健康センター", "lat": 34.374, "lon": 139.257, "coordinateSource": "manual approximate from Niijima official route context; needs precise stop review"},
            ],
            "directions": [
                {
                    "direction": "from_b_pier",
                    "trips": [
                        trip("niijima_fureai_b_pier_001", ("B堤駐車場", "7:55"), ("本村診療所", "7:58"), ("住民センター", "8:03"), ("健康センター", "8:05")),
                        trip("niijima_fureai_b_pier_summer_001", ("B堤駐車場", "8:15"), ("本村診療所", "8:18"), ("住民センター", "8:23"), ("健康センター", "8:25"), service_days="summer_linked_to_nishiki_ship_period"),
                        trip("niijima_fureai_b_pier_002", ("B堤駐車場", "11:15"), ("住民センター", "11:18"), ("健康センター", "11:23"), ("若郷診療所前", "11:25")),
                        trip("niijima_fureai_b_pier_003", ("B堤駐車場", "16:15"), ("住民センター", "16:20"), ("健康センター", "16:22"), ("若郷診療所前", "16:40")),
                    ],
                }
            ],
        },
        route(
            "nishinoshima_town_bus_beppu_urago",
            "西ノ島町営バス（別府交通センター ⇔ 浦郷）",
            "西ノ島町",
            nishinoshima_pdf,
            [
                "Nishinoshima official town-bus page publishes the 2026 town-bus timetable, fare, and stop map.",
                "This source slice models the ordinary 別府交通センター ⇔ 浦郷 rows useful for ferry-port access at 別府港.",
                "Seasonal/marked service exceptions remain source-visible in the PDF and should be refined before runtime promotion.",
            ],
        )
        | {
            "sourceUrls": [nishinoshima_page, nishinoshima_pdf],
            "serviceDays": "daily_with_source_marked_exceptions",
            "adultFareYen": 200,
            "promotionStatus": "source_collected_needs_calendar_refinement",
            "portNames": ["西ノ島"],
            "connectorAnchorStopNames": ["別府交通センター"],
            "busStops": [
                {"name": "別府交通センター", "lat": 36.10765, "lon": 133.041493, "coordinateSource": "docs/data/v5_ship_map.geojson:西ノ島 / 別府港"},
                {"name": "浦郷", "lat": 36.0975, "lon": 132.997, "coordinateSource": "manual approximate from official Nishinoshima timetable route; needs precise stop review"},
            ],
            "directions": [
                {
                    "direction": "to_beppu",
                    "trips": [
                        trip("nishinoshima_urago_beppu_001", ("浦郷", "7:01"), ("別府交通センター", "7:22")),
                        trip("nishinoshima_urago_beppu_002", ("浦郷", "7:45"), ("別府交通センター", "8:06")),
                        trip("nishinoshima_urago_beppu_003", ("浦郷", "9:38"), ("別府交通センター", "10:00")),
                        trip("nishinoshima_urago_beppu_004", ("浦郷", "10:14"), ("別府交通センター", "10:36")),
                        trip("nishinoshima_urago_beppu_005", ("浦郷", "11:38"), ("別府交通センター", "12:00")),
                        trip("nishinoshima_urago_beppu_006", ("浦郷", "13:09"), ("別府交通センター", "13:33")),
                        trip("nishinoshima_urago_beppu_007", ("浦郷", "14:52"), ("別府交通センター", "15:14")),
                        trip("nishinoshima_urago_beppu_008", ("浦郷", "16:38"), ("別府交通センター", "17:02")),
                        trip("nishinoshima_urago_beppu_009", ("浦郷", "17:13"), ("別府交通センター", "17:34")),
                        trip("nishinoshima_urago_beppu_010", ("浦郷", "18:33"), ("別府交通センター", "18:54")),
                    ],
                },
                {
                    "direction": "to_urago",
                    "trips": [
                        trip("nishinoshima_beppu_urago_001", ("別府交通センター", "7:50"), ("浦郷", "8:12")),
                        trip("nishinoshima_beppu_urago_002", ("別府交通センター", "8:40"), ("浦郷", "9:01")),
                        trip("nishinoshima_beppu_urago_003", ("別府交通センター", "10:20"), ("浦郷", "10:42")),
                        trip("nishinoshima_beppu_urago_004", ("別府交通センター", "11:17"), ("浦郷", "11:39")),
                        trip("nishinoshima_beppu_urago_005", ("別府交通センター", "12:20"), ("浦郷", "12:42")),
                        trip("nishinoshima_beppu_urago_006", ("別府交通センター", "14:01"), ("浦郷", "14:25")),
                        trip("nishinoshima_beppu_urago_007", ("別府交通センター", "15:36"), ("浦郷", "15:58")),
                        trip("nishinoshima_beppu_urago_008", ("別府交通センター", "17:26"), ("浦郷", "17:50")),
                        trip("nishinoshima_beppu_urago_009", ("別府交通センター", "18:32"), ("浦郷", "18:53")),
                        trip("nishinoshima_beppu_urago_010", ("別府交通センター", "19:08"), ("浦郷", "19:30")),
                    ],
                },
            ],
        },
        route(
            "suo_oshima_bocho_bus_kuka_obatake",
            "防長バス 大島本線（周防久賀 ⇔ 大畠駅）",
            "防長交通",
            suo_pdf,
            [
                "Suo-Oshima official transport page publishes the 2026-04-01 防長バス 大島本線 timetable.",
                "周防久賀 is the ordinary route-bus stop nearest the 久賀 ferry-port area; exact pier-to-stop walking connector still needs coordinate review.",
            ],
        )
        | {
            "sourceUrls": [suo_page, suo_pdf],
            "serviceDays": "weekday",
            "promotionStatus": "source_collected_needs_port_stop_coordinate_review",
            "portNames": ["周防大島久賀港"],
            "connectorAnchorStopNames": ["周防久賀"],
            "busStops": [
                {"name": "周防久賀", "lat": 33.944937, "lon": 132.272673, "coordinateSource": "docs/data/v5_ship_map.geojson:周防大島久賀港; nearest bus stop needs precise review"},
                {"name": "大畠駅", "lat": 33.962, "lon": 132.181, "coordinateSource": "manual station coordinate seed; needs precise bus-stop review"},
            ],
            "directions": [
                {
                    "direction": "to_kuka",
                    "trips": [
                        trip("suo_oshima_obatake_kuka_wd_001", ("大畠駅", "7:50"), ("周防久賀", "8:12")),
                        trip("suo_oshima_obatake_kuka_wd_002", ("大畠駅", "9:07"), ("周防久賀", "9:28")),
                        trip("suo_oshima_obatake_kuka_wd_003", ("大畠駅", "11:18"), ("周防久賀", "11:39")),
                        trip("suo_oshima_obatake_kuka_wd_004", ("大畠駅", "13:18"), ("周防久賀", "13:39")),
                        trip("suo_oshima_obatake_kuka_wd_005", ("大畠駅", "15:00"), ("周防久賀", "15:21")),
                        trip("suo_oshima_obatake_kuka_wd_006", ("大畠駅", "17:18"), ("周防久賀", "17:40")),
                        trip("suo_oshima_obatake_kuka_wd_007", ("大畠駅", "20:26"), ("周防久賀", "20:47")),
                    ],
                },
                {
                    "direction": "to_obatake",
                    "trips": [
                        trip("suo_oshima_kuka_obatake_wd_001", ("周防久賀", "7:04"), ("大畠駅", "7:25")),
                        trip("suo_oshima_kuka_obatake_wd_002", ("周防久賀", "8:37"), ("大畠駅", "9:02")),
                        trip("suo_oshima_kuka_obatake_wd_003", ("周防久賀", "10:16"), ("大畠駅", "10:44")),
                        trip("suo_oshima_kuka_obatake_wd_004", ("周防久賀", "12:36"), ("大畠駅", "12:55")),
                        trip("suo_oshima_kuka_obatake_wd_005", ("周防久賀", "15:57"), ("大畠駅", "16:34")),
                        trip("suo_oshima_kuka_obatake_wd_006", ("周防久賀", "17:08"), ("大畠駅", "17:39")),
                        trip("suo_oshima_kuka_obatake_wd_007", ("周防久賀", "18:53"), ("大畠駅", "19:05")),
                    ],
                },
            ],
        },
        route(
            "suo_oshima_town_bus_ihota_hirano",
            "町営バス一般混乗型スクールバス油田森野線（伊保田港 ⇔ 周防平野）",
            "周防大島町",
            suo_pdf,
            [
                "Suo-Oshima official transport page publishes the 2025-03-15 town-bus general-use school-bus 油田森野線 timetable.",
                "The PDF states the service can be used by the general public; this source slice uses 伊保田港 rows directly.",
            ],
        )
        | {
            "sourceUrls": [suo_page, suo_pdf],
            "serviceDays": "daily_with_weekday_weekend_variants",
            "promotionStatus": "source_collected_needs_calendar_refinement",
            "portNames": ["伊保田", "伊保田港"],
            "busStops": [
                {"name": "伊保田港", "lat": 33.9442177, "lon": 132.4391337, "coordinateSource": "docs/data/v5_ship_map.geojson:伊保田港"},
                {"name": "周防平野", "lat": 33.902, "lon": 132.36, "coordinateSource": "manual approximate from official Suo-Oshima route context; needs precise stop review"},
            ],
            "directions": [
                {
                    "direction": "to_hirano",
                    "trips": [
                        trip("suo_oshima_ihota_hirano_wd_001", ("伊保田港", "7:26"), ("周防平野", "7:50"), service_days="weekday"),
                        trip("suo_oshima_ihota_hirano_wd_002", ("伊保田港", "9:17"), ("周防平野", "9:41"), service_days="weekday"),
                        trip("suo_oshima_ihota_hirano_wd_003", ("伊保田港", "14:40"), ("周防平野", "15:04"), service_days="weekday"),
                        trip("suo_oshima_ihota_hirano_wd_004", ("伊保田港", "17:44"), ("周防平野", "18:08"), service_days="weekday"),
                        trip("suo_oshima_ihota_hirano_hol_001", ("伊保田港", "7:26"), ("周防平野", "7:50"), service_days="weekend_holiday"),
                        trip("suo_oshima_ihota_hirano_hol_002", ("伊保田港", "9:19"), ("周防平野", "9:43"), service_days="weekend_holiday"),
                        trip("suo_oshima_ihota_hirano_hol_003", ("伊保田港", "14:01"), ("周防平野", "14:25"), service_days="weekend_holiday"),
                    ],
                },
                {
                    "direction": "to_ihota",
                    "trips": [
                        trip("suo_oshima_hirano_ihota_wd_001", ("周防平野", "8:32"), ("伊保田港", "8:56"), service_days="weekday"),
                        trip("suo_oshima_hirano_ihota_wd_002", ("周防平野", "12:07"), ("伊保田港", "12:31"), service_days="weekday"),
                        trip("suo_oshima_hirano_ihota_wd_003", ("周防平野", "15:18"), ("伊保田港", "15:42"), service_days="weekday"),
                        trip("suo_oshima_hirano_ihota_wd_004", ("周防平野", "16:23"), ("伊保田港", "16:47"), service_days="weekday"),
                        trip("suo_oshima_hirano_ihota_wd_005", ("周防平野", "18:15"), ("伊保田港", "18:39"), service_days="weekday"),
                        trip("suo_oshima_hirano_ihota_hol_001", ("周防平野", "9:55"), ("伊保田港", "10:19"), service_days="weekend_holiday"),
                        trip("suo_oshima_hirano_ihota_hol_002", ("周防平野", "14:30"), ("伊保田港", "14:54"), service_days="weekend_holiday"),
                    ],
                },
            ],
        },
        route(
            "okamura_tobishima_kona_mitarai_hiro",
            "瀬戸内産交バス（小長港 ⇔ 御手洗港・広駅）",
            "瀬戸内産交",
            okamura_pdf,
            [
                "Yutaka Uminoeki Tobishimakan access page links the Setouchi Sanko bus timetable for the Tobishima access corridor.",
                "This route does not directly start at 岡村港; it is a source-backed onward-access candidate after the ferry/bridge-side access is reviewed.",
                "Do not promote as a 2 km 岡村港 connector until the 岡村港 to 小長港/御手洗 access relationship is explicitly modeled.",
            ],
        )
        | {
            "sourceUrls": [okamura_page, okamura_pdf],
            "serviceDays": "weekday_and_holiday_variants",
            "promotionStatus": "source_collected_not_direct_port_connector",
            "portNames": ["岡村港"],
            "connectorAnchorStopNames": ["小長港"],
            "busStops": [
                {"name": "小長港", "lat": 34.183, "lon": 132.852, "coordinateSource": "manual approximate from Tobishima access source; needs precise stop review"},
                {"name": "御手洗港", "lat": 34.184, "lon": 132.866, "coordinateSource": "manual approximate from Tobishima access source; needs precise stop review"},
                {"name": "広駅", "lat": 34.228, "lon": 132.628, "coordinateSource": "manual station coordinate seed; needs precise bus-stop review"},
            ],
            "directions": [
                {
                    "direction": "to_mitarai_weekday",
                    "trips": [
                        trip("okamura_kona_mitarai_wd_001", ("小長港", "9:09"), ("御手洗港", "9:14"), service_days="weekday"),
                        trip("okamura_kona_mitarai_wd_002", ("小長港", "10:34"), ("御手洗港", "10:39"), service_days="weekday"),
                        trip("okamura_kona_mitarai_wd_003", ("小長港", "11:54"), ("御手洗港", "11:59"), service_days="weekday"),
                        trip("okamura_kona_mitarai_wd_004", ("小長港", "13:44"), ("御手洗港", "13:49"), service_days="weekday"),
                        trip("okamura_kona_mitarai_wd_005", ("小長港", "15:59"), ("御手洗港", "16:04"), service_days="weekday"),
                    ],
                },
                {
                    "direction": "to_hiro_weekday",
                    "trips": [
                        trip("okamura_mitarai_hiro_wd_001", ("御手洗港", "10:16"), ("小長港", "10:21"), ("広駅", "11:40"), service_days="weekday"),
                        trip("okamura_mitarai_hiro_wd_002", ("御手洗港", "11:26"), ("小長港", "11:31"), ("広駅", "12:50"), service_days="weekday"),
                        trip("okamura_mitarai_hiro_wd_003", ("御手洗港", "13:16"), ("小長港", "13:21"), ("広駅", "14:40"), service_days="weekday"),
                        trip("okamura_mitarai_hiro_wd_004", ("御手洗港", "16:46"), ("小長港", "16:51"), ("広駅", "18:10"), service_days="weekday"),
                    ],
                },
            ],
        },
        route(
            "iki_kotsu_indouji_ashibe",
            "壱岐交通（印通寺 ⇔ 芦辺）",
            "壱岐交通",
            iki_indouji_pdf,
            [
                "Iki Kotsu official route-bus page publishes the 印通寺 bus timetable PDF.",
                "This first playable source slice uses explicit 印通寺 ⇔ 芦辺 rows from the official PDF; 印通寺港 and 印通寺 are adjacent port-side stops and need final coordinate matching before runtime connector promotion.",
            ],
        )
        | {
            "sourceUrls": [iki_page, iki_indouji_pdf],
            "serviceDays": "daily",
            "promotionStatus": "source_collected_needs_port_stop_coordinate_review",
            "portNames": ["印通寺"],
            "busStops": [
                {"name": "印通寺", "lat": 33.741574, "lon": 129.754972, "coordinateSource": "docs/data/v5_ship_map.geojson:印通寺; exact bus stop/port terminal matching needed"},
                {"name": "芦辺", "lat": 33.800, "lon": 129.722, "coordinateSource": "manual approximate from Iki Kotsu official route context; needs precise stop review"},
            ],
            "directions": [
                {
                    "direction": "to_ashibe",
                    "trips": [
                        trip("iki_indouji_ashibe_001", ("印通寺", "7:30"), ("芦辺", "7:50")),
                        trip("iki_indouji_ashibe_002", ("印通寺", "10:35"), ("芦辺", "10:57")),
                        trip("iki_indouji_ashibe_003", ("印通寺", "12:18"), ("芦辺", "12:40")),
                        trip("iki_indouji_ashibe_004", ("印通寺", "17:35"), ("芦辺", "17:50")),
                    ],
                }
            ],
        },
        route(
            "kumejima_town_bus_kanegusuku_honnomori",
            "久米島町営バス（兼城港ターミナル前 ⇔ ほんのもり前）",
            "久米島町",
            kumejima_pdf,
            [
                "Kumejima Town official bus PDF lists scheduled passage times for 兼城港（ターミナル前）.",
                "This first playable source slice keeps explicit 兼城港ターミナル前 ⇔ ほんのもり前 adjacent timetable rows from the official PDF.",
            ],
        )
        | {
            "sourceUrls": [kumejima_page, kumejima_pdf],
            "serviceDays": "daily",
            "promotionStatus": "source_collected_needs_calendar_refinement",
            "portNames": ["兼城港"],
            "busStops": [
                {"name": "兼城港（ターミナル前）", "lat": 26.3417, "lon": 126.7637, "coordinateSource": "docs/data/v5_ship_map.geojson:兼城港"},
                {"name": "ほんのもり前", "lat": 26.342, "lon": 126.766, "coordinateSource": "manual approximate from Kumejima official bus route context; needs precise stop review"},
            ],
            "directions": [
                {
                    "direction": "from_kanegusuku",
                    "trips": [
                        trip("kumejima_kanegusuku_honnomori_001", ("兼城港（ターミナル前）", "8:02"), ("ほんのもり前", "8:04")),
                        trip("kumejima_kanegusuku_honnomori_002", ("兼城港（ターミナル前）", "13:12"), ("ほんのもり前", "13:14")),
                        trip("kumejima_kanegusuku_honnomori_003", ("兼城港（ターミナル前）", "17:52"), ("ほんのもり前", "17:54")),
                    ],
                }
            ],
        },
        route(
            "setonaikai_kotsu_munakata_miyaura",
            "瀬戸内海交通 宗方線（宗方港 ⇔ 宮浦港）",
            "瀬戸内海交通",
            munakata_jorudan,
            [
                "Imabari public-transport planning material and public bus datasets identify the 瀬戸内海交通 宗方線 between 宗方港 and 宮浦港.",
                "This first playable source slice uses published public timetable rows for the 宗方港 ⇔ 宮浦港 route; replace with an operator PDF if 瀬戸内海交通 publishes a current machine-readable timetable.",
            ],
        )
        | {
            "sourceUrls": [munakata_jorudan, munakata_busmap, "https://www.city.imabari.ehime.jp/chiiki/kokyokotu/keikaku/keikaku_202108.pdf"],
            "serviceDays": "daily",
            "promotionStatus": "source_collected_needs_operator_pdf_confirmation",
            "portNames": ["宗方港"],
            "busStops": [
                {"name": "宗方港", "lat": 34.2031092, "lon": 132.9428741, "coordinateSource": "docs/data/v5_ship_map.geojson:宗方港"},
                {"name": "宮浦港", "lat": 34.249, "lon": 133.004, "coordinateSource": "manual approximate from Omishima route context; needs precise stop review"},
            ],
            "directions": [
                {"direction": "to_miyaura", "trips": [
                    trip("munakata_miyaura_001", ("宗方港", "8:00"), ("宮浦港", "8:25")),
                    trip("munakata_miyaura_002", ("宗方港", "8:57"), ("宮浦港", "9:22")),
                    trip("munakata_miyaura_003", ("宗方港", "10:32"), ("宮浦港", "10:57")),
                    trip("munakata_miyaura_004", ("宗方港", "12:57"), ("宮浦港", "13:22")),
                    trip("munakata_miyaura_005", ("宗方港", "14:03"), ("宮浦港", "14:28")),
                    trip("munakata_miyaura_006", ("宗方港", "15:26"), ("宮浦港", "15:51")),
                    trip("munakata_miyaura_007", ("宗方港", "17:44"), ("宮浦港", "18:09")),
                ]},
                {"direction": "to_munakata", "trips": [
                    trip("miyaura_munakata_001", ("宮浦港", "7:26"), ("宗方港", "7:51")),
                    trip("miyaura_munakata_002", ("宮浦港", "8:11"), ("宗方港", "8:36")),
                    trip("miyaura_munakata_003", ("宮浦港", "9:55"), ("宗方港", "10:20")),
                    trip("miyaura_munakata_004", ("宮浦港", "12:20"), ("宗方港", "12:45")),
                    trip("miyaura_munakata_005", ("宮浦港", "14:49"), ("宗方港", "15:14")),
                    trip("miyaura_munakata_006", ("宮浦港", "17:05"), ("宗方港", "17:30")),
                    trip("miyaura_munakata_007", ("宮浦港", "17:55"), ("宗方港", "18:20")),
                ]},
            ],
        },
        route(
            "teshima_shuttle_ieura_karato",
            "豊島シャトルバス（家浦港 ⇔ 唐櫃港）",
            "土庄町コミュニティ / 豊島シャトルバス",
            teshima_page,
            [
                "Teshima official tourism access page publishes the island shuttle bus timetable between 家浦港 and 唐櫃港.",
                "This source slice uses the visible official tourism timetable rows; museum-closure and special-period exceptions need calendar refinement before runtime promotion.",
            ],
        )
        | {
            "sourceUrls": [teshima_page, "https://benesse-artsite.jp/uploads/teshima-bus_20250418.pdf"],
            "serviceDays": "daily_with_museum_closure_exceptions",
            "promotionStatus": "source_collected_needs_calendar_refinement",
            "portNames": ["家浦"],
            "busStops": [
                {"name": "家浦港", "lat": 34.4900759, "lon": 134.0609824, "coordinateSource": "docs/data/v5_ship_map.geojson:家浦"},
                {"name": "唐櫃港", "lat": 34.484, "lon": 134.089, "coordinateSource": "manual approximate from Teshima route context; needs precise stop review"},
            ],
            "directions": [
                {"direction": "to_karato", "trips": [
                    trip("teshima_ieura_karato_001", ("家浦港", "8:30"), ("唐櫃港", "8:47")),
                    trip("teshima_ieura_karato_002", ("家浦港", "10:05"), ("唐櫃港", "10:22")),
                    trip("teshima_ieura_karato_003", ("家浦港", "11:50"), ("唐櫃港", "12:07")),
                    trip("teshima_ieura_karato_004", ("家浦港", "13:18"), ("唐櫃港", "13:35")),
                    trip("teshima_ieura_karato_005", ("家浦港", "14:26"), ("唐櫃港", "14:43")),
                    trip("teshima_ieura_karato_006", ("家浦港", "15:11"), ("唐櫃港", "15:28")),
                    trip("teshima_ieura_karato_007", ("家浦港", "16:30"), ("唐櫃港", "16:47")),
                ]},
            ],
        },
        route(
            "hirado_oshima_bus_mato_yamazuji",
            "平戸市大島バス（的山港・神浦 source candidate）",
            "平戸市",
            hirado_oshima_page,
            [
                "Hirado official page states 大島バス is a scheduled route bus operating within 大島村 and publishes the current fare and timetable PDFs.",
                "This is kept as an official source candidate until the PDF table is extracted into endpoint stop-time rows for 的山港 and 神浦.",
            ],
        )
        | {
            "sourceUrls": [hirado_oshima_page],
            "serviceDays": "daily_with_weekday_only_variants",
            "adultFareYen": 100,
            "promotionStatus": "source_collected_needs_calendar_refinement",
            "portNames": ["的山港", "神浦"],
            "busStops": [
                {"name": "的山港", "lat": 33.486, "lon": 129.548, "coordinateSource": "docs/data/v5_ship_map.geojson:的山港"},
                {"name": "神浦", "lat": 33.2548582, "lon": 129.0946886, "coordinateSource": "docs/data/v5_ship_map.geojson:神浦"},
            ],
            "directions": [
                {"direction": "from_kounoura_to_matoyama", "trips": [
                    trip("hirado_oshima_kounoura_matoyama_001", ("神浦", "06:24"), ("的山港", "06:45")),
                    trip("hirado_oshima_kounoura_matoyama_002", ("神浦", "08:34"), ("的山港", "09:01")),
                    trip("hirado_oshima_kounoura_matoyama_003", ("神浦", "10:29"), ("的山港", "10:56")),
                    trip("hirado_oshima_kounoura_matoyama_004", ("神浦", "13:19"), ("的山港", "13:37")),
                    trip("hirado_oshima_kounoura_matoyama_005", ("神浦", "15:49"), ("的山港", "16:07")),
                ]},
                {"direction": "from_matoyama_to_kounoura", "trips": [
                    trip("hirado_oshima_matoyama_kounoura_001", ("的山港", "09:10"), ("神浦", "09:24")),
                    trip("hirado_oshima_matoyama_kounoura_002", ("的山港", "11:05"), ("神浦", "11:27")),
                    trip("hirado_oshima_matoyama_kounoura_003", ("的山港", "13:45"), ("神浦", "14:07")),
                    trip("hirado_oshima_matoyama_kounoura_004", ("的山港", "16:15"), ("神浦", "16:37")),
                    trip("hirado_oshima_matoyama_kounoura_005", ("的山港", "18:28"), ("神浦", "18:47")),
                ]},
            ],
        },
        route(
            "aguni_village_bus_port_line",
            "粟国村コミュニティバス アニー号（粟国港 ⇔ 浜コミュニティー）",
            "粟国村",
            aguni_pdf,
            [
                "Aguni Village official access page publishes village bus fare, route maps, and bus timetable PDF.",
                "The official timetable includes 粟国港 timed to the ferry arrival and a fixed route to 浜コミュニティー.",
            ],
        )
        | {
            "sourceUrls": [aguni_page, aguni_pdf],
            "serviceDays": "daily",
            "adultFareYen": 100,
            "promotionStatus": "source_collected_needs_calendar_refinement",
            "portNames": ["粟国港"],
            "busStops": [
                {"name": "粟国港", "lat": 26.585, "lon": 127.227, "coordinateSource": "manual approximate from Aguni official port/bus route context; needs precise stop review"},
                {"name": "浜コミュニティー", "lat": 26.584, "lon": 127.228, "coordinateSource": "manual approximate from Aguni official route context; needs precise stop review"},
            ],
            "directions": [
                {"direction": "from_port", "trips": [
                    trip("aguni_port_hama_001", ("粟国港", "12:00"), ("浜コミュニティー", "12:30")),
                ]},
                {"direction": "to_port", "trips": [
                    trip("aguni_hama_port_001", ("浜コミュニティー", "11:28"), ("粟国港", "11:30")),
                ]},
            ],
        },
        route(
            "nakajima_kisen_island_bus_candidate",
            "中島汽船バス（中島港 island-bus candidate）",
            "中島汽船バス",
            nakajima_bus_page,
            [
                "Public bus datasets list 中島汽船バス island loop routes from 中島港 and 神浦.",
                "Exact operator timetable rows still need extraction before playable runtime promotion.",
            ],
        )
        | {
            "sourceUrls": [nakajima_bus_page, "https://www.navitime.co.jp/bus/company/00001138/", "https://japantravel.navitime.com/en/area/jp/depArrTimeList/00185481/00185499/00041503?direction=up"],
            "serviceDays": "daily",
            "promotionStatus": "source_collected_needs_calendar_refinement",
            "portNames": ["中島"],
            "busStops": [
                {"name": "中島港", "lat": 33.975, "lon": 132.62, "coordinateSource": "manual approximate from Nakajima route context; needs precise stop review"},
                {"name": "神浦", "lat": 33.982, "lon": 132.59, "coordinateSource": "manual approximate from Nakajima-Kisen route context; needs precise stop review"},
                {"name": "神浦桟橋", "lat": 33.982, "lon": 132.588, "coordinateSource": "manual approximate from Nakajima-Kisen route context; needs precise stop review"},
            ],
            "directions": [
                {"direction": "nakajima_port_to_kounoura", "trips": [
                    trip("nakajima_port_kounoura_001", ("中島港", "07:25"), ("神浦", "07:34"), ("神浦桟橋", "07:37")),
                    trip("nakajima_port_kounoura_002", ("中島港", "07:52"), ("神浦", "08:01"), ("神浦桟橋", "08:04")),
                    trip("nakajima_port_kounoura_003", ("中島港", "08:28"), ("神浦", "08:37"), ("神浦桟橋", "08:40")),
                    trip("nakajima_port_kounoura_004", ("中島港", "14:00"), ("神浦", "14:09")),
                    trip("nakajima_port_kounoura_005", ("中島港", "15:20"), ("神浦", "15:29"), ("神浦桟橋", "15:32")),
                    trip("nakajima_port_kounoura_006", ("中島港", "15:40"), ("神浦", "15:49")),
                    trip("nakajima_port_kounoura_007", ("中島港", "16:25"), ("神浦", "16:34")),
                    trip("nakajima_port_kounoura_008", ("中島港", "18:10"), ("神浦", "18:19")),
                ]},
            ],
        },
        route(
            "wajima_local_bus_port_candidate",
            "輪島市コミュニティ/特急バス（輪島港 candidate）",
            "輪島市 / 北陸鉄道",
            wajima_bus_pdf,
            [
                "Wajima community and regional bus sources publish scheduled public bus service around Wajima.",
                "The exact 輪島港/マリンタウン port-side stop relationship needs review before playable runtime promotion.",
            ],
        )
        | {
            "sourceUrls": [wajima_bus_pdf, "https://www.hokutetsu.co.jp/_wp/wp-content/uploads/2025/03/Wajima-Ltd-Exp-Separate-Tap2ride.pdf"],
            "serviceDays": "source_candidate",
            "promotionStatus": "official_source_found_needs_port_stop_mapping",
            "portNames": ["輪島港"],
            "busStops": [
                {"name": "輪島港", "lat": 37.397, "lon": 136.900, "coordinateSource": "manual approximate from Wajima port context; needs precise stop review"},
            ],
            "directions": [],
        },
        route(
            "shinkamigoto_saihi_arikawa_candidate",
            "新上五島町内西肥バス（有川港 candidate）",
            "西肥自動車",
            saihi_shinkamigoto_notice,
            [
                "Saihi official information identifies 2025-08-25 Shinkamigoto route changes including 有川港 linked routes.",
                "Exact 有川港 endpoint rows need extraction from current Saihi stop/route PDFs before playable runtime promotion.",
            ],
        )
        | {
            "sourceUrls": [saihi_shinkamigoto_notice, saihi_arikawa_terminal_pdf, "https://mb.jorudan.co.jp/os/bus/4201/stop/232456.html"],
            "serviceDays": "daily_with_calendar_exceptions",
            "promotionStatus": "source_collected_needs_stop_sequence_review",
            "portNames": ["有川"],
            "busStops": [
                {"name": "有川港ターミナル", "lat": 32.984, "lon": 129.116, "coordinateSource": "manual approximate from Shinkamigoto route context; needs precise stop review"},
                {"name": "青方", "lat": 32.983, "lon": 129.073, "coordinateSource": "manual approximate from Saihi Shinkamigoto route context; needs precise stop review"},
                {"name": "鯛の浦", "lat": 32.992, "lon": 129.137, "coordinateSource": "manual approximate from Saihi Shinkamigoto route context; needs precise stop review"},
            ],
            "directions": [
                {"direction": "arikawa_to_aokata", "trips": [
                    trip("saihi_arikawa_aokata_001", ("有川港ターミナル", "08:04"), ("青方", "08:17")),
                    trip("saihi_arikawa_aokata_002", ("有川港ターミナル", "09:53"), ("青方", "10:06")),
                    trip("saihi_arikawa_aokata_003", ("有川港ターミナル", "12:37"), ("青方", "12:50")),
                    trip("saihi_arikawa_aokata_004", ("有川港ターミナル", "15:40"), ("青方", "15:53")),
                    trip("saihi_arikawa_aokata_005", ("有川港ターミナル", "16:50"), ("青方", "17:03")),
                ]},
                {"direction": "arikawa_to_tainoura", "trips": [
                    trip("saihi_arikawa_tainoura_001", ("有川港ターミナル", "06:36"), ("鯛の浦", "06:55")),
                    trip("saihi_arikawa_tainoura_002", ("有川港ターミナル", "07:30"), ("鯛の浦", "07:49")),
                    trip("saihi_arikawa_tainoura_003", ("有川港ターミナル", "09:29"), ("鯛の浦", "09:48")),
                    trip("saihi_arikawa_tainoura_004", ("有川港ターミナル", "11:25"), ("鯛の浦", "11:44")),
                    trip("saihi_arikawa_tainoura_005", ("有川港ターミナル", "12:29"), ("鯛の浦", "12:48")),
                    trip("saihi_arikawa_tainoura_006", ("有川港ターミナル", "16:33"), ("鯛の浦", "16:52")),
                ]},
            ],
        },
        route(
            "miyakou_ayukawa_line_port_to_ishinomaki",
            "ミヤコーバス 鮎川線（鮎川港 ⇔ 石巻方面）",
            "ミヤコーバス",
            ayukawa_miyakou,
            [
                "Miyagi Kotsu/Miyakoh Bus timetable search lists 鮎川港 as a bus stop on the 鮎川線.",
                "Miyagi Prefecture transport material also lists current 鮎川港 departures on the same line.",
            ],
        )
        | {
            "sourceUrls": [ayukawa_miyakou, ayukawa_pref_pdf],
            "serviceDays": "daily",
            "promotionStatus": "source_collected_needs_stop_sequence_review",
            "portNames": ["鮎川港"],
            "busStops": [
                {"name": "鮎川港", "lat": 38.299, "lon": 141.505, "coordinateSource": "docs/data/v5_ship_map.geojson:鮎川港/manual stop review needed"},
                {"name": "石巻駅前", "lat": 38.435, "lon": 141.303, "coordinateSource": "manual approximate from Miyakoh Bus route endpoint; needs precise stop review"},
            ],
            "directions": [
                {"direction": "from_port", "trips": [
                    trip("ayukawa_ishinomaki_001", ("鮎川港", "06:45"), ("石巻駅前", "08:20")),
                    trip("ayukawa_ishinomaki_002", ("鮎川港", "07:20"), ("石巻駅前", "08:55")),
                    trip("ayukawa_ishinomaki_003", ("鮎川港", "10:25"), ("石巻駅前", "12:00")),
                    trip("ayukawa_ishinomaki_004", ("鮎川港", "12:30"), ("石巻駅前", "14:05")),
                    trip("ayukawa_ishinomaki_005", ("鮎川港", "14:30"), ("石巻駅前", "16:05")),
                    trip("ayukawa_ishinomaki_006", ("鮎川港", "16:30"), ("石巻駅前", "18:05")),
                ]},
            ],
        },
        route(
            "minamitane_community_bus_shimama_candidate",
            "南種子町コミュニティバス 島間線（島間港 candidate）",
            "南種子町 / さんまりん観光",
            shimama_tanegashima_bus,
            [
                "Tanegashima public timetable page publishes さんまりん観光 route bus tables.",
                "NAVITIME lists 南種子町コミュニティバス 島間線 stops near 種子島島間港, including 島間 and 州崎港前.",
            ],
        )
        | {
            "sourceUrls": [shimama_tanegashima_bus, shimama_navitime, "https://www.furusato-tanegashima.net/fj/minamitanetyou/sm-mukaikata.html"],
            "serviceDays": "weekday",
            "promotionStatus": "source_collected_needs_calendar_refinement",
            "portNames": ["島間港"],
            "busStops": [
                {"name": "島間", "lat": 30.405, "lon": 130.901, "coordinateSource": "manual approximate from Shimama port vicinity; needs precise stop review"},
                {"name": "州崎港前", "lat": 30.405, "lon": 130.898, "coordinateSource": "manual approximate from NAVITIME stop list; needs precise stop review"},
                {"name": "河内温泉", "lat": 30.413, "lon": 130.903, "coordinateSource": "manual approximate from Minamitane community bus context; needs precise stop review"},
            ],
            "directions": [
                {"direction": "from_port", "trips": [
                    trip("shimama_suzaki_kawachi_001", ("州崎港前", "10:41"), ("島間", "10:47"), ("河内温泉", "11:28"), service_days="weekday"),
                ]},
                {"direction": "to_port", "trips": [
                    trip("shimama_to_suzaki_001", ("島間", "17:20"), ("州崎港前", "17:26"), service_days="weekday"),
                    trip("shimama_to_suzaki_002", ("島間", "17:35"), ("州崎港前", "17:41"), service_days="weekday"),
                    trip("shimama_to_suzaki_003", ("島間", "18:20"), ("州崎港前", "18:26"), service_days="weekday"),
                ]},
            ],
        },
        route(
            "goto_city_community_kaizu_candidate",
            "五島市コミュニティバス 貝津コース（貝津港待合所前 candidate）",
            "五島市コミュニティバス",
            kaizu_jorudan,
            [
                "Jorudan public transit listing identifies 貝津港待合所前 on the 五島市コミュニティバス 貝津コース.",
                "Exact current municipal/operator timetable rows still need extraction before runtime promotion.",
            ],
        )
        | {
            "sourceUrls": [kaizu_jorudan, kaizu_city_pdf],
            "serviceDays": "monday_to_saturday",
            "promotionStatus": "source_collected_needs_calendar_refinement",
            "portNames": ["貝津"],
            "busStops": [
                {"name": "貝津港待合所前", "lat": 32.758, "lon": 128.641, "coordinateSource": "manual approximate from Kaizu port context; needs precise stop review"},
                {"name": "三井楽タクシー", "lat": 32.746, "lon": 128.694, "coordinateSource": "manual approximate from Miiraku community bus context; needs precise stop review"},
                {"name": "竹山公園前", "lat": 32.754, "lon": 128.652, "coordinateSource": "manual approximate from Miiraku community bus context; needs precise stop review"},
            ],
            "directions": [
                {"direction": "to_kaizu_port", "trips": [
                    trip("goto_kaizu_port_001", ("三井楽タクシー", "08:10"), ("竹山公園前", "08:20"), ("貝津港待合所前", "08:23"), service_days="monday_to_saturday"),
                    trip("goto_kaizu_port_002", ("三井楽タクシー", "13:00"), ("竹山公園前", "13:10"), ("貝津港待合所前", "13:13"), service_days="monday_to_saturday"),
                    trip("goto_kaizu_port_003", ("三井楽タクシー", "16:00"), ("竹山公園前", "16:10"), ("貝津港待合所前", "16:13"), service_days="monday_to_saturday"),
                ]},
                {"direction": "from_kaizu_port", "trips": [
                    trip("goto_kaizu_from_port_001", ("貝津港待合所前", "08:23"), ("竹山公園前", "08:25"), ("三井楽タクシー", "08:35"), service_days="monday_to_saturday"),
                    trip("goto_kaizu_from_port_002", ("貝津港待合所前", "13:13"), ("竹山公園前", "13:15"), ("三井楽タクシー", "13:25"), service_days="monday_to_saturday"),
                    trip("goto_kaizu_from_port_003", ("貝津港待合所前", "16:13"), ("竹山公園前", "16:15"), ("三井楽タクシー", "16:25"), service_days="monday_to_saturday"),
                ]},
            ],
        },
        route(
            "hirado_takushima_fureai_bus_candidate",
            "平戸市ふれあいセンター度島号（度島 candidate）",
            "平戸市",
            hirado_fureai_page,
            [
                "Hirado city bus pages and island-community references identify municipal/community transport around 度島.",
                "The 度島 record needs current local timetable extraction and public-use confirmation before runtime promotion.",
            ],
        )
        | {
            "sourceUrls": [hirado_fureai_page, "https://www.nijinet.or.jp/Portals/0/pdf/publishing/shima/259/shima_259_04.pdf"],
            "serviceDays": "source_candidate",
            "promotionStatus": "official_source_found_needs_public_use_and_timetable_confirmation",
            "portNames": ["度島"],
            "busStops": [
                {"name": "度島港", "lat": 33.408, "lon": 129.515, "coordinateSource": "manual approximate from Hirado ferry context; needs precise stop review"},
            ],
            "directions": [],
        },
        route(
            "saihi_gounokubi_bus_candidate",
            "西肥バス 郷ノ首 candidate",
            "西肥自動車",
            gounokubi_yahoo,
            [
                "Public transit listings identify 郷の首 as a Saihi Bus stop.",
                "Exact route, stop coordinate, and current timetable rows need extraction before runtime promotion.",
            ],
        )
        | {
            "sourceUrls": [gounokubi_yahoo, saihi_route_pdf],
            "serviceDays": "weekday_with_calendar_exceptions",
            "promotionStatus": "source_collected_needs_stop_sequence_review",
            "portNames": ["郷ノ首"],
            "busStops": [
                {"name": "有川港ターミナル", "lat": 32.984, "lon": 129.116, "coordinateSource": "manual approximate from Shinkamigoto route context; needs precise stop review"},
                {"name": "青方", "lat": 32.983, "lon": 129.073, "coordinateSource": "manual approximate from Saihi Shinkamigoto route context; needs precise stop review"},
                {"name": "郷の首", "lat": 32.96, "lon": 129.05, "coordinateSource": "manual approximate from Saihi/Goto context; needs precise stop review"},
                {"name": "奈良尾車庫前", "lat": 32.831, "lon": 129.061, "coordinateSource": "manual approximate from Saihi Shinkamigoto route context; needs precise stop review"},
            ],
            "directions": [
                {"direction": "arikawa_to_narao_via_gounokubi", "trips": [
                    trip("saihi_arikawa_gounokubi_narao_001", ("有川港ターミナル", "10:24"), ("青方", "10:29"), ("郷の首", "10:35"), ("奈良尾車庫前", "10:45")),
                    trip("saihi_arikawa_gounokubi_narao_002", ("有川港ターミナル", "12:37"), ("青方", "12:40"), ("郷の首", "12:47"), ("奈良尾車庫前", "12:58")),
                    trip("saihi_arikawa_gounokubi_narao_003", ("有川港ターミナル", "14:41"), ("青方", "14:44"), ("郷の首", "14:51"), ("奈良尾車庫前", "15:02")),
                    trip("saihi_arikawa_gounokubi_narao_004", ("有川港ターミナル", "15:40"), ("青方", "15:43"), ("郷の首", "15:50"), ("奈良尾車庫前", "16:01")),
                    trip("saihi_arikawa_gounokubi_narao_005", ("有川港ターミナル", "16:29"), ("青方", "16:32"), ("郷の首", "16:39"), ("奈良尾車庫前", "16:50")),
                    trip("saihi_arikawa_gounokubi_narao_006", ("有川港ターミナル", "17:59"), ("青方", "18:02"), ("郷の首", "18:09"), ("奈良尾車庫前", "18:20")),
                ]},
            ],
        },
        route(
            "tokashiki_bus_port_aharen",
            "とかしき観光バス（渡嘉敷港 ⇔ 阿波連ビーチ）",
            "とかしき観光バス",
            tokashiki_page,
            [
                "Tokashiki Bus official timetable page publishes the scheduled shared bus between 渡嘉敷港 and 阿波連ビーチ with adult fare 400 yen.",
                "Official page gives endpoint departure times by season; bus-routes GTFS pages are retained as timetable-row cross-checks before runtime promotion.",
            ],
        )
        | {
            "sourceUrls": [tokashiki_page, tokashiki_gtfs_port, tokashiki_gtfs_beach],
            "serviceDays": "seasonal_variants",
            "adultFareYen": 400,
            "promotionStatus": "source_collected_needs_calendar_refinement",
            "portNames": ["渡嘉敷港"],
            "busStops": [
                {"name": "渡嘉敷港", "lat": 26.1991475, "lon": 127.3695236, "coordinateSource": "docs/data/v5_ship_map.geojson:渡嘉敷港"},
                {"name": "阿波連ビーチ", "lat": 26.169, "lon": 127.345, "coordinateSource": "manual approximate from Tokashiki Bus route context; needs precise stop review"},
            ],
            "directions": [
                {"direction": "from_port", "trips": [
                    trip("tokashiki_port_aharen_001", ("渡嘉敷港", "09:50"), ("阿波連ビーチ", "10:00")),
                    trip("tokashiki_port_aharen_002", ("渡嘉敷港", "11:30"), ("阿波連ビーチ", "11:40")),
                    trip("tokashiki_port_aharen_003", ("渡嘉敷港", "17:20"), ("阿波連ビーチ", "17:30")),
                ]},
                {"direction": "to_port", "trips": [
                    trip("tokashiki_aharen_port_001", ("阿波連ビーチ", "09:00"), ("渡嘉敷港", "09:10")),
                    trip("tokashiki_aharen_port_002", ("阿波連ビーチ", "15:00"), ("渡嘉敷港", "15:10")),
                    trip("tokashiki_aharen_port_003", ("阿波連ビーチ", "16:30"), ("渡嘉敷港", "16:40")),
                ]},
            ],
        },
        route(
            "kagoshima_city_sakurajima_island_view",
            "サクラジマアイランドビュー（桜島港起点循環）",
            "鹿児島市交通局",
            sakurajima_city_pdf,
            [
                "Kagoshima City/Sakurajima Ferry official page states Sakurajima Island View operates every 30 minutes from 9:30 to 16:30 from Sakurajima Port.",
                "Kagoshima City Transportation Bureau PDF is the official route timetable source; endpoint arrival rows need full PDF/table extraction before runtime promotion.",
            ],
        )
        | {
            "sourceUrls": [sakurajima_ferry_page, sakurajima_city_pdf],
            "serviceDays": "daily",
            "promotionStatus": "source_collected_needs_calendar_refinement",
            "portNames": ["桜島"],
            "busStops": [
                {"name": "桜島港", "lat": 31.592602, "lon": 130.6000526, "coordinateSource": "docs/data/v5_ship_map.geojson:桜島"},
                {"name": "ビジターセンター", "lat": 31.590, "lon": 130.596, "coordinateSource": "manual approximate from official Sakurajima Island View route context; needs precise stop review"},
                {"name": "湯之平展望所", "lat": 31.596, "lon": 130.557, "coordinateSource": "manual approximate from official Sakurajima Island View route context; needs precise stop review"},
            ],
            "directions": [
                {"direction": "sakurajima_loop", "trips": [
                    trip("sakurajima_island_view_001", ("桜島港", "09:30"), ("ビジターセンター", "09:36"), ("湯之平展望所", "10:10"), ("桜島港", "10:25")),
                    trip("sakurajima_island_view_002", ("桜島港", "10:00"), ("ビジターセンター", "10:06"), ("湯之平展望所", "10:40"), ("桜島港", "10:55")),
                    trip("sakurajima_island_view_003", ("桜島港", "10:30"), ("ビジターセンター", "10:36"), ("湯之平展望所", "11:10"), ("桜島港", "11:25")),
                    trip("sakurajima_island_view_004", ("桜島港", "11:00"), ("ビジターセンター", "11:06"), ("湯之平展望所", "11:40"), ("桜島港", "11:55")),
                    trip("sakurajima_island_view_005", ("桜島港", "11:30"), ("ビジターセンター", "11:36"), ("湯之平展望所", "12:10"), ("桜島港", "12:25")),
                    trip("sakurajima_island_view_006", ("桜島港", "12:00"), ("ビジターセンター", "12:06"), ("湯之平展望所", "12:40"), ("桜島港", "12:55")),
                    trip("sakurajima_island_view_007", ("桜島港", "12:30"), ("ビジターセンター", "12:36"), ("湯之平展望所", "13:10"), ("桜島港", "13:25")),
                    trip("sakurajima_island_view_008", ("桜島港", "13:00"), ("ビジターセンター", "13:06"), ("湯之平展望所", "13:40"), ("桜島港", "13:55")),
                    trip("sakurajima_island_view_009", ("桜島港", "13:30"), ("ビジターセンター", "13:36"), ("湯之平展望所", "14:10"), ("桜島港", "14:25")),
                    trip("sakurajima_island_view_010", ("桜島港", "14:00"), ("ビジターセンター", "14:06"), ("湯之平展望所", "14:40"), ("桜島港", "14:55")),
                    trip("sakurajima_island_view_011", ("桜島港", "14:30"), ("ビジターセンター", "14:36"), ("湯之平展望所", "15:10"), ("桜島港", "15:25")),
                    trip("sakurajima_island_view_012", ("桜島港", "15:00"), ("ビジターセンター", "15:06"), ("湯之平展望所", "15:40"), ("桜島港", "15:55")),
                    trip("sakurajima_island_view_013", ("桜島港", "15:30"), ("ビジターセンター", "15:36"), ("湯之平展望所", "16:10"), ("桜島港", "16:25")),
                    trip("sakurajima_island_view_014", ("桜島港", "16:00"), ("ビジターセンター", "16:06"), ("湯之平展望所", "16:40"), ("桜島港", "16:55")),
                    trip("sakurajima_island_view_015", ("桜島港", "16:30"), ("ビジターセンター", "16:36"), ("湯之平展望所", "17:10"), ("桜島港", "17:25")),
                ]},
            ],
        },
        route(
            "shinkamigoto_saihi_route_bus_source_candidate",
            "新上五島町内西肥バス路線（上五島・友住 port access candidate）",
            "西肥自動車",
            shinkamigoto_page,
            [
                "Shinkamigoto official town page states public route buses operate in the town.",
                "Saihi Bus official information page confirms Shinkamigoto town route fare search support.",
                "Saihi publishes the official 2026-04 Shinkamigoto route timetable PDF, plus current stop timetable PDFs for 友住 and 友住海岸.",
                "The route PDF exposes 青方港相河ターミナル service for the 上五島/Aokata ferry side, but the exact gameplay endpoint mapping still needs review.",
                "The 友住/友住海岸 stop PDFs are official and current, but their text layer does not expose enough stop-time rows for safe automated extraction; review the PDF table/image before creating trips.",
            ],
        )
        | {
            "sourceUrls": [shinkamigoto_page, saihi_fare_page, saihi_route_pdf, saihi_tomosumi_pdf, saihi_tomosumi_kaigan_pdf],
            "serviceDays": "daily_with_calendar_exceptions",
            "promotionStatus": "source_collected_needs_tomosumi_stop_time_refinement",
            "portNames": ["上五島", "友住"],
            "connectorAnchorStopNames": ["青方港相河ターミナル", "友住"],
            "busStops": [
                {"name": "青方港相河ターミナル", "lat": 33.016, "lon": 129.192, "coordinateSource": "manual approximate from Aokata/Aikawa ferry terminal context; needs precise stop review"},
                {"name": "青方", "lat": 32.983, "lon": 129.073, "coordinateSource": "manual approximate from Saihi Shinkamigoto route context; needs precise stop review"},
                {"name": "上五島", "lat": 33.015063, "lon": 129.192011, "coordinateSource": "docs/data/v5_ship_map.geojson:上五島; port identity needs bus-stop match"},
                {"name": "箒山", "lat": 33.002, "lon": 129.103, "coordinateSource": "manual approximate from Saihi Shinkamigoto route context; needs precise stop review"},
                {"name": "有川港ターミナル", "lat": 32.984, "lon": 129.116, "coordinateSource": "manual approximate from Shinkamigoto route context; needs precise stop review"},
                {"name": "友住", "lat": 32.99888, "lon": 129.174452, "coordinateSource": "docs/data/v5_ship_map.geojson:友住; port identity needs bus-stop match"},
                {"name": "新上五島町役場前", "lat": 32.984, "lon": 129.073, "coordinateSource": "manual approximate civic-center seed; needs precise stop review"},
            ],
            "directions": [
                {"direction": "aokata_to_arikawa_via_kamigoto", "trips": [
                    trip("saihi_aokata_kamigoto_001", ("青方港相河ターミナル", "07:35"), ("青方", "07:37"), ("上五島", "07:42"), ("箒山", "07:44")),
                    trip("saihi_aokata_kamigoto_002", ("青方港相河ターミナル", "09:05"), ("青方", "09:07"), ("上五島", "09:12"), ("箒山", "09:14")),
                    trip("saihi_aokata_kamigoto_003", ("青方港相河ターミナル", "11:21"), ("青方", "11:23"), ("上五島", "11:28"), ("箒山", "11:30")),
                    trip("saihi_aokata_kamigoto_004", ("青方港相河ターミナル", "17:40"), ("青方", "17:42"), ("上五島", "17:47"), ("箒山", "17:49")),
                ]},
            ],
        },
    ]


def merge_routes(existing: list[dict[str, Any]], additions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept_existing = [route for route in existing if route.get("routeCode") not in NON_RUNTIME_ROUTE_CODES]
    by_code = {route["routeCode"]: index for index, route in enumerate(kept_existing)}
    merged = list(kept_existing)
    for item in additions:
        code = item["routeCode"]
        if code in NON_RUNTIME_ROUTE_CODES:
            continue
        if code in by_code:
            merged[by_code[code]] = preserve_reviewed_stop_coordinates(merged[by_code[code]], item)
        else:
            by_code[code] = len(merged)
            merged.append(item)
    return merged


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    additions = build_routes()
    payload["generatedAt"] = datetime.now(UTC).isoformat()
    payload["routes"] = enrich_service_profiles(merge_routes(payload.get("routes", []), additions))
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DATA_PATH, DOCS_PATH)

    runtime_additions = [item for item in additions if item.get("routeCode") not in NON_RUNTIME_ROUTE_CODES]
    added_codes = [item["routeCode"] for item in runtime_additions]
    trip_count = 0
    candidate_count = 0
    for item in runtime_additions:
        if not item.get("directions"):
            candidate_count += 1
        for direction in item.get("directions", []):
            trip_count += len(direction.get("trips", []))
    audit = {
        "schemaVersion": "v5_remote_small_island_ship_port_bus_source_audit_v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "summary": {
            "addedOrUpdatedRouteCount": len(additions),
            "sourceBackedTripCount": trip_count,
            "sourceCandidateWithoutTripsCount": candidate_count,
            "routeCodes": added_codes,
        },
    }
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOCS_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(AUDIT_PATH, DOCS_AUDIT_PATH)
    print("OK remote ship-port bus source collected:", audit["summary"])


if __name__ == "__main__":
    main()
