#!/usr/bin/env python3
"""Collect official airport-bus source indexes for priority airports."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "airport_source_index"
DEFAULT_OUTPUT = ROOT / "data" / "v5_airport_bus_official_source_index.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_airport_bus_official_source_index.json"

SOURCES = [
    {
        "iata": "HND",
        "airportName": "Tokyo Haneda Airport",
        "url": "https://tokyo-haneda.com/en/access/bus/index.html",
        "sourceName": "Haneda Airport Passenger Terminal",
    },
    {
        "iata": "CTS",
        "airportName": "New Chitose Airport",
        "url": "https://www.hokkaido-airports.com/en/new-chitose/access/bus/",
        "sourceName": "Hokkaido Airports New Chitose",
    },
    {
        "iata": "ITM",
        "airportName": "Osaka Itami Airport",
        "url": "https://www.osaka-airport.co.jp/en/access/from-airport/bus",
        "sourceName": "Osaka Itami Airport",
    },
    {
        "iata": "KIX",
        "airportName": "Kansai International Airport",
        "url": "https://www.kansai-airport.or.jp/en/access/from-airport/bus",
        "sourceName": "Kansai International Airport",
    },
]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_text(url: str, cache_dir: Path, *, refresh: bool = False) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"
    if cache_path.exists() and not refresh:
        return cache_path.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={"User-Agent": "OniChase-v5-airport-bus-source-index/0.1"})
    with urllib.request.urlopen(req, timeout=30) as response:
        text = response.read().decode("utf-8", "replace")
    cache_path.write_text(text, encoding="utf-8")
    return text


def clean_text(value: str) -> str:
    value = re.sub(r"<script.*?</script>", " ", value, flags=re.S | re.I)
    value = re.sub(r"<style.*?</style>", " ", value, flags=re.S | re.I)
    value = re.sub(r"<.*?>", " ", value, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def extract_links(page_html: str, base_url: str) -> list[dict[str, str]]:
    links = []
    seen = set()
    for match in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page_html, flags=re.S | re.I):
        href = html.unescape(match.group(1)).strip()
        label = clean_text(match.group(2))
        if not href or href.startswith("#") or not label:
            continue
        absolute = urllib.parse.urljoin(base_url, href)
        lowered = f"{absolute} {label}".lower()
        if not any(token in lowered for token in ["bus", "timetable", "limousine", "airport", "kanku", "kate", "chuo", "hokto", "keikyu", "hankyu"]):
            continue
        key = (absolute, label)
        if key in seen:
            continue
        seen.add(key)
        links.append({"label": label, "url": absolute})
    return links


def route_like_links(links: list[dict[str, str]]) -> list[dict[str, str]]:
    output = []
    for link in links:
        text = f"{link['label']} {link['url']}"
        if any(token in text for token in ["/timetable/detail/", "View the timetable", "Sta.", "Station", "Airport", "Kansai", "Sapporo", "Osaka", "Kyoto", "Kobe", "Nara", "Haneda"]):
            output.append(link)
    return output


def collect_source(source: dict[str, str], cache_dir: Path, refresh: bool) -> dict[str, Any]:
    page_html = fetch_text(source["url"], cache_dir, refresh=refresh)
    links = extract_links(page_html, source["url"])
    route_links = route_like_links(links)
    return {
        **source,
        "sourceKind": "official_airport_access_page",
        "linkCount": len(links),
        "routeCandidateCount": len(route_links),
        "links": links,
        "routeCandidates": route_links,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--refresh-cache", action="store_true")
    args = parser.parse_args()

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    airports = [collect_source(source, args.cache_dir, args.refresh_cache) for source in SOURCES]
    payload = {
        "schemaVersion": "v5_airport_bus_official_source_index.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official airport access pages and linked operator timetable pages. This is an index for parser work, not merged gameplay data.",
        "airports": airports,
        "summary": {
            "airportCount": len(airports),
            "linkCount": sum(item["linkCount"] for item in airports),
            "routeCandidateCount": sum(item["routeCandidateCount"] for item in airports),
        },
    }
    write_json(args.output, payload)
    write_json(args.docs_output, payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
