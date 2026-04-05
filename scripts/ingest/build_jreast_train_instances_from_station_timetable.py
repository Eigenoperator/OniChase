#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from parse_jreast_train_detail import parse_html as parse_train_detail_html
from train_instance_normalization import normalize_train_instances


BASE_URL = "https://timetables.jreast.co.jp"
ROOT = Path(__file__).resolve().parents[1]

class AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._current_href = href
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href is not None:
            text = re.sub(r"\s+", " ", "".join(self._text_parts)).strip()
            self.anchors.append({"href": self._current_href, "text": text})
            self._current_href = None
            self._text_parts = []


def fetch_html(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; Codex OniChase Builder)"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {502, 503, 504} or attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def normalize_url(href: str, base_url: str) -> str:
    return urllib.parse.urljoin(base_url, href)


def collect_anchors(html: str) -> list[dict[str, str]]:
    parser = AnchorCollector()
    parser.feed(html)
    return parser.anchors


def extract_train_links_from_timetable_page(html: str, page_url: str) -> list[str]:
    anchors = collect_anchors(html)
    train_links = []
    seen: set[str] = set()
    for anchor in anchors:
        href = anchor["href"]
        if "/train/" not in href:
            continue
        full_url = normalize_url(href, page_url)
        if full_url in seen:
            continue
        seen.add(full_url)
        train_links.append(full_url)
    return train_links


def dedupe_train_instances(train_instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for train in train_instances:
        key = train["train_number"]
        if key not in deduped:
            deduped[key] = train
            continue
        current_len = len(train["stop_times"])
        previous_len = len(deduped[key]["stop_times"])
        if current_len > previous_len:
            deduped[key] = train
    return list(deduped.values())


def parse_direction_and_issue(html: str) -> tuple[str | None, str | None]:
    direction = None
    direction_match = re.search(r"Yamanote Line for (.*?)\s+\((Clockwise|Counterclockwise)\)", html)
    if direction_match:
        direction = direction_match.group(2).lower()
    issue = None
    issue_match = re.search(r"based on ([A-Za-z]+\.?\s+\d{4}) issue", html)
    if issue_match:
        issue = issue_match.group(1)
    return direction, issue


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build train-instance data from one official JR East station timetable page."
    )
    parser.add_argument("--timetable-url", required=True, help="Official JR East weekday timetable page URL.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--stations", required=True, help="Path to the canonical station dataset JSON file.")
    parser.add_argument(
        "--station-name",
        required=True,
        help="Human-readable source station name for metadata only.",
    )
    parser.add_argument(
        "--line-id",
        default="JR_YAMANOTE",
        help="Canonical line or route-family id to record on stop_times. Default: JR_YAMANOTE",
    )
    parser.add_argument(
        "--dataset-id",
        default="train_instances_from_station_timetable_v0_1",
        help="Output dataset id.",
    )
    parser.add_argument(
        "--label",
        default="Train instances built from one JR East station timetable page",
        help="Human-readable output dataset label.",
    )
    args = parser.parse_args()

    stations_data = json.loads(Path(args.stations).read_text(encoding="utf-8"))
    timetable_html = fetch_html(args.timetable_url)
    direction_label, source_issue = parse_direction_and_issue(timetable_html)
    train_links = extract_train_links_from_timetable_page(timetable_html, args.timetable_url)

    raw_instances: list[dict[str, Any]] = []
    source_urls: list[str] = []
    for train_url in train_links:
        source_urls.append(train_url)
        train_html = fetch_html(train_url)
        parsed = parse_train_detail_html(train_html, train_url, line_id=args.line_id)
        raw_instances.extend(parsed["train_instances"])

    normalized_instances, unresolved = normalize_train_instances(raw_instances, stations_data)
    if unresolved:
        unresolved_display = ", ".join(sorted(unresolved))
        raise ValueError(f"Unresolved station names: {unresolved_display}")
    deduped_instances = dedupe_train_instances(normalized_instances)

    output = {
      "id": args.dataset_id,
      "label": args.label,
      "version": "0.1.0",
      "source_station_name": args.station_name,
      "service_day": "weekday",
      "direction_label": direction_label,
      "source_issue": source_issue,
      "source_timetable_url": args.timetable_url,
      "line_id": args.line_id,
      "source_train_urls": source_urls,
      "train_instances": deduped_instances
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Source station: {args.station_name}")
    print(f"Timetable URL: {args.timetable_url}")
    print(f"Train detail pages fetched: {len(train_links)}")
    print(f"Train instances after dedupe: {len(deduped_instances)}")
    print(f"Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
