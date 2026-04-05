#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from parse_jrkyushu_train_timetable import parse_html as parse_train_html
from train_instance_normalization import normalize_train_instances


def fetch_html(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Codex OniChase Builder)"})
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


TARGET_SERVICE_NAMES = {
    "SHINKANSEN_KYUSHU": ["みずほ", "さくら", "つばめ"],
    "SHINKANSEN_NISHI_KYUSHU": ["かもめ"],
}


def extract_train_links(html: str, page_url: str, line_id: str) -> list[str]:
    matches = re.finditer(
        r'<td class=back5.*?<a href="(/jr-k_time/\d{4}/\d{4}/\d+\.html\?c=\d+&ym=\d+&d=\d+)".*?</td>',
        html,
        re.DOTALL,
    )
    deduped: list[str] = []
    seen: set[str] = set()
    targets = TARGET_SERVICE_NAMES.get(line_id, [])
    for match in matches:
        link = match.group(1)
        snippet = match.group(0)
        if targets and not any(name in snippet for name in targets):
            continue
        full = urllib.parse.urljoin(page_url, link)
        if full in seen:
            continue
        seen.add(full)
        deduped.append(full)
    return deduped


def dedupe_train_instances(train_instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for train in train_instances:
        key = train["train_number"]
        current = merged.get(key)
        if current is None or len(train["stop_times"]) > len(current["stop_times"]):
            merged[key] = train
    return list(merged.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Build train instances from a JR Kyushu station timetable page.")
    parser.add_argument("--timetable-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stations", required=True)
    parser.add_argument("--station-name", required=True)
    parser.add_argument("--line-id", default="SHINKANSEN_KYUSHU")
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--service-day", default="weekday")
    parser.add_argument("--train-type-filter", default="新幹線")
    args = parser.parse_args()

    stations_data = json.loads(Path(args.stations).read_text(encoding="utf-8"))
    timetable_html = fetch_html(args.timetable_url)
    train_links = extract_train_links(timetable_html, args.timetable_url, args.line_id)

    raw_instances: list[dict[str, Any]] = []
    kept_urls: list[str] = []
    for train_url in train_links:
        train_html = fetch_html(train_url)
        parsed = parse_train_html(train_html, train_url, args.line_id)
        for train in parsed["train_instances"]:
            if args.train_type_filter and train.get("train_type") and args.train_type_filter not in str(train.get("train_type", "")):
                continue
            raw_instances.append(train)
            kept_urls.append(train_url)
        if len(kept_urls) % 25 == 0:
            print(f"Fetched {len(kept_urls)} JR Kyushu train pages...", flush=True)

    normalized_instances, unresolved = normalize_train_instances(raw_instances, stations_data)
    if unresolved:
        unresolved_display = ", ".join(sorted(unresolved))
        raise ValueError(f"Unresolved station names: {unresolved_display}")

    deduped = dedupe_train_instances(normalized_instances)
    output = {
        "id": args.dataset_id,
        "label": args.label,
        "version": "0.1.0",
        "source_station_name": args.station_name,
        "service_day": args.service_day,
        "source_timetable_url": args.timetable_url,
        "line_id": args.line_id,
        "source_train_urls": kept_urls,
        "train_instances": deduped,
    }

    out = Path(args.output)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Train detail pages fetched: {len(train_links)}")
    print(f"Train instances after dedupe: {len(deduped)}")
    print(f"Wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
