#!/usr/bin/env python3
"""Collect official Niigata Airport bus PDF timetable sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE_URLS = [
    "https://www.niigata-kotsu.co.jp/~noriai/route-bus/timetable/access/airport/files/260329_niigatasta-tt.pdf",
    "https://www.niigata-kotsu.co.jp/~noriai/route-bus/timetable/access/airport/files/260329_airport-tt.pdf",
]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "niigata_airport_pdfs"
DEFAULT_OUTPUT = ROOT / "data" / "v5_niigata_airport_official_bus_pdfs.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_niigata_airport_official_bus_pdfs.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_niigata_airport_official_bus_pdfs_audit.json"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_path_for(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.pdf"


def fetch_bytes(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> tuple[bytes, Path, str]:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path.read_bytes(), path, "application/pdf"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        content_type = response.headers.get("content-type", "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data, path, content_type


def pdf_text(path: Path) -> str:
    result = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=False, capture_output=True, text=True, timeout=30)
    return result.stdout if result.returncode == 0 else ""


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    pdfs = []
    for url in SOURCE_URLS:
        data, path, content_type = fetch_bytes(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
        text = pdf_text(path)
        times = sorted(set(re.findall(r"\b\d{1,2}:\d{2}\b", text)))
        direction = "to_airport" if "niigatasta" in url else "from_airport"
        status = "pdf_time_text_found" if times else "pdf_cached_no_time_text"
        pdfs.append(
            {
                "url": url,
                "direction": direction,
                "status": status,
                "contentType": content_type,
                "cachePath": str(path.relative_to(ROOT)),
                "byteCount": len(data),
                "timeTextCount": len(times),
                "sampleTimes": times[:30],
                "textSample": re.sub(r"\s+", " ", text).strip()[:800],
            }
        )
    status_counts = Counter(pdf["status"] for pdf in pdfs)
    source = {
        "schemaVersion": "v5_official_bus_source.niigata_airport_pdfs.v1",
        "generatedAt": generated_at,
        "sourcePolicy": "Official Niigata Kotsu airport-bus PDF timetable sources. This pass caches PDFs and extracts text; route normalization is separate.",
        "airportIata": "KIJ",
        "operatorName": "Niigata Kotsu",
        "pdfs": pdfs,
    }
    audit = {
        "schemaVersion": "v5_official_bus_source_audit.niigata_airport_pdfs.v1",
        "generatedAt": generated_at,
        "pdfCount": len(pdfs),
        "statusCounts": dict(sorted(status_counts.items())),
        "timeTextPdfCount": status_counts["pdf_time_text_found"],
        "pdfs": pdfs,
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
