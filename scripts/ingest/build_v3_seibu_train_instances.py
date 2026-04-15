#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests


ROOT = Path(__file__).resolve().parents[2]
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_seibu_weekday_train_instances.json"
CACHE_DIR = ROOT / "data" / "v3_external" / "seibu"
TIMEOUT = 30
MAX_FETCH_RETRIES = 5
SERVICE_DAY = "2026-04-15"
OFFICIAL_INDEX_URL = "https://seibu.ekitan.com/english/timetable"
BASE_URL = "https://seibu.ekitan.com"
CHECKPOINT_EVERY = 1
CHECKPOINT_TRAINS_EVERY = 100
ROUTE_COLOR = "005BAC"


def cache_path(url: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"


def fetch_text(url: str) -> str:
    path = cache_path(url)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    last_error: Exception | None = None
    for attempt in range(1, MAX_FETCH_RETRIES + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            path.write_text(response.text, encoding="utf-8")
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_FETCH_RETRIES:
                break
            time.sleep(min(2 * attempt, 10))
    assert last_error is not None
    raise last_error


def centroid(coords: list) -> tuple[float, float]:
    points: list[tuple[float, float]] = []

    def walk(node: list) -> None:
        if not node:
            return
        if isinstance(node[0], (int, float)):
            points.append((float(node[0]), float(node[1])))
            return
        for child in node:
            walk(child)

    walk(coords)
    lon = sum(p[0] for p in points) / len(points)
    lat = sum(p[1] for p in points) / len(points)
    return lon, lat


def load_station_seed() -> list[dict]:
    geojson = json.loads(N02_STATION_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for feature in geojson["features"]:
        props = feature["properties"]
        if props.get("N02_004") != "西武鉄道":
            continue
        name = props.get("N02_005")
        if not name or name in out:
            continue
        lon, lat = centroid(feature["geometry"]["coordinates"])
        out[name] = {
            "station_id": f"SEIBU_{name}",
            "name_ja": name,
            "operator": "西武鉄道",
            "line_id": props.get("N02_003", ""),
            "lat": round(lat, 8),
            "lon": round(lon, 8),
            "n02_station_code": props.get("N02_005c"),
            "n02_group_code": props.get("N02_005g"),
        }
    return sorted(out.values(), key=lambda item: item["name_ja"])


def normalize_station_name(name: str) -> str:
    text = " ".join(html.unescape(name).replace("\u3000", " ").split())
    text = text.replace("ヶ", "ケ")
    return text


def normalize_hhmm(value: str) -> str:
    value = " ".join(value.split())
    match = re.search(r"(\d{1,2}:\d{2})", value)
    return match.group(1) if match else ""


def discover_station_pages() -> list[str]:
    text = fetch_text(OFFICIAL_INDEX_URL)
    matches = sorted(set(re.findall(r"/english/timetable/station/\d+-\d+/d[12]", text)))
    return [urljoin(BASE_URL, match + "?dw=0") for match in matches]


def discover_detail_urls(station_page_url: str) -> list[str]:
    text = fetch_text(station_page_url.replace("/english/", "/norikae/"))
    urls = []
    seen: set[str] = set()
    for tx, sf, date, minute, dw in re.findall(
        r"openOneTrainTimetable\('([^']+)','([^']+)','([^']+)','([^']+)','([^']+)'\s*\)",
        text,
    ):
        url = (
            f"{BASE_URL}/norikae/timetable/onetraintimetable/"
            f"?tx={tx}&sf={sf}&date={date}&time={minute}&dw={dw}"
        )
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def parse_headsign_and_type(raw: str) -> tuple[str, str]:
    text = " ".join(raw.split())
    text = text.replace("（平日）", "").replace("（土休日）", "").strip()
    match = re.match(r"^(.*?行き)\s+(.+)$", text)
    if match:
        return match.group(1), match.group(2)
    return "", text


def parse_detail_page(detail_url: str, station_lookup: dict[str, dict]) -> dict | None:
    text = fetch_text(detail_url)
    route_match = re.search(r"<h3><span>(.*?)</span></h3>", text, re.S)
    title_match = re.search(r"<h3><span>.*?</span></h3>\s*<h3><span>(.*?)</span></h3>", text, re.S)
    route_text = normalize_station_name(re.sub(r"<.*?>", " ", route_match.group(1))) if route_match else ""
    title_text = normalize_station_name(re.sub(r"<.*?>", " ", title_match.group(1))) if title_match else ""
    headsign, train_type = parse_headsign_and_type(title_text)

    table_match = re.search(r"<table>\s*<tbody>(.*?)</tbody>\s*</table>", text, re.S)
    if not table_match:
        return None

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), re.S)
    stop_times = []
    for row in rows[1:]:
        cols = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cols) != 3:
            continue
        station_name = normalize_station_name(re.sub(r"<.*?>", " ", cols[0]))
        station = station_lookup.get(station_name)
        if station is None:
            continue
        arrival = normalize_hhmm(re.sub(r"<.*?>", " ", cols[1]))
        departure = normalize_hhmm(re.sub(r"<.*?>", " ", cols[2]))
        if not arrival:
            arrival = departure
        if not departure:
            departure = arrival
        stop_times.append(
            {
                "sequence": len(stop_times) + 1,
                "station_name_raw": station_name,
                "station_id": station["station_id"],
                "line_id": station.get("line_id"),
                "arrival_hhmm": arrival,
                "departure_hhmm": departure,
                "platform": None,
            }
        )

    if len(stop_times) < 2:
        return None

    params = dict(re.findall(r"[?&]([^=&]+)=([^&]+)", detail_url))
    if params.get("date") and params.get("date") != SERVICE_DAY.replace("-", ""):
        return None
    train_number = params.get("tx") or params.get("sf", hashlib.sha1(detail_url.encode("utf-8")).hexdigest()[:12])
    service_instance_id = f"SEIBU_{train_number}_{SERVICE_DAY}"

    return {
        "service_instance_id": service_instance_id,
        "train_number": train_number,
        "service_name": "Seibu",
        "headsign": headsign or route_text.split(" - ")[-1] if route_text else "",
        "train_type": train_type,
        "route_color": ROUTE_COLOR,
        "stop_times": stop_times,
        "source_url": detail_url,
    }


def write_output(station_seed: list[dict], source_reports: list[dict], train_instances: list[dict]) -> None:
    deduped: dict[str | tuple, dict] = {}
    for item in train_instances:
        stop_times = item.get("stop_times", [])
        if not stop_times:
            continue
        key = item.get("train_number") or (
            item.get("service_name"),
            item.get("headsign"),
            item.get("train_type"),
            stop_times[0].get("departure_hhmm", ""),
            stop_times[-1].get("arrival_hhmm", ""),
            tuple((s.get("station_id"), s.get("arrival_hhmm"), s.get("departure_hhmm")) for s in stop_times),
        )
        existing = deduped.get(key)
        if existing is None or len(stop_times) > len(existing.get("stop_times", [])):
            deduped[key] = item
    payload = {
        "id": "v3_tokyo_seibu_weekday_train_instances_v0_1",
        "label": "v3 Tokyo Seibu weekday train instances",
        "version": "0.1.0",
        "service_day": SERVICE_DAY,
        "station_seed": station_seed,
        "source_reports": source_reports,
        "train_instances": sorted(
            deduped.values(),
            key=lambda item: (
                item["stop_times"][0]["departure_hhmm"],
                item["train_number"],
                item["service_instance_id"],
            ),
        ),
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    station_seed = load_station_seed()
    station_lookup = {entry["name_ja"]: entry for entry in station_seed}
    station_pages = discover_station_pages()

    if OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        source_reports = existing.get("source_reports", [])
        train_instances: list[dict] = existing.get("train_instances", [])
    else:
        source_reports = []
        train_instances = []

    seen_instances: set[str] = {item["service_instance_id"] for item in train_instances}
    completed_station_pages = {report["station_page"] for report in source_reports}
    next_train_checkpoint = ((len(train_instances) // CHECKPOINT_TRAINS_EVERY) + 1) * CHECKPOINT_TRAINS_EVERY

    for station_index, station_page in enumerate(station_pages, start=1):
        if station_page in completed_station_pages:
            continue
        try:
            detail_urls = discover_detail_urls(station_page)
        except Exception as exc:
            source_reports.append(
                {
                    "station_page": station_page,
                    "detail_count": 0,
                    "new_trains": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            write_output(station_seed, source_reports, train_instances)
            print(
                f"[seibu] station error {station_index}/{len(station_pages)} "
                f"{station_page} -> {type(exc).__name__}: {exc}"
            )
            continue
        added = 0
        for detail_url in detail_urls:
            try:
                parsed = parse_detail_page(detail_url, station_lookup)
            except Exception:
                continue
            if not parsed or parsed["service_instance_id"] in seen_instances:
                continue
            seen_instances.add(parsed["service_instance_id"])
            train_instances.append(parsed)
            added += 1
            if len(train_instances) >= next_train_checkpoint:
                write_output(station_seed, source_reports, train_instances)
                print(
                    f"[seibu] train checkpoint {len(train_instances)} "
                    f"after station {station_index}/{len(station_pages)}"
                )
                next_train_checkpoint += CHECKPOINT_TRAINS_EVERY

        source_reports.append(
            {
                "station_page": station_page,
                "detail_count": len(detail_urls),
                "new_trains": added,
            }
        )
        if station_index % CHECKPOINT_EVERY == 0:
            write_output(station_seed, source_reports, train_instances)
            print(
                f"[seibu] checkpoint {station_index}/{len(station_pages)}: "
                f"{len(source_reports)} source pages, {len(train_instances)} trains"
            )

    write_output(station_seed, source_reports, train_instances)
    print(f"[seibu] wrote {len(train_instances)} train instances -> {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
