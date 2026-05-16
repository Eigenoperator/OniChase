#!/usr/bin/env python3
"""Download the complete official JAL domestic timetable XML set.

JAL's timetable page loads route XML files from:
    https://www.jal.co.jp/en/dom/time/xml/{period}/{FROM}_{TO}.xml

The route index is not published as a standalone file, so this downloader uses
the airport codes embedded in the timetable page and probes every physical
airport pair. Existing files are overwritten only when the official response is
valid XML.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PERIOD = "20260329_20260531"
DEFAULT_PAGE_CACHE = ROOT / "data/v5_flight_source_cache/jal/timeTable_20260329_20260531.html"
DEFAULT_OUTPUT_DIR = ROOT / "data/v5_flight_source_cache/jal/20260329_20260531"
BASE_URL = "https://www.jal.co.jp/en/dom/time/xml"
USER_AGENT = "Mozilla/5.0"
CITY_GROUP_CODES = {"TYO", "OSA", "SPK", "NGY"}


def load_airport_codes(page_cache: Path) -> list[str]:
    html = page_cache.read_text(encoding="utf-8", errors="replace")
    codes = set(re.findall(r'data-cd="([A-Z0-9]{3})"', html))
    return sorted(code for code in codes if code not in CITY_GROUP_CODES)


def load_missing_reverse_pairs(output_dir: Path) -> list[tuple[str, str]]:
    stems = {path.stem for path in output_dir.glob("*.xml")}
    pairs = set()
    for stem in stems:
        origin, dest = stem.split("_", 1)
        reverse = f"{dest}_{origin}"
        if reverse not in stems:
            pairs.add((dest, origin))
    return sorted(pairs)


def is_valid_timetable_xml(path: Path) -> bool:
    try:
        text = path.read_text(encoding="iso-8859-1", errors="replace")
    except OSError:
        return False
    return "<timetable>" in text and "</timetable>" in text


def fetch_pair(period: str, output_dir: Path, origin: str, dest: str, timeout: int) -> tuple[str, str, str]:
    target = output_dir / f"{origin}_{dest}.xml"
    url = f"{BASE_URL}/{period}/{origin}_{dest}.xml"
    with tempfile.NamedTemporaryFile(prefix=f"{origin}_{dest}.", suffix=".xml", delete=False) as handle:
        tmp_path = Path(handle.name)
    try:
        result = subprocess.run(
            [
                "wget",
                "-q",
                "-O",
                str(tmp_path),
                "--user-agent",
                USER_AGENT,
                "--timeout",
                str(timeout),
                "--tries",
                "1",
                url,
            ],
            check=False,
        )
        if result.returncode != 0 or not is_valid_timetable_xml(tmp_path):
            return origin, dest, "missing"
        old = target.read_bytes() if target.exists() else None
        new = tmp_path.read_bytes()
        if old == new:
            return origin, dest, "unchanged"
        target.write_bytes(new)
        return origin, dest, "updated" if old is not None else "added"
    finally:
        tmp_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--page-cache", type=Path, default=DEFAULT_PAGE_CACHE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument("--missing-reverses-only", action="store_true")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    airports = load_airport_codes(args.page_cache)
    pairs = (
        load_missing_reverse_pairs(args.output_dir)
        if args.missing_reverses_only
        else [(origin, dest) for origin in airports for dest in airports if origin != dest]
    )
    counts: dict[str, int] = {"added": 0, "updated": 0, "unchanged": 0, "missing": 0}
    changed: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(fetch_pair, args.period, args.output_dir, origin, dest, args.timeout)
            for origin, dest in pairs
        ]
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            origin, dest, status = future.result()
            counts[status] = counts.get(status, 0) + 1
            if status in {"added", "updated"}:
                changed.append(f"{origin}_{dest}.xml")
            if index % 250 == 0:
                print(f"checked {index}/{len(pairs)} {counts}")

    print(
        {
            "airportCount": len(airports),
            "pairCount": len(pairs),
            "missingReversesOnly": args.missing_reverses_only,
            "counts": counts,
            "changedFiles": sorted(changed),
        }
    )


if __name__ == "__main__":
    main()
