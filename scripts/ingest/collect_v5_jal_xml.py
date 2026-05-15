#!/usr/bin/env python3
"""Collect JAL/JTA/RAC domestic timetable XML files into V5 flight records."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "data/v5_flight_source_cache/jal/20260329_20260531"
OUTPUT = ROOT / "data/v5_domestic_flights_jal_20260329_20260531.json"

SOURCE_REF = {
    "id": "jal-domestic-timetable-xml-20260329-20260531",
    "url": "https://www.jal.co.jp/jp/en/dom/route/time/timeTable.html",
    "period": "2026-03-29/2026-05-31",
    "sourceDate": None,
}
SERVICE_START = date(2026, 3, 29)
SERVICE_END = date(2026, 5, 31)

OPERATOR_NAMES = {
    "JAL": "Japan Airlines Group",
    "JTA": "Japan Transocean Air",
    "RAC": "Ryukyu Air Commuter",
}
SKIP_CODESHARE_FLEETS = {"FDA", "AMX", "ORC"}

MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def calendar_for_dates(days: set[date], status: str, note: str | None = None) -> dict:
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekdays = sorted({day.isoweekday() for day in days})
    return {
        "servicePeriod": {"start": SERVICE_START.isoformat(), "end": SERVICE_END.isoformat()},
        "operatingDates": [day.isoformat() for day in sorted(days)],
        "operatingWeekdays": weekdays,
        "operatingWeekdayNames": [weekday_names[index - 1] for index in weekdays],
        "calendarParseStatus": status,
        "calendarParseError": None,
        "sourceCalendarNote": note,
    }


def expand_jal_date_phrase(phrase: str) -> set[date]:
    phrase = phrase.replace("<br>", " ").replace(",", " , ")
    tokens = re.findall(r"(?:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.)?(\d{1,2})(?:-(?:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.)?(\d{1,2}))?", phrase)
    days: set[date] = set()
    current_month: int | None = None
    for start_month_raw, start_day_raw, end_month_raw, end_day_raw in tokens:
        if start_month_raw:
            current_month = MONTHS[start_month_raw]
        if current_month is None:
            continue
        start_month = current_month
        end_month = MONTHS[end_month_raw] if end_month_raw else start_month
        start_day = int(start_day_raw)
        end_day = int(end_day_raw or start_day_raw)
        start = date(2026, start_month, start_day)
        end = date(2026, end_month, end_day)
        current = max(start, SERVICE_START)
        last = min(end, SERVICE_END)
        while current <= last:
            days.add(current)
            current += timedelta(days=1)
        current_month = end_month
    return days


def service_calendar_for_remark(remark: str | None) -> dict:
    all_days = set(daterange(SERVICE_START, SERVICE_END))
    if not remark:
        return calendar_for_dates(all_days, "default_all_period")
    operation = re.search(r"Operation on (.*?)(?:<br>|$)", remark)
    no_operation = re.search(r"No operation on (.*?)(?:<br>|$)", remark)
    if operation:
        days = expand_jal_date_phrase(operation.group(1))
        return calendar_for_dates(days, "parsed_operating_dates", remark)
    if no_operation:
        days = all_days - expand_jal_date_phrase(no_operation.group(1))
        return calendar_for_dates(days, "parsed_except_dates", remark)
    return calendar_for_dates(all_days, "default_all_period_with_time_note", remark)


def normalize_flight_number(value: str) -> tuple[str, str]:
    prefix, digits = value.split()
    if prefix == "JAL":
        return "JAL", f"JL{int(digits):04d}"
    if prefix == "JTA":
        return "JTA", f"NU{int(digits):04d}"
    if prefix == "RAC":
        return "RAC", f"RAC{int(digits):04d}"
    return prefix, f"{prefix}{int(digits):04d}"


def main() -> None:
    rows = []
    skipped_codeshare = 0
    bad_xml = []
    for xml_path in sorted(SOURCE_DIR.glob("*.xml")):
        origin, dest = xml_path.stem.split("_", 1)
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError as exc:
            bad_xml.append({"file": xml_path.name, "error": str(exc)})
            continue
        for time_node in root.findall("time"):
            fleet = (time_node.findtext("fleet") or "").strip()
            if fleet in SKIP_CODESHARE_FLEETS:
                skipped_codeshare += 1
                continue
            fltno = (time_node.findtext("fltno") or "").strip()
            if not fltno:
                continue
            carrier, normalized_flight = normalize_flight_number(fltno)
            rows.append(
                {
                    "carrier": carrier,
                    "flight": normalized_flight,
                    "originAirport": origin,
                    "destinationAirport": dest,
                    "departureTimeLocal": (time_node.findtext("std") or "").strip(),
                    "arrivalTimeLocal": (time_node.findtext("sta") or "").strip(),
                    "calendarNote": (time_node.findtext("rmk") or "").strip() or None,
                    "fleet": fleet or None,
                    "sourceFile": xml_path.name,
                }
            )

    flights = []
    seen = {}
    for row in rows:
        key = (
            row["carrier"],
            row["flight"],
            row["originAirport"],
            row["destinationAirport"],
            row["departureTimeLocal"],
            row["arrivalTimeLocal"],
            row["calendarNote"],
        )
        seen[key] = row
    for row in sorted(seen.values(), key=lambda item: (item["originAirport"], item["destinationAirport"], item["departureTimeLocal"], item["flight"])):
        raw = "|".join(str(row.get(key) or "") for key in ["carrier", "flight", "originAirport", "destinationAirport", "departureTimeLocal", "arrivalTimeLocal", "calendarNote"])
        flights.append(
            {
                "physicalFlightId": "flight.jp.dom." + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16],
                "mode": "flight",
                "operatingCarrier": row["carrier"],
                "operatingCarrierName": OPERATOR_NAMES.get(row["carrier"], row["carrier"]),
                "operatingFlightNumber": row["flight"],
                "marketingFlights": [row["flight"]],
                "originAirport": row["originAirport"],
                "destinationAirport": row["destinationAirport"],
                "departureTimeLocal": row["departureTimeLocal"],
                "arrivalTimeLocal": row["arrivalTimeLocal"],
                "calendarNote": row["calendarNote"],
                "serviceCalendar": service_calendar_for_remark(row["calendarNote"]),
                "sourceRefs": [SOURCE_REF["id"]],
                "dedupeConfidence": "high",
                "sourceFleetNote": row["fleet"],
            }
        )

    status_counts = {}
    for flight in flights:
        status = flight["serviceCalendar"]["calendarParseStatus"]
        status_counts[status] = status_counts.get(status, 0) + 1
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE_REF,
        "rules": {
            "dedupeCodeshares": True,
            "airportIdFormat": "IATA",
            "calendarPolicy": "JAL XML rows are valid for the published period. Operation/no-operation remarks are expanded; pure time-change remarks stay all-period with note.",
            "skippedCodeshareFleets": sorted(SKIP_CODESHARE_FLEETS),
        },
        "summary": {
            "sourceXmlCount": len(list(SOURCE_DIR.glob("*.xml"))),
            "parsedRows": len(rows),
            "physicalFlightCount": len(flights),
            "duplicateRowsRemoved": len(rows) - len(flights),
            "skippedCodeshareRows": skipped_codeshare,
            "badXml": bad_xml,
            "calendarStatusCounts": dict(sorted(status_counts.items())),
        },
        "flights": flights,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
