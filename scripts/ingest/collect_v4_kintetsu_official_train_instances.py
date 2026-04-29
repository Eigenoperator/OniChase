#!/usr/bin/env python3
"""Collect v4 weekday train instances from Kintetsu's official timetable pages.

Kintetsu publishes a station-direction timetable index as JSON and each
departure links to a T7 train-detail page.  This collector walks all weekday
station timetable pages, canonicalizes T7 train-detail links by train id/time,
then parses the full stop list from each train-detail page.
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

from collect_v4_gtfs_train_instances import (
    V4StationMatcher,
    load_json,
    normalize_line,
    normalize_name_variants,
    write_json,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_LINE_INVENTORY = ROOT / "data" / "v4_nationwide_line_inventory.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_kintetsu_official_cache"
DEFAULT_OUTPUT = ROOT / "data" / "v4_kintetsu_official_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_kintetsu_official_train_instances_audit.json"
DEFAULT_SERVICE_DATE = "2026-04-27"

KINTETSU_OPERATOR_ID = "kintetsu"
KINTETSU_OPERATOR_NAME = "近畿日本鉄道"
KINTETSU_TIMETABLE_JSON_URL = "https://www.kintetsu.co.jp/common/rn/json/kttimetable.json?250714"
KINTETSU_T7_BASE = "https://eki.kintetsu.co.jp/norikae/T7"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cache_path(cache_dir: Path, namespace: str, key: str, suffix: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return cache_dir / namespace / f"{digest}{suffix}"


def fetch_bytes_cached(url: str, cache_dir: Path, namespace: str, suffix: str, refresh: bool, timeout: int = 60) -> bytes:
    path = cache_path(cache_dir, namespace, url, suffix)
    if path.exists() and not refresh:
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/json,*/*",
            "User-Agent": "Mozilla/5.0 (compatible; OniChase-v4-kintetsu-official-collector/0.1)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    path.write_bytes(raw)
    return raw


def decode_html(raw: bytes) -> str:
    return raw.decode("cp932", errors="replace")


def strip_tags(value: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_hhmm(value: str) -> str | None:
    text = strip_tags(value)
    text = text.replace("：", ":").replace("－", "").replace("-", "").strip()
    if not text:
        return None
    match = re.search(r"(\d{1,2})\s*:\s*(\d{2})", text)
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"


def minutes(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    hour_text, minute_text = value.split(":", 1)
    try:
        total = int(hour_text) * 60 + int(minute_text)
    except ValueError:
        return None
    # Existing v4 timetable audits treat after-midnight service as next-day
    # when comparing monotonic order.
    if total < 3 * 60:
        total += 24 * 60
    return total


def clean_source_line_label(value: str) -> str:
    text = strip_tags(value)
    text = re.sub(r"【([^】]+)】.*", r"\1", text)
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = text.replace("生駒ケーブル", "生駒鋼索線")
    text = text.replace("西信貴ケーブル", "西信貴鋼索線")
    return text.strip()


def source_line_names_to_physical(label: str, physical_lines: set[str]) -> list[str]:
    cleaned = clean_source_line_label(label)
    candidates = [cleaned]
    candidates.extend(part.strip() for part in re.split(r"[・/／]", cleaned) if part.strip())
    output: list[str] = []
    for item in candidates:
        if item in physical_lines and item not in output:
            output.append(item)
    return output


def canonical_t7_from_href(href: str, base_url: str) -> tuple[str, str] | None:
    absolute = urllib.parse.urljoin(base_url, html.unescape(href))
    parsed = urllib.parse.urlparse(absolute)
    if not parsed.path.endswith("/T7") and not parsed.path.endswith("T7"):
        return None
    params = urllib.parse.parse_qs(parsed.query)
    tx = (params.get("tx") or [""])[0]
    dw = (params.get("dw") or ["0"])[0]
    time = (params.get("time") or [""])[0]
    if not tx:
        return None
    # Keep sf and the rest of the original query in the fetch URL.  Some train
    # detail pages work with only tx/dw/time, but through-service pages can
    # return "data lost" unless the station-context parameter is preserved.
    sf = (params.get("sf") or [""])[0]
    # The station-page links often include mobile/session parameters.  Keeping
    # those can force a truncated IM page; the stable PC detail page only needs
    # the station code plus train id/day/time.
    normalized_params = {"tx": tx, "dw": dw, "USR": "PC"}
    if time:
        # Time is only context for a few legacy pages.  It must not be part of
        # the canonical train key because the same real train appears from many
        # station pages with different station-local time parameters.
        normalized_params["time"] = time
    if sf:
        normalized_params = {"sf": sf, **normalized_params}
    normalized = f"{KINTETSU_T7_BASE}?{urllib.parse.urlencode(normalized_params)}"
    return f"{tx}|{dw}", normalized


def extract_t7_links(page_html: str, page_url: str) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    for match in re.finditer(r"""href\s*=\s*["']([^"']*T7\?[^"']+)["']""", page_html, flags=re.IGNORECASE):
        canonical = canonical_t7_from_href(match.group(1), page_url)
        if canonical:
            output.append(canonical)
    return output


def parse_train_header(page_html: str) -> dict[str, str | None]:
    before_stop_table = page_html.split("停車駅", 1)[0]
    bolds = re.findall(r"<b[^>]*>(.*?)</b>", before_stop_table, flags=re.IGNORECASE | re.DOTALL)
    header = ""
    for bold in reversed(bolds):
        text = strip_tags(bold)
        if "平日のダイヤ" in text or "行き" in text:
            header = text
            break
    header = header.replace("平日のダイヤ", "").strip()
    header = re.sub(r"\s+", " ", header)
    origin = None
    origin_match = re.search(r"（始発駅：(.+?)）", header)
    if origin_match:
        origin = origin_match.group(1).strip()
        header = (header[: origin_match.start()] + header[origin_match.end() :]).strip()
    headsign = None
    train_type = None
    destination_match = re.search(r"(.+?)\s+(.+?)行き", header)
    if destination_match:
        train_type = destination_match.group(1).strip() or None
        headsign = destination_match.group(2).strip() or None
    elif header.endswith("行き"):
        headsign = header[:-2].strip() or None
    else:
        train_type = header or None
    return {
        "header": header or None,
        "train_type": train_type,
        "headsign": headsign,
        "origin": origin,
    }


def parse_train_stop_rows(page_html: str) -> list[dict[str, Any]]:
    if "停車駅" not in page_html:
        return []
    segment = page_html.split("停車駅", 1)[1]
    rows: list[dict[str, Any]] = []
    row_pattern = re.compile(
        r"<tr[^>]*>\s*"
        r"<td[^>]*>\s*<a[^>]*>(?P<station>.*?)</a>\s*</td>\s*"
        r"<td[^>]*>(?P<arr>.*?)</td>\s*"
        r"<td[^>]*>(?P<dep>.*?)</td>\s*"
        r"</tr>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for index, match in enumerate(row_pattern.finditer(segment), start=1):
        station_name = strip_tags(match.group("station"))
        if not station_name:
            continue
        arrival = parse_hhmm(match.group("arr"))
        departure = parse_hhmm(match.group("dep"))
        rows.append(
            {
                "sequence": index,
                "station_name_raw": station_name,
                "arrival_hhmm": arrival,
                "departure_hhmm": departure,
            }
        )
    return rows


class KintetsuPhysicalIndex:
    def __init__(self, physical_map: dict[str, Any], line_inventory: dict[str, Any]) -> None:
        self.by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.line_ids: dict[str, str] = {}
        self.physical_lines: set[str] = set()
        for line in line_inventory.get("lines", []):
            if line.get("operatorName") != KINTETSU_OPERATOR_NAME:
                continue
            line_name = str(line.get("lineName") or "")
            if line_name:
                self.line_ids[line_name] = str(line.get("id") or line_name)
                self.physical_lines.add(line_name)
        for station in physical_map.get("physicalStations", []):
            if station.get("operatorName") != KINTETSU_OPERATOR_NAME:
                continue
            for key in normalize_name_variants(station.get("nameJa") or ""):
                self.by_name[key].append(station)

    def candidates(self, station_name: str) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for key in normalize_name_variants(station_name):
            for station in self.by_name.get(key, []):
                station_id = str(station.get("id") or "")
                if station_id in seen:
                    continue
                seen.add(station_id)
                candidates.append(station)
        return candidates

    def line_id(self, line_name: str | None) -> str | None:
        if not line_name:
            return None
        return self.line_ids.get(line_name) or line_name


def score_candidate(
    candidate: dict[str, Any],
    source_lines: set[str],
    previous_choice: dict[str, Any] | None,
    previous_lines: set[str],
    next_lines: set[str],
) -> tuple[int, str, str]:
    line = str(candidate.get("lineName") or "")
    group_id = str(candidate.get("stationGroupId") or "")
    score = 0
    if line in source_lines:
        score += 4
    if line in previous_lines:
        score += 7
    if line in next_lines:
        score += 7
    if previous_choice:
        if line == previous_choice.get("lineName"):
            score += 10
        if group_id == previous_choice.get("stationGroupId"):
            score += 4
    return (score, line, group_id)


def attach_station_matches(
    rows: list[dict[str, Any]],
    matcher: V4StationMatcher,
    physical_index: KintetsuPhysicalIndex,
    source_lines: set[str],
) -> tuple[list[dict[str, Any]], Counter[str], list[dict[str, Any]]]:
    candidate_lists = [physical_index.candidates(row["station_name_raw"]) for row in rows]
    candidate_line_sets = [{str(candidate.get("lineName") or "") for candidate in candidates} for candidates in candidate_lists]
    matched_rows: list[dict[str, Any]] = []
    match_methods: Counter[str] = Counter()
    unmatched: list[dict[str, Any]] = []
    previous_choice: dict[str, Any] | None = None
    visit_counts: Counter[str] = Counter()

    for index, row in enumerate(rows):
        candidates = candidate_lists[index]
        choice: dict[str, Any] | None = None
        match_method = "unmatched"
        if candidates:
            previous_lines = candidate_line_sets[index - 1] if index > 0 else set()
            next_lines = candidate_line_sets[index + 1] if index + 1 < len(candidate_line_sets) else set()
            choice = max(
                candidates,
                key=lambda candidate: score_candidate(candidate, source_lines, previous_choice, previous_lines, next_lines),
            )
            match_method = "kintetsu_name_context"
        else:
            fallback = matcher.match(
                operator_name=KINTETSU_OPERATOR_NAME,
                line_name=None,
                stop_name=row["station_name_raw"],
                stop_lat=None,
                stop_lon=None,
            )
            if fallback.get("matched"):
                choice = {
                    "id": fallback["physicalStationId"],
                    "stationGroupId": fallback["stationGroupId"],
                    "lineName": None,
                }
                match_method = fallback["method"]

        if choice:
            station_group_id = str(choice.get("stationGroupId") or "")
            visit_counts[station_group_id] += 1
            line_name = choice.get("lineName")
            matched = {
                **row,
                "station_id": station_group_id,
                "station_group_id": station_group_id,
                "physical_station_id": choice.get("id"),
                "line_id": physical_index.line_id(str(line_name) if line_name else None),
                "line_name": line_name,
                "platform": None,
                "loop_pass_index": visit_counts[station_group_id],
                "match_method": match_method,
                "match_distance_m": None,
            }
            previous_choice = choice
        else:
            fallback_id = "KINTETSU_UNMATCHED_" + hashlib.sha1(row["station_name_raw"].encode("utf-8")).hexdigest()[:12]
            matched = {
                **row,
                "station_id": fallback_id,
                "station_group_id": None,
                "physical_station_id": None,
                "line_id": None,
                "line_name": None,
                "platform": None,
                "loop_pass_index": None,
                "match_method": "unmatched",
                "match_distance_m": None,
            }
            unmatched.append({"stationName": row["station_name_raw"], "matchMethod": "unmatched"})
        match_methods[matched["match_method"]] += 1
        matched_rows.append(matched)
    return matched_rows, match_methods, unmatched


def primary_line(stop_times: list[dict[str, Any]]) -> tuple[str | None, str | None, list[str]]:
    counts = Counter(str(stop.get("line_name") or "") for stop in stop_times if stop.get("line_name"))
    if not counts:
        return None, None, []
    line_name, _count = counts.most_common(1)[0]
    line_names = sorted(counts)
    line_id = next((str(stop.get("line_id")) for stop in stop_times if stop.get("line_name") == line_name and stop.get("line_id")), line_name)
    return line_id, line_name, line_names


def parse_train_detail(
    key: str,
    url: str,
    page_html: str,
    source_line_names: set[str],
    matcher: V4StationMatcher,
    physical_index: KintetsuPhysicalIndex,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    header = parse_train_header(page_html)
    rows = parse_train_stop_rows(page_html)
    source_lines: set[str] = set()
    for label in source_line_names:
        source_lines.update(source_line_names_to_physical(label, physical_index.physical_lines))
    stop_times, match_methods, unmatched = attach_station_matches(rows, matcher, physical_index, source_lines)
    line_id, line_name, line_names = primary_line(stop_times)
    tx, dw = key.split("|", 1)
    service_instance_id = f"kintetsu_official:{tx}:{dw}"
    train_type = header.get("train_type") or None
    headsign = header.get("headsign") or None
    service_name = " ".join(part for part in [str(train_type or ""), f"{headsign}行き" if headsign else ""] if part).strip()
    if not service_name:
        service_name = line_name or "近鉄列車"
    train = None
    matched_stop_count = sum(1 for stop in stop_times if stop.get("station_group_id"))
    if len(stop_times) >= 2 and matched_stop_count >= 2:
        train = {
            "train_number": service_instance_id,
            "service_instance_id": service_instance_id,
            "source_trip_id": key,
            "operator_id": KINTETSU_OPERATOR_ID,
            "operator_name": KINTETSU_OPERATOR_NAME,
            "service_name": service_name,
            "display_name": service_name,
            "headsign": headsign or "",
            "train_type": train_type,
            "route_color": None,
            "line_id": line_id,
            "line_name": line_name,
            "physical_line_names": line_names,
            "source_feed_key": "kintetsu_official_2026-04-27",
            "source_url": url,
            "source_line_names": sorted(source_line_names),
            "stop_times": stop_times,
        }
    audit = {
        "key": key,
        "url": url,
        "parsed": train is not None,
        "stopCount": len(stop_times),
        "matchedStopCount": matched_stop_count,
        "unmatchedStopCount": len(unmatched),
        "unmatchedStops": unmatched[:20],
        "matchMethods": dict(sorted(match_methods.items())),
        "lineNames": line_names,
        "header": header,
    }
    return train, audit


def load_weekday_timetable_entries(cache_dir: Path, refresh: bool) -> list[dict[str, Any]]:
    raw = fetch_bytes_cached(KINTETSU_TIMETABLE_JSON_URL, cache_dir, "json", ".json", refresh=refresh)
    data = json.loads(raw.decode("utf-8-sig"))
    entries = [item for item in data if item.get("曜日") == "平日" and item.get("URL")]
    unique: dict[str, dict[str, Any]] = {}
    for item in entries:
        unique[str(item["URL"])] = item
    return sorted(unique.values(), key=lambda item: (item.get("路線名") or "", item.get("駅名") or "", item["URL"]))


def collect_train_detail_urls(
    entries: list[dict[str, Any]],
    cache_dir: Path,
    refresh: bool,
    workers: int,
    max_pages: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    selected_entries = entries[:max_pages] if max_pages else entries
    train_details: dict[str, dict[str, Any]] = {}
    page_audits: list[dict[str, Any]] = []

    def fetch_one(entry: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[str, str]], str | None]:
        url = str(entry["URL"])
        try:
            raw = fetch_bytes_cached(url, cache_dir, "t5", ".html", refresh=refresh)
            page_html = decode_html(raw)
            return entry, extract_t7_links(page_html, url), None
        except Exception as exc:  # noqa: BLE001 - audit should keep moving.
            return entry, [], f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(fetch_one, entry) for entry in selected_entries]
        for index, future in enumerate(as_completed(futures), start=1):
            entry, links, error = future.result()
            if index % 50 == 0 or index == len(futures):
                print(f"  T5 pages {index}/{len(futures)}; train detail keys={len(train_details)}", flush=True)
            if error:
                page_audits.append(
                    {
                        "url": entry.get("URL"),
                        "lineName": entry.get("路線名"),
                        "stationName": entry.get("駅名"),
                        "error": error,
                        "trainDetailLinkCount": 0,
                    }
                )
                continue
            for key, url in links:
                item = train_details.setdefault(
                    key,
                    {
                        "key": key,
                        "url": url,
                        "urls": set(),
                        "sourceLineNames": set(),
                        "sourceStationNames": set(),
                        "sourceDirectionNames": set(),
                    },
                )
                item["urls"].add(url)
                item["sourceLineNames"].add(str(entry.get("路線名") or ""))
                item["sourceStationNames"].add(str(entry.get("駅名") or ""))
                item["sourceDirectionNames"].add(str(entry.get("方面名") or ""))
            page_audits.append(
                {
                    "url": entry.get("URL"),
                    "lineName": entry.get("路線名"),
                    "stationName": entry.get("駅名"),
                    "directionName": entry.get("方面名"),
                    "trainDetailLinkCount": len(links),
                    "error": None,
                }
            )

    normalized: dict[str, dict[str, Any]] = {}
    for key, item in train_details.items():
        normalized[key] = {
            **item,
            "urls": sorted(item["urls"]),
            "sourceLineNames": sorted(item["sourceLineNames"]),
            "sourceStationNames": sorted(item["sourceStationNames"]),
            "sourceDirectionNames": sorted(item["sourceDirectionNames"]),
        }
    return normalized, page_audits


def collect_trains(
    train_details: dict[str, dict[str, Any]],
    cache_dir: Path,
    refresh: bool,
    workers: int,
    max_trains: int,
    matcher: V4StationMatcher,
    physical_index: KintetsuPhysicalIndex,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    items = list(sorted(train_details.values(), key=lambda item: item["key"]))
    if max_trains:
        items = items[:max_trains]
    trains: list[dict[str, Any]] = []
    detail_audits: list[dict[str, Any]] = []
    fetch_errors: list[dict[str, Any]] = []

    def fetch_parse_one(item: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
        key = str(item["key"])
        urls = [str(url) for url in (item.get("urls") or [item["url"]])]
        parsed_contexts: list[tuple[dict[str, Any], dict[str, Any]]] = []
        context_errors: list[dict[str, Any]] = []
        try:
            for url in urls:
                try:
                    raw = fetch_bytes_cached(url, cache_dir, "t7", ".html", refresh=refresh)
                    page_html = decode_html(raw)
                    if "停車駅" not in page_html and "★検索結果" in page_html:
                        raw = fetch_bytes_cached(url, cache_dir, "t7", ".html", refresh=True)
                        page_html = decode_html(raw)
                    train, context_audit = parse_train_detail(
                        key,
                        url,
                        page_html,
                        set(item.get("sourceLineNames") or []),
                        matcher,
                        physical_index,
                    )
                    if train:
                        parsed_contexts.append((train, context_audit))
                    else:
                        context_errors.append({
                            "url": url,
                            "error": "parsed_without_train",
                            "stopCount": context_audit.get("stopCount") if context_audit else None,
                        })
                except Exception as exc:  # noqa: BLE001
                    context_errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
            if not parsed_contexts:
                return None, None, {
                    "key": key,
                    "url": urls[0] if urls else "",
                    "contextUrlCount": len(urls),
                    "contextErrorsSample": context_errors[:8],
                    "error": "no_parsed_context",
                }
            train, best_context_audit = max(
                parsed_contexts,
                key=lambda pair: (
                    pair[1].get("matchedStopCount") or 0,
                    pair[1].get("stopCount") or 0,
                    -len(str(pair[0].get("source_url") or "")),
                ),
            )
            audit = {
                **best_context_audit,
                "contextUrlCount": len(urls),
                "parsedContextCount": len(parsed_contexts),
                "contextErrorCount": len(context_errors),
                "contextErrorsSample": context_errors[:8],
                "contextStopCountsSample": sorted(
                    [
                        {
                            "url": context_train.get("source_url"),
                            "stopCount": context_audit.get("stopCount"),
                            "matchedStopCount": context_audit.get("matchedStopCount"),
                            "firstStop": (context_train.get("stop_times") or [{}])[0].get("station_name_raw"),
                            "lastStop": (context_train.get("stop_times") or [{}])[-1].get("station_name_raw"),
                        }
                        for context_train, context_audit in parsed_contexts
                    ],
                    key=lambda row: (-(row.get("matchedStopCount") or 0), -(row.get("stopCount") or 0), str(row.get("firstStop") or "")),
                )[:12],
                "sourceStationNamesSample": list(item.get("sourceStationNames") or [])[:8],
                "sourceDirectionNamesSample": list(item.get("sourceDirectionNames") or [])[:8],
            }
            return train, audit, None
        except Exception as exc:  # noqa: BLE001
            return None, None, {"key": key, "url": urls[0] if urls else "", "error": f"{type(exc).__name__}: {exc}"}

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(fetch_parse_one, item) for item in items]
        for index, future in enumerate(as_completed(futures), start=1):
            train, audit, error = future.result()
            if train:
                trains.append(train)
            if audit:
                detail_audits.append(audit)
            if error:
                fetch_errors.append(error)
            if index % 250 == 0 or index == len(futures):
                print(f"  T7 train details {index}/{len(futures)}; parsed trains={len(trains)}", flush=True)
    return sorted(trains, key=lambda item: item["service_instance_id"]), detail_audits, fetch_errors


def audit_train_integrity(trains: list[dict[str, Any]]) -> dict[str, Any]:
    duplicate_ids = [train_id for train_id, count in Counter(train["service_instance_id"] for train in trains).items() if count > 1]
    short = [train["service_instance_id"] for train in trains if len(train.get("stop_times") or []) < 2]
    bad_order: list[dict[str, Any]] = []
    unmatched_stops: list[dict[str, Any]] = []
    line_counts: Counter[str] = Counter()
    for train in trains:
        previous = -1
        for stop in train.get("stop_times") or []:
            if stop.get("line_name"):
                line_counts[str(stop["line_name"])] += 1
            if not stop.get("station_group_id"):
                unmatched_stops.append(
                    {
                        "serviceInstanceId": train["service_instance_id"],
                        "stationNameRaw": stop.get("station_name_raw"),
                    }
                )
            current = minutes(stop.get("departure_hhmm") or stop.get("arrival_hhmm"))
            if current is None:
                continue
            if current < previous:
                bad_order.append(
                    {
                        "serviceInstanceId": train["service_instance_id"],
                        "stationNameRaw": stop.get("station_name_raw"),
                        "previousMinutes": previous,
                        "currentMinutes": current,
                    }
                )
            previous = max(previous, current)
    return {
        "duplicateServiceInstanceIdCount": len(duplicate_ids),
        "duplicateServiceInstanceIdsSample": sorted(duplicate_ids)[:20],
        "shortTrainInstanceCount": len(short),
        "shortTrainInstancesSample": sorted(short)[:20],
        "badTimeOrderCount": len(bad_order),
        "badTimeOrderSample": bad_order[:20],
        "unmatchedStopCount": len(unmatched_stops),
        "unmatchedStopsSample": unmatched_stops[:20],
        "lineStopCounts": dict(sorted(line_counts.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--line-inventory", type=Path, default=DEFAULT_LINE_INVENTORY)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--service-date", default=DEFAULT_SERVICE_DATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--max-pages", type=int, default=0)
    parser.add_argument("--max-trains", type=int, default=0)
    args = parser.parse_args()

    physical_map = load_json(args.physical_map)
    line_inventory = load_json(args.line_inventory)
    matcher = V4StationMatcher(physical_map)
    physical_index = KintetsuPhysicalIndex(physical_map, line_inventory)

    print("Loading Kintetsu weekday timetable index...", flush=True)
    entries = load_weekday_timetable_entries(args.cache_dir, refresh=args.refresh_cache)
    print(f"  weekday station-direction pages={len(entries)}", flush=True)
    print("Collecting train-detail links from station timetable pages...", flush=True)
    train_details, page_audits = collect_train_detail_urls(
        entries,
        args.cache_dir,
        refresh=args.refresh_cache,
        workers=args.workers,
        max_pages=args.max_pages,
    )
    print(f"  unique train-detail keys={len(train_details)}", flush=True)
    print("Parsing train-detail stop lists...", flush=True)
    trains, detail_audits, fetch_errors = collect_trains(
        train_details,
        args.cache_dir,
        refresh=args.refresh_cache,
        workers=args.workers,
        max_trains=args.max_trains,
        matcher=matcher,
        physical_index=physical_index,
    )

    integrity = audit_train_integrity(trains)
    output = {
        "id": "v4_kintetsu_official_weekday_train_instances_v0_1",
        "label": "V4 weekday train instances collected from Kintetsu official train-detail timetables",
        "version": "0.1.0",
        "service_day": args.service_date,
        "source": {
            "kind": "official_kintetsu_timetable_t5_t7",
            "timetableJsonUrl": KINTETSU_TIMETABLE_JSON_URL,
        },
        "station_identity": physical_map.get("identityVersion"),
        "train_instances": trains,
    }
    audit = {
        "schema": "onichase.v4.kintetsu_official_train_instances_audit.v1",
        "generatedAt": now_iso(),
        "serviceDay": args.service_date,
        "operatorName": KINTETSU_OPERATOR_NAME,
        "timetablePageCount": len(entries),
        "scannedTimetablePageCount": len(entries[: args.max_pages] if args.max_pages else entries),
        "trainDetailKeyCount": len(train_details),
        "parsedTrainDetailCount": len(detail_audits),
        "trainInstanceCount": len(trains),
        "stopTimeCount": sum(len(train["stop_times"]) for train in trains),
        "fetchErrorCount": len(fetch_errors),
        "fetchErrorsSample": fetch_errors[:20],
        "integrity": integrity,
        "pageAuditsSample": page_audits[:50],
        "detailAuditsSample": detail_audits[:50],
    }
    write_json(args.output, output)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(trains)} train instances")
    print(
        f"Wrote {args.audit_output}: unmatched={integrity['unmatchedStopCount']} "
        f"bad_order={integrity['badTimeOrderCount']} fetch_errors={len(fetch_errors)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
