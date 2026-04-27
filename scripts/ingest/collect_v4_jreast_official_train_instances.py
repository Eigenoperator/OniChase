#!/usr/bin/env python3
"""Collect JR East train instances from the official Japanese timetable site.

This collector starts from v4 physical lines, finds official JR East station
timetable pages by station-name search, extracts weekday timetable pages for a
target line, then parses train-detail pages into v4 station_identity_v2 ids.
It is designed for the "remaining JR East lines" pass after the v3 Tokyo-core
corpus has already been adapted to v4.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from html import unescape
from pathlib import Path
from typing import Any

from collect_v4_gtfs_train_instances import V4StationMatcher, haversine_m, normalize_name_variants
from parse_jreast_train_detail import parse_html as parse_train_detail_html


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_LINE_INVENTORY = ROOT / "docs" / "data" / "v4_maplibre" / "line_inventory.json"
DEFAULT_COVERAGE = ROOT / "data" / "v4_jr_company_timetable_coverage_audit.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_jreast_official_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_jreast_official_train_instances_audit.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_jreast_official_cache"

BASE_URL = "https://timetables.jreast.co.jp"
SEARCH_URL = BASE_URL + "/cgi-bin/st_search.cgi"
ISSUE = "2605"

LINE_ALIASES = {
    "奥羽線": ["奥羽線", "奥羽本線", "山形線"],
    "信越線": ["信越線", "信越本線"],
    "羽越線": ["羽越線", "羽越本線"],
    "東北線": ["東北線", "東北本線", "宇都宮線"],
    "中央線": ["中央線", "中央本線"],
    "大船渡線": ["大船渡線", "大船渡線ＢＲＴ", "大船渡線BRT"],
    "気仙沼線": ["気仙沼線", "気仙沼線ＢＲＴ", "気仙沼線BRT"],
}


TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(TAG_RE.sub(" ", value))).strip()


def normalize_key(value: str) -> str:
    text = value or ""
    for old in ("　", " ", "-", "‐", "ー", "・", "（", "）", "(", ")", "線", "本"):
        text = text.replace(old, "")
    return text.lower()


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
    return cache_dir / f"{digest}.html"


def fetch_text(url: str, cache_dir: Path, refresh: bool = False, delay_seconds: float = 0.05) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(cache_dir, url)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (OniChase-v4 JR East collector)"})
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                text = response.read().decode(charset, errors="replace")
            break
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 5:
                if path.exists():
                    return path.read_text(encoding="utf-8")
                raise
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt == 5:
                if path.exists():
                    return path.read_text(encoding="utf-8")
                raise
        sleep_seconds = min(30, attempt * 3)
        print(f"  retry {attempt}/5 for {url} after {type(last_error).__name__}: {last_error}", flush=True)
        time.sleep(sleep_seconds)
    else:
        raise RuntimeError(f"Failed to fetch {url}: {last_error}")
    path.write_text(text, encoding="utf-8")
    if delay_seconds:
        time.sleep(delay_seconds)
    return text


def line_id_lookup(line_inventory: dict[str, Any]) -> dict[tuple[str, str], str]:
    return {
        (line["operatorName"], line["lineName"]): line["id"]
        for line in line_inventory["lines"]
    }


def physical_station_names_by_line(physical_map: dict[str, Any]) -> dict[str, list[str]]:
    names: dict[str, set[str]] = defaultdict(set)
    for station in physical_map["physicalStations"]:
        if station.get("operatorName") != "東日本旅客鉄道":
            continue
        names[station["lineName"]].add(station["nameJa"])
    return {line_name: sorted(station_names) for line_name, station_names in names.items()}


def build_context_station_index(physical_map: dict[str, Any]) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, dict[str, Any]]]:
    groups_by_id = {group["id"]: group for group in physical_map["stationGroups"]}
    candidates_by_name: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for station in physical_map["physicalStations"]:
        group = groups_by_id.get(station["stationGroupId"])
        if not group:
            continue
        for name_key in normalize_name_variants(station.get("nameJa") or ""):
            candidates_by_name[name_key].setdefault(
                station["stationGroupId"],
                {
                    "stationGroupId": station["stationGroupId"],
                    "physicalStationId": station["id"],
                    "nameJa": station.get("nameJa"),
                    "lat": group["centroid"]["lat"],
                    "lon": group["centroid"]["lon"],
                },
            )
    return candidates_by_name, groups_by_id


def missing_jreast_lines(coverage_audit: dict[str, Any]) -> list[str]:
    for company in coverage_audit["companies"]:
        if company["operatorId"] != "jr_east":
            continue
        return [
            line["lineName"]
            for line in company["lines"]
            if line["coverageStatus"] != "covered"
        ]
    return []


def search_station_list_pages(station_name: str, cache_dir: Path, refresh: bool = False) -> list[dict[str, str]]:
    query = urllib.parse.urlencode({"mode": "0", "ekimei": station_name})
    html = fetch_text(f"{SEARCH_URL}?{query}", cache_dir=cache_dir, refresh=refresh)
    pages: list[dict[str, str]] = []
    seen: set[str] = set()
    for href, label_html in re.findall(r'<a[^>]+href="([^"]*/timetable/list\d{4}\.html)"[^>]*>(.*?)</a>', html, re.DOTALL):
        label = strip_tags(label_html)
        if station_name not in label:
            continue
        url = urllib.parse.urljoin(BASE_URL + "/", href)
        if url in seen:
            continue
        seen.add(url)
        pages.append({"stationName": station_name, "listUrl": url, "label": label})
    return pages


def parse_station_list_page(html: str, list_url: str) -> dict[str, Any]:
    station_match = re.search(r'<h1 class="station_name01">(.*?)</h1>', html, re.DOTALL)
    station_name = strip_tags(station_match.group(1)) if station_match else None
    candidates: list[dict[str, str]] = []
    for row_html in re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL):
        weekday_match = re.search(r'<td class="weekday">\s*<a href="([^"]+)"', row_html, re.DOTALL)
        if not weekday_match:
            continue
        th_match = re.search(r"<th>(.*?)</th>", row_html, re.DOTALL)
        td_matches = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if not th_match or not td_matches:
            continue
        route_name = strip_tags(th_match.group(1))
        direction = strip_tags(td_matches[0])
        timetable_url = urllib.parse.urljoin(list_url, weekday_match.group(1))
        candidates.append(
            {
                "stationName": station_name or "",
                "routeName": route_name,
                "direction": direction,
                "timetableUrl": timetable_url,
            }
        )
    return {"stationName": station_name, "candidates": candidates}


def route_matches_line(route_name: str, line_name: str) -> bool:
    route_key = normalize_key(route_name)
    if "新幹線" in route_name and "新幹線" not in line_name:
        return False
    if line_name == "東北線":
        if any(token in route_name for token in ("新幹線", "京浜東北", "根岸線")):
            return False
        if any(token in route_name for token in ("東北本線", "東北線", "宇都宮線")):
            return True
        return False
    aliases = LINE_ALIASES.get(line_name, [line_name])
    for alias in aliases:
        alias_key = normalize_key(alias)
        if route_key == alias_key or alias_key in route_key or route_key in alias_key:
            return True
    return False


def extract_train_links_from_timetable_page(html: str, page_url: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for href in re.findall(r'href="([^"]+/train/[^"]+)"', html):
        full_url = urllib.parse.urljoin(page_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        links.append(full_url)
    return links


def minutes_from_hhmm(value: str | None) -> int | None:
    if not value:
        return None
    parts = value.split(":")
    if len(parts) < 2:
        return None
    return int(parts[0]) * 60 + int(parts[1])


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


def context_point_for_stop(stop: dict[str, Any], groups_by_id: dict[str, dict[str, Any]]) -> tuple[float, float] | None:
    group_id = stop.get("station_group_id")
    if not group_id:
        return None
    group = groups_by_id.get(group_id)
    if not group:
        return None
    centroid = group.get("centroid") or {}
    return float(centroid["lat"]), float(centroid["lon"])


def resolve_contextual_unmatched_stop_times(
    stop_times: list[dict[str, Any]],
    candidates_by_name: dict[str, dict[str, dict[str, Any]]],
    groups_by_id: dict[str, dict[str, Any]],
) -> None:
    for index, stop in enumerate(stop_times):
        if stop.get("station_group_id"):
            continue
        candidates: dict[str, dict[str, Any]] = {}
        for name_key in normalize_name_variants(stop.get("station_name_raw") or ""):
            candidates.update(candidates_by_name.get(name_key, {}))
        if not candidates:
            continue

        context_points: list[tuple[float, float]] = []
        for prev in reversed(stop_times[:index]):
            point = context_point_for_stop(prev, groups_by_id)
            if point:
                context_points.append(point)
                break
        for nxt in stop_times[index + 1 :]:
            point = context_point_for_stop(nxt, groups_by_id)
            if point:
                context_points.append(point)
                break
        if not context_points:
            continue

        ranked = sorted(
            candidates.values(),
            key=lambda candidate: sum(
                haversine_m(point[0], point[1], float(candidate["lat"]), float(candidate["lon"]))
                for point in context_points
            ),
        )
        best = ranked[0]
        stop["station_id"] = best["stationGroupId"]
        stop["station_group_id"] = best["stationGroupId"]
        stop["physical_station_id"] = best["physicalStationId"]
        stop["match_method"] = "context_nearest_group"
        stop["match_distance_m"] = round(
            sum(
                haversine_m(point[0], point[1], float(best["lat"]), float(best["lon"]))
                for point in context_points
            )
            / len(context_points),
            1,
        )


def normalize_train(
    raw_train: dict[str, Any],
    train_url: str,
    line_name: str,
    line_id: str,
    matcher: V4StationMatcher,
    candidates_by_name: dict[str, dict[str, dict[str, Any]]],
    groups_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    stop_times: list[dict[str, Any]] = []
    visit_counts: Counter[str] = Counter()
    for raw_stop in raw_train.get("stop_times") or []:
        stop_name = raw_stop.get("station_name_raw") or ""
        match = matcher.match(
            operator_name="東日本旅客鉄道",
            line_name=line_name,
            stop_name=stop_name,
            stop_lat=None,
            stop_lon=None,
        )
        if match["matched"]:
            station_id = match["stationGroupId"]
        else:
            station_id = f"JREAST_UNMATCHED_{normalize_key(stop_name)}"
        visit_counts[station_id] += 1
        stop_times.append(
            {
                "sequence": int(raw_stop.get("sequence") or len(stop_times) + 1),
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
        )

    normalize_overnight_stop_times(stop_times)
    resolve_contextual_unmatched_stop_times(stop_times, candidates_by_name, groups_by_id)
    unmatched = [
        {
            "lineName": line_name,
            "trainUrl": train_url,
            "trainNumber": raw_train.get("train_number"),
            "stationNameRaw": stop["station_name_raw"],
            "matchMethod": stop["match_method"],
            "candidateCount": 0,
        }
        for stop in stop_times
        if not stop.get("station_group_id")
    ]
    url_tail = "/".join(urllib.parse.urlparse(train_url).path.split("/")[-3:]).replace("/", "_").replace(".html", "")
    service_instance_id = f"jr_east_official:{normalize_key(line_name)}:{url_tail}"
    train = {
        "train_number": raw_train.get("train_number") or service_instance_id,
        "service_instance_id": service_instance_id,
        "source_trip_id": service_instance_id,
        "operator_id": "jr_east",
        "operator_name": "東日本旅客鉄道",
        "service_name": line_name,
        "headsign": "",
        "train_type": raw_train.get("train_type"),
        "route_color": None,
        "line_id": line_id,
        "line_name": line_name,
        "source_feed_key": f"jreast_official_{ISSUE}",
        "source_url": train_url,
        "stop_times": stop_times,
    }
    if raw_train.get("display_name"):
        train["display_name"] = raw_train["display_name"]
    if raw_train.get("service_name"):
        train["service_name_detail"] = raw_train["service_name"]
    if raw_train.get("service_number"):
        train["service_number"] = raw_train["service_number"]
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


def write_collection_outputs(
    *,
    output_path: Path,
    audit_path: Path,
    physical_map: dict[str, Any],
    target_lines: list[str],
    trains_by_id: dict[str, dict[str, Any]],
    line_audits: list[dict[str, Any]],
    unmatched: list[dict[str, Any]],
    partial: bool,
) -> None:
    trains = sorted(trains_by_id.values(), key=lambda train: train["service_instance_id"])
    duplicate_ids = [
        key for key, count in Counter(train["service_instance_id"] for train in trains).items()
        if count > 1
    ]
    audit = {
        "schema": "onichase.v4.jreast_official_train_instances_audit.v1",
        "issue": ISSUE,
        "partial": partial,
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
        "unmatchedStops": unmatched[:1000],
    }
    output = {
        "id": "v4_jreast_official_weekday_train_instances_v0_1",
        "label": "V4 JR East weekday train instances collected from official Japanese JR East timetables",
        "version": "0.1.0",
        "partial": partial,
        "service_day": "weekday",
        "source": "https://timetables.jreast.co.jp/",
        "source_issue": "JR時刻表 2026年5月号",
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
    parser.add_argument("--line", action="append", help="Collect only this JR East physical line. Can be repeated.")
    parser.add_argument("--max-lines", type=int, default=0, help="Debug limit; 0 means all selected lines.")
    parser.add_argument("--max-stations-per-line", type=int, default=0, help="Debug limit; 0 means all stations.")
    parser.add_argument("--refresh", action="store_true", help="Refetch official pages instead of using local cache.")
    args = parser.parse_args()

    physical_map = load_json(args.physical_map)
    line_inventory = load_json(args.line_inventory)
    coverage_audit = load_json(args.coverage_audit)
    matcher = V4StationMatcher(physical_map)
    candidates_by_name, groups_by_id = build_context_station_index(physical_map)
    line_ids = line_id_lookup(line_inventory)
    station_names_by_line = physical_station_names_by_line(physical_map)
    target_lines = args.line or missing_jreast_lines(coverage_audit)
    if args.max_lines:
        target_lines = target_lines[: args.max_lines]

    all_trains_by_id: dict[str, dict[str, Any]] = {}
    line_audits: list[dict[str, Any]] = []
    all_unmatched: list[dict[str, Any]] = []

    for line_index, line_name in enumerate(target_lines, start=1):
        line_id = line_ids.get(("東日本旅客鉄道", line_name), f"JR_EAST_{normalize_key(line_name)}")
        station_names = station_names_by_line.get(line_name, [])
        if args.max_stations_per_line:
            station_names = station_names[: args.max_stations_per_line]
        timetable_candidates_by_url: dict[str, dict[str, str]] = {}
        searched_station_count = 0
        matched_station_pages = 0

        print(f"[{line_index}/{len(target_lines)}] {line_name}: search {len(station_names)} stations", flush=True)
        for station_name in station_names:
            searched_station_count += 1
            for page in search_station_list_pages(station_name, args.cache_dir, refresh=args.refresh):
                list_html = fetch_text(page["listUrl"], cache_dir=args.cache_dir, refresh=args.refresh)
                parsed = parse_station_list_page(list_html, page["listUrl"])
                page_matched = False
                for candidate in parsed["candidates"]:
                    if not route_matches_line(candidate["routeName"], line_name):
                        continue
                    timetable_candidates_by_url.setdefault(
                        candidate["timetableUrl"],
                        {
                            **candidate,
                            "sourceListUrl": page["listUrl"],
                            "sourceStationQuery": station_name,
                        },
                    )
                    page_matched = True
                if page_matched:
                    matched_station_pages += 1

        train_links: set[str] = set()
        for candidate in timetable_candidates_by_url.values():
            timetable_html = fetch_text(candidate["timetableUrl"], cache_dir=args.cache_dir, refresh=args.refresh)
            for train_url in extract_train_links_from_timetable_page(timetable_html, candidate["timetableUrl"]):
                train_links.add(train_url)

        line_train_count_before = len(all_trains_by_id)
        line_unmatched: list[dict[str, Any]] = []
        for train_index, train_url in enumerate(sorted(train_links), start=1):
            train_html = fetch_text(train_url, cache_dir=args.cache_dir, refresh=args.refresh)
            parsed = parse_train_detail_html(train_html, train_url, line_id=line_name)
            for raw_train in parsed["train_instances"]:
                train, unmatched = normalize_train(
                    raw_train,
                    train_url,
                    line_name,
                    line_id,
                    matcher,
                    candidates_by_name,
                    groups_by_id,
                )
                if len(train["stop_times"]) < 2:
                    continue
                all_trains_by_id[train["service_instance_id"]] = train
                line_unmatched.extend(unmatched)
            if train_index % 100 == 0 or train_index == len(train_links):
                print(f"  {line_name}: parsed {train_index}/{len(train_links)} train detail pages", flush=True)

        line_trains = [
            train for train in all_trains_by_id.values()
            if train.get("line_name") == line_name
        ]
        all_unmatched.extend(line_unmatched)
        line_audits.append(
            {
                "lineName": line_name,
                "lineId": line_id,
                "physicalStationCount": len(station_names_by_line.get(line_name, [])),
                "searchedStationCount": searched_station_count,
                "matchedStationPageCount": matched_station_pages,
                "timetablePageCount": len(timetable_candidates_by_url),
                "trainDetailPageCount": len(train_links),
                "newTrainInstanceCount": len(all_trains_by_id) - line_train_count_before,
                "lineTrainInstanceCount": len(line_trains),
                "unmatchedStopCount": len(line_unmatched),
                "badTimeOrderCount": sum(bad_time_order_count(train) for train in line_trains),
                "sampleTimetablePages": list(timetable_candidates_by_url.values())[:10],
                "unmatchedStopsSample": line_unmatched[:20],
            }
        )
        print(
            f"  {line_name}: timetables={len(timetable_candidates_by_url)} "
            f"details={len(train_links)} trains={len(line_trains)} unmatched={len(line_unmatched)}",
            flush=True,
        )
        write_collection_outputs(
            output_path=args.output,
            audit_path=args.audit_output,
            physical_map=physical_map,
            target_lines=target_lines,
            trains_by_id=all_trains_by_id,
            line_audits=line_audits,
            unmatched=all_unmatched,
            partial=True,
        )

    write_collection_outputs(
        output_path=args.output,
        audit_path=args.audit_output,
        physical_map=physical_map,
        target_lines=target_lines,
        trains_by_id=all_trains_by_id,
        line_audits=line_audits,
        unmatched=all_unmatched,
        partial=False,
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
