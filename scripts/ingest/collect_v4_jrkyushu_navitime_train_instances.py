#!/usr/bin/env python3
"""Collect JR Kyushu train instances through the shared Navitime collector."""

from __future__ import annotations

from pathlib import Path

import collect_v4_jrcentral_navitime_train_instances as nav


ROOT = Path(__file__).resolve().parents[2]

nav.OPERATOR_ID = "jr_kyushu"
nav.OPERATOR_NAME = "九州旅客鉄道"
nav.ROUTE_COLOR = "D81E24"
nav.SOURCE_KEY = "jr_kyushu_navitime"
nav.AUDIT_SCHEMA = "onichase.v4.jrkyushu_navitime_train_instances_audit.v1"
nav.COLLECTION_ID = "v4_jrkyushu_navitime_weekday_train_instances_v0_1"
nav.COLLECTION_LABEL = "V4 JR Kyushu weekday train instances collected from Navitime stop pages"
nav.DEFAULT_OUTPUT = ROOT / "data" / "v4_jrkyushu_navitime_weekday_train_instances.json.gz"
nav.DEFAULT_AUDIT = ROOT / "data" / "v4_jrkyushu_navitime_train_instances_audit.json"
nav.DEFAULT_CACHE_DIR = ROOT / "data" / "v4_jrkyushu_navitime_cache"
nav.LINE_ALIASES = {
    "鹿児島線": ["鹿児島線", "鹿児島本線", "JR鹿児島本線", "ＪＲ鹿児島本線"],
    "日豊線": ["日豊線", "日豊本線", "JR日豊本線", "ＪＲ日豊本線"],
    "長崎線": ["長崎線", "長崎本線", "JR長崎本線", "ＪＲ長崎本線"],
    "佐世保線": ["佐世保線", "JR佐世保線", "ＪＲ佐世保線"],
    "大村線": ["大村線", "JR大村線", "ＪＲ大村線"],
    "久大線": ["久大線", "久大本線", "ゆふ高原線", "JR久大本線", "ＪＲ久大本線"],
    "豊肥線": ["豊肥線", "豊肥本線", "阿蘇高原線", "JR豊肥本線", "ＪＲ豊肥本線"],
    "筑肥線": ["筑肥線", "JR筑肥線", "ＪＲ筑肥線"],
    "唐津線": ["唐津線", "JR唐津線", "ＪＲ唐津線"],
    "筑豊線": ["筑豊線", "筑豊本線", "若松線", "福北ゆたか線", "原田線", "JR筑豊本線", "ＪＲ筑豊本線"],
    "篠栗線": ["篠栗線", "福北ゆたか線", "JR篠栗線", "ＪＲ篠栗線"],
    "香椎線": ["香椎線", "海の中道線", "JR香椎線", "ＪＲ香椎線"],
    "日田彦山線": ["日田彦山線", "JR日田彦山線", "ＪＲ日田彦山線"],
    "後藤寺線": ["後藤寺線", "JR後藤寺線", "ＪＲ後藤寺線"],
    "三角線": ["三角線", "あまくさみすみ線", "JR三角線", "ＪＲ三角線"],
    "肥薩線": ["肥薩線", "えびの高原線", "JR肥薩線", "ＪＲ肥薩線"],
    "吉都線": ["吉都線", "えびの高原線", "JR吉都線", "ＪＲ吉都線"],
    "宮崎空港線": ["宮崎空港線", "JR宮崎空港線", "ＪＲ宮崎空港線"],
    "日南線": ["日南線", "JR日南線", "ＪＲ日南線"],
    "指宿枕崎線": ["指宿枕崎線", "JR指宿枕崎線", "ＪＲ指宿枕崎線"],
    "山陽線": ["山陽線", "山陽本線", "JR山陽本線", "ＪＲ山陽本線"],
}


def main() -> int:
    nav.load_jrcentral_station_orders = lambda cache_dir, refresh=False: {}  # type: ignore[assignment]
    return nav.main()


if __name__ == "__main__":
    raise SystemExit(main())
