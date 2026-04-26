#!/usr/bin/env python3
"""Audit likely timetable sources for the current v4 nationwide rail scope.

This script does not collect train instances.  It builds a reusable source
registry so the v4 timetable ingestion work can advance operator by operator
without relying on chat history.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import sys
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = ROOT / "docs" / "data" / "v4_maplibre" / "line_inventory.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_timetable_source_registry.json"
DEFAULT_GTFS_ROUTE_INDEX = ROOT / "data" / "v4_gtfs_repository_route_index.json"
DEFAULT_OFFICIAL_SITE_CANDIDATES = ROOT / "data" / "v4_official_site_timetable_candidates.json"

GTFS_REPOSITORY_FILES_URL = "https://api.gtfs-data.jp/v2/files?target_date=all"

RAIL_ROUTE_TYPES = {0, 1, 2, 5, 6, 7, 11, 12}
BUS_ONLY_ROUTE_TYPES = {3}


# ODPT's CKAN API currently responds as HTML in this environment, so keep the
# railway GTFS leads as explicit seeds and verify/refresh them through the
# catalog pages during source-audit work.
ODPT_RAIL_GTFS_LEADS: dict[str, list[dict[str, Any]]] = {
    "横浜市": [
        {
            "sourceKind": "odpt_rail_gtfs_candidate",
            "title": "横浜市営地下鉄 / Yokohama Municipal Subway",
            "url": "https://ckan.odpt.org/en/dataset/yokohama_municipal_train",
            "scopeNote": "ODPT railway GTFS candidate for Yokohama Municipal Subway.",
        }
    ],
    "函館市": [
        {
            "sourceKind": "odpt_rail_gtfs_candidate",
            "title": "函館市電 / Hakodate City Tram",
            "url": "https://ckan.odpt.org/en/dataset/hakodate_city_alllines",
            "scopeNote": "ODPT railway GTFS candidate for Hakodate City Tram.",
        }
    ],
    "京都市": [
        {
            "sourceKind": "odpt_rail_gtfs_candidate",
            "title": "京都市営地下鉄 / Kyoto City Subway",
            "url": "https://ckan.odpt.org/en/dataset/?res_format=GTFS%2FGTFS-JP&tags=%E9%89%84%E9%81%93-railway",
            "scopeNote": "ODPT Challenge 2025 limited railway GTFS candidate.",
        }
    ],
    "東日本旅客鉄道": [
        {
            "sourceKind": "odpt_rail_gtfs_candidate",
            "title": "JR東日本 鉄道関連情報 / Train information of JR East",
            "url": "https://ckan.odpt.org/organization/jreast?res_format=GTFS%2FGTFS-JP",
            "scopeNote": "Kanto-area conventional lines only; Shinkansen and several edge lines are excluded by the ODPT catalog note.",
        }
    ],
    "東武鉄道": [
        {
            "sourceKind": "odpt_rail_gtfs_candidate",
            "title": "東武鉄道 鉄道関連情報 / Train information of Tobu",
            "url": "https://ckan.odpt.org/dataset/tobu_train",
            "scopeNote": "ODPT Challenge 2025 railway GTFS candidate for Tobu.",
        }
    ],
    "相模鉄道": [
        {
            "sourceKind": "odpt_rail_gtfs_candidate",
            "title": "相模鉄道 鉄道関連情報 / Train information of Sotetsu",
            "url": "https://ckan.odpt.org/en/dataset/?organization=sotetsu&res_format=GTFS%2FGTFS-JP",
            "scopeNote": "ODPT Challenge 2025 railway GTFS candidate for Sotetsu.",
        }
    ],
    "首都圏新都市鉄道": [
        {
            "sourceKind": "odpt_rail_gtfs_candidate",
            "title": "首都圏新都市鉄道（つくばエクスプレス） 鉄道関連情報",
            "url": "https://ckan.odpt.org/en/dataset/train-mir",
            "scopeNote": "ODPT railway GTFS candidate for Tsukuba Express.",
        }
    ],
    "東京都": [
        {
            "sourceKind": "odpt_rail_gtfs_candidate",
            "title": "東京都交通局 鉄道関連情報",
            "url": "https://ckan.odpt.org/en/dataset/train-toei",
            "scopeNote": "Toei Subway, Tokyo Sakura Tram, and Nippori-Toneri Liner.",
        }
    ],
    "多摩都市モノレール": [
        {
            "sourceKind": "odpt_rail_gtfs_candidate",
            "title": "多摩都市モノレール 鉄道関連情報",
            "url": "https://ckan.odpt.org/en/dataset/train-tamamonorail",
            "scopeNote": "ODPT railway GTFS candidate for Tama Monorail.",
        }
    ],
    "東京臨海高速鉄道": [
        {
            "sourceKind": "odpt_rail_gtfs_candidate",
            "title": "東京臨海高速鉄道 鉄道関連情報",
            "url": "https://ckan.odpt.org/en/dataset/train-twr",
            "scopeNote": "ODPT railway GTFS candidate for Rinkai Line.",
        }
    ],
    "東京地下鉄": [
        {
            "sourceKind": "odpt_rail_gtfs_candidate",
            "title": "東京メトロ 鉄道関連情報",
            "url": "https://ckan.odpt.org/en/dataset/train-tokyometro",
            "scopeNote": "ODPT railway GTFS candidate for Tokyo Metro.",
        }
    ],
}


MANUAL_OFFICIAL_TIMETABLE_LEADS: dict[str, list[dict[str, Any]]] = {
    "WILLER　TRAINS": [{"title": "京都丹後鉄道 時刻表", "url": "https://trains.willer.co.jp/timetable/"}],
    "こうべ未来都市機構": [{"title": "まやビューライン 営業時間・料金", "url": "https://koberope.jp/maya/price/"}],
    "アイジーアールいわて銀河鉄道": [{"title": "IGRいわて銀河鉄道 時刻表", "url": "https://igr.jp/timetable/"}],
    "一般社団法人札幌市交通事業振興公社": [{"title": "札幌市交通局 時刻表", "url": "https://www.city.sapporo.jp/st/time/index.html"}],
    "一般財団法人青函トンネル記念館": [{"title": "青函トンネル記念館 公式サイト", "url": "http://seikan-tunnel-museum.jp/"}],
    "上田電鉄": [{"title": "上田電鉄 時刻表", "url": "https://www.uedadentetsu.com/timetable/"}],
    "仙台市": [{"title": "仙台市交通局 時刻表", "url": "https://www.navi.kotsu.city.sendai.jp/"}],
    "会津鉄道": [{"title": "会津鉄道 時刻表", "url": "https://aizutetsudo.jp/timetable"}],
    "北大阪急行電鉄": [{"title": "北大阪急行電鉄 公式サイト", "url": "https://www.kita-kyu.co.jp/"}],
    "北海道旅客鉄道": [{"title": "JR北海道 各駅時刻表検索", "url": "https://www.jrhokkaido.co.jp/network/station/station.html"}],
    "北総鉄道": [{"title": "北総鉄道 時刻表", "url": "https://hokuso.ekitan.com/jp/pc/T1"}],
    "十国峠": [{"title": "十国峠 パノラマケーブルカー運賃・営業時間", "url": "https://www.jukkoku-cable.jp/guide/index.html"}],
    "名古屋ガイドウェイバス": [{"title": "名古屋ガイドウェイバス 公式サイト", "url": "https://www.guideway.co.jp/"}],
    "名古屋市": [{"title": "名古屋市交通局 地下鉄時刻表", "url": "https://www.kotsu.city.nagoya.jp/subway/timetable.html"}],
    "大阪市高速電気軌道": [{"title": "Osaka Metro 駅ガイド", "url": "https://subway.osakametro.co.jp/station_guide/"}],
    "山万": [{"title": "山万ユーカリが丘線 時刻表", "url": "https://town.yukarigaoka.jp/yukariline/timetable/"}],
    "嵯峨野観光鉄道": [{"title": "嵯峨野観光鉄道 時刻表のご案内", "url": "https://www.sagano-kanko.co.jp/train-info"}],
    "広島高速交通": [{"title": "アストラムライン 駅・時刻表", "url": "https://www.astramline.co.jp/station/timetable.html"}],
    "新京成電鉄": [{"title": "新京成電鉄 公式サイト", "url": "https://www.shinkeisei.co.jp/"}],
    "札幌市": [{"title": "札幌市交通局 時刻表", "url": "https://www.city.sapporo.jp/st/time/index.html"}],
    "神戸六甲鉄道": [{"title": "六甲ケーブル 時刻表・運賃", "url": "https://www.rokkocable.com/information/"}],
    "福岡市": [{"title": "福岡市地下鉄 路線図・駅時刻表", "url": "https://subway.city.fukuoka.lg.jp/schedule/index.php"}],
    "立山黒部貫光": [{"title": "立山黒部アルペンルート 時刻表", "url": "https://www.alpen-route.com/timetable/"}],
    "紀州鉄道": [{"title": "紀州鉄道 公式サイト", "url": "https://kishu-railway.com/"}],
    "能勢電鉄": [{"title": "能勢電鉄 時刻表", "url": "https://noseden.ekitan.com/norikae/timetable"}],
    "舞浜リゾートライン": [{"title": "ディズニーリゾートライン", "url": "https://www.tokyodisneyresort.jp/tdr/resortline.html"}],
    "鞍馬寺": [{"title": "鞍馬寺 山内案内", "url": "https://www.kuramadera.or.jp/annai.html"}],
    "鹿児島市": [{"title": "鹿児島市交通局 路線・運賃・時刻表検索", "url": "https://www.kotsu-city-kagoshima.jp/wp/timesearch/"}],
}


EXISTING_TIMETABLE_WORK: dict[str, list[dict[str, Any]]] = {
    "東日本旅客鉄道": [
        {
            "sourceKind": "existing_partial_collector",
            "title": "JR East official station timetable collector",
            "scripts": [
                "scripts/ingest/discover_jreast_timetable.py",
                "scripts/ingest/build_v3_tokyo_jreast_core_train_instances.py",
            ],
            "dataFiles": ["data/v3_tokyo_jreast_core_weekday_train_instances.json"],
            "scopeNote": "v3 Tokyo-core conventional-line batch only; nationwide JR East remains open.",
        }
    ],
    "東海旅客鉄道": [
        {
            "sourceKind": "existing_partial_collector",
            "title": "JR Central Tokaido Shinkansen collector",
            "scripts": ["scripts/ingest/build_v3_jr_central_tokaido_train_instances.py"],
            "dataFiles": ["data/v3_tokyo_jr_central_tokaido_weekday_train_instances.json"],
            "scopeNote": "Tokaido Shinkansen only; conventional JR Central lines remain open.",
        }
    ],
    "西日本旅客鉄道": [
        {
            "sourceKind": "collector_available_not_full",
            "title": "JR West station/train timetable parser",
            "scripts": [
                "scripts/ingest/build_jrwest_train_instances_from_station_timetable.py",
                "scripts/ingest/parse_jrwest_train_timetable.py",
            ],
            "dataFiles": ["data/shinkansen_v2_weekday_train_instances_merged.json"],
            "scopeNote": "Parser exists and shinkansen merged data exists; full JR West conventional collection is not complete.",
        }
    ],
    "九州旅客鉄道": [
        {
            "sourceKind": "collector_available_not_full",
            "title": "JR Kyushu station/train timetable parser",
            "scripts": [
                "scripts/ingest/build_jrkyushu_train_instances_from_station_timetable.py",
                "scripts/ingest/parse_jrkyushu_train_timetable.py",
            ],
            "dataFiles": ["data/shinkansen_v2_weekday_train_instances_merged.json"],
            "scopeNote": "Parser exists and shinkansen merged data exists; full JR Kyushu conventional collection is not complete.",
        }
    ],
    "東京地下鉄": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Tokyo Metro official transfer API collector",
            "scripts": ["scripts/ingest/build_v3_tokyo_metro_train_instances.py"],
            "dataFiles": ["data/v3_tokyo_tokyo_metro_weekday_train_instances.json.gz"],
            "scopeNote": "v3 company-level Tokyo Metro batch.",
        }
    ],
    "東京都": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Toei GTFS collector",
            "scripts": ["scripts/ingest/build_v3_toei_train_instances_from_gtfs.py"],
            "dataFiles": ["data/v3_tokyo_toei_weekday_train_instances.json"],
            "scopeNote": "v3 Toei rail batch.",
        }
    ],
    "東急電鉄": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Tokyu station timetable collector",
            "scripts": ["scripts/ingest/build_v3_tokyu_train_instances.py"],
            "dataFiles": ["data/v3_tokyo_tokyu_weekday_train_instances.json"],
            "scopeNote": "v3 company-level Tokyu batch.",
        }
    ],
    "小田急電鉄": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Odakyu station timetable collector",
            "scripts": ["scripts/ingest/build_v3_odakyu_train_instances.py"],
            "dataFiles": ["data/v3_tokyo_odakyu_weekday_train_instances.json"],
            "scopeNote": "v3 company-level Odakyu batch.",
        }
    ],
    "京王電鉄": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Keio API collector",
            "scripts": ["scripts/ingest/build_v3_keio_train_instances.py"],
            "dataFiles": ["data/v3_tokyo_keio_weekday_train_instances.json"],
            "scopeNote": "v3 company-level Keio batch.",
        }
    ],
    "京浜急行電鉄": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Keikyu timetable collector",
            "scripts": ["scripts/ingest/build_v3_keikyu_train_instances.py"],
            "dataFiles": ["data/v3_tokyo_keikyu_weekday_train_instances.json"],
            "scopeNote": "v3 company-level Keikyu batch.",
        }
    ],
    "東武鉄道": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Tobu station timetable collector",
            "scripts": ["scripts/ingest/build_v3_tobu_train_instances.py"],
            "dataFiles": ["data/v3_tokyo_tobu_weekday_train_instances.json"],
            "scopeNote": "v3 company-level Tobu batch.",
        }
    ],
    "西武鉄道": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Seibu station timetable collector",
            "scripts": ["scripts/ingest/build_v3_seibu_train_instances.py"],
            "dataFiles": ["data/v3_tokyo_seibu_weekday_train_instances.json"],
            "scopeNote": "v3 company-level Seibu batch.",
        }
    ],
    "京成電鉄": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Keisei station timetable collector",
            "scripts": ["scripts/ingest/build_v3_keisei_train_instances.py"],
            "dataFiles": ["data/v3_tokyo_keisei_weekday_train_instances.json"],
            "scopeNote": "v3 company-level Keisei batch.",
        }
    ],
    "東京臨海高速鉄道": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Rinkai Line timetable collector",
            "scripts": ["scripts/ingest/build_v3_tokyo_rinkai_train_instances.py"],
            "dataFiles": ["data/v3_tokyo_rinkai_weekday_train_instances.json"],
            "scopeNote": "v3 Rinkai batch.",
        }
    ],
    "ゆりかもめ": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Yurikamome PDF timetable collector",
            "scripts": ["scripts/ingest/build_v3_yurikamome_train_instances_from_pdfs.py"],
            "dataFiles": ["data/v3_tokyo_yurikamome_weekday_train_instances.json"],
            "scopeNote": "v3 Yurikamome batch.",
        }
    ],
    "東京モノレール": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Tokyo Monorail timetable collector",
            "scripts": ["scripts/ingest/build_v3_tokyo_tokyo_monorail_train_instances.py"],
            "dataFiles": ["data/v3_tokyo_tokyo_monorail_weekday_train_instances.json"],
            "scopeNote": "v3 Tokyo Monorail batch.",
        }
    ],
    "多摩都市モノレール": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Tama Monorail PDF timetable collector",
            "scripts": ["scripts/ingest/build_v3_tama_monorail_train_instances_from_pdfs.py"],
            "dataFiles": ["data/v3_tokyo_tama_monorail_weekday_train_instances.json"],
            "scopeNote": "v3 Tama Monorail batch.",
        }
    ],
    "首都圏新都市鉄道": [
        {
            "sourceKind": "existing_v3_collector",
            "title": "Tsukuba Express API collector",
            "scripts": ["scripts/ingest/build_v3_tsukuba_express_train_instances.py"],
            "dataFiles": ["data/v3_tokyo_tsukuba_express_weekday_train_instances.json"],
            "scopeNote": "v3 Tsukuba Express batch.",
        }
    ],
}


def normalized_name(value: str) -> str:
    text = (value or "").lower()
    replacements = {
        "　": "",
        " ": "",
        "株式会社": "",
        "有限会社": "",
        "一般社団法人": "",
        "旅客鉄道株式会社": "旅客鉄道",
        "鉄道株式会社": "鉄道",
        "電鉄株式会社": "電鉄",
        "電気鉄道": "電鉄",
        "交通局": "",
        "bureauoftransportation": "",
        "cityof": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def source_lead_key(lead: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(lead.get("sourceKind") or ""),
        str(lead.get("fileUrl") or lead.get("url") or lead.get("feedPageUrl") or ""),
        str(lead.get("title") or lead.get("feedName") or lead.get("organizationName") or ""),
    )


def dedupe_source_leads(leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for lead in leads:
        key = source_lead_key(lead)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(lead)
    return deduped


def fetch_json_url(url: str, timeout: int = 60) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json,*/*",
            "Accept-Encoding": "gzip",
            "User-Agent": "OniChase-v4-timetable-source-audit/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return json.loads(raw)


def read_train_count(path: str) -> int | None:
    target = ROOT / path
    if not target.exists():
        return None
    opener = gzip.open if target.suffix == ".gz" else open
    with opener(target, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    trains = data.get("train_instances")
    return len(trains) if isinstance(trains, list) else None


def annotate_existing_work() -> dict[str, list[dict[str, Any]]]:
    annotated: dict[str, list[dict[str, Any]]] = {}
    for operator, leads in EXISTING_TIMETABLE_WORK.items():
        out: list[dict[str, Any]] = []
        for lead in leads:
            item = dict(lead)
            data_files = item.get("dataFiles") or []
            counts = {}
            for path in data_files:
                count = read_train_count(path)
                if count is not None:
                    counts[path] = count
            if counts:
                item["trainInstanceCounts"] = counts
                item["totalKnownTrainInstances"] = sum(counts.values())
            out.append(item)
        annotated[operator] = out
    return annotated


def manual_official_timetable_leads() -> dict[str, list[dict[str, Any]]]:
    leads_by_operator: dict[str, list[dict[str, Any]]] = {}
    for operator_name, leads in MANUAL_OFFICIAL_TIMETABLE_LEADS.items():
        out: list[dict[str, Any]] = []
        for lead in leads:
            out.append(
                {
                    "sourceKind": "manual_official_timetable_page_candidate",
                    "candidateStatus": "manual_seed",
                    "title": lead["title"],
                    "url": lead["url"],
                    "scopeNote": "Manual official-source seed for operators whose timetable entry was missed by first-pass automated discovery.",
                }
            )
        leads_by_operator[operator_name] = out
    return leads_by_operator



def fetch_gtfs_repository_index(no_network: bool) -> tuple[list[dict[str, Any]], list[str]]:
    if no_network:
        return [], ["GTFS repository index fetch skipped by --no-network."]
    try:
        data = fetch_json_url(GTFS_REPOSITORY_FILES_URL)
    except Exception as exc:  # noqa: BLE001 - audit should report and continue.
        return [], [f"GTFS repository index fetch failed: {type(exc).__name__}: {exc}"]
    if not isinstance(data, dict) or not isinstance(data.get("body"), list):
        return [], ["GTFS repository index response did not contain a body list."]
    return data["body"], []


def is_name_match(operator_name: str, feed: dict[str, Any]) -> bool:
    op = normalized_name(operator_name)
    if not op:
        return False
    org = normalized_name(str(feed.get("organization_name") or ""))
    feed_name = normalized_name(str(feed.get("feed_name") or ""))
    org_id = normalized_name(str(feed.get("organization_id") or ""))
    feed_id = normalized_name(str(feed.get("feed_id") or ""))
    haystack = [org, feed_name, org_id, feed_id]
    if op in haystack:
        return True
    if len(op) >= 4 and any(op in value or value in op for value in haystack if len(value) >= 4):
        return True
    return False


def inspect_gtfs_route_types(feed_url: str, timeout: int = 45) -> dict[str, Any]:
    request = urllib.request.Request(
        feed_url,
        headers={"User-Agent": "OniChase-v4-timetable-source-audit/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        with archive.open("routes.txt") as routes_file:
            text = io.TextIOWrapper(routes_file, encoding="utf-8-sig")
            reader = csv.DictReader(text)
            route_types: set[int] = set()
            route_names: list[str] = []
            for row in reader:
                value = (row.get("route_type") or "").strip()
                if value:
                    try:
                        route_types.add(int(value))
                    except ValueError:
                        pass
                name = row.get("route_long_name") or row.get("route_short_name") or row.get("route_id")
                if name and len(route_names) < 8:
                    route_names.append(name)
    route_type_list = sorted(route_types)
    is_rail = bool(route_types & RAIL_ROUTE_TYPES)
    bus_only = bool(route_types) and route_types <= BUS_ONLY_ROUTE_TYPES
    return {
        "routeTypes": route_type_list,
        "sampleRouteNames": route_names,
        "isRailLike": is_rail,
        "isBusOnly": bus_only,
    }


def match_gtfs_repository_feeds(
    operators: list[dict[str, Any]],
    feeds: list[dict[str, Any]],
    inspect_route_types: bool,
    max_downloads: int,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    matches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    download_count = 0
    inspected = 0
    inspection_errors = 0

    for feed in feeds:
        matched_operator_names = [
            operator["operatorName"]
            for operator in operators
            if is_name_match(operator["operatorName"], feed)
        ]
        if not matched_operator_names:
            continue

        base = {
            "sourceKind": "gtfs_repository_candidate",
            "organizationName": feed.get("organization_name"),
            "feedName": feed.get("feed_name"),
            "feedPrefId": feed.get("feed_pref_id"),
            "feedPageUrl": feed.get("feed_page_url"),
            "fileUrl": feed.get("file_url"),
            "licenseId": feed.get("feed_license_id"),
            "fileFromDate": feed.get("file_from_date"),
            "fileToDate": feed.get("file_to_date"),
            "fileLastUpdatedAt": feed.get("file_last_updated_at"),
        }

        if inspect_route_types and feed.get("file_url") and download_count < max_downloads:
            download_count += 1
            try:
                base.update(inspect_gtfs_route_types(str(feed["file_url"])))
                inspected += 1
            except (OSError, urllib.error.URLError, zipfile.BadZipFile, KeyError) as exc:
                inspection_errors += 1
                base["inspectionError"] = f"{type(exc).__name__}: {exc}"

        if base.get("isBusOnly"):
            base["candidateStatus"] = "rejected_bus_only_name_match"
        elif base.get("isRailLike"):
            base["candidateStatus"] = "rail_gtfs_candidate"
        else:
            base["candidateStatus"] = "unverified_name_match"

        for operator_name in matched_operator_names:
            matches[operator_name].append(dict(base))

    stats = {
        "matchedFeeds": sum(len(items) for items in matches.values()),
        "operatorsWithMatches": len(matches),
        "routeTypeInspectedFeeds": inspected,
        "routeTypeInspectionErrors": inspection_errors,
        "maxCandidateDownloads": max_downloads,
    }
    return matches, stats


def load_gtfs_route_index(path: Path | None) -> tuple[list[dict[str, Any]], list[str]]:
    if not path or not path.exists():
        return [], []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        return [], [f"GTFS route index read failed: {type(exc).__name__}: {exc}"]
    feeds = data.get("feeds", []) if isinstance(data, dict) else []
    return [feed for feed in feeds if isinstance(feed, dict)], []


def load_official_site_candidates(path: Path | None) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any], list[str]]:
    if not path or not path.exists():
        return {}, {}, []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        return {}, {}, [f"Official site candidate read failed: {type(exc).__name__}: {exc}"]

    matches: dict[str, list[dict[str, Any]]] = {}
    for operator in data.get("operators", []):
        operator_name = operator.get("operatorName")
        if not operator_name:
            continue
        leads: list[dict[str, Any]] = []
        for candidate in operator.get("candidates", []):
            if candidate.get("candidateStatus") not in {"high_confidence", "medium_confidence"}:
                continue
            leads.append(
                {
                    "sourceKind": "official_timetable_page_candidate",
                    "candidateStatus": candidate.get("candidateStatus"),
                    "title": candidate.get("title") or candidate.get("label") or candidate.get("url"),
                    "label": candidate.get("label"),
                    "url": candidate.get("url"),
                    "domain": candidate.get("domain"),
                    "officialWebsite": candidate.get("officialWebsite"),
                    "score": candidate.get("score"),
                    "foundAs": candidate.get("foundAs"),
                    "scopeNote": "Discovered by crawling a Wikidata official website; verify page structure before writing a collector.",
                }
            )
        if leads:
            matches[operator_name] = leads[:8]
    return matches, data.get("counts", {}), []


def text_values_for_route_index_feed(feed: dict[str, Any]) -> list[str]:
    values = [
        str(feed.get("organizationName") or ""),
        str(feed.get("feedName") or ""),
        str(feed.get("organizationId") or ""),
        str(feed.get("feedId") or ""),
    ]
    for agency in feed.get("agencies") or []:
        values.append(str(agency.get("agencyName") or ""))
        values.append(str(agency.get("agencyUrl") or ""))
    return values


def line_match_score(line_name: str, route_name: str) -> int:
    line = normalized_name(line_name)
    route = normalized_name(route_name)
    if not line or not route:
        return 0
    if min(len(line), len(route)) < 5:
        return 0
    if line == route:
        return 100
    if len(line) >= 5 and line in route:
        return 80
    if len(route) >= 5 and route in line:
        return 70
    return 0


def match_gtfs_route_index(
    operators: list[dict[str, Any]],
    lines_by_operator: dict[str, list[dict[str, Any]]],
    route_index_feeds: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    matches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rail_feeds = [feed for feed in route_index_feeds if feed.get("status") == "ok" and feed.get("isRailLike")]

    unique_line_owner: dict[str, str] = {}
    ambiguous_lines: set[str] = set()
    for operator in operators:
        operator_name = operator["operatorName"]
        for line in lines_by_operator.get(operator_name, []):
            key = normalized_name(line["lineName"])
            if len(key) < 5:
                continue
            if key in unique_line_owner and unique_line_owner[key] != operator_name:
                ambiguous_lines.add(key)
            else:
                unique_line_owner[key] = operator_name
    for key in ambiguous_lines:
        unique_line_owner.pop(key, None)

    for feed in rail_feeds:
        feed_values = " ".join(text_values_for_route_index_feed(feed))
        normalized_feed_text = normalized_name(feed_values)
        route_names: list[str] = []
        for route in feed.get("routes") or []:
            route_names.extend(
                str(route.get(key) or "")
                for key in ("shortName", "longName", "routeDesc")
                if route.get(key)
            )

        matched: dict[str, set[str]] = defaultdict(set)
        for operator in operators:
            operator_name = operator["operatorName"]
            operator_norm = normalized_name(operator_name)
            if is_name_match(operator_name, {
                "organization_name": feed_values,
                "feed_name": "",
                "organization_id": "",
                "feed_id": "",
            }):
                matched[operator_name].add("operator_or_agency_name")
                continue
            if operator_norm and len(operator_norm) >= 3 and operator_norm in normalized_feed_text:
                matched[operator_name].add("operator_or_agency_name")

        for route_name in route_names:
            route_norm = normalized_name(route_name)
            if route_norm in unique_line_owner:
                matched[unique_line_owner[route_norm]].add("unique_route_line_name")
                continue
            for operator in operators:
                operator_name = operator["operatorName"]
                for line in lines_by_operator.get(operator_name, []):
                    score = line_match_score(line["lineName"], route_name)
                    if score >= 80:
                        matched[operator_name].add("route_line_name")

        for operator_name, reasons in matched.items():
            matches[operator_name].append(
                {
                    "sourceKind": "gtfs_repository_route_index_candidate",
                    "organizationName": feed.get("organizationName"),
                    "feedName": feed.get("feedName"),
                    "feedPrefId": feed.get("feedPrefId"),
                    "feedPageUrl": feed.get("feedPageUrl"),
                    "fileUrl": feed.get("fileUrl"),
                    "licenseId": feed.get("licenseId"),
                    "fileFromDate": feed.get("fileFromDate"),
                    "fileToDate": feed.get("fileToDate"),
                    "fileLastUpdatedAt": feed.get("fileLastUpdatedAt"),
                    "candidateStatus": "rail_gtfs_candidate",
                    "matchedBy": sorted(reasons),
                    "routeTypes": feed.get("routeTypes"),
                    "agencyNames": [
                        agency.get("agencyName")
                        for agency in (feed.get("agencies") or [])
                        if agency.get("agencyName")
                    ][:8],
                    "sampleRouteNames": [
                        route_name for route_name in route_names if route_name
                    ][:12],
                    "routeCount": feed.get("routeCount"),
                    "stopCount": feed.get("stopCount"),
                    "stopTimeCount": feed.get("stopTimeCount"),
                }
            )

    stats = {
        "routeIndexFeeds": len(route_index_feeds),
        "railLikeRouteIndexFeeds": len(rail_feeds),
        "matchedFeeds": sum(len(items) for items in matches.values()),
        "operatorsWithMatches": len(matches),
    }
    return matches, stats


def build_registry(args: argparse.Namespace) -> dict[str, Any]:
    with open(args.inventory, encoding="utf-8") as handle:
        inventory = json.load(handle)

    operators = sorted(inventory["operators"], key=lambda item: item["operatorName"])
    lines_by_operator: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in inventory["lines"]:
        lines_by_operator[line["operatorName"]].append(line)

    gtfs_feeds, warnings = fetch_gtfs_repository_index(args.no_network)
    route_index_feeds, route_index_warnings = load_gtfs_route_index(args.gtfs_route_index)
    warnings.extend(route_index_warnings)
    official_site_matches, official_site_stats, official_site_warnings = load_official_site_candidates(args.official_site_candidates)
    warnings.extend(official_site_warnings)
    gtfs_matches, gtfs_stats = match_gtfs_repository_feeds(
        operators,
        gtfs_feeds,
        inspect_route_types=not args.skip_route_type_inspection,
        max_downloads=args.max_candidate_downloads,
    )
    route_index_matches, route_index_stats = match_gtfs_route_index(
        operators,
        lines_by_operator,
        route_index_feeds,
    )
    existing_work = annotate_existing_work()
    manual_official_work = manual_official_timetable_leads()

    operator_entries: list[dict[str, Any]] = []
    status_counts: dict[str, int] = defaultdict(int)
    total_known_train_instances = 0
    unique_existing_file_counts: dict[str, int] = {}

    for operator in operators:
        operator_name = operator["operatorName"]
        source_leads: list[dict[str, Any]] = []
        source_leads.extend(existing_work.get(operator_name, []))
        source_leads.extend(ODPT_RAIL_GTFS_LEADS.get(operator_name, []))
        source_leads.extend(manual_official_work.get(operator_name, []))
        source_leads.extend(gtfs_matches.get(operator_name, []))
        source_leads.extend(route_index_matches.get(operator_name, []))
        source_leads.extend(official_site_matches.get(operator_name, []))
        source_leads = dedupe_source_leads(source_leads)

        known = sum(int(lead.get("totalKnownTrainInstances") or 0) for lead in source_leads)
        total_known_train_instances += known
        for lead in source_leads:
            for path, count in (lead.get("trainInstanceCounts") or {}).items():
                unique_existing_file_counts[path] = int(count)
        has_existing = any(
            lead.get("sourceKind") in {"existing_v3_collector", "existing_partial_collector", "collector_available_not_full"}
            for lead in source_leads
        )
        has_rail_gtfs = any(
            lead.get("sourceKind") == "odpt_rail_gtfs_candidate"
            or lead.get("candidateStatus") == "rail_gtfs_candidate"
            for lead in source_leads
        )
        has_unverified_candidate = any(
            lead.get("candidateStatus") == "unverified_name_match" for lead in source_leads
        )
        has_rejected_name_match = any(
            lead.get("candidateStatus") == "rejected_bus_only_name_match" for lead in source_leads
        )
        has_official_page = any(
            lead.get("sourceKind") in {
                "official_timetable_page_candidate",
                "manual_official_timetable_page_candidate",
            }
            for lead in source_leads
        )
        if has_existing and has_rail_gtfs:
            source_status = "existing_work_and_external_candidate"
        elif has_existing:
            source_status = "existing_work"
        elif has_rail_gtfs:
            source_status = "external_candidate_found"
        elif has_official_page:
            source_status = "official_page_candidate_found"
        elif has_unverified_candidate:
            source_status = "unverified_candidate_found"
        elif has_rejected_name_match:
            source_status = "needs_source_research_rejected_name_match_only"
        else:
            source_status = "needs_source_research"
        status_counts[source_status] += 1

        operator_lines = sorted(lines_by_operator[operator_name], key=lambda item: item["lineName"])
        operator_entries.append(
            {
                "operatorId": operator["operatorId"],
                "operatorName": operator_name,
                "lineCount": operator["lineCount"],
                "lineNames": [line["lineName"] for line in operator_lines],
                "physicalStationCount": operator["physicalStationCount"],
                "trackCenterlineCount": operator["trackCenterlineCount"],
                "sourceStatus": source_status,
                "knownTrainInstanceCount": known,
                "sourceLeads": source_leads,
            }
        )

    coverage_summary = {
        "operatorCount": len(operators),
        "operatorLineCount": len(inventory["lines"]),
        "gtfsRepositoryFeedsScanned": len(gtfs_feeds),
        "operatorLeadKnownTrainInstances": total_known_train_instances,
        "uniqueExistingDataFiles": len(unique_existing_file_counts),
        "uniqueKnownTrainInstancesFromExistingFiles": sum(unique_existing_file_counts.values()),
        "sourceStatusCounts": dict(sorted(status_counts.items())),
        "gtfsRepositoryMatchStats": gtfs_stats,
        "gtfsRouteIndexMatchStats": route_index_stats,
        "officialSiteCandidateStats": official_site_stats,
        "warnings": warnings,
    }

    return {
        "schema": "onichase.v4.timetable_source_registry.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "sourcePolicy": [
            "Prefer official GTFS/GTFS-JP/API sources before scraping timetable pages.",
            "Reuse the v3 station alias and station-group matching method for v4 timetable stop matching.",
            "Treat GTFS repository name matches as leads until route types and station coverage are audited.",
        ],
        "inputs": {
            "lineInventory": str(args.inventory),
            "gtfsRepositoryFilesUrl": None if args.no_network else GTFS_REPOSITORY_FILES_URL,
            "gtfsRouteIndex": str(args.gtfs_route_index) if args.gtfs_route_index else None,
            "officialSiteCandidates": str(args.official_site_candidates) if args.official_site_candidates else None,
            "odptCatalogSeeds": sorted(ODPT_RAIL_GTFS_LEADS),
        },
        "coverageSummary": coverage_summary,
        "operators": operator_entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--gtfs-route-index", type=Path, default=DEFAULT_GTFS_ROUTE_INDEX)
    parser.add_argument("--official-site-candidates", type=Path, default=DEFAULT_OFFICIAL_SITE_CANDIDATES)
    parser.add_argument("--skip-route-type-inspection", action="store_true")
    parser.add_argument("--max-candidate-downloads", type=int, default=40)
    args = parser.parse_args()

    registry = build_registry(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(registry, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    summary = registry["coverageSummary"]
    print(f"Wrote {args.output}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
