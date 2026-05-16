#!/usr/bin/env python3
"""Collect official Osaka Itami airport-bus linked timetable pages."""

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
INDEX_URL = "https://www.osaka-airport.co.jp/en/access/from-airport/bus"
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "itm_linked_pages"
DEFAULT_OUTPUT = ROOT / "data" / "v5_itm_official_bus_pages.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_itm_official_bus_pages.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_itm_official_bus_pages_audit.json"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.html"


def fetch_text(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[str, Path]:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8"), path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", "ignore")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text, path


def plain_text(html_text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html_text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_index(html_text: str) -> list[dict[str, str]]:
    links = []
    seen: set[str] = set()
    for match in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", html_text, re.S):
        href = html.unescape(match.group(1))
        url = urllib.parse.urljoin(INDEX_URL, href)
        if url in seen:
            continue
        label = re.sub("<.*?>", " ", match.group(2))
        label = re.sub(r"\s+", " ", html.unescape(label)).strip()
        host = urllib.parse.urlparse(url).netloc
        if not label or host in {"www.osaka-airport.co.jp", "osaka-airport.co.jp"}:
            continue
        if any(token in url.lower() for token in ["facebook", "youtube", "instagram", "linkedin", "x.com"]):
            continue
        if label.lower() in {"english", "train", "limousine bus", "group bus", "taxi"}:
            continue
        links.append({"label": label, "url": url, "host": host})
        seen.add(url)
    return links


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    index_html, index_cache = fetch_text(INDEX_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    candidates = parse_index(index_html)
    pages = []
    for link in candidates:
        try:
            text, cache_path = fetch_text(link["url"], args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
            body = plain_text(text)
            times = sorted(set(re.findall(r"\b\d{1,2}:\d{2}\b", body)))
            status = "time_text_found" if times else "fetched_no_time_text"
            pages.append(
                {
                    **link,
                    "status": status,
                    "cachePath": str(cache_path.relative_to(ROOT)),
                    "timeTextCount": len(times),
                    "sampleTimes": times[:12],
                }
            )
        except (OSError, urllib.error.URLError) as exc:
            pages.append({**link, "status": "fetch_error", "error": f"{type(exc).__name__}: {exc}"})
    status_counts = Counter(page["status"] for page in pages)
    source = {
        "schemaVersion": "v5_official_bus_source.itm_linked_pages.v1",
        "generatedAt": generated_at,
        "sourceIndexUrl": INDEX_URL,
        "sourceIndexCachePath": str(index_cache.relative_to(ROOT)),
        "sourcePolicy": "Official Osaka Itami airport access page plus linked operator timetable pages. This source layer records linked pages; per-operator timetable normalization is separate.",
        "airportIata": "ITM",
        "pages": pages,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.itm_linked_pages.v1",
        "generatedAt": generated_at,
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
    print(json.dumps({"pageCount": audit["pageCount"], "timeTextPageCount": audit["timeTextPageCount"], "statusCounts": audit["statusCounts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
