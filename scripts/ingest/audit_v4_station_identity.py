#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from build_v4_japan_physical_map import (
    DEFAULT_AUDIT,
    DEFAULT_OUTPUT,
    build_identity_audit,
    load_json,
    write_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit station_identity_v2 inside a v4 physical map bundle.")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    bundle = load_json(args.bundle)
    audit = build_identity_audit(
        bundle.get("physicalStations", []),
        bundle.get("stationGroups", []),
        bundle.get("trackCenterlines", []),
    )
    write_json(args.output, audit)
    print(
        "Audited station_identity_v2:",
        f"{audit['counts']['physicalStations']} physical stations,",
        f"{audit['counts']['stationGroups']} station groups,",
        f"{audit['counts']['sameNameSplitNameCount']} same-name split names,",
        f"{audit['counts']['lineCoverageWarningCount']} line coverage warnings.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
