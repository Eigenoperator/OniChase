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
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "data/v5_flight_source_cache/ana_timetable_all_20260701_20261024.pdf"
DEFAULT_OUTPUT = ROOT / "data/v5_domestic_flights_ana_20260701_20261024.json"
SKYMARK_SOURCE = ROOT / "data/v5_flight_source_cache/skymark_timetable_2026summerEngUpdate.pdf"
SKYMARK_OUTPUT = ROOT / "data/v5_domestic_flights_skymark_20260601_20261024.json"
AIRDO_SOURCE = ROOT / "data/v5_flight_source_cache/airdo_timetable_20260329_20261024.html"
AIRDO_OUTPUT = ROOT / "data/v5_domestic_flights_airdo_20260329_20261024.json"
STARFLYER_SOURCE_DIR = ROOT / "data/v5_flight_source_cache/starflyer"
STARFLYER_OUTPUT = ROOT / "data/v5_domestic_flights_starflyer_20260329_20261024.json"
IBEX_SOURCE = ROOT / "data/v5_flight_source_cache/ibex_timetable_20260329_20261024.html"
IBEX_OUTPUT = ROOT / "data/v5_domestic_flights_ibex_20260329_20261024.json"
TOKI_SOURCE = ROOT / "data/v5_flight_source_cache/toki_schedules_20260329_20260831.html"
TOKI_OUTPUT = ROOT / "data/v5_domestic_flights_toki_20260329_20260831.json"
FDA_SOURCE_DIR = ROOT / "data/v5_flight_source_cache/fda_routes"
FDA_OUTPUT = ROOT / "data/v5_domestic_flights_fda_20260329_20261024.json"
JETSTAR_SOURCE = ROOT / "data/v5_flight_source_cache/jetstar_gk_timetable_26nsdom.pdf"
JETSTAR_OUTPUT = ROOT / "data/v5_domestic_flights_jetstar_20260329_20261024.json"
SPRING_SOURCE = ROOT / "data/v5_flight_source_cache/spring_ij_domestic_20260329_20261024.pdf"
SPRING_OUTPUT = ROOT / "data/v5_domestic_flights_spring_20260329_20261024.json"
PEACH_SOURCE = ROOT / "data/v5_flight_source_cache/peach_domestic_20260329_20261024.pdf"
PEACH_OUTPUT = ROOT / "data/v5_domestic_flights_peach_20260329_20261024.json"

ANA_SOURCE_REF = {
    "id": "ana-domestic-timetable-pdf-20260701-20261024",
    "url": "https://www.ana.co.jp/guide/plan/airinfo/dom-timetable/pdf/timetable_all_20260701_20261024.pdf",
    "period": "2026-07-01/2026-10-24",
    "sourceDate": "2026-03-30",
}
ANA_SERVICE_START = date(2026, 7, 1)
ANA_SERVICE_END = date(2026, 10, 24)

SKYMARK_SOURCE_REF = {
    "id": "skymark-timetable-pdf-20260601-20261024",
    "url": "https://smart.skymark.co.jp/en/news/detail/__icsFiles/afieldfile/2026/03/09/timetable_2026summerEngUpdate.pdf",
    "period": "2026-06-01/2026-10-24",
    "sourceDate": "2026-03-09",
}
SKYMARK_SERVICE_START = date(2026, 6, 1)
SKYMARK_SERVICE_END = date(2026, 10, 24)

AIRDO_SOURCE_REF = {
    "id": "airdo-timetable-web-20260329-20261024",
    "url": "https://www.airdo.jp/plan/timetable/",
    "period": "2026-03-29/2026-10-24",
    "sourceDate": None,
}
AIRDO_SERVICE_START = date(2026, 3, 29)
AIRDO_SERVICE_END = date(2026, 10, 24)

STARFLYER_SOURCE_REF = {
    "id": "starflyer-timetable-web-20260329-20261024",
    "url": "https://www.starflyer.jp/en/timetable/",
    "period": "2026-03-29/2026-10-24",
    "sourceDate": None,
}
STARFLYER_SERVICE_START = date(2026, 3, 29)
STARFLYER_SERVICE_END = date(2026, 10, 24)

IBEX_SOURCE_REF = {
    "id": "ibex-timetable-web-20260329-20261024",
    "url": "https://www.ibexair.co.jp/timetable/",
    "period": "2026-03-29/2026-10-24",
    "sourceDate": None,
}
IBEX_SERVICE_START = date(2026, 3, 29)
IBEX_SERVICE_END = date(2026, 10, 24)

TOKI_SOURCE_REF = {
    "id": "toki-air-schedules-web-20260329-20260831",
    "url": "https://tokiair.com/schedules/",
    "period": "2026-03-29/2026-08-31",
    "sourceDate": None,
}

FDA_SOURCE_REF = {
    "id": "fda-timetable-web-20260329-20261024",
    "url": "https://www.fujidream.co.jp/en/timetable/",
    "period": "2026-03-29/2026-10-24",
    "sourceDate": None,
}
FDA_SERVICE_START = date(2026, 3, 29)
FDA_SERVICE_END = date(2026, 10, 24)

JETSTAR_SOURCE_REF = {
    "id": "jetstar-japan-domestic-timetable-pdf-20260329-20261024",
    "url": "https://files.jetstar.com/api/public/content/gk_timetable_26nsdom",
    "period": "2026-03-29/2026-10-24",
    "sourceDate": "2026-03-26",
}
JETSTAR_SERVICE_START = date(2026, 3, 29)
JETSTAR_SERVICE_END = date(2026, 10, 24)

SPRING_SOURCE_REF = {
    "id": "spring-japan-domestic-timetable-pdf-20260329-20261024",
    "url": "https://ajax.springairlines.com/style/site/img/home/0513UP_%E3%82%B9%E3%83%97%E3%83%AA%E3%83%B3%E3%82%B0%E3%83%BB%E3%82%B8%E3%83%A3%E3%83%91%E3%83%B3%202026%E5%B9%B4%E5%A4%8F%E3%83%80%E3%82%A4%E3%83%A4%20%E5%9B%BD%E5%86%85%E7%B7%9A%E3%83%95%E3%83%A9%E3%82%A4%E3%83%88%E3%82%B9%E3%82%B1%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%EF%BC%8820260329-20261024%EF%BC%89%20(1).pdf",
    "period": "2026-03-29/2026-10-24",
    "sourceDate": "2026-05-13",
}
SPRING_SERVICE_START = date(2026, 3, 29)
SPRING_SERVICE_END = date(2026, 10, 24)

PEACH_SOURCE_REF = {
    "id": "peach-domestic-timetable-pdf-20260329-20261024",
    "url": "https://www.flypeach.com/application/files/6117/7854/7644/20260514_S26_20260329-20261024_dom_EN.pdf",
    "period": "2026-03-29/2026-10-24",
    "sourceDate": "2026-05-14",
}
PEACH_SERVICE_START = date(2026, 3, 29)
PEACH_SERVICE_END = date(2026, 10, 24)

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
    "SKY": "Skymark Airlines",
    "FDA": "Fuji Dream Airlines",
    "TOK": "Toki Air",
    "JJP": "Jetstar Japan",
    "SJO": "Spring Japan",
    "APJ": "Peach Aviation",
}

MARKETING_PREFIX_TO_OPERATOR = {
    "NH": "ANA",
}

AIRPORT_IATA = {
    "東京（羽田）": "HND",
    "東京(羽田)": "HND",
    "羽田": "HND",
    "東京（成田）": "NRT",
    "東京／成田": "NRT",
    "東京/成田": "NRT",
    "成田": "NRT",
    "大阪（伊丹）": "ITM",
    "大阪（関西）": "KIX",
    "大阪／関西": "KIX",
    "大阪（神戸）": "UKB",
    "神戸": "UKB",
    "札幌（新千歳）": "CTS",
    "札幌(新千歳)": "CTS",
    "札幌／新千歳": "CTS",
    "新千歳": "CTS",
    "札幌（丘珠）": "OKD",
    "札幌(丘珠)": "OKD",
    "丘珠": "OKD",
    "名古屋（中部）": "NGO",
    "名古屋(中部)": "NGO",
    "名古屋／中部": "NGO",
    "中部": "NGO",
    "名古屋（小牧）": "NKM",
    "名古屋(小牧)": "NKM",
    "小牧": "NKM",
    "福岡": "FUK",
    "沖縄（那覇）": "OKA",
    "沖縄／那覇": "OKA",
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
    "名古屋": "NGO",
    "Haneda": "HND",
    "Haneda (Tokyo)": "HND",
    "Sapporo(New Chitose)": "CTS",
    "Kobe": "UKB",
    "Fukuoka": "FUK",
    "Nagasaki": "NGS",
    "Kagoshima": "KOJ",
    "Amamioshima": "ASJ",
    "Naha": "OKA",
    "Miyako(Shimojishima)": "SHI",
    "Ibaraki": "IBR",
    "Nagoya(Chubu)": "NGO",
    "Nagoya (Chubu)": "NGO",
    "Chubu (Nagoya)": "NGO",
    "Sendai": "SDJ",
    "Kitakyushu": "KKJ",
    "Kansai (Osaka)": "KIX",
    "Yamaguchi Ube": "UBJ",
    "新千歳空港": "CTS",
    "仙台空港": "SDJ",
    "福島空港": "FKS",
    "新潟空港": "KIJ",
    "名古屋（中部国際空港）": "NGO",
    "大阪（伊丹空港）": "ITM",
    "広島空港": "HIJ",
    "松山空港": "MYJ",
    "福岡空港": "FUK",
    "大分空港": "OIT",
    "Mt. Fuji Shizuoka": "FSZ",
    "Shizuoka": "FSZ",
    "Sapporo (Okadama)": "OKD",
    "Nagoya (Komaki)": "NKM",
    "Aomori": "AOJ",
    "Iwate Hanamaki": "HNA",
    "Yamagata": "GAJ",
    "Niigata": "KIJ",
    "Matsumoto": "MMJ",
    "Izumo": "IZO",
    "Kochi": "KCZ",
    "Kumamoto": "KMJ",
    "Kagoshima": "KOJ",
    "Tokyo (Narita)": "NRT",
    "Tokyo (Haneda)": "HND",
    "Osaka (Kansai)": "KIX",
    "Sapporo (New Chitose)": "CTS",
    "Memanbetsu": "MMB",
    "Kushiro": "KUH",
    "Miyazaki": "KMI",
    "Amami": "ASJ",
    "Okinawa (Naha)": "OKA",
    "Ishigaki": "ISG",
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


SKYMARK_ROUTE_RE = re.compile(
    r"(?P<origin>[A-Za-z][A-Za-z() ]+?)→(?P<dest>[A-Za-z][A-Za-z() ]+?)(?=\s{2,}|$)"
)
SKYMARK_FLIGHT_RE = re.compile(
    r"(?P<flight>SKY\d{3})(?:\s*(?P<markers>(?:※\d)+))?\s+(?P<dep>\d{2}:\d{2})\s+(?P<arr>\d{2}:\d{2})"
)
SKYMARK_WEEKDAY_MARKERS = {
    "※1": {3, 5},
    "※2": {1, 2, 4, 6, 7},
}
SKYMARK_MONTHS = {
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
}


def skymark_all_service_dates() -> list[date]:
    return list(daterange(SKYMARK_SERVICE_START, SKYMARK_SERVICE_END))


def calendar_for_period(start: date, end: date, status: str = "default_all_period", extra: dict | None = None) -> dict:
    dates = list(daterange(start, end))
    weekdays = sorted({day.isoweekday() for day in dates})
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    payload = {
        "servicePeriod": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "operatingDates": [day.isoformat() for day in dates],
        "operatingWeekdays": weekdays,
        "operatingWeekdayNames": [weekday_names[index - 1] for index in weekdays],
        "calendarParseStatus": status,
        "calendarParseError": None,
    }
    if extra:
        payload.update(extra)
    return payload


def calendar_for_weekdays(
    start: date,
    end: date,
    weekdays: set[int],
    extra_dates: set[date] | None = None,
    status: str = "parsed_weekday_note",
    extra: dict | None = None,
) -> dict:
    dates = [day for day in daterange(start, end) if day.isoweekday() in weekdays]
    if extra_dates:
        dates = sorted(set(dates) | {day for day in extra_dates if start <= day <= end})
    else:
        dates = sorted(dates)
    weekday_values = sorted({day.isoweekday() for day in dates})
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    payload = {
        "servicePeriod": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "operatingDates": [day.isoformat() for day in dates],
        "operatingWeekdays": weekday_values,
        "operatingWeekdayNames": [weekday_names[index - 1] for index in weekday_values],
        "calendarParseStatus": status,
        "calendarParseError": None,
    }
    if extra:
        payload.update(extra)
    return payload


def split_marker_string(markers: str | None) -> list[str]:
    if not markers:
        return []
    return re.findall(r"※\d", markers)


def date_range_for_month_days(month_name: str, start_day: int, end_month_name: str, end_day: int) -> set[date]:
    start = date(2026, SKYMARK_MONTHS[month_name], start_day)
    end = date(2026, SKYMARK_MONTHS[end_month_name], end_day)
    return {day for day in daterange(start, end) if SKYMARK_SERVICE_START <= day <= SKYMARK_SERVICE_END}


def skymark_service_calendar(markers: list[str]) -> dict:
    dates = set(skymark_all_service_dates())
    notes: list[str] = []
    parse_errors: list[str] = []

    for marker in markers:
        if marker in SKYMARK_WEEKDAY_MARKERS:
            weekdays = SKYMARK_WEEKDAY_MARKERS[marker]
            dates &= {day for day in skymark_all_service_dates() if day.isoweekday() in weekdays}
            notes.append(marker)
        elif marker == "※3":
            dates &= date_range_for_month_days("March", 29, "June", 18)
            notes.append(marker)
        elif marker == "※4":
            dates &= date_range_for_month_days("June", 19, "October", 24)
            notes.append(marker)
        elif marker == "※5":
            excluded = {
                date(2026, 6, day) for day in [2, 3, 9, 10, 16, 17, 23, 24, 30]
            } | {
                date(2026, 7, day) for day in [1, 7, 8, 14, 15]
            } | {
                date(2026, 9, 30),
                date(2026, 10, 6),
                date(2026, 10, 7),
                date(2026, 10, 13),
                date(2026, 10, 14),
                date(2026, 10, 18),
                date(2026, 10, 20),
                date(2026, 10, 21),
                date(2026, 10, 24),
            }
            dates -= excluded
            notes.append(marker)
        elif marker == "※6":
            excluded = {
                date(2026, 6, day) for day in [3, 4, 10, 11, 17, 18, 24, 25]
            } | {
                date(2026, 7, day) for day in [1, 2, 8, 9, 15, 16]
            } | {
                date(2026, 10, 1),
                date(2026, 10, 7),
                date(2026, 10, 8),
                date(2026, 10, 14),
                date(2026, 10, 15),
                date(2026, 10, 19),
                date(2026, 10, 21),
                date(2026, 10, 22),
            }
            dates -= excluded
            notes.append(marker)
        else:
            parse_errors.append(f"unknown Skymark marker {marker}")

    weekdays = sorted({day.isoweekday() for day in dates})
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return {
        "servicePeriod": {
            "start": SKYMARK_SERVICE_START.isoformat(),
            "end": SKYMARK_SERVICE_END.isoformat(),
        },
        "operatingDates": [day.isoformat() for day in sorted(dates)],
        "operatingWeekdays": weekdays,
        "operatingWeekdayNames": [weekday_names[index - 1] for index in weekdays],
        "calendarParseStatus": "parsed_marker_note" if markers else "default_all_period",
        "calendarParseError": "; ".join(parse_errors) if parse_errors else None,
        "sourceCalendarMarkers": markers,
        "sourceCalendarNotes": notes,
    }


def parse_skymark_pdf_text(text: str) -> tuple[list[dict], set[str], int]:
    routes: list[tuple[int, str, str, bool]] = []
    split_at: int | None = None
    records: list[dict] = []
    unknown_airports: set[str] = set()
    skipped_via_sections = 0

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        headers: list[tuple[int, str, str, bool]] = []
        for match in SKYMARK_ROUTE_RE.finditer(line):
            origin = match.group("origin").strip()
            dest = match.group("dest").strip()
            lookahead = line[match.end() : match.end() + 24]
            is_via = "Via" in lookahead
            headers.append((match.start(), origin, dest, is_via))
        if headers:
            routes = headers[:2]
            split_at = max(1, routes[1][0] - 4) if len(routes) > 1 else None
            continue
        if "→" in line:
            if "Via" in line:
                skipped_via_sections += 1
            routes = []
            split_at = None
            continue

        if not routes:
            continue
        parts = [line] if split_at is None else [line[:split_at], line[split_at:]]
        for column_index, part in enumerate(parts[: len(routes)]):
            _, origin, dest, is_via = routes[column_index]
            if is_via:
                continue
            for match in SKYMARK_FLIGHT_RE.finditer(part):
                origin_iata = AIRPORT_IATA.get(origin)
                dest_iata = AIRPORT_IATA.get(dest)
                if not origin_iata:
                    unknown_airports.add(origin)
                if not dest_iata:
                    unknown_airports.add(dest)
                if not origin_iata or not dest_iata:
                    continue
                markers = split_marker_string(match.group("markers"))
                records.append(
                    {
                        "flight": match.group("flight"),
                        "originAirport": origin_iata,
                        "destinationAirport": dest_iata,
                        "departureTimeLocal": match.group("dep"),
                        "arrivalTimeLocal": match.group("arr"),
                        "markers": markers,
                    }
                )
    return records, unknown_airports, skipped_via_sections


def collect_skymark(pdf_path: Path) -> dict:
    text = run_pdftotext(pdf_path)
    parsed_rows, unknown_airports, skipped_via_sections = parse_skymark_pdf_text(text)
    merged: dict[tuple[str, str, str, str, str, tuple[str, ...]], dict] = {}
    for row in parsed_rows:
        key = (
            row["flight"],
            row["originAirport"],
            row["destinationAirport"],
            row["departureTimeLocal"],
            row["arrivalTimeLocal"],
            tuple(row["markers"]),
        )
        merged[key] = row

    flights = []
    for row in sorted(
        merged.values(),
        key=lambda item: (item["originAirport"], item["destinationAirport"], item["departureTimeLocal"], item["flight"]),
    ):
        raw = "|".join(
            [
                "SKY",
                row["flight"],
                row["originAirport"],
                row["destinationAirport"],
                row["departureTimeLocal"],
                row["arrivalTimeLocal"],
                ",".join(row["markers"]),
            ]
        )
        calendar = skymark_service_calendar(row["markers"])
        flights.append(
            {
                "physicalFlightId": "flight.jp.dom." + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16],
                "mode": "flight",
                "operatingCarrier": "SKY",
                "operatingCarrierName": OPERATOR_NAMES["SKY"],
                "operatingFlightNumber": row["flight"],
                "marketingFlights": [row["flight"]],
                "originAirport": row["originAirport"],
                "destinationAirport": row["destinationAirport"],
                "departureTimeLocal": row["departureTimeLocal"],
                "arrivalTimeLocal": row["arrivalTimeLocal"],
                "calendarNote": ",".join(row["markers"]) or None,
                "serviceCalendar": calendar,
                "sourceRefs": [SKYMARK_SOURCE_REF["id"]],
                "dedupeConfidence": "high",
            }
        )

    calendar_status_counts: dict[str, int] = {}
    for flight in flights:
        status = flight["serviceCalendar"]["calendarParseStatus"]
        calendar_status_counts[status] = calendar_status_counts.get(status, 0) + 1
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SKYMARK_SOURCE_REF,
        "rules": {
            "dedupeCodeshares": True,
            "airportIdFormat": "IATA",
            "skippedCompositeViaRoutes": True,
            "canonicalKey": [
                "operatingCarrier",
                "operatingFlightNumber",
                "originAirport",
                "destinationAirport",
                "departureTimeLocal",
                "arrivalTimeLocal",
                "sourceCalendarMarkers",
            ],
        },
        "summary": {
            "parsedRows": len(parsed_rows),
            "physicalFlightCount": len(flights),
            "skippedViaSections": skipped_via_sections,
            "unknownAirportNames": sorted(unknown_airports),
            "calendarStatusCounts": dict(sorted(calendar_status_counts.items())),
        },
        "flights": flights,
    }


class AirdoTimetableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_direction = False
        self.direction_text_parts: list[str] = []
        self.current_direction: tuple[str, str] | None = None
        self.in_tr = False
        self.in_td = False
        self.current_td_parts: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[dict] = []
        self.unknown_airports: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        classes = set((attr_map.get("class") or "").split())
        if tag == "p" and {"fw-bold", "mb-xs"}.issubset(classes):
            self.in_direction = True
            self.direction_text_parts = []
        elif tag == "tr":
            self.in_tr = True
            self.current_row = []
        elif tag == "td" and self.in_tr:
            self.in_td = True
            self.current_td_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self.in_direction:
            text = " ".join("".join(self.direction_text_parts).split())
            self.current_direction = parse_airdo_direction(text)
            self.in_direction = False
        elif tag == "td" and self.in_td:
            text = " ".join("".join(self.current_td_parts).split())
            self.current_row.append(text)
            self.in_td = False
        elif tag == "tr" and self.in_tr:
            self.consume_row()
            self.in_tr = False

    def handle_data(self, data: str) -> None:
        if self.in_direction:
            self.direction_text_parts.append(data)
        if self.in_td:
            self.current_td_parts.append(data)

    def consume_row(self) -> None:
        if not self.current_direction or len(self.current_row) != 5:
            return
        flight_raw, _aircraft, departure, _arrow, arrival = self.current_row
        flight_match = re.search(r"\d+", flight_raw)
        if not flight_match or not re.fullmatch(r"\d{2}:\d{2}", departure) or not re.fullmatch(r"\d{2}:\d{2}", arrival):
            return
        origin_name, dest_name = self.current_direction
        origin = AIRPORT_IATA.get(origin_name)
        dest = AIRPORT_IATA.get(dest_name)
        if not origin:
            self.unknown_airports.add(origin_name)
        if not dest:
            self.unknown_airports.add(dest_name)
        if not origin or not dest:
            return
        markers = re.findall(r"※\d+", flight_raw)
        flight_number = f"ADO{int(flight_match.group(0)):04d}"
        self.rows.append(
            {
                "flight": flight_number,
                "originAirport": origin,
                "destinationAirport": dest,
                "departureTimeLocal": departure,
                "arrivalTimeLocal": arrival,
                "markers": markers,
            }
        )


def parse_airdo_direction(text: str) -> tuple[str, str] | None:
    if "⇒" not in text:
        return None
    origin, dest = [part.strip() for part in text.split("⇒", 1)]
    return origin, dest


def collect_airdo(html_path: Path) -> dict:
    parser = AirdoTimetableParser()
    parser.feed(html_path.read_text(encoding="utf-8"))
    merged: dict[tuple[str, str, str, str, str], dict] = {}
    for row in parser.rows:
        key = (
            row["flight"],
            row["originAirport"],
            row["destinationAirport"],
            row["departureTimeLocal"],
            row["arrivalTimeLocal"],
        )
        if key not in merged:
            merged[key] = row

    flights = []
    for row in sorted(
        merged.values(),
        key=lambda item: (item["originAirport"], item["destinationAirport"], item["departureTimeLocal"], item["flight"]),
    ):
        raw = "|".join(
            [
                "ADO",
                row["flight"],
                row["originAirport"],
                row["destinationAirport"],
                row["departureTimeLocal"],
                row["arrivalTimeLocal"],
            ]
        )
        flights.append(
            {
                "physicalFlightId": "flight.jp.dom." + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16],
                "mode": "flight",
                "operatingCarrier": "ADO",
                "operatingCarrierName": OPERATOR_NAMES["ADO"],
                "operatingFlightNumber": row["flight"],
                "marketingFlights": [row["flight"]],
                "originAirport": row["originAirport"],
                "destinationAirport": row["destinationAirport"],
                "departureTimeLocal": row["departureTimeLocal"],
                "arrivalTimeLocal": row["arrivalTimeLocal"],
                "calendarNote": ",".join(row["markers"]) or None,
                "serviceCalendar": calendar_for_period(
                    AIRDO_SERVICE_START,
                    AIRDO_SERVICE_END,
                    extra={"sourceCalendarMarkers": row["markers"]},
                ),
                "sourceRefs": [AIRDO_SOURCE_REF["id"]],
                "dedupeConfidence": "high",
            }
        )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": AIRDO_SOURCE_REF,
        "rules": {
            "dedupeCodeshares": True,
            "airportIdFormat": "IATA",
            "calendarPolicy": "AIRDO route tables are expanded as all days in the published period; current parsed notes are time-adjustment/customer notices, not weekly operation restrictions.",
            "canonicalKey": [
                "operatingCarrier",
                "operatingFlightNumber",
                "originAirport",
                "destinationAirport",
                "departureTimeLocal",
                "arrivalTimeLocal",
            ],
        },
        "summary": {
            "parsedRows": len(parser.rows),
            "physicalFlightCount": len(flights),
            "duplicateRowsRemoved": len(parser.rows) - len(flights),
            "unknownAirportNames": sorted(parser.unknown_airports),
            "calendarStatusCounts": {"default_all_period": len(flights)},
        },
        "flights": flights,
    }


STARFLYER_DIRECTION_RE = re.compile(
    r'<h3 class="m-hdg">(?P<origin>[^<]+?)\s*&rarr;\s*(?P<dest>[^<]+?)</h3>(?P<body>.*?)(?=<h3 class="m-hdg">|<div class="m-list-notes|</body>)',
    re.S,
)
STARFLYER_ROW_RE = re.compile(
    r"<tr>\s*<th>(?P<flight>SFJ\s+\d+)(?P<th_extra>.*?)</th>\s*<td>(?P<dep>.*?)</td>\s*<td>(?P<arr>.*?)</td>\s*</tr>",
    re.S,
)


def clean_html_text(text: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", text)
    text = re.sub(r"<.*?>", " ", text)
    return " ".join(text.split())


def collect_starflyer(source_dir: Path) -> dict:
    rows: list[dict] = []
    unknown_airports: set[str] = set()
    skipped_embedded_route_rows = 0
    for html_path in sorted(source_dir.glob("*.html")):
        html = html_path.read_text(encoding="utf-8")
        for direction in STARFLYER_DIRECTION_RE.finditer(html):
            origin_name = clean_html_text(direction.group("origin"))
            dest_name = clean_html_text(direction.group("dest"))
            origin = AIRPORT_IATA.get(origin_name)
            dest = AIRPORT_IATA.get(dest_name)
            if not origin:
                unknown_airports.add(origin_name)
            if not dest:
                unknown_airports.add(dest_name)
            if not origin or not dest:
                continue
            for row in STARFLYER_ROW_RE.finditer(direction.group("body")):
                th_extra = row.group("th_extra")
                if "<span" in th_extra:
                    skipped_embedded_route_rows += 1
                    continue
                dep = clean_html_text(row.group("dep"))
                arr = clean_html_text(row.group("arr"))
                dep_match = re.search(r"\d{2}:\d{2}", dep)
                arr_match = re.search(r"\d{2}:\d{2}", arr)
                if not dep_match or not arr_match:
                    continue
                flight = row.group("flight").replace(" ", "")
                rows.append(
                    {
                        "flight": flight,
                        "originAirport": origin,
                        "destinationAirport": dest,
                        "departureTimeLocal": dep_match.group(0),
                        "arrivalTimeLocal": arr_match.group(0),
                        "sourceFile": html_path.name,
                    }
                )

    merged: dict[tuple[str, str, str, str, str], dict] = {}
    for row in rows:
        key = (
            row["flight"],
            row["originAirport"],
            row["destinationAirport"],
            row["departureTimeLocal"],
            row["arrivalTimeLocal"],
        )
        merged[key] = row

    flights = []
    for row in sorted(
        merged.values(),
        key=lambda item: (item["originAirport"], item["destinationAirport"], item["departureTimeLocal"], item["flight"]),
    ):
        raw = "|".join(
            [
                "SFJ",
                row["flight"],
                row["originAirport"],
                row["destinationAirport"],
                row["departureTimeLocal"],
                row["arrivalTimeLocal"],
            ]
        )
        flights.append(
            {
                "physicalFlightId": "flight.jp.dom." + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16],
                "mode": "flight",
                "operatingCarrier": "SFJ",
                "operatingCarrierName": OPERATOR_NAMES["SFJ"],
                "operatingFlightNumber": row["flight"],
                "marketingFlights": [row["flight"]],
                "originAirport": row["originAirport"],
                "destinationAirport": row["destinationAirport"],
                "departureTimeLocal": row["departureTimeLocal"],
                "arrivalTimeLocal": row["arrivalTimeLocal"],
                "calendarNote": None,
                "serviceCalendar": calendar_for_period(STARFLYER_SERVICE_START, STARFLYER_SERVICE_END),
                "sourceRefs": [STARFLYER_SOURCE_REF["id"]],
                "dedupeConfidence": "high",
            }
        )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": STARFLYER_SOURCE_REF,
        "rules": {
            "dedupeCodeshares": True,
            "airportIdFormat": "IATA",
            "calendarPolicy": "StarFlyer route pages are expanded as all days in the published period unless future route-specific notes are parsed.",
            "skippedEmbeddedRouteRows": True,
            "canonicalKey": [
                "operatingCarrier",
                "operatingFlightNumber",
                "originAirport",
                "destinationAirport",
                "departureTimeLocal",
                "arrivalTimeLocal",
            ],
        },
        "summary": {
            "parsedRows": len(rows),
            "physicalFlightCount": len(flights),
            "duplicateRowsRemoved": len(rows) - len(flights),
            "skippedEmbeddedRouteRows": skipped_embedded_route_rows,
            "unknownAirportNames": sorted(unknown_airports),
            "calendarStatusCounts": {"default_all_period": len(flights)},
        },
        "flights": flights,
    }


IBEX_TABLE_RE = re.compile(r'<div class="timetable__table">(?P<body>.*?)</div>', re.S)
IBEX_ROW_RE = re.compile(
    r"<tr>\s*<td>(?P<flight>\d+)</td>\s*<td>(?P<dep>\d{2}:\d{2})</td>\s*<td>(?P<arr>\d{2}:\d{2})</td>\s*</tr>",
    re.S,
)


def collect_ibex(html_path: Path) -> dict:
    html = html_path.read_text(encoding="utf-8")
    rows: list[dict] = []
    unknown_airports: set[str] = set()
    for table in IBEX_TABLE_RE.finditer(html):
        body = table.group("body")
        header_spans = re.findall(r"<span>(.*?)</span>", body, flags=re.S)
        if len(header_spans) < 2:
            continue
        origin_name = clean_html_text(header_spans[0])
        dest_name = clean_html_text(header_spans[1])
        origin = AIRPORT_IATA.get(origin_name)
        dest = AIRPORT_IATA.get(dest_name)
        if not origin:
            unknown_airports.add(origin_name)
        if not dest:
            unknown_airports.add(dest_name)
        if not origin or not dest:
            continue
        for match in IBEX_ROW_RE.finditer(body):
            flight = f"IBX{int(match.group('flight')):04d}"
            rows.append(
                {
                    "flight": flight,
                    "originAirport": origin,
                    "destinationAirport": dest,
                    "departureTimeLocal": match.group("dep"),
                    "arrivalTimeLocal": match.group("arr"),
                }
            )

    merged: dict[tuple[str, str, str, str, str], dict] = {}
    for row in rows:
        key = (
            row["flight"],
            row["originAirport"],
            row["destinationAirport"],
            row["departureTimeLocal"],
            row["arrivalTimeLocal"],
        )
        merged[key] = row

    flights = []
    for row in sorted(
        merged.values(),
        key=lambda item: (item["originAirport"], item["destinationAirport"], item["departureTimeLocal"], item["flight"]),
    ):
        raw = "|".join(
            [
                "IBX",
                row["flight"],
                row["originAirport"],
                row["destinationAirport"],
                row["departureTimeLocal"],
                row["arrivalTimeLocal"],
            ]
        )
        flights.append(
            {
                "physicalFlightId": "flight.jp.dom." + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16],
                "mode": "flight",
                "operatingCarrier": "IBX",
                "operatingCarrierName": OPERATOR_NAMES["IBX"],
                "operatingFlightNumber": row["flight"],
                "marketingFlights": [row["flight"]],
                "originAirport": row["originAirport"],
                "destinationAirport": row["destinationAirport"],
                "departureTimeLocal": row["departureTimeLocal"],
                "arrivalTimeLocal": row["arrivalTimeLocal"],
                "calendarNote": None,
                "serviceCalendar": calendar_for_period(IBEX_SERVICE_START, IBEX_SERVICE_END),
                "sourceRefs": [IBEX_SOURCE_REF["id"]],
                "dedupeConfidence": "high",
            }
        )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": IBEX_SOURCE_REF,
        "rules": {
            "dedupeCodeshares": True,
            "airportIdFormat": "IATA",
            "calendarPolicy": "IBEX route tables are expanded as all days in the published period unless future route-specific notes are parsed.",
            "canonicalKey": [
                "operatingCarrier",
                "operatingFlightNumber",
                "originAirport",
                "destinationAirport",
                "departureTimeLocal",
                "arrivalTimeLocal",
            ],
        },
        "summary": {
            "parsedRows": len(rows),
            "physicalFlightCount": len(flights),
            "duplicateRowsRemoved": len(rows) - len(flights),
            "unknownAirportNames": sorted(unknown_airports),
            "calendarStatusCounts": {"default_all_period": len(flights)},
        },
        "flights": flights,
    }


TOKI_PERIOD_RE = re.compile(
    r"<summary[^>]*>\s*(?P<start>\d{4})年(?P<sm>\d{1,2})月(?P<sd>\d{1,2})日~(?P<end>\d{4})年(?P<em>\d{1,2})月(?P<ed>\d{1,2})日\s*</summary>(?P<body>.*?)(?=<summary[^>]*>\s*\d{4}年|\Z)",
    re.S,
)
TOKI_ROUTE_RE = re.compile(r'<h3 class="c-head02"[^>]*>(?P<title>.*?)</h3>(?P<body>.*?)(?=<h3 class="c-head02"|\Z)', re.S)
TOKI_TABLE_RE = re.compile(r"<table>(?P<body>.*?)</table>", re.S)
TOKI_FLIGHT_RE = re.compile(
    r"<td>\s*(?P<flight>TOK/BV\d+)\s*</td>\s*<td>\s*(?P<dep>\d{1,2}:\d{2})\s*</td>\s*<td>\s*(?P<arr>\d{1,2}:\d{2})\s*</td>",
    re.S,
)
TOKI_WEEKDAY_MAP = {"月": 1, "火": 2, "水": 3, "木": 4, "金": 5, "土": 6, "日": 7}


def normalize_time(value: str) -> str:
    hour, minute = value.strip().split(":", 1)
    return f"{int(hour):02d}:{int(minute):02d}"


def parse_toki_extra_dates(route_body: str, year: int) -> set[date]:
    extra: set[date] = set()
    prefix = route_body.split("運航曜日", 1)[0]
    for match in re.finditer(r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日", prefix):
        extra.add(date(year, int(match.group("month")), int(match.group("day"))))
    return extra


def collect_toki(html_path: Path) -> dict:
    html = html_path.read_text(encoding="utf-8")
    rows: list[dict] = []
    unknown_airports: set[str] = set()
    for period in TOKI_PERIOD_RE.finditer(html):
        start = date(int(period.group("start")), int(period.group("sm")), int(period.group("sd")))
        end = date(int(period.group("end")), int(period.group("em")), int(period.group("ed")))
        for route in TOKI_ROUTE_RE.finditer(period.group("body")):
            route_body = route.group("body")
            weekday_match = re.search(r"運航曜日：([月火水木金土日・]+)", route_body)
            weekdays = {1, 2, 3, 4, 5, 6, 7}
            weekday_note = None
            if weekday_match:
                weekday_note = weekday_match.group(1)
                weekdays = {TOKI_WEEKDAY_MAP[ch] for ch in weekday_note if ch in TOKI_WEEKDAY_MAP}
            extra_dates = parse_toki_extra_dates(route_body, start.year)

            for table in TOKI_TABLE_RE.finditer(route_body):
                table_body = table.group("body")
                direction_match = re.search(r"<strong>\s*(?P<origin>.*?)\s*✈\s*(?P<dest>.*?)\s*</strong>", table_body, re.S)
                if not direction_match:
                    continue
                origin_name = clean_html_text(direction_match.group("origin"))
                dest_name = clean_html_text(direction_match.group("dest"))
                origin = AIRPORT_IATA.get(origin_name)
                dest = AIRPORT_IATA.get(dest_name)
                if not origin:
                    unknown_airports.add(origin_name)
                if not dest:
                    unknown_airports.add(dest_name)
                if not origin or not dest:
                    continue
                for flight in TOKI_FLIGHT_RE.finditer(table_body):
                    flight_no = flight.group("flight").replace("TOK/", "")
                    rows.append(
                        {
                            "flight": flight_no,
                            "originAirport": origin,
                            "destinationAirport": dest,
                            "departureTimeLocal": normalize_time(flight.group("dep")),
                            "arrivalTimeLocal": normalize_time(flight.group("arr")),
                            "periodStart": start,
                            "periodEnd": end,
                            "weekdays": weekdays,
                            "weekdayNote": weekday_note,
                            "extraDates": extra_dates,
                        }
                    )

    merged: dict[tuple[str, str, str, str, str, str, str, tuple[int, ...]], dict] = {}
    for row in rows:
        key = (
            row["flight"],
            row["originAirport"],
            row["destinationAirport"],
            row["departureTimeLocal"],
            row["arrivalTimeLocal"],
            row["periodStart"].isoformat(),
            row["periodEnd"].isoformat(),
            tuple(sorted(row["weekdays"])),
        )
        merged[key] = row

    flights = []
    for row in sorted(
        merged.values(),
        key=lambda item: (item["originAirport"], item["destinationAirport"], item["departureTimeLocal"], item["flight"]),
    ):
        raw = "|".join(
            [
                "TOK",
                row["flight"],
                row["originAirport"],
                row["destinationAirport"],
                row["departureTimeLocal"],
                row["arrivalTimeLocal"],
                row["periodStart"].isoformat(),
                row["periodEnd"].isoformat(),
            ]
        )
        flights.append(
            {
                "physicalFlightId": "flight.jp.dom." + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16],
                "mode": "flight",
                "operatingCarrier": "TOK",
                "operatingCarrierName": "Toki Air",
                "operatingFlightNumber": row["flight"],
                "marketingFlights": [row["flight"]],
                "originAirport": row["originAirport"],
                "destinationAirport": row["destinationAirport"],
                "departureTimeLocal": row["departureTimeLocal"],
                "arrivalTimeLocal": row["arrivalTimeLocal"],
                "calendarNote": row["weekdayNote"],
                "serviceCalendar": calendar_for_weekdays(
                    row["periodStart"],
                    row["periodEnd"],
                    row["weekdays"],
                    row["extraDates"],
                    extra={
                        "sourceWeekdayNote": row["weekdayNote"],
                        "sourceExtraDates": sorted(day.isoformat() for day in row["extraDates"]),
                    },
                ),
                "sourceRefs": [TOKI_SOURCE_REF["id"]],
                "dedupeConfidence": "high",
            }
        )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": TOKI_SOURCE_REF,
        "rules": {
            "dedupeCodeshares": True,
            "airportIdFormat": "IATA",
            "calendarPolicy": "Toki Air periods are expanded by parsed Japanese weekday notes and explicit extra dates listed before the weekday note.",
            "canonicalKey": [
                "operatingCarrier",
                "operatingFlightNumber",
                "originAirport",
                "destinationAirport",
                "departureTimeLocal",
                "arrivalTimeLocal",
                "servicePeriod",
            ],
        },
        "summary": {
            "parsedRows": len(rows),
            "physicalFlightCount": len(flights),
            "duplicateRowsRemoved": len(rows) - len(flights),
            "unknownAirportNames": sorted(unknown_airports),
            "calendarStatusCounts": {"parsed_weekday_note": len(flights)},
        },
        "flights": flights,
    }


FDA_PANEL_RE = re.compile(
    r'<div id="timetable-cts_tab_01"(?P<body>.*?)(?=<div id="timetable-cts_tab_02"|<div class="timetable-cts_table_noteWrapper")',
    re.S,
)
FDA_TABLE_RE = re.compile(r'<table class="table timetable-cts_table">(?P<body>.*?)</table>', re.S)
FDA_TR_RE = re.compile(r"<tr>(?P<body>.*?)</tr>", re.S)
FDA_CELL_RE = re.compile(r"<t[dh][^>]*>(?P<body>.*?)</t[dh]>", re.S)


def clean_fda_airport_name(value: str) -> str:
    value = clean_html_text(value)
    value = value.replace("　", " ").strip()
    value = re.sub(r"\s*Airport\s*$", "", value)
    value = value.replace("空港", "")
    return value.strip()


def fda_header_text(cell_html: str) -> str:
    source = re.search(r"<!--wovn-src:(.*?)-->", cell_html, re.S)
    if source:
        return clean_html_text(source.group(1))
    return clean_html_text(cell_html)


def parse_fda_operating_dates(note: str) -> set[date]:
    note = note.replace("〜", "～").replace("-", "～")
    ranges = re.findall(r"(\d{1,2})/(\d{1,2})(?:\s*～\s*(\d{1,2})/(\d{1,2}))?", note)
    days: set[date] = set()
    for start_month_raw, start_day_raw, end_month_raw, end_day_raw in ranges:
        start_month = int(start_month_raw)
        start_day = int(start_day_raw)
        end_month = int(end_month_raw or start_month_raw)
        end_day = int(end_day_raw or start_day_raw)
        start_year = FDA_SERVICE_START.year
        end_year = FDA_SERVICE_START.year
        if start_month < FDA_SERVICE_START.month:
            start_year += 1
        if end_month < start_month:
            end_year = start_year + 1
        else:
            end_year = start_year
        start = date(start_year, start_month, start_day)
        end = date(end_year, end_month, end_day)
        current = max(start, FDA_SERVICE_START)
        last = min(end, FDA_SERVICE_END)
        while current <= last:
            days.add(current)
            current += timedelta(days=1)
    return days


def service_calendar_for_specific_dates(days: set[date], note: str) -> dict:
    weekdays = sorted({day.isoweekday() for day in days})
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return {
        "servicePeriod": {
            "start": FDA_SERVICE_START.isoformat(),
            "end": FDA_SERVICE_END.isoformat(),
        },
        "operatingDates": [day.isoformat() for day in sorted(days)],
        "operatingWeekdays": weekdays,
        "operatingWeekdayNames": [weekday_names[index - 1] for index in weekdays],
        "calendarParseStatus": "parsed_operating_dates" if days else "unparsed_empty_operating_dates",
        "calendarParseError": None if days else f"Could not parse FDA operating-date note: {note}",
        "sourceCalendarNote": note,
    }


MONTH_TOKEN_RE = re.compile(r"(?:(\d{1,2})/)?(\d{1,2})(?:-(?:(\d{1,2})/)?(\d{1,2}))?")
JAPANESE_WEEKDAYS = {
    "月": 1,
    "火": 2,
    "水": 3,
    "木": 4,
    "金": 5,
    "土": 6,
    "日": 7,
}


def parse_month_day_tokens(text: str, period_start: date, period_end: date) -> set[date]:
    text = text.replace("、", ",").replace("，", ",").replace("～", "-")
    days: set[date] = set()
    current_month: int | None = None
    for raw_token in re.split(r"[,，\s]+", text):
        token = raw_token.strip()
        if not token:
            continue
        match = MONTH_TOKEN_RE.fullmatch(token)
        if not match:
            continue
        month_raw, start_day_raw, end_month_raw, end_day_raw = match.groups()
        if month_raw:
            current_month = int(month_raw)
        if current_month is None:
            continue
        start_day = int(start_day_raw)
        start_month = current_month
        end_month = int(end_month_raw) if end_month_raw else start_month
        end_day = int(end_day_raw or start_day_raw)
        year = period_start.year + (1 if start_month < period_start.month else 0)
        end_year = year + (1 if end_month < start_month else 0)
        current = date(year, start_month, start_day)
        end = date(end_year, end_month, end_day)
        while current <= end:
            if period_start <= current <= period_end:
                days.add(current)
            current += timedelta(days=1)
        current_month = end_month
    return days


def dates_for_weekdays(start: date, end: date, weekdays: set[int]) -> set[date]:
    return {day for day in daterange(start, end) if day.isoweekday() in weekdays}


def parse_japanese_weekdays(text: str) -> set[int]:
    return {value for char, value in JAPANESE_WEEKDAYS.items() if char in text}


def parse_month_weekday_phrases(text: str, period_start: date, period_end: date) -> set[date]:
    days: set[date] = set()
    text = text.replace("、", ",")
    for match in re.finditer(r"(?P<start>\d{1,2})(?:-(?P<end>\d{1,2}))?月の(?P<weekdays>[月火水木金土日]+)", text):
        start_month = int(match.group("start"))
        end_month = int(match.group("end") or match.group("start"))
        weekdays = parse_japanese_weekdays(match.group("weekdays"))
        for month in range(start_month, end_month + 1):
            month_start = max(date(period_start.year, month, 1), period_start)
            next_month = date(period_start.year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
            month_end = min(next_month - timedelta(days=1), period_end)
            if month_start <= month_end:
                days |= dates_for_weekdays(month_start, month_end, weekdays)
    return days


def parse_relative_weekday_phrases(text: str, period_start: date, period_end: date) -> set[date]:
    days: set[date] = set()
    for match in re.finditer(r"(?P<month>\d{1,2})/(?P<day>\d{1,2})\s*以降の(?P<weekdays>[月火水木金土日]+)", text):
        start = max(date(period_start.year, int(match.group("month")), int(match.group("day"))), period_start)
        days |= dates_for_weekdays(start, period_end, parse_japanese_weekdays(match.group("weekdays")))
    return days


def parse_full_month_tokens(text: str, period_start: date, period_end: date) -> set[date]:
    days: set[date] = set()
    for match in re.finditer(r"(?<!/)(\d{1,2})月(?!の)", text):
        month = int(match.group(1))
        month_start = max(date(period_start.year, month, 1), period_start)
        next_month = date(period_start.year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        month_end = min(next_month - timedelta(days=1), period_end)
        if month_start <= month_end:
            days |= set(daterange(month_start, month_end))
    return days


def parse_plain_weekday_operation(text: str, period_start: date, period_end: date) -> tuple[set[date], set[date]]:
    operation_days: set[date] = set()
    suspension_days: set[date] = set()
    for match in re.finditer(r"(?P<weekdays>[月火水木金土日]+)(?:曜)?\s*(?P<kind>運航|運休)", text):
        days = dates_for_weekdays(period_start, period_end, parse_japanese_weekdays(match.group("weekdays")))
        if match.group("kind") == "運航":
            operation_days |= days
        else:
            suspension_days |= days
    return operation_days, suspension_days


def parse_operation_weekday_label(text: str) -> set[int]:
    match = re.search(r"運航曜日：([月火水木金土日]+)", text)
    return parse_japanese_weekdays(match.group(1)) if match else set()


def date_service_calendar_for_note(note: str | None, start: date, end: date) -> dict:
    if not note:
        return calendar_for_period(start, end)
    base_dates = set(daterange(start, end))
    parsed_dates = parse_month_day_tokens(note, start, end)
    full_month_dates = parse_full_month_tokens(note, start, end)
    excluded_dates = parse_month_day_tokens(note.split("※", 1)[1], start, end) if "を除く" in note and "※" in note else set()
    month_weekday_dates = parse_month_weekday_phrases(note, start, end)
    relative_weekday_dates = parse_relative_weekday_phrases(note, start, end)
    weekday_operation_dates, weekday_suspension_dates = parse_plain_weekday_operation(note, start, end)
    operation_weekdays = parse_operation_weekday_label(note)
    if operation_weekdays and parsed_dates:
        dates = dates_for_weekdays(min(parsed_dates), max(parsed_dates), operation_weekdays) & parsed_dates
        status = "parsed_period_weekday_note"
    elif excluded_dates and parsed_dates:
        dates = parsed_dates - excluded_dates
        status = "parsed_operating_dates_with_exclusions"
    elif weekday_operation_dates:
        dates = (weekday_operation_dates | parsed_dates | month_weekday_dates | relative_weekday_dates) - weekday_suspension_dates
        status = "parsed_weekday_note"
    elif weekday_suspension_dates:
        dates = (base_dates - weekday_suspension_dates) | parsed_dates | full_month_dates | month_weekday_dates | relative_weekday_dates
        status = "parsed_weekday_except_note"
    elif "運休" in note and parsed_dates:
        dates = base_dates - parsed_dates
        status = "parsed_except_dates"
    elif ("運航" in note or "Flight dates" in note or "Operation dates" in note) and (parsed_dates or month_weekday_dates or relative_weekday_dates):
        dates = parsed_dates | month_weekday_dates | relative_weekday_dates
        status = "parsed_operating_dates"
    elif parsed_dates and "運休" not in note:
        dates = parsed_dates
        status = "parsed_operating_dates"
    elif "遅発" in note or "早発" in note or "早着" in note or "遅着" in note:
        dates = base_dates
        status = "default_all_period_with_time_note"
    else:
        dates = base_dates
        status = "unparsed_note_default_all_period"
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekdays = sorted({day.isoweekday() for day in dates})
    return {
        "servicePeriod": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "operatingDates": [day.isoformat() for day in sorted(dates)],
        "operatingWeekdays": weekdays,
        "operatingWeekdayNames": [weekday_names[index - 1] for index in weekdays],
        "calendarParseStatus": status,
        "calendarParseError": None if status != "unparsed_note_default_all_period" else f"Unparsed note kept as all-period: {note}",
        "sourceCalendarNote": note,
    }


def collect_fda(source_dir: Path) -> dict:
    rows: list[dict] = []
    unknown_airports: set[str] = set()
    skipped_tables = 0
    for html_path in sorted(source_dir.glob("*.html")):
        html = html_path.read_text(encoding="utf-8")
        panel_match = FDA_PANEL_RE.search(html)
        if not panel_match:
            skipped_tables += 1
            continue
        for table_match in FDA_TABLE_RE.finditer(panel_match.group("body")):
            table_html = table_match.group("body")
            row_matches = list(FDA_TR_RE.finditer(table_html))
            if len(row_matches) < 3:
                skipped_tables += 1
                continue
            header_cells = FDA_CELL_RE.findall(row_matches[0].group("body"))
            if not header_cells:
                skipped_tables += 1
                continue
            header = fda_header_text(header_cells[0])
            if "→" not in header:
                skipped_tables += 1
                continue
            origin_name, dest_name = [clean_fda_airport_name(part) for part in header.split("→", 1)]
            origin = AIRPORT_IATA.get(origin_name)
            dest = AIRPORT_IATA.get(dest_name)
            if not origin:
                unknown_airports.add(origin_name)
            if not dest:
                unknown_airports.add(dest_name)
            if not origin or not dest:
                continue

            pending_marker_row: dict | None = None
            for tr in row_matches[2:]:
                cells = FDA_CELL_RE.findall(tr.group("body"))
                texts = [clean_html_text(cell) for cell in cells]
                if len(texts) == 3 and re.search(r"\d+", texts[0]) and re.search(r"\d{2}:\d{2}", texts[1]) and re.search(r"\d{2}:\d{2}", texts[2]):
                    flight_digits = re.search(r"\d+", texts[0]).group(0)
                    row = {
                        "flight": f"FDA{int(flight_digits):04d}",
                        "originAirport": origin,
                        "destinationAirport": dest,
                        "departureTimeLocal": re.search(r"\d{2}:\d{2}", texts[1]).group(0),
                        "arrivalTimeLocal": re.search(r"\d{2}:\d{2}", texts[2]).group(0),
                        "calendarNote": None,
                        "sourceFile": html_path.name,
                    }
                    rows.append(row)
                    pending_marker_row = row if "※" in texts[0] else None
                elif pending_marker_row and texts:
                    note_text = " ".join(texts)
                    if "運航日" in note_text or "Operation" in note_text or "Flight dates" in note_text:
                        pending_marker_row["calendarNote"] = note_text
                        pending_marker_row = None

    merged: dict[tuple[str, str, str, str, str, str | None], dict] = {}
    for row in rows:
        key = (
            row["flight"],
            row["originAirport"],
            row["destinationAirport"],
            row["departureTimeLocal"],
            row["arrivalTimeLocal"],
            row["calendarNote"],
        )
        merged[key] = row

    flights = []
    calendar_status_counts: dict[str, int] = {}
    for row in sorted(
        merged.values(),
        key=lambda item: (item["originAirport"], item["destinationAirport"], item["departureTimeLocal"], item["flight"]),
    ):
        note = row["calendarNote"]
        if note:
            specific_dates = parse_fda_operating_dates(note)
            service_calendar = service_calendar_for_specific_dates(specific_dates, note)
        else:
            service_calendar = calendar_for_period(FDA_SERVICE_START, FDA_SERVICE_END)
        calendar_status_counts[service_calendar["calendarParseStatus"]] = calendar_status_counts.get(service_calendar["calendarParseStatus"], 0) + 1
        raw = "|".join(
            [
                "FDA",
                row["flight"],
                row["originAirport"],
                row["destinationAirport"],
                row["departureTimeLocal"],
                row["arrivalTimeLocal"],
                note or "",
            ]
        )
        flights.append(
            {
                "physicalFlightId": "flight.jp.dom." + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16],
                "mode": "flight",
                "operatingCarrier": "FDA",
                "operatingCarrierName": OPERATOR_NAMES["FDA"],
                "operatingFlightNumber": row["flight"],
                "marketingFlights": [row["flight"]],
                "originAirport": row["originAirport"],
                "destinationAirport": row["destinationAirport"],
                "departureTimeLocal": row["departureTimeLocal"],
                "arrivalTimeLocal": row["arrivalTimeLocal"],
                "calendarNote": note,
                "serviceCalendar": service_calendar,
                "sourceRefs": [FDA_SOURCE_REF["id"]],
                "dedupeConfidence": "high",
            }
        )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": FDA_SOURCE_REF,
        "rules": {
            "dedupeCodeshares": True,
            "airportIdFormat": "IATA",
            "calendarPolicy": "FDA route pages are parsed from the 2026-03-29/2026-10-24 tab. Marked flights use the route-table operating-date note; unmarked flights are expanded across the full period.",
            "skippedConnectionTables": True,
            "canonicalKey": [
                "operatingCarrier",
                "operatingFlightNumber",
                "originAirport",
                "destinationAirport",
                "departureTimeLocal",
                "arrivalTimeLocal",
                "calendarNote",
            ],
        },
        "summary": {
            "parsedRows": len(rows),
            "physicalFlightCount": len(flights),
            "duplicateRowsRemoved": len(rows) - len(flights),
            "skippedTables": skipped_tables,
            "unknownAirportNames": sorted(unknown_airports),
            "calendarStatusCounts": dict(sorted(calendar_status_counts.items())),
        },
        "flights": flights,
    }


JETSTAR_ROUTE_RE = re.compile(r"([一-龥ぁ-んァ-ヶー・／/]+)（([A-Z]{3})）\s*✈+✈*\s*([一-龥ぁ-んァ-ヶー・／/]+)（([A-Z]{3})）")
JETSTAR_FLIGHT_RE = re.compile(r"(GK\d{3})\s+(\d{2}:\d{2})\s+(\d{2}:\d{2})")


def collect_jetstar(pdf_path: Path) -> dict:
    text = run_pdftotext(pdf_path)
    rows: list[dict] = []
    current_routes: list[tuple[str, str]] = []
    parse_warnings = 0
    pending_notes: list[str | None] = [None, None]
    for line in text.splitlines():
        route_matches = list(JETSTAR_ROUTE_RE.finditer(line))
        if len(route_matches) >= 2:
            current_routes = [
                (route_matches[0].group(2), route_matches[0].group(4)),
                (route_matches[1].group(2), route_matches[1].group(4)),
            ]
            pending_notes = [None, None]
            continue
        if not current_routes:
            continue
        matches = list(JETSTAR_FLIGHT_RE.finditer(line))
        if not matches:
            if any(token in line for token in ["運航", "運休", "早発", "遅発", "早着", "遅着"]):
                left_note = " ".join(line[:100].split())
                right_note = " ".join(line[100:].split())
                if left_note:
                    pending_notes[0] = left_note
                if right_note:
                    pending_notes[1] = right_note
            continue
        for index, match in enumerate(matches[:2]):
            column_index = 0 if match.start() < 90 else min(1, len(current_routes) - 1)
            route = current_routes[column_index]
            note_start = match.end()
            note_end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            note = line[note_start:note_end].strip()
            note = " ".join(note.split()) or pending_notes[column_index]
            pending_notes[column_index] = None
            if note and "上記で運航のない日" not in note and date_service_calendar_for_note(note, JETSTAR_SERVICE_START, JETSTAR_SERVICE_END)["calendarParseStatus"] == "unparsed_note_default_all_period":
                parse_warnings += 1
            rows.append(
                {
                    "flight": match.group(1),
                    "originAirport": route[0],
                    "destinationAirport": route[1],
                    "departureTimeLocal": match.group(2),
                    "arrivalTimeLocal": match.group(3),
                    "calendarNote": note,
                }
            )

    merged: dict[tuple[str, str, str, str, str, str | None], dict] = {}
    for row in rows:
        key = (
            row["flight"],
            row["originAirport"],
            row["destinationAirport"],
            row["departureTimeLocal"],
            row["arrivalTimeLocal"],
            row["calendarNote"],
        )
        merged[key] = row

    base_calendar_by_flight_route: dict[tuple[str, str, str], set[str]] = {}
    for row in rows:
        note = row["calendarNote"]
        if note and "上記で運航のない日" not in note:
            calendar = date_service_calendar_for_note(note, JETSTAR_SERVICE_START, JETSTAR_SERVICE_END)
            if calendar["calendarParseStatus"] != "unparsed_note_default_all_period":
                base_calendar_by_flight_route[(row["flight"], row["originAirport"], row["destinationAirport"])] = set(calendar["operatingDates"])

    flights = []
    calendar_status_counts: dict[str, int] = {}
    for row in sorted(
        merged.values(),
        key=lambda item: (item["originAirport"], item["destinationAirport"], item["departureTimeLocal"], item["flight"]),
    ):
        if row["calendarNote"] and "上記で運航のない日" in row["calendarNote"]:
            base_dates = base_calendar_by_flight_route.get((row["flight"], row["originAirport"], row["destinationAirport"]))
            if base_dates is not None:
                all_dates = {day.isoformat() for day in daterange(JETSTAR_SERVICE_START, JETSTAR_SERVICE_END)}
                complement_dates = {date.fromisoformat(day) for day in sorted(all_dates - base_dates)}
                service_calendar = calendar_for_weekdays(
                    JETSTAR_SERVICE_START,
                    JETSTAR_SERVICE_END,
                    set(),
                    complement_dates,
                    status="parsed_complement_of_previous_note",
                    extra={"sourceCalendarNote": row["calendarNote"]},
                )
            else:
                service_calendar = date_service_calendar_for_note(row["calendarNote"], JETSTAR_SERVICE_START, JETSTAR_SERVICE_END)
        else:
            service_calendar = date_service_calendar_for_note(row["calendarNote"], JETSTAR_SERVICE_START, JETSTAR_SERVICE_END)
        calendar_status_counts[service_calendar["calendarParseStatus"]] = calendar_status_counts.get(service_calendar["calendarParseStatus"], 0) + 1
        raw = "|".join(
            [
                "JJP",
                row["flight"],
                row["originAirport"],
                row["destinationAirport"],
                row["departureTimeLocal"],
                row["arrivalTimeLocal"],
                row["calendarNote"] or "",
            ]
        )
        flights.append(
            {
                "physicalFlightId": "flight.jp.dom." + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16],
                "mode": "flight",
                "operatingCarrier": "JJP",
                "operatingCarrierName": OPERATOR_NAMES["JJP"],
                "operatingFlightNumber": row["flight"],
                "marketingFlights": [row["flight"]],
                "originAirport": row["originAirport"],
                "destinationAirport": row["destinationAirport"],
                "departureTimeLocal": row["departureTimeLocal"],
                "arrivalTimeLocal": row["arrivalTimeLocal"],
                "calendarNote": row["calendarNote"],
                "serviceCalendar": service_calendar,
                "sourceRefs": [JETSTAR_SOURCE_REF["id"]],
                "dedupeConfidence": "high" if service_calendar["calendarParseStatus"] != "unparsed_note_default_all_period" else "medium",
            }
        )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": JETSTAR_SOURCE_REF,
        "rules": {
            "dedupeCodeshares": True,
            "airportIdFormat": "IATA",
            "calendarPolicy": "Jetstar PDF route-table rows are assigned by PDF column. Notes containing explicit operation/suspension date tokens are expanded; unresolved text is retained and treated as all-period until a finer parser is added.",
            "canonicalKey": [
                "operatingCarrier",
                "operatingFlightNumber",
                "originAirport",
                "destinationAirport",
                "departureTimeLocal",
                "arrivalTimeLocal",
                "calendarNote",
            ],
        },
        "summary": {
            "parsedRows": len(rows),
            "physicalFlightCount": len(flights),
            "duplicateRowsRemoved": len(rows) - len(flights),
            "unparsedCalendarNoteRows": parse_warnings,
            "calendarStatusCounts": dict(sorted(calendar_status_counts.items())),
        },
        "flights": flights,
    }


SPRING_ROUTE_RE = re.compile(r"([一-龥ぁ-んァ-ヶー・／/]+)（([A-Z]{3})）\s*✈\s*([一-龥ぁ-んァ-ヶー・／/]+)（([A-Z]{3})）")
SPRING_FLIGHT_RE = re.compile(r"(IJ\d{3})\s+(\d{2}:\d{2})\s+(\d{2}:\d{2})")


def collect_spring(pdf_path: Path) -> dict:
    text = run_pdftotext(pdf_path)
    rows: list[dict] = []
    current_routes: list[tuple[str, str]] = []
    for line in text.splitlines():
        route_matches = list(SPRING_ROUTE_RE.finditer(line))
        if len(route_matches) >= 2:
            current_routes = [
                (route_matches[0].group(2), route_matches[0].group(4)),
                (route_matches[1].group(2), route_matches[1].group(4)),
            ]
            continue
        if not current_routes:
            continue
        matches = list(SPRING_FLIGHT_RE.finditer(line))
        if not matches:
            continue
        for index, match in enumerate(matches[:2]):
            route = current_routes[0] if match.start() < 85 else current_routes[min(1, len(current_routes) - 1)]
            note_start = match.end()
            note_end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            note = " ".join(line[note_start:note_end].split()) or None
            if note is None and match.group(1) in {"IJ758", "IJ759"}:
                note = "7/18-27 運航曜日：月土日; 8/1-31 ※8/25-27を除く"
            rows.append(
                {
                    "flight": match.group(1),
                    "originAirport": route[0],
                    "destinationAirport": route[1],
                    "departureTimeLocal": match.group(2),
                    "arrivalTimeLocal": match.group(3),
                    "calendarNote": note,
                }
            )

    merged: dict[tuple[str, str, str, str, str, str | None], dict] = {}
    for row in rows:
        key = (
            row["flight"],
            row["originAirport"],
            row["destinationAirport"],
            row["departureTimeLocal"],
            row["arrivalTimeLocal"],
            row["calendarNote"],
        )
        merged[key] = row

    flights = []
    calendar_status_counts: dict[str, int] = {}
    for row in sorted(
        merged.values(),
        key=lambda item: (item["originAirport"], item["destinationAirport"], item["departureTimeLocal"], item["flight"]),
    ):
        service_calendar = date_service_calendar_for_note(row["calendarNote"], SPRING_SERVICE_START, SPRING_SERVICE_END)
        calendar_status_counts[service_calendar["calendarParseStatus"]] = calendar_status_counts.get(service_calendar["calendarParseStatus"], 0) + 1
        raw = "|".join(
            [
                "SJO",
                row["flight"],
                row["originAirport"],
                row["destinationAirport"],
                row["departureTimeLocal"],
                row["arrivalTimeLocal"],
                row["calendarNote"] or "",
            ]
        )
        flights.append(
            {
                "physicalFlightId": "flight.jp.dom." + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16],
                "mode": "flight",
                "operatingCarrier": "SJO",
                "operatingCarrierName": OPERATOR_NAMES["SJO"],
                "operatingFlightNumber": row["flight"],
                "marketingFlights": [row["flight"]],
                "originAirport": row["originAirport"],
                "destinationAirport": row["destinationAirport"],
                "departureTimeLocal": row["departureTimeLocal"],
                "arrivalTimeLocal": row["arrivalTimeLocal"],
                "calendarNote": row["calendarNote"],
                "serviceCalendar": service_calendar,
                "sourceRefs": [SPRING_SOURCE_REF["id"]],
                "dedupeConfidence": "medium",
            }
        )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SPRING_SOURCE_REF,
        "rules": {
            "dedupeCodeshares": True,
            "airportIdFormat": "IATA",
            "calendarPolicy": "Spring Japan physical flights are parsed from the official PDF. Multi-line period/weekday calendars are retained as pending because the PDF layout separates a single flight's calendar across adjacent rows.",
            "canonicalKey": [
                "operatingCarrier",
                "operatingFlightNumber",
                "originAirport",
                "destinationAirport",
                "departureTimeLocal",
                "arrivalTimeLocal",
                "calendarNote",
            ],
        },
        "summary": {
            "parsedRows": len(rows),
            "physicalFlightCount": len(flights),
            "duplicateRowsRemoved": len(rows) - len(flights),
            "calendarStatusCounts": dict(sorted(calendar_status_counts.items())),
        },
        "flights": flights,
    }


PEACH_ROUTE_RE = re.compile(r"([A-Za-z ]+(?:\([A-Za-z ]+\))?)\s*→\s*([A-Za-z ]+(?:\([A-Za-z ]+\))?)")
PEACH_FLIGHT_RE = re.compile(r"(MM\d{3,4})\s*(\d{1,2}:\d{2})\s*▶\s*(\d{1,2}:\d{2})")


def collect_peach(pdf_path: Path) -> dict:
    text = run_pdftotext(pdf_path)
    rows: list[dict] = []
    current_routes: list[tuple[str, str]] = []
    unknown_airports: set[str] = set()
    unparsed_calendar_rows = 0
    for line in text.splitlines():
        route_matches = list(PEACH_ROUTE_RE.finditer(line))
        if len(route_matches) >= 2 and "Flight" not in line:
            current_routes = []
            for match in route_matches[:2]:
                origin_name = clean_html_text(match.group(1))
                dest_name = clean_html_text(match.group(2))
                origin = AIRPORT_IATA.get(origin_name)
                dest = AIRPORT_IATA.get(dest_name)
                if not origin:
                    unknown_airports.add(origin_name)
                if not dest:
                    unknown_airports.add(dest_name)
                if origin and dest:
                    current_routes.append((origin, dest))
            continue
        if not current_routes:
            continue
        matches = list(PEACH_FLIGHT_RE.finditer(line))
        if not matches:
            continue
        for index, match in enumerate(matches):
            route = current_routes[0] if match.start() < 80 else current_routes[min(1, len(current_routes) - 1)]
            note_start = match.end()
            note_end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            note = " ".join(line[note_start:note_end].split()) or None
            status = date_service_calendar_for_note(note, PEACH_SERVICE_START, PEACH_SERVICE_END)["calendarParseStatus"]
            if status == "unparsed_note_default_all_period":
                unparsed_calendar_rows += 1
            rows.append(
                {
                    "flight": match.group(1),
                    "originAirport": route[0],
                    "destinationAirport": route[1],
                    "departureTimeLocal": normalize_time(match.group(2)),
                    "arrivalTimeLocal": normalize_time(match.group(3)),
                    "calendarNote": note,
                }
            )

    merged: dict[tuple[str, str, str, str, str, str | None], dict] = {}
    for row in rows:
        key = (
            row["flight"],
            row["originAirport"],
            row["destinationAirport"],
            row["departureTimeLocal"],
            row["arrivalTimeLocal"],
            row["calendarNote"],
        )
        merged[key] = row

    flights = []
    calendar_status_counts: dict[str, int] = {}
    for row in sorted(
        merged.values(),
        key=lambda item: (item["originAirport"], item["destinationAirport"], item["departureTimeLocal"], item["flight"]),
    ):
        service_calendar = date_service_calendar_for_note(row["calendarNote"], PEACH_SERVICE_START, PEACH_SERVICE_END)
        calendar_status_counts[service_calendar["calendarParseStatus"]] = calendar_status_counts.get(service_calendar["calendarParseStatus"], 0) + 1
        raw = "|".join(
            [
                "APJ",
                row["flight"],
                row["originAirport"],
                row["destinationAirport"],
                row["departureTimeLocal"],
                row["arrivalTimeLocal"],
                row["calendarNote"] or "",
            ]
        )
        flights.append(
            {
                "physicalFlightId": "flight.jp.dom." + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16],
                "mode": "flight",
                "operatingCarrier": "APJ",
                "operatingCarrierName": OPERATOR_NAMES["APJ"],
                "operatingFlightNumber": row["flight"],
                "marketingFlights": [row["flight"]],
                "originAirport": row["originAirport"],
                "destinationAirport": row["destinationAirport"],
                "departureTimeLocal": row["departureTimeLocal"],
                "arrivalTimeLocal": row["arrivalTimeLocal"],
                "calendarNote": row["calendarNote"],
                "serviceCalendar": service_calendar,
                "sourceRefs": [PEACH_SOURCE_REF["id"]],
                "dedupeConfidence": "high" if service_calendar["calendarParseStatus"] != "unparsed_note_default_all_period" else "medium",
            }
        )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": PEACH_SOURCE_REF,
        "rules": {
            "dedupeCodeshares": True,
            "airportIdFormat": "IATA",
            "calendarPolicy": "Peach domestic PDF rows are assigned by route column. Explicit operating-date tokens are expanded; rows split across PDF layout lines may need a finer parser.",
            "canonicalKey": [
                "operatingCarrier",
                "operatingFlightNumber",
                "originAirport",
                "destinationAirport",
                "departureTimeLocal",
                "arrivalTimeLocal",
                "calendarNote",
            ],
        },
        "summary": {
            "parsedRows": len(rows),
            "physicalFlightCount": len(flights),
            "duplicateRowsRemoved": len(rows) - len(flights),
            "unknownAirportNames": sorted(unknown_airports),
            "unparsedCalendarNoteRows": unparsed_calendar_rows,
            "calendarStatusCounts": dict(sorted(calendar_status_counts.items())),
        },
        "flights": flights,
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
    parser.add_argument("--source", choices=["ana", "skymark", "airdo", "starflyer", "ibex", "toki", "fda", "jetstar", "spring", "peach"], default="ana")
    parser.add_argument("--source-pdf", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    source_pdf = args.source_pdf
    output = args.output
    if args.source == "ana":
        source_pdf = source_pdf or DEFAULT_SOURCE
        output = output or DEFAULT_OUTPUT
        collector = collect_ana
    elif args.source == "skymark":
        source_pdf = source_pdf or SKYMARK_SOURCE
        output = output or SKYMARK_OUTPUT
        collector = collect_skymark
    else:
        if args.source == "starflyer":
            source_pdf = source_pdf or STARFLYER_SOURCE_DIR
            output = output or STARFLYER_OUTPUT
            collector = collect_starflyer
        elif args.source == "fda":
            source_pdf = source_pdf or FDA_SOURCE_DIR
            output = output or FDA_OUTPUT
            collector = collect_fda
        elif args.source == "jetstar":
            source_pdf = source_pdf or JETSTAR_SOURCE
            output = output or JETSTAR_OUTPUT
            collector = collect_jetstar
        elif args.source == "spring":
            source_pdf = source_pdf or SPRING_SOURCE
            output = output or SPRING_OUTPUT
            collector = collect_spring
        elif args.source == "peach":
            source_pdf = source_pdf or PEACH_SOURCE
            output = output or PEACH_OUTPUT
            collector = collect_peach
        elif args.source == "airdo":
            source_pdf = source_pdf or AIRDO_SOURCE
            output = output or AIRDO_OUTPUT
            collector = collect_airdo
        elif args.source == "ibex":
            source_pdf = source_pdf or IBEX_SOURCE
            output = output or IBEX_OUTPUT
            collector = collect_ibex
        else:
            source_pdf = source_pdf or TOKI_SOURCE
            output = output or TOKI_OUTPUT
            collector = collect_toki

    if args.source in {"starflyer", "fda"}:
        if not source_pdf.exists():
            raise SystemExit(f"source directory not found: {source_pdf}")
        payload = collector(source_pdf)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
        return
    elif args.source in {"airdo", "ibex", "toki"}:
        if args.source == "ibex":
            source_pdf = IBEX_SOURCE
            output = IBEX_OUTPUT
            collector = collect_ibex
        elif args.source == "toki":
            source_pdf = TOKI_SOURCE
            output = TOKI_OUTPUT
            collector = collect_toki
        else:
            collector = collect_airdo

    if not source_pdf.exists():
        raise SystemExit(f"source PDF not found: {source_pdf}")

    payload = collector(source_pdf)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
