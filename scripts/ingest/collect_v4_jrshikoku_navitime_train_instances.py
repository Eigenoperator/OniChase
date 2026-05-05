#!/usr/bin/env python3
"""Collect JR Shikoku train instances through the shared Navitime collector."""

from __future__ import annotations

from pathlib import Path

import collect_v4_jrcentral_navitime_train_instances as nav


ROOT = Path(__file__).resolve().parents[2]

nav.OPERATOR_ID = "jr_shikoku"
nav.OPERATOR_NAME = "四国旅客鉄道"
nav.ROUTE_COLOR = "2F7D32"
nav.SOURCE_KEY = "jr_shikoku_navitime"
nav.AUDIT_SCHEMA = "onichase.v4.jrshikoku_navitime_train_instances_audit.v1"
nav.COLLECTION_ID = "v4_jrshikoku_navitime_weekday_train_instances_v0_1"
nav.COLLECTION_LABEL = "V4 JR Shikoku weekday train instances collected from Navitime stop pages"
nav.DEFAULT_OUTPUT = ROOT / "data" / "v4_jrshikoku_navitime_weekday_train_instances.json.gz"
nav.DEFAULT_AUDIT = ROOT / "data" / "v4_jrshikoku_navitime_train_instances_audit.json"
nav.DEFAULT_CACHE_DIR = ROOT / "data" / "v4_jrshikoku_navitime_cache"
nav.LINE_ALIASES = {
    "予讃線": ["予讃線", "JR予讃線", "ＪＲ予讃線"],
    "内子線": ["内子線", "JR内子線", "ＪＲ内子線"],
    "予土線": ["予土線", "JR予土線", "ＪＲ予土線"],
    "土讃線": ["土讃線", "JR土讃線", "ＪＲ土讃線"],
    "高徳線": ["高徳線", "JR高徳線", "ＪＲ高徳線"],
    "徳島線": ["徳島線", "よしの川ブルーライン", "JR徳島線", "ＪＲ徳島線"],
    "牟岐線": ["牟岐線", "阿波室戸シーサイドライン", "JR牟岐線", "ＪＲ牟岐線"],
    "鳴門線": ["鳴門線", "JR鳴門線", "ＪＲ鳴門線"],
    "本四備讃線": ["本四備讃線", "瀬戸大橋線", "JR瀬戸大橋線", "ＪＲ瀬戸大橋線"],
}


def main() -> int:
    nav.load_jrcentral_station_orders = lambda cache_dir, refresh=False: {}  # type: ignore[assignment]
    return nav.main()


if __name__ == "__main__":
    raise SystemExit(main())
