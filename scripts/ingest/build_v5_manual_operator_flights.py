#!/usr/bin/env python3
"""Build official-source V5 flight artifacts for image/PDF-table operators.

These operators publish real timetable tables that are not cleanly machine
readable. The rows below are transcribed from cached official source files.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE_START = date(2026, 3, 29)
SERVICE_END = date(2026, 10, 24)


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def calendar_for_period(note: str | None = None) -> dict:
    dates = list(daterange(SERVICE_START, SERVICE_END))
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekdays = sorted({day.isoweekday() for day in dates})
    return {
        "servicePeriod": {"start": SERVICE_START.isoformat(), "end": SERVICE_END.isoformat()},
        "operatingDates": [day.isoformat() for day in dates],
        "operatingWeekdays": weekdays,
        "operatingWeekdayNames": [weekday_names[index - 1] for index in weekdays],
        "calendarParseStatus": "default_all_period_from_official_table",
        "calendarParseError": None,
        "sourceCalendarNote": note,
    }


def flight_id(carrier: str, flight: str, origin: str, dest: str, dep: str, arr: str, note: str | None) -> str:
    raw = "|".join([carrier, flight, origin, dest, dep, arr, note or ""])
    return "flight.jp.dom." + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def make_flight(carrier: str, carrier_name: str, flight: str, origin: str, dest: str, dep: str, arr: str, source_ref: str, note: str | None = None) -> dict:
    return {
        "physicalFlightId": flight_id(carrier, flight, origin, dest, dep, arr, note),
        "mode": "flight",
        "operatingCarrier": carrier,
        "operatingCarrierName": carrier_name,
        "operatingFlightNumber": flight,
        "marketingFlights": [flight],
        "originAirport": origin,
        "destinationAirport": dest,
        "departureTimeLocal": dep,
        "arrivalTimeLocal": arr,
        "calendarNote": note,
        "serviceCalendar": calendar_for_period(note),
        "sourceRefs": [source_ref],
        "dedupeConfidence": "high",
    }


def write_payload(path: Path, source: dict, flights: list[dict], rules: dict) -> None:
    calendar_counts = {}
    for flight in flights:
        status = (flight.get("serviceCalendar") or {}).get("calendarParseStatus")
        calendar_counts[status] = calendar_counts.get(status, 0) + 1
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "rules": rules,
        "summary": {
            "physicalFlightCount": len(flights),
            "calendarStatusCounts": dict(sorted(calendar_counts.items())),
        },
        "flights": sorted(flights, key=lambda f: (f["originAirport"], f["destinationAirport"], f["departureTimeLocal"], f["operatingFlightNumber"])),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path.name, json.dumps(payload["summary"], ensure_ascii=False))


def build_orc() -> None:
    source = {
        "id": "orc-official-pdf-timetable-20260329-20261024",
        "url": "https://www.orc-air.co.jp/fare/",
        "period": "2026-03-29/2026-10-24",
        "sourceDate": None,
    }
    route_airports = {
        "⾧崎－壱岐": ("NGS", "IKI"),
        "⾧崎－五島福江": ("NGS", "FUJ"),
        "⾧崎－対馬": ("NGS", "TSJ"),
        "福岡－五島福江": ("FUK", "FUJ"),
        "福岡－対馬": ("FUK", "TSJ"),
        "福岡－宮崎": ("FUK", "KMI"),
        "福岡－中部": ("FUK", "NGO"),
        "福岡－小松": ("FUK", "KMQ"),
        "中部－宮崎": ("NGO", "KMI"),
        "中部－秋田": ("NGO", "AXT"),
    }
    fallback_calendars = {}
    fallback_path = ROOT / "data/v5_domestic_flights_orc_from_ana_20260701_20261024.json"
    if fallback_path.exists():
        for flight in json.loads(fallback_path.read_text(encoding="utf-8"))["flights"]:
            fallback_calendars[(flight["originAirport"], flight["destinationAirport"], flight["departureTimeLocal"], flight["arrivalTimeLocal"])] = flight["serviceCalendar"]
    rows: dict[tuple[str, str, str, str, str], tuple[str, str, str, str, str]] = {}
    for pdf_path in sorted((ROOT / "data/v5_flight_source_cache/orc").glob("*.pdf")):
        text = subprocess.check_output(["pdftotext", "-layout", str(pdf_path), "-"], text=True)
        title_match = re.search(r"FLIGHT SCHEDULE\s+(.+?)線", text)
        if not title_match:
            continue
        route = title_match.group(1)
        if route not in route_airports:
            continue
        left_airport, right_airport = route_airports[route]
        for line in text.splitlines():
            matches = re.findall(r"(\d{2})\s+\([^)]*\)\s+(\d{1,2}:\d{2})\s+＞\s+(\d{1,2}:\d{2})", line)
            if len(matches) >= 1:
                for index, (number, dep, arr) in enumerate(matches[:2]):
                    origin, dest = (left_airport, right_airport) if index == 0 else (right_airport, left_airport)
                    dep = dep.zfill(5)
                    arr = arr.zfill(5)
                    key = (number, origin, dest, dep, arr)
                    rows[key] = key
    flights = []
    for number, origin, dest, dep, arr in rows.values():
        flight = make_flight("ORC", "Oriental Air Bridge", f"ORC{int(number):04d}", origin, dest, dep, arr, source["id"])
        calendar = fallback_calendars.get((origin, dest, dep, arr))
        if calendar:
            flight["serviceCalendar"] = calendar
            flight["calendarNote"] = calendar.get("sourceCalendarNote")
        flights.append(flight)
    write_payload(
        ROOT / "data/v5_domestic_flights_orc_official_20260329_20261024.json",
        source,
        flights,
        {"sourcePolicy": "Rows parsed from official ORC route PDFs; overlapping ANA official calendars are reused when they provide date notes.", "airportIdFormat": "IATA"},
    )


def build_amx() -> None:
    source = {
        "id": "amx-official-image-timetable-20260329-20261024",
        "url": "https://www.amx.co.jp/time/",
        "period": "2026-03-29/2026-10-24",
        "sourceDate": None,
    }
    rows = [
        ("101", "AXJ", "FUK", "07:40", "08:20"),
        ("105", "AXJ", "FUK", "15:45", "16:25"),
        ("107", "AXJ", "FUK", "18:00", "18:40"),
        ("102", "FUK", "AXJ", "08:50", "09:25"),
        ("106", "FUK", "AXJ", "16:55", "17:30"),
        ("108", "FUK", "AXJ", "19:10", "19:45"),
        ("201", "AXJ", "KMJ", "09:55", "10:15"),
        ("202", "KMJ", "AXJ", "14:50", "15:15"),
        ("801", "KMJ", "ITM", "10:45", "12:10"),
        ("802", "ITM", "KMJ", "12:50", "14:20"),
    ]
    flights = [make_flight("AMX", "Amakusa Airlines", f"AMX{int(no):04d}", o, d, dep, arr, source["id"]) for no, o, d, dep, arr in rows]
    write_payload(
        ROOT / "data/v5_domestic_flights_amx_official_20260329_20261024.json",
        source,
        flights,
        {"sourcePolicy": "Rows transcribed from cached official AMX timetable images.", "airportIdFormat": "IATA"},
    )


def build_solaseed() -> None:
    source = {
        "id": "solaseed-official-image-timetable-20260329-20261024",
        "url": "https://www.solaseedair.jp/timetable/assets/mediafile/time_20260329-20261024.pdf",
        "period": "2026-03-29/2026-10-24",
        "sourceDate": "2026-01-21",
    }
    rows = [
        ("51","HND","KMI","06:45","08:30"),("55","HND","KMI","10:05","11:55"),("57","HND","KMI","12:00","13:40"),("59","HND","KMI","14:30","16:15"),("61","HND","KMI","15:25","17:10"),("65","HND","KMI","19:15","21:00"),
        ("52","KMI","HND","07:35","09:15"),("56","KMI","HND","11:25","13:05"),("58","KMI","HND","12:35","14:15"),("60","KMI","HND","14:15","15:55"),("62","KMI","HND","16:50","18:35"),("64","KMI","HND","18:30","20:10"),
        ("11","HND","KMJ","07:15","09:05"),("13","HND","KMJ","10:40","12:35"),("15","HND","KMJ","12:15","14:10"),("17","HND","KMJ","16:35","18:25"),("19","HND","KMJ","18:05","19:55"),
        ("12","KMJ","HND","07:35","09:20"),("14","KMJ","HND","09:50","11:30"),("16","KMJ","HND","13:10","14:50"),("18","KMJ","HND","14:55","16:40"),("20","KMJ","HND","19:00","20:40"),
        ("31","HND","NGS","07:05","09:00"),("33","HND","NGS","09:35","11:30"),("35","HND","NGS","12:50","14:45"),("37","HND","NGS","18:40","20:35"),
        ("32","NGS","HND","09:35","11:20"),("34","NGS","HND","12:05","13:50"),("36","NGS","HND","15:35","17:25"),("38","NGS","HND","21:10","22:50"),
        ("71","HND","KOJ","07:50","09:40"),("75","HND","KOJ","13:05","14:55"),("77","HND","KOJ","15:05","17:00"),("79","HND","KOJ","18:10","20:05"),
        ("72","KOJ","HND","07:10","08:55"),("74","KOJ","HND","10:10","11:55"),("78","KOJ","HND","15:35","17:25"),("80","KOJ","HND","20:30","22:15"),
        ("91","HND","OIT","06:25","08:00"),("93","HND","OIT","09:55","11:40"),("95","HND","OIT","14:40","16:20"),("97","HND","OIT","17:15","18:55"),
        ("92","OIT","HND","08:30","10:00"),("94","OIT","HND","12:20","14:00"),("96","OIT","HND","16:55","18:35"),("98","OIT","HND","19:50","21:20"),
        ("21","HND","OKA","06:10","08:55"),("23","HND","OKA","13:45","16:30"),("25","HND","OKA","19:10","21:55"),
        ("22","OKA","HND","09:50","12:15"),("24","OKA","HND","15:25","18:00"),("26","OKA","HND","20:25","22:50"),
        ("67","KMI","OKA","09:05","10:40"),("68","OKA","KMI","16:35","17:55"),
        ("83","KOJ","OKA","09:25","10:55"),("85","KOJ","OKA","17:40","19:10"),("84","OKA","KOJ","07:25","08:45"),("86","OKA","KOJ","19:45","21:05"),
        ("121","NGO","OKA","12:15","14:40"),("122","OKA","NGO","15:35","17:40"),("101","FUK","OKA","13:00","14:50"),("102","OKA","FUK","10:35","12:20"),
        ("125","UKB","OKA","07:50","10:00"),("127","UKB","OKA","13:50","16:00"),("129","UKB","OKA","17:30","19:40"),("126","OKA","UKB","11:20","13:15"),("128","OKA","UKB","15:00","16:55"),("130","OKA","UKB","20:20","22:20"),
        ("43","OKA","ISG","11:35","12:40"),("49","OKA","ISG","17:10","18:10"),("44","ISG","OKA","13:15","14:20"),("50","ISG","OKA","18:50","19:50"),
        ("108","KMI","NGO","07:40","08:55"),("110","KMI","NGO","17:50","19:05"),("107","NGO","KMI","09:30","10:50"),("109","NGO","KMI","19:40","21:00"),
        ("116","KOJ","NGO","10:20","11:40"),("118","KOJ","NGO","20:40","22:00"),("115","NGO","KOJ","08:10","09:30"),("117","NGO","KOJ","18:25","19:45"),
    ]
    flights = [make_flight("SNA", "Solaseed Air", f"SNA{int(no):04d}", o, d, dep, arr, source["id"], "Some rows have official July-Sep time-change footnotes; base timetable row is retained.") for no, o, d, dep, arr in rows]
    write_payload(
        ROOT / "data/v5_domestic_flights_solaseed_official_20260329_20261024.json",
        source,
        flights,
        {"sourcePolicy": "Rows transcribed from cached official Solaseed timetable PDF image.", "airportIdFormat": "IATA"},
    )


def main() -> None:
    build_orc()
    build_amx()
    build_solaseed()


if __name__ == "__main__":
    main()
