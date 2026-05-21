#!/usr/bin/env python3
"""Probe skipped V5 ship sources for timetable/fare parseability.

This does not promote gameplay data by itself. It only downloads official
source pages already attached to the route inventory and records whether the
source appears to contain explicit HH:MM times and yen fare signals.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = ROOT / "data/v5_ship_playable_promotion_audit.json"
SOURCE_FILES = [
    ROOT / "data/v5_ship_seikan_ferry_official.json",
    ROOT / "data/v5_ship_priority_batch_official.json",
    ROOT / "data/v5_ship_long_distance_batch_official.json",
    ROOT / "data/v5_ship_expansion_to_70_official.json",
    ROOT / "data/v5_ship_expansion_150_map_batch1_official.json",
    ROOT / "data/v5_ship_map_to_193_official.json",
    ROOT / "data/v5_ship_playable_400_batch_official.json",
    ROOT / "data/v5_ship_playable_500_batch_official.json",
]
OUT_PATH = ROOT / "data/v5_ship_source_parse_candidates.json"
CACHE_DIR = ROOT / "data/v5_ship_source_probe_cache"

TIME_RE = re.compile(r"(?<!\d)(?:[01]?\d|2[0-9])[:：][0-5]\d(?!\d)")
YEN_RE = re.compile(r"(?:¥|￥|円|運賃|旅客|大人|片道|料金)")
PDF_RE = re.compile(r"\.pdf(?:$|[?#])", re.IGNORECASE)


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def route_sources(route: dict) -> list[str]:
    urls = list(route.get("sourceUrls") or [])
    fare_urls = (route.get("fare") or {}).get("sourceUrls") or []
    urls.extend(fare_urls)
    for pattern in route.get("servicePatterns") or []:
        urls.extend(pattern.get("sourceUrls") or [])
    return sorted({url for url in urls if isinstance(url, str) and url.startswith(("http://", "https://"))})


def cache_name(url: str) -> str:
    parsed = urlparse(url)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{parsed.netloc}{parsed.path}")[:180]
    suffix = ".pdf" if PDF_RE.search(url) else ".html"
    return slug.rstrip("._-") + suffix


def fetch(url: str) -> tuple[str, str | None]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / cache_name(url)
    if not path.exists() or path.stat().st_size == 0:
        try:
            subprocess.run(
                ["curl", "-L", "--max-time", "20", "--retry", "1", "-A", "OniChaseSourceAudit/1.0", "-o", str(path), url],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as exc:
            return "", f"curl_failed:{exc.returncode}"
    if PDF_RE.search(url) or path.suffix.lower() == ".pdf":
        try:
            text = subprocess.check_output(["pdftotext", "-layout", str(path), "-"], stderr=subprocess.DEVNULL, timeout=20)
            return text.decode("utf-8", errors="ignore"), None
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return "", f"pdf_text_failed:{type(exc).__name__}"
    return path.read_text(encoding="utf-8", errors="ignore"), None


def main() -> None:
    audit = read_json(AUDIT_PATH)
    skipped_ids = {item["routeId"] for item in audit.get("skippedRoutes", [])}
    routes_by_id: dict[str, dict] = {}
    for source_path in SOURCE_FILES:
        if not source_path.exists():
            continue
        payload = read_json(source_path)
        for route in payload.get("routes") or []:
            route_id = route.get("routeId")
            if route_id in skipped_ids:
                routes_by_id[route_id] = route

    grouped: dict[str, dict] = {}
    for route_id, route in routes_by_id.items():
        urls = route_sources(route)
        if not urls:
            urls = ["NO_SOURCE_URL"]
        primary = urls[0]
        group = grouped.setdefault(primary, {
            "sourceUrl": primary,
            "operatorSet": set(),
            "routeIds": [],
            "routes": [],
            "allSourceUrls": set(),
        })
        group["operatorSet"].add(str(route.get("operator") or ""))
        group["routeIds"].append(route_id)
        group["routes"].append({
            "routeId": route_id,
            "operator": route.get("operator"),
            "origin": route.get("origin"),
            "destination": route.get("destination"),
        })
        group["allSourceUrls"].update(urls)

    source_groups = []
    for primary, group in sorted(grouped.items(), key=lambda item: (-len(item[1]["routeIds"]), item[0])):
        probe_urls = [url for url in sorted(group["allSourceUrls"]) if url != "NO_SOURCE_URL"][:3]
        combined_text = ""
        errors = []
        for url in probe_urls:
            text, error = fetch(url)
            if error:
                errors.append({"url": url, "error": error})
            combined_text += "\n" + text[:400000]
        time_count = len(TIME_RE.findall(combined_text))
        fare_signal_count = len(YEN_RE.findall(combined_text))
        source_groups.append({
            "sourceUrl": primary,
            "allSourceUrls": sorted(group["allSourceUrls"]),
            "operators": sorted(group["operatorSet"]),
            "routeCount": len(group["routeIds"]),
            "routeIds": sorted(group["routeIds"]),
            "sampleRoutes": group["routes"][:8],
            "timeSignalCount": time_count,
            "fareSignalCount": fare_signal_count,
            "hasExplicitTimeSignals": time_count >= 4,
            "hasFareSignals": fare_signal_count >= 2,
            "fetchErrors": errors,
            "recommendedNextStep": (
                "candidate_for_parser"
                if time_count >= 4 and fare_signal_count >= 2
                else "needs_manual_source_review_or_pdf_parser"
            ),
        })

    recommended_counts = defaultdict(int)
    recommended_routes = defaultdict(int)
    for group in source_groups:
        recommended_counts[group["recommendedNextStep"]] += 1
        recommended_routes[group["recommendedNextStep"]] += group["routeCount"]

    payload = {
        "schema": "onichase.v5.ship_source_parse_candidates.1",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "skippedRouteCount": len(skipped_ids),
        "sourceGroupCount": len(source_groups),
        "recommendedSourceGroupCounts": dict(sorted(recommended_counts.items())),
        "recommendedRouteCounts": dict(sorted(recommended_routes.items())),
        "sourceGroups": source_groups,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "skippedRouteCount": payload["skippedRouteCount"],
        "sourceGroupCount": payload["sourceGroupCount"],
        "recommendedRouteCounts": payload["recommendedRouteCounts"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
