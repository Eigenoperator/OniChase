#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PUBLIC_PAGE = ROOT / "docs" / "v3.html"
LOCAL_MIRROR = ROOT / "ui" / "v3_maplibre.html"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_sync() -> list[str]:
    if not PUBLIC_PAGE.exists():
        return [f"missing public v3 page: {PUBLIC_PAGE}"]
    if not LOCAL_MIRROR.exists():
        return [f"missing local v3 mirror: {LOCAL_MIRROR}"]
    if read_text(PUBLIC_PAGE) != read_text(LOCAL_MIRROR):
        return [f"{LOCAL_MIRROR.relative_to(ROOT)} is out of sync with {PUBLIC_PAGE.relative_to(ROOT)}"]
    return []


def sync_page() -> None:
    LOCAL_MIRROR.write_text(read_text(PUBLIC_PAGE), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build/sync the local v3 MapLibre page mirror from docs/v3.html, the current source of truth."
    )
    parser.add_argument("--check", action="store_true", help="Only verify that ui/v3_maplibre.html matches docs/v3.html.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.check:
        errors = check_sync()
        if errors:
            for error in errors:
                print(error)
            raise SystemExit(1)
        print("v3 page mirror is in sync")
        return
    sync_page()
    print(f"synced {LOCAL_MIRROR.relative_to(ROOT)} from {PUBLIC_PAGE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
