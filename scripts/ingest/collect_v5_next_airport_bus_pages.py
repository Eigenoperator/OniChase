#!/usr/bin/env python3
"""Collect official bus source pages for the next airport-bus backlog batch."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "next_airport_pages"
DEFAULT_OUTPUT = ROOT / "data" / "v5_next_airport_bus_pages.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_next_airport_bus_pages.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_next_airport_bus_pages_audit.json"

AIRPORTS = [
    {
        "iata": "KOJ",
        "name": "Kagoshima Airport",
        "urls": [
            "https://www.koj-ab.co.jp/en/ground-transportation/public-transportation-bus.html",
            "https://www.iwasaki-corp.com/bus/airport/",
        ],
    },
    {
        "iata": "KMI",
        "name": "Miyazaki Airport",
        "urls": ["https://www.miyazaki-airport.co.jp/access/bus"],
    },
    {
        "iata": "UKB",
        "name": "Kobe Airport",
        "urls": [
            "https://www.kairport.co.jp/access/from-airport/bus",
            "https://www.shinkibus.co.jp/bus/cityloop/time/",
            "https://navi.shinkibus.jp/jikoku/timetable?tcode=74050&pcode=5&generation=2026-04-01",
            "https://timetable.nishinihonjrbus.co.jp/timeline/2-2-D-1Tokushima.html",
            "https://www.kobe-minato.co.jp/route61.html#timetable",
        ],
    },
    {
        "iata": "ISG",
        "name": "New Ishigaki Airport",
        "urls": [
            "https://www.ishigaki-airport.co.jp/en/access/bus-taxi/index.html",
            "https://karrykanko.com/ishigaki/",
        ],
    },
]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    suffix = ".pdf" if urllib.parse.urlparse(url).path.lower().endswith(".pdf") else ".html"
    return cache_dir / f"{digest}{suffix}"


def fetch_bytes(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[bytes, Path, str]:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        content_type = "application/pdf" if path.suffix == ".pdf" else "text/html"
        return path.read_bytes(), path, content_type
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        content_type = response.headers.get("content-type", "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data, path, content_type


def text_from_bytes(data: bytes, content_type: str, path: Path) -> str:
    if path.suffix == ".pdf" or "pdf" in content_type.lower():
        return ""
    return data.decode("utf-8", "ignore")


def plain_text(html_text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html_text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_links(base_url: str, html_text: str) -> list[dict[str, str]]:
    links = []
    seen: set[str] = set()
    for match in re.finditer(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html_text, re.S | re.I):
        href = html.unescape(match.group(1))
        label = re.sub("<.*?>", " ", match.group(2))
        label = re.sub(r"\s+", " ", html.unescape(label)).strip()
        url = urllib.parse.urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        if any(token in url.lower() for token in ["bus", "time", "pdf", "access", "route", "交通", "時刻"]):
            links.append({"label": label, "url": url})
    return links[:80]


def page_record(airport: dict[str, Any], url: str, args: argparse.Namespace) -> dict[str, Any]:
    try:
        data, cache_path, content_type = fetch_bytes(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    except (OSError, urllib.error.URLError) as exc:
        return {"iata": airport["iata"], "url": url, "status": "fetch_error", "error": f"{type(exc).__name__}: {exc}"}
    text = text_from_bytes(data, content_type, cache_path)
    body = plain_text(text) if text else ""
    times = sorted(set(re.findall(r"\b\d{1,2}:\d{2}\b", body)))
    links = extract_links(url, text) if text else []
    if cache_path.suffix == ".pdf" or "pdf" in content_type.lower():
        status = "pdf_cached_needs_pdf_parser"
    elif times:
        status = "time_text_found"
    else:
        status = "fetched_no_time_text"
    return {
        "iata": airport["iata"],
        "airportName": airport["name"],
        "url": url,
        "status": status,
        "contentType": content_type,
        "cachePath": str(cache_path.relative_to(ROOT)),
        "timeTextCount": len(times),
        "sampleTimes": times[:20],
        "candidateLinkCount": len(links),
        "candidateLinks": links,
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    pages = []
    for airport in AIRPORTS:
        for url in airport["urls"]:
            pages.append(page_record(airport, url, args))
    status_counts = Counter(page["status"] for page in pages)
    source = {
        "schemaVersion": "v5_official_bus_source.next_airport_pages.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official airport/operator bus pages for the next backlog batch. Pages are cached and classified; dedicated timetable parsers should be added per operator.",
        "airports": AIRPORTS,
        "pages": pages,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.next_airport_pages.v1",
        "generatedAt": generated_at,
        "airportCount": len(AIRPORTS),
        "pageCount": len(pages),
        "statusCounts": dict(sorted(status_counts.items())),
        "timeTextPageCount": status_counts["time_text_found"],
        "pages": pages,
    }
    return source, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    source, audit = collect(args)
    write_json(args.output, source)
    write_json(args.docs_output, source)
    write_json(args.audit_output, audit)
    print(json.dumps({"airportCount": audit["airportCount"], "pageCount": audit["pageCount"], "timeTextPageCount": audit["timeTextPageCount"], "statusCounts": audit["statusCounts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
