#!/usr/bin/env python3
"""Collect official Ishigaki Airport bus sources."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import ssl
import subprocess
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AIRPORT_PAGE = "https://www.ishigaki-airport.co.jp/access/bus-taxi/index.html"
KARRY_URL = "https://karrykanko.com/ishigaki/"
AZUMA_URL = "https://www.azumabus.co.jp/"
AZUMA_ROUTE10_URL = "http://www.azumabus.co.jp/mwbhpwp/wp-content/uploads/304ee517825e26f2c4586d9463f9408d.pdf"
AZUMA_ROUTE10_NAVITIME_URL = "https://www.navitime.co.jp/bus/company/00001313/route/00070167/"
AZUMA_ROUTE4_URL = "http://www.azumabus.co.jp/mwbhpwp/wp-content/uploads/8b0914b31ee1e3a38334fa0a71c5c980.pdf"
AZUMA_ROUTE4_NAVITIME_URL = "https://www.navitime.co.jp/bus/company/00001313/route/00070168/"
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "ishigaki_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_ishigaki_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_ishigaki_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_ishigaki_airport_official_bus_audit.json"

AZUMA_ROUTE10_DOWN_ROWS = [
    ("バスターミナル", ["07:45", "11:15", "12:45", "13:15", "14:45"]),
    ("石垣港離島ターミナル", ["07:46", "11:16", "12:46", "13:16", "14:46"]),
    ("桟橋通り", ["07:49", "11:19", "12:49", "13:19", "14:49"]),
    ("登野城小学校前", ["07:50", "11:20", "12:50", "13:20", "14:50"]),
    ("アートホテル石垣島", ["07:53", "11:23", "12:53", "13:23", "14:53"]),
    ("みんさー工芸館前", ["07:57", "11:27", "12:57", "13:27", "14:57"]),
    ("中央運動公園入口", ["07:58", "11:28", "12:58", "13:28", "14:58"]),
    ("平得北", ["07:59", "11:29", "12:59", "13:29", "14:59"]),
    ("真栄里東", ["08:03", "11:33", "13:03", "13:33", "15:03"]),
    ("ANAインターコンチネンタル", ["08:04", "11:34", "13:04", "13:34", "15:04"]),
    ("沖縄県八重山合同庁舎前", ["08:06", "11:36", "13:06", "13:36", "15:06"]),
    ("徳洲会病院前", ["08:06", "11:36", "13:06", "13:36", "15:06"]),
    ("ドン・キホーテ前", ["08:06", "11:36", "13:06", "13:36", "15:06"]),
    ("大浜農協前", ["08:07", "11:37", "13:07", "13:37", "15:07"]),
    ("大浜", ["08:08", "11:38", "13:08", "13:38", "15:08"]),
    ("磯辺", ["08:10", "11:40", "13:10", "13:40", "15:10"]),
    ("太陽の里前", ["08:10", "11:40", "13:10", "13:40", "15:10"]),
    ("宮良団地前", ["08:11", "11:41", "13:11", "13:41", "15:11"]),
    ("宮良橋", ["08:12", "11:42", "13:12", "13:42", "15:12"]),
    ("宮良西", ["08:13", "11:43", "13:13", "13:43", "15:13"]),
    ("宮良東", ["08:14", "11:44", "13:14", "13:44", "15:14"]),
    ("特別支援学校", ["08:15", "11:45", "13:15", "13:45", "15:15"]),
    ("ばすきなよお入口", ["08:16", "11:46", "13:16", "13:46", "15:16"]),
    ("白保中学校", ["08:16", "11:46", "13:16", "13:46", "15:16"]),
    ("白保小学校", ["08:17", "11:47", "13:17", "13:47", "15:17"]),
    ("白保", ["08:18", "11:48", "13:18", "13:48", "15:18"]),
    ("盛山南", ["08:22", "11:52", "13:22", "13:52", "15:22"]),
    ("石垣空港", ["08:25", "11:55", "13:25", "13:55", "15:25"]),
]

AZUMA_ROUTE10_UP_ROWS = [
    ("石垣空港", ["08:45", "12:15", "13:45", "14:15", "15:45"]),
    ("白保", ["08:52", "12:22", "13:52", "14:22", "15:52"]),
    ("白保小学校", ["08:53", "12:23", "13:53", "14:23", "15:53"]),
    ("白保中学校", ["08:54", "12:24", "13:54", "14:24", "15:54"]),
    ("ばすきなよお入口", ["08:54", "12:24", "13:54", "14:24", "15:54"]),
    ("特別支援学校", ["08:55", "12:25", "13:55", "14:25", "15:55"]),
    ("宮良東", ["08:56", "12:26", "13:56", "14:26", "15:56"]),
    ("宮良西", ["08:56", "12:26", "13:56", "14:26", "15:56"]),
    ("宮良橋", ["08:57", "12:27", "13:57", "14:27", "15:57"]),
    ("宮良団地前", ["08:58", "12:28", "13:58", "14:28", "15:58"]),
    ("太陽の里前", ["08:59", "12:29", "13:59", "14:29", "15:59"]),
    ("磯辺", ["08:59", "12:29", "13:59", "14:29", "15:59"]),
    ("大浜", ["09:01", "12:31", "14:01", "14:31", "16:01"]),
    ("大浜農協前", ["09:02", "12:32", "14:02", "14:32", "16:02"]),
    ("ドン・キホーテ前", ["09:02", "12:32", "14:02", "14:32", "16:02"]),
    ("徳洲会病院前", ["09:03", "12:33", "14:03", "14:33", "16:03"]),
    ("沖縄県八重山合同庁舎前", ["09:03", "12:33", "14:03", "14:33", "16:03"]),
    ("ANAインターコンチネンタル", ["09:06", "12:36", "14:06", "14:36", "16:06"]),
    ("真栄里東", ["09:07", "12:37", "14:07", "14:37", "16:07"]),
    ("平得北", ["09:10", "12:40", "14:10", "14:40", "16:10"]),
    ("中央運動公園入口", ["09:11", "12:41", "14:11", "14:41", "16:11"]),
    ("みんさー工芸館前", ["09:12", "12:42", "14:12", "14:42", "16:12"]),
    ("アートホテル石垣島", ["09:16", "12:46", "14:16", "14:46", "16:16"]),
    ("登野城小学校前", ["09:19", "12:49", "14:19", "14:49", "16:19"]),
    ("桟橋通り", ["09:20", "12:50", "14:20", "14:50", "16:20"]),
    ("石垣港離島ターミナル", ["09:23", "12:53", "14:23", "14:53", "16:23"]),
    ("バスターミナル", ["09:25", "12:55", "14:25", "14:55", "16:25"]),
]

AZUMA_ROUTE10_STOP_COORDS = {
    "バスターミナル": (24.332664, 124.155814, "00428242"),
    "桟橋通り": (24.334711, 124.160553, "00428144"),
    "登野城小学校前": (24.337329, 124.163007, "00428145"),
    "アートホテル石垣島": (24.341904, 124.160287, "00428185"),
    "みんさー工芸館前": (24.335732, 124.170587, "00428217"),
    "中央運動公園入口": (24.335659, 124.175062, "00428219"),
    "平得北": (24.333973, 124.178369, "00428218"),
    "真栄里東": (24.330743, 124.185947, "00428223"),
    "ANAインターコンチネンタル": (24.330690, 124.188922, "00428188"),
    "沖縄県八重山合同庁舎前": (24.334021, 124.186936, "00428110"),
    "徳洲会病院前": (24.335123, 124.190119, "00428111"),
    "ドン・キホーテ前": (24.335766, 124.191618, "00428245"),
    "大浜農協前": (24.337047, 124.195223, "00428112"),
    "大浜": (24.338970, 124.196554, "00428113"),
    "磯辺": (24.349931, 124.201712, "00428140"),
    "太陽の里前": (24.350938, 124.204881, "00428114"),
    "宮良団地前": (24.351921, 124.208204, "00428115"),
    "宮良橋": (24.353272, 124.212549, "00428116"),
    "宮良西": (24.347531, 124.220874, "00428117"),
    "宮良東": (24.346331, 124.223114, "00428243"),
    "特別支援学校": (24.346011, 124.225688, "00428119"),
    "ばすきなよお入口": (24.346421, 124.233327, "00428120"),
    "白保中学校": (24.346580, 124.235660, "00428121"),
    "白保小学校": (24.347502, 124.239179, "00428122"),
    "白保": (24.349734, 124.241257, "00428123"),
    "盛山南": (24.377801, 124.243894, "00428124"),
}

AZUMA_ROUTE4_EXTRA_STOP_COORDS = {
    "博物館前": (24.332899, 124.159169, "00428102"),
    "裁判所前": (24.331000, 124.161210, "00428103"),
    "八重山毎日新聞社前": (24.331759, 124.165078, "00428233"),
    "かねひで前": (24.332011, 124.169314, "00428105"),
    "平得": (24.332696, 124.174080, "00428106"),
    "平得東": (24.332274, 124.178852, "00428108"),
    "サンエー前": (24.332520, 124.182803, "00428109"),
}

AZUMA_ROUTE4_DOWN_DEPARTURES = [
    "06:30",
    "07:00",
    "07:30",
    "08:00",
    "08:30",
    "09:00",
    "09:30",
    "10:00",
    "10:30",
    "11:00",
    "11:30",
    "12:00",
    "12:30",
    "13:00",
    "13:30",
    "14:00",
    "14:30",
    "15:00",
    "15:30",
    "16:00",
    "16:30",
    "17:00",
    "17:30",
    "18:00",
    "18:30",
    "19:00",
    "19:30",
    "20:00",
    "21:00",
]

AZUMA_ROUTE4_UP_DEPARTURES = [
    "07:15",
    "07:45",
    "08:30",
    "09:00",
    "09:30",
    "10:00",
    "10:30",
    "11:00",
    "11:30",
    "12:00",
    "12:30",
    "13:00",
    "13:30",
    "14:00",
    "14:30",
    "15:00",
    "15:30",
    "16:00",
    "16:30",
    "17:00",
    "17:30",
    "18:00",
    "18:30",
    "19:00",
    "19:30",
    "20:00",
    "20:30",
    "21:00",
    "21:45",
]

AZUMA_ROUTE4_DOWN_OFFSETS = [
    ("バスターミナル", 0, None),
    ("石垣港離島ターミナル", 3, {27, 28}),
    ("博物館前", 5, None),
    ("裁判所前", 6, None),
    ("八重山毎日新聞社前", 8, None),
    ("かねひで前", 10, None),
    ("平得", 12, None),
    ("平得東", 13, None),
    ("サンエー前", 15, None),
    ("沖縄県八重山合同庁舎前", 16, None),
    ("徳洲会病院前", 16, None),
    ("ドン・キホーテ前", 16, None),
    ("大浜農協前", 17, None),
    ("大浜", 18, None),
    ("磯辺", 20, None),
    ("太陽の里前", 20, None),
    ("宮良団地前", 21, None),
    ("宮良橋", 22, None),
    ("宮良西", 23, None),
    ("宮良東", 24, None),
    ("特別支援学校", 25, None),
    ("ばすきなよお入口", 26, None),
    ("白保中学校", 26, None),
    ("白保小学校", 27, None),
    ("白保", 28, None),
    ("盛山南", 32, None),
    ("石垣空港", 35, None),
]

AZUMA_ROUTE4_UP_OFFSETS = [
    ("石垣空港", 0, None),
    ("白保", 7, None),
    ("白保小学校", 8, None),
    ("白保中学校", 9, None),
    ("ばすきなよお入口", 9, None),
    ("特別支援学校", 10, None),
    ("宮良東", 11, None),
    ("宮良西", 11, None),
    ("宮良橋", 12, None),
    ("宮良団地前", 13, None),
    ("太陽の里前", 14, None),
    ("磯辺", 14, None),
    ("大浜", 16, None),
    ("大浜農協前", 17, None),
    ("ドン・キホーテ前", 17, None),
    ("徳洲会病院前", 18, None),
    ("沖縄県八重山合同庁舎前", 18, None),
    ("サンエー前", 19, None),
    ("平得東", 22, None),
    ("平得", 23, None),
    ("かねひで前", 25, None),
    ("八重山毎日新聞社前", 26, {0, 1}),
    ("裁判所前", 28, {0, 1}),
    ("博物館前", 29, {0, 1}),
    ("石垣港離島ターミナル", 32, {24, 25, 26, 27, 28}),
    ("バスターミナル", 35, None),
]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    suffix = ".pdf" if urllib.parse.urlparse(url).path.lower().endswith(".pdf") else ".html"
    return cache_dir / f"{digest}{suffix}"


def fetch_bytes(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[bytes, Path, str]:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        content_type = "application/pdf" if path.suffix == ".pdf" else "text/html"
        return path.read_bytes(), path, content_type
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    context = ssl._create_unverified_context() if "azumabus.co.jp" in url else None
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        data = response.read()
        content_type = response.headers.get("content-type", "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data, path, content_type


def fetch_text(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[str, Path]:
    data, path, _content_type = fetch_bytes(url, cache_dir, refresh=refresh, timeout=timeout)
    return data.decode("utf-8", "ignore"), path


def plain_text(html_text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html_text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def azuma_pdf_links(html_text: str) -> list[dict[str, str]]:
    links = []
    seen: set[str] = set()
    for match in re.finditer(r"<a[^>]+href=[\"']([^\"']+\.pdf)[\"'][^>]*>(.*?)</a>", html_text, re.S | re.I):
        url = urllib.parse.urljoin(AZUMA_URL, html.unescape(match.group(1)))
        if url in seen:
            continue
        seen.add(url)
        label = re.sub("<.*?>", " ", match.group(2))
        label = re.sub(r"\s+", " ", html.unescape(label)).strip()
        if any(token in label for token in ["空港", "Airport", "広域", "路線図", "時刻表"]):
            links.append({"label": label, "url": url})
    return links


def pdf_text(path: Path) -> str:
    try:
        completed = subprocess.run(["pdftotext", str(path), "-"], check=False, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout if completed.returncode == 0 else ""


def parse_hour_blocks(body: str, heading: str) -> list[str]:
    start = body.find(heading)
    if start < 0:
        return []
    end_candidates = [body.find(next_heading, start + len(heading)) for next_heading in ["石垣空港発 時刻表", "石垣港離島ターミナル発 時刻表", "カリー観光石垣営業所"] if body.find(next_heading, start + len(heading)) > 0]
    end = min(end_candidates) if end_candidates else len(body)
    segment = body[start:end]
    times = []
    for hour_match in re.finditer(r"(\d{1,2})時\s+([^時]+?)(?=\s+\d{1,2}時|$)", segment):
        hour = int(hour_match.group(1))
        minutes = re.findall(r"(?<!\d)(\d{1,2})(?!\d)", hour_match.group(2))
        for minute in minutes:
            value = int(minute)
            if 0 <= value < 60:
                times.append(f"{hour:02d}:{value:02d}")
    return times


def parse_karry_route(html_text: str, cache_path: Path) -> dict[str, Any]:
    body = plain_text(html_text)
    airport_departures = parse_hour_blocks(body, "石垣空港発 時刻表")
    terminal_departures = parse_hour_blocks(body, "石垣港離島ターミナル発 時刻表")
    fare_match = re.search(r"片道運賃\s+大人：(\d+)円\s+小人：(\d+)円", body)
    adult_fare = int(fare_match.group(1)) if fare_match else 550
    child_fare = int(fare_match.group(2)) if fare_match else 280
    trips = []
    for index, departure in enumerate(airport_departures, start=1):
        hour, minute = map(int, departure.split(":"))
        arrival_minutes = hour * 60 + minute + 30
        trips.append(
            {
                "tripId": f"isg_karry:from_airport:{index:03d}",
                "direction": "from_airport",
                "stopTimes": [
                    {"stopName": "石垣空港", "time": departure},
                    {"stopName": "石垣港離島ターミナル", "time": f"{arrival_minutes // 60:02d}:{arrival_minutes % 60:02d}"},
                ],
            }
        )
    for index, departure in enumerate(terminal_departures, start=1):
        hour, minute = map(int, departure.split(":"))
        arrival_minutes = hour * 60 + minute + 30
        trips.append(
            {
                "tripId": f"isg_karry:to_airport:{index:03d}",
                "direction": "to_airport",
                "stopTimes": [
                    {"stopName": "石垣港離島ターミナル", "time": departure},
                    {"stopName": "石垣空港", "time": f"{arrival_minutes // 60:02d}:{arrival_minutes % 60:02d}"},
                ],
            }
        )
    return {
        "sourceKind": "official_karry_html_timetable",
        "operatorName": "カリー観光",
        "airportIata": "ISG",
        "routeCode": "isg_karry_direct",
        "routeName": "石垣空港 ⇔ 石垣港離島ターミナル直行バス",
        "sourceUrl": KARRY_URL,
        "cachePath": str(cache_path.relative_to(ROOT)),
        "adultFareYen": adult_fare,
        "childFareYen": child_fare,
        "routeStopNames": ["石垣空港", "石垣港離島ターミナル"],
        "trips": trips,
        "tripCount": len(trips),
    }


def build_column_trips(route_code: str, direction: str, rows: list[tuple[str, list[str]]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    column_count = len(rows[0][1])
    trips = []
    for column in range(column_count):
        stop_times = []
        for stop_name, times in rows:
            if column >= len(times):
                continue
            stop_times.append({"stopName": stop_name, "time": times[column]})
        trips.append(
            {
                "tripId": f"{route_code}:{direction}:{column + 1:03d}",
                "direction": direction,
                "stopTimes": stop_times,
            }
        )
    return trips


def build_offset_trips(route_code: str, direction: str, departures: list[str], offsets: list[tuple[str, int, set[int] | None]]) -> list[dict[str, Any]]:
    trips = []
    for index, departure in enumerate(departures):
        hour, minute = map(int, departure.split(":"))
        base = hour * 60 + minute
        stop_times = []
        for stop_name, offset, skipped_indexes in offsets:
            if skipped_indexes and index in skipped_indexes:
                continue
            value = base + offset
            stop_times.append({"stopName": stop_name, "time": f"{value // 60:02d}:{value % 60:02d}"})
        trips.append(
            {
                "tripId": f"{route_code}:{direction}:{index + 1:03d}",
                "direction": direction,
                "stopTimes": stop_times,
            }
        )
    return trips


def route_stop_names_from_offsets(offsets: list[tuple[str, int, set[int] | None]]) -> list[str]:
    names = []
    for name, _offset, _skipped in offsets:
        if name not in names:
            names.append(name)
    return names


def parse_azuma_route4(cache_path: Path) -> dict[str, Any]:
    route_code = "isg_azuma_route4_airport"
    trips = build_offset_trips(route_code, "to_airport", AZUMA_ROUTE4_DOWN_DEPARTURES, AZUMA_ROUTE4_DOWN_OFFSETS) + build_offset_trips(
        route_code, "from_airport", AZUMA_ROUTE4_UP_DEPARTURES, AZUMA_ROUTE4_UP_OFFSETS
    )
    merged_coords = AZUMA_ROUTE10_STOP_COORDS | AZUMA_ROUTE4_EXTRA_STOP_COORDS
    bus_stops = []
    for name, (lat, lon, node_id) in merged_coords.items():
        bus_stops.append(
            {
                "name": name,
                "lat": lat,
                "lon": lon,
                "coordinateSource": "NAVITIME bus stop page",
                "coordinateSourceUrl": f"https://www.navitime.co.jp/diagram/bus/{node_id}/00070168/",
            }
        )
    return {
        "sourceKind": "official_azuma_pdf_timetable",
        "operatorName": "東運輸",
        "airportIata": "ISG",
        "routeCode": route_code,
        "routeName": "系統④ 平得・大浜・白保経由空港線",
        "sourceUrl": AZUMA_ROUTE4_URL,
        "cachePath": str(cache_path.relative_to(ROOT)),
        "coordinateReferenceUrl": AZUMA_ROUTE4_NAVITIME_URL,
        "serviceDays": "daily",
        "routeStopNames": route_stop_names_from_offsets(AZUMA_ROUTE4_DOWN_OFFSETS),
        "busStops": bus_stops,
        "trips": trips,
        "tripCount": len(trips),
    }


def parse_azuma_route10(cache_path: Path) -> dict[str, Any]:
    route_code = "isg_azuma_route10_airport"
    trips = build_column_trips(route_code, "to_airport", AZUMA_ROUTE10_DOWN_ROWS) + build_column_trips(
        route_code, "from_airport", AZUMA_ROUTE10_UP_ROWS
    )
    bus_stops = []
    for name, (lat, lon, node_id) in AZUMA_ROUTE10_STOP_COORDS.items():
        bus_stops.append(
            {
                "name": name,
                "lat": lat,
                "lon": lon,
                "coordinateSource": "NAVITIME bus stop page",
                "coordinateSourceUrl": f"https://www.navitime.co.jp/diagram/bus/{node_id}/00070167/",
            }
        )
    return {
        "sourceKind": "official_azuma_pdf_timetable",
        "operatorName": "東運輸",
        "airportIata": "ISG",
        "routeCode": route_code,
        "routeName": "系統⑩ アートホテル・ANAインターコンチネンタル経由空港線",
        "sourceUrl": AZUMA_ROUTE10_URL,
        "cachePath": str(cache_path.relative_to(ROOT)),
        "coordinateReferenceUrl": AZUMA_ROUTE10_NAVITIME_URL,
        "serviceDays": "daily",
        "routeStopNames": [name for name, _times in AZUMA_ROUTE10_DOWN_ROWS],
        "busStops": bus_stops,
        "trips": trips,
        "tripCount": len(trips),
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    airport_html, airport_cache = fetch_text(AIRPORT_PAGE, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    karry_html, karry_cache = fetch_text(KARRY_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    azuma_html, azuma_cache = fetch_text(AZUMA_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    routes = [parse_karry_route(karry_html, karry_cache)]
    pdf_sources = []
    route4_cache = None
    route10_cache = None
    for link in azuma_pdf_links(azuma_html):
        _data, path, content_type = fetch_bytes(link["url"], args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        if link["url"] == AZUMA_ROUTE4_URL:
            route4_cache = path
        if link["url"] == AZUMA_ROUTE10_URL:
            route10_cache = path
        text = pdf_text(path)
        times = sorted(set(re.findall(r"\b\d{1,2}:\d{2}\b", text)))
        pdf_sources.append(
            {
                "label": link["label"],
                "sourceUrl": link["url"],
                "cachePath": str(path.relative_to(ROOT)),
                "contentType": content_type,
                "status": "pdf_time_text_found" if times else "pdf_cached_no_time_text",
                "timeTextCount": len(times),
                "sampleTimes": times[:20],
            }
        )
    status_counts = Counter(source["status"] for source in pdf_sources)
    if route4_cache:
        routes.append(parse_azuma_route4(route4_cache))
    if route10_cache:
        routes.append(parse_azuma_route10(route10_cache))
    source = {
        "schemaVersion": "v5_official_bus_source.ishigaki_airport.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Ishigaki Airport bus sources. Karry Kanko direct-bus HTML and Azuma Bus route 4/10 official PDFs are normalized into trips. Azuma stop coordinates are referenced from NAVITIME stop pages because the official PDFs provide stop names and stop-times but not machine-readable coordinates. Remaining Azuma PDFs stay cached until a dedicated table parser is added.",
        "airportPage": {"sourceUrl": AIRPORT_PAGE, "cachePath": str(airport_cache.relative_to(ROOT)), "candidateTimeTextCount": len(re.findall(r"\b\d{1,2}:\d{2}\b", plain_text(airport_html)))},
        "azumaIndexPage": {"sourceUrl": AZUMA_URL, "cachePath": str(azuma_cache.relative_to(ROOT)), "pdfCount": len(pdf_sources)},
        "azumaPdfSources": pdf_sources,
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.ishigaki_airport.v1",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "tripCount": sum(route["tripCount"] for route in routes),
        "azumaPdfCount": len(pdf_sources),
        "azumaPdfStatusCounts": dict(sorted(status_counts.items())),
        "routes": [
            {"routeCode": route["routeCode"], "tripCount": route["tripCount"], "adultFareYen": route.get("adultFareYen")}
            for route in routes
        ],
        "azumaPdfSources": [{k: source[k] for k in ["label", "status", "timeTextCount", "sourceUrl"]} for source in pdf_sources],
    }
    return source, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    source, audit = collect(args)
    write_json(args.output, source)
    write_json(args.docs_output, source)
    write_json(args.audit_output, audit)
    print(json.dumps({"routeCount": audit["routeCount"], "tripCount": audit["tripCount"], "azumaPdfCount": audit["azumaPdfCount"], "azumaPdfStatusCounts": audit["azumaPdfStatusCounts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
