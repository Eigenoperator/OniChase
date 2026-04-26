#!/usr/bin/env python3
"""Discover ODPT CKAN railway GTFS download resources for v4.

The ODPT catalog exposes many railway GTFS resources through CKAN HTML pages.
Some files are public `api-public.odpt.org` downloads, while others require an
ODPT developer token.  This script turns those catalog pages into a reusable
machine-readable audit so collection can safely ingest public feeds and record
token-gated feeds as blockers.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "data" / "v4_timetable_source_registry.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_odpt_gtfs_resource_audit.json"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "a" and attr_map.get("href"):
            self._current_href = attr_map["href"]
            self._current_text = []
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href:
            self.links.append(
                {
                    "href": html.unescape(self._current_href),
                    "text": " ".join("".join(self._current_text).split()),
                }
            )
            self._current_href = None
            self._current_text = []
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data)
        if self._in_title:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_html(url: str, timeout: int = 45) -> tuple[str, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "OniChase-v4-odpt-discovery/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        raw = response.read()
    return raw.decode(charset, errors="replace"), charset


def parse_html_links(url: str, text: str) -> tuple[str, list[dict[str, str]]]:
    parser = LinkParser()
    parser.feed(text)
    links: list[dict[str, str]] = []
    for link in parser.links:
        href = urllib.parse.urljoin(url, link["href"])
        links.append({"href": href, "text": link["text"]})
    return parser.title, links


def is_odpt_file_url(url: str) -> bool:
    return "/api/v4/files/" in url and ("api-public.odpt.org" in url or "api.odpt.org" in url)


def classify_file_url(url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    requires_token = "api.odpt.org" in parsed.netloc or "consumerKey" in url
    is_public = "api-public.odpt.org" in parsed.netloc and not requires_token
    cleaned = url
    if requires_token:
        cleaned = re.sub(r"([?&]acl:consumerKey=)(?:\[[^\]]*\]|[^&]*)", r"\1", cleaned)
    date_match = re.search(r"(?:[?&]date=|[-_])((?:20)\d{6})", url)
    return {
        "url": url,
        "cleanedUrl": cleaned,
        "isPublic": is_public,
        "requiresToken": requires_token,
        "detectedDate": date_match.group(1) if date_match else None,
    }


def dedupe_dicts(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for item in items:
        value = str(item.get(key) or "")
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(item)
    return output


def collect_odpt_leads(registry: dict[str, Any]) -> list[dict[str, str]]:
    leads: list[dict[str, str]] = []
    for operator in registry.get("operators", []):
        for lead in operator.get("sourceLeads", []):
            if lead.get("sourceKind") != "odpt_rail_gtfs_candidate":
                continue
            url = lead.get("url")
            if not url:
                continue
            leads.append(
                {
                    "operatorId": operator["operatorId"],
                    "operatorName": operator["operatorName"],
                    "title": lead.get("title") or operator["operatorName"],
                    "catalogUrl": url,
                    "scopeNote": lead.get("scopeNote") or "",
                }
            )
    return leads


def discover_lead(lead: dict[str, str]) -> dict[str, Any]:
    page_errors: list[str] = []
    resource_pages: list[dict[str, Any]] = []
    direct_files: list[dict[str, Any]] = []

    try:
        catalog_html, _charset = fetch_html(lead["catalogUrl"])
        catalog_title, catalog_links = parse_html_links(lead["catalogUrl"], catalog_html)
    except Exception as exc:  # noqa: BLE001 - discovery should keep auditing other leads.
        return {
            **lead,
            "catalogTitle": None,
            "catalogFetchOk": False,
            "errors": [f"catalog_fetch_failed: {type(exc).__name__}: {exc}"],
            "resourcePages": [],
            "fileDownloads": [],
            "publicDownloads": [],
            "tokenRequiredDownloads": [],
            "selectedPublicDownload": None,
        }

    resource_urls: list[str] = []
    for link in catalog_links:
        href = link["href"]
        if "/dataset/" in href and "/resource/" in href:
            resource_urls.append(href)
        if is_odpt_file_url(href):
            direct_files.append(classify_file_url(href) | {"sourcePageUrl": lead["catalogUrl"], "sourcePageTitle": catalog_title})

    for resource_url in sorted(set(resource_urls)):
        try:
            resource_html, _charset = fetch_html(resource_url)
            resource_title, resource_links = parse_html_links(resource_url, resource_html)
        except Exception as exc:  # noqa: BLE001
            page_errors.append(f"resource_fetch_failed: {resource_url}: {type(exc).__name__}: {exc}")
            continue

        resource_files: list[dict[str, Any]] = []
        for link in resource_links:
            href = link["href"]
            if is_odpt_file_url(href):
                resource_files.append(
                    classify_file_url(href)
                    | {
                        "sourcePageUrl": resource_url,
                        "sourcePageTitle": resource_title,
                        "linkText": link.get("text") or "",
                    }
                )
        resource_files = dedupe_dicts(resource_files, "url")
        resource_pages.append(
            {
                "url": resource_url,
                "title": resource_title,
                "fileCount": len(resource_files),
                "fileDownloads": resource_files,
            }
        )

    file_downloads: list[dict[str, Any]] = direct_files[:]
    for page in resource_pages:
        file_downloads.extend(page["fileDownloads"])
    file_downloads = dedupe_dicts(file_downloads, "url")
    public_downloads = [item for item in file_downloads if item["isPublic"]]
    token_downloads = [item for item in file_downloads if item["requiresToken"]]
    public_downloads.sort(key=lambda item: (item.get("detectedDate") or "", item["url"]), reverse=True)

    return {
        **lead,
        "catalogTitle": catalog_title,
        "catalogFetchOk": True,
        "errors": page_errors,
        "resourcePages": resource_pages,
        "fileDownloads": file_downloads,
        "publicDownloads": public_downloads,
        "tokenRequiredDownloads": token_downloads,
        "selectedPublicDownload": public_downloads[0] if public_downloads else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-leads", type=int, default=0)
    args = parser.parse_args()

    registry = load_json(args.registry)
    leads = collect_odpt_leads(registry)
    if args.max_leads:
        leads = leads[: args.max_leads]

    results: list[dict[str, Any]] = []
    for index, lead in enumerate(leads, start=1):
        print(f"[{index}/{len(leads)}] {lead['operatorName']} {lead['catalogUrl']}", flush=True)
        result = discover_lead(lead)
        results.append(result)
        print(
            f"  public={len(result['publicDownloads'])} token={len(result['tokenRequiredDownloads'])} "
            f"resources={len(result['resourcePages'])} errors={len(result['errors'])}",
            flush=True,
        )

    summary_by_status: dict[str, int] = defaultdict(int)
    for result in results:
        if result.get("selectedPublicDownload"):
            summary_by_status["public_download_available"] += 1
        elif result.get("tokenRequiredDownloads"):
            summary_by_status["token_required"] += 1
        elif result.get("catalogFetchOk"):
            summary_by_status["catalog_found_no_download"] += 1
        else:
            summary_by_status["catalog_fetch_failed"] += 1

    output = {
        "schema": "onichase.v4.odpt_gtfs_resource_audit.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "sourceRegistry": str(args.registry),
        "leadCount": len(leads),
        "summary": {
            "statusCounts": dict(sorted(summary_by_status.items())),
            "publicDownloadCount": sum(len(result["publicDownloads"]) for result in results),
            "tokenRequiredDownloadCount": sum(len(result["tokenRequiredDownloads"]) for result in results),
            "resourcePageCount": sum(len(result["resourcePages"]) for result in results),
        },
        "operators": sorted(results, key=lambda item: item["operatorName"]),
    }
    write_json(args.output, output)
    print(f"Wrote {args.output}")
    print(json.dumps(output["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
