#!/usr/bin/env python3
"""Collect remaining v4 non-JR train instances from Navitime stop-chain pages.

This collector is intentionally generic.  It uses the v4 real physical map as
the seed, discovers Navitime timetable pages from each physical station, parses
full "停車駅/時刻表" stop-chain pages, and keeps only trains that actually touch
the target operator-line in the v4 physical map.

It is a fallback collector for operators that do not yet have a cleaner
official GTFS/API/PDF collector.  Existing official collectors remain preferred
when the current train bundle is built.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import os
import re
import time
import unicodedata
import urllib.parse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from collect_v4_gtfs_train_instances import (
    V4StationMatcher,
    haversine_m,
    normalize_line,
    normalize_name,
    normalize_name_variants,
)
from train_instance_merge import index_train_instances, upsert_train_instance


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_LINE_INVENTORY = ROOT / "data" / "v4_nationwide_line_inventory.json"
DEFAULT_COVERAGE = ROOT / "data" / "v4_non_jr_timetable_coverage_audit.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_navitime_non_jr_cache"
DEFAULT_OUTPUT = ROOT / "data" / "v4_navitime_non_jr_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_navitime_non_jr_train_instances_audit.json"
DEFAULT_SERVICE_DATE = "2026-04-27"

AUTOCOMPLETE_URL = "https://media.cld.navitime.jp/media/biz/widget/diagram/search/train/autocomplete"
NAVITIME_BASE = "https://www.navitime.co.jp"
SOURCE_KEY = "navitime_non_jr"
TIMEOUT = 8
MAX_FETCH_RETRIES = 1
CHECKPOINT_TRAINS_EVERY = 500

JR_OPERATOR_NAMES = {
    "北海道旅客鉄道",
    "東日本旅客鉄道",
    "東海旅客鉄道",
    "西日本旅客鉄道",
    "四国旅客鉄道",
    "九州旅客鉄道",
    "JR Shinkansen",
}

GENERIC_LINE_NAMES = {
    "支線",
    "鋼索線",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    if path.suffix == ".gz":
        with gzip.open(tmp_path, "wt", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    else:
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def cache_path(cache_dir: Path, url: str, suffix: str = ".cache") -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}{suffix}"


def fetch_text(url: str, cache_dir: Path, refresh: bool = False) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(cache_dir, url, ".html")
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8", errors="replace")

    last_error: Exception | None = None
    for attempt in range(1, MAX_FETCH_RETRIES + 1):
        try:
            response = requests.get(
                url,
                timeout=TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (compatible; OniChase-v4-navitime-nonjr/0.1)"},
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
            path.write_text(response.text, encoding="utf-8")
            time.sleep(0.02)
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_FETCH_RETRIES:
                if path.exists():
                    return path.read_text(encoding="utf-8", errors="replace")
                raise
            time.sleep(min(2 * attempt, 8))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def fetch_json(url: str, cache_dir: Path, refresh: bool = False) -> Any:
    path = cache_path(cache_dir, url, ".json")
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    text = fetch_text(url, cache_dir=cache_dir, refresh=refresh)
    data = json.loads(text)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def strip_tags(value: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", value or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_station_name(value: str) -> str:
    text = html.unescape(str(value or "")).strip()
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"〔[^〕]*〕", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"［[^］]*］", "", text)
    text = text.replace("ＪＲ", "").replace("JR", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_station_lookup_key(value: str) -> str:
    return normalize_name(unicodedata.normalize("NFKC", clean_station_name(value)))


def normalize_hhmm(value: str) -> str:
    match = re.search(r"(\d{1,2}:\d{2})", value)
    return match.group(1) if match else ""


def minutes_from_hhmm(value: str | None) -> int | None:
    if value is None:
        return None
    value = str(value)
    if not value or ":" not in value:
        return None
    hour, minute = value.split(":", 1)
    try:
        total = int(hour) * 60 + int(minute)
    except ValueError:
        return None
    return total


def minutes_sort_key(value: str | None) -> int:
    minutes = minutes_from_hhmm(value)
    if minutes is None:
        return 99_999
    if minutes < 3 * 60:
        return minutes + 24 * 60
    return minutes


def hhmm_from_minutes(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def normalize_overnight_stop_times(stop_times: list[dict[str, Any]]) -> None:
    previous = -1
    day_offset = 0
    for stop in stop_times:
        for key in ("arrival_hhmm", "departure_hhmm"):
            raw_minutes = minutes_from_hhmm(stop.get(key))
            if raw_minutes is None:
                continue
            while raw_minutes + day_offset < previous:
                day_offset += 24 * 60
            adjusted = raw_minutes + day_offset
            stop[key] = hhmm_from_minutes(adjusted)
            previous = max(previous, adjusted)


def normalize_stop_url(url: str, service_day: str) -> str:
    year, month, day = service_day.split("-")
    parsed = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["year"] = year
    query["month"] = month
    query["day"] = day
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def safe_key(value: str) -> str:
    key = normalize_name(value)
    return re.sub(r"[^0-9A-Za-z_]+", "_", key).strip("_") or hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]


def train_code_from_stop_url(stop_url: str) -> tuple[str, str]:
    match = re.search(r"/diagram/stops/([^/]+)/([^/?]+)/", stop_url)
    if match:
        return match.group(1), match.group(2)
    return "unknown", hashlib.sha1(stop_url.encode("utf-8")).hexdigest()[:12]


def split_navitime_title(title: str) -> tuple[str, str, str, str]:
    clean = title.replace("の停車駅/時刻表", "").strip()
    match = re.match(r"^(.*?)\((.*?)(\d{1,2}:\d{2})発\s+(.+?行)\)$", clean)
    if not match:
        return clean, "", "", ""
    service_text = match.group(1).strip()
    origin = clean_station_name(match.group(2))
    departure = match.group(3)
    headsign = clean_station_name(match.group(4).replace("行", ""))
    return service_text, origin, departure, headsign


def train_type_from_service_text(service_text: str) -> str:
    for train_type in (
        "特急",
        "急行",
        "快速急行",
        "区間急行",
        "準急",
        "区間準急",
        "快速",
        "普通",
        "各停",
        "ワンマン",
    ):
        if train_type in service_text:
            return train_type
    return ""


def extract_stop_rows_from_navitime_html(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in re.findall(r'<li\s+class="stops-list[^"]*"[^>]*>(.*?)</li>', text, flags=re.S):
        station_match = re.search(r'class="station-name-link"[^>]*>(.*?)</a>', item, flags=re.S)
        time_match = re.search(r'<dd\s+class="(?:time|from-to-time)"[^>]*>(.*?)</dd>', item, flags=re.S)
        if not station_match or not time_match:
            continue
        station_name = clean_station_name(station_match.group(1))
        time_html = time_match.group(1)
        time_text = strip_tags(time_html)
        times = re.findall(r"\d{1,2}:\d{2}", time_text)
        if not station_name or not times:
            continue
        if len(times) >= 2:
            arrival, departure = times[0], times[1]
        else:
            arrival = departure = times[0]
        rows.append(
            {
                "station_name": station_name,
                "arrival_hhmm": arrival,
                "departure_hhmm": departure,
            }
        )
    return rows


def line_name_aliases(line_name: str) -> set[str]:
    """Return normalized label aliases that should identify one physical line."""

    aliases = {line_name}
    # Many official inventories store route numbers plus a public nickname,
    # e.g. 福岡市 1号線(空港線), while timetable pages usually say 空港線.
    for inner in re.findall(r"[（(]([^）)]+)[）)]", line_name):
        if inner:
            aliases.add(inner)
    without_parentheses = re.sub(r"[（(][^）)]+[）)]", "", line_name).strip()
    if without_parentheses:
        aliases.add(without_parentheses)
    return {normalize_line(alias) for alias in aliases if normalize_line(alias)}


def line_text_matches(line_name: str, text: str) -> bool:
    if line_name in GENERIC_LINE_NAMES:
        return True
    text_key = normalize_line(text)
    return any(alias and (alias in text_key or text_key in alias) for alias in line_name_aliases(line_name))


def physical_indexes(physical_map: dict[str, Any]) -> tuple[
    dict[tuple[str, str], list[dict[str, Any]]],
    dict[str, dict[str, Any]],
]:
    by_operator_line: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_id = {station["id"]: station for station in physical_map["physicalStations"]}
    for station in physical_map["physicalStations"]:
        by_operator_line[(station.get("operatorName") or "", station.get("lineName") or "")].append(station)
    return by_operator_line, by_id


def line_inventory_lookup(line_inventory: dict[str, Any]) -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], str]]:
    ids: dict[tuple[str, str], str] = {}
    colors: dict[tuple[str, str], str] = {}
    for line in line_inventory.get("lines", []):
        key = (str(line.get("operatorName") or ""), str(line.get("lineName") or ""))
        ids[key] = str(line.get("id") or f"{key[0]}_{key[1]}")
        colors[key] = str(line.get("lineColor") or line.get("operatorColor") or "#3A6EA5").lstrip("#")
    return ids, colors


def target_lines_from_coverage(
    coverage: dict[str, Any],
    operators: set[str] | None,
    include_partial: bool,
) -> list[tuple[str, list[str]]]:
    output: list[tuple[str, list[str]]] = []
    for operator in coverage.get("operators", []):
        operator_name = str(operator.get("operatorName") or "")
        if not operator_name or operator_name in JR_OPERATOR_NAMES:
            continue
        if operators and operator_name not in operators:
            continue
        lines: list[str] = []
        for line in operator.get("lines", []):
            status = str(line.get("coverageStatus") or "")
            if status.startswith("missing") or (include_partial and status not in {"covered", "complete"}):
                lines.append(str(line.get("lineName") or ""))
        lines = [line for line in lines if line]
        if lines:
            output.append((operator_name, sorted(set(lines))))
    return output


def sampled_station_names(physical_stations: list[dict[str, Any]], sample_size: int) -> list[str]:
    if not physical_stations:
        return []
    if sample_size <= 0 or len(physical_stations) <= sample_size:
        return sorted({station["nameJa"] for station in physical_stations if station.get("nameJa")})
    if sample_size == 1:
        ordered = sorted(
            physical_stations,
            key=lambda station: (float(station.get("lon") or 0), float(station.get("lat") or 0)),
        )
        middle = ordered[len(ordered) // 2]
        return [middle["nameJa"]] if middle.get("nameJa") else []
    lons = [float(station["lon"]) for station in physical_stations if station.get("lon") is not None]
    lats = [float(station["lat"]) for station in physical_stations if station.get("lat") is not None]
    sort_key = "lon"
    if lons and lats and (max(lats) - min(lats)) > (max(lons) - min(lons)):
        sort_key = "lat"
    ordered = sorted(
        physical_stations,
        key=lambda station: (float(station.get(sort_key) or 0), float(station.get("lon" if sort_key == "lat" else "lat") or 0)),
    )
    indexes = {
        round(index * (len(ordered) - 1) / (sample_size - 1))
        for index in range(sample_size)
    }
    names = {ordered[index]["nameJa"] for index in indexes if ordered[index].get("nameJa")}
    return sorted(names)


def discover_navitime_nodes(
    station_names: list[str],
    cache_dir: Path,
    refresh: bool = False,
    station_prefectures: dict[str, set[str]] | None = None,
) -> list[dict[str, str]]:
    nodes: list[dict[str, str]] = []
    seen: set[str] = set()
    allowed_label_suffixes = {"上", "下", "山頂", "山麓", "の", "ノ"}
    for station_name in station_names:
        target_variants = {normalize_station_lookup_key(station_name)}
        target_variants.update(normalize_name_variants(station_name))
        url = f"{AUTOCOMPLETE_URL}?word={urllib.parse.quote(station_name)}"
        try:
            items = fetch_json(url, cache_dir=cache_dir, refresh=refresh)
        except Exception:
            continue
        for item in items[:8]:
            label = clean_station_name(str(item.get("label") or ""))
            raw_label = str(item.get("label") or "")
            label_prefecture_match = re.search(r"[（(]([^）)]+?[都道府県])(?:[^）)]*)[）)]", raw_label)
            target_prefectures = (station_prefectures or {}).get(station_name) or set()
            if label_prefecture_match and target_prefectures:
                if label_prefecture_match.group(1) not in target_prefectures:
                    continue
            label_key = normalize_station_lookup_key(label)
            if label_key not in target_variants and not any(key.startswith(label_key) for key in target_variants if key):
                expanded_match = False
                for key in target_variants:
                    if not key or not label_key.startswith(key):
                        continue
                    suffix = label_key[len(key):]
                    if suffix in allowed_label_suffixes:
                        expanded_match = True
                        break
                if not expanded_match:
                    continue
            node_id = str(item.get("id") or "")
            if not node_id or node_id in seen:
                continue
            seen.add(node_id)
            nodes.append({"stationName": station_name, "nodeId": node_id, "label": str(item.get("label") or station_name)})
    return nodes


def discover_timetable_candidates(node_id: str, cache_dir: Path, service_day: str, refresh: bool = False) -> list[dict[str, str]]:
    text = fetch_text(f"{NAVITIME_BASE}/diagram/lineList?node={node_id}", cache_dir=cache_dir, refresh=refresh)
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r"""<a[^>]+href\s*=\s*["']([^"']+/diagram/timetable\?[^"']+)["'][^>]*>(.*?)</a>""", re.I | re.S)
    for match in pattern.finditer(text):
        url = html.unescape(match.group(1))
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = NAVITIME_BASE + url
        if url in seen:
            continue
        seen.add(url)
        label = strip_tags(match.group(2))
        candidates.append({"timetableUrl": url, "label": label})
    return candidates


def discover_stop_urls(timetable_url: str, cache_dir: Path, service_day: str, refresh: bool = False) -> list[str]:
    text = fetch_text(timetable_url, cache_dir=cache_dir, refresh=refresh)
    urls: list[str] = []
    seen: set[str] = set()
    for href in re.findall(r'href="([^"]*?/diagram/stops/[^"]+)"', text):
        url = html.unescape(href)
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = NAVITIME_BASE + url
        url = normalize_stop_url(url, service_day)
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def context_point_for_stop(stop: dict[str, Any], matcher: V4StationMatcher) -> tuple[float, float] | None:
    group_id = stop.get("station_group_id")
    if not group_id:
        return None
    group = matcher.groups_by_id.get(group_id)
    if not group:
        return None
    centroid = group.get("centroid") or {}
    if "lat" not in centroid or "lon" not in centroid:
        return None
    return float(centroid["lat"]), float(centroid["lon"])


def resolve_contextual_unmatched_stop_times(
    stop_times: list[dict[str, Any]],
    matcher: V4StationMatcher,
    physical_by_id: dict[str, dict[str, Any]],
) -> None:
    for index, stop in enumerate(stop_times):
        if stop.get("station_group_id"):
            continue
        candidates: dict[str, dict[str, Any]] = {}
        for name_key in normalize_name_variants(stop.get("station_name_raw") or ""):
            for station in matcher.physical_by_name.get(name_key, []):
                candidates.setdefault(station["stationGroupId"], station)
        if not candidates:
            continue
        context_points: list[tuple[float, float]] = []
        for prev in reversed(stop_times[:index]):
            point = context_point_for_stop(prev, matcher)
            if point:
                context_points.append(point)
                break
        for nxt in stop_times[index + 1 :]:
            point = context_point_for_stop(nxt, matcher)
            if point:
                context_points.append(point)
                break
        if not context_points:
            continue
        best = min(
            candidates.values(),
            key=lambda station: sum(
                haversine_m(point[0], point[1], float(station["lat"]), float(station["lon"]))
                for point in context_points
            ),
        )
        distance = sum(
            haversine_m(point[0], point[1], float(best["lat"]), float(best["lon"]))
            for point in context_points
        ) / len(context_points)
        stop["station_id"] = best["stationGroupId"]
        stop["station_group_id"] = best["stationGroupId"]
        stop["physical_station_id"] = best["id"]
        stop["match_method"] = "context_nearest_group"
        stop["match_distance_m"] = round(distance, 1)
        apply_physical_stop_metadata(stop, physical_by_id)


def apply_physical_stop_metadata(stop: dict[str, Any], physical_by_id: dict[str, dict[str, Any]]) -> None:
    physical = physical_by_id.get(str(stop.get("physical_station_id") or ""))
    if not physical:
        return
    stop["physical_operator_name"] = physical.get("operatorName")
    stop["physical_line_name"] = physical.get("lineName")


def parse_stop_page(
    stop_url: str,
    *,
    operator_name: str,
    target_line_name: str,
    line_id: str,
    route_color: str,
    known_station_keys: set[str],
    matcher: V4StationMatcher,
    physical_by_id: dict[str, dict[str, Any]],
    service_day: str,
    cache_dir: Path,
    refresh: bool,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    text = fetch_text(stop_url, cache_dir=cache_dir, refresh=refresh)
    clean = re.sub(r"<script.*?</script>", " ", text, flags=re.S)
    clean = re.sub(r"<style.*?</style>", " ", clean, flags=re.S)
    clean = re.sub(r"<[^>]+>", "\n", clean)
    clean = html.unescape(clean)
    lines = [re.sub(r"\s+", " ", line).strip() for line in clean.splitlines()]
    lines = [line for line in lines if line]

    title_raw = next((line for line in lines if "の停車駅/時刻表" in line), "")
    if not title_raw:
        return None, [], "missing_title"
    service_text, origin_name, origin_departure, headsign = split_navitime_title(title_raw)
    train_type = train_type_from_service_text(service_text)
    navitime_line_id, train_code = train_code_from_stop_url(stop_url)

    raw_rows: list[dict[str, str]] = extract_stop_rows_from_navitime_html(text)
    if not raw_rows and origin_name and origin_departure:
        raw_rows.append({"station_name": origin_name, "arrival_hhmm": origin_departure, "departure_hhmm": origin_departure})

    if not raw_rows:
        for index, line in enumerate(lines):
            station_name = clean_station_name(line)
            station_key = normalize_station_lookup_key(station_name)
            if station_key not in known_station_keys:
                continue
            arrival = ""
            departure = ""
            for next_line in lines[index + 1 : index + 7]:
                hhmm = normalize_hhmm(next_line)
                if not hhmm:
                    if len(next_line) <= 5:
                        continue
                    break
                if not arrival:
                    arrival = hhmm
                elif not departure:
                    departure = hhmm
                    break
            if arrival:
                raw_rows.append({"station_name": station_name, "arrival_hhmm": arrival, "departure_hhmm": departure or arrival})

    by_station_time: dict[tuple[str, str], dict[str, str]] = {}
    for row in raw_rows:
        key = (normalize_station_lookup_key(row["station_name"]), row["arrival_hhmm"])
        by_station_time[key] = row
    raw_rows = sorted(
        by_station_time.values(),
        key=lambda row: minutes_sort_key(row.get("arrival_hhmm") or row.get("departure_hhmm")),
    )
    if len(raw_rows) < 2:
        return None, [], "short_raw_stop_list"

    stop_times: list[dict[str, Any]] = []
    visit_counts: Counter[str] = Counter()
    for row in raw_rows:
        stop_name = row["station_name"]
        match = matcher.match(
            operator_name=operator_name,
            line_name=target_line_name,
            stop_name=stop_name,
            stop_lat=None,
            stop_lon=None,
        )
        station_id = match["stationGroupId"] if match["matched"] else f"NAVITIME_UNMATCHED_{normalize_name(stop_name)}"
        visit_counts[station_id] += 1
        stop = {
            "sequence": len(stop_times) + 1,
            "station_name_raw": stop_name,
            "station_id": station_id,
            "station_group_id": match["stationGroupId"],
            "physical_station_id": match["physicalStationId"],
            "line_id": line_id,
            "line_name": target_line_name,
            "arrival_hhmm": row.get("arrival_hhmm"),
            "departure_hhmm": row.get("departure_hhmm"),
            "platform": None,
            "loop_pass_index": visit_counts[station_id],
            "match_method": match["method"],
            "match_distance_m": match["distanceMeters"],
        }
        apply_physical_stop_metadata(stop, physical_by_id)
        stop_times.append(stop)

    if len(stop_times) < 2:
        return None, [], "short_stop_list"
    normalize_overnight_stop_times(stop_times)
    resolve_contextual_unmatched_stop_times(stop_times, matcher, physical_by_id)

    unmatched = [
        {
            "operatorName": operator_name,
            "lineName": target_line_name,
            "sourceUrl": stop_url,
            "trainNumber": train_code,
            "stationNameRaw": stop["station_name_raw"],
            "matchMethod": stop["match_method"],
        }
        for stop in stop_times
        if not stop.get("station_group_id")
    ]
    service_instance_id = f"{SOURCE_KEY}:{safe_key(operator_name)}:{navitime_line_id}:{train_code}:{service_day}"
    train = {
        "train_number": train_code,
        "service_instance_id": service_instance_id,
        "source_trip_id": service_instance_id,
        "operator_id": safe_key(operator_name),
        "operator_name": operator_name,
        "service_name": target_line_name,
        "service_name_detail": service_text,
        "display_name": service_text if service_text and not line_text_matches(target_line_name, service_text) else "",
        "headsign": headsign,
        "train_type": train_type,
        "route_color": route_color,
        "line_id": line_id,
        "line_name": target_line_name,
        "source_feed_key": f"{SOURCE_KEY}_{service_day}",
        "source_url": stop_url,
        "stop_times": stop_times,
    }
    return train, unmatched, None


def target_line_touch_count(train: dict[str, Any], target_station_ids: set[str]) -> int:
    return len({
        stop.get("physical_station_id")
        for stop in train.get("stop_times", [])
        if stop.get("physical_station_id") in target_station_ids
    })


def filter_valid_navitime_trains(
    train_instances: list[dict[str, Any]],
    physical_map: dict[str, Any],
) -> list[dict[str, Any]]:
    station_ids_by_operator_line: dict[tuple[str, str], set[str]] = defaultdict(set)
    for station in physical_map.get("physicalStations", []):
        station_ids_by_operator_line[
            (str(station.get("operatorName") or ""), str(station.get("lineName") or ""))
        ].add(str(station.get("id") or ""))

    output: list[dict[str, Any]] = []
    for train in train_instances:
        operator_name = str(train.get("operator_name") or "")
        candidate_lines = list(train.get("service_line_names") or [])
        if train.get("line_name") and train["line_name"] not in candidate_lines:
            candidate_lines.append(str(train["line_name"]))
        touched: list[str] = []
        touch_counts: dict[str, int] = {}
        for line_name in candidate_lines:
            target_ids = station_ids_by_operator_line.get((operator_name, line_name), set())
            if not target_ids:
                continue
            required = min(2, max(1, len(target_ids)))
            count = target_line_touch_count(train, target_ids)
            touch_counts[line_name] = count
            if count >= required:
                touched.append(line_name)
        if not touched:
            continue
        primary = max(touched, key=lambda line: (touch_counts[line], -candidate_lines.index(line)))
        train = dict(train)
        train["line_name"] = primary
        train["service_name"] = primary
        train["service_line_names"] = sorted(touched)
        train["service_line_touch_counts"] = touch_counts
        output.append(train)
    return output


def enrich_train_line_membership(
    train: dict[str, Any],
    operator_name: str,
    line_names: list[str],
    target_station_ids_by_line: dict[str, set[str]],
    line_ids: dict[tuple[str, str], str],
    line_colors: dict[tuple[str, str], str],
) -> None:
    counts = {
        line_name: target_line_touch_count(train, target_station_ids_by_line[line_name])
        for line_name in line_names
    }
    touched = [line for line, count in counts.items() if count > 0]
    if touched:
        primary = max(touched, key=lambda line: (counts[line], -line_names.index(line)))
        train["line_name"] = primary
        train["line_id"] = line_ids.get((operator_name, primary), train.get("line_id") or primary)
        train["route_color"] = line_colors.get((operator_name, primary), train.get("route_color") or "3A6EA5")
        train["service_name"] = primary
        train["service_line_names"] = sorted(touched)
        train["service_line_touch_counts"] = counts


def bad_time_order_count(train: dict[str, Any]) -> int:
    previous = -1
    bad = 0
    for stop in train.get("stop_times") or []:
        current = minutes_from_hhmm(stop.get("departure_hhmm") or stop.get("arrival_hhmm"))
        if current is None:
            continue
        if current < previous:
            bad += 1
        previous = max(previous, current)
    return bad


def write_outputs(
    *,
    output_path: Path,
    audit_path: Path,
    physical_map: dict[str, Any],
    service_day: str,
    train_instances: list[dict[str, Any]],
    operator_audits: list[dict[str, Any]],
    line_audits: list[dict[str, Any]],
    unmatched: list[dict[str, Any]],
    partial: bool,
) -> None:
    valid_train_instances = filter_valid_navitime_trains(train_instances, physical_map)
    trains = sorted(
        valid_train_instances,
        key=lambda train: (
            train.get("operator_name") or "",
            train.get("line_name") or "",
            train["stop_times"][0].get("departure_hhmm") or "",
            train.get("service_instance_id") or "",
        ),
    )
    duplicate_ids = [
        key for key, count in Counter(train["service_instance_id"] for train in trains).items()
        if count > 1
    ]
    audit = {
        "schema": "onichase.v4.navitime_non_jr_train_instances_audit.v1",
        "generatedAt": now_iso(),
        "partial": partial,
        "serviceDay": service_day,
        "operatorCount": len(operator_audits),
        "lineCount": len(line_audits),
        "trainInstanceCount": len(trains),
        "stopTimeCount": sum(len(train.get("stop_times") or []) for train in trains),
        "duplicateServiceInstanceIdCount": len(duplicate_ids),
        "duplicateServiceInstanceIdsSample": duplicate_ids[:20],
        "shortTrainInstanceCount": sum(1 for train in trains if len(train.get("stop_times") or []) < 2),
        "badTimeOrderCount": sum(bad_time_order_count(train) for train in trains),
        "unmatchedStopCount": len(unmatched),
        "operatorAudits": operator_audits,
        "lineAudits": line_audits,
        "unmatchedStops": unmatched[:1000],
    }
    output = {
        "id": "v4_navitime_non_jr_weekday_train_instances_v0_1",
        "label": "V4 non-JR weekday train instances collected from Navitime stop-chain pages",
        "version": "0.1.0",
        "partial": partial,
        "service_day": service_day,
        "source": "https://www.navitime.co.jp/diagram/",
        "station_identity": physical_map.get("identityVersion"),
        "train_instances": trains,
    }
    write_json(output_path, output)
    write_json(audit_path, audit)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--line-inventory", type=Path, default=DEFAULT_LINE_INVENTORY)
    parser.add_argument("--coverage-audit", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--service-date", default=DEFAULT_SERVICE_DATE)
    parser.add_argument("--operator", action="append", help="Collect only this operator. Can be repeated.")
    parser.add_argument("--line", action="append", help="Collect only this line name within selected operators. Can be repeated.")
    parser.add_argument("--max-operators", type=int, default=0)
    parser.add_argument("--max-lines", type=int, default=0)
    parser.add_argument("--max-stations-per-line", type=int, default=0)
    parser.add_argument(
        "--station-sample-size",
        type=int,
        default=18,
        help="Evenly sample this many physical stations per line for Navitime discovery; 0 means all.",
    )
    parser.add_argument("--max-train-groups-per-line", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--include-partial", action="store_true")
    parser.add_argument("--no-label-filter", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    physical_map = load_json(args.physical_map)
    line_inventory = load_json(args.line_inventory)
    coverage = load_json(args.coverage_audit)
    matcher = V4StationMatcher(physical_map)
    by_operator_line, physical_by_id = physical_indexes(physical_map)
    line_ids, line_colors = line_inventory_lookup(line_inventory)
    requested_operators = set(args.operator or []) or None
    requested_lines = set(args.line or [])
    operator_targets = target_lines_from_coverage(coverage, requested_operators, include_partial=args.include_partial)
    if args.max_operators:
        operator_targets = operator_targets[: args.max_operators]

    known_station_keys = {
        normalize_station_lookup_key(station["nameJa"])
        for station in physical_map["physicalStations"]
    }

    if args.output.exists() and os.environ.get("REBUILD") != "1":
        existing = load_json(args.output)
        train_instances, instance_index = index_train_instances(existing.get("train_instances", []))
    else:
        train_instances = []
        instance_index = {}

    operator_audits: list[dict[str, Any]] = []
    line_audits: list[dict[str, Any]] = []
    all_unmatched: list[dict[str, Any]] = []
    seen_source_urls = {train.get("source_url") for train in train_instances if train.get("source_url")}
    next_train_checkpoint = ((len(train_instances) // CHECKPOINT_TRAINS_EVERY) + 1) * CHECKPOINT_TRAINS_EVERY

    for operator_index, (operator_name, line_names) in enumerate(operator_targets, start=1):
        if requested_lines:
            line_names = [line for line in line_names if line in requested_lines]
        if args.max_lines:
            line_names = line_names[: args.max_lines]
        if not line_names:
            continue
        operator_train_before = len(train_instances)
        operator_line_audits: list[dict[str, Any]] = []
        target_station_ids_by_line = {
            line_name: {station["id"] for station in by_operator_line.get((operator_name, line_name), [])}
            for line_name in line_names
        }
        print(f"[operator {operator_index}/{len(operator_targets)}] {operator_name}: {len(line_names)} lines", flush=True)

        for line_index, line_name in enumerate(line_names, start=1):
            physical_stations = by_operator_line.get((operator_name, line_name), [])
            station_names = sampled_station_names(physical_stations, args.station_sample_size)
            if args.max_stations_per_line:
                station_names = station_names[: args.max_stations_per_line]
            station_prefectures: dict[str, set[str]] = defaultdict(set)
            for station in physical_stations:
                if station.get("nameJa") in station_names and station.get("prefectureNameJa"):
                    station_prefectures[str(station["nameJa"])].add(str(station["prefectureNameJa"]))
            line_id = line_ids.get((operator_name, line_name), f"{safe_key(operator_name)}_{safe_key(line_name)}")
            route_color = line_colors.get((operator_name, line_name), "3A6EA5")
            required_touch_count = min(2, max(1, len(physical_stations)))
            print(f"  [{line_index}/{len(line_names)}] {line_name}: seed_stations={len(station_names)}", flush=True)

            nodes = discover_navitime_nodes(
                station_names,
                cache_dir=args.cache_dir,
                refresh=args.refresh,
                station_prefectures=station_prefectures,
            )
            timetable_candidates: dict[str, dict[str, str]] = {}
            node_errors = 0
            for node in nodes:
                try:
                    for candidate in discover_timetable_candidates(
                        node["nodeId"],
                        cache_dir=args.cache_dir,
                        service_day=args.service_date,
                        refresh=args.refresh,
                    ):
                        # For specific line names this cheap label filter avoids
                        # parsing obvious transfers. Generic names are validated
                        # later by physical-line touch count instead.
                        if not args.no_label_filter and line_name not in GENERIC_LINE_NAMES and candidate["label"]:
                            if not line_text_matches(line_name, candidate["label"]):
                                # Keep ambiguous empty labels, reject clear misses.
                                continue
                        timetable_candidates.setdefault(candidate["timetableUrl"], {**candidate, "sourceNodeId": node["nodeId"], "sourceStationName": node["stationName"]})
                except Exception as exc:
                    node_errors += 1
                    print(f"    node error {node['stationName']} {type(exc).__name__}: {exc}", flush=True)

            stop_url_candidates_by_key: dict[tuple[str, str], list[str]] = defaultdict(list)
            timetable_errors = 0
            raw_stop_url_count = 0
            for candidate in timetable_candidates.values():
                try:
                    for stop_url in discover_stop_urls(
                        candidate["timetableUrl"],
                        cache_dir=args.cache_dir,
                        service_day=args.service_date,
                        refresh=args.refresh,
                    ):
                        raw_stop_url_count += 1
                        stop_url_candidates_by_key[train_code_from_stop_url(stop_url)].append(stop_url)
                except Exception as exc:
                    timetable_errors += 1
                    print(f"    timetable error {type(exc).__name__}: {exc}", flush=True)

            train_groups = sorted(stop_url_candidates_by_key.items())
            if args.max_train_groups_per_line:
                train_groups = train_groups[: args.max_train_groups_per_line]

            line_train_before = len(train_instances)
            line_unmatched: list[dict[str, Any]] = []
            stop_page_errors: Counter[str] = Counter()
            parsed_pages = 0
            accepted_pages = 0
            skipped_seen = 0
            def parse_group(group_index: int, stop_urls: list[str], seen_snapshot: set[str]) -> dict[str, Any]:
                parsed = None
                unmatched: list[dict[str, Any]] = []
                skip_reason = None
                errors: Counter[str] = Counter()
                local_seen: set[str] = set()
                local_skipped_seen = 0
                local_parsed_pages = 0
                for stop_url in sorted(set(stop_urls)):
                    if stop_url in seen_snapshot:
                        local_skipped_seen += 1
                        continue
                    try:
                        parsed, unmatched, skip_reason = parse_stop_page(
                            stop_url,
                            operator_name=operator_name,
                            target_line_name=line_name,
                            line_id=line_id,
                            route_color=route_color,
                            known_station_keys=known_station_keys,
                            matcher=matcher,
                            physical_by_id=physical_by_id,
                            service_day=args.service_date,
                            cache_dir=args.cache_dir,
                            refresh=args.refresh,
                        )
                    except Exception as exc:
                        local_seen.add(stop_url)
                        errors[f"{type(exc).__name__}: {exc}"] += 1
                        continue
                    local_seen.add(stop_url)
                    local_parsed_pages += 1
                    if not parsed:
                        errors[skip_reason or "unparsed"] += 1
                        continue
                    touch_count = target_line_touch_count(parsed, target_station_ids_by_line[line_name])
                    if touch_count < required_touch_count:
                        errors[f"off_target_line_touch_{touch_count}"] += 1
                        parsed = None
                        continue
                    break
                return {
                    "groupIndex": group_index,
                    "parsed": parsed,
                    "unmatched": unmatched,
                    "errors": errors,
                    "seen": local_seen,
                    "skippedSeen": local_skipped_seen,
                    "parsedPages": local_parsed_pages,
                }

            seen_snapshot = set(seen_source_urls)
            next_train_checkpoint_local = next_train_checkpoint
            completed_groups = 0
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
                futures = [
                    executor.submit(parse_group, group_index, stop_urls, seen_snapshot)
                    for group_index, ((_navitime_line_id, _train_code), stop_urls) in enumerate(train_groups, start=1)
                ]
                for future in as_completed(futures):
                    result = future.result()
                    completed_groups += 1
                    seen_source_urls.update(result["seen"])
                    skipped_seen += result["skippedSeen"]
                    parsed_pages += result["parsedPages"]
                    stop_page_errors.update(result["errors"])
                    parsed = result["parsed"]
                    if not parsed:
                        if completed_groups % 100 == 0:
                            print(f"    progress groups={completed_groups}/{len(train_groups)} accepted={accepted_pages}", flush=True)
                        continue
                    enrich_train_line_membership(
                        parsed,
                        operator_name=operator_name,
                        line_names=line_names,
                        target_station_ids_by_line=target_station_ids_by_line,
                        line_ids=line_ids,
                        line_colors=line_colors,
                    )
                    line_unmatched.extend(result["unmatched"])
                    action = upsert_train_instance(train_instances, instance_index, parsed)
                    if action in {"added", "updated"}:
                        accepted_pages += 1
                    if len(train_instances) >= next_train_checkpoint_local:
                        write_outputs(
                            output_path=args.output,
                            audit_path=args.audit_output,
                            physical_map=physical_map,
                            service_day=args.service_date,
                            train_instances=train_instances,
                            operator_audits=operator_audits,
                            line_audits=line_audits,
                            unmatched=all_unmatched + line_unmatched,
                            partial=True,
                        )
                        print(
                            f"    checkpoint trains={len(train_instances)} "
                            f"groups={completed_groups}/{len(train_groups)}",
                            flush=True,
                        )
                        next_train_checkpoint_local += CHECKPOINT_TRAINS_EVERY
                    if completed_groups % 100 == 0:
                        print(f"    progress groups={completed_groups}/{len(train_groups)} accepted={accepted_pages}", flush=True)
            next_train_checkpoint = next_train_checkpoint_local

            all_unmatched.extend(line_unmatched)
            line_trains = [
                train for train in train_instances
                if train.get("operator_name") == operator_name
                and (
                    train.get("line_name") == line_name
                    or line_name in (train.get("service_line_names") or [])
                )
            ]
            audit = {
                "operatorName": operator_name,
                "lineName": line_name,
                "physicalStationCount": len(physical_stations),
                "seedStationCount": len(station_names),
                "navitimeNodeCount": len(nodes),
                "nodeErrorCount": node_errors,
                "timetablePageCount": len(timetable_candidates),
                "timetableErrorCount": timetable_errors,
                "rawStopPageLinkCount": raw_stop_url_count,
                "trainGroupCount": len(train_groups),
                "parsedStopPageCount": parsed_pages,
                "acceptedStopPageCount": accepted_pages,
                "skippedSeenStopPageCount": skipped_seen,
                "newTrainInstanceCount": len(train_instances) - line_train_before,
                "lineTrainInstanceCount": len(line_trains),
                "unmatchedStopCount": len(line_unmatched),
                "badTimeOrderCount": sum(bad_time_order_count(train) for train in line_trains),
                "stopPageErrors": dict(stop_page_errors.most_common(20)),
                "sampleTimetablePages": list(timetable_candidates.values())[:10],
                "unmatchedStopsSample": line_unmatched[:20],
            }
            line_audits.append(audit)
            operator_line_audits.append(audit)
            print(
                f"    {line_name}: nodes={len(nodes)} timetables={len(timetable_candidates)} "
                f"groups={len(train_groups)} accepted={accepted_pages} line_trains={len(line_trains)} "
                f"unmatched={len(line_unmatched)}",
                flush=True,
            )
            write_outputs(
                output_path=args.output,
                audit_path=args.audit_output,
                physical_map=physical_map,
                service_day=args.service_date,
                train_instances=train_instances,
                operator_audits=operator_audits,
                line_audits=line_audits,
                unmatched=all_unmatched,
                partial=True,
            )

        operator_audits.append(
            {
                "operatorName": operator_name,
                "targetLineCount": len(line_names),
                "newTrainInstanceCount": len(train_instances) - operator_train_before,
                "operatorTrainInstanceCount": sum(1 for train in train_instances if train.get("operator_name") == operator_name),
                "lineAudits": operator_line_audits,
            }
        )

    write_outputs(
        output_path=args.output,
        audit_path=args.audit_output,
        physical_map=physical_map,
        service_day=args.service_date,
        train_instances=train_instances,
        operator_audits=operator_audits,
        line_audits=line_audits,
        unmatched=all_unmatched,
        partial=False,
    )
    final_audit = load_json(args.audit_output)
    print(f"Wrote {args.output}: {final_audit['trainInstanceCount']} trains")
    print(f"Wrote {args.audit_output}: unmatched={final_audit['unmatchedStopCount']} bad_time_order={final_audit['badTimeOrderCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
