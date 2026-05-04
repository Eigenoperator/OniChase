#!/usr/bin/env python3
"""Collect JR West train instances from official JR Odekake timetable pages."""

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
from pathlib import Path
from typing import Any

import requests

from collect_v4_gtfs_train_instances import V4StationMatcher, haversine_m, normalize_line, normalize_name, normalize_name_variants
from parse_jrwest_train_timetable import parse_html as parse_train_html
from train_instance_merge import index_train_instances, upsert_train_instance


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_LINE_INVENTORY = ROOT / "docs" / "data" / "v4_maplibre" / "line_inventory.json"
DEFAULT_COVERAGE = ROOT / "data" / "v4_jr_company_timetable_coverage_with_jreast_jrcentral_audit.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_jrwest_official_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_jrwest_official_train_instances_audit.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_jrwest_official_cache"

OPERATOR_ID = "jr_west"
OPERATOR_NAME = "西日本旅客鉄道"
SERVICE_DAY = "20260427"
TIMEOUT = 20
MAX_FETCH_RETRIES = 3
ROUTE_COLOR = "2369C9"
SPLIT_COLUMN_STITCH_MAX_GAP_MINUTES = 15

SEARCH_URL = "https://eki.jr-odekake.net/search_free"
TIMETABLE_BASE = "https://timetable.jr-odekake.net"

LINE_ALIASES = {
    "東海道線": ["東海道線", "JR京都線", "ＪＲ京都線", "JR神戸線", "ＪＲ神戸線", "琵琶湖線"],
    "山陽線": ["山陽線", "山陽本線", "JR神戸線", "ＪＲ神戸線"],
    "福知山線": ["福知山線", "JR宝塚線", "ＪＲ宝塚線"],
    "関西線": ["関西線", "関西本線", "大和路線"],
    "片町線": ["片町線", "学研都市線"],
    "桜井線": ["桜井線", "万葉まほろば線"],
    "紀勢線": ["紀勢線", "紀勢本線", "きのくに線"],
    "山陰線": ["山陰線", "山陰本線", "嵯峨野線"],
    "桜島線": ["桜島線", "JRゆめ咲線", "ＪＲゆめ咲線", "ユニバーサルシティ"],
    "本四備讃線": ["本四備讃線", "瀬戸大橋線"],
    "吉備線": ["吉備線", "桃太郎線"],
    "宇野線": ["宇野線", "宇野みなと線", "瀬戸大橋線"],
    "大阪環状線": ["大阪環状線"],
    "JR東西線": ["JR東西線", "ＪＲ東西線"],
    "おおさか東線": ["おおさか東線"],
    "関西空港線": ["関西空港線", "関空快速"],
    "北陸線": ["北陸線", "北陸本線", "琵琶湖線"],
    "博多南線": ["博多南線"],
    "湖西線": ["湖西線"],
    "奈良線": ["奈良線"],
    "阪和線": ["阪和線"],
    "和歌山線": ["和歌山線"],
    "越美北線": ["越美北線", "九頭竜線"],
}

EXTRA_LINE_STATION_NAMES = {
    # Tsuruga is physically mapped as Hokuriku/Obama/Hokuriku Shinkansen, but JR
    # Odekake exposes Tsuruga-origin Thunderbird services on the Kosei Line tab.
    "湖西線": ["敦賀"],
}

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
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.cache"


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
                headers={"User-Agent": "Mozilla/5.0 (OniChase-v4 JR West collector)"},
            )
            if response.status_code in {400, 404, 410}:
                response.raise_for_status()
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
            text = response.text
            path.write_text(text, encoding="utf-8")
            time.sleep(0.02)
            return text
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code in {400, 404, 410}:
                raise
            last_error = exc
        except requests.Timeout:
            raise
        except requests.RequestException as exc:
            last_error = exc
        if attempt == MAX_FETCH_RETRIES:
            if path.exists():
                return path.read_text(encoding="utf-8", errors="replace")
            if last_error:
                raise last_error
        time.sleep(min(2 * attempt, 8))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", value))).strip()


def clean_station_name(value: str) -> str:
    text = html.unescape(str(value or "")).strip()
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"〔[^〕]*〕", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"［[^］]*］", "", text)
    text = text.replace("ＪＲ", "JR")
    text = re.sub(r"\s+", " ", text).strip()
    if text.endswith("駅"):
        text = text[:-1]
    return text


def normalize_station_lookup_key(value: str) -> str:
    return normalize_name(clean_station_name(value))


def clean_line_text(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = text.replace("ＪＲ", "JR")
    text = text.replace("本線", "線")
    text = text.replace(" ", "").replace("　", "")
    return text


def line_matches_text(line_name: str, text: str) -> bool:
    clean_text = clean_line_text(text)
    aliases = LINE_ALIASES.get(line_name, [line_name, line_name.replace("線", "本線")])
    for alias in aliases:
        clean_alias = clean_line_text(alias)
        if clean_alias and clean_alias in clean_text:
            return True
    return False


def line_id_lookup(line_inventory: dict[str, Any]) -> dict[tuple[str, str], str]:
    return {
        (line["operatorName"], line["lineName"]): line["id"]
        for line in line_inventory["lines"]
    }


def physical_station_names_by_line(physical_map: dict[str, Any]) -> dict[str, list[str]]:
    names: dict[str, set[str]] = defaultdict(set)
    for station in physical_map["physicalStations"]:
        if station.get("operatorName") == OPERATOR_NAME:
            names[station["lineName"]].add(station["nameJa"])
    for line_name, station_names in EXTRA_LINE_STATION_NAMES.items():
        names[line_name].update(station_names)
    return {line_name: sorted(station_names) for line_name, station_names in names.items()}


def missing_jrwest_lines(coverage_audit: dict[str, Any]) -> list[str]:
    for company in coverage_audit["companies"]:
        if company["operatorId"] == OPERATOR_ID:
            return [
                line["lineName"]
                for line in company["lines"]
                if line["coverageStatus"] != "covered"
                and line["lineName"] not in {"山陽新幹線", "北陸新幹線"}
            ]
    return []


def discover_station_eids(station_name: str, cache_dir: Path, refresh: bool = False) -> list[dict[str, str]]:
    url = f"{SEARCH_URL}?keyword={urllib.parse.quote(station_name)}"
    html_text = fetch_text(url, cache_dir=cache_dir, refresh=refresh)
    final_ids: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(r'<a[^>]+href="(/top\?id=(\d+))"[^>]*>(.*?)</a>', html_text, re.DOTALL):
        eid = match.group(2)
        label = clean_station_name(strip_tags(match.group(3)))
        if normalize_station_lookup_key(label) != normalize_station_lookup_key(station_name):
            continue
        if eid in seen:
            continue
        seen.add(eid)
        final_ids.append({"stationName": station_name, "eid": eid, "label": label})
    if final_ids:
        return final_ids
    # Unique station searches often redirect directly to /top?id=...
    id_match = re.search(r'/top\?id=(\d+)', html_text) or re.search(r'id=(\d+)', url)
    title_match = re.search(r"<title>(.*?)</title>", html_text, re.DOTALL)
    title = clean_station_name(strip_tags(title_match.group(1))) if title_match else station_name
    if id_match and normalize_station_lookup_key(title).startswith(normalize_station_lookup_key(station_name)):
        return [{"stationName": station_name, "eid": id_match.group(1), "label": title}]
    return []


def extract_mydia_url(top_or_search_html: str, eid: str) -> str | None:
    match = re.search(r'href="([^"]*mydia_sp\.cgi[^"]+)"', top_or_search_html)
    if not match:
        return None
    return html.unescape(match.group(1))


def get_station_timetable_home(eid: str, cache_dir: Path, refresh: bool = False) -> str | None:
    top_url = f"https://eki.jr-odekake.net/top?id={eid}"
    top_html = fetch_text(top_url, cache_dir=cache_dir, refresh=refresh)
    mydia_url = extract_mydia_url(top_html, eid)
    if not mydia_url:
        return None
    if mydia_url.startswith("//"):
        return "https:" + mydia_url
    if mydia_url.startswith("/"):
        return urllib.parse.urljoin("https://timetable.jr-odekake.net/", mydia_url)
    return mydia_url


def parse_station_timetable_options(html_text: str, page_url: str, line_name: str) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for row in re.findall(r'<table class="ekiTable03 timetable".*?</table>', html_text, re.DOTALL):
        th = re.search(r"<th[^>]*.*?</th>", row, re.DOTALL)
        row_line_name = strip_tags(th.group(0)) if th else ""
        if not line_matches_text(line_name, row_line_name):
            continue
        for link_match in re.finditer(r'onclick="link\((\d+)\)"[^>]*>(.*?)</a>', row, re.DOTALL):
            timetable_id = link_match.group(1)
            direction = strip_tags(link_match.group(2))
            options.append(
                {
                    "stationTimetableUrl": f"{TIMETABLE_BASE}/station-timetable/{timetable_id}?date={SERVICE_DAY}",
                    "stationTimetableId": timetable_id,
                    "lineLabel": row_line_name,
                    "directionLabel": direction,
                    "sourcePageUrl": page_url,
                }
            )
    return options


def extract_train_links(station_timetable_html: str, page_url: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for href in re.findall(r'href="(/train-timetable/\d+\?date=\d+)"', station_timetable_html):
        url = urllib.parse.urljoin(TIMETABLE_BASE, href)
        if url in seen:
            continue
        seen.add(url)
        links.append(url)
    return links


def train_id_from_url(train_url: str) -> str:
    match = re.search(r"/train-timetable/(\d+)", train_url)
    return match.group(1) if match else hashlib.sha1(train_url.encode("utf-8")).hexdigest()[:12]


def minutes_from_hhmm(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    hour, minute = value.split(":", 1)
    try:
        return int(hour) * 60 + int(minute)
    except ValueError:
        return None


def hhmm_from_minutes(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def train_boundary_minutes(train: dict[str, Any], boundary: str) -> int | None:
    stops = train.get("stop_times") or []
    if not stops:
        return None
    stop = stops[0] if boundary == "first" else stops[-1]
    return minutes_from_hhmm(stop.get("departure_hhmm") or stop.get("arrival_hhmm"))


def train_boundary_station_id(train: dict[str, Any], boundary: str) -> str:
    stops = train.get("stop_times") or []
    if not stops:
        return ""
    stop = stops[0] if boundary == "first" else stops[-1]
    return str(stop.get("station_group_id") or stop.get("station_id") or stop.get("station_name_raw") or "")


def can_stitch_split_column_trains(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("operator_id") != OPERATOR_ID or right.get("operator_id") != OPERATOR_ID:
        return False
    if left.get("line_name") != "湖西線" or right.get("line_name") != "湖西線":
        return False
    if not left.get("source_url") or left.get("source_url") != right.get("source_url"):
        return False
    if train_boundary_station_id(left, "last") != train_boundary_station_id(right, "first"):
        return False
    left_arrival = train_boundary_minutes(left, "last")
    right_departure = train_boundary_minutes(right, "first")
    if left_arrival is None or right_departure is None:
        return False
    gap = right_departure - left_arrival
    return 0 <= gap <= SPLIT_COLUMN_STITCH_MAX_GAP_MINUTES


def merged_boundary_stop(left_stop: dict[str, Any], right_stop: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left_stop)
    for key in ("departure_hhmm", "platform", "line_id", "line_name", "match_method", "match_distance_m"):
        if not merged.get(key) and right_stop.get(key):
            merged[key] = right_stop[key]
    if right_stop.get("arrival_hhmm") and not merged.get("arrival_hhmm"):
        merged["arrival_hhmm"] = right_stop["arrival_hhmm"]
    return merged


def stitch_train_chain(chain: list[dict[str, Any]]) -> dict[str, Any]:
    stitched = dict(chain[0])
    numbers = [str(train.get("train_number") or "").strip() for train in chain if train.get("train_number")]
    normalized_numbers = [normalize_line(number) for number in numbers if number]
    source_url = str(stitched.get("source_url") or "")
    train_id = train_id_from_url(source_url)
    stitched["train_number"] = "+".join(dict.fromkeys(numbers))
    stitched["service_number"] = stitched["train_number"]
    stitched["service_instance_id"] = (
        f"jr_west_official:{normalize_line(str(stitched.get('line_name') or ''))}:"
        f"{train_id}:{'-'.join(dict.fromkeys(normalized_numbers))}:{SERVICE_DAY}"
    )
    stitched["source_trip_id"] = stitched["service_instance_id"]
    stitched["source_column_count"] = max(int(train.get("source_column_count") or 1) for train in chain)
    stitched["source_column_index"] = None
    stitched["source_split_train_numbers"] = numbers
    stitched["source_split_service_instance_ids"] = [
        str(train.get("service_instance_id") or "") for train in chain
    ]
    stop_times: list[dict[str, Any]] = []
    for index, train in enumerate(chain):
        source_stops = [dict(stop) for stop in train.get("stop_times") or []]
        if not source_stops:
            continue
        if index == 0:
            stop_times.extend(source_stops)
            continue
        if stop_times and train_boundary_station_id({"stop_times": [stop_times[-1]]}, "first") == train_boundary_station_id({"stop_times": [source_stops[0]]}, "first"):
            stop_times[-1] = merged_boundary_stop(stop_times[-1], source_stops[0])
            stop_times.extend(source_stops[1:])
        else:
            stop_times.extend(source_stops)
    for sequence, stop in enumerate(stop_times, start=1):
        stop["sequence"] = sequence
    stitched["stop_times"] = stop_times
    return stitched


def stitch_reviewed_split_column_trains(train_instances: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_source_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for train in train_instances:
        if train.get("operator_id") == OPERATOR_ID and train.get("line_name") == "湖西線" and train.get("source_url"):
            by_source_url[str(train["source_url"])].append(train)

    consumed_ids: set[str] = set()
    stitched_by_first_id: dict[str, dict[str, Any]] = {}
    stitched_chains: list[list[str]] = []
    for trains in by_source_url.values():
        if len(trains) < 2:
            continue
        ordered = sorted(
            trains,
            key=lambda train: (
                train_boundary_minutes(train, "first") if train_boundary_minutes(train, "first") is not None else 99_999,
                str(train.get("service_instance_id") or ""),
            ),
        )
        for train in ordered:
            train_id = str(train.get("service_instance_id") or "")
            if train_id in consumed_ids:
                continue
            chain = [train]
            consumed_ids.add(train_id)
            while True:
                candidates = [
                    candidate for candidate in ordered
                    if str(candidate.get("service_instance_id") or "") not in consumed_ids
                    and can_stitch_split_column_trains(chain[-1], candidate)
                ]
                candidates.sort(
                    key=lambda candidate: (
                        train_boundary_minutes(candidate, "first") if train_boundary_minutes(candidate, "first") is not None else 99_999,
                        str(candidate.get("service_instance_id") or ""),
                    )
                )
                if not candidates:
                    break
                next_train = candidates[0]
                consumed_ids.add(str(next_train.get("service_instance_id") or ""))
                chain.append(next_train)
            if len(chain) >= 2:
                stitched = stitch_train_chain(chain)
                stitched_by_first_id[str(chain[0].get("service_instance_id") or "")] = stitched
                stitched_chains.append([str(item.get("service_instance_id") or "") for item in chain])
            else:
                consumed_ids.discard(train_id)

    repaired: list[dict[str, Any]] = []
    emitted_stitched_ids: set[str] = set()
    for train in train_instances:
        service_instance_id = str(train.get("service_instance_id") or "")
        stitched = stitched_by_first_id.get(service_instance_id)
        if stitched:
            repaired.append(stitched)
            emitted_stitched_ids.add(stitched["service_instance_id"])
            continue
        if service_instance_id in consumed_ids:
            continue
        repaired.append(train)

    return repaired, {
        "reviewedSplitColumnStitchCount": len(stitched_chains),
        "reviewedSplitColumnSourceRowCount": sum(len(chain) for chain in stitched_chains),
        "reviewedSplitColumnStitchedTrainIds": sorted(emitted_stitched_ids)[:100],
        "reviewedSplitColumnStitchSamples": stitched_chains[:20],
    }


def normalize_overnight_stop_times(stop_times: list[dict[str, Any]]) -> None:
    previous = -1
    day_offset = 0
    for stop in stop_times:
        for key in ("arrival_hhmm", "departure_hhmm"):
            raw = minutes_from_hhmm(stop.get(key))
            if raw is None:
                continue
            while raw + day_offset < previous:
                day_offset += 24 * 60
            adjusted = raw + day_offset
            stop[key] = hhmm_from_minutes(adjusted)
            previous = max(previous, adjusted)


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


def normalize_train(
    raw_train: dict[str, Any],
    train_url: str,
    line_name: str,
    line_id: str,
    matcher: V4StationMatcher,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    stop_times: list[dict[str, Any]] = []
    visit_counts: Counter[str] = Counter()
    for raw_stop in raw_train.get("stop_times") or []:
        stop_name = clean_station_name(raw_stop.get("station_name_raw") or "")
        match = matcher.match(OPERATOR_NAME, line_name, stop_name, None, None)
        station_id = match["stationGroupId"] if match["matched"] else f"JRWEST_UNMATCHED_{normalize_name(stop_name)}"
        visit_counts[station_id] += 1
        stop = {
            "sequence": len(stop_times) + 1,
            "station_name_raw": stop_name,
            "station_id": station_id,
            "station_group_id": match["stationGroupId"],
            "physical_station_id": match["physicalStationId"],
            "line_id": line_id,
            "line_name": line_name,
            "arrival_hhmm": raw_stop.get("arrival_hhmm"),
            "departure_hhmm": raw_stop.get("departure_hhmm"),
            "platform": raw_stop.get("platform"),
            "loop_pass_index": visit_counts[station_id],
            "match_method": match["method"],
            "match_distance_m": match["distanceMeters"],
        }
        stop_times.append(stop)
    normalize_overnight_stop_times(stop_times)
    resolve_contextual_unmatched_stop_times(stop_times, matcher)
    train_id = train_id_from_url(train_url)
    train_number = raw_train.get("train_number") or train_id
    train_id_suffix = train_id
    if int(raw_train.get("source_column_count") or 1) > 1:
        train_id_suffix = f"{train_id}:{normalize_line(str(train_number))}"
    service_instance_id = f"jr_west_official:{normalize_line(line_name)}:{train_id_suffix}:{SERVICE_DAY}"
    unmatched = [
        {
            "lineName": line_name,
            "sourceUrl": train_url,
            "trainNumber": train_number,
            "stationNameRaw": stop["station_name_raw"],
            "matchMethod": stop["match_method"],
        }
        for stop in stop_times
        if not stop.get("station_group_id")
    ]
    train = {
        "train_number": train_number,
        "service_instance_id": service_instance_id,
        "source_trip_id": service_instance_id,
        "operator_id": OPERATOR_ID,
        "operator_name": OPERATOR_NAME,
        "service_name": line_name,
        "headsign": "",
        "train_type": raw_train.get("train_type"),
        "route_color": ROUTE_COLOR,
        "line_id": line_id,
        "line_name": line_name,
        "source_feed_key": f"jr_west_official_{SERVICE_DAY}",
        "source_url": train_url,
        "stop_times": stop_times,
    }
    for key in ("display_name", "route_name", "coupled_route_names", "operating_days", "service_name", "service_number", "source_column_index", "source_column_count"):
        if raw_train.get(key):
            if key == "service_name":
                train["service_name_detail"] = raw_train[key]
            else:
                train[key] = raw_train[key]
    return train, unmatched


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
    target_lines: list[str],
    train_instances: list[dict[str, Any]],
    line_audits: list[dict[str, Any]],
    unmatched: list[dict[str, Any]],
    partial: bool,
) -> None:
    repaired_train_instances, stitch_audit = stitch_reviewed_split_column_trains(train_instances)
    trains = sorted(repaired_train_instances, key=lambda t: (t.get("line_name") or "", t["stop_times"][0].get("departure_hhmm") or "", t["service_instance_id"]))
    audit = {
        "schema": "onichase.v4.jrwest_official_train_instances_audit.v1",
        "partial": partial,
        "serviceDay": SERVICE_DAY,
        "targetLineCount": len(target_lines),
        "completedLineCount": len(line_audits),
        "targetLines": target_lines,
        "trainInstanceCount": len(trains),
        "stopTimeCount": sum(len(train.get("stop_times") or []) for train in trains),
        "duplicateServiceInstanceIdCount": sum(1 for _, c in Counter(t["service_instance_id"] for t in trains).items() if c > 1),
        "shortTrainInstanceCount": sum(1 for train in trains if len(train.get("stop_times") or []) < 2),
        "badTimeOrderCount": sum(bad_time_order_count(train) for train in trains),
        "unmatchedStopCount": len(unmatched),
        **stitch_audit,
        "lineAudits": line_audits,
        "unmatchedStops": unmatched[:1000],
    }
    payload = {
        "id": "v4_jrwest_official_weekday_train_instances_v0_1",
        "label": "V4 JR West weekday train instances collected from official JR Odekake pages",
        "version": "0.1.0",
        "partial": partial,
        "service_day": SERVICE_DAY,
        "source": "https://timetable.jr-odekake.net/",
        "station_identity": physical_map.get("identityVersion"),
        "train_instances": trains,
    }
    write_json(output_path, payload)
    write_json(audit_path, audit)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--line-inventory", type=Path, default=DEFAULT_LINE_INVENTORY)
    parser.add_argument("--coverage-audit", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--line", action="append")
    parser.add_argument("--max-lines", type=int, default=0)
    parser.add_argument("--max-stations-per-line", type=int, default=0)
    parser.add_argument("--max-trains-per-line", type=int, default=0)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    physical_map = load_json(args.physical_map)
    line_inventory = load_json(args.line_inventory)
    coverage_audit = load_json(args.coverage_audit)
    matcher = V4StationMatcher(physical_map)
    line_ids = line_id_lookup(line_inventory)
    station_names_by_line = physical_station_names_by_line(physical_map)
    target_lines = args.line or missing_jrwest_lines(coverage_audit)
    if args.max_lines:
        target_lines = target_lines[: args.max_lines]

    if args.output.exists() and os.environ.get("REBUILD") != "1":
        existing = load_json(args.output)
        train_instances, instance_index = index_train_instances(existing.get("train_instances", []))
    else:
        train_instances = []
        instance_index = {}
    all_unmatched: list[dict[str, Any]] = []
    line_audits: list[dict[str, Any]] = []

    for line_index, line_name in enumerate(target_lines, start=1):
        line_id = line_ids.get((OPERATOR_NAME, line_name), f"JR_WEST_{normalize_line(line_name)}")
        station_names = station_names_by_line.get(line_name, [])
        if args.max_stations_per_line:
            station_names = station_names[: args.max_stations_per_line]
        print(f"[{line_index}/{len(target_lines)}] {line_name}: search {len(station_names)} stations", flush=True)
        station_records: dict[str, dict[str, str]] = {}
        station_search_errors = 0
        for station_name in station_names:
            try:
                for record in discover_station_eids(station_name, args.cache_dir, refresh=args.refresh):
                    station_records.setdefault(record["eid"], record)
            except Exception:
                station_search_errors += 1

        station_timetable_options: dict[str, dict[str, Any]] = {}
        mydia_errors = 0
        for record in station_records.values():
            try:
                mydia_url = get_station_timetable_home(record["eid"], args.cache_dir, refresh=args.refresh)
                if not mydia_url:
                    continue
                mydia_html = fetch_text(mydia_url, args.cache_dir, refresh=args.refresh)
                for option in parse_station_timetable_options(mydia_html, mydia_url, line_name):
                    option["sourceStationName"] = record["stationName"]
                    option["sourceEid"] = record["eid"]
                    station_timetable_options.setdefault(option["stationTimetableUrl"], option)
            except Exception:
                mydia_errors += 1

        train_urls_by_id: dict[str, dict[str, Any]] = {}
        station_timetable_errors = 0
        for option in station_timetable_options.values():
            try:
                station_tt_html = fetch_text(option["stationTimetableUrl"], args.cache_dir, refresh=args.refresh)
                for train_url in extract_train_links(station_tt_html, option["stationTimetableUrl"]):
                    train_urls_by_id.setdefault(train_id_from_url(train_url), {"trainUrl": train_url, "option": option})
            except Exception:
                station_timetable_errors += 1
        train_items = list(train_urls_by_id.values())
        if args.max_trains_per_line:
            train_items = train_items[: args.max_trains_per_line]

        line_train_count_before = len(train_instances)
        line_unmatched: list[dict[str, Any]] = []
        train_errors: Counter[str] = Counter()
        parsed_train_pages = 0
        for train_index, item in enumerate(train_items, start=1):
            train_url = item["trainUrl"]
            try:
                train_html = fetch_text(train_url, args.cache_dir, refresh=args.refresh)
                parsed = parse_train_html(train_html, train_url, line_id=line_name)
            except Exception as exc:
                train_errors[f"{type(exc).__name__}: {exc}"] += 1
                continue
            for raw_train in parsed.get("train_instances") or []:
                train, unmatched = normalize_train(raw_train, train_url, line_name, line_id, matcher)
                if len(train["stop_times"]) < 2:
                    continue
                upsert_train_instance(train_instances, instance_index, train)
                line_unmatched.extend(unmatched)
                parsed_train_pages += 1
            if train_index % 250 == 0:
                print(f"  {line_name}: parsed {train_index}/{len(train_items)} train pages", flush=True)

        line_trains = [train for train in train_instances if train.get("line_name") == line_name]
        all_unmatched.extend(line_unmatched)
        line_audits.append(
            {
                "lineName": line_name,
                "lineId": line_id,
                "physicalStationCount": len(station_names_by_line.get(line_name, [])),
                "searchedStationCount": len(station_names),
                "stationEidCount": len(station_records),
                "stationSearchErrorCount": station_search_errors,
                "mydiaErrorCount": mydia_errors,
                "stationTimetablePageCount": len(station_timetable_options),
                "stationTimetableErrorCount": station_timetable_errors,
                "trainPageCount": len(train_items),
                "parsedTrainPageCount": parsed_train_pages,
                "newTrainInstanceCount": len(train_instances) - line_train_count_before,
                "lineTrainInstanceCount": len(line_trains),
                "unmatchedStopCount": len(line_unmatched),
                "badTimeOrderCount": sum(bad_time_order_count(train) for train in line_trains),
                "trainErrors": dict(train_errors.most_common(20)),
                "sampleStationTimetablePages": list(station_timetable_options.values())[:10],
                "unmatchedStopsSample": line_unmatched[:20],
            }
        )
        print(
            f"  {line_name}: eids={len(station_records)} station_timetables={len(station_timetable_options)} "
            f"trains={len(line_trains)} unmatched={len(line_unmatched)}",
            flush=True,
        )
        write_outputs(
            output_path=args.output,
            audit_path=args.audit_output,
            physical_map=physical_map,
            target_lines=target_lines,
            train_instances=train_instances,
            line_audits=line_audits,
            unmatched=all_unmatched,
            partial=True,
        )

    write_outputs(
        output_path=args.output,
        audit_path=args.audit_output,
        physical_map=physical_map,
        target_lines=target_lines,
        train_instances=train_instances,
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
