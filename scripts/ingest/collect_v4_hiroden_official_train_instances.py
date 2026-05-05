#!/usr/bin/env python3
"""Collect v4 weekday train instances from Hiroden official tram timetable CGI.

Hiroden publishes route-level PDFs, but the station timetable CGI expands each
departure into a "号車別時刻表" page with concrete downstream stop times.  This
collector crawls all official tram stops/directions, keeps the earliest observed
page for each real service, and converts those official stop lists into the v4
train_instances schema.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collect_v4_gtfs_train_instances import V4StationMatcher, load_json, normalize_name_variants, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_LINE_INVENTORY = ROOT / "data" / "v4_nationwide_line_inventory.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_hiroden_official_cache"
DEFAULT_OUTPUT = ROOT / "data" / "v4_hiroden_official_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_hiroden_official_train_instances_audit.json"
DEFAULT_SERVICE_DATE = "2026-04-27"

BASE = "https://www.hiroden.co.jp"
CGI_BASE = f"{BASE}/cgi-bin/"
OPERATOR_NAME = "広島電鉄"
SOURCE_FEED_KEY = "hiroden_official_tram_cgi"

ROUTE_SOURCES = [
    {"key": "r01", "ri": "01", "display": "1号線", "label": "広島駅−広島港", "primaryLine": "宇品線"},
    {"key": "r02", "ri": "02", "display": "2号線", "label": "広島駅−宮島口", "primaryLine": "宮島線"},
    {"key": "r03", "ri": "03", "display": "3号線", "label": "西広島−広電本社前", "primaryLine": "本線"},
    {"key": "r04", "ri": "04", "display": "循環線", "label": "循環線", "primaryLine": "皆実線"},
    {"key": "r05", "ri": "05", "display": "5号線", "label": "広島駅−比治山下−広島港", "primaryLine": "皆実線"},
    {"key": "r06", "ri": "06", "display": "6号線", "label": "広島駅−江波", "primaryLine": "江波線"},
    {"key": "r07", "ri": "07", "display": "7号線", "label": "横川駅−広島港", "primaryLine": "横川線"},
    {"key": "r08", "ri": "08", "display": "8号線", "label": "横川駅−江波", "primaryLine": "横川線"},
    {"key": "r09", "ri": "09", "display": "9号線", "label": "江波−八丁堀−白島", "primaryLine": "白島線"},
]
ROUTE_BY_RI = {source["ri"]: source for source in ROUTE_SOURCES}

STATION_ALIASES = {
    "ＪＡ": ["JA広島病院前"],
    "JA": ["JA広島病院前"],
    "ドーム": ["原爆ドーム前"],
    "紙屋東": ["紙屋町東"],
    "紙屋西": ["紙屋町西"],
    "十日市": ["十日市町"],
    "西広島": ["広電西広島", "広電西広島（己斐）"],
    "西観音": ["西観音町"],
    "商工セ": ["商工センター入口"],
    "修大協": ["修大協創中高前"],
    "五日市": ["広電五日市"],
    "佐伯区": ["佐伯区役所前"],
    "山陽女": ["山陽女学園前"],
    "廿市役": ["廿日市市役所前", "廿日市市役所前（平良）"],
    "阿品": ["広電阿品"],
    "宮島口": ["広電宮島口"],
    "広島港": ["広島港", "広島港（宇品）"],
    "広電前": ["広電本社前"],
    "元宇品": ["元宇品口"],
    "日赤前": ["日赤病院前"],
    "市役所": ["市役所前"],
    "県病院": ["県病院前"],
    "広大附": ["広大附属学校前"],
    "皆実六": ["皆実町六丁目"],
    "皆実二": ["皆実町二丁目"],
    "比治橋": ["比治山橋"],
    "比治下": ["比治山下"],
    "宇品二": ["宇品二丁目"],
    "宇品三": ["宇品三丁目"],
    "宇品四": ["宇品四丁目"],
    "宇品五": ["宇品五丁目"],
    "横川一": ["横川一丁目"],
    "舟入幸": ["舟入幸町"],
    "舟入川": ["舟入川口町"],
    "舟入本": ["舟入本町"],
    "家裁前": ["家庭裁判所前"],
    "家庭裁": ["家庭裁判所前"],
    "縮景園": ["縮景園前"],
    "女学院": ["女学院前"],
    "猿猴橋": ["猿猴橋町"],
    "段原一": ["段原一丁目"],
    "南区役": ["南区役所前"],
}

LINE_PREFERENCES_BY_ROUTE = {
    "01": ["本線", "宇品線"],
    "02": ["宮島線", "本線"],
    "03": ["本線", "宇品線"],
    "04": ["皆実線", "本線", "白島線", "宇品線"],
    "05": ["皆実線", "宇品線", "本線"],
    "06": ["本線", "江波線"],
    "07": ["横川線", "本線", "宇品線"],
    "08": ["横川線", "江波線", "本線"],
    "09": ["江波線", "本線", "白島線"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "").replace("\u3000", "")


def strip_tags(value: str) -> str:
    text = re.sub(r"<!--.*?-->", "", value or "", flags=re.DOTALL)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_station_name(value: str) -> str:
    text = strip_tags(value)
    text = compact(text)
    text = text.replace("ＪＡ", "JA")
    return text


def canonical_station_names(value: str) -> list[str]:
    cleaned = clean_station_name(value)
    names = [cleaned, *STATION_ALIASES.get(cleaned, [])]
    output: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name and name not in seen:
            seen.add(name)
            output.append(name)
    return output


def parse_hhmm(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d{1,2})\s*:\s*(\d{2})", value)
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"


def minutes(value: str | None) -> int | None:
    hhmm = parse_hhmm(value)
    if not hhmm:
        return None
    hour_text, minute_text = hhmm.split(":")
    total = int(hour_text) * 60 + int(minute_text)
    if total < 3 * 60:
        total += 24 * 60
    return total


def load_physical_map(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def cache_path(cache_dir: Path, namespace: str, key: str, suffix: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return cache_dir / namespace / f"{digest}{suffix}"


def fetch_text_cached(url: str, cache_dir: Path, namespace: str, refresh: bool, timeout: int = 90) -> str:
    path = cache_path(cache_dir, namespace, url, ".html")
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8", errors="replace")
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,*/*",
            "User-Agent": "Mozilla/5.0 (compatible; OniChase-v4-hiroden-official-collector/0.1)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    text = raw.decode(charset, errors="replace")
    path.write_text(text, encoding="utf-8")
    return text


def cgi_url(script: str, params: dict[str, str]) -> str:
    return urllib.parse.urljoin(CGI_BASE, script) + "?" + urllib.parse.urlencode(params)


def query_without_sn(url: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(url)
    params = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    params.pop("sn", None)
    return params


class HirodenPhysicalIndex:
    def __init__(self, physical_map: dict[str, Any], line_inventory: dict[str, Any]) -> None:
        self.matcher = V4StationMatcher(physical_map)
        self.station_by_id = {station["id"]: station for station in physical_map.get("physicalStations", [])}
        self.line_id_by_operator_line: dict[tuple[str, str], str] = {}
        self.line_color_by_operator_line: dict[tuple[str, str], str] = {}
        self.station_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.line_station_names: dict[str, set[str]] = defaultdict(set)
        for line in line_inventory.get("lines", []):
            operator_name = str(line.get("operatorName") or "")
            line_name = str(line.get("lineName") or "")
            self.line_id_by_operator_line[(operator_name, line_name)] = str(line.get("id") or line_name)
            self.line_color_by_operator_line[(operator_name, line_name)] = str(
                line.get("lineColor") or line.get("operatorColor") or "#005BAC"
            ).lstrip("#")
        for station in physical_map.get("physicalStations", []):
            if station.get("operatorName") != OPERATOR_NAME:
                continue
            line_name = str(station.get("lineName") or "")
            for key in normalize_name_variants(station.get("nameJa") or ""):
                self.station_by_name[key].append(station)
                self.line_station_names[line_name].add(key)

    def line_id(self, line_name: str) -> str:
        return self.line_id_by_operator_line.get((OPERATOR_NAME, line_name)) or line_name

    def route_color(self, line_name: str) -> str:
        return self.line_color_by_operator_line.get((OPERATOR_NAME, line_name), "#005BAC").lstrip("#")

    def station_for_match(self, match: dict[str, Any]) -> dict[str, Any] | None:
        station_id = match.get("physicalStationId")
        if not station_id:
            return None
        return self.station_by_id.get(str(station_id))

    def candidates(self, station_name: str) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for alias in canonical_station_names(station_name):
            for key in normalize_name_variants(alias):
                for station in self.station_by_name.get(key, []):
                    station_id = str(station.get("id") or "")
                    if station_id in seen:
                        continue
                    seen.add(station_id)
                    output.append(station)
        return output

    def match_stop(self, station_name: str, route_id: str) -> dict[str, Any]:
        preferred_lines = LINE_PREFERENCES_BY_ROUTE.get(route_id, [])
        candidates = self.candidates(station_name)
        if candidates:
            ranked = sorted(
                candidates,
                key=lambda station: (
                    min((preferred_lines.index(station.get("lineName")) for _ in [0] if station.get("lineName") in preferred_lines), default=99),
                    str(station.get("lineName") or ""),
                    str(station.get("stationGroupId") or ""),
                ),
            )
            best = ranked[0]
            return {
                "matched": True,
                "method": "hiroden_name_context",
                "stationGroupId": best["stationGroupId"],
                "physicalStationId": best["id"],
                "candidateCount": len(candidates),
            }
        for alias in canonical_station_names(station_name):
            for line_name in preferred_lines:
                match = self.matcher.match(OPERATOR_NAME, line_name, alias, None, None)
                if match.get("matched"):
                    match["method"] = f"fallback_{line_name}_{match['method']}"
                    return match
        return self.matcher.match(OPERATOR_NAME, preferred_lines[0] if preferred_lines else None, station_name, None, None)


def parse_route_station_links(route_html: str) -> list[dict[str, str]]:
    stations: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"""href=["']psearch\.cgi\?di=(?P<di>[^"']+)["'][^>]*>(?P<name>.*?)</a>""",
        route_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        di = html.unescape(match.group("di")).strip()
        name = strip_tags(match.group("name"))
        if not di or di in seen:
            continue
        seen.add(di)
        stations.append({"di": di, "name": name})
    return stations


def parse_station_directions(station_html: str) -> tuple[str, list[dict[str, str]]]:
    station_name = ""
    strong = re.search(r"<strong>【(?P<name>.*?)】</strong>", station_html, flags=re.DOTALL)
    if strong:
        station_name = strip_tags(strong.group("name"))
    hidden = re.search(r"""name=["']hn["']\s+value=["'](?P<name>[^"']+)["']""", station_html)
    if hidden:
        station_name = html.unescape(hidden.group("name")).strip() or station_name
    directions: list[dict[str, str]] = []
    seen: set[str] = set()
    select_match = re.search(r"""<select\s+name=["']hm["'].*?</select>""", station_html, flags=re.IGNORECASE | re.DOTALL)
    if not select_match:
        return station_name, directions
    for match in re.finditer(r"""<option\s+value=["'](?P<hm>[^"']+)["'][^>]*>(?P<label>.*?)(?=<option|</select>)""", select_match.group(0), flags=re.DOTALL | re.IGNORECASE):
        hm = html.unescape(match.group("hm")).strip()
        label = strip_tags(match.group("label"))
        if not hm or hm in seen:
            continue
        seen.add(hm)
        directions.append({"hm": hm, "label": label})
    return station_name, directions


def parse_departure_links(result_html: str, source_station: dict[str, str], direction: dict[str, str]) -> list[dict[str, Any]]:
    departures: list[dict[str, Any]] = []
    for row_match in re.finditer(r"<tr>(?P<row>.*?)</tr>", result_html, flags=re.DOTALL | re.IGNORECASE):
        row = row_match.group("row")
        if "pjikokuhyo.cgi" not in row:
            continue
        href_match = re.search(r"""href=["'](?P<href>pjikokuhyo\.cgi\?[^"']+)["']""", row, flags=re.IGNORECASE)
        if not href_match:
            continue
        time_match = re.search(r">(?P<time>\d{1,2}:\d{2})</a>", row)
        hhmm = parse_hhmm(time_match.group("time") if time_match else None)
        if not hhmm:
            continue
        href = html.unescape(href_match.group("href"))
        url = urllib.parse.urljoin(CGI_BASE, href)
        params = query_without_sn(url)
        key = tuple(params.get(name, "") for name in ("dk", "ri", "dc", "dt", "sd", "ed", "ss"))
        departures.append(
            {
                "key": key,
                "url": url,
                "time": hhmm,
                "timeMinutes": minutes(hhmm) or 99999,
                "sourceStation": source_station,
                "direction": direction,
                "params": params,
            }
        )
    return departures


def parse_detail_stop_rows(detail_html: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row_match in re.finditer(r"<tr>(?P<row>.*?)</tr>", detail_html, flags=re.DOTALL | re.IGNORECASE):
        row = row_match.group("row")
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.DOTALL | re.IGNORECASE)
        if len(cells) < 2:
            continue
        hhmm = parse_hhmm(strip_tags(cells[0]))
        if not hhmm:
            continue
        station_cell = cells[1]
        code_match = re.search(r"<!--\s*(?P<code>[^-]+?)\s*-->", station_cell)
        station_name = clean_station_name(station_cell)
        if not station_name:
            continue
        rows.append(
            {
                "time": hhmm,
                "stationName": station_name,
                "stationCode": (code_match.group("code").strip() if code_match else ""),
            }
        )
    return rows


def build_train(detail: dict[str, Any], physical_index: HirodenPhysicalIndex) -> tuple[dict[str, Any] | None, Counter[str], list[dict[str, Any]]]:
    rows = detail["rows"]
    params = detail["params"]
    route_id = params.get("ri") or detail.get("routeId") or ""
    route = ROUTE_BY_RI.get(route_id, {"display": f"{route_id}号線", "label": f"{route_id}号線", "primaryLine": ""})
    if len(rows) < 2:
        return None, Counter(), []
    match_methods: Counter[str] = Counter()
    unmatched_samples: list[dict[str, Any]] = []
    stop_times: list[dict[str, Any]] = []
    for sequence, row in enumerate(rows, start=1):
        match = physical_index.match_stop(row["stationName"], route_id)
        station = physical_index.station_for_match(match)
        if match.get("matched"):
            match_methods[str(match["method"])] += 1
        else:
            match_methods[str(match.get("method") or "unmatched")] += 1
            if len(unmatched_samples) < 25:
                unmatched_samples.append(
                    {
                        "stationName": row["stationName"],
                        "stationCode": row.get("stationCode"),
                        "routeId": route_id,
                        "sourceUrl": detail["url"],
                    }
                )
        line_name = str(station.get("lineName") if station else route.get("primaryLine") or "")
        stop_times.append(
            {
                "sequence": sequence,
                "station_name_raw": row["stationName"],
                "station_code": row.get("stationCode"),
                "station_id": match.get("stationGroupId"),
                "station_group_id": match.get("stationGroupId"),
                "physical_station_id": match.get("physicalStationId"),
                "operator_name": OPERATOR_NAME,
                "line_id": physical_index.line_id(line_name) if line_name else "",
                "line_name": line_name,
                "arrival_hhmm": row["time"],
                "departure_hhmm": row["time"],
                "match_method": match.get("method"),
            }
        )
    matched_count = sum(1 for stop in stop_times if stop.get("physical_station_id"))
    if matched_count < 2:
        return None, match_methods, unmatched_samples
    first_time = stop_times[0]["departure_hhmm"]
    last_time = stop_times[-1]["arrival_hhmm"]
    route_display = str(route.get("display") or f"{route_id}号線")
    primary_line = str(route.get("primaryLine") or stop_times[0].get("line_name") or "")
    service_instance_id = (
        f"hiroden:ri{route_id}:dc{params.get('dc','')}:dk{params.get('dk','')}:"
        f"ed{params.get('ed','')}:ss{params.get('ss','')}:{first_time.replace(':', '')}"
    )
    train = {
        "train_number": f"{route_display}{first_time.replace(':', '')}",
        "service_instance_id": service_instance_id,
        "source_trip_id": service_instance_id,
        "operator_id": OPERATOR_NAME,
        "operator_name": OPERATOR_NAME,
        "service_name": route_display,
        "service_number": first_time.replace(":", ""),
        "headsign": stop_times[-1]["station_name_raw"],
        "train_type": route_display,
        "route_color": physical_index.route_color(primary_line) if primary_line else "005BAC",
        "line_id": physical_index.line_id(primary_line) if primary_line else route_display,
        "line_name": primary_line or route_display,
        "source_feed_key": SOURCE_FEED_KEY,
        "origin": stop_times[0]["station_name_raw"],
        "destination": stop_times[-1]["station_name_raw"],
        "source_timetable_url": detail["url"],
        "first_departure_hhmm": first_time,
        "last_arrival_hhmm": last_time,
        "reconstruction_method": "official_tram_cgi_vehicle_timetable",
        "stop_times": stop_times,
    }
    return train, match_methods, unmatched_samples


def discover_station_pages(cache_dir: Path, service_date: str, refresh: bool) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    station_by_di: dict[str, dict[str, str]] = {}
    route_station_links: list[dict[str, Any]] = []
    for route in ROUTE_SOURCES:
        url = cgi_url("rlist.cgi", {"l": route["key"]})
        route_html = fetch_text_cached(url, cache_dir, "route_pages", refresh)
        stations = parse_route_station_links(route_html)
        for station in stations:
            station_by_di.setdefault(station["di"], station)
            route_station_links.append({"route": route, "station": station})
    return list(station_by_di.values()), route_station_links


def collect_station_directions(stations: list[dict[str, str]], cache_dir: Path, refresh: bool, workers: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    tasks: list[tuple[dict[str, str], str]] = [
        (station, cgi_url("psearch.cgi", {"di": station["di"]}))
        for station in stations
    ]
    pages: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch_text_cached, url, cache_dir, "station_pages", refresh): (station, url)
            for station, url in tasks
        }
        for future in as_completed(futures):
            station, url = futures[future]
            try:
                text = future.result()
                official_name, directions = parse_station_directions(text)
                station_name = official_name or station["name"]
                for direction in directions:
                    pages.append({"station": {"di": station["di"], "name": station_name}, "direction": direction})
            except Exception as exc:
                errors.append({"url": url, "station": station.get("name", ""), "error": str(exc)})
    return pages, errors


def collect_departure_links(
    station_directions: list[dict[str, Any]],
    cache_dir: Path,
    service_date_compact: str,
    refresh: bool,
    workers: int,
) -> tuple[dict[tuple[str, ...], dict[str, Any]], list[dict[str, str]], Counter[str]]:
    best_by_key: dict[tuple[str, ...], dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    direction_counts: Counter[str] = Counter()

    def fetch_page(item: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
        station = item["station"]
        direction = item["direction"]
        url = cgi_url(
            "psearch.cgi",
            {
                "act": "1",
                "di": station["di"],
                "hn": station["name"],
                "hm": direction["hm"],
                "dt": service_date_compact,
                "tm": "all",
            },
        )
        return item, url, fetch_text_cached(url, cache_dir, "departure_pages", refresh)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_page, item): item for item in station_directions}
        for future in as_completed(futures):
            item = futures[future]
            try:
                source_item, url, text = future.result()
                station = source_item["station"]
                direction = source_item["direction"]
                direction_counts[f"{station['di']}:{direction['hm']}"] += 1
                for departure in parse_departure_links(text, station, direction):
                    current = best_by_key.get(departure["key"])
                    if current is None or departure["timeMinutes"] < current["timeMinutes"]:
                        best_by_key[departure["key"]] = departure
            except Exception as exc:
                station = item.get("station", {})
                direction = item.get("direction", {})
                errors.append(
                    {
                        "station": station.get("name", ""),
                        "di": station.get("di", ""),
                        "hm": direction.get("hm", ""),
                        "error": str(exc),
                    }
                )
    return best_by_key, errors, direction_counts


def collect_details(best_departures: dict[tuple[str, ...], dict[str, Any]], cache_dir: Path, refresh: bool, workers: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    details: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    def fetch_detail(departure: dict[str, Any]) -> dict[str, Any]:
        text = fetch_text_cached(departure["url"], cache_dir, "detail_pages", refresh)
        params = query_without_sn(departure["url"])
        rows = parse_detail_stop_rows(text)
        return {
            "key": departure["key"],
            "url": departure["url"],
            "params": params,
            "routeId": params.get("ri", ""),
            "sourceStation": departure["sourceStation"],
            "direction": departure["direction"],
            "rows": rows,
        }

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_detail, departure): departure for departure in best_departures.values()}
        for future in as_completed(futures):
            departure = futures[future]
            try:
                detail = future.result()
                details.append(detail)
            except Exception as exc:
                params = departure.get("params", {})
                errors.append(
                    {
                        "routeId": params.get("ri", ""),
                        "dc": params.get("dc", ""),
                        "url": departure.get("url", ""),
                        "error": str(exc),
                    }
                )
    return details, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--line-inventory", type=Path, default=DEFAULT_LINE_INVENTORY)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--service-date", default=DEFAULT_SERVICE_DATE)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    service_date_compact = args.service_date.replace("-", "")
    physical_index = HirodenPhysicalIndex(load_physical_map(args.physical_map), load_json(args.line_inventory))

    stations, route_station_links = discover_station_pages(args.cache_dir, args.service_date, args.refresh)
    station_directions, station_page_errors = collect_station_directions(stations, args.cache_dir, args.refresh, args.workers)
    best_departures, departure_errors, direction_counts = collect_departure_links(
        station_directions,
        args.cache_dir,
        service_date_compact,
        args.refresh,
        args.workers,
    )
    details, detail_errors = collect_details(best_departures, args.cache_dir, args.refresh, args.workers)

    trains: list[dict[str, Any]] = []
    match_methods: Counter[str] = Counter()
    unmatched_samples: list[dict[str, Any]] = []
    detail_short_count = 0
    for detail in details:
        if len(detail.get("rows") or []) < 2:
            detail_short_count += 1
            continue
        train, methods, unmatched = build_train(detail, physical_index)
        match_methods.update(methods)
        unmatched_samples.extend(unmatched)
        if train:
            trains.append(train)

    duplicate_ids = [item for item, count in Counter(train["service_instance_id"] for train in trains).items() if count > 1]
    line_counts = Counter(train["line_name"] for train in trains)
    route_counts = Counter(train["service_name"] for train in trains)
    stop_count_distribution = Counter(str(len(train["stop_times"])) for train in trains)
    audit = {
        "schema": "onichase.v4.hiroden_official_train_instances_audit.v1",
        "generatedAt": now_iso(),
        "serviceDate": args.service_date,
        "sourceFeedKey": SOURCE_FEED_KEY,
        "counts": {
            "routeSourceCount": len(ROUTE_SOURCES),
            "routeStationLinkCount": len(route_station_links),
            "uniqueStationCount": len(stations),
            "stationDirectionCount": len(station_directions),
            "uniqueDepartureKeyCount": len(best_departures),
            "detailPageCount": len(details),
            "detailShortCount": detail_short_count,
            "trainInstanceCount": len(trains),
            "stopTimeCount": sum(len(train.get("stop_times") or []) for train in trains),
            "unmatchedSampleCount": len(unmatched_samples),
            "duplicateIdCount": len(duplicate_ids),
            "stationPageErrorCount": len(station_page_errors),
            "departurePageErrorCount": len(departure_errors),
            "detailPageErrorCount": len(detail_errors),
        },
        "lineTrainCounts": dict(sorted(line_counts.items())),
        "routeTrainCounts": dict(sorted(route_counts.items())),
        "stopCountDistribution": dict(sorted(stop_count_distribution.items(), key=lambda item: int(item[0]))),
        "matchMethods": dict(sorted(match_methods.items())),
        "directionPageCounts": dict(sorted(direction_counts.items())),
        "duplicateIdSample": duplicate_ids[:20],
        "unmatchedSamples": unmatched_samples[:100],
        "stationPageErrors": station_page_errors[:100],
        "departurePageErrors": departure_errors[:100],
        "detailPageErrors": detail_errors[:100],
    }
    payload = {
        "schema": "onichase.v4.train_instances.v1",
        "id": "v4_hiroden_official_weekday_train_instances_v0_1",
        "label": "V4 weekday train instances reconstructed from Hiroden official tram CGI",
        "generatedAt": now_iso(),
        "serviceDate": args.service_date,
        "sourceFeedKey": SOURCE_FEED_KEY,
        "train_instances": sorted(trains, key=lambda item: item["service_instance_id"]),
    }
    write_json(args.output, payload)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(trains)} trains, {audit['counts']['stopTimeCount']} stop_times")
    print(
        f"Wrote {args.audit_output}: unmatched={len(unmatched_samples)} "
        f"duplicate_ids={len(duplicate_ids)} errors={len(station_page_errors) + len(departure_errors) + len(detail_errors)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
