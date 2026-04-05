#!/usr/bin/env python3

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_HTML = ROOT / "ui" / "v2_web_client.html"
DOCS_DIR = ROOT / "docs"
DOCS_DATA_DIR = DOCS_DIR / "data"
TARGET_HTML = DOCS_DIR / "index.html"
NOJEKYLL = DOCS_DIR / ".nojekyll"

DATA_FILES = [
    ROOT / "data" / "shinkansen_v2_bundle.json",
    ROOT / "data" / "shinkansen_v2_weekday_train_instances_merged.json",
]


def build() -> None:
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    html = SOURCE_HTML.read_text(encoding="utf-8").replace("__DATA_BASE__", "./data")
    TARGET_HTML.write_text(html, encoding="utf-8")
    NOJEKYLL.write_text("", encoding="utf-8")
    for path in DATA_FILES:
      shutil.copy2(path, DOCS_DATA_DIR / path.name)


if __name__ == "__main__":
    build()
