#!/usr/bin/env python3
"""Collect official Ishigaki Airport bus sources."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import ssl
import subprocess
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AIRPORT_PAGE = "https://www.ishigaki-airport.co.jp/access/bus-taxi/index.html"
KARRY_URL = "https://karrykanko.com/ishigaki/"
AZUMA_URL = "https://www.azumabus.co.jp/"
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "ishigaki_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_ishigaki_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_ishigaki_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_ishigaki_airport_official_bus_audit.json"


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
    context = ssl._create_unverified_context() if "azumabus.co.jp" in url else None
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        data = response.read()
        content_type = response.headers.get("content-type", "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data, path, content_type


def fetch_text(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[str, Path]:
    data, path, _content_type = fetch_bytes(url, cache_dir, refresh=refresh, timeout=timeout)
    return data.decode("utf-8", "ignore"), path


def plain_text(html_text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html_text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def azuma_pdf_links(html_text: str) -> list[dict[str, str]]:
    links = []
    seen: set[str] = set()
    for match in re.finditer(r"<a[^>]+href=[\"']([^\"']+\.pdf)[\"'][^>]*>(.*?)</a>", html_text, re.S | re.I):
        url = urllib.parse.urljoin(AZUMA_URL, html.unescape(match.group(1)))
        if url in seen:
            continue
        seen.add(url)
        label = re.sub("<.*?>", " ", match.group(2))
        label = re.sub(r"\s+", " ", html.unescape(label)).strip()
        if any(token in label for token in ["空港", "Airport", "広域", "路線図", "時刻表"]):
            links.append({"label": label, "url": url})
    return links


def pdf_text(path: Path) -> str:
    try:
        completed = subprocess.run(["pdftotext", str(path), "-"], check=False, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout if completed.returncode == 0 else ""


def parse_hour_blocks(body: str, heading: str) -> list[str]:
    start = body.find(heading)
    if start < 0:
        return []
    end_candidates = [body.find(next_heading, start + len(heading)) for next_heading in ["石垣空港発 時刻表", "石垣港離島ターミナル発 時刻表", "カリー観光石垣営業所"] if body.find(next_heading, start + len(heading)) > 0]
    end = min(end_candidates) if end_candidates else len(body)
    segment = body[start:end]
    times = []
    for hour_match in re.finditer(r"(\d{1,2})時\s+([^時]+?)(?=\s+\d{1,2}時|$)", segment):
        hour = int(hour_match.group(1))
        minutes = re.findall(r"(?<!\d)(\d{1,2})(?!\d)", hour_match.group(2))
        for minute in minutes:
            value = int(minute)
            if 0 <= value < 60:
                times.append(f"{hour:02d}:{value:02d}")
    return times


def parse_karry_route(html_text: str, cache_path: Path) -> dict[str, Any]:
    body = plain_text(html_text)
    airport_departures = parse_hour_blocks(body, "石垣空港発 時刻表")
    terminal_departures = parse_hour_blocks(body, "石垣港離島ターミナル発 時刻表")
    fare_match = re.search(r"片道運賃\s+大人：(\d+)円\s+小人：(\d+)円", body)
    adult_fare = int(fare_match.group(1)) if fare_match else 550
    child_fare = int(fare_match.group(2)) if fare_match else 280
    trips = []
    for index, departure in enumerate(airport_departures, start=1):
        hour, minute = map(int, departure.split(":"))
        arrival_minutes = hour * 60 + minute + 30
        trips.append(
            {
                "tripId": f"isg_karry:from_airport:{index:03d}",
                "direction": "from_airport",
                "stopTimes": [
                    {"stopName": "石垣空港", "time": departure},
                    {"stopName": "石垣港離島ターミナル", "time": f"{arrival_minutes // 60:02d}:{arrival_minutes % 60:02d}"},
                ],
            }
        )
    for index, departure in enumerate(terminal_departures, start=1):
        hour, minute = map(int, departure.split(":"))
        arrival_minutes = hour * 60 + minute + 30
        trips.append(
            {
                "tripId": f"isg_karry:to_airport:{index:03d}",
                "direction": "to_airport",
                "stopTimes": [
                    {"stopName": "石垣港離島ターミナル", "time": departure},
                    {"stopName": "石垣空港", "time": f"{arrival_minutes // 60:02d}:{arrival_minutes % 60:02d}"},
                ],
            }
        )
    return {
        "sourceKind": "official_karry_html_timetable",
        "operatorName": "カリー観光",
        "airportIata": "ISG",
        "routeCode": "isg_karry_direct",
        "routeName": "石垣空港 ⇔ 石垣港離島ターミナル直行バス",
        "sourceUrl": KARRY_URL,
        "cachePath": str(cache_path.relative_to(ROOT)),
        "adultFareYen": adult_fare,
        "childFareYen": child_fare,
        "routeStopNames": ["石垣空港", "石垣港離島ターミナル"],
        "trips": trips,
        "tripCount": len(trips),
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    airport_html, airport_cache = fetch_text(AIRPORT_PAGE, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    karry_html, karry_cache = fetch_text(KARRY_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    azuma_html, azuma_cache = fetch_text(AZUMA_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    routes = [parse_karry_route(karry_html, karry_cache)]
    pdf_sources = []
    for link in azuma_pdf_links(azuma_html):
        _data, path, content_type = fetch_bytes(link["url"], args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        text = pdf_text(path)
        times = sorted(set(re.findall(r"\b\d{1,2}:\d{2}\b", text)))
        pdf_sources.append(
            {
                "label": link["label"],
                "sourceUrl": link["url"],
                "cachePath": str(path.relative_to(ROOT)),
                "contentType": content_type,
                "status": "pdf_time_text_found" if times else "pdf_cached_no_time_text",
                "timeTextCount": len(times),
                "sampleTimes": times[:20],
            }
        )
    status_counts = Counter(source["status"] for source in pdf_sources)
    source = {
        "schemaVersion": "v5_official_bus_source.ishigaki_airport.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Ishigaki Airport bus sources. Karry Kanko direct-bus HTML is normalized into trips; Azuma Bus PDFs are cached as official timetable sources and need a dedicated PDF table parser before full route normalization.",
        "airportPage": {"sourceUrl": AIRPORT_PAGE, "cachePath": str(airport_cache.relative_to(ROOT)), "candidateTimeTextCount": len(re.findall(r"\b\d{1,2}:\d{2}\b", plain_text(airport_html)))},
        "azumaIndexPage": {"sourceUrl": AZUMA_URL, "cachePath": str(azuma_cache.relative_to(ROOT)), "pdfCount": len(pdf_sources)},
        "azumaPdfSources": pdf_sources,
        "routes": routes,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.ishigaki_airport.v1",
        "generatedAt": generated_at,
        "routeCount": len(routes),
        "tripCount": sum(route["tripCount"] for route in routes),
        "azumaPdfCount": len(pdf_sources),
        "azumaPdfStatusCounts": dict(sorted(status_counts.items())),
        "routes": [{"routeCode": route["routeCode"], "tripCount": route["tripCount"], "adultFareYen": route["adultFareYen"]} for route in routes],
        "azumaPdfSources": [{k: source[k] for k in ["label", "status", "timeTextCount", "sourceUrl"]} for source in pdf_sources],
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
    print(json.dumps({"routeCount": audit["routeCount"], "tripCount": audit["tripCount"], "azumaPdfCount": audit["azumaPdfCount"], "azumaPdfStatusCounts": audit["azumaPdfStatusCounts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
