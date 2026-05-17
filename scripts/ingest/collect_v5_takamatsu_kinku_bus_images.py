#!/usr/bin/env python3
"""Collect Kinku Bus official Takamatsu Airport timetable image sources."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MONTH_PAGES = [
    "http://kinkuubus.com/r5-12/",
    "https://kinkuubus.com/R6-10",
    "https://kinkuubus.com/r6-6",
]
INDEX_URL = "https://kinkuubus.com/%E6%89%80%E6%9C%89%E3%83%90%E3%82%B9-2/"
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "takamatsu_kinku"
DEFAULT_OUTPUT = ROOT / "data" / "v5_takamatsu_kinku_official_bus_images.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_takamatsu_kinku_official_bus_images.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_takamatsu_kinku_official_bus_images_audit.json"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str, suffix: str = ".html") -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}{suffix}"


def fetch_bytes(url: str, cache_dir: Path, *, refresh: bool, timeout: int, suffix: str = ".html") -> tuple[bytes, Path, str]:
    path = cache_path_for(cache_dir, url, suffix)
    if path.exists() and not refresh:
        return path.read_bytes(), path, ""
    parsed = urllib.parse.urlsplit(url)
    safe_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, urllib.parse.quote(parsed.path), urllib.parse.quote(parsed.query, safe="=&"), parsed.fragment))
    request = urllib.request.Request(safe_url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        content_type = response.headers.get("content-type", "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data, path, content_type


def image_links(page_url: str, html_text: str) -> list[str]:
    links = []
    seen: set[str] = set()
    for match in re.finditer(r"<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>", html_text, re.S | re.I):
        url = urllib.parse.urljoin(page_url, html.unescape(match.group(1)))
        if url in seen:
            continue
        seen.add(url)
        lowered = url.lower()
        if any(ext in lowered for ext in [".jpg", ".jpeg", ".png", ".webp"]) and "wp-content/uploads" in lowered:
            links.append(url)
    return links


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    pages = []
    image_sources = []
    for page_url in [INDEX_URL, *MONTH_PAGES]:
        try:
            data, page_cache, content_type = fetch_bytes(page_url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
            html_text = data.decode("utf-8", "ignore")
            links = image_links(page_url, html_text)
            pages.append({"sourceUrl": page_url, "cachePath": str(page_cache.relative_to(ROOT)), "status": "ok", "imageCount": len(links), "contentType": content_type})
            for image_url in links:
                suffix = Path(urllib.parse.urlparse(image_url).path).suffix.lower() or ".jpg"
                image_data, image_cache, image_type = fetch_bytes(image_url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout, suffix=suffix)
                image_sources.append({"sourcePageUrl": page_url, "imageUrl": image_url, "cachePath": str(image_cache.relative_to(ROOT)), "contentType": image_type, "byteCount": len(image_data), "status": "cached_image_needs_ocr"})
        except OSError as exc:
            pages.append({"sourceUrl": page_url, "status": "fetch_error", "error": f"{type(exc).__name__}: {exc}", "imageCount": 0})
    status_counts = Counter(item["status"] for item in image_sources)
    source = {
        "schemaVersion": "v5_official_bus_source.takamatsu_kinku_images.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Kinku Bus monthly timetable pages and uploaded timetable images. Images are cached as release source material; OCR or a dedicated image-table parser is required before playable trips can be emitted.",
        "airportIata": "TAK",
        "operatorName": "琴空バス",
        "pages": pages,
        "imageSources": image_sources,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.takamatsu_kinku_images.v1",
        "generatedAt": generated_at,
        "pageCount": len(pages),
        "imageCount": len(image_sources),
        "statusCounts": dict(sorted(status_counts.items())),
        "pages": pages,
        "images": [{k: item[k] for k in ["sourcePageUrl", "imageUrl", "cachePath", "byteCount", "status"]} for item in image_sources],
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
    print(json.dumps({"pageCount": audit["pageCount"], "imageCount": audit["imageCount"], "statusCounts": audit["statusCounts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
