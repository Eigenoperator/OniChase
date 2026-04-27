#!/usr/bin/env python3
"""Apply manual physical-station overrides to the v4 nationwide map bundle.

These overrides are intentionally small and explicit.  They cover cases where
the source physical map is correct for its vintage, but later timetable data
references a station opened after the map snapshot.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_v4_japan_physical_map import (
    DEFAULT_AUDIT,
    DEFAULT_OUTPUT,
    build_identity_audit,
    load_json,
    normalize_key,
    stable_id,
    summarize_operators,
    write_json,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OVERRIDES = ROOT / "data" / "v4_manual_physical_station_overrides.json"


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)


def manual_group_id(override_id: str, operator_id: str, line_name: str, name: str) -> str:
    return stable_id("SG_MANUAL", override_id, operator_id, line_name, name)


def manual_station_id(override_id: str, operator_id: str, line_name: str, name: str) -> str:
    return stable_id("PS_MANUAL", override_id, operator_id, line_name, name)


def make_station(override: dict[str, Any], group_id: str, station_id: str) -> dict[str, Any]:
    lon = round(float(override["lon"]), 7)
    lat = round(float(override["lat"]), 7)
    name = str(override["nameJa"])
    return {
        "id": station_id,
        "stationGroupId": group_id,
        "identityVersion": "station_identity_v2",
        "nameJa": name,
        "nameKey": override.get("nameKey") or normalize_key(name),
        "operatorId": override["operatorId"],
        "operatorName": override["operatorName"],
        "lineName": override["lineName"],
        "sourceStationCode": f"manual:{override['id']}",
        "sourceGroupCode": f"manual:{override['id']}",
        "prefectureCode": override.get("prefectureCode"),
        "prefectureNameJa": override.get("prefectureNameJa"),
        "prefectureNameEn": override.get("prefectureNameEn"),
        "prefectureAssignmentMethod": "manual_override",
        "locationNote": override.get("locationNote") or override.get("prefectureNameJa"),
        "lat": lat,
        "lon": lon,
        "stationLine": [[lon, lat]],
        "source": {
            "dataset": "manual_physical_station_overrides",
            "overrideId": override["id"],
            "openedDate": override.get("openedDate"),
            "reason": override.get("reason"),
            "sourceUrls": override.get("sourceUrls", []),
        },
    }


def make_group(override: dict[str, Any], group_id: str, station_id: str) -> dict[str, Any]:
    name = str(override["nameJa"])
    return {
        "id": group_id,
        "identityVersion": "station_identity_v2",
        "groupingMethod": "manual_opened_after_source_snapshot",
        "sourceGroupCodes": [f"manual:{override['id']}"],
        "nameJa": name,
        "nameKeys": [override.get("nameKey") or normalize_key(name)],
        "operatorIds": [override["operatorId"]],
        "operatorNames": [override["operatorName"]],
        "lineNames": [override["lineName"]],
        "prefectureCodes": [override.get("prefectureCode")] if override.get("prefectureCode") else [],
        "prefectureNamesJa": [override.get("prefectureNameJa")] if override.get("prefectureNameJa") else [],
        "prefectureNamesEn": [override.get("prefectureNameEn")] if override.get("prefectureNameEn") else [],
        "locationNote": override.get("locationNote") or override.get("prefectureNameJa"),
        "physicalStationIds": [station_id],
        "centroid": {
            "lat": round(float(override["lat"]), 7),
            "lon": round(float(override["lon"]), 7),
        },
        "physicalStationCount": 1,
    }


def apply_overrides(bundle: dict[str, Any], overrides: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, int]]:
    station_by_id = {station["id"]: station for station in bundle["physicalStations"]}
    group_by_id = {group["id"]: group for group in bundle["stationGroups"]}
    existing_manual_ids = {
        str(station.get("source", {}).get("overrideId"))
        for station in bundle["physicalStations"]
        if station.get("source", {}).get("dataset") == "manual_physical_station_overrides"
    }

    stats = Counter()
    for override in overrides:
        override_id = str(override["id"])
        old_station_ids = [
            station_id
            for station_id, station in station_by_id.items()
            if str(station.get("source", {}).get("overrideId") or "") == override_id
        ]
        old_group_ids = [
            group_id
            for group_id, group in group_by_id.items()
            if any(source_code == f"manual:{override_id}" for source_code in group.get("sourceGroupCodes", []))
        ]
        for station_id in old_station_ids:
            station_by_id.pop(station_id, None)
        for group_id in old_group_ids:
            group_by_id.pop(group_id, None)

        group_id = manual_group_id(override_id, override["operatorId"], override["lineName"], override["nameJa"])
        station_id = manual_station_id(override_id, override["operatorId"], override["lineName"], override["nameJa"])
        station = make_station(override, group_id, station_id)
        group = make_group(override, group_id, station_id)

        if old_station_ids or old_group_ids or override_id in existing_manual_ids or station_id in station_by_id or group_id in group_by_id:
            stats["replaced"] += 1
        else:
            stats["added"] += 1
        station_by_id[station_id] = station
        group_by_id[group_id] = group
        existing_manual_ids.add(override_id)

    bundle["physicalStations"] = sorted(station_by_id.values(), key=lambda item: item["id"])
    bundle["stationGroups"] = sorted(group_by_id.values(), key=lambda item: item["id"])
    bundle["operators"] = summarize_operators(
        bundle["physicalStations"],
        bundle["stationGroups"],
        bundle["trackCenterlines"],
    )
    bundle["counts"] = {
        "physicalStations": len(bundle["physicalStations"]),
        "stationGroups": len(bundle["stationGroups"]),
        "trackCenterlines": len(bundle["trackCenterlines"]),
        "operators": len(bundle["operators"]),
    }
    bundle["generatedAt"] = datetime.now(timezone.utc).isoformat()
    source = bundle.setdefault("source", {})
    notes = source.setdefault("notes", [])
    note = "Manual physical station overrides are applied after the source map snapshot for new stations referenced by current timetable data."
    if note not in notes:
        notes.append(note)
    source["manualPhysicalStationOverridesPath"] = relative(DEFAULT_OVERRIDES)
    return bundle, dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    bundle = load_json(args.bundle)
    overrides_payload = load_json(args.overrides)
    overrides = list(overrides_payload.get("stationOverrides", []))
    updated, stats = apply_overrides(bundle, overrides)
    audit = build_identity_audit(
        updated["physicalStations"],
        updated["stationGroups"],
        updated["trackCenterlines"],
    )
    audit.setdefault("manualPhysicalStationOverrides", {
        "path": relative(args.overrides),
        "appliedCount": len(overrides),
    })
    write_json(args.output, updated)
    write_json(args.audit_output, audit)
    print(
        f"Applied {len(overrides)} manual station override(s): "
        f"{stats.get('added', 0)} added, {stats.get('replaced', 0)} replaced."
    )
    print(
        f"Bundle now has {updated['counts']['physicalStations']} physical stations, "
        f"{updated['counts']['stationGroups']} station groups."
    )
    print(f"Wrote {args.output}")
    print(f"Wrote {args.audit_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
