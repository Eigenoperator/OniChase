#!/usr/bin/env python3
"""Collect Odate-Noshiro Airport official limousine-bus timetable."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "odate_noshiro_airport"
DEFAULT_OUTPUT = ROOT / "data" / "v5_odate_noshiro_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_odate_noshiro_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_odate_noshiro_airport_official_bus_audit.json"

AIRPORT_PAGE_URL = "https://onj-airterminal.com/bus/"
OPERATOR_PAGE_URL = "https://shuhokubus-gr.co.jp/taxi/limousine.html"
OPERATOR_BASE_URL = "https://shuhokubus-gr.co.jp/taxi/"
KML_URL = "https://www.google.com/maps/d/u/0/kml?mid=z9WuJAM-0_64.kXRZAwX4g6tQ&forcekml=1"
JSON_PATHS = {
    "outbound": "json/outbound.json",
    "inbound": "json/inbound.json",
    "flights": "json/flights.json",
    "periods": "json/periods.json",
}

ROUTE_CODE = "odate_noshiro_airport_limousine"
SERVICE_DAYS = "daily"
AIRPORT_IATA = "ONJ"

STOP_COORD_ALIASES = {
    "大館市役所前": ["大館市役所前", "始発:大館市役所", "18.大館市役所前"],
    "大館鳳鳴高校前": ["大館鳳鳴高校前"],
    "城南小学校前": ["城南小学校前"],
    "風呂屋町": ["風呂屋町"],
    "長倉町": ["長倉町"],
    "末広町": ["末広町"],
    "看護福祉大前": ["看護福祉大前"],
    "大館駅前": ["大館駅前", "大館駅前（1番乗降場)"],
    "中道一丁目": ["中道一丁目", "中道１丁目"],
    "清水四丁目": ["清水四丁目", "清水４丁目"],
    "大館桂桜高校前": ["大館桂桜高校前"],
    "餅田": ["餅田"],
    "中立花": ["中立花"],
    "山瀬小学校前": ["山瀬小学校前"],
    "谷地の平団地前": ["谷地の平団地前"],
    "早口": ["早口"],
    "糠沢": ["糠沢"],
    "いとく鷹巣SC前": ["いとく鷹巣SC前", "いとく鷹巣ショッピングセンター前", "いとく鷹巣ショッピングセンター"],
    "鷹巣駅前": ["鷹巣駅前"],
    "北秋田振興局前": ["北秋田振興局前", "北秋田地域振興局前"],
    "病院前": ["病院前"],
    "大館能代空港": ["大館能代空港", "終点.大館能代空港", "始発.大館能代空港"],
}


def cache_path_for(cache_dir: Path, url: str, suffix: str | None = None) -> Path:
    parsed_suffix = suffix or Path(urllib.parse.urlparse(url).path).suffix or ".html"
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}{parsed_suffix}"


def fetch(url: str, cache_dir: Path, *, refresh: bool, timeout: int, suffix: str | None = None) -> Path:
    path = cache_path_for(cache_dir, url, suffix)
    if path.exists() and not refresh:
        return path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_name(value: str) -> str:
    text = html.unescape(str(value or "")).strip()
    text = re.sub(r"^[往復]?\d+[.．、]?", "", text)
    text = re.sub(r"^(始発|終点)[:：.]?", "", text)
    text = text.replace("１", "一").replace("４", "四")
    text = text.replace("ショッピングセンター", "SC")
    text = re.sub(r"[\\s　（）()・]", "", text)
    return text


def parse_kml_points(path: Path) -> dict[str, dict[str, Any]]:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    raw_points: dict[str, dict[str, Any]] = {}
    for placemark in root.findall(".//k:Placemark", ns):
        name = placemark.findtext("k:name", default="", namespaces=ns).strip()
        coordinates = placemark.findtext(".//k:Point/k:coordinates", default="", namespaces=ns).strip()
        if not name or not coordinates:
            continue
        lon_text, lat_text, *_ = coordinates.split(",")
        raw_points[name] = {
            "lat": float(lat_text),
            "lon": float(lon_text),
            "coordinateSource": f"official_google_mymaps:{name}",
        }

    resolved: dict[str, dict[str, Any]] = {}
    normalized_index = {normalize_name(name): value for name, value in raw_points.items()}
    for stop_name, candidates in STOP_COORD_ALIASES.items():
        for candidate in candidates:
            key = normalize_name(candidate)
            if key in normalized_index:
                resolved[stop_name] = normalized_index[key]
                break
        if stop_name not in resolved:
            target = normalize_name(stop_name)
            for raw_name, value in raw_points.items():
                raw_key = normalize_name(raw_name)
                if target in raw_key or raw_key in target:
                    resolved[stop_name] = value
                    break
    return resolved


def parse_time_seconds(value: str) -> int:
    hour, minute = [int(part) for part in value.split(":", 1)]
    return hour * 3600 + minute * 60


def format_time(seconds: int) -> str:
    seconds %= 24 * 3600
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}"


def current_period(periods_payload: dict[str, Any]) -> dict[str, Any]:
    today = datetime.now(UTC).date().isoformat()
    periods = periods_payload.get("periods") or []
    for period in periods:
        if str(period.get("validFrom") or "") <= today <= str(period.get("validTo") or ""):
            return period
    if not periods:
        raise ValueError("No Odate-Noshiro timetable periods found.")
    return periods[-1]


def fare_for(fares: list[dict[str, Any]], *, period_id: str, from_stop_id: str, to_stop_id: str) -> int | None:
    for fare in fares:
        if fare.get("periodId") == period_id and fare.get("from") == from_stop_id and fare.get("to") == to_stop_id:
            return int(fare["adult"])
    return None


def make_trip(direction: str, flight: dict[str, Any], stops: list[dict[str, Any]], index: int, period: dict[str, Any]) -> dict[str, Any]:
    anchor_seconds = parse_time_seconds(flight["time"]) + int(flight.get("offset") or 0) * 60
    stop_times = [
        {
            "stopName": stop["name"],
            "time": format_time(anchor_seconds + int(stop.get("offset") or 0) * 60),
        }
        for stop in stops
    ]
    return {
        "tripId": f"odate_noshiro_airport:{direction}:{index:03d}",
        "direction": direction,
        "serviceStart": str(period["validFrom"]).replace("-", ""),
        "serviceEnd": str(period["validTo"]).replace("-", ""),
        "serviceDays": SERVICE_DAYS,
        "sourceFlight": flight.get("flight"),
        "stopTimes": stop_times,
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cache_paths = [
        fetch(AIRPORT_PAGE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout, suffix=".html"),
        fetch(OPERATOR_PAGE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout, suffix=".html"),
        fetch(KML_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout, suffix=".kml"),
    ]
    json_payloads = {}
    for key, relative_path in JSON_PATHS.items():
        url = urllib.parse.urljoin(OPERATOR_BASE_URL, relative_path)
        path = fetch(url, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout, suffix=".json")
        cache_paths.append(path)
        json_payloads[key] = read_json(path)

    period = current_period(json_payloads["periods"])
    period_id = period["id"]
    outbound_flights = [row for row in json_payloads["flights"]["departures"] if row.get("periodId") == period_id]
    inbound_flights = [row for row in json_payloads["flights"]["arrivals"] if row.get("periodId") == period_id]
    if not outbound_flights or not inbound_flights:
        raise ValueError(f"No current ONJ flights for period {period_id}")

    point_index = parse_kml_points(cache_paths[2])
    all_stop_names = []
    for payload_key in ["outbound", "inbound"]:
        for stop in json_payloads[payload_key]["stops"]:
            if stop["name"] not in all_stop_names:
                all_stop_names.append(stop["name"])
    missing_coords = [name for name in all_stop_names if name not in point_index]
    if missing_coords:
        raise ValueError(f"Missing coordinates for ONJ stops: {missing_coords}")

    outbound_stops = json_payloads["outbound"]["stops"]
    inbound_stops = json_payloads["inbound"]["stops"]
    trips = []
    for index, flight in enumerate(outbound_flights, start=1):
        trips.append(make_trip("to_airport", flight, outbound_stops, index, period))
    for index, flight in enumerate(inbound_flights, start=1):
        trips.append(make_trip("from_airport", flight, inbound_stops, index, period))

    outbound_fare = fare_for(
        json_payloads["outbound"]["fares"],
        period_id=period_id,
        from_stop_id="odate-station",
        to_stop_id="airport",
    )
    inbound_fare = fare_for(
        json_payloads["inbound"]["fares"],
        period_id=period_id,
        from_stop_id="airport",
        to_stop_id="odate-station",
    )
    adult_fare = max(fare for fare in [outbound_fare, inbound_fare] if fare is not None)

    route = {
        "sourceKind": "official_odate_noshiro_airport_json_kml",
        "operatorName": "秋北タクシー",
        "airportIata": AIRPORT_IATA,
        "routeCode": ROUTE_CODE,
        "routeName": "大館市内・鷹巣駅前 ⇔ 大館能代空港",
        "sourceUrl": OPERATOR_PAGE_URL,
        "sourceUrls": [AIRPORT_PAGE_URL, OPERATOR_PAGE_URL, KML_URL]
        + [urllib.parse.urljoin(OPERATOR_BASE_URL, value) for value in JSON_PATHS.values()],
        "cachePath": str(cache_paths[1].relative_to(ROOT)),
        "cachePaths": [str(path.relative_to(ROOT)) for path in cache_paths],
        "serviceStart": str(period["validFrom"]).replace("-", ""),
        "serviceEnd": str(period["validTo"]).replace("-", ""),
        "serviceDays": SERVICE_DAYS,
        "adultFareYen": adult_fare,
        "routeStopNames": all_stop_names,
        "tripCount": len(trips),
        "stops": [{"stopName": name, **point_index[name]} for name in all_stop_names],
        "busStops": [{"name": name, **point_index[name]} for name in all_stop_names],
        "trips": trips,
        "sourceNotes": [
            "Timetable stops, offsets, fares, and flight-linked current period are from Shuhoku Taxi official JSON files.",
            "Stop coordinates are from the Shuhoku Taxi official Google My Maps KML linked by the operator page.",
            "Inbound airport departures are flight-arrival-linked; current official JSON emits scheduled anchors for ANA719/721/723.",
        ],
    }
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_odate_noshiro_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source pages retain copyright.",
        "routes": [route],
    }
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "periodId": period_id,
        "routeCount": 1,
        "tripCount": len(trips),
        "stopCount": len(all_stop_names),
        "coordinateStopCount": len(point_index),
        "directionCounts": dict(Counter(trip["direction"] for trip in trips)),
        "fareToOdateStationYen": adult_fare,
        "sourceUrls": route["sourceUrls"],
    }
    return payload, audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--refresh-cache", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload, audit = collect(args)
    write_json(args.output, payload)
    write_json(args.docs_output, payload)
    write_json(args.audit_output, audit)
    if args.docs_output != args.output:
        args.docs_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.output, args.docs_output)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
