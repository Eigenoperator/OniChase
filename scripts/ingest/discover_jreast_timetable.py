#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser


BASE_URL = "https://timetables.jreast.co.jp"


class AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._current_href = href
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href is not None:
            text = re.sub(r"\s+", " ", "".join(self._text_parts)).strip()
            self.anchors.append({"href": self._current_href, "text": text})
            self._current_href = None
            self._text_parts = []


def fetch_html(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Codex JR East Discovery Script)"
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def collect_anchors(html: str) -> list[dict[str, str]]:
    parser = AnchorCollector()
    parser.feed(html)
    return parser.anchors


def normalize_url(href: str, base_url: str) -> str:
    return urllib.parse.urljoin(base_url, href)


def filter_timetable_links(anchors: list[dict[str, str]], keyword: str | None) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for anchor in anchors:
        href = anchor["href"]
        text = anchor["text"]
        full_url = normalize_url(href, BASE_URL)
        haystack = f"{text} {href}".lower()
        if "/timetable/" not in haystack and "list" not in haystack:
            continue
        if keyword and keyword.lower() not in haystack:
            continue
        results.append({"text": text, "url": full_url})
    return results


def filter_train_links(anchors: list[dict[str, str]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for anchor in anchors:
        href = anchor["href"]
        if "/train/" not in href:
            continue
        results.append({"text": anchor["text"], "url": normalize_url(href, BASE_URL)})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover JR East timetable and train-detail links from an official timetable page."
    )
    parser.add_argument("--url", required=True, help="Official JR East station timetable or station list URL.")
    parser.add_argument(
        "--keyword",
        default="Yamanote",
        help="Optional keyword filter for timetable links. Default: Yamanote",
    )
    args = parser.parse_args()

    try:
        html = fetch_html(args.url)
    except urllib.error.URLError as exc:
        print(f"Fetch failed for {args.url}: {exc}", file=sys.stderr)
        return 1

    anchors = collect_anchors(html)
    timetable_links = filter_timetable_links(anchors, args.keyword)
    train_links = filter_train_links(anchors)

    print(f"Source URL: {args.url}")
    print(f"Anchors found: {len(anchors)}")
    print("")
    print("Timetable-like links:")
    for item in timetable_links[:50]:
        print(f"- {item['text'] or '(no text)'} -> {item['url']}")
    print("")
    print("Train-detail links:")
    for item in train_links[:50]:
        print(f"- {item['text'] or '(no text)'} -> {item['url']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
