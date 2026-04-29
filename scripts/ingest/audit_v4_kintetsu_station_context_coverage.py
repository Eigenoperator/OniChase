#!/usr/bin/env python3
"""Audit Kintetsu T5 station-page departures against collected T7 train details.

Kintetsu T7 detail pages are station-context sensitive: the same tx/dw train
can render only the downstream stops from the source station (`sf`) used in the
T5 timetable link.  This audit catches cases where the collector deduped a
train by tx/dw using a different station context, so a station-page departure is
present in T5 but the collected train instance no longer contains that station.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from collect_v4_kintetsu_official_train_instances import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    DEFAULT_OUTPUT,
    KINTETSU_TIMETABLE_JSON_URL,
    cache_path,
    canonical_t7_from_href,
    decode_html,
    extract_t7_links,
)


DEFAULT_AUDIT = ROOT / "data" / "v4_kintetsu_station_context_coverage_audit.json"


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_cached_timetable_entries(cache_dir: Path) -> list[dict[str, Any]]:
    path = cache_path(cache_dir, "json", KINTETSU_TIMETABLE_JSON_URL, ".json")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return [item for item in data if item.get("曜日") == "平日" and item.get("URL")]


def cached_t5_html(cache_dir: Path, url: str) -> str | None:
    path = cache_path(cache_dir, "t5", url, ".html")
    if not path.exists():
        return None
    return decode_html(path.read_bytes())


def train_key_from_link(href: str, page_url: str) -> str | None:
    canonical = canonical_t7_from_href(href, page_url)
    return canonical[0] if canonical else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--trains", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--sample-limit", type=int, default=120)
    args = parser.parse_args()

    entries = load_cached_timetable_entries(args.cache_dir)
    trains_payload = load_json(args.trains)
    train_by_key = {
        str(train.get("source_trip_id") or ""): train
        for train in trains_payload["train_instances"]
    }

    missing_context_samples: list[dict[str, Any]] = []
    missing_train_samples: list[dict[str, Any]] = []
    missing_by_station_direction: Counter[str] = Counter()
    checked_departures = 0
    missing_context_count = 0
    missing_train_count = 0
    page_count = 0
    uncached_page_count = 0
    page_link_counts: Counter[str] = Counter()

    for entry in entries:
        page_url = str(entry["URL"])
        station_name = str(entry.get("駅名") or "")
        line_name = str(entry.get("路線名") or "")
        direction_name = str(entry.get("方面名") or "")
        page_key = f"{station_name}|{line_name}|{direction_name}"
        page_html = cached_t5_html(args.cache_dir, page_url)
        if page_html is None:
            uncached_page_count += 1
            continue
        page_count += 1
        links = extract_t7_links(page_html, page_url)
        page_link_counts[page_key] += len(links)
        for key, _url in links:
            checked_departures += 1
            train = train_by_key.get(key)
            if not train:
                missing_train_count += 1
                if len(missing_train_samples) < args.sample_limit:
                    missing_train_samples.append({
                        "station": station_name,
                        "line": line_name,
                        "direction": direction_name,
                        "trainKey": key,
                        "pageUrl": page_url,
                    })
                continue
            stop_names = [
                str(stop.get("station_name_raw") or stop.get("station_name") or "")
                for stop in train.get("stop_times") or []
            ]
            if station_name not in stop_names:
                missing_context_count += 1
                missing_by_station_direction[page_key] += 1
                if len(missing_context_samples) < args.sample_limit:
                    missing_context_samples.append({
                        "station": station_name,
                        "line": line_name,
                        "direction": direction_name,
                        "trainKey": key,
                        "serviceInstanceId": train.get("service_instance_id"),
                        "serviceName": train.get("service_name"),
                        "headsign": train.get("headsign"),
                        "collectedFirstStop": stop_names[0] if stop_names else "",
                        "collectedLastStop": stop_names[-1] if stop_names else "",
                        "collectedStopSample": stop_names[:12],
                        "pageUrl": page_url,
                        "sourceUrl": train.get("source_url"),
                    })

    missing_station_directions = []
    for key, missing_count in missing_by_station_direction.most_common():
        total = page_link_counts.get(key, 0)
        station, line, direction = key.split("|", 2)
        missing_station_directions.append({
            "station": station,
            "line": line,
            "direction": direction,
            "missingContextCount": missing_count,
            "pageDepartureLinkCount": total,
            "missingContextRate": round(missing_count / total, 4) if total else None,
        })

    output = {
        "schema": "onichase.v4.kintetsu_station_context_coverage_audit.v1",
        "inputs": {
            "cacheDir": str(args.cache_dir),
            "trains": str(args.trains),
        },
        "summary": {
            "cachedTimetablePageCount": page_count,
            "uncachedTimetablePageCount": uncached_page_count,
            "checkedStationPageDepartureLinks": checked_departures,
            "missingTrainCount": missing_train_count,
            "missingStationContextCount": missing_context_count,
            "stationDirectionWithMissingContextCount": len(missing_by_station_direction),
        },
        "missingStationDirections": missing_station_directions,
        "missingStationContextSamples": missing_context_samples,
        "missingTrainSamples": missing_train_samples,
    }
    write_json(args.output, output)
    print(
        f"Wrote {args.output}: checked={checked_departures} "
        f"missing_context={missing_context_count} missing_trains={missing_train_count}"
    )
    return 1 if missing_context_count or missing_train_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
