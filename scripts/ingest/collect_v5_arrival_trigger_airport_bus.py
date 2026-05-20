#!/usr/bin/env python3
"""Collect arrival-trigger airport bus timetables for V5 gameplay."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / "data" / "v5_bus_official_cache" / "arrival_trigger_airport_bus"
DEFAULT_FLIGHTS = ROOT / "data" / "v5_domestic_flights_current_bundle.json"
DEFAULT_OUTPUT = ROOT / "data" / "v5_arrival_trigger_airport_official_bus_source.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_arrival_trigger_airport_official_bus_source.json"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_arrival_trigger_airport_official_bus_audit.json"

OKI_SOURCE_URL = "https://oki.ichibata.co.jp/airport.html"
ARRIVAL_TRIGGER_OFFSET_MINUTES = 5
AIRPORT_BOARDING_LEAD_MINUTES = 50
OKI_TRAVEL_MINUTES = 10

STOPS = {
    "隠岐空港": {"lat": 36.178388, "lon": 133.323566, "coordinateSource": "OurAirports OKI coordinate"},
    "隠岐ポートプラザ前": {"lat": 36.2027906, "lon": 133.3341518, "coordinateSource": "nominatim:隠岐ビューポートホテル"},
}


def cache_path_for(cache_dir: Path, url: str) -> Path:
    suffix = Path(url.split("?", 1)[0]).suffix or ".html"
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}{suffix}"


def fetch(url: str, cache_dir: Path, *, refresh: bool, timeout: int) -> Path:
    path = cache_path_for(cache_dir, url)
    if path.exists() and not refresh:
        return path
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OniChase-v5-bus-ingest/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_hhmm(value: str) -> int:
    hour, minute = [int(part) for part in value.split(":", 1)]
    return hour * 60 + minute


def format_hhmm(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def service_bounds(flight: dict[str, Any]) -> tuple[str, str]:
    period = ((flight.get("serviceCalendar") or {}).get("servicePeriod") or {})
    start = str(period.get("start") or "20260329").replace("-", "")
    end = str(period.get("end") or "20270331").replace("-", "")
    return start, end


def flight_label(flight: dict[str, Any]) -> str:
    labels = flight.get("marketingFlights") or []
    return str(labels[0]) if labels else str(flight.get("physicalFlightId") or "flight")


def make_trip(
    *,
    route_code: str,
    direction: str,
    index: int,
    start_name: str,
    end_name: str,
    start: str,
    end: str,
    service_start: str,
    service_end: str,
    trigger: dict[str, Any],
) -> dict[str, Any]:
    return {
        "tripId": f"{route_code}:{direction}:{index:03d}",
        "direction": direction,
        "serviceStart": service_start,
        "serviceEnd": service_end,
        "serviceDays": "daily",
        "trigger": trigger,
        "stopTimes": [{"stopName": start_name, "time": start}, {"stopName": end_name, "time": end}],
    }


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cache_path = fetch(OKI_SOURCE_URL, args.cache_dir, refresh=args.refresh_cache, timeout=args.timeout)
    if cache_path.stat().st_size < 10_000:
        raise ValueError(f"Oki airport source looks too small: {cache_path}")
    flights = json.loads(args.flights.read_text(encoding="utf-8")).get("flights") or []
    inbound = sorted(
        [flight for flight in flights if flight.get("destinationAirport") == "OKI" and flight.get("arrivalTimeLocal")],
        key=lambda item: (item["arrivalTimeLocal"], flight_label(item)),
    )
    outbound = sorted(
        [flight for flight in flights if flight.get("originAirport") == "OKI" and flight.get("departureTimeLocal")],
        key=lambda item: (item["departureTimeLocal"], flight_label(item)),
    )

    trips: list[dict[str, Any]] = []
    for index, flight in enumerate(inbound, start=1):
        start_minutes = parse_hhmm(flight["arrivalTimeLocal"]) + ARRIVAL_TRIGGER_OFFSET_MINUTES
        service_start, service_end = service_bounds(flight)
        trips.append(
            make_trip(
                route_code="oki_airport_port_plaza",
                direction="from_airport",
                index=index,
                start_name="隠岐空港",
                end_name="隠岐ポートプラザ前",
                start=format_hhmm(start_minutes),
                end=format_hhmm(start_minutes + OKI_TRAVEL_MINUTES),
                service_start=service_start,
                service_end=service_end,
                trigger={
                    "kind": "flight_arrival",
                    "airportIata": "OKI",
                    "flightId": flight.get("physicalFlightId"),
                    "flightLabel": flight_label(flight),
                    "arrivalTimeLocal": flight.get("arrivalTimeLocal"),
                    "offsetMinutes": ARRIVAL_TRIGGER_OFFSET_MINUTES,
                    "sourceRule": "arrival_time_plus_configured_offset",
                },
            )
        )
    for index, flight in enumerate(outbound, start=1):
        start_minutes = parse_hhmm(flight["departureTimeLocal"]) - AIRPORT_BOARDING_LEAD_MINUTES
        service_start, service_end = service_bounds(flight)
        trips.append(
            make_trip(
                route_code="oki_airport_port_plaza",
                direction="to_airport",
                index=index,
                start_name="隠岐ポートプラザ前",
                end_name="隠岐空港",
                start=format_hhmm(start_minutes),
                end=format_hhmm(start_minutes + OKI_TRAVEL_MINUTES),
                service_start=service_start,
                service_end=service_end,
                trigger={
                    "kind": "flight_departure",
                    "airportIata": "OKI",
                    "flightId": flight.get("physicalFlightId"),
                    "flightLabel": flight_label(flight),
                    "departureTimeLocal": flight.get("departureTimeLocal"),
                    "leadMinutes": AIRPORT_BOARDING_LEAD_MINUTES,
                    "sourceRule": "flight_departure_minus_official_50_minutes",
                },
            )
        )

    route = {
        "sourceKind": "official_oki_ichibata_arrival_trigger_airport_html",
        "operatorName": "隠岐一畑交通",
        "airportIata": "OKI",
        "routeCode": "oki_airport_port_plaza",
        "routeName": "隠岐ポートプラザ前 ⇔ 隠岐空港",
        "sourceUrl": OKI_SOURCE_URL,
        "sourceUrls": [OKI_SOURCE_URL],
        "cachePath": str(cache_path.relative_to(ROOT)),
        "cachePaths": [str(cache_path.relative_to(ROOT))],
        "serviceStart": min((trip["serviceStart"] for trip in trips), default="20260329"),
        "serviceEnd": max((trip["serviceEnd"] for trip in trips), default="20270331"),
        "serviceDays": "daily",
        "adultFareYen": 520,
        "arrivalTriggerOffsetMinutes": ARRIVAL_TRIGGER_OFFSET_MINUTES,
        "airportBoardingLeadMinutes": AIRPORT_BOARDING_LEAD_MINUTES,
        "routeStopNames": ["隠岐ポートプラザ前", "隠岐空港"],
        "tripCount": len(trips),
        "stops": [{"stopName": name, **STOPS[name]} for name in ["隠岐ポートプラザ前", "隠岐空港"]],
        "busStops": [{"name": name, **STOPS[name]} for name in ["隠岐ポートプラザ前", "隠岐空港"]],
        "trips": trips,
        "sourceNotes": [
            "Official Oki Ichibata page says airport-bound buses depart Port Plaza 50 minutes before each flight departure.",
            "Official Oki Ichibata page says airport departures vary by aircraft arrival and leave after baggage/passengers are ready.",
            f"OniChase V5 gameplay expands arrival-trigger bus departures as flight arrival + {ARRIVAL_TRIGGER_OFFSET_MINUTES} minutes by user rule.",
            "Travel time between 隠岐空港 and 隠岐ポートプラザ is 10 minutes in the official source.",
        ],
    }
    payload = {
        "schemaVersion": 1,
        "sourceFamily": "official_arrival_trigger_airport_bus",
        "generatedAt": generated_at,
        "license": "Official timetable facts collected for gameplay routing; source page retains copyright.",
        "routes": [route],
    }
    audit = {
        "generatedAt": generated_at,
        "sourceFamily": payload["sourceFamily"],
        "routeCount": 1,
        "tripCount": len(trips),
        "stopCount": 2,
        "coordinateStopCount": 2,
        "directionCounts": dict(Counter(trip["direction"] for trip in trips)),
        "arrivalTriggerOffsetMinutes": ARRIVAL_TRIGGER_OFFSET_MINUTES,
        "sourceUrls": [OKI_SOURCE_URL],
    }
    return payload, audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--flights", type=Path, default=DEFAULT_FLIGHTS)
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
