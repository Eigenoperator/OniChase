#!/usr/bin/env python3
"""Lightweight V5 data readiness audit.

This reads published docs/data artifacts and writes a compact JSON report. It
does not rebuild bundles or scan external sources.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "data" / "v5_data_readiness_audit.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_data_readiness_audit.json"


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_json_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def count_port_connectors(port_connectors: dict) -> dict:
    ports = port_connectors.get("ports") or {}
    counts = Counter()
    ports_with = Counter()
    for access in ports.values():
      for key, label in (("rail", "rail"), ("busStops", "bus"), ("airports", "airport")):
          n = len(access.get(key) or [])
          counts[label] += n
          if n:
              ports_with[label] += 1
    return {
        "portCount": len(ports),
        "connectorCounts": dict(sorted(counts.items())),
        "portsWithConnectorCounts": dict(sorted(ports_with.items())),
        "maxConnectorMeters": port_connectors.get("maxConnectorMeters"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    args = parser.parse_args()

    failures: list[dict] = []

    flights = read_json(ROOT / "docs/data/v5_domestic_flights_current_bundle.json")
    ships = read_json(ROOT / "docs/data/v5_ship_timetable_current_bundle.json")
    airport_bus = read_json(ROOT / "docs/data/v5_airport_bus_access_audit.json")
    port_connectors = read_json(ROOT / "docs/data/v5_port_connectors.json")
    remote_readiness = read_json(ROOT / "docs/data/v5_remote_ship_bus_readiness_audit.json")
    remote_quality = read_json(ROOT / "docs/data/v5_remote_ship_bus_quality_review_queue.json")
    remote_runtime = read_json(ROOT / "docs/data/v5_remote_ship_bus_runtime_smoke.json")
    bus_bundle = read_json_gz(ROOT / "docs/data/v5_bus_gtfs_current_bundle.json.gz")

    bus_class_counts = Counter(route.get("serviceClass") or "unknown" for route in bus_bundle.get("routes", []))
    bus_counts = {
        "routeCount": len(bus_bundle.get("routes", [])),
        "tripCount": len(bus_bundle.get("trips", [])),
        "stopCount": len(bus_bundle.get("stops", [])),
        "stopTimeCount": len(bus_bundle.get("stopTimes", [])),
        "walkingConnectorCount": len(bus_bundle.get("walkingConnectors", [])),
        "serviceClassCounts": dict(sorted(bus_class_counts.items())),
    }

    airport_summary = airport_bus.get("summary") or {}
    remote_readiness_summary = remote_readiness.get("summary") or {}
    remote_quality_summary = remote_quality.get("summary") or {}
    remote_runtime_summary = remote_runtime.get("summary") or {}

    def check(condition: bool, message: str, details=None) -> None:
        if not condition:
            failures.append({"message": message, "details": details or {}})

    check((airport_summary.get("airportClassCoveredCount") or 0) >= 75, "Airport bus coverage below 75", airport_summary)
    check((airport_summary.get("documentedNoPublicBusCount") or 0) == 1, "Airport documented no-public-bus count changed", airport_summary)
    check((airport_summary.get("undocumentedNoNearbyStopCount") or 0) == 0, "Airport has undocumented no-nearby-stop gaps", airport_summary)
    check((ships.get("metadata") or {}).get("sailingCount", 0) > 0, "No promoted ship sailings", ships.get("metadata"))
    check(remote_readiness_summary.get("pendingPortCount") == 0, "Remote ship-bus pending ports remain", remote_readiness_summary)
    check(remote_readiness_summary.get("manualCoordinateStopRefCount") == 0, "Remote ship-bus manual coordinate refs remain", remote_readiness_summary)
    check(remote_quality_summary.get("coordinateReviewCount") == 0, "Remote ship-bus coordinate review queue is not empty", remote_quality_summary)
    check(remote_quality_summary.get("weakTransferReviewCount") == 0, "Remote ship-bus weak transfer queue is not empty", remote_quality_summary)
    check(remote_runtime_summary.get("missingRuntimeRouteCount") == 0, "Remote ship-bus runtime routes missing", remote_runtime_summary)
    check(remote_runtime_summary.get("noWeekdayTripRouteCount") == 0, "Remote ship-bus runtime routes without weekday trips", remote_runtime_summary)
    check(bus_class_counts.get("bus_airport", 0) > 0, "No airport bus routes in runtime bundle", bus_counts)

    report = {
        "schemaVersion": "v5_data_readiness_audit_v1",
        "summary": {
            "failureCount": len(failures),
            "flightCount": len(flights.get("flights", [])),
            "flightAirportCount": len({item.get("originAirport") for item in flights.get("flights", []) if item.get("originAirport")} | {item.get("destinationAirport") for item in flights.get("flights", []) if item.get("destinationAirport")}),
            "shipRouteCount": (ships.get("metadata") or {}).get("routeCount"),
            "shipSailingCount": (ships.get("metadata") or {}).get("sailingCount"),
            "airportBusCoverage": airport_summary,
            "portConnectors": count_port_connectors(port_connectors),
            "busRuntime": bus_counts,
            "remoteShipBusReadiness": remote_readiness_summary,
            "remoteShipBusQuality": remote_quality_summary,
            "remoteShipBusRuntime": remote_runtime_summary,
            "busGameplayScope": "airport connectors plus port connector routes/trips only; ordinary local/highway/night stays source-side",
        },
        "failures": failures,
    }

    for output in (args.output, args.docs_output):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if failures:
        print(f"FAIL v5 data readiness: failures={len(failures)}")
        return 1
    print(
        "OK v5 data readiness: "
        f"flights={report['summary']['flightCount']} "
        f"airports={airport_summary.get('airportClassCoveredCount')}/{airport_summary.get('airportCount')}+{airport_summary.get('documentedNoPublicBusCount')}no-bus "
        f"ships={report['summary']['shipSailingCount']} "
        f"busRoutes={bus_counts['routeCount']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
