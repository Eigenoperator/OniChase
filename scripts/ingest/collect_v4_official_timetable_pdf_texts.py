#!/usr/bin/env python3
"""Collect text layers from official timetable PDF candidates for v4.

This is a raw-data collection step, not a train-instance parser.  Many Japanese
regional railway operators publish only PDF timetables.  Capturing their text
layers into a reusable corpus lets later operator-specific parsers work without
re-crawling websites and records which sources are scanned images or broken.
"""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATES = ROOT / "data" / "v4_official_site_timetable_candidates.json"
DEFAULT_OUTPUT = ROOT / "data" / "v4_official_timetable_pdf_text_corpus.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_official_timetable_pdf_text_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_url(url: str) -> str:
    return (url or "").strip()


def is_pdf_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(normalize_url(url))
    return ".pdf" in parsed.path.lower()


def iter_pdf_candidates(data: dict[str, Any], statuses: set[str]) -> list[dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}
    for operator in data.get("operators", []):
        for candidate in operator.get("candidates", []):
            url = normalize_url(candidate.get("url") or "")
            if not url or not is_pdf_url(url):
                continue
            if candidate.get("candidateStatus") not in statuses:
                continue
            if url in by_url:
                continue
            by_url[url] = {
                "operatorId": operator.get("operatorId"),
                "operatorName": operator.get("operatorName"),
                "lineNames": operator.get("lineNames") or [],
                "candidateStatus": candidate.get("candidateStatus"),
                "title": candidate.get("title") or "",
                "label": candidate.get("label") or "",
                "url": url,
                "officialWebsite": candidate.get("officialWebsite"),
                "domain": candidate.get("domain"),
                "score": candidate.get("score"),
            }
    return sorted(by_url.values(), key=lambda item: (item["operatorName"], item["url"]))


def fetch_bytes(url: str, timeout: int = 45) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    safe_url = urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            urllib.parse.quote(parsed.path, safe="/%"),
            urllib.parse.quote(parsed.query, safe="=&?/%"),
            parsed.fragment,
        )
    )
    request = urllib.request.Request(
        safe_url,
        headers={"User-Agent": "OniChase-v4-official-pdf-text/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def pdf_to_text(raw: bytes) -> tuple[str, str | None]:
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "source.pdf"
        txt_path = Path(tmp) / "source.txt"
        pdf_path.write_bytes(raw)
        proc = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf_path), str(txt_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            return "", proc.stderr.strip() or f"pdftotext exited {proc.returncode}"
        return txt_path.read_text(encoding="utf-8", errors="replace"), None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--statuses", default="high_confidence", help="Comma-separated candidateStatus values.")
    parser.add_argument("--max-pdfs", type=int, default=0)
    args = parser.parse_args()

    statuses = {item.strip() for item in args.statuses.split(",") if item.strip()}
    candidates = iter_pdf_candidates(load_json(args.candidates), statuses)
    if args.max_pdfs:
        candidates = candidates[: args.max_pdfs]

    documents: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        print(f"[{index}/{len(candidates)}] {candidate['operatorName']} {candidate['url']}", flush=True)
        try:
            raw = fetch_bytes(candidate["url"])
            text, text_error = pdf_to_text(raw)
        except Exception as exc:  # noqa: BLE001 - corpus collection should continue across broken links.
            audits.append({**candidate, "status": "fetch_or_extract_error", "error": f"{type(exc).__name__}: {exc}"})
            print(f"  error={type(exc).__name__}: {exc}", flush=True)
            continue

        normalized_text = text.replace("\x00", "")
        text_length = len(normalized_text.strip())
        status = "ok" if text_length else "empty_text"
        if text_error:
            status = "extract_error"
        audits.append(
            {
                **candidate,
                "status": status,
                "byteLength": len(raw),
                "textLength": text_length,
                "error": text_error,
            }
        )
        if status == "ok":
            documents.append(
                {
                    **candidate,
                    "byteLength": len(raw),
                    "textLength": text_length,
                    "text": normalized_text,
                }
            )
        print(f"  status={status} bytes={len(raw)} text={text_length}", flush=True)

    status_counts: dict[str, int] = {}
    for item in audits:
        status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1

    output = {
        "schema": "onichase.v4.official_timetable_pdf_text_corpus.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "sourceCandidates": str(args.candidates),
        "statuses": sorted(statuses),
        "documentCount": len(documents),
        "documents": documents,
    }
    audit = {
        "schema": "onichase.v4.official_timetable_pdf_text_audit.v1",
        "generatedAt": output["generatedAt"],
        "candidateCount": len(candidates),
        "documentCount": len(documents),
        "statusCounts": dict(sorted(status_counts.items())),
        "audits": audits,
    }
    write_json(args.output, output)
    write_json(args.audit_output, audit)
    print(f"Wrote {args.output}: {len(documents)} text documents")
    print(f"Wrote {args.audit_output}")
    print(json.dumps(audit["statusCounts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
