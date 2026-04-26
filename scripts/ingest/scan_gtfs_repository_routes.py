#!/usr/bin/env python3
"""Build a lightweight route index for every GTFS.jp repository feed.

The output intentionally stores only metadata from agency.txt/routes.txt and
small counts.  Feed zip files are downloaded transiently and are not cached.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "data" / "v4_gtfs_repository_route_index.json"
GTFS_REPOSITORY_FILES_URL = "https://api.gtfs-data.jp/v2/files?target_date=all"

RAIL_ROUTE_TYPES = {0, 1, 2, 5, 6, 7, 11, 12}
BUS_ROUTE_TYPES = {3}


def fetch_json_url(url: str, timeout: int = 60) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json,*/*",
            "Accept-Encoding": "gzip",
            "User-Agent": "OniChase-v4-gtfs-route-scan/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return json.loads(raw)


def read_csv_from_zip(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    try:
        with archive.open(name) as member:
            text = io.TextIOWrapper(member, encoding="utf-8-sig")
            return list(csv.DictReader(text))
    except KeyError:
        return []


def inspect_feed(feed: dict[str, Any], timeout: int) -> dict[str, Any]:
    file_url = feed.get("file_url")
    item = {
        "organizationId": feed.get("organization_id"),
        "organizationName": feed.get("organization_name"),
        "feedId": feed.get("feed_id"),
        "feedName": feed.get("feed_name"),
        "feedPrefId": feed.get("feed_pref_id"),
        "feedPageUrl": feed.get("feed_page_url"),
        "fileUrl": file_url,
        "fileFromDate": feed.get("file_from_date"),
        "fileToDate": feed.get("file_to_date"),
        "fileLastUpdatedAt": feed.get("file_last_updated_at"),
        "licenseId": feed.get("feed_license_id"),
    }
    if not file_url:
        item["status"] = "missing_file_url"
        return item

    request = urllib.request.Request(
        str(file_url),
        headers={"User-Agent": "OniChase-v4-gtfs-route-scan/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            agency_rows = read_csv_from_zip(archive, "agency.txt")
            route_rows = read_csv_from_zip(archive, "routes.txt")
            stop_rows = read_csv_from_zip(archive, "stops.txt")
            stop_time_rows = read_csv_from_zip(archive, "stop_times.txt")
    except (OSError, urllib.error.URLError, zipfile.BadZipFile) as exc:
        item["status"] = "inspection_error"
        item["error"] = f"{type(exc).__name__}: {exc}"
        return item

    route_types: set[int] = set()
    routes: list[dict[str, Any]] = []
    for row in route_rows:
        route_type_raw = (row.get("route_type") or "").strip()
        route_type = None
        if route_type_raw:
            try:
                route_type = int(route_type_raw)
                route_types.add(route_type)
            except ValueError:
                pass
        routes.append(
            {
                "routeId": row.get("route_id"),
                "agencyId": row.get("agency_id"),
                "shortName": row.get("route_short_name"),
                "longName": row.get("route_long_name"),
                "routeDesc": row.get("route_desc"),
                "routeType": route_type,
                "routeColor": row.get("route_color"),
                "routeTextColor": row.get("route_text_color"),
            }
        )

    agencies = [
        {
            "agencyId": row.get("agency_id"),
            "agencyName": row.get("agency_name"),
            "agencyUrl": row.get("agency_url"),
            "agencyTimezone": row.get("agency_timezone"),
            "agencyLang": row.get("agency_lang"),
        }
        for row in agency_rows
    ]

    item.update(
        {
            "status": "ok",
            "agencyCount": len(agency_rows),
            "routeCount": len(route_rows),
            "stopCount": len(stop_rows),
            "stopTimeCount": len(stop_time_rows),
            "routeTypes": sorted(route_types),
            "isRailLike": bool(route_types & RAIL_ROUTE_TYPES),
            "isBusOnly": bool(route_types) and route_types <= BUS_ROUTE_TYPES,
            "agencies": agencies,
            "routes": routes,
        }
    )
    return item


def load_existing(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return {
        item.get("fileUrl"): item
        for item in data.get("feeds", [])
        if item.get("fileUrl") and item.get("status") == "ok"
    }


def write_output(path: Path, feeds: list[dict[str, Any]]) -> None:
    status_counts: dict[str, int] = {}
    rail_like = 0
    for item in feeds:
        status = item.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        if item.get("isRailLike"):
            rail_like += 1
    output = {
        "schema": "onichase.v4.gtfs_repository_route_index.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "sourceUrl": GTFS_REPOSITORY_FILES_URL,
        "counts": {
            "feedCount": len(feeds),
            "railLikeFeedCount": rail_like,
            "statusCounts": dict(sorted(status_counts.items())),
        },
        "feeds": sorted(feeds, key=lambda item: (str(item.get("feedPrefId")), str(item.get("organizationName")), str(item.get("feedName")))),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--max-feeds", type=int, default=0, help="Debug limit; 0 means all feeds.")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--flush-every", type=int, default=25)
    args = parser.parse_args()

    data = fetch_json_url(GTFS_REPOSITORY_FILES_URL)
    feeds = data.get("body", []) if isinstance(data, dict) else []
    if args.max_feeds:
        feeds = feeds[: args.max_feeds]

    existing = load_existing(args.output) if args.resume else {}
    results: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for feed in feeds:
        file_url = feed.get("file_url")
        if file_url in existing:
            results.append(existing[file_url])
        else:
            pending.append(feed)

    print(f"GTFS repository feeds: {len(feeds)} total, {len(results)} reused, {len(pending)} pending")
    completed = 0
    with ThreadPoolExecutor(max_workers=max(args.workers, 1)) as executor:
        future_to_feed = {executor.submit(inspect_feed, feed, args.timeout): feed for feed in pending}
        for future in as_completed(future_to_feed):
            results.append(future.result())
            completed += 1
            if completed % args.flush_every == 0:
                write_output(args.output, results)
                print(f"scanned {completed}/{len(pending)} pending feeds")

    write_output(args.output, results)
    with open(args.output, encoding="utf-8") as handle:
        summary = json.load(handle)["counts"]
    print(f"Wrote {args.output}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
