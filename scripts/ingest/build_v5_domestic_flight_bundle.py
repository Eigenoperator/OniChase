#!/usr/bin/env python3
"""Build the current V5 domestic flight release bundle.

The input files intentionally include overlapping official sources. This script
chooses one playable record per physical flight while keeping provenance.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/v5_domestic_flights_current_bundle.json"


INPUTS = [
    ("ana", ROOT / "data/v5_domestic_flights_ana_20260701_20261024.json"),
    ("airdo", ROOT / "data/v5_domestic_flights_airdo_20260329_20261024.json"),
    ("skymark", ROOT / "data/v5_domestic_flights_skymark_20260601_20261024.json"),
    ("starflyer", ROOT / "data/v5_domestic_flights_starflyer_20260329_20261024.json"),
    ("ibex", ROOT / "data/v5_domestic_flights_ibex_20260329_20261024.json"),
    ("toki", ROOT / "data/v5_domestic_flights_toki_20260329_20260831.json"),
    ("fda", ROOT / "data/v5_domestic_flights_fda_20260329_20261024.json"),
    ("jetstar", ROOT / "data/v5_domestic_flights_jetstar_20260329_20261024.json"),
    ("spring", ROOT / "data/v5_domestic_flights_spring_20260329_20261024.json"),
    ("peach", ROOT / "data/v5_domestic_flights_peach_20260329_20261024.json"),
    ("jal", ROOT / "data/v5_domestic_flights_jal_20260329_20260531.json"),
    ("solaseed_from_ana", ROOT / "data/v5_domestic_flights_solaseed_from_ana_20260701_20261024.json"),
    ("orc_from_ana", ROOT / "data/v5_domestic_flights_orc_from_ana_20260701_20261024.json"),
    ("amx_from_ana", ROOT / "data/v5_domestic_flights_amx_from_ana_20260701_20261024.json"),
    ("jac_from_ana", ROOT / "data/v5_domestic_flights_jac_from_ana_20260701_20261024.json"),
]

ANA_DIRECT_CARRIERS = {"ANA", "AKX"}
INDEPENDENT_OR_FALLBACK_CARRIERS = {
    "ADO",
    "SKY",
    "SFJ",
    "IBX",
    "TOK",
    "FDA",
    "JJP",
    "SJO",
    "APJ",
    "SNA",
    "ORC",
    "AMX",
    "JAC",
    "JAL",
    "JTA",
    "RAC",
}


def physical_key(flight: dict) -> tuple:
    calendar = flight.get("serviceCalendar") or {}
    period = calendar.get("servicePeriod") or {}
    return (
        flight.get("operatingCarrier"),
        flight.get("operatingFlightNumber") or ",".join(flight.get("marketingFlights") or []),
        flight.get("originAirport"),
        flight.get("destinationAirport"),
        flight.get("departureTimeLocal"),
        flight.get("arrivalTimeLocal"),
        flight.get("calendarNote"),
        period.get("start"),
        period.get("end"),
    )


def fallback_key(flight: dict) -> tuple:
    calendar = flight.get("serviceCalendar") or {}
    period = calendar.get("servicePeriod") or {}
    return (
        flight.get("operatingCarrier"),
        flight.get("originAirport"),
        flight.get("destinationAirport"),
        flight.get("departureTimeLocal"),
        flight.get("arrivalTimeLocal"),
        period.get("start"),
        period.get("end"),
    )


def merge_lists(left: list | None, right: list | None) -> list:
    return sorted({*(left or []), *(right or [])})


def read_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    selected: dict[tuple, dict] = {}
    skipped_from_ana_codeshare = 0
    duplicate_rows_merged = 0
    loaded_files = []

    for source_name, path in INPUTS:
        payload = read_payload(path)
        loaded_files.append({"name": source_name, "path": str(path.relative_to(ROOT)), "flightCount": len(payload.get("flights", []))})
        for flight in payload.get("flights", []):
            carrier = flight.get("operatingCarrier")
            if source_name == "ana" and carrier not in ANA_DIRECT_CARRIERS:
                skipped_from_ana_codeshare += 1
                continue
            if source_name != "ana" and carrier not in INDEPENDENT_OR_FALLBACK_CARRIERS:
                continue

            key = physical_key(flight)
            existing_key = selected.get(key) and key

            if existing_key:
                existing = selected[existing_key]
                existing["marketingFlights"] = merge_lists(existing.get("marketingFlights"), flight.get("marketingFlights"))
                existing["sourceRefs"] = merge_lists(existing.get("sourceRefs"), flight.get("sourceRefs"))
                duplicate_rows_merged += 1
            else:
                selected[key] = dict(flight)

    flights = sorted(
        selected.values(),
        key=lambda item: (
            item.get("originAirport") or "",
            item.get("destinationAirport") or "",
            item.get("departureTimeLocal") or "",
            item.get("operatingCarrier") or "",
            item.get("operatingFlightNumber") or "",
        ),
    )
    carrier_counts = Counter(flight.get("operatingCarrier") for flight in flights)
    calendar_counts = Counter((flight.get("serviceCalendar") or {}).get("calendarParseStatus") for flight in flights)
    missing_required = []
    for flight in flights:
        for field in ["physicalFlightId", "operatingCarrier", "originAirport", "destinationAirport", "departureTimeLocal", "arrivalTimeLocal", "serviceCalendar"]:
            if not flight.get(field):
                missing_required.append({"physicalFlightId": flight.get("physicalFlightId"), "field": field})

    out = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "periodCoverage": {
            "note": "Current bundle mixes available official periods. JAL/JTA/RAC full 2026 summer timetable is not yet available from the official timetable page.",
        },
        "rules": {
            "oneRecordPerPhysicalFlight": True,
            "anaCodesharePolicy": "ANA all-area timetable is used for ANA/AKX direct records and as fallback split artifacts for SNA/ORC/AMX/JAC; independent operator sources override ANA-marketed ADO/SFJ/IBX where available.",
            "dedupeKeys": ["carrier+flight+airports+times+calendarNote", "carrier+airports+times fallback"],
        },
        "inputs": loaded_files,
        "summary": {
            "physicalFlightCount": len(flights),
            "carrierCounts": dict(sorted(carrier_counts.items())),
            "calendarStatusCounts": dict(sorted(calendar_counts.items())),
            "skippedAnaCodeshareRows": skipped_from_ana_codeshare,
            "duplicateRowsMerged": duplicate_rows_merged,
            "missingRequiredFieldCount": len(missing_required),
            "remainingMajorSourceGaps": ["JAL/JTA/RAC official July-August timetable"],
            "knownCalendarParserGaps": {
                "Jetstar": 7,
                "SpringJapan": 4,
            },
        },
        "missingRequiredFields": missing_required[:50],
        "flights": flights,
    }

    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
