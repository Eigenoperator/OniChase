#!/usr/bin/env python3
"""Collect JR Central conventional-line train instances from Navitime stop pages.

JR Central's official conventional-line timetable pages expose station-level
PDFs, which are useful for auditing departures but do not directly provide full
stop lists per train.  Navitime's train stop pages do expose the stop chain, so
this collector uses the v4 physical map as the line/station seed, collects full
weekday stop lists, and writes v4 station_identity_v2-aligned train instances.
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
import urllib.parse
from collections import Counter, defaultdict
from copy import deepcopy
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
DEFAULT_LINE_INVENTORY = ROOT / "docs" / "data" / "v4_maplibre" / "line_inventory.json"
DEFAULT_COVERAGE = ROOT / "data" / "v4_jr_company_timetable_coverage_audit.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_jrcentral_navitime_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_jrcentral_navitime_train_instances_audit.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_jrcentral_navitime_cache"

AUTOCOMPLETE_URL = "https://media.cld.navitime.jp/media/biz/widget/diagram/search/train/autocomplete"
NAVITIME_BASE = "https://www.navitime.co.jp"
JRC_LINE_STATION_URL = "https://railway.jr-central.co.jp/common/_api/time-schedule/list_line_station.json"
OPERATOR_ID = "jr_central"
OPERATOR_NAME = "東海旅客鉄道"
SERVICE_DAY = "2026-04-27"
TIMEOUT = 15
MAX_FETCH_RETRIES = 3
CHECKPOINT_TRAINS_EVERY = 250

ROUTE_COLOR = "F77321"
SOURCE_KEY = "jr_central_navitime"
AUDIT_SCHEMA = "onichase.v4.jrcentral_navitime_train_instances_audit.v1"
COLLECTION_ID = "v4_jrcentral_navitime_weekday_train_instances_v0_1"
COLLECTION_LABEL = "V4 JR Central weekday train instances collected from Navitime stop pages"

LINE_ALIASES = {
    "中央線": ["中央線", "中央本線", "ＪＲ中央本線", "JR中央本線"],
    "関西線": ["関西線", "関西本線", "ＪＲ関西本線", "JR関西本線"],
    "紀勢線": ["紀勢線", "紀勢本線", "ＪＲ紀勢本線", "JR紀勢本線"],
    "高山線": ["高山線", "高山本線", "ＪＲ高山本線", "JR高山本線"],
    "東海道線": ["東海道線", "東海道本線", "ＪＲ東海道本線", "JR東海道本線"],
    "御殿場線": ["御殿場線"],
    "身延線": ["身延線"],
    "参宮線": ["参宮線"],
    "太多線": ["太多線"],
    "飯田線": ["飯田線"],
    "武豊線": ["武豊線"],
    "名松線": ["名松線"],
}

LINE_WORD_RE = re.compile(r"(ＪＲ|JR)?[一-龥ぁ-んァ-ヶー・]+(?:本線|線)")
TAG_RE = re.compile(r"<[^>]+>")


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path(cache_dir: Path, url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.cache"


def fetch_text(url: str, cache_dir: Path, refresh: bool = False) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(cache_dir, url)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8", errors="replace")

    last_error: Exception | None = None
    for attempt in range(1, MAX_FETCH_RETRIES + 1):
        try:
            response = requests.get(
                url,
                timeout=TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (OniChase-v4 JR Central collector)"},
            )
            if response.status_code in {400, 404, 410}:
                response.raise_for_status()
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
            text = response.text
            path.write_text(text, encoding="utf-8")
            time.sleep(0.03)
            return text
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code in {400, 404, 410}:
                raise
            last_error = exc
            if attempt == MAX_FETCH_RETRIES:
                if path.exists():
                    return path.read_text(encoding="utf-8", errors="replace")
                raise
            time.sleep(min(2 * attempt, 12))
        except requests.Timeout:
            raise
        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_FETCH_RETRIES:
                if path.exists():
                    return path.read_text(encoding="utf-8", errors="replace")
                raise
            time.sleep(min(2 * attempt, 12))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def fetch_json(url: str, cache_dir: Path, refresh: bool = False) -> Any:
    text = fetch_text(url, cache_dir=cache_dir, refresh=refresh)
    return json.loads(text)


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", value))).strip()


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
    return normalize_name(clean_station_name(value))


def clean_line_text(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = text.replace("ＪＲ", "").replace("JR", "")
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = text.replace("本線", "線")
    text = text.replace(" ", "").replace("　", "")
    return text


def line_matches_text(line_name: str, text: str) -> bool:
    clean_text = clean_line_text(text)
    aliases = LINE_ALIASES.get(line_name, [line_name])
    for alias in aliases:
        clean_alias = clean_line_text(alias)
        if not clean_alias:
            continue
        if clean_alias in clean_text:
            return True
    return False


def normalize_stop_url(url: str, service_day: str) -> str:
    year, month, day = service_day.split("-")
    parsed = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["year"] = year
    query["month"] = month
    query["day"] = day
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def line_id_lookup(line_inventory: dict[str, Any]) -> dict[tuple[str, str], str]:
    return {
        (line["operatorName"], line["lineName"]): line["id"]
        for line in line_inventory["lines"]
    }


def load_jrcentral_station_orders(cache_dir: Path, refresh: bool = False) -> dict[str, dict[str, int]]:
    try:
        data = fetch_json(JRC_LINE_STATION_URL, cache_dir=cache_dir, refresh=refresh)
    except Exception:
        return {}
    orders: dict[str, dict[str, int]] = {}
    for line in data.get("line_list", []):
        line_name = line.get("line_name")
        if not line_name:
            continue
        order_by_station: dict[str, int] = {}
        for station in line.get("station", []):
            try:
                order = int(station.get("sort") or 0)
            except ValueError:
                order = 0
            if not order:
                continue
            order_by_station[normalize_station_lookup_key(station.get("name") or "")] = order
        orders[line_name] = order_by_station
    return orders


def physical_station_names_by_line(physical_map: dict[str, Any]) -> dict[str, list[str]]:
    names: dict[str, set[str]] = defaultdict(set)
    for station in physical_map["physicalStations"]:
        if station.get("operatorName") != OPERATOR_NAME:
            continue
        names[station["lineName"]].add(station["nameJa"])
    return {line_name: sorted(station_names) for line_name, station_names in names.items()}


def missing_jrcentral_lines(coverage_audit: dict[str, Any]) -> list[str]:
    for company in coverage_audit["companies"]:
        if company["operatorId"] == OPERATOR_ID:
            return [
                line["lineName"]
                for line in company["lines"]
                if line["coverageStatus"] != "covered"
                and line["lineName"] != "東海道新幹線"
            ]
    return []


def discover_navitime_nodes(station_names: list[str], cache_dir: Path, refresh: bool = False) -> list[dict[str, str]]:
    nodes: list[dict[str, str]] = []
    seen_nodes: set[str] = set()
    for station_name in station_names:
        target_variants = {normalize_station_lookup_key(station_name)}
        for variant in normalize_name_variants(station_name):
            target_variants.add(variant)
        url = f"{AUTOCOMPLETE_URL}?word={urllib.parse.quote(station_name)}"
        try:
            items = fetch_json(url, cache_dir=cache_dir, refresh=refresh)
        except Exception:
            continue
        for item in items:
            label = clean_station_name(item.get("label", ""))
            label_key = normalize_station_lookup_key(label)
            if label_key not in target_variants and not any(
                label_key.startswith(key) or key.startswith(label_key)
                for key in target_variants
                if key
            ):
                continue
            node_id = str(item.get("id") or "")
            if not node_id or node_id in seen_nodes:
                continue
            seen_nodes.add(node_id)
            nodes.append(
                {
                    "stationName": station_name,
                    "nodeId": node_id,
                    "label": str(item.get("label") or station_name),
                }
            )
    return nodes


def discover_timetable_urls(node_id: str, cache_dir: Path, refresh: bool = False) -> list[str]:
    text = fetch_text(f"{NAVITIME_BASE}/diagram/lineList?node={node_id}", cache_dir=cache_dir, refresh=refresh)
    urls: list[str] = []
    seen: set[str] = set()
    for href in re.findall(r'href="([^"]+/diagram/timetable\?[^"]+)"', text):
        url = href
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = NAVITIME_BASE + url
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def timetable_page_matches_line(html_text: str, line_name: str) -> tuple[bool, str]:
    title_match = re.search(r"<title>(.*?)</title>", html_text, re.DOTALL)
    title = strip_tags(title_match.group(1)) if title_match else ""
    if line_matches_text(line_name, title):
        return True, title
    return line_matches_text(line_name, html_text[:20_000]), title


def discover_stop_urls(timetable_url: str, cache_dir: Path, service_day: str, refresh: bool = False) -> list[str]:
    text = fetch_text(timetable_url, cache_dir=cache_dir, refresh=refresh)
    urls: list[str] = []
    seen: set[str] = set()
    for href in re.findall(r'href="([^"]*?/diagram/stops/[^"]+)"', text):
        url = href
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


def normalize_hhmm(value: str) -> str:
    match = re.search(r"(\d{1,2}:\d{2})", value)
    return match.group(1) if match else ""


def minutes_from_hhmm(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    hour, minute = value.split(":", 1)
    try:
        total = int(hour) * 60 + int(minute)
    except ValueError:
        return None
    return total


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


def minutes_sort_key(value: str | None) -> int:
    minutes = minutes_from_hhmm(value)
    if minutes is None:
        return 99_999
    if minutes < 3 * 60:
        return minutes + 24 * 60
    return minutes


def train_code_from_stop_url(stop_url: str) -> tuple[str, str]:
    match = re.search(r"/diagram/stops/([^/]+)/([^/?]+)/", stop_url)
    if match:
        return match.group(1), match.group(2)
    return "unknown", hashlib.sha1(stop_url.encode("utf-8")).hexdigest()[:12]


def updown_from_timetable_url(timetable_url: str) -> str:
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(timetable_url).query))
    return str(query.get("updown") or "")


def candidate_origin_sort_key(candidate: dict[str, Any]) -> tuple[int, str]:
    order = int(candidate.get("sourceStationOrder") or 999_999)
    updown = candidate.get("updown")
    if updown == "0":
        order = -order
    return order, str(candidate.get("sourceNodeId") or "")


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
    for train_type in ("特急", "ホームライナー", "区間快速", "快速", "普通", "ワンマン"):
        if train_type in service_text:
            return train_type
    return ""


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


def resolve_contextual_unmatched_stop_times(stop_times: list[dict[str, Any]], matcher: V4StationMatcher) -> None:
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


def parse_stop_page(
    stop_url: str,
    *,
    target_line_name: str,
    line_id: str,
    known_station_keys: set[str],
    matcher: V4StationMatcher,
    service_day: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    text = fetch_text(stop_url, cache_dir=parse_stop_page.cache_dir, refresh=parse_stop_page.refresh)
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

    raw_rows: list[dict[str, str]] = []
    if origin_name and origin_departure:
        raw_rows.append({"station_name": origin_name, "arrival_hhmm": origin_departure, "departure_hhmm": origin_departure})

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
                # Navitime often inserts platform or labels between arrival and
                # departure; keep scanning a few short non-time tokens.
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

    # Deduplicate stations that were found both in the title and in the list.
    by_station_time: dict[tuple[str, str], dict[str, str]] = {}
    for row in raw_rows:
        key = (normalize_station_lookup_key(row["station_name"]), row["arrival_hhmm"])
        by_station_time[key] = row
    raw_rows = sorted(
        by_station_time.values(),
        key=lambda row: minutes_sort_key(row.get("arrival_hhmm") or row.get("departure_hhmm")),
    )

    stop_times: list[dict[str, Any]] = []
    visit_counts: Counter[str] = Counter()
    for row in raw_rows:
        stop_name = row["station_name"]
        match = matcher.match(
            operator_name=OPERATOR_NAME,
            line_name=target_line_name,
            stop_name=stop_name,
            stop_lat=None,
            stop_lon=None,
        )
        station_id = match["stationGroupId"] if match["matched"] else f"JRCENTRAL_UNMATCHED_{normalize_name(stop_name)}"
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
        stop_times.append(stop)

    if len(stop_times) < 2:
        return None, [], "short_stop_list"
    normalize_overnight_stop_times(stop_times)
    resolve_contextual_unmatched_stop_times(stop_times, matcher)
    unmatched = [
        {
            "lineName": target_line_name,
            "sourceUrl": stop_url,
            "trainNumber": train_code,
            "stationNameRaw": stop["station_name_raw"],
            "matchMethod": stop["match_method"],
            "candidateCount": None,
        }
        for stop in stop_times
        if not stop.get("station_group_id")
    ]
    service_instance_id = f"{SOURCE_KEY}:{normalize_line(target_line_name)}:{navitime_line_id}:{train_code}:{service_day}"
    train = {
        "train_number": train_code,
        "service_instance_id": service_instance_id,
        "source_trip_id": service_instance_id,
        "operator_id": OPERATOR_ID,
        "operator_name": OPERATOR_NAME,
        "service_name": target_line_name,
        "service_name_detail": service_text,
        "display_name": service_text if not line_matches_text(target_line_name, service_text) else "",
        "headsign": headsign,
        "train_type": train_type,
        "route_color": ROUTE_COLOR,
        "line_id": line_id,
        "line_name": target_line_name,
        "source_feed_key": f"{SOURCE_KEY}_{service_day}",
        "source_url": stop_url,
        "stop_times": stop_times,
    }
    return train, unmatched, None


# Mutable knobs for the parser without threading cache args through every
# low-level call. This script is single-process and non-parallel.
parse_stop_page.cache_dir = DEFAULT_CACHE_DIR  # type: ignore[attr-defined]
parse_stop_page.refresh = False  # type: ignore[attr-defined]


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


def write_collection_outputs(
    *,
    output_path: Path,
    audit_path: Path,
    physical_map: dict[str, Any],
    target_lines: list[str],
    train_instances: list[dict[str, Any]],
    line_audits: list[dict[str, Any]],
    unmatched: list[dict[str, Any]],
    partial: bool,
    source_reports: list[dict[str, Any]],
) -> None:
    trains = sorted(
        train_instances,
        key=lambda train: (
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
        "schema": AUDIT_SCHEMA,
        "partial": partial,
        "serviceDay": SERVICE_DAY,
        "targetLineCount": len(target_lines),
        "completedLineCount": len(line_audits),
        "targetLines": target_lines,
        "trainInstanceCount": len(trains),
        "stopTimeCount": sum(len(train["stop_times"]) for train in trains),
        "duplicateServiceInstanceIdCount": len(duplicate_ids),
        "shortTrainInstanceCount": sum(1 for train in trains if len(train.get("stop_times") or []) < 2),
        "badTimeOrderCount": sum(bad_time_order_count(train) for train in trains),
        "unmatchedStopCount": len(unmatched),
        "lineAudits": line_audits,
        "sourceReports": source_reports[-1000:],
        "unmatchedStops": unmatched[:1000],
    }
    output = {
        "id": COLLECTION_ID,
        "label": COLLECTION_LABEL,
        "version": "0.1.0",
        "partial": partial,
        "service_day": SERVICE_DAY,
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
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--line", action="append", help="Collect only this JR Central physical line. Can be repeated.")
    parser.add_argument("--max-lines", type=int, default=0, help="Debug limit; 0 means all selected lines.")
    parser.add_argument("--max-stations-per-line", type=int, default=0, help="Debug limit; 0 means all stations.")
    parser.add_argument("--max-stop-pages-per-line", type=int, default=0, help="Debug limit; 0 means all stop pages.")
    parser.add_argument("--refresh", action="store_true", help="Refetch Navitime pages instead of using local cache.")
    args = parser.parse_args()

    parse_stop_page.cache_dir = args.cache_dir  # type: ignore[attr-defined]
    parse_stop_page.refresh = args.refresh  # type: ignore[attr-defined]

    physical_map = load_json(args.physical_map)
    line_inventory = load_json(args.line_inventory)
    coverage_audit = load_json(args.coverage_audit)
    matcher = V4StationMatcher(physical_map)
    line_ids = line_id_lookup(line_inventory)
    station_names_by_line = physical_station_names_by_line(physical_map)
    station_orders_by_line = load_jrcentral_station_orders(args.cache_dir, refresh=args.refresh)
    target_lines = args.line or missing_jrcentral_lines(coverage_audit)
    if args.max_lines:
        target_lines = target_lines[: args.max_lines]

    # Use every v4 physical station as a parser vocabulary, not only JR Central
    # stations, so through services can keep their cross-company tail stops.
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

    source_reports: list[dict[str, Any]] = []
    line_audits: list[dict[str, Any]] = []
    all_unmatched: list[dict[str, Any]] = []
    seen_source_urls = {train.get("source_url") for train in train_instances if train.get("source_url")}
    next_train_checkpoint = ((len(train_instances) // CHECKPOINT_TRAINS_EVERY) + 1) * CHECKPOINT_TRAINS_EVERY

    for line_index, line_name in enumerate(target_lines, start=1):
        line_id = line_ids.get((OPERATOR_NAME, line_name), f"JR_CENTRAL_{normalize_line(line_name)}")
        station_names = station_names_by_line.get(line_name, [])
        if args.max_stations_per_line:
            station_names = station_names[: args.max_stations_per_line]
        print(f"[{line_index}/{len(target_lines)}] {line_name}: discover {len(station_names)} stations", flush=True)

        nodes = discover_navitime_nodes(station_names, cache_dir=args.cache_dir, refresh=args.refresh)
        station_order = station_orders_by_line.get(line_name, {})
        timetable_candidates: dict[str, dict[str, Any]] = {}
        node_errors = 0
        for node in nodes:
            try:
                for timetable_url in discover_timetable_urls(node["nodeId"], cache_dir=args.cache_dir, refresh=args.refresh):
                    page_html = fetch_text(timetable_url, cache_dir=args.cache_dir, refresh=args.refresh)
                    matched, title = timetable_page_matches_line(page_html, line_name)
                    if not matched:
                        continue
                    timetable_candidates.setdefault(
                        timetable_url,
                        {
                            "timetableUrl": timetable_url,
                            "sourceStationName": node["stationName"],
                            "sourceStationOrder": station_order.get(normalize_station_lookup_key(node["stationName"]), 999_999),
                            "sourceNodeId": node["nodeId"],
                            "updown": updown_from_timetable_url(timetable_url),
                            "title": title,
                        },
                    )
            except Exception as exc:
                node_errors += 1
                source_reports.append(
                    {
                        "lineName": line_name,
                        "stationName": node["stationName"],
                        "nodeId": node["nodeId"],
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        stop_url_candidates_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        raw_stop_url_count = 0
        timetable_errors = 0
        for candidate in timetable_candidates.values():
            try:
                for stop_url in discover_stop_urls(
                    candidate["timetableUrl"],
                    cache_dir=args.cache_dir,
                    service_day=SERVICE_DAY,
                    refresh=args.refresh,
                ):
                    raw_stop_url_count += 1
                    navitime_line_id, train_code = train_code_from_stop_url(stop_url)
                    stop_url_candidates_by_key[(navitime_line_id, train_code)].append(
                        {
                            "stopUrl": stop_url,
                            "candidate": candidate,
                        }
                    )
            except Exception as exc:
                timetable_errors += 1
                source_reports.append(
                    {
                        "lineName": line_name,
                        "timetableUrl": candidate["timetableUrl"],
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        train_groups = sorted(stop_url_candidates_by_key.items())
        if args.max_stop_pages_per_line:
            train_groups = train_groups[: args.max_stop_pages_per_line]

        line_train_count_before = len(train_instances)
        line_unmatched: list[dict[str, Any]] = []
        stop_page_errors: Counter[str] = Counter()
        parsed_pages = 0
        skipped_seen = 0
        for stop_index, ((navitime_line_id, train_code), candidate_items) in enumerate(train_groups, start=1):
            service_instance_id = f"{SOURCE_KEY}:{normalize_line(line_name)}:{navitime_line_id}:{train_code}:{SERVICE_DAY}"
            if service_instance_id in instance_index:
                skipped_seen += 1
                continue
            parsed = None
            unmatched: list[dict[str, Any]] = []
            skip_reason = None
            for item in sorted(candidate_items, key=lambda value: candidate_origin_sort_key(value["candidate"])):
                stop_url = item["stopUrl"]
                if stop_url in seen_source_urls:
                    continue
                try:
                    parsed, unmatched, skip_reason = parse_stop_page(
                        stop_url,
                        target_line_name=line_name,
                        line_id=line_id,
                        known_station_keys=known_station_keys,
                        matcher=matcher,
                        service_day=SERVICE_DAY,
                    )
                except Exception as exc:
                    stop_page_errors[f"{type(exc).__name__}: {exc}"] += 1
                    seen_source_urls.add(stop_url)
                    continue
                seen_source_urls.add(stop_url)
                if parsed:
                    break
                stop_page_errors[skip_reason or "unparsed"] += 1
            line_unmatched.extend(unmatched)
            if not parsed:
                continue
            parsed_pages += 1
            action = upsert_train_instance(train_instances, instance_index, parsed)
            if len(train_instances) >= next_train_checkpoint:
                write_collection_outputs(
                    output_path=args.output,
                    audit_path=args.audit_output,
                    physical_map=physical_map,
                    target_lines=target_lines,
                    train_instances=train_instances,
                    line_audits=line_audits,
                    unmatched=all_unmatched + line_unmatched,
                    partial=True,
                    source_reports=source_reports,
                )
                print(
                    f"  {line_name}: train checkpoint {len(train_instances)} "
                    f"after train group {stop_index}/{len(train_groups)} ({action})",
                    flush=True,
                )
                next_train_checkpoint += CHECKPOINT_TRAINS_EVERY
            if stop_index % 50 == 0:
                print(
                    f"  {line_name}: parsed train groups {stop_index}/{len(train_groups)} "
                    f"line_trains={len([train for train in train_instances if train.get('line_name') == line_name])}",
                    flush=True,
                )

        line_trains = [train for train in train_instances if train.get("line_name") == line_name]
        all_unmatched.extend(line_unmatched)
        line_audits.append(
            {
                "lineName": line_name,
                "lineId": line_id,
                "physicalStationCount": len(station_names_by_line.get(line_name, [])),
                "navitimeNodeCount": len(nodes),
                "nodeErrorCount": node_errors,
                "timetablePageCount": len(timetable_candidates),
                "timetableErrorCount": timetable_errors,
                "rawStopPageLinkCount": raw_stop_url_count,
                "trainGroupCount": len(train_groups),
                "parsedStopPageCount": parsed_pages,
                "skippedAlreadySeenStopPageCount": skipped_seen,
                "newTrainInstanceCount": len(train_instances) - line_train_count_before,
                "lineTrainInstanceCount": len(line_trains),
                "unmatchedStopCount": len(line_unmatched),
                "badTimeOrderCount": sum(bad_time_order_count(train) for train in line_trains),
                "stopPageErrors": dict(stop_page_errors.most_common(20)),
                "sampleTimetablePages": list(timetable_candidates.values())[:10],
                "unmatchedStopsSample": line_unmatched[:20],
            }
        )
        print(
            f"  {line_name}: nodes={len(nodes)} timetables={len(timetable_candidates)} "
            f"raw_stop_links={raw_stop_url_count} train_groups={len(train_groups)} parsed={parsed_pages} "
            f"line_trains={len(line_trains)} unmatched={len(line_unmatched)}",
            flush=True,
        )
        write_collection_outputs(
            output_path=args.output,
            audit_path=args.audit_output,
            physical_map=physical_map,
            target_lines=target_lines,
            train_instances=train_instances,
            line_audits=line_audits,
            unmatched=all_unmatched,
            partial=True,
            source_reports=source_reports,
        )

    write_collection_outputs(
        output_path=args.output,
        audit_path=args.audit_output,
        physical_map=physical_map,
        target_lines=target_lines,
        train_instances=train_instances,
        line_audits=line_audits,
        unmatched=all_unmatched,
        partial=False,
        source_reports=source_reports,
    )
    final_audit = load_json(args.audit_output)
    print(f"Wrote {args.output}: {final_audit['trainInstanceCount']} trains")
    print(
        f"Wrote {args.audit_output}: unmatched={final_audit['unmatchedStopCount']} "
        f"bad_time_order={final_audit['badTimeOrderCount']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
