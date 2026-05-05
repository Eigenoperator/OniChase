#!/usr/bin/env python3
"""Collect v4 weekday train instances from Keihan official all-train PDFs."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import subprocess
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collect_v4_gtfs_train_instances import V4StationMatcher, load_json, normalize_name_variants, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_LINE_INVENTORY = ROOT / "data" / "v4_nationwide_line_inventory.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_keihan_official_cache"
DEFAULT_OUTPUT = ROOT / "data" / "v4_keihan_official_weekday_train_instances.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_keihan_official_train_instances_audit.json"
DEFAULT_SERVICE_DATE = "2026-04-27"

BASE = "https://www.keihan.co.jp"
OPERATOR_NAME = "京阪電気鉄道"
SOURCE_FEED_KEY = "keihan_official_all_train_pdf"

PDF_SOURCES = [
    {
        "key": "time01-9",
        "url": f"{BASE}/traffic/time-fare/pdf/time01-9.pdf",
        "label": "京阪本線・中之島線・鴨東線 平日 出町柳方面行き",
        "primaryLine": "京阪本線",
    },
    {
        "key": "time01-10",
        "url": f"{BASE}/traffic/time-fare/pdf/time01-10.pdf",
        "label": "京阪本線・中之島線・鴨東線 平日 淀屋橋・中之島方面行き",
        "primaryLine": "京阪本線",
    },
    {
        "key": "time02-5",
        "url": f"{BASE}/traffic/time-fare/pdf/time02-5.pdf",
        "label": "交野線 平日上り",
        "primaryLine": "交野線",
    },
    {
        "key": "time02-6",
        "url": f"{BASE}/traffic/time-fare/pdf/time02-6.pdf",
        "label": "交野線 平日下り",
        "primaryLine": "交野線",
    },
    {
        "key": "time03-5",
        "url": f"{BASE}/traffic/time-fare/pdf/time03-5.pdf",
        "label": "宇治線 平日上り",
        "primaryLine": "宇治線",
    },
    {
        "key": "time03-6",
        "url": f"{BASE}/traffic/time-fare/pdf/time03-6.pdf",
        "label": "宇治線 平日下り",
        "primaryLine": "宇治線",
    },
]

STATION_ALIASES = {
    "衹園四条": ["祇園四条", "祗園四条"],
    "祇󠄀園四条": ["祇園四条", "祗園四条"],
    "星ケ丘": ["星ヶ丘"],
}

NAKANOSHIMA = {"中之島", "渡辺橋", "大江橋", "なにわ橋"}
KATANO = {"宮之阪", "星ケ丘", "星ヶ丘", "村野", "郡津", "交野市", "河内森", "私市"}
UJI = {"観月橋", "桃山南口", "六地蔵", "木幡", "黄檗", "三室戸", "宇治"}
KAMOTO = {"三条", "神宮丸太町", "出町柳"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch_bytes_cached(url: str, cache_dir: Path, refresh: bool) -> bytes:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    path = cache_dir / "pdf" / f"{digest}.pdf"
    if path.exists() and not refresh:
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; OniChase-v4-keihan-official-collector/0.1)"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    path.write_bytes(data)
    return data


def pdf_cache_path(url: str, cache_dir: Path) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return cache_dir / "pdf" / f"{digest}.pdf"


def tsv_for_pdf(pdf_path: Path, refresh: bool) -> Path:
    tsv_path = pdf_path.with_suffix(".tsv")
    if tsv_path.exists() and not refresh:
        return tsv_path
    subprocess.run(["pdftotext", "-tsv", str(pdf_path), str(tsv_path)], check=True)
    return tsv_path


def load_physical_map(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


class KeihanPhysicalIndex:
    def __init__(self, physical_map: dict[str, Any], line_inventory: dict[str, Any]) -> None:
        self.matcher = V4StationMatcher(physical_map)
        self.station_by_id = {station["id"]: station for station in physical_map["physicalStations"]}
        self.station_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.line_id_by_operator_line: dict[tuple[str, str], str] = {}
        self.line_color_by_operator_line: dict[tuple[str, str], str] = {}
        for line in line_inventory.get("lines", []):
            operator_name = str(line.get("operatorName") or "")
            line_name = str(line.get("lineName") or "")
            self.line_id_by_operator_line[(operator_name, line_name)] = str(line.get("id") or line_name)
            self.line_color_by_operator_line[(operator_name, line_name)] = str(
                line.get("lineColor") or line.get("operatorColor") or "#011E41"
            ).lstrip("#")
        for station in physical_map.get("physicalStations", []):
            if station.get("operatorName") != OPERATOR_NAME:
                continue
            for key in normalize_name_variants(station.get("nameJa") or ""):
                self.station_by_name[key].append(station)

    def line_id(self, line_name: str) -> str:
        return self.line_id_by_operator_line.get((OPERATOR_NAME, line_name)) or line_name

    def route_color(self, line_name: str) -> str:
        return self.line_color_by_operator_line.get((OPERATOR_NAME, line_name), "#011E41").lstrip("#")

    def station_for_match(self, match: dict[str, Any]) -> dict[str, Any] | None:
        station_id = match.get("physicalStationId")
        if not station_id:
            return None
        return self.station_by_id.get(str(station_id))

    def candidates(self, station_name: str) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for alias in [station_name, *STATION_ALIASES.get(station_name, [])]:
            for key in normalize_name_variants(alias):
                for station in self.station_by_name.get(key, []):
                    station_id = str(station.get("id") or "")
                    if station_id in seen:
                        continue
                    seen.add(station_id)
                    output.append(station)
        return output

    def match_stop(self, station_name: str, preferred_lines: list[str]) -> dict[str, Any]:
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
                "method": "keihan_name_context",
                "stationGroupId": best["stationGroupId"],
                "physicalStationId": best["id"],
                "candidateCount": len(candidates),
            }
        for line_name in preferred_lines:
            match = self.matcher.match(OPERATOR_NAME, line_name, station_name, None, None)
            if match.get("matched"):
                match["method"] = f"fallback_{line_name}_{match['method']}"
                return match
        return self.matcher.match(OPERATOR_NAME, preferred_lines[0] if preferred_lines else None, station_name, None, None)


def preferred_lines_for_station(station_name: str, primary_line: str) -> list[str]:
    if station_name in NAKANOSHIMA:
        return ["中之島線", "京阪本線"]
    if station_name in KATANO:
        return ["交野線", "京阪本線"]
    if station_name in UJI:
        return ["宇治線", "京阪本線"]
    if station_name in KAMOTO:
        return ["鴨東線", "京阪本線"]
    if primary_line in {"交野線", "宇治線"} and station_name in {"枚方市", "中書島"}:
        return [primary_line, "京阪本線"]
    return [primary_line, "京阪本線", "鴨東線", "中之島線"]


def clean_text(value: str) -> str:
    return (value or "").strip().replace("祇󠄀", "祇")


def parse_hhmm(value: str) -> str | None:
    if not re.fullmatch(r"\d{1,2}:\d{2}", value or ""):
        return None
    hour, minute = value.split(":")
    return f"{int(hour):02d}:{int(minute):02d}"


def minutes(value: str | None) -> int | None:
    if not value or ":" not in value:
        return None
    hour_text, minute_text = value.split(":", 1)
    total = int(hour_text) * 60 + int(minute_text)
    if total < 3 * 60:
        total += 24 * 60
    return total


def cluster_rows(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda item: (item["top"], item["left"])):
        if not rows or abs(rows[-1][0]["top"] - word["top"]) > 2.2:
            rows.append([word])
        else:
            rows[-1].append(word)
    return [sorted(row, key=lambda item: item["left"]) for row in rows]


def read_tsv_words(tsv_path: Path) -> dict[int, list[dict[str, Any]]]:
    pages: dict[int, list[dict[str, Any]]] = defaultdict(list)
    with tsv_path.open(encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row.get("level") != "5":
                continue
            text = clean_text(row.get("text") or "")
            if not text:
                continue
            pages[int(row["page_num"])].append(
                {
                    "page": int(row["page_num"]),
                    "left": float(row["left"]),
                    "top": float(row["top"]),
                    "text": text,
                }
            )
    return pages


def nearest_column(left: float, column_xs: list[float]) -> int | None:
    if not column_xs:
        return None
    index = min(range(len(column_xs)), key=lambda i: abs(column_xs[i] - left))
    if abs(column_xs[index] - left) > 17:
        return None
    return index


def parse_pdf_table(tsv_path: Path, source: dict[str, str]) -> list[dict[str, Any]]:
    raw_trains: list[dict[str, Any]] = []
    pages = read_tsv_words(tsv_path)
    for page_num, words in sorted(pages.items()):
        rows = cluster_rows(words)
        type_row = next((row for row in rows if row and row[0]["text"] == "列車種別"), None)
        dest_row = next((row for row in rows if row and row[0]["text"] == "行先駅"), None)
        if not type_row:
            continue
        column_words = [word for word in type_row if word["left"] > 110]
        column_xs = [word["left"] for word in column_words]
        train_types = [word["text"] for word in column_words]
        destinations: list[str] = [""] * len(column_xs)
        if dest_row:
            for word in dest_row:
                if word["left"] <= 110:
                    continue
                column = nearest_column(word["left"], column_xs)
                if column is not None:
                    destinations[column] = word["text"]
        page_trains = [
            {
                "source": source,
                "page": page_num,
                "column": index,
                "trainType": train_types[index] if index < len(train_types) else "普通",
                "headsign": destinations[index] if index < len(destinations) else "",
                "stops": {},
            }
            for index in range(len(column_xs))
        ]
        current_station: str | None = None
        pending_arrival: tuple[list[dict[str, Any]], list[dict[str, Any]]] | None = None

        def apply_row(station_name: str, event: str, row_words: list[dict[str, Any]]) -> None:
            if not station_name or event not in {"着", "発"}:
                return
            for word in row_words:
                hhmm = parse_hhmm(word["text"])
                if not hhmm or word["left"] <= 110:
                    continue
                column = nearest_column(word["left"], column_xs)
                if column is None:
                    continue
                stop = page_trains[column]["stops"].setdefault(
                    station_name,
                    {"stationName": station_name, "arrival": None, "departure": None},
                )
                if event == "着":
                    stop["arrival"] = hhmm
                else:
                    stop["departure"] = hhmm

        for row in rows:
            if not row:
                continue
            y = row[0]["top"]
            if y < 95 or y > 790:
                continue
            if any(word["text"].startswith("ページ") or word["text"] == "###PAGE###" for word in row):
                continue
            left_words = [word for word in row if word["left"] < 112]
            station_words = [
                word["text"]
                for word in left_words
                if word["text"] not in {"着", "発"} and not word["text"].startswith("【") and "ページ" not in word["text"]
            ]
            station_name = "".join(station_words).strip()
            event = next((word["text"] for word in left_words if word["text"] in {"着", "発"}), "")
            has_times = any(parse_hhmm(word["text"]) for word in row if word["left"] > 110)
            if not has_times:
                if station_name:
                    current_station = station_name
                    if pending_arrival:
                        apply_row(current_station, "着", pending_arrival[1])
                        pending_arrival = None
                continue
            if event == "着" and not station_name:
                pending_arrival = (left_words, row)
                continue
            if station_name:
                current_station = station_name
            if event == "発" and not station_name:
                station_name = current_station or ""
            if event == "着" and not station_name and current_station:
                station_name = current_station
            apply_row(station_name, event, row)
        raw_trains.extend(page_trains)
    return raw_trains


def build_train(raw_train: dict[str, Any], physical_index: KeihanPhysicalIndex) -> tuple[dict[str, Any] | None, Counter[str], list[dict[str, Any]]]:
    source = raw_train["source"]
    primary_line = source["primaryLine"]
    stop_rows = [
        stop for stop in raw_train["stops"].values()
        if stop.get("arrival") or stop.get("departure")
    ]
    stop_rows.sort(key=lambda stop: minutes(stop.get("departure") or stop.get("arrival") or "99:99") or 99999)
    if len(stop_rows) < 2:
        return None, Counter(), []
    match_methods: Counter[str] = Counter()
    unmatched: list[dict[str, Any]] = []
    stop_times: list[dict[str, Any]] = []
    for sequence, row in enumerate(stop_rows, start=1):
        station_name = row["stationName"]
        preferred_lines = preferred_lines_for_station(station_name, primary_line)
        match = physical_index.match_stop(station_name, preferred_lines)
        station = physical_index.station_for_match(match)
        if match.get("matched"):
            match_methods[str(match["method"])] += 1
        else:
            match_methods[str(match.get("method") or "unmatched")] += 1
            if len(unmatched) < 25:
                unmatched.append({"stationName": station_name, "sourceKey": source["key"], "primaryLine": primary_line})
        line_name = str(station.get("lineName") if station else preferred_lines[0])
        stop_times.append(
            {
                "sequence": sequence,
                "station_name_raw": station_name,
                "station_id": match.get("stationGroupId"),
                "station_group_id": match.get("stationGroupId"),
                "physical_station_id": match.get("physicalStationId"),
                "operator_name": OPERATOR_NAME,
                "line_id": physical_index.line_id(line_name),
                "line_name": line_name,
                "arrival_hhmm": row.get("arrival"),
                "departure_hhmm": row.get("departure"),
                "match_method": match.get("method"),
            }
        )
    if len(stop_times) < 2:
        return None, match_methods, unmatched
    first_time = stop_times[0].get("departure_hhmm") or stop_times[0].get("arrival_hhmm") or "00:00"
    headsign = raw_train.get("headsign") or stop_times[-1]["station_name_raw"]
    service_name = raw_train.get("trainType") or "普通"
    service_instance_id = f"keihan:{source['key']}:p{raw_train['page']}:c{raw_train['column']}:{first_time.replace(':', '')}"
    train = {
        "train_number": f"{service_name}{first_time.replace(':', '')}",
        "service_instance_id": service_instance_id,
        "source_trip_id": service_instance_id,
        "operator_id": OPERATOR_NAME,
        "operator_name": OPERATOR_NAME,
        "service_name": service_name,
        "service_number": first_time.replace(":", ""),
        "headsign": headsign,
        "train_type": service_name,
        "route_color": physical_index.route_color(primary_line),
        "line_id": physical_index.line_id(primary_line),
        "line_name": primary_line,
        "source_feed_key": SOURCE_FEED_KEY,
        "origin": stop_times[0]["station_name_raw"],
        "destination": headsign,
        "source_timetable_url": source["url"],
        "first_departure_hhmm": first_time,
        "reconstruction_method": "official_all_train_pdf_tsv_columns",
        "stop_times": stop_times,
    }
    return train, match_methods, unmatched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--line-inventory", type=Path, default=DEFAULT_LINE_INVENTORY)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--service-date", default=DEFAULT_SERVICE_DATE)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    physical_index = KeihanPhysicalIndex(load_physical_map(args.physical_map), load_json(args.line_inventory))
    raw_trains: list[dict[str, Any]] = []
    source_errors: list[dict[str, str]] = []
    for source in PDF_SOURCES:
        try:
            fetch_bytes_cached(source["url"], args.cache_dir, args.refresh)
            pdf_path = pdf_cache_path(source["url"], args.cache_dir)
            tsv_path = tsv_for_pdf(pdf_path, args.refresh)
            raw_trains.extend(parse_pdf_table(tsv_path, source))
        except Exception as exc:
            source_errors.append({"sourceKey": source["key"], "url": source["url"], "error": str(exc)})

    trains: list[dict[str, Any]] = []
    match_methods: Counter[str] = Counter()
    unmatched_samples: list[dict[str, Any]] = []
    for raw_train in raw_trains:
        train, methods, unmatched = build_train(raw_train, physical_index)
        match_methods.update(methods)
        unmatched_samples.extend(unmatched)
        if train:
            trains.append(train)

    duplicate_ids = [item for item, count in Counter(train["service_instance_id"] for train in trains).items() if count > 1]
    line_counts = Counter(train["line_name"] for train in trains)
    stop_count_distribution = Counter(str(len(train["stop_times"])) for train in trains)
    audit = {
        "schema": "onichase.v4.keihan_official_train_instances_audit.v1",
        "generatedAt": now_iso(),
        "serviceDate": args.service_date,
        "sourceFeedKey": SOURCE_FEED_KEY,
        "counts": {
            "sourceCount": len(PDF_SOURCES),
            "sourceErrorCount": len(source_errors),
            "rawTrainCount": len(raw_trains),
            "trainInstanceCount": len(trains),
            "stopTimeCount": sum(len(train.get("stop_times") or []) for train in trains),
            "unmatchedSampleCount": len(unmatched_samples),
            "duplicateIdCount": len(duplicate_ids),
        },
        "lineTrainCounts": dict(sorted(line_counts.items())),
        "stopCountDistribution": dict(sorted(stop_count_distribution.items(), key=lambda item: int(item[0]))),
        "matchMethods": dict(sorted(match_methods.items())),
        "duplicateIdSample": duplicate_ids[:20],
        "unmatchedSamples": unmatched_samples[:100],
        "sourceErrors": source_errors,
    }
    payload = {
        "schema": "onichase.v4.train_instances.v1",
        "id": "v4_keihan_official_weekday_train_instances_v0_1",
        "label": "V4 weekday train instances reconstructed from Keihan official all-train PDFs",
        "generatedAt": now_iso(),
        "serviceDate": args.service_date,
        "sourceFeedKey": SOURCE_FEED_KEY,
        "train_instances": sorted(trains, key=lambda item: item["service_instance_id"]),
    }
    write_json(args.output, payload)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(trains)} trains, {audit['counts']['stopTimeCount']} stop_times")
    print(f"Wrote {args.audit_output}: unmatched={len(unmatched_samples)} duplicate_ids={len(duplicate_ids)} source_errors={len(source_errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
