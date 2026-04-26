#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_v4_japan_physical_map import (
    DEFAULT_N02_SECTIONS,
    DEFAULT_N02_STATIONS,
    DEFAULT_OUTPUT,
    collect_points,
    corrected_line_operator,
    geometry_point,
    load_json,
    operator_id_for,
    station_line_operator_pairs,
    write_json,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAPLIBRE_DIR = ROOT / "docs" / "data" / "v4_maplibre"
DEFAULT_OUTPUT_PATH = ROOT / "data" / "v4_line_presence_audit.json"

LineKey = tuple[str, str]


def line_key(operator_id: Any, line_name: Any) -> LineKey:
    return str(operator_id or "").strip(), str(line_name or "").strip()


def display_path(path: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def pair_label(key: LineKey, names: dict[LineKey, dict[str, str]]) -> dict[str, str]:
    operator_id, line_name = key
    meta = names.get(key, {})
    return {
        "operatorId": operator_id,
        "operatorName": meta.get("operatorName") or operator_id,
        "lineName": line_name,
    }


def counter_sample(counter: Counter[LineKey], names: dict[LineKey, dict[str, str]], limit: int = 40) -> list[dict[str, Any]]:
    rows = []
    for key, count in sorted(counter.items(), key=lambda item: (item[0][0], item[0][1]))[:limit]:
        rows.append({**pair_label(key, names), "count": count})
    return rows


def set_sample(keys: set[LineKey], names: dict[LineKey, dict[str, str]], limit: int = 40) -> list[dict[str, str]]:
    return [pair_label(key, names) for key in sorted(keys)[:limit]]


def mismatch_sample(
    expected: Counter[LineKey],
    actual: Counter[LineKey],
    names: dict[LineKey, dict[str, str]],
    limit: int = 40,
) -> list[dict[str, Any]]:
    mismatches = []
    for key in sorted(set(expected) | set(actual)):
        expected_count = expected.get(key, 0)
        actual_count = actual.get(key, 0)
        if expected_count == actual_count:
            continue
        mismatches.append(
            {
                **pair_label(key, names),
                "expected": expected_count,
                "actual": actual_count,
                "delta": actual_count - expected_count,
            }
        )
    return mismatches[:limit]


def raw_station_counter(path: Path) -> tuple[Counter[LineKey], dict[LineKey, dict[str, str]], Counter[str]]:
    counter: Counter[LineKey] = Counter()
    names: dict[LineKey, dict[str, str]] = {}
    dropped: Counter[str] = Counter()
    for feature in load_json(path).get("features", []):
        props = feature.get("properties", {})
        name = str(props.get("N02_005") or "").strip()
        line_name = str(props.get("N02_003") or "").strip()
        operator_name = str(props.get("N02_004") or "").strip()
        if not name or not line_name or not operator_name:
            dropped["missing_required_property"] += 1
            continue
        if geometry_point(feature.get("geometry", {})) is None:
            dropped["missing_station_geometry"] += 1
            continue
        key = line_key(operator_id_for(operator_name), line_name)
        counter[key] += 1
        names.setdefault(key, {"operatorName": operator_name, "lineName": line_name})
    return counter, names, dropped


def raw_section_counter(
    path: Path,
    known_station_pairs: set[tuple[str, str]],
) -> tuple[Counter[LineKey], dict[LineKey, dict[str, str]], Counter[str], list[dict[str, Any]]]:
    counter: Counter[LineKey] = Counter()
    names: dict[LineKey, dict[str, str]] = {}
    dropped: Counter[str] = Counter()
    corrected_samples: list[dict[str, Any]] = []
    for feature_index, feature in enumerate(load_json(path).get("features", [])):
        props = feature.get("properties", {})
        points = collect_points(feature.get("geometry", {}))
        line_name = str(props.get("N02_003") or "").strip()
        operator_name = str(props.get("N02_004") or "").strip()
        if not line_name or not operator_name:
            dropped["missing_required_property"] += 1
            continue
        if len(points) < 2:
            dropped["missing_track_geometry"] += 1
            continue
        line_name, operator_name, corrected_swap = corrected_line_operator(line_name, operator_name, known_station_pairs)
        if corrected_swap:
            dropped["corrected_line_operator_swap"] += 1
            if len(corrected_samples) < 20:
                corrected_samples.append(
                    {
                        "sourceFeatureIndex": feature_index,
                        "rawLineName": str(props.get("N02_003") or "").strip(),
                        "rawOperatorName": str(props.get("N02_004") or "").strip(),
                        "correctedLineName": line_name,
                        "correctedOperatorName": operator_name,
                    }
                )
        key = line_key(operator_id_for(operator_name), line_name)
        counter[key] += 1
        names.setdefault(key, {"operatorName": operator_name, "lineName": line_name})
    return counter, names, dropped, corrected_samples


def bundle_counters(bundle: dict[str, Any]) -> tuple[Counter[LineKey], Counter[LineKey], dict[LineKey, dict[str, str]]]:
    station_counter: Counter[LineKey] = Counter()
    track_counter: Counter[LineKey] = Counter()
    names: dict[LineKey, dict[str, str]] = {}
    for station in bundle.get("physicalStations", []):
        key = line_key(station.get("operatorId"), station.get("lineName"))
        station_counter[key] += 1
        names.setdefault(key, {"operatorName": station.get("operatorName") or key[0], "lineName": key[1]})
    for track in bundle.get("trackCenterlines", []):
        key = line_key(track.get("operatorId"), track.get("lineName"))
        track_counter[key] += 1
        names.setdefault(key, {"operatorName": track.get("operatorName") or key[0], "lineName": key[1]})
    return station_counter, track_counter, names


def geojson_counter(path: Path, *, count_features: bool) -> Counter[LineKey]:
    counter: Counter[LineKey] = Counter()
    for feature in load_json(path).get("features", []):
        props = feature.get("properties", {})
        key = line_key(props.get("operator_id"), props.get("line_name"))
        if not key[0] or not key[1]:
            continue
        counter[key] += 1 if count_features else 0
        if not count_features:
            counter.setdefault(key, 0)
    return counter


def inventory_counter(path: Path) -> Counter[LineKey]:
    counter: Counter[LineKey] = Counter()
    for line in load_json(path).get("lines", []):
        key = line_key(line.get("operatorId"), line.get("lineName"))
        if key[0] and key[1]:
            counter[key] += 1
    return counter


def build_audit(
    station_path: Path,
    section_path: Path,
    bundle_path: Path,
    maplibre_dir: Path,
) -> dict[str, Any]:
    raw_stations, raw_station_names, raw_station_dropped = raw_station_counter(station_path)
    raw_sections, raw_section_names, raw_section_dropped, raw_section_corrected_samples = raw_section_counter(
        section_path,
        station_line_operator_pairs(load_json(bundle_path).get("physicalStations", [])),
    )
    bundle = load_json(bundle_path)
    bundle_stations, bundle_tracks, bundle_names = bundle_counters(bundle)
    maplibre_stations = geojson_counter(maplibre_dir / "physical_stations.geojson", count_features=True)
    maplibre_tracks = geojson_counter(maplibre_dir / "track_centerlines.geojson", count_features=True)
    maplibre_overview_pairs = set(geojson_counter(maplibre_dir / "track_overview.geojson", count_features=False))
    inventory = inventory_counter(maplibre_dir / "line_inventory.json")

    names = {**raw_station_names, **raw_section_names, **bundle_names}
    raw_station_pairs = set(raw_stations)
    raw_section_pairs = set(raw_sections)
    bundle_station_pairs = set(bundle_stations)
    bundle_track_pairs = set(bundle_tracks)
    bundle_all_pairs = bundle_station_pairs | bundle_track_pairs
    inventory_pairs = set(inventory)

    warnings = {
        "rawStationPairsMissingFromBundleStations": set_sample(raw_station_pairs - bundle_station_pairs, names),
        "rawSectionPairsMissingFromBundleTracks": set_sample(raw_section_pairs - bundle_track_pairs, names),
        "bundleStationPairsMissingFromMapLibreStations": set_sample(bundle_station_pairs - set(maplibre_stations), names),
        "bundleTrackPairsMissingFromMapLibreTracks": set_sample(bundle_track_pairs - set(maplibre_tracks), names),
        "bundleTrackPairsMissingFromMapLibreOverview": set_sample(bundle_track_pairs - maplibre_overview_pairs, names),
        "bundlePairsMissingFromInventory": set_sample(bundle_all_pairs - inventory_pairs, names),
        "inventoryPairsMissingFromBundle": set_sample(inventory_pairs - bundle_all_pairs, names),
        "stationFeatureCountMismatchesRawVsBundle": mismatch_sample(raw_stations, bundle_stations, names),
        "trackFeatureCountMismatchesRawVsBundle": mismatch_sample(raw_sections, bundle_tracks, names),
        "stationFeatureCountMismatchesBundleVsMapLibre": mismatch_sample(bundle_stations, maplibre_stations, names),
        "trackFeatureCountMismatchesBundleVsMapLibre": mismatch_sample(bundle_tracks, maplibre_tracks, names),
    }
    warning_counts = {key: len(value) for key, value in warnings.items()}

    return {
        "schema": "onichase.v4.line_presence_audit.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceBundleSchema": bundle.get("schema"),
        "sourceGeneratedAt": bundle.get("generatedAt"),
        "inputs": {
            "n02Stations": display_path(station_path),
            "n02Sections": display_path(section_path),
            "bundle": display_path(bundle_path),
            "maplibreDir": display_path(maplibre_dir),
        },
        "counts": {
            "rawStationOperatorLinePairs": len(raw_station_pairs),
            "rawSectionOperatorLinePairs": len(raw_section_pairs),
            "bundleStationOperatorLinePairs": len(bundle_station_pairs),
            "bundleTrackOperatorLinePairs": len(bundle_track_pairs),
            "bundleUnionOperatorLinePairs": len(bundle_all_pairs),
            "maplibreStationOperatorLinePairs": len(set(maplibre_stations)),
            "maplibreTrackOperatorLinePairs": len(set(maplibre_tracks)),
            "maplibreOverviewOperatorLinePairs": len(maplibre_overview_pairs),
            "inventoryOperatorLinePairs": len(inventory_pairs),
            "rawValidStationFeatures": sum(raw_stations.values()),
            "rawValidSectionFeatures": sum(raw_sections.values()),
            "bundlePhysicalStations": sum(bundle_stations.values()),
            "bundleTrackCenterlines": sum(bundle_tracks.values()),
            "maplibrePhysicalStations": sum(maplibre_stations.values()),
            "maplibreTrackCenterlines": sum(maplibre_tracks.values()),
            "rawStationDropped": dict(sorted(raw_station_dropped.items())),
            "rawSectionNotes": dict(sorted(raw_section_dropped.items())),
            "warningCounts": warning_counts,
            "totalWarnings": sum(warning_counts.values()),
        },
        "notes": {
            "rawSectionCorrectedLineOperatorSwapSamples": raw_section_corrected_samples,
        },
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whether v4 operator-line pairs survive from raw N02 into bundle and MapLibre exports.")
    parser.add_argument("--n02-stations", type=Path, default=DEFAULT_N02_STATIONS)
    parser.add_argument("--n02-sections", type=Path, default=DEFAULT_N02_SECTIONS)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--maplibre-dir", type=Path, default=DEFAULT_MAPLIBRE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    audit = build_audit(args.n02_stations, args.n02_sections, args.bundle, args.maplibre_dir)
    write_json(args.output, audit)
    counts = audit["counts"]
    print(
        "Audited v4 line presence:",
        f"{counts['bundleUnionOperatorLinePairs']} bundle operator-line pairs,",
        f"{counts['inventoryOperatorLinePairs']} inventory pairs,",
        f"{counts['totalWarnings']} warnings.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
