#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

from train_instance_merge import index_train_instances, upsert_train_instance


ROOT = Path(__file__).resolve().parents[2]
N02_STATION_PATH = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "data" / "v3_tokyo_tobu_weekday_train_instances.json"
CACHE_DIR = ROOT / "data" / "v3_external" / "tobu"
TIMEOUT = 30
MAX_FETCH_RETRIES = 5
SERVICE_DAY = "2026-04-15"
AUTOCOMPLETE_URL = "https://media.cld.navitime.jp/media/biz/widget/diagram/search/train/autocomplete"
NAVITIME_BASE = "https://www.navitime.co.jp"
CHECKPOINT_TRAINS_EVERY = 100
ROUTE_COLOR = "00529B"


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


def fetch_json(url: str) -> list[dict]:
    path = cache_path(url)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    last_error: Exception | None = None
    for attempt in range(1, MAX_FETCH_RETRIES + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            data = response.json()
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return data
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
        if props.get("N02_004") != "東武鉄道":
            continue
        name = props.get("N02_005")
        if not name or name in out:
            continue
        lon, lat = centroid(feature["geometry"]["coordinates"])
        out[name] = {
            "station_id": f"TOBU_{name}",
            "name_ja": name,
            "operator": "東武鉄道",
            "line_id": props.get("N02_003", ""),
            "lat": round(lat, 8),
            "lon": round(lon, 8),
            "n02_station_code": props.get("N02_005c"),
            "n02_group_code": props.get("N02_005g"),
        }
    return sorted(out.values(), key=lambda item: item["name_ja"])


def normalize_station_name(name: str) -> str:
    text = " ".join(html.unescape(name).replace("\u3000", " ").split())
    text = re.sub(r"[（(].*?[）)]", "", text)
    text = re.sub(r"［.*?］", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = text.replace("ヶ", "ケ")
    text = text.replace("塚", "塚")
    text = text.replace("曾", "曽")
    return text


def normalize_hhmm(value: str) -> str:
    match = re.search(r"(\d{1,2}:\d{2})", value)
    return match.group(1) if match else ""


def hhmm_minutes(value: str) -> int:
    if not value or ":" not in value:
        return 99_999
    hour, minute = value.split(":", 1)
    try:
        total = int(hour) * 60 + int(minute)
    except ValueError:
        return 99_999
    if total < 3 * 60:
        total += 24 * 60
    return total


def discover_navitime_nodes(station_seed: list[dict]) -> list[dict]:
    nodes = []
    seen_nodes: set[str] = set()
    for station in station_seed:
        query = quote(station["name_ja"])
        url = f"{AUTOCOMPLETE_URL}?word={query}"
        try:
            items = fetch_json(url)
        except Exception:
            continue
        target = normalize_station_name(station["name_ja"])
        match = None
        for item in items:
            label = normalize_station_name(item.get("label", ""))
            if (
                label == target
                or label.startswith(target + "(")
                or label.startswith(target + "（")
                or label.startswith(target + "[")
                or label.startswith(target + "［")
            ):
                match = item
                break
        if not match:
            continue
        node_id = match.get("id")
        if not node_id or node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)
        nodes.append(
            {
                "station_name": station["name_ja"],
                "station_id": station["station_id"],
                "node_id": node_id,
            }
        )
    return nodes


def discover_timetable_urls(node_id: str) -> list[str]:
    text = fetch_text(f"{NAVITIME_BASE}/diagram/lineList?node={node_id}")
    urls = []
    seen: set[str] = set()
    for href in re.findall(r'href="([^"]+/diagram/timetable\?[^"]+)"', text):
        url = href
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = NAVITIME_BASE + url
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def discover_stop_urls(timetable_url: str) -> list[str]:
    text = fetch_text(timetable_url)
    urls = []
    seen: set[str] = set()
    for href in re.findall(r'href="([^"]*?/diagram/stops/[^"]+)"', text):
        url = href
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = NAVITIME_BASE + url
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def parse_stop_page(stop_url: str, station_lookup: dict[str, dict]) -> dict | None:
    text = fetch_text(stop_url)
    clean = re.sub(r"<script.*?</script>", " ", text, flags=re.S)
    clean = re.sub(r"<style.*?</style>", " ", clean, flags=re.S)
    clean = re.sub(r"<[^>]+>", "\n", clean)
    clean = html.unescape(clean)
    lines = [re.sub(r"\s+", " ", line).strip() for line in clean.splitlines()]
    lines = [line for line in lines if line]

    title_raw = next((line for line in lines if "の停車駅/時刻表" in line), "")
    title = title_raw.replace("の停車駅/時刻表", "")
    line_name = ""
    if title:
        if "(" in title:
            line_name = title.split("(", 1)[0]
    title_head = next((line for line in lines if ("行き" in line and ("平日" in line or "土休日" in line))), "")
    train_type = ""
    headsign = ""
    if title_head:
        title_head = title_head.replace("（平日）", "").replace("（土休日）", "").strip()
        match = re.match(r"^(.*?行)\s*(.+)$", title_head)
        if match:
            headsign = match.group(1)
            train_type = match.group(2).strip()
        else:
            headsign = title_head

    station_rows = []
    title_inner = title_raw.replace("（", "(").replace("）", ")")
    if "(" in title_inner:
        title_inner = title_inner.split("(", 1)[1]
        current_match = re.match(r"(.+?)(\d{1,2}:\d{2})発", title_inner)
        if current_match:
            current_station_name = normalize_station_name(current_match.group(1))
            current_station = station_lookup.get(current_station_name)
            current_departure = current_match.group(2)
            if current_station is not None:
                station_rows.append((current_station, current_departure, current_departure))
    for i, line in enumerate(lines):
        station = station_lookup.get(normalize_station_name(line))
        if station is None:
            continue
        arrival = ""
        departure = ""
        for nxt in lines[i + 1 : i + 6]:
            hhmm = normalize_hhmm(nxt)
            if not hhmm:
                break
            if not arrival:
                arrival = hhmm
            elif not departure:
                departure = hhmm
                break
        if arrival:
            if not departure:
                departure = arrival
            station_rows.append((station, arrival, departure))
    if len(station_rows) < 2:
        return None

    station_rows.sort(key=lambda row: hhmm_minutes(row[1] or row[2]))

    stop_times = []
    seen_station_ids: set[str] = set()
    for station, arrival, departure in station_rows:
        if station["station_id"] in seen_station_ids:
            continue
        seen_station_ids.add(station["station_id"])
        stop_times.append(
            {
                "sequence": len(stop_times) + 1,
                "station_name_raw": station["name_ja"],
                "station_id": station["station_id"],
                "line_id": station.get("line_id"),
                "arrival_hhmm": arrival,
                "departure_hhmm": departure,
                "platform": None,
            }
        )
    if len(stop_times) < 2:
        return None

    m = re.search(r"/diagram/stops/[^/]+/([^/?]+)/", stop_url)
    train_code = m.group(1) if m else hashlib.sha1(stop_url.encode("utf-8")).hexdigest()[:12]
    params = dict(re.findall(r"[?&]([^=&]+)=([^&]+)", stop_url))
    year = params.get("year", "")
    month = params.get("month", "")
    day = params.get("day", "")
    # Navitime advances the URL date over time; for this collector we normalize
    # the captured weekday pattern into SERVICE_DAY rather than rejecting fresh
    # weekday pages that are otherwise structurally identical.
    return {
        "service_instance_id": f"TOBU_{train_code}_{SERVICE_DAY}",
        "train_number": train_code,
        "service_name": line_name or "Tobu",
        "headsign": headsign,
        "train_type": train_type,
        "route_color": ROUTE_COLOR,
        "stop_times": stop_times,
        "source_url": stop_url,
    }


def write_output(station_seed: list[dict], source_reports: list[dict], train_instances: list[dict], node_seed: list[dict]) -> None:
    payload = {
        "id": "v3_tokyo_tobu_weekday_train_instances_v0_1",
        "label": "v3 Tokyo Tobu weekday train instances",
        "version": "0.1.0",
        "service_day": SERVICE_DAY,
        "station_seed": station_seed,
        "node_seed": node_seed,
        "source_reports": source_reports,
        "train_instances": sorted(
            train_instances,
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
    station_lookup = {normalize_station_name(entry["name_ja"]): entry for entry in station_seed}
    node_seed = discover_navitime_nodes(station_seed)
    only_stations = {
        name.strip()
        for name in os.environ.get("ONLY_STATIONS", "").split(",")
        if name.strip()
    }
    process_node_seed = [
        node for node in node_seed if not only_stations or node["station_name"] in only_stations
    ]

    rebuild = os.environ.get("REBUILD") == "1"
    if OUTPUT_PATH.exists() and not rebuild:
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        source_reports = existing.get("source_reports", [])
        train_instances, instance_index = index_train_instances(existing.get("train_instances", []))
    else:
        source_reports = []
        train_instances = []
        instance_index = {}

    completed_nodes = {report["node_id"] for report in source_reports}
    next_train_checkpoint = ((len(train_instances) // CHECKPOINT_TRAINS_EVERY) + 1) * CHECKPOINT_TRAINS_EVERY

    for idx, node in enumerate(process_node_seed, start=1):
        node_id = node["node_id"]
        if node_id in completed_nodes and node["station_name"] not in only_stations:
            continue
        try:
            timetable_urls = discover_timetable_urls(node_id)
        except Exception as exc:
            source_reports.append(
                {
                    "node_id": node_id,
                    "station_name": node["station_name"],
                    "timetable_count": 0,
                    "new_trains": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            write_output(station_seed, source_reports, train_instances, node_seed)
            print(f"[tobu] node error {idx}/{len(process_node_seed)} {node_id} -> {type(exc).__name__}: {exc}")
            continue

        added = 0
        for timetable_url in timetable_urls:
            try:
                stop_urls = discover_stop_urls(timetable_url)
            except Exception:
                continue
            for stop_url in stop_urls:
                try:
                    parsed = parse_stop_page(stop_url, station_lookup)
                except Exception:
                    continue
                if not parsed:
                    continue
                action = upsert_train_instance(train_instances, instance_index, parsed)
                if action == "added":
                    added += 1
                if len(train_instances) >= next_train_checkpoint:
                    write_output(station_seed, source_reports, train_instances, node_seed)
                    print(f"[tobu] train checkpoint {len(train_instances)} after node {idx}/{len(process_node_seed)}")
                    next_train_checkpoint += CHECKPOINT_TRAINS_EVERY

        source_reports.append(
            {
                "node_id": node_id,
                "station_name": node["station_name"],
                "timetable_count": len(timetable_urls),
                "new_trains": added,
            }
        )
        write_output(station_seed, source_reports, train_instances, node_seed)
        print(f"[tobu] checkpoint {idx}/{len(process_node_seed)}: {len(source_reports)} nodes, {len(train_instances)} trains")

    write_output(station_seed, source_reports, train_instances, node_seed)
    print(f"[tobu] wrote {len(train_instances)} train instances -> {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
