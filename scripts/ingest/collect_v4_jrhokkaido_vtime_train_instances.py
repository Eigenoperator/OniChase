#!/usr/bin/env python3
"""Collect JR Hokkaido train instances from official vtime line timetables."""

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
from collections import Counter
from pathlib import Path
from typing import Any

import requests

from collect_v4_gtfs_train_instances import V4StationMatcher, normalize_line, normalize_name, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_LINE_INVENTORY = ROOT / "docs" / "data" / "v4_maplibre" / "line_inventory.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_jrhokkaido_vtime_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_jrhokkaido_vtime_train_instances_audit.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_jrhokkaido_vtime_cache"

OPERATOR_ID = "jr_hokkaido"
OPERATOR_NAME = "北海道旅客鉄道"
SERVICE_DAY = "20260427"
ROUTE_COLOR = "2CB3C9"
LINE_LIST_URL = "https://jrhokkaidonorikae.com/linelist/linelist.php"
VTIME_BASE_URL = "https://jrhokkaidonorikae.com/vtime/vtime.php"
TIMEOUT = 25

LINE_ALIAS_TO_PHYSICAL = {
    "北海道新幹線": "北海道新幹線",
    "函館本線": "函館線",
    "函館線": "函館線",
    "室蘭本線": "室蘭線",
    "室蘭線": "室蘭線",
    "千歳線": "千歳線",
    "宗谷本線": "宗谷線",
    "宗谷線": "宗谷線",
    "石北本線": "石北線",
    "石北線": "石北線",
    "富良野線": "富良野線",
    "日高本線": "日高線",
    "日高線": "日高線",
    "札沼線": "札沼線",
    "根室本線": "根室線",
    "根室線": "根室線",
    "石勝線": "石勝線",
    "釧網本線": "釧網線",
    "釧網線": "釧網線",
    "留萌本線": "留萌線",
    "留萌線": "留萌線",
    "海峡線": "海峡線",
}

SERVICE_LABEL_PHYSICAL_LINES = {
    "ライラック": ["函館線"],
    "カムイ": ["函館線"],
    "オホーツク": ["函館線", "石北線"],
    "宗谷": ["函館線", "宗谷線"],
    "サロベツ": ["宗谷線"],
    "大雪": ["石北線"],
    "きたみ": ["石北線"],
    "おおぞら": ["千歳線", "石勝線", "根室線"],
    "とかち": ["千歳線", "石勝線", "根室線"],
    "フラノラベンダーエクスプレス": ["函館線", "根室線", "富良野線"],
    "すずらん": ["室蘭線", "千歳線"],
    "北斗": ["函館線", "室蘭線", "千歳線"],
    "エアポート": ["千歳線", "函館線"],
}

SKIP_LABEL_PARTS = {
    "道南いさりび鉄道",
    # Hokkaido Shinkansen is already covered by the v2/v4 shinkansen corpus.
    # The JR Hokkaido vtime page also contains JR East stations, which makes it
    # the wrong source for company-local station_identity matching.
    "東北・山形・秋田・北海道新幹線",
}

TAG_RE = re.compile(r"<[^>]+>")


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def cache_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"


def fetch_text(url: str, cache_dir: Path, refresh: bool = False) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(cache_dir, url)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8", errors="replace")
    response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0 (OniChase-v4 JR Hokkaido collector)"})
    response.raise_for_status()
    response.encoding = "utf-8"
    text = response.text
    path.write_text(text, encoding="utf-8")
    time.sleep(0.03)
    return text


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub("", value))).strip()


def extract_rows(table_html: str) -> list[tuple[str, str]]:
    return re.findall(r'<tr[^>]*class="row ([^"]+)"[^>]*>(.*?)</tr>', table_html, re.DOTALL)


def extract_cells(row_html: str) -> list[str]:
    return [
        strip_tags(cell)
        for cell in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
    ]


def extract_table(html_text: str, div_id: str) -> str:
    match = re.search(rf'<div id="{re.escape(div_id)}".*?<table>(.*?)</table>', html_text, re.DOTALL)
    return match.group(1) if match else ""


def line_id_lookup(line_inventory: dict[str, Any]) -> dict[str, str]:
    return {
        line["lineName"]: line["id"]
        for line in line_inventory["lines"]
        if line.get("operatorName") == OPERATOR_NAME
    }


def physical_lines_for_label(label: str, known_lines: set[str]) -> list[str]:
    found: list[str] = []
    for alias, physical_line in LINE_ALIAS_TO_PHYSICAL.items():
        if alias in label and physical_line in known_lines and physical_line not in found:
            found.append(physical_line)
    for keyword, physical_lines in SERVICE_LABEL_PHYSICAL_LINES.items():
        if keyword not in label:
            continue
        for physical_line in physical_lines:
            if physical_line in known_lines and physical_line not in found:
                found.append(physical_line)
    return found


def discover_vtime_entries(html_text: str, known_lines: set[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for match in re.finditer(r'<div class="line">(.*?)</div>', html_text, re.DOTALL):
        row_html = match.group(1)
        label_match = re.search(r'<span class="line-name">(.*?)</span>', row_html, re.DOTALL)
        label = strip_tags(label_match.group(1)) if label_match else ""
        if not label or any(part in label for part in SKIP_LABEL_PARTS):
            continue
        physical_lines = physical_lines_for_label(label, known_lines)
        if not physical_lines:
            continue
        for button in re.finditer(
            r'<span class="updown-button" data-sid="([^"]*)" data-eid="([^"]*)" data-reid="([^"]*)">(.*?)</span>',
            row_html,
            re.DOTALL,
        ):
            sid, eid, reid, direction_html = button.groups()
            params = {"s": sid, "d": SERVICE_DAY}
            if eid:
                params["e"] = eid
            if reid:
                params["re"] = reid
            entries.append(
                {
                    "label": label,
                    "direction": strip_tags(direction_html),
                    "sid": sid,
                    "eid": eid,
                    "reid": reid,
                    "physicalLineCandidates": physical_lines,
                    "url": f"{VTIME_BASE_URL}?{urllib.parse.urlencode(params)}",
                }
            )
    return entries


def parse_compact_time(value: str, previous_minutes: int | None) -> tuple[str | None, int | None]:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) < 3:
        return None, previous_minutes
    digits = digits[-4:] if len(digits) > 4 else digits
    hour = int(digits[:-2])
    minute = int(digits[-2:])
    if minute >= 60:
        return None, previous_minutes
    total = hour * 60 + minute
    if previous_minutes is not None:
        while total + 180 < previous_minutes:
            total += 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}", total


def best_station_match(
    matcher: V4StationMatcher,
    physical_station_by_id: dict[str, dict[str, Any]],
    station_name: str,
    candidate_lines: list[str],
    all_lines: list[str],
) -> tuple[dict[str, Any], str | None]:
    for line_name in candidate_lines:
        match = matcher.match(OPERATOR_NAME, line_name, station_name, None, None)
        if match["matched"] and str(match.get("method", "")).startswith("operator_line_name"):
            return match, line_name
    for line_name in all_lines:
        match = matcher.match(OPERATOR_NAME, line_name, station_name, None, None)
        if match["matched"] and str(match.get("method", "")).startswith("operator_line_name"):
            return match, line_name
    match = matcher.match(OPERATOR_NAME, None, station_name, None, None)
    if match["matched"] and match.get("physicalStationId") in physical_station_by_id:
        station = physical_station_by_id[match["physicalStationId"]]
        return match, station.get("lineName")
    return match, None


def append_or_merge_stop(stop_times: list[dict[str, Any]], stop: dict[str, Any]) -> None:
    if stop_times and stop_times[-1].get("station_group_id") == stop.get("station_group_id"):
        current = stop_times[-1]
        if stop.get("arrival_hhmm"):
            current["arrival_hhmm"] = stop["arrival_hhmm"]
        if stop.get("departure_hhmm"):
            current["departure_hhmm"] = stop["departure_hhmm"]
        return
    stop["sequence"] = len(stop_times) + 1
    stop_times.append(stop)


def parse_vtime_page(
    html_text: str,
    entry: dict[str, Any],
    matcher: V4StationMatcher,
    line_ids: dict[str, str],
    all_lines: list[str],
    physical_station_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    top_rows = extract_rows(extract_table(html_text, "topHeader"))
    label_rows = extract_rows(extract_table(html_text, "ekidoriBody"))
    body_rows = extract_rows(extract_table(html_text, "timeBody"))
    if not top_rows or not label_rows or not body_rows:
        return [], [{"entry": entry, "reason": "missing_table"}]

    header_by_class: dict[str, list[str]] = {}
    for row_class, row_html in top_rows:
        header_by_class[row_class.split()[0]] = extract_cells(row_html)

    station_rows: list[tuple[str, str, list[str]]] = []
    for (label_class, label_html), (_, body_html) in zip(label_rows, body_rows):
        if not label_class.startswith("A01"):
            continue
        label_cells = extract_cells(label_html)
        body_cells = extract_cells(body_html)
        if not label_cells:
            continue
        station_name = label_cells[0]
        dep_arv = label_cells[1] if len(label_cells) > 1 else "発"
        station_rows.append((station_name, dep_arv, body_cells))

    train_numbers = header_by_class.get("B01", [])
    train_types = header_by_class.get("B03", [])
    train_names_extra = header_by_class.get("B05", [])
    trains: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for column_index, train_number in enumerate(train_numbers):
        train_number = train_number.strip()
        if not train_number:
            continue
        stop_times: list[dict[str, Any]] = []
        previous_minutes: int | None = None
        physical_lines_in_train: list[str] = []
        for station_name, dep_arv, body_cells in station_rows:
            if column_index >= len(body_cells):
                continue
            hhmm, previous_minutes_candidate = parse_compact_time(body_cells[column_index], previous_minutes)
            if not hhmm:
                continue
            previous_minutes = previous_minutes_candidate
            match, matched_line = best_station_match(
                matcher,
                physical_station_by_id,
                station_name,
                entry["physicalLineCandidates"],
                all_lines,
            )
            if not match["matched"]:
                unmatched.append(
                    {
                        "stationNameRaw": station_name,
                        "trainNumber": train_number,
                        "sourceLabel": entry["label"],
                        "sourceUrl": entry["url"],
                        "matchMethod": match["method"],
                        "candidateCount": match["candidateCount"],
                    }
                )
                continue
            line_name = matched_line or entry["physicalLineCandidates"][0]
            if line_name not in physical_lines_in_train:
                physical_lines_in_train.append(line_name)
            stop: dict[str, Any] = {
                "sequence": 0,
                "station_name_raw": station_name,
                "station_id": match["stationGroupId"],
                "station_group_id": match["stationGroupId"],
                "physical_station_id": match["physicalStationId"],
                "line_id": line_ids.get(line_name, f"JR_HOKKAIDO_{normalize_line(line_name)}"),
                "line_name": line_name,
                "arrival_hhmm": hhmm if "着" in dep_arv else None,
                "departure_hhmm": hhmm if "発" in dep_arv else None,
                "platform": None,
                "loop_pass_index": 1,
                "match_method": match["method"],
                "match_distance_m": match["distanceMeters"],
            }
            if not stop["arrival_hhmm"] and not stop["departure_hhmm"]:
                stop["departure_hhmm"] = hhmm
            append_or_merge_stop(stop_times, stop)
        if len(stop_times) < 2:
            continue
        for sequence, stop in enumerate(stop_times, start=1):
            stop["sequence"] = sequence
        first = stop_times[0]
        last = stop_times[-1]
        train_type = train_types[column_index].strip() if column_index < len(train_types) else ""
        display_name = train_names_extra[column_index].strip() if column_index < len(train_names_extra) else ""
        primary_line = physical_lines_in_train[0] if physical_lines_in_train else entry["physicalLineCandidates"][0]
        first_time = first.get("departure_hhmm") or first.get("arrival_hhmm") or ""
        last_time = last.get("arrival_hhmm") or last.get("departure_hhmm") or ""
        signature = hashlib.sha1(
            "|".join(
                [
                    train_number,
                    first["station_name_raw"],
                    first_time,
                    last["station_name_raw"],
                    last_time,
                    ",".join(stop["station_name_raw"] for stop in stop_times),
                ]
            ).encode("utf-8")
        ).hexdigest()[:12]
        trains.append(
            {
                "train_number": train_number,
                "service_instance_id": f"jr_hokkaido_vtime:{entry['sid']}:{train_number}:{signature}:{SERVICE_DAY}",
                "source_trip_id": f"jr_hokkaido_vtime:{entry['sid']}:{train_number}:{signature}:{SERVICE_DAY}",
                "operator_id": OPERATOR_ID,
                "operator_name": OPERATOR_NAME,
                "service_name": entry["label"],
                "display_name": display_name or train_type or train_number,
                "headsign": last["station_name_raw"],
                "train_type": train_type,
                "route_color": ROUTE_COLOR,
                "line_id": line_ids.get(primary_line, f"JR_HOKKAIDO_{normalize_line(primary_line)}"),
                "line_name": primary_line,
                "physical_line_names": physical_lines_in_train,
                "source_collection": "jr_hokkaido_vtime_20260427",
                "source_feed_key": "jr_hokkaido_vtime_20260427",
                "source_url": entry["url"],
                "source_vtime_label": entry["label"],
                "source_vtime_direction": entry["direction"],
                "stop_times": stop_times,
            }
        )
    return trains, unmatched


def dedupe_train_instances(trains: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_signature: dict[tuple[Any, ...], dict[str, Any]] = {}
    for train in trains:
        stops = train.get("stop_times") or []
        signature = (
            train.get("train_number"),
            stops[0].get("station_group_id") if stops else None,
            stops[0].get("departure_hhmm") or stops[0].get("arrival_hhmm") if stops else None,
            stops[-1].get("station_group_id") if stops else None,
            stops[-1].get("arrival_hhmm") or stops[-1].get("departure_hhmm") if stops else None,
        )
        current = best_by_signature.get(signature)
        if current is None or len(stops) > len(current.get("stop_times") or []):
            best_by_signature[signature] = train
    return sorted(
        best_by_signature.values(),
        key=lambda train: (
            train.get("line_name") or "",
            (train.get("stop_times") or [{}])[0].get("departure_hhmm") or "",
            train.get("train_number") or "",
            train.get("service_instance_id") or "",
        ),
    )


def bad_time_order_count(train: dict[str, Any]) -> int:
    previous = -1
    bad = 0
    for stop in train.get("stop_times") or []:
        hhmm = stop.get("departure_hhmm") or stop.get("arrival_hhmm")
        if not hhmm or ":" not in hhmm:
            continue
        hour, minute = [int(part) for part in hhmm.split(":", 1)]
        current = hour * 60 + minute
        if current < previous:
            bad += 1
        previous = max(previous, current)
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--line-inventory", type=Path, default=DEFAULT_LINE_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--max-pages", type=int, default=0)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    physical_map = load_json(args.physical_map)
    line_inventory = load_json(args.line_inventory)
    matcher = V4StationMatcher(physical_map)
    line_ids = line_id_lookup(line_inventory)
    known_lines = {
        station["lineName"]
        for station in physical_map["physicalStations"]
        if station.get("operatorName") == OPERATOR_NAME
    }
    all_lines = sorted(known_lines)
    physical_station_by_id = {
        station["id"]: station
        for station in physical_map["physicalStations"]
    }

    line_list_html = fetch_text(LINE_LIST_URL, args.cache_dir, refresh=args.refresh)
    entries = discover_vtime_entries(line_list_html, known_lines)
    if args.max_pages:
        entries = entries[: args.max_pages]
    print(f"Discovered {len(entries)} JR Hokkaido vtime pages", flush=True)

    trains: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    page_audits: list[dict[str, Any]] = []
    errors: Counter[str] = Counter()
    for page_index, entry in enumerate(entries, start=1):
        try:
            html_text = fetch_text(entry["url"], args.cache_dir, refresh=args.refresh)
            page_trains, page_unmatched = parse_vtime_page(
                html_text,
                entry,
                matcher,
                line_ids,
                all_lines,
                physical_station_by_id,
            )
        except Exception as exc:  # noqa: BLE001
            errors[f"{type(exc).__name__}: {exc}"] += 1
            continue
        trains.extend(page_trains)
        unmatched.extend(page_unmatched)
        page_audits.append(
            {
                "label": entry["label"],
                "direction": entry["direction"],
                "sid": entry["sid"],
                "url": entry["url"],
                "physicalLineCandidates": entry["physicalLineCandidates"],
                "trainInstanceCount": len(page_trains),
                "unmatchedStopCount": len(page_unmatched),
            }
        )
        print(
            f"[{page_index}/{len(entries)}] {entry['label']} {entry['direction']}: "
            f"trains={len(page_trains)} unmatched={len(page_unmatched)}",
            flush=True,
        )

    deduped = dedupe_train_instances(trains)
    audit = {
        "schema": "onichase.v4.jrhokkaido_vtime_train_instances_audit.v1",
        "serviceDay": SERVICE_DAY,
        "source": LINE_LIST_URL,
        "vtimePageCount": len(entries),
        "rawTrainInstanceCount": len(trains),
        "trainInstanceCount": len(deduped),
        "duplicateDroppedCount": len(trains) - len(deduped),
        "stopTimeCount": sum(len(train.get("stop_times") or []) for train in deduped),
        "badTimeOrderCount": sum(bad_time_order_count(train) for train in deduped),
        "unmatchedStopCount": len(unmatched),
        "physicalLineCounts": dict(sorted(Counter(line for train in deduped for line in train.get("physical_line_names", [])).items())),
        "pageAudits": page_audits,
        "errors": dict(errors.most_common(20)),
        "unmatchedStops": unmatched[:1000],
    }
    payload = {
        "id": "v4_jrhokkaido_vtime_weekday_train_instances_v0_1",
        "label": "V4 JR Hokkaido weekday train instances collected from official vtime line timetables",
        "version": "0.1.0",
        "partial": False,
        "service_day": SERVICE_DAY,
        "source": LINE_LIST_URL,
        "station_identity": physical_map.get("identityVersion"),
        "train_instances": deduped,
    }
    write_json(args.output, payload)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(deduped)} trains")
    print(f"Wrote {args.audit_output}: unmatched={audit['unmatchedStopCount']} bad_time_order={audit['badTimeOrderCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
