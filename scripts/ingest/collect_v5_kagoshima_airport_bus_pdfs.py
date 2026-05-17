#!/usr/bin/env python3
"""Collect Kagoshima Airport bus official PDF timetable sources."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE_URL = "https://www.iwasaki-corp.com/kagoshima_kotsu/airport-bus/airport/"
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "kagoshima_airport_pdfs"
DEFAULT_OUTPUT = ROOT / "data" / "v5_kagoshima_airport_official_bus_pdfs.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_kagoshima_airport_official_bus_pdfs.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_kagoshima_airport_official_bus_pdfs_audit.json"


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


def extract_pdf_links(base_url: str, html_text: str) -> list[dict[str, str]]:
    links = []
    seen: set[str] = set()
    for match in re.finditer(r"<a[^>]+href=[\"']([^\"']+\.pdf(?:\?[^\"']*)?)[\"'][^>]*>(.*?)</a>", html_text, re.S | re.I):
        url = urllib.parse.urljoin(base_url, html.unescape(match.group(1)))
        if url in seen:
            continue
        label = re.sub("<.*?>", " ", match.group(2))
        label = re.sub(r"\s+", " ", html.unescape(label)).strip()
        links.append({"label": label, "url": url})
        seen.add(url)
    return links


def pdf_text(path: Path) -> str:
    try:
        result = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=False, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    html_bytes, html_cache, _ = fetch_bytes(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    html_text = html_bytes.decode("utf-8", "ignore")
    pdf_links = extract_pdf_links(SOURCE_URL, html_text)
    pages = []
    for link in pdf_links:
        data, cache_path, content_type = fetch_bytes(link["url"], args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        text = pdf_text(cache_path)
        times = sorted(set(re.findall(r"\b\d{1,2}:\d{2}\b", text)))
        airport_mentions = len(re.findall("鹿児島空港|空港", text))
        status = "pdf_time_text_found" if times else "pdf_cached_no_time_text"
        pages.append(
            {
                **link,
                "status": status,
                "contentType": content_type,
                "cachePath": str(cache_path.relative_to(ROOT)),
                "byteCount": len(data),
                "timeTextCount": len(times),
                "airportMentionCount": airport_mentions,
                "sampleTimes": times[:20],
                "textSample": re.sub(r"\s+", " ", text).strip()[:500],
            }
        )
    status_counts = Counter(page["status"] for page in pages)
    source = {
        "schemaVersion": "v5_official_bus_source.kagoshima_airport_pdfs.v1",
        "generatedAt": generated_at,
        "sourceUrl": SOURCE_URL,
        "sourceCachePath": str(html_cache.relative_to(ROOT)),
        "sourcePolicy": "Official Kagoshima Kotsu airport-bus PDF timetable sources. This pass caches PDFs and extracts text; route normalization is separate.",
        "airportIata": "KOJ",
        "operatorName": "Kagoshima Kotsu",
        "pdfs": pages,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.kagoshima_airport_pdfs.v1",
        "generatedAt": generated_at,
        "pdfCount": len(pages),
        "statusCounts": dict(sorted(status_counts.items())),
        "timeTextPdfCount": status_counts["pdf_time_text_found"],
        "pdfs": pages,
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
    print(json.dumps({"pdfCount": audit["pdfCount"], "timeTextPdfCount": audit["timeTextPdfCount"], "statusCounts": audit["statusCounts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
