#!/usr/bin/env python3
"""Collect MLIT scheduled passenger/ferry operator discovery data.

This does not make ship routes playable. It snapshots the national discovery
baseline so the ship backlog can be checked against every MLIT-listed scheduled
operator with an official web source.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen
from zoneinfo import ZoneInfo


SOURCE_URL = "https://www.mlit.go.jp/maritime/bosai_shipslink.html"
OUT = Path("data/v5_ship_mlit_discovery.json")
REGION_RE = re.compile(r'<a name="[^"]+"><strong>([^<]+)</strong></a>')
ENTRY_RE = re.compile(
    r'<a href="(?P<href>[^"]+)"[^>]*>(?P<operator>.*?)</a>'
    r'(?P<suffix>.*?)〔(?P<route>.*?)〕',
)
TAG_RE = re.compile(r"<[^>]+>")


EXCLUDE_OPERATORS = {
    "▲トップに戻る",
    "北海道",
    "東北",
    "関東",
    "北陸信越",
    "中部",
    "近畿",
    "神戸",
    "中国",
    "四国",
    "九州",
    "沖縄",
}


def clean(value: str) -> str:
    value = TAG_RE.sub("", value)
    value = unescape(value)
    value = value.replace("\u3000", " ")
    value = value.replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def classify(operator: str, route: str, suffix: str) -> str:
    text = f"{operator} {route} {suffix}"
    if any(token in text for token in ["水上バス", "遊覧船", "海賊船", "観光船"]):
        return "review_transport_or_sightseeing"
    if any(token in text for token in ["フェリー", "汽船", "海運", "商船", "ライン", "渡船", "航路"]):
        return "scheduled_public_candidate"
    if any(token in text for token in ["市", "町", "村", "県"]):
        return "municipal_scheduled_candidate"
    return "scheduled_public_candidate"


def main() -> None:
    html = urlopen(SOURCE_URL, timeout=30).read().decode("utf-8")
    region = None
    entries = []
    seen = set()
    for raw_line in html.splitlines():
        region_match = REGION_RE.search(raw_line)
        if region_match:
            region = clean(region_match.group(1))
            continue
        match = ENTRY_RE.search(raw_line)
        if not match:
            continue
        operator = clean(match.group("operator"))
        if operator in EXCLUDE_OPERATORS:
            continue
        suffix = clean(match.group("suffix"))
        route = clean(match.group("route"))
        href = urljoin(SOURCE_URL, unescape(match.group("href")))
        key = (region, operator, route, href)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "region": region or "unknown",
                "operator": operator,
                "routeText": route,
                "url": href,
                "mlitSuffix": suffix,
                "candidateClass": classify(operator, route, suffix),
                "playableStatus": "discovery_only",
            }
        )

    generated_at = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")
    by_region = {}
    by_class = {}
    for entry in entries:
        by_region[entry["region"]] = by_region.get(entry["region"], 0) + 1
        by_class[entry["candidateClass"]] = by_class.get(entry["candidateClass"], 0) + 1
    payload = {
        "schema": "onichase.v5.ship.mlitDiscovery.v1",
        "sourceUrl": SOURCE_URL,
        "generatedAt": generated_at,
        "entryCount": len(entries),
        "byRegion": by_region,
        "byCandidateClass": by_class,
        "notes": [
            "MLIT lists scheduled routes with an operator web page, grouped by operator location rather than exact departure region.",
            "This file is a national discovery baseline; official timetable, calendar, fare, coordinates, and connectors are still required before playable promotion.",
            "review_transport_or_sightseeing entries must be manually reviewed before collection.",
        ],
        "items": entries,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT} entryCount={payload['entryCount']} "
        f"classes={payload['byCandidateClass']} generatedAt={generated_at}"
    )


if __name__ == "__main__":
    main()
