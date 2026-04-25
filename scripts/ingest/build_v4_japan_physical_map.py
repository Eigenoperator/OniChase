#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_N02_STATIONS = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_Station.geojson"
DEFAULT_N02_SECTIONS = ROOT / "data" / "raw_n02_24" / "UTF-8" / "N02-24_RailroadSection.geojson"
DEFAULT_OUTPUT = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_AUDIT = ROOT / "data" / "v4_station_identity_audit.json"


OPERATOR_NAME_TO_ID = {
    "北海道旅客鉄道": "jr_hokkaido",
    "東日本旅客鉄道": "jr_east",
    "東海旅客鉄道": "jr_central",
    "西日本旅客鉄道": "jr_west",
    "四国旅客鉄道": "jr_shikoku",
    "九州旅客鉄道": "jr_kyushu",
    "日本貨物鉄道": "jr_freight",
    "東京地下鉄": "tokyo_metro",
    "東京都": "toei",
    "東京都交通局": "toei",
    "京王電鉄": "keio",
    "京浜急行電鉄": "keikyu",
    "京急電鉄": "keikyu",
    "京成電鉄": "keisei",
    "小田急電鉄": "odakyu",
    "西武鉄道": "seibu",
    "東急電鉄": "tokyu",
    "東京急行電鉄": "tokyu",
    "東武鉄道": "tobu",
    "相模鉄道": "sotetsu",
    "東京臨海高速鉄道": "rinkai",
    "ゆりかもめ": "yurikamome",
    "東京モノレール": "tokyo_monorail",
    "多摩都市モノレール": "tama_monorail",
    "首都圏新都市鉄道": "tsukuba_express",
    "埼玉高速鉄道": "saitama_railway",
}


def load_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write(text)
        return
    path.write_text(text, encoding="utf-8")


def normalize_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = text.replace("ヶ", "ケ").replace("ヵ", "カ").replace("髙", "高").replace("﨑", "崎")
    text = re.sub(r"[\(（\[【〔〈<].*?[\)）\]】〕〉>]", "", text)
    text = re.sub(r"[\s\-‐‑‒–—ー・･'’`/／]", "", text)
    return text


def slug(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).upper()
    text = re.sub(r"[^A-Z0-9]+", "_", text).strip("_")
    return text[:64]


def stable_hash(*parts: Any, length: int = 14) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length].upper()


def stable_id(prefix: str, *parts: Any) -> str:
    readable = slug(parts[0]) if parts else ""
    digest = stable_hash(*parts)
    if readable and re.search(r"[A-Z]", readable):
        return f"{prefix}_{readable}_{digest}"
    return f"{prefix}_{digest}"


def operator_id_for(value: Any) -> str:
    text = str(value or "").strip()
    return OPERATOR_NAME_TO_ID.get(text) or normalize_key(text) or "unknown_operator"


def collect_points(geometry: dict[str, Any]) -> list[list[float]]:
    coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if not coords:
        return []
    kind = geometry.get("type")
    if kind == "Point":
        return [[round(float(coords[0]), 7), round(float(coords[1]), 7)]]
    if kind == "LineString":
        return [
            [round(float(point[0]), 7), round(float(point[1]), 7)]
            for point in coords
            if isinstance(point, list) and len(point) >= 2
        ]
    if kind == "MultiLineString":
        points: list[list[float]] = []
        for part in coords:
            points.extend(
                [round(float(point[0]), 7), round(float(point[1]), 7)]
                for point in part
                if isinstance(point, list) and len(point) >= 2
            )
        return points
    return []


def geometry_point(geometry: dict[str, Any]) -> tuple[float, float] | None:
    points = collect_points(geometry)
    if not points:
        return None
    lon = sum(point[0] for point in points) / len(points)
    lat = sum(point[1] for point in points) / len(points)
    return round(lat, 7), round(lon, 7)


def fallback_group_key(name_key: str, lat: float, lon: float) -> str:
    # Roughly one urban block. This intentionally prevents same-name stations
    # in different cities from collapsing into one gameplay interchange.
    return f"fallback:{name_key}:{round(lat, 3):.3f}:{round(lon, 3):.3f}"


def station_group_id_for(props: dict[str, Any], name_key: str, lat: float, lon: float) -> tuple[str, str, str | None]:
    group_code = str(props.get("N02_005g") or "").strip()
    if group_code:
        return f"SG_N02G_{slug(group_code) or stable_hash(group_code, length=10)}", "n02_group_code", group_code
    key = fallback_group_key(name_key, lat, lon)
    return stable_id("SG_FALLBACK", key), "name_plus_position_fallback", None


def build_physical_stations(station_features: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    physical_stations: list[dict[str, Any]] = []
    groups: dict[str, dict[str, Any]] = {}

    for feature_index, feature in enumerate(station_features):
        props = feature.get("properties", {})
        name = str(props.get("N02_005") or "").strip()
        line_name = str(props.get("N02_003") or "").strip()
        operator_name = str(props.get("N02_004") or "").strip()
        if not name or not line_name or not operator_name:
            continue
        point = geometry_point(feature.get("geometry", {}))
        if point is None:
            continue
        lat, lon = point
        name_key = normalize_key(name)
        operator_id = operator_id_for(operator_name)
        station_group_id, grouping_method, group_code = station_group_id_for(props, name_key, lat, lon)
        source_station_code = str(props.get("N02_005c") or "").strip() or None
        station_line = collect_points(feature.get("geometry", {}))
        physical_id = stable_id(
            "PS",
            source_station_code or name,
            operator_name,
            line_name,
            name,
            lat,
            lon,
            feature_index,
        )
        physical_stations.append(
            {
                "id": physical_id,
                "stationGroupId": station_group_id,
                "identityVersion": "station_identity_v2",
                "nameJa": name,
                "nameKey": name_key,
                "operatorId": operator_id,
                "operatorName": operator_name,
                "lineName": line_name,
                "sourceStationCode": source_station_code,
                "sourceGroupCode": group_code,
                "lat": lat,
                "lon": lon,
                "stationLine": station_line,
                "source": {
                    "dataset": "mlit_n02_2024",
                    "featureIndex": feature_index,
                    "railwayClass": props.get("N02_001"),
                    "railwayType": props.get("N02_002"),
                },
            }
        )

        group = groups.setdefault(
            station_group_id,
            {
                "id": station_group_id,
                "identityVersion": "station_identity_v2",
                "groupingMethod": grouping_method,
                "sourceGroupCodes": [],
                "nameJa": name,
                "nameKeys": set(),
                "operatorIds": set(),
                "operatorNames": set(),
                "lineNames": set(),
                "physicalStationIds": [],
                "_lat_sum": 0.0,
                "_lon_sum": 0.0,
            },
        )
        if group_code and group_code not in group["sourceGroupCodes"]:
            group["sourceGroupCodes"].append(group_code)
        group["nameKeys"].add(name_key)
        group["operatorIds"].add(operator_id)
        group["operatorNames"].add(operator_name)
        group["lineNames"].add(line_name)
        group["physicalStationIds"].append(physical_id)
        group["_lat_sum"] += lat
        group["_lon_sum"] += lon

    station_groups: list[dict[str, Any]] = []
    for group in groups.values():
        count = len(group["physicalStationIds"])
        station_groups.append(
            {
                "id": group["id"],
                "identityVersion": group["identityVersion"],
                "groupingMethod": group["groupingMethod"],
                "sourceGroupCodes": sorted(group["sourceGroupCodes"]),
                "nameJa": group["nameJa"],
                "nameKeys": sorted(group["nameKeys"]),
                "operatorIds": sorted(group["operatorIds"]),
                "operatorNames": sorted(group["operatorNames"]),
                "lineNames": sorted(group["lineNames"]),
                "physicalStationIds": sorted(group["physicalStationIds"]),
                "centroid": {
                    "lat": round(group["_lat_sum"] / count, 7),
                    "lon": round(group["_lon_sum"] / count, 7),
                },
                "physicalStationCount": count,
            }
        )

    return (
        sorted(physical_stations, key=lambda item: item["id"]),
        sorted(station_groups, key=lambda item: item["id"]),
    )


def station_line_operator_pairs(physical_stations: list[dict[str, Any]]) -> set[tuple[str, str]]:
    return {
        (station["lineName"], station["operatorName"])
        for station in physical_stations
        if station.get("lineName") and station.get("operatorName")
    }


def corrected_line_operator(
    line_name: str,
    operator_name: str,
    known_pairs: set[tuple[str, str]],
) -> tuple[str, str, bool]:
    if (line_name, operator_name) in known_pairs:
        return line_name, operator_name, False
    if (operator_name, line_name) in known_pairs:
        return operator_name, line_name, True
    return line_name, operator_name, False


def build_track_centerlines(section_features: list[dict[str, Any]], known_pairs: set[tuple[str, str]]) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    for feature_index, feature in enumerate(section_features):
        props = feature.get("properties", {})
        points = collect_points(feature.get("geometry", {}))
        if len(points) < 2:
            continue
        line_name = str(props.get("N02_003") or "").strip()
        operator_name = str(props.get("N02_004") or "").strip()
        if not line_name or not operator_name:
            continue
        line_name, operator_name, corrected_swap = corrected_line_operator(line_name, operator_name, known_pairs)
        operator_id = operator_id_for(operator_name)
        track_id = stable_id(
            "TRK",
            operator_name,
            line_name,
            props.get("N02_001"),
            props.get("N02_002"),
            feature_index,
            points[0],
            points[-1],
        )
        tracks.append(
            {
                "id": track_id,
                "operatorId": operator_id,
                "operatorName": operator_name,
                "lineName": line_name,
                "railwayClass": props.get("N02_001"),
                "railwayType": props.get("N02_002"),
                "points": points,
                "source": {
                    "dataset": "mlit_n02_2024",
                    "featureIndex": feature_index,
                    "correctedLineOperatorSwap": corrected_swap,
                },
            }
        )
    return sorted(tracks, key=lambda item: item["id"])


def summarize_operators(
    physical_stations: list[dict[str, Any]],
    station_groups: list[dict[str, Any]],
    tracks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    station_counts = Counter(station["operatorId"] for station in physical_stations)
    group_counts: Counter[str] = Counter()
    for group in station_groups:
        for operator_id in group["operatorIds"]:
            group_counts[operator_id] += 1
    track_counts = Counter(track["operatorId"] for track in tracks)
    operator_names: dict[str, Counter[str]] = defaultdict(Counter)
    for station in physical_stations:
        operator_names[station["operatorId"]][station["operatorName"]] += 1
    for track in tracks:
        operator_names[track["operatorId"]][track["operatorName"]] += 1

    operators = sorted(set(station_counts) | set(group_counts) | set(track_counts))
    return [
        {
            "operatorId": operator_id,
            "nameJa": operator_names[operator_id].most_common(1)[0][0] if operator_names[operator_id] else operator_id,
            "physicalStationCount": station_counts.get(operator_id, 0),
            "stationGroupCount": group_counts.get(operator_id, 0),
            "trackCenterlineCount": track_counts.get(operator_id, 0),
        }
        for operator_id in operators
    ]


def build_identity_audit(physical_stations: list[dict[str, Any]], station_groups: list[dict[str, Any]], tracks: list[dict[str, Any]]) -> dict[str, Any]:
    groups_by_id = {group["id"]: group for group in station_groups}
    name_to_groups: dict[str, set[str]] = defaultdict(set)
    name_to_physical: Counter[str] = Counter()
    group_methods = Counter(group["groupingMethod"] for group in station_groups)
    group_code_count = sum(1 for station in physical_stations if station.get("sourceGroupCode"))

    for station in physical_stations:
        name_key = station["nameKey"]
        name_to_groups[name_key].add(station["stationGroupId"])
        name_to_physical[name_key] += 1

    same_name_split = [
        {
            "nameKey": name_key,
            "displayNames": sorted({groups_by_id[group_id]["nameJa"] for group_id in group_ids if group_id in groups_by_id})[:8],
            "stationGroupCount": len(group_ids),
            "physicalStationCount": name_to_physical[name_key],
            "sampleStationGroupIds": sorted(group_ids)[:8],
        }
        for name_key, group_ids in name_to_groups.items()
        if len(group_ids) > 1
    ]
    same_name_split.sort(key=lambda item: (-item["stationGroupCount"], item["nameKey"]))

    multi_name_groups = [
        {
            "stationGroupId": group["id"],
            "nameJa": group["nameJa"],
            "nameKeys": group["nameKeys"],
            "operatorNames": group["operatorNames"][:8],
            "lineNames": group["lineNames"][:8],
        }
        for group in station_groups
        if len(group["nameKeys"]) > 1
    ]
    multi_name_groups.sort(key=lambda item: (item["stationGroupId"]))

    line_coverage: dict[tuple[str, str], dict[str, Any]] = {}
    for station in physical_stations:
        key = (station["operatorId"], station["lineName"])
        entry = line_coverage.setdefault(
            key,
            {
                "operatorId": station["operatorId"],
                "operatorName": station["operatorName"],
                "lineName": station["lineName"],
                "physicalStationCount": 0,
                "stationGroupIds": set(),
                "trackCenterlineCount": 0,
            },
        )
        entry["physicalStationCount"] += 1
        entry["stationGroupIds"].add(station["stationGroupId"])
    for track in tracks:
        key = (track["operatorId"], track["lineName"])
        entry = line_coverage.setdefault(
            key,
            {
                "operatorId": track["operatorId"],
                "operatorName": track["operatorName"],
                "lineName": track["lineName"],
                "physicalStationCount": 0,
                "stationGroupIds": set(),
                "trackCenterlineCount": 0,
            },
        )
        entry["trackCenterlineCount"] += 1

    missing_station_or_track = []
    for entry in line_coverage.values():
        group_count = len(entry["stationGroupIds"])
        if entry["physicalStationCount"] == 0 or entry["trackCenterlineCount"] == 0:
            missing_station_or_track.append(
                {
                    "operatorId": entry["operatorId"],
                    "operatorName": entry["operatorName"],
                    "lineName": entry["lineName"],
                    "physicalStationCount": entry["physicalStationCount"],
                    "stationGroupCount": group_count,
                    "trackCenterlineCount": entry["trackCenterlineCount"],
                }
            )
    missing_station_or_track.sort(key=lambda item: (item["operatorId"], item["lineName"]))

    return {
        "schema": "onichase.v4.station_identity_audit.v1",
        "identityVersion": "station_identity_v2",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "physicalStations": len(physical_stations),
            "stationGroups": len(station_groups),
            "trackCenterlines": len(tracks),
            "groupingMethods": dict(sorted(group_methods.items())),
            "physicalStationsWithN02GroupCode": group_code_count,
            "physicalStationsWithoutN02GroupCode": len(physical_stations) - group_code_count,
            "sameNameSplitNameCount": len(same_name_split),
            "multiNameStationGroupCount": len(multi_name_groups),
            "lineCoverageWarningCount": len(missing_station_or_track),
        },
        "sameNameSplitSamples": same_name_split[:40],
        "multiNameStationGroupSamples": multi_name_groups[:40],
        "lineCoverageWarnings": missing_station_or_track[:80],
    }


def build_bundle(station_path: Path, section_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    station_features = load_json(station_path).get("features", [])
    section_features = load_json(section_path).get("features", [])
    physical_stations, station_groups = build_physical_stations(station_features)
    tracks = build_track_centerlines(section_features, station_line_operator_pairs(physical_stations))
    audit = build_identity_audit(physical_stations, station_groups, tracks)
    operators = summarize_operators(physical_stations, station_groups, tracks)
    bundle = {
        "schema": "onichase.v4.japan_physical_map.v1",
        "identityVersion": "station_identity_v2",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "id": "mlit_n02_2024",
            "stationPath": str(station_path.relative_to(ROOT) if station_path.is_relative_to(ROOT) else station_path),
            "railroadSectionPath": str(section_path.relative_to(ROOT) if section_path.is_relative_to(ROOT) else section_path),
            "notes": [
                "Physical stations preserve real N02 station geometries.",
                "Station groups are gameplay/interchange identity only; they do not replace physical station coordinates.",
                "N02_005g group code is used first, with name-plus-position fallback only when no source group code exists.",
            ],
        },
        "counts": {
            "physicalStations": len(physical_stations),
            "stationGroups": len(station_groups),
            "trackCenterlines": len(tracks),
            "operators": len(operators),
        },
        "operators": operators,
        "stationGroups": station_groups,
        "physicalStations": physical_stations,
        "trackCenterlines": tracks,
    }
    return bundle, audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v4 nationwide physical railway map from MLIT N02-2024.")
    parser.add_argument("--n02-stations", type=Path, default=DEFAULT_N02_STATIONS)
    parser.add_argument("--n02-sections", type=Path, default=DEFAULT_N02_SECTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    bundle, audit = build_bundle(args.n02_stations, args.n02_sections)
    write_json(args.output, bundle)
    write_json(args.audit_output, audit)
    print(
        "Built v4 physical map:",
        f"{bundle['counts']['physicalStations']} physical stations,",
        f"{bundle['counts']['stationGroups']} station groups,",
        f"{bundle['counts']['trackCenterlines']} track centerlines,",
        f"{bundle['counts']['operators']} operators.",
    )
    print(
        "Identity audit:",
        f"{audit['counts']['sameNameSplitNameCount']} same-name split names,",
        f"{audit['counts']['multiNameStationGroupCount']} multi-name groups,",
        f"{audit['counts']['lineCoverageWarningCount']} line coverage warnings.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
