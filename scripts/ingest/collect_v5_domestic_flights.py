#!/usr/bin/env python3
"""Collect V5 Japan domestic flight schedules from official source files.

The first implemented source is ANA's all-area domestic timetable PDF. The
collector deliberately models marketed flights separately from physical flights
so codeshares can be merged instead of duplicated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "data/v5_flight_source_cache/ana_timetable_all_20260701_20261024.pdf"
DEFAULT_OUTPUT = ROOT / "data/v5_domestic_flights_ana_20260701_20261024.json"

ANA_SOURCE_REF = {
    "id": "ana-domestic-timetable-pdf-20260701-20261024",
    "url": "https://www.ana.co.jp/guide/plan/airinfo/dom-timetable/pdf/timetable_all_20260701_20261024.pdf",
    "period": "2026-07-01/2026-10-24",
    "sourceDate": "2026-03-30",
}
ANA_SERVICE_START = date(2026, 7, 1)
ANA_SERVICE_END = date(2026, 10, 24)

OPERATOR_NAMES = {
    "ANA": "All Nippon Airways",
    "AKX": "ANA Wings",
    "ADO": "Air Do",
    "IBX": "IBEX Airlines",
    "IBEX": "IBEX Airlines",
    "SNA": "Solaseed Air",
    "SFJ": "StarFlyer",
    "ORC": "Oriental Air Bridge",
    "JAC": "Japan Air Commuter",
    "AMX": "Amakusa Airlines",
}

MARKETING_PREFIX_TO_OPERATOR = {
    "NH": "ANA",
}

AIRPORT_IATA = {
    "東京（羽田）": "HND",
    "東京(羽田)": "HND",
    "羽田": "HND",
    "東京（成田）": "NRT",
    "成田": "NRT",
    "大阪（伊丹）": "ITM",
    "大阪（関西）": "KIX",
    "大阪（神戸）": "UKB",
    "神戸": "UKB",
    "札幌（新千歳）": "CTS",
    "新千歳": "CTS",
    "札幌（丘珠）": "OKD",
    "丘珠": "OKD",
    "名古屋（中部）": "NGO",
    "中部": "NGO",
    "名古屋（小牧）": "NKM",
    "小牧": "NKM",
    "福岡": "FUK",
    "沖縄（那覇）": "OKA",
    "那覇": "OKA",
    "青森": "AOJ",
    "三沢": "MSJ",
    "大館能代": "ONJ",
    "秋田": "AXT",
    "花巻": "HNA",
    "仙台": "SDJ",
    "庄内": "SYO",
    "山形": "GAJ",
    "新潟": "KIJ",
    "富山": "TOY",
    "小松": "KMQ",
    "能登": "NTQ",
    "松本": "MMJ",
    "静岡": "FSZ",
    "鳥取": "TTJ",
    "米子": "YGJ",
    "岡山": "OKJ",
    "広島": "HIJ",
    "岩国": "IWK",
    "萩・石見": "IWJ",
    "出雲": "IZO",
    "隠岐": "OKI",
    "山口宇部": "UBJ",
    "徳島": "TKS",
    "高松": "TAK",
    "松山": "MYJ",
    "高知": "KCZ",
    "北九州": "KKJ",
    "佐賀": "HSG",
    "長崎": "NGS",
    "対馬": "TSJ",
    "壱岐": "IKI",
    "五島福江": "FUJ",
    "福江": "FUJ",
    "熊本": "KMJ",
    "大分": "OIT",
    "宮崎": "KMI",
    "鹿児島": "KOJ",
    "種子島": "TNE",
    "屋久島": "KUM",
    "奄美大島": "ASJ",
    "奄美": "ASJ",
    "天草": "AXJ",
    "八丈島": "HAC",
    "福島": "FKS",
    "喜界島": "KKX",
    "徳之島": "TKN",
    "沖永良部": "OKE",
    "与論": "RNJ",
    "宮古": "MMY",
    "下地島": "SHI",
    "石垣": "ISG",
    "多良間": "TRA",
    "久米島": "UEO",
    "北大東": "KTD",
    "南大東": "MMD",
    "与那国": "OGN",
    "稚内": "WKJ",
    "利尻": "RIS",
    "旭川": "AKJ",
    "オホーツク紋別": "MBE",
    "紋別": "MBE",
    "女満別": "MMB",
    "根室中標津": "SHB",
    "中標津": "SHB",
    "釧路": "KUH",
    "帯広": "OBO",
    "函館": "HKD",
    "奥尻": "OIR",
}

ROUTE_RE = re.compile(r"(?P<origin>[^\s　]+（[^）]+）|[一-龥ぁ-んァ-ヶー・]+)→(?P<dest>[^\s　]+（[^）]+）|[一-龥ぁ-んァ-ヶー・]+)")
FLIGHT_RE = re.compile(
    r"(?:(?P<flight>[A-Z]{2}\d{3,4})\s+)?(?P<dep>\d{2}:\d{2})\s+(?P<arr>\d{2}:\d{2})\s+(?P<op>[A-Z]{2,4})(?:\s+(?P<note>.*?))?\s*$"
)


@dataclass
class ParsedRow:
    marketing_flight: str
    origin_name: str
    destination_name: str
    departure_time: str
    arrival_time: str
    operating_carrier: str
    calendar_note: str = ""
    source_line: str = ""

    @property
    def marketing_carrier(self) -> str:
        prefix = re.match(r"[A-Z]+", self.marketing_flight).group(0)
        return MARKETING_PREFIX_TO_OPERATOR.get(prefix, prefix)

    @property
    def origin_airport(self) -> str | None:
        return AIRPORT_IATA.get(self.origin_name)

    @property
    def destination_airport(self) -> str | None:
        return AIRPORT_IATA.get(self.destination_name)

    @property
    def is_codeshare_candidate(self) -> bool:
        return self.marketing_carrier != self.operating_carrier


@dataclass
class PhysicalFlight:
    operating_carrier: str
    origin_airport: str
    destination_airport: str
    departure_time_local: str
    arrival_time_local: str
    calendar_note: str
    marketing_flights: set[str] = field(default_factory=set)
    source_lines: list[str] = field(default_factory=list)
    dedupe_confidence: str = "medium"

    def physical_id(self) -> str:
        raw = "|".join(
            [
                self.operating_carrier,
                self.origin_airport,
                self.destination_airport,
                self.departure_time_local,
                self.arrival_time_local,
                self.calendar_note,
            ]
        )
        return "flight.jp.dom." + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def to_json(self) -> dict:
        service_calendar = service_calendar_for_note(self.calendar_note)
        return {
            "physicalFlightId": self.physical_id(),
            "mode": "flight",
            "operatingCarrier": self.operating_carrier,
            "operatingCarrierName": OPERATOR_NAMES.get(self.operating_carrier),
            "operatingFlightNumber": None,
            "marketingFlights": sorted(self.marketing_flights),
            "originAirport": self.origin_airport,
            "destinationAirport": self.destination_airport,
            "departureTimeLocal": self.departure_time_local,
            "arrivalTimeLocal": self.arrival_time_local,
            "calendarNote": self.calendar_note or None,
            "serviceCalendar": service_calendar,
            "sourceRefs": [ANA_SOURCE_REF["id"]],
            "dedupeConfidence": self.dedupe_confidence,
        }


def run_pdftotext(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return result.stdout


def split_columns(line: str, split_at: int | None) -> list[str]:
    if split_at is None or len(line) <= split_at:
        return [line]
    return [line[:split_at], line[split_at:]]


def find_route_headers(line: str) -> list[tuple[int, str, str]]:
    out = []
    for match in ROUTE_RE.finditer(line):
        origin = match.group("origin").strip()
        dest = match.group("dest").strip()
        if origin in {"便名", "出発", "到着"} or dest in {"便名", "出発", "到着"}:
            continue
        out.append((match.start(), origin, dest))
    return out


def parse_ana_layout_text(text: str) -> tuple[list[ParsedRow], set[str]]:
    routes: list[tuple[int, str, str]] = []
    split_at: int | None = None
    pending_flight: dict[int, str | None] = {0: None, 1: None}
    rows: list[ParsedRow] = []
    unknown_airports: set[str] = set()

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        headers = find_route_headers(line)
        if headers:
            routes = headers[:2]
            if len(routes) > 1:
                split_at = max(1, routes[1][0] - 4)
            else:
                split_at = None
            pending_flight = {0: None, 1: None}
            continue

        if not routes or "便名" in line or "国内線時刻表" in line:
            continue

        parts = split_columns(line, split_at)
        for column_index, part in enumerate(parts[: len(routes)]):
            chunk = part.strip()
            if not chunk:
                continue
            flight_only = re.fullmatch(r"[A-Z]{2}\d{3,4}", chunk)
            if flight_only:
                pending_flight[column_index] = chunk
                continue

            match = FLIGHT_RE.search(chunk)
            if not match:
                continue

            flight = match.group("flight") or pending_flight.get(column_index)
            if not flight:
                continue
            pending_flight[column_index] = flight

            _, origin, dest = routes[column_index]
            note = (match.group("note") or "").strip()
            # The PDF is two-column text. When a left-column row has no note,
            # pdftotext can leak the right-column flight into the note capture.
            # Keep true calendar notes, but discard adjacent-column flight text.
            note = re.split(r"\s+[A-Z]{2}\d{3,4}\s+", f" {note} ", maxsplit=1)[0].strip()
            note = note.split("。", 1)[0] + ("。" if "。" in note else "")
            if note and "運航" not in note and "運休" not in note:
                note = ""
            row = ParsedRow(
                marketing_flight=flight,
                origin_name=origin,
                destination_name=dest,
                departure_time=match.group("dep"),
                arrival_time=match.group("arr"),
                operating_carrier=match.group("op"),
                calendar_note=note,
                source_line=chunk,
            )
            if not row.origin_airport:
                unknown_airports.add(origin)
            if not row.destination_airport:
                unknown_airports.add(dest)
            rows.append(row)

    return rows, unknown_airports


def merge_physical_flights(rows: Iterable[ParsedRow]) -> list[PhysicalFlight]:
    merged: dict[tuple[str, str, str, str, str, str], PhysicalFlight] = {}
    for row in rows:
        if not row.origin_airport or not row.destination_airport:
            continue
        key = (
            row.operating_carrier,
            row.origin_airport,
            row.destination_airport,
            row.departure_time,
            row.arrival_time,
            row.calendar_note,
        )
        if key not in merged:
            merged[key] = PhysicalFlight(
                operating_carrier=row.operating_carrier,
                origin_airport=row.origin_airport,
                destination_airport=row.destination_airport,
                departure_time_local=row.departure_time,
                arrival_time_local=row.arrival_time,
                calendar_note=row.calendar_note,
                dedupe_confidence="medium" if row.is_codeshare_candidate else "high",
            )
        merged[key].marketing_flights.add(row.marketing_flight)
        if row.source_line not in merged[key].source_lines:
            merged[key].source_lines.append(row.source_line)
    return sorted(
        merged.values(),
        key=lambda f: (f.origin_airport, f.destination_airport, f.departure_time_local, f.operating_carrier),
    )


def daterange(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def all_service_dates() -> list[date]:
    return list(daterange(ANA_SERVICE_START, ANA_SERVICE_END))


def parse_month_day_calendar(note: str) -> tuple[list[date], str, str | None]:
    """Parse ANA date notes such as `7/1-31,8/7-16運航。`."""

    clean = (note or "").strip()
    if not clean:
        return all_service_dates(), "default_all_period", None
    if "運休" in clean:
        return all_service_dates(), "unparsed", f"unsupported suspension note: {clean}"
    if "運航" not in clean:
        return all_service_dates(), "unparsed", f"unsupported note: {clean}"

    body = clean.split("運航", 1)[0].rstrip("。")
    dates: set[date] = set()
    current_month: int | None = None
    for token in [piece.strip() for piece in body.split(",") if piece.strip()]:
        month_match = re.fullmatch(r"(?P<month>\d{1,2})/(?P<rest>\d{1,2}(?:-\d{1,2})?)", token)
        day_match = re.fullmatch(r"(?P<rest>\d{1,2}(?:-\d{1,2})?)", token)
        if month_match:
            current_month = int(month_match.group("month"))
            rest = month_match.group("rest")
        elif day_match and current_month is not None:
            rest = day_match.group("rest")
        else:
            return all_service_dates(), "unparsed", f"unsupported date token `{token}` in `{clean}`"

        if "-" in rest:
            start_day, end_day = [int(value) for value in rest.split("-", 1)]
        else:
            start_day = end_day = int(rest)
        if current_month is None:
            return all_service_dates(), "unparsed", f"missing month in `{clean}`"
        for day in range(start_day, end_day + 1):
            try:
                service_date = date(ANA_SERVICE_START.year, current_month, day)
            except ValueError as exc:
                return all_service_dates(), "unparsed", f"invalid date in `{clean}`: {exc}"
            if ANA_SERVICE_START <= service_date <= ANA_SERVICE_END:
                dates.add(service_date)

    if not dates:
        return all_service_dates(), "unparsed", f"empty parsed date set for `{clean}`"
    return sorted(dates), "parsed_date_note", None


def service_calendar_for_note(note: str) -> dict:
    dates, status, error = parse_month_day_calendar(note)
    weekdays = sorted({day.isoweekday() for day in dates})
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return {
        "servicePeriod": {
            "start": ANA_SERVICE_START.isoformat(),
            "end": ANA_SERVICE_END.isoformat(),
        },
        "operatingDates": [day.isoformat() for day in dates],
        "operatingWeekdays": weekdays,
        "operatingWeekdayNames": [weekday_names[index - 1] for index in weekdays],
        "calendarParseStatus": status,
        "calendarParseError": error,
    }


def collect_ana(pdf_path: Path) -> dict:
    text = run_pdftotext(pdf_path)
    parsed_rows, unknown_airports = parse_ana_layout_text(text)
    physical_flights = merge_physical_flights(parsed_rows)
    codeshare_candidates = sum(1 for row in parsed_rows if row.is_codeshare_candidate)
    flights = [flight.to_json() for flight in physical_flights]
    calendar_status_counts: dict[str, int] = {}
    for flight in flights:
        status = flight["serviceCalendar"]["calendarParseStatus"]
        calendar_status_counts[status] = calendar_status_counts.get(status, 0) + 1
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": ANA_SOURCE_REF,
        "rules": {
            "dedupeCodeshares": True,
            "airportIdFormat": "IATA",
            "canonicalKey": [
                "operatingCarrier",
                "originAirport",
                "destinationAirport",
                "departureTimeLocal",
                "arrivalTimeLocal",
                "calendarNote",
            ],
        },
        "summary": {
            "parsedMarketedRows": len(parsed_rows),
            "physicalFlightCount": len(physical_flights),
            "codeshareCandidateRows": codeshare_candidates,
            "unknownAirportNames": sorted(unknown_airports),
            "calendarStatusCounts": dict(sorted(calendar_status_counts.items())),
        },
        "flights": flights,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-pdf", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.source_pdf.exists():
        raise SystemExit(f"source PDF not found: {args.source_pdf}")

    payload = collect_ana(args.source_pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
