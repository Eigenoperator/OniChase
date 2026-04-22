#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

from merge_train_instance_datasets import merge_datasets
from parse_jreast_train_detail import parse_html as parse_train_detail_html
from train_instance_normalization import normalize_train_instances


ROOT = Path(__file__).resolve().parents[2]
STATIONS_PATH = ROOT / "data" / "v3_jreast_station_seed.json"
YAMANOTE_PATH = ROOT / "data" / "yamanote_weekday_train_instances_merged.json"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_jreast_core_weekday_train_instances.json"
REPORT_PATH = ROOT / "data" / "v3_tokyo_jreast_core_timetable_links.json"
CACHE_DIR = ROOT / "data" / "v3_tokyo_jreast_core_cache"
ALLOWED_TRAIN_TYPES = {
    None,
    "",
    "Local",
    "Rapid",
    "Chuo Special Rapid",
    "Commuter Rapid",
    "Special Rapid",
    "Ome Special Rapid",
    "Commuter Special Rapid",
}


TIMETABLE_PAGES = [
    {
        "station_name": "Tokyo",
        "title": "Keiyo・Musashino Line",
        "line_id": "JR_EAST_KEIYO_MUSASHINO",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1039/1039070.html",
    },
    {
        "station_name": "Tokyo",
        "title": "Sobu Line (Rapid)",
        "line_id": "JR_EAST_SOBU_RAPID",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1039/1039080.html",
    },
    {
        "station_name": "Tokyo",
        "title": "Chuo Line (Rapid)",
        "line_id": "JR_EAST_CHUO_RAPID",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1039/1039090.html",
    },
    {
        "station_name": "Tokyo",
        "title": "Tokaido Line (Ueno-Tokyo Line)",
        "line_id": "JR_EAST_TOKAIDO",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1039/1039100.html",
    },
    {
        "station_name": "Tokyo",
        "title": "Ueno-Tokyo Line (Joban Line)",
        "line_id": "JR_EAST_UENO_TOKYO",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1039/1039170.html",
    },
    {
        "station_name": "Tokyo",
        "title": "Yokosuka Line",
        "line_id": "JR_EAST_YOKOSUKA",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1039/1039130.html",
    },
    {
        "station_name": "Tokyo",
        "title": "Keihin-Tohoku・Negishi Line",
        "line_id": "JR_EAST_KEIHIN_TOHOKU_NEGISHI",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1039/1039140.html",
    },
    {
        "station_name": "Tokyo",
        "title": "Keihin-Tohoku・Negishi Line",
        "line_id": "JR_EAST_KEIHIN_TOHOKU_NEGISHI",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1039/1039150.html",
    },
    {
        "station_name": "Shinjuku",
        "title": "Saikyo・Kawagoe Line",
        "line_id": "JR_EAST_SAIKYO_KAWAGOE",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0866/0866010.html",
    },
    {
        "station_name": "Shinjuku",
        "title": "Saikyo・Kawagoe Line",
        "line_id": "JR_EAST_SAIKYO_KAWAGOE",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0866/0866020.html",
    },
    {
        "station_name": "Shinjuku",
        "title": "Chuo・Sobu Line (Local)",
        "line_id": "JR_EAST_CHUO_SOBU_LOCAL",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0866/0866030.html",
    },
    {
        "station_name": "Shinjuku",
        "title": "Chuo・Sobu Line (Local)",
        "line_id": "JR_EAST_CHUO_SOBU_LOCAL",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0866/0866040.html",
    },
    {
        "station_name": "Shinjuku",
        "title": "Chuo Line (Rapid)",
        "line_id": "JR_EAST_CHUO_RAPID",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0866/0866060.html",
    },
    {
        "station_name": "Shinjuku",
        "title": "Chuo Line (Rapid)",
        "line_id": "JR_EAST_CHUO_RAPID",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0866/0866070.html",
    },
    {
        "station_name": "Shinjuku",
        "title": "Shonan-Shinjuku Line",
        "line_id": "JR_EAST_SHONAN_SHINJUKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0866/0866080.html",
    },
    {
        "station_name": "Shinjuku",
        "title": "Shonan-Shinjuku Line",
        "line_id": "JR_EAST_SHONAN_SHINJUKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0866/0866090.html",
    },
    {
        "station_name": "Ueno",
        "title": "Joban Line (Rapid)",
        "line_id": "JR_EAST_JOBAN_RAPID",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0204/0204070.html",
    },
    {
        "station_name": "Ueno",
        "title": "Ueno-Tokyo Line",
        "line_id": "JR_EAST_UENO_TOKYO",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0204/0204140.html",
    },
    {
        "station_name": "Shinagawa",
        "title": "Tokaido Line",
        "line_id": "JR_EAST_TOKAIDO",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0788/0788030.html",
    },
    {
        "station_name": "Shinagawa",
        "title": "Tokaido Line (Ueno-Tokyo Line)",
        "line_id": "JR_EAST_TOKAIDO",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0788/0788040.html",
    },
    {
        "station_name": "Shinagawa",
        "title": "Ueno-Tokyo Line (Joban Line)",
        "line_id": "JR_EAST_UENO_TOKYO",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0788/0788110.html",
    },
    {
        "station_name": "Shinagawa",
        "title": "Yokosuka Line",
        "line_id": "JR_EAST_YOKOSUKA",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0788/0788070.html",
    },
    {
        "station_name": "Shinagawa",
        "title": "Yokosuka Line",
        "line_id": "JR_EAST_YOKOSUKA",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0788/0788080.html",
    },
    {
        "station_name": "Yokohama",
        "title": "Tokaido Line",
        "line_id": "JR_EAST_TOKAIDO",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1638/1638010.html",
    },
    {
        "station_name": "Yokohama",
        "title": "Tokaido Line (Ueno-Tokyo Line)",
        "line_id": "JR_EAST_TOKAIDO",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1638/1638020.html",
    },
    {
        "station_name": "Yokohama",
        "title": "Shonan-Shinjuku Line",
        "line_id": "JR_EAST_SHONAN_SHINJUKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1638/1638030.html",
    },
    {
        "station_name": "Yokohama",
        "title": "Shonan-Shinjuku Line",
        "line_id": "JR_EAST_SHONAN_SHINJUKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1638/1638040.html",
    },
    {
        "station_name": "Yokohama",
        "title": "Yokosuka Line",
        "line_id": "JR_EAST_YOKOSUKA",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1638/1638060.html",
    },
    {
        "station_name": "Yokohama",
        "title": "Yokosuka Line",
        "line_id": "JR_EAST_YOKOSUKA",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table1638/1638070.html",
    },
    {
        "station_name": "Chiba",
        "title": "Sobu・Narita Line",
        "line_id": "JR_NARITA",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0989/0989010.html",
    },
    {
        "station_name": "Chiba",
        "title": "Uchibo Line",
        "line_id": "JR_UCHIBO",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0989/0989020.html",
    },
    {
        "station_name": "Chiba",
        "title": "Sotobo Line",
        "line_id": "JR_SOTOBO",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0989/0989030.html",
    },
    {
        "station_name": "Chiba",
        "title": "Sobu Line (Rapid)",
        "line_id": "JR_EAST_SOBU_RAPID",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0989/0989040.html",
    },
    {
        "station_name": "Chiba",
        "title": "Chuo・Sobu Line (Local)",
        "line_id": "JR_EAST_CHUO_SOBU_LOCAL",
        "timetable_url": "https://timetables.jreast.co.jp/en/timetable/table0989/0989050.html",
    },
    {
        "station_name": "Tachikawa",
        "title": "Ome・Itsukaichi Line",
        "line_id": "JR_OME",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0958/0958030.html",
    },
    {
        "station_name": "Ome",
        "title": "Ome Line",
        "line_id": "JR_OME",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0303/0303010.html",
    },
    {
        "station_name": "Oku-Tama",
        "title": "Ome Line",
        "line_id": "JR_OME",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0368/0368010.html",
    },
    {
        "station_name": "Takasaki",
        "title": "Joetsu Line",
        "line_id": "JR_JOETSU_LOCAL",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0934/0934050.html",
    },
    {
        "station_name": "Minakami",
        "title": "Joetsu Line",
        "line_id": "JR_JOETSU_LOCAL",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt1474/1474010.html",
    },
    {
        "station_name": "Takasaki",
        "title": "Ryomo Line",
        "line_id": "JR_RYOMO",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0934/0934090.html",
    },
    {
        "station_name": "Omiya",
        "title": "Utsunomiya Line (Tohoku Line)",
        "line_id": "JR_TOHOKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0350/0350070.html",
    },
    {
        "station_name": "Utsunomiya",
        "title": "Utsunomiya Line (Tohoku Line)",
        "line_id": "JR_TOHOKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0248/0248050.html",
    },
    {
        "station_name": "Utsunomiya",
        "title": "Utsunomiya Line (Tohoku Line)",
        "line_id": "JR_TOHOKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0248/0248060.html",
    },
    {
        "station_name": "Kuroiso",
        "title": "Tohoku Line",
        "line_id": "JR_TOHOKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0638/0638010.html",
    },
    {
        "station_name": "Kuroiso",
        "title": "Utsunomiya Line (Tohoku Line)",
        "line_id": "JR_TOHOKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0638/0638020.html",
    },
    {
        "station_name": "Koriyama",
        "title": "Tohoku Line",
        "line_id": "JR_TOHOKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0675/0675050.html",
    },
    {
        "station_name": "Koriyama",
        "title": "Tohoku Line",
        "line_id": "JR_TOHOKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0675/0675060.html",
    },
    {
        "station_name": "Fukushima",
        "title": "Tohoku Line",
        "line_id": "JR_TOHOKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt1352/1352040.html",
    },
    {
        "station_name": "Fukushima",
        "title": "Tohoku Line",
        "line_id": "JR_TOHOKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt1352/1352050.html",
    },
    {
        "station_name": "Sendai",
        "title": "Tohoku Line",
        "line_id": "JR_TOHOKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0913/0913080.html",
    },
    {
        "station_name": "Sendai",
        "title": "Tohoku Line",
        "line_id": "JR_TOHOKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0913/0913090.html",
    },
    {
        "station_name": "Morioka",
        "title": "Tohoku Line",
        "line_id": "JR_TOHOKU",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt1565/1565040.html",
    },
    {
        "station_name": "Mito",
        "title": "Joban Line",
        "line_id": "JR_JOBAN",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt1471/1471010.html",
    },
    {
        "station_name": "Mito",
        "title": "Joban Line",
        "line_id": "JR_JOBAN",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt1471/1471020.html",
    },
    {
        "station_name": "Iwaki",
        "title": "Joban Line",
        "line_id": "JR_JOBAN",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0166/0166010.html",
    },
    {
        "station_name": "Iwaki",
        "title": "Joban Line",
        "line_id": "JR_JOBAN",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0166/0166020.html",
    },
    {
        "station_name": "Haranomachi",
        "title": "Joban Line",
        "line_id": "JR_JOBAN",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt1259/1259010.html",
    },
    {
        "station_name": "Haranomachi",
        "title": "Joban Line",
        "line_id": "JR_JOBAN",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt1259/1259020.html",
    },
    {
        "station_name": "Sendai",
        "title": "Joban Line",
        "line_id": "JR_JOBAN",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0913/0913040.html",
    },
    {
        "station_name": "Kobuchizawa",
        "title": "Chuo Line",
        "line_id": "JR_CHUO",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0707/0707020.html",
    },
    {
        "station_name": "Kobuchizawa",
        "title": "Chuo Line",
        "line_id": "JR_CHUO",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0707/0707030.html",
    },
    {
        "station_name": "Kami-Suwa",
        "title": "Chuo Line",
        "line_id": "JR_CHUO",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0492/0492010.html",
    },
    {
        "station_name": "Kami-Suwa",
        "title": "Chuo Line",
        "line_id": "JR_CHUO",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0492/0492020.html",
    },
    {
        "station_name": "Shinano-Kawashima",
        "title": "Chuo Line",
        "line_id": "JR_CHUO",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0792/0792010.html",
    },
    {
        "station_name": "Shinano-Kawashima",
        "title": "Chuo Line",
        "line_id": "JR_CHUO",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0792/0792020.html",
    },
    {
        "station_name": "Ono",
        "title": "Chuo Line",
        "line_id": "JR_CHUO",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0389/0389010.html",
    },
    {
        "station_name": "Ono",
        "title": "Chuo Line",
        "line_id": "JR_CHUO",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0389/0389020.html",
    },
    {
        "station_name": "Kawagoe",
        "title": "Kawagoe Line",
        "line_id": "JR_KAWAGOE",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0525/0525010.html",
    },
    {
        "station_name": "Kawagoe",
        "title": "Saikyo・Kawagoe Line",
        "line_id": "JR_EAST_SAIKYO_KAWAGOE",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0525/0525020.html",
    },
    {
        "station_name": "Tateyama",
        "title": "Uchibo Line",
        "line_id": "JR_UCHIBO",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0969/0969010.html",
    },
    {
        "station_name": "Tateyama",
        "title": "Uchibo Line",
        "line_id": "JR_UCHIBO",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0969/0969020.html",
    },
    {
        "station_name": "Takagimachi",
        "title": "Senseki Line",
        "line_id": "JR_SENSEKI",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0932/0932010.html",
    },
    {
        "station_name": "Takagimachi",
        "title": "Senseki Line",
        "line_id": "JR_SENSEKI",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0932/0932020.html",
    },
    {
        "station_name": "Kashimajingu",
        "title": "Kashima Line",
        "line_id": "JR_KASHIMA",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0431/0431010.html",
    },
    {
        "station_name": "Kashimajingu",
        "title": "Kashima Line",
        "line_id": "JR_KASHIMA",
        "timetable_url": "https://timetables.jreast.co.jp/en/2605/timetable/tt0431/0431020.html",
    },
]


def fetch_html(url: str, retries: int = 5) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; Codex OniChase V3 JR Builder)"},
    )
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt == retries:
                raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == retries:
                raise
        sleep_seconds = min(10, attempt * 2)
        print(f"  retry {attempt}/{retries} for {url} after error: {last_error}", flush=True)
        time.sleep(sleep_seconds)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def normalize_timetable_url(url: str) -> str:
    if "/en/timetable/table" in url:
        return re.sub(r"/en/timetable/table(\d{4})/", r"/en/2604/timetable/tt\1/", url)
    return url


def extract_train_links_from_timetable_page(html: str, page_url: str) -> list[str]:
    links = []
    seen = set()
    for href in re.findall(r'href="([^"]+/train/[^"]+)"', html):
        full_url = urllib.parse.urljoin(page_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        links.append(full_url)
    return links


def cache_path_for_page(page: dict[str, str]) -> Path:
    stem = Path(page["timetable_url"]).stem
    return CACHE_DIR / f"{page['line_id'].lower()}_{page['station_name'].lower()}_{stem}.json"


def collect_dataset(page: dict[str, str], delay_seconds: float = 0.02) -> tuple[dict[str, object], dict[str, object]]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = cache_path_for_page(page)
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        cached["dataset"]["train_instances"] = [
            train for train in cached["dataset"]["train_instances"]
            if train.get("train_type") in ALLOWED_TRAIN_TYPES
        ]
        cached["report"]["kept_instance_count"] = len(cached["dataset"]["train_instances"])
        print(
            f"[cache] {page['station_name']} | {page['title']} | details={cached['report']['train_detail_count']}",
            flush=True,
        )
        return cached["dataset"], cached["report"]

    timetable_url = normalize_timetable_url(page["timetable_url"])
    timetable_html = fetch_html(timetable_url)
    train_links = extract_train_links_from_timetable_page(timetable_html, timetable_url)
    print(
        f"[collect] {page['station_name']} | {page['title']} | details={len(train_links)}",
        flush=True,
    )

    raw_instances = []
    for index, train_url in enumerate(train_links, start=1):
        train_html = fetch_html(train_url)
        parsed = parse_train_detail_html(train_html, train_url, line_id=page["line_id"])
        raw_instances.extend(parsed["train_instances"])
        if index % 50 == 0 or index == len(train_links):
            print(
                f"  fetched {index}/{len(train_links)} detail pages for {page['title']}",
                flush=True,
            )
        time.sleep(delay_seconds)

    dataset = {
        "id": f"{page['line_id'].lower()}_{page['station_name'].lower()}_{Path(page['timetable_url']).stem}",
        "label": page["title"],
        "source_station_name": page["station_name"],
        "source_timetable_url": timetable_url,
        "line_id": page["line_id"],
        "train_instances": [
            train for train in raw_instances
            if train.get("train_type") in ALLOWED_TRAIN_TYPES
        ],
    }
    report_item = {
        "station_name": page["station_name"],
        "timetable_url": timetable_url,
        "title": page["title"],
        "line_id": page["line_id"],
        "train_detail_count": len(train_links),
        "raw_instance_count": len(raw_instances),
        "kept_instance_count": len(dataset["train_instances"]),
    }
    cache_path.write_text(
        json.dumps({"dataset": dataset, "report": report_item}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return dataset, report_item


def main() -> int:
    stations_data = json.loads(STATIONS_PATH.read_text(encoding="utf-8"))
    yamanote_dataset = json.loads(YAMANOTE_PATH.read_text(encoding="utf-8"))

    raw_datasets = [
        {
            "id": yamanote_dataset["id"],
            "label": yamanote_dataset["label"],
            "line_id": "JR_EAST_YAMANOTE",
            "train_instances": yamanote_dataset["train_instances"],
        }
    ]
    selected_pages = [
        {
            "station_name": "Prebuilt",
            "timetable_url": str(YAMANOTE_PATH.relative_to(ROOT)),
            "title": "Yamanote Line merged weekday dataset",
            "line_id": "JR_EAST_YAMANOTE",
            "train_detail_count": 0,
            "raw_instance_count": len(yamanote_dataset["train_instances"]),
        }
    ]

    for page in TIMETABLE_PAGES:
        dataset, report_item = collect_dataset(page)
        raw_datasets.append(dataset)
        selected_pages.append(report_item)

    normalized_datasets = []
    unresolved_total = set()
    for dataset in raw_datasets:
        normalized_instances, unresolved = normalize_train_instances(dataset["train_instances"], stations_data)
        normalized_instances = [
            train for train in normalized_instances
            if len(train.get("stop_times", [])) >= 2
        ]
        unresolved_total.update(unresolved)
        normalized_datasets.append(
            {
                **{k: v for k, v in dataset.items() if k != "train_instances"},
                "train_instances": normalized_instances,
            }
        )

    if unresolved_total:
        print(
            "Warning: unresolved station names skipped: "
            + ", ".join(sorted(unresolved_total)[:80])
            + (f" ... (+{len(unresolved_total) - 80} more)" if len(unresolved_total) > 80 else ""),
            flush=True,
        )

    merged_by_key, merge_report = merge_datasets(normalized_datasets)
    merged_instances = sorted(
        merged_by_key.values(),
        key=lambda train: (
            train.get("stop_times", [{}])[0].get("departure_hhmm")
            or train.get("stop_times", [{}])[0].get("arrival_hhmm")
            or "99:99",
            train["train_number"],
        ),
    )

    output = {
        "id": "v3_tokyo_jreast_core_weekday_train_instances_v0_1",
        "label": "V3 Tokyo core JR East weekday train instances from official JR East timetables",
        "version": "0.1.0",
        "service_day": "weekday",
        "station_seed_id": stations_data["id"],
        "selected_timetable_pages": selected_pages,
        "source_dataset_ids": [dataset["id"] for dataset in normalized_datasets],
        "unresolved_station_names": sorted(unresolved_total),
        "merge_report": merge_report,
        "train_instances": merged_instances,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps({"selected_timetable_pages": selected_pages}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Selected timetable pages: {len(selected_pages)}")
    print(f"Merged train instances: {len(merged_instances)}")
    print(f"Wrote: {OUTPUT_PATH}")
    print(f"Wrote: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
