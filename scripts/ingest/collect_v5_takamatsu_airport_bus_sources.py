#!/usr/bin/env python3
"""Collect official Takamatsu Airport bus source pages and PDFs."""

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
SOURCE_URL = "https://www.takamatsu-airport.com/access/bus/index.php"
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "takamatsu_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_takamatsu_airport_official_bus_sources.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_takamatsu_airport_official_bus_sources.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_takamatsu_airport_official_bus_sources_audit.json"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str, content_type: str = "") -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    path = urllib.parse.urlparse(url).path.lower()
    suffix = ".pdf" if path.endswith(".pdf") or "pdf" in content_type.lower() else ".html"
    return cache_dir / f"{digest}{suffix}"


def fetch_bytes(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[bytes, Path, str]:
    provisional = cache_path_for(cache_dir, url)
    if provisional.exists() and not refresh:
        content_type = "application/pdf" if provisional.suffix == ".pdf" else "text/html"
        return provisional.read_bytes(), provisional, content_type
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        content_type = response.headers.get("content-type", "")
    path = cache_path_for(cache_dir, url, content_type)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data, path, content_type


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
        url = urllib.parse.urljoin(base_url, html.unescape(match.group(1)))
        label = re.sub("<.*?>", " ", match.group(2))
        label = re.sub(r"\s+", " ", html.unescape(label)).strip()
        if url in seen:
            continue
        seen.add(url)
        lowered = url.lower()
        if "/timetable/" in lowered and "timeschedule" not in lowered:
            continue
        explicit_label = any(token in label for token in ["時刻表", "運賃表", "運行会社ウェブサイト", "バス・飛行機時刻表"])
        official_timetable_asset = "/assets/timeschedule/" in lowered or "/limousine" in lowered
        operator_site = any(domain in lowered for domain in ["kotoden.co.jp", "kotosan.co.jp", "k-sss.com", "yonkoh.co.jp", "kotobus-express.jp", "kinkuubus.com"])
        anchor_only = urllib.parse.urlparse(url)._replace(fragment="").geturl() == base_url
        if (explicit_label or official_timetable_asset or operator_site) and not anchor_only:
            links.append({"label": label, "url": url})
    return links


def pdf_text(path: Path) -> str:
    try:
        completed = subprocess.run(["pdftotext", str(path), "-"], check=False, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout if completed.returncode == 0 else ""


def route_summaries(body: str) -> list[dict[str, Any]]:
    summaries = []
    pattern = re.compile(r"(高松市内方面|琴平方面|綾川・坂出・宇多津・丸亀方面|丸亀・善通寺・観音寺・四国中央方面|阿波池田方面).*?(?=(?:高松市内方面|琴平方面|綾川・坂出・宇多津・丸亀方面|丸亀・善通寺・観音寺・四国中央方面|阿波池田方面)|乗り場案内)", re.S)
    for match in pattern.finditer(body):
        section = match.group(0)
        title = match.group(1)
        operator = re.search(r"運行会社：\s*([^\s]+)", section)
        adult_fares = [int(value.replace(",", "")) for value in re.findall(r"(\d[\d,]*)円", section)]
        summaries.append(
            {
                "routeName": title,
                "operatorName": operator.group(1) if operator else "",
                "sampleFaresYen": adult_fares[:12],
                "hasMonthlyChangeNote": "毎月時刻が変更" in section,
            }
        )
    return summaries


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    data, cache_path, content_type = fetch_bytes(SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    html_text = data.decode("utf-8", "ignore")
    body = plain_text(html_text)
    links = extract_links(SOURCE_URL, html_text)
    source_pages = []
    for link in links:
        try:
            linked_data, linked_cache, linked_type = fetch_bytes(link["url"], args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
            if linked_cache.suffix == ".pdf" or "pdf" in linked_type.lower():
                text = pdf_text(linked_cache)
                times = sorted(set(re.findall(r"\b\d{1,2}[:：]\d{2}\b", text)))
                status = "pdf_time_text_found" if times else "pdf_cached_no_time_text"
            else:
                text = linked_data.decode("utf-8", "ignore")
                page_body = plain_text(text)
                times = sorted(set(re.findall(r"\b\d{1,2}[:：]\d{2}\b", page_body)))
                status = "html_time_text_found" if times else "html_cached_no_time_text"
            source_pages.append({"label": link["label"], "sourceUrl": link["url"], "cachePath": str(linked_cache.relative_to(ROOT)), "contentType": linked_type, "status": status, "timeTextCount": len(times), "sampleTimes": times[:20]})
        except OSError as exc:
            source_pages.append({"label": link["label"], "sourceUrl": link["url"], "status": "fetch_error", "error": f"{type(exc).__name__}: {exc}"})
    status_counts = Counter(page["status"] for page in source_pages)
    source = {
        "schemaVersion": "v5_official_bus_source.takamatsu_airport_sources.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Takamatsu Airport access bus page, linked operator pages, fare summaries, and PDFs. This is source capture; route-specific parsers should promote parseable pages/PDFs into playable trips.",
        "airportIata": "TAK",
        "airportPage": {"sourceUrl": SOURCE_URL, "cachePath": str(cache_path.relative_to(ROOT)), "contentType": content_type},
        "routeSummaries": route_summaries(body),
        "sourcePages": source_pages,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.takamatsu_airport_sources.v1",
        "generatedAt": generated_at,
        "routeSummaryCount": len(source["routeSummaries"]),
        "sourcePageCount": len(source_pages),
        "statusCounts": dict(sorted(status_counts.items())),
        "routeSummaries": source["routeSummaries"],
        "sourcePages": [{k: page.get(k) for k in ["label", "sourceUrl", "status", "timeTextCount"]} for page in source_pages],
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
    print(json.dumps({"routeSummaryCount": audit["routeSummaryCount"], "sourcePageCount": audit["sourcePageCount"], "statusCounts": audit["statusCounts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
