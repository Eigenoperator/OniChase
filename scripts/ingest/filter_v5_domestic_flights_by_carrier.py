#!/usr/bin/env python3
"""Split a collected V5 domestic flight bundle by operating carrier."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--carrier", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    flights = [flight for flight in payload["flights"] if flight.get("operatingCarrier") == args.carrier]
    out = {
        "schemaVersion": payload.get("schemaVersion", 1),
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": payload.get("source"),
        "derivedFrom": str(args.input),
        "rules": {
            "carrierFilter": args.carrier,
            "sourcePolicy": "Derived from an official all-carrier or codeshare-aware source by operatingCarrier; physical flights are not duplicated.",
        },
        "summary": {
            "operatingCarrier": args.carrier,
            "physicalFlightCount": len(flights),
            "sourcePhysicalFlightCount": len(payload.get("flights", [])),
        },
        "flights": flights,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
