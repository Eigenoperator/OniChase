#!/usr/bin/env python3
"""Discover official websites and timetable links for v4 rail operators.

The workflow is deliberately conservative:
1. Use Wikidata P856 to find official websites by Japanese operator label.
2. Crawl a small same-domain neighborhood.
3. Keep links/pages containing timetable-related terms as source candidates.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "data" / "v4_timetable_source_registry.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_official_site_timetable_candidates.json"

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

TIMETABLE_TERMS = (
    "時刻表",
    "ダイヤ",
    "列車時刻",
    "運行時刻",
    "timetable",
    "schedule",
    "diagram",
    "jikoku",
)
RAIL_NAV_TERMS = (
    "鉄道",
    "電車",
    "列車",
    "駅",
    "乗る",
    "利用",
    "路線",
    "train",
    "rail",
    "station",
)
SKIP_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".css",
    ".js",
    ".ico",
    ".zip",
    ".mp4",
    ".mp3",
)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_compact(value: str) -> str:
    return normalize_space(value).replace(" ", "").replace("　", "").lower()


def same_site_domain(url: str) -> str:
    netloc = urllib.parse.urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def url_allowed(url: str, base_domain: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if same_site_domain(url) != base_domain:
        return False
    path = parsed.path.lower()
    return not path.endswith(SKIP_EXTENSIONS)


def fetch_text(url: str, timeout: int) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) OniChase-v4-official-site-discovery/0.1",
            "Accept": "text/html,application/xhtml+xml,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(2_500_000)
        charset = response.headers.get_content_charset()
    if charset:
        return raw.decode(charset, "ignore")
    for encoding in ("utf-8", "cp932", "shift_jis", "euc_jp"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def page_title(text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    if not match:
        return ""
    return normalize_space(html.unescape(re.sub(r"<.*?>", "", match.group(1))))


def parse_links(text: str, base_url: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for raw_href, raw_label in re.findall(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", text, re.I | re.S):
        href = html.unescape(raw_href)
        url = urllib.parse.urljoin(base_url, href)
        url = urllib.parse.urldefrag(url)[0]
        label = normalize_space(html.unescape(re.sub(r"<.*?>", "", raw_label)))
        links.append({"url": url, "label": label})
    return links


def score_timetable_candidate(url: str, label: str, title: str = "") -> int:
    haystack = normalize_compact(" ".join([url, label, title]))
    score = 0
    if any(term.lower() in haystack for term in TIMETABLE_TERMS):
        score += 60
    if any(term.lower() in haystack for term in RAIL_NAV_TERMS):
        score += 15
    if re.search(r"(timetable|jikoku|diagram|daiya|time|schedule|station|eki|train|rail)", haystack):
        score += 10
    if url.lower().endswith(".pdf"):
        score += 5
    return score


def classify(score: int) -> str:
    if score >= 70:
        return "high_confidence"
    if score >= 50:
        return "medium_confidence"
    if score >= 30:
        return "review_needed"
    return "low_relevance"


def wikidata_official_websites(labels: list[str], chunk_size: int, delay: float, timeout: int) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {label: [] for label in labels}
    for start in range(0, len(labels), chunk_size):
        chunk = labels[start : start + chunk_size]
        values = " ".join(json.dumps(label, ensure_ascii=False) + "@ja" for label in chunk)
        query = f"""
SELECT ?label ?item ?itemLabel ?website WHERE {{
  VALUES ?label {{ {values} }}
  ?item rdfs:label ?label.
  OPTIONAL {{ ?item wdt:P856 ?website. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ja,en". }}
}}
"""
        url = SPARQL_ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "OniChase/0.1 (https://github.com/Eigenoperator/OniChase)"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        for row in data.get("results", {}).get("bindings", []):
            label = row.get("label", {}).get("value")
            if not label:
                continue
            item = row.get("item", {}).get("value")
            website = row.get("website", {}).get("value")
            item_label = row.get("itemLabel", {}).get("value")
            out.setdefault(label, []).append(
                {
                    "wikidataItem": item,
                    "wikidataLabel": item_label,
                    "officialWebsite": website,
                }
            )
        if delay:
            time.sleep(delay)
    return out


def crawl_site_for_timetable(website: str, timeout: int, max_pages: int, max_depth: int) -> tuple[list[dict[str, Any]], list[str]]:
    if not website:
        return [], []
    base_domain = same_site_domain(website)
    queue: deque[tuple[str, int]] = deque([(website, 0)])
    seen: set[str] = set()
    candidates_by_url: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    while queue and len(seen) < max_pages:
        url, depth = queue.popleft()
        url = urllib.parse.urldefrag(url)[0]
        if url in seen or not url_allowed(url, base_domain):
            continue
        seen.add(url)
        try:
            text = fetch_text(url, timeout)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
            continue

        title = page_title(text)
        page_score = score_timetable_candidate(url, "", title)
        if page_score >= 50:
            candidates_by_url[url] = {
                "url": url,
                "title": title,
                "label": "",
                "score": page_score,
                "candidateStatus": classify(page_score),
                "foundAs": "page",
            }

        for link in parse_links(text, url):
            link_url = link["url"]
            if not url_allowed(link_url, base_domain):
                continue
            score = score_timetable_candidate(link_url, link["label"], "")
            if score >= 50:
                existing = candidates_by_url.get(link_url)
                item = {
                    "url": link_url,
                    "title": "",
                    "label": link["label"],
                    "score": score,
                    "candidateStatus": classify(score),
                    "foundAs": "link",
                }
                if not existing or item["score"] > existing["score"]:
                    candidates_by_url[link_url] = item

            link_text = normalize_compact(link_url + " " + link["label"])
            should_follow = depth < max_depth and (
                score >= 30
                or any(term.lower() in link_text for term in RAIL_NAV_TERMS)
                or depth == 0
            )
            if should_follow and link_url not in seen:
                queue.append((link_url, depth + 1))

    candidates = sorted(candidates_by_url.values(), key=lambda item: item["score"], reverse=True)
    return candidates[:20], errors[:10]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-status", action="append", default=["needs_source_research", "needs_source_research_rejected_name_match_only"])
    parser.add_argument("--max-operators", type=int, default=0)
    parser.add_argument("--wikidata-chunk-size", type=int, default=40)
    parser.add_argument("--wikidata-delay", type=float, default=0.25)
    parser.add_argument("--crawl-delay", type=float, default=0.15)
    parser.add_argument("--timeout", type=int, default=18)
    parser.add_argument("--max-pages", type=int, default=18)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    with open(args.registry, encoding="utf-8") as handle:
        registry = json.load(handle)
    target_statuses = set(args.target_status or [])
    operators = [
        operator
        for operator in registry["operators"]
        if operator.get("sourceStatus") in target_statuses
    ]
    if args.max_operators:
        operators = operators[: args.max_operators]

    existing_by_operator: dict[str, dict[str, Any]] = {}
    if args.resume and args.output.exists():
        with open(args.output, encoding="utf-8") as handle:
            existing = json.load(handle)
        existing_by_operator = {
            item.get("operatorName"): item
            for item in existing.get("operators", [])
            if item.get("operatorName")
        }

    labels = [operator["operatorName"] for operator in operators]
    websites = wikidata_official_websites(labels, args.wikidata_chunk_size, args.wikidata_delay, args.timeout)

    output_operators: list[dict[str, Any]] = []

    def write_partial() -> None:
        best_counts: dict[str, int] = {}
        website_count = 0
        for item in output_operators:
            if item["wikidataOfficialWebsites"]:
                website_count += 1
            best = item.get("candidates", [{}])[0].get("candidateStatus", "no_candidate") if item.get("candidates") else "no_candidate"
            best_counts[best] = best_counts.get(best, 0) + 1
        output = {
            "schema": "onichase.v4.official_site_timetable_candidates.v1",
            "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "sourceRegistry": str(args.registry),
            "counts": {
                "operatorCount": len(output_operators),
                "operatorsWithOfficialWebsite": website_count,
                "bestCandidateStatusCounts": dict(sorted(best_counts.items())),
            },
            "operators": sorted(output_operators, key=lambda item: item["operatorName"]),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(output, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    for index, operator in enumerate(operators, start=1):
        operator_name = operator["operatorName"]
        if operator_name in existing_by_operator:
            output_operators.append(existing_by_operator[operator_name])
            print(f"[{index}/{len(operators)}] {operator_name}: reused", flush=True)
            continue
        site_rows = [row for row in websites.get(operator_name, []) if row.get("officialWebsite")]
        unique_sites: list[str] = []
        for row in site_rows:
            site = row["officialWebsite"]
            if site not in unique_sites:
                unique_sites.append(site)

        candidates: list[dict[str, Any]] = []
        errors: list[str] = []
        for site in unique_sites[:3]:
            site_candidates, site_errors = crawl_site_for_timetable(site, args.timeout, args.max_pages, args.max_depth)
            for candidate in site_candidates:
                candidate["officialWebsite"] = site
                candidate["domain"] = same_site_domain(candidate["url"])
            candidates.extend(site_candidates)
            errors.extend(site_errors)
            if args.crawl_delay:
                time.sleep(args.crawl_delay)

        by_url: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            existing = by_url.get(candidate["url"])
            if not existing or candidate["score"] > existing["score"]:
                by_url[candidate["url"]] = candidate
        candidates = sorted(by_url.values(), key=lambda item: item["score"], reverse=True)
        output_operators.append(
            {
                "operatorId": operator["operatorId"],
                "operatorName": operator_name,
                "sourceStatusBeforeDiscovery": operator.get("sourceStatus"),
                "lineCount": operator.get("lineCount"),
                "lineNames": operator.get("lineNames"),
                "wikidataOfficialWebsites": site_rows,
                "candidates": candidates[:20],
                "errors": errors[:10],
            }
        )
        print(f"[{index}/{len(operators)}] {operator_name}: websites={len(unique_sites)} candidates={len(candidates)}", flush=True)
        write_partial()

    write_partial()
    with open(args.output, encoding="utf-8") as handle:
        output = json.load(handle)
    print(f"Wrote {args.output}")
    print(json.dumps(output["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
