#!/usr/bin/env python3
"""Audit timetable coverage for JR-company physical lines in v4.

The physical map is line/operator oriented, while the current timetable corpus
still contains a mixture of v3 service-family ids, shinkansen families, and
new GTFS line names.  This audit keeps that mapping explicit so missing JR
lines are visible before we collect more data.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHYSICAL_MAP = ROOT / "data" / "v4_japan_physical_map.json.gz"
DEFAULT_TRAINS = ROOT / "data" / "v4_current_weekday_train_instances.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_jr_company_timetable_coverage_audit.json"

JR_COMPANIES = {
    "jr_east": "東日本旅客鉄道",
    "jr_central": "東海旅客鉄道",
    "jr_west": "西日本旅客鉄道",
    "jr_hokkaido": "北海道旅客鉄道",
    "jr_shikoku": "四国旅客鉄道",
    "jr_kyushu": "九州旅客鉄道",
}

# Current v3/v4 service-family ids are not N02 physical line names.  Keep the
# bridge deliberately small and auditable; do not infer nationwide coverage from
# a through-service name unless the collected stops really represent that line.
SERVICE_FAMILY_TO_PHYSICAL_LINES = {
    "JR_CHUO": ["中央線"],
    "JR_EAST_CHUO_RAPID": ["中央線"],
    "JR_EAST_CHUO_SOBU_LOCAL": ["中央線", "総武線"],
    "JR_EAST_JOBAN_RAPID": ["常磐線"],
    "JR_EAST_KEIHIN_TOHOKU_NEGISHI": ["東北線", "東海道線", "根岸線"],
    "JR_EAST_KEIYO_MUSASHINO": ["京葉線", "武蔵野線"],
    "JR_EAST_SAIKYO_KAWAGOE": ["赤羽線", "川越線"],
    "JR_EAST_SHONAN_SHINJUKU": ["東北線", "高崎線", "東海道線", "横須賀線"],
    "JR_EAST_SOBU_RAPID": ["総武線", "横須賀線"],
    "JR_EAST_TOKAIDO": ["東海道線"],
    "JR_EAST_UENO_TOKYO": ["東北線", "東海道線", "常磐線"],
    "JR_EAST_YOKOSUKA": ["横須賀線"],
    "JR_JOBAN": ["常磐線"],
    "JR_JOETSU_LOCAL": ["上越線"],
    "JR_KASHIMA": ["鹿島線"],
    "JR_KAWAGOE": ["川越線"],
    "JR_NARITA": ["成田線"],
    "JR_OME": ["青梅線", "五日市線"],
    "JR_RYOMO": ["両毛線"],
    "JR_SENSEKI": ["仙石線"],
    "JR_SOTOBO": ["外房線"],
    "JR_TOHOKU": ["東北線"],
    "JR_UCHIBO": ["内房線"],
    "JR_YAMANOTE": ["山手線"],
    # Direct physical line names already present in the adapted v3 corpus.
    "東海道線": ["東海道線"],
}

SHINKANSEN_FAMILY_TO_COMPANY_LINES = {
    "SHINKANSEN_AKITA": {
        "jr_east": ["田沢湖線", "奥羽線"],
    },
    "SHINKANSEN_HOKURIKU": {
        "jr_east": ["北陸新幹線"],
        "jr_west": ["北陸新幹線"],
    },
    "SHINKANSEN_JOETSU": {
        "jr_east": ["上越新幹線"],
    },
    "SHINKANSEN_KYUSHU": {
        "jr_kyushu": ["九州新幹線"],
    },
    "SHINKANSEN_NISHI_KYUSHU": {
        "jr_kyushu": ["西九州新幹線"],
    },
    "SHINKANSEN_TOHOKU_HOKKAIDO": {
        "jr_east": ["東北新幹線"],
        "jr_hokkaido": ["北海道新幹線", "海峡線"],
    },
    "SHINKANSEN_TOKAIDO_SANYO": {
        "jr_central": ["東海道新幹線"],
        "jr_west": ["山陽新幹線"],
    },
    "SHINKANSEN_YAMAGATA": {
        "jr_east": ["奥羽線"],
    },
}

INACTIVE_PHYSICAL_LINES = {
    ("jr_hokkaido", "留萌線"): {
        "coverageStatus": "inactive_no_current_regular_passenger_service",
        "reason": "JR Hokkaido ended the remaining Rumoi Line service on 2026-03-31; the service day audited here is 2026-04-27.",
    },
}


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def physical_lines_by_company(physical_map: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    lines: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    stations_by_line: dict[tuple[str, str], set[str]] = defaultdict(set)
    tracks_by_line: Counter[tuple[str, str]] = Counter()
    for station in physical_map["physicalStations"]:
        operator_id = station["operatorId"]
        if operator_id not in JR_COMPANIES:
            continue
        line_name = station["lineName"]
        stations_by_line[(operator_id, line_name)].add(station["nameJa"])
    for track in physical_map["trackCenterlines"]:
        operator_id = track["operatorId"]
        if operator_id not in JR_COMPANIES:
            continue
        tracks_by_line[(operator_id, track["lineName"])] += 1
    for (operator_id, line_name), station_names in stations_by_line.items():
        lines[operator_id][line_name] = {
            "lineName": line_name,
            "physicalStationCount": len(station_names),
            "trackCenterlineCount": tracks_by_line[(operator_id, line_name)],
            "sampleStationNames": sorted(station_names)[:20],
        }
    return lines


def collect_coverage(trains: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    coverage: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(lambda: {
        "trainCount": 0,
        "sourceCollections": Counter(),
        "serviceFamilies": Counter(),
        "sampleTrainNumbers": [],
    }))
    for train in trains:
        operator_name = train.get("operator_name")
        line_key = train.get("line_name") or train.get("line_id") or train.get("service_name")
        source_collection = train.get("source_collection") or "unknown"
        service_family = str(line_key or "")
        train_number = str(train.get("train_number") or train.get("service_instance_id") or "")

        physical_by_company: dict[str, set[str]] = defaultdict(set)
        if operator_name in JR_COMPANIES.values():
            company_ids = [operator_id for operator_id, name in JR_COMPANIES.items() if name == operator_name]
            explicit_physical_lines = [
                str(line_name)
                for line_name in train.get("physical_line_names", [])
                if str(line_name or "").strip()
            ]
            physical_lines = (
                explicit_physical_lines
                or SERVICE_FAMILY_TO_PHYSICAL_LINES.get(service_family)
                or SERVICE_FAMILY_TO_PHYSICAL_LINES.get(str(train.get("line_id") or ""))
            )
            if physical_lines:
                for company_id in company_ids:
                    physical_by_company[company_id].update(physical_lines)
            elif service_family:
                for company_id in company_ids:
                    physical_by_company[company_id].add(service_family)

        if operator_name == "JR Shinkansen":
            shinkansen_map = SHINKANSEN_FAMILY_TO_COMPANY_LINES.get(service_family) or SHINKANSEN_FAMILY_TO_COMPANY_LINES.get(str(train.get("line_id") or ""))
            if shinkansen_map:
                for company_id, physical_lines in shinkansen_map.items():
                    physical_by_company[company_id].update(physical_lines)

        for company_id, physical_lines in physical_by_company.items():
            for physical_line in physical_lines:
                item = coverage[company_id][physical_line]
                item["trainCount"] += 1
                item["sourceCollections"][source_collection] += 1
                item["serviceFamilies"][service_family] += 1
                if len(item["sampleTrainNumbers"]) < 8 and train_number:
                    item["sampleTrainNumbers"].append(train_number)

    output: dict[str, dict[str, dict[str, Any]]] = {}
    for company_id, by_line in coverage.items():
        output[company_id] = {}
        for line_name, item in by_line.items():
            output[company_id][line_name] = {
                "trainCount": item["trainCount"],
                "sourceCollections": dict(sorted(item["sourceCollections"].items())),
                "serviceFamilies": dict(sorted(item["serviceFamilies"].items())),
                "sampleTrainNumbers": item["sampleTrainNumbers"],
            }
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-map", type=Path, default=DEFAULT_PHYSICAL_MAP)
    parser.add_argument("--trains", type=Path, default=DEFAULT_TRAINS)
    parser.add_argument(
        "--extra-trains",
        type=Path,
        action="append",
        default=[],
        help="Additional train-instance dataset to include in coverage, e.g. newly collected JR-company data.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    physical_map = load_json(args.physical_map)
    train_data = load_json(args.trains)
    train_instances = list(train_data["train_instances"])
    extra_sources: list[str] = []
    for extra_path in args.extra_trains:
        extra_data = load_json(extra_path)
        train_instances.extend(extra_data["train_instances"])
        extra_sources.append(str(extra_path.relative_to(ROOT) if extra_path.is_relative_to(ROOT) else extra_path))
    physical = physical_lines_by_company(physical_map)
    coverage = collect_coverage(train_instances)

    companies: list[dict[str, Any]] = []
    for company_id, company_name in JR_COMPANIES.items():
        physical_lines = physical.get(company_id, {})
        covered_lines = coverage.get(company_id, {})
        line_items: list[dict[str, Any]] = []
        for line_name, physical_item in sorted(physical_lines.items()):
            covered = covered_lines.get(line_name)
            inactive = INACTIVE_PHYSICAL_LINES.get((company_id, line_name))
            coverage_status = "covered" if covered else "missing_train_instances"
            if inactive and not covered:
                coverage_status = inactive["coverageStatus"]
            line_items.append(
                {
                    **physical_item,
                    "coverageStatus": coverage_status,
                    "coverage": covered,
                    "inactiveReason": inactive["reason"] if inactive else None,
                }
            )
        companies.append(
            {
                "operatorId": company_id,
                "operatorName": company_name,
                "physicalLineCount": len(physical_lines),
                "coveredLineCount": sum(1 for item in line_items if item["coverageStatus"] == "covered"),
                "inactiveLineCount": sum(1 for item in line_items if item["coverageStatus"].startswith("inactive_")),
                "missingLineCount": sum(1 for item in line_items if item["coverageStatus"] == "missing_train_instances"),
                "lines": line_items,
            }
        )

    output = {
        "schema": "onichase.v4.jr_company_timetable_coverage_audit.v1",
        "physicalMap": str(args.physical_map.relative_to(ROOT) if args.physical_map.is_relative_to(ROOT) else args.physical_map),
        "trainCollection": str(args.trains.relative_to(ROOT) if args.trains.is_relative_to(ROOT) else args.trains),
        "extraTrainCollections": extra_sources,
        "companies": companies,
    }
    write_json(args.output, output)
    for company in companies:
        print(
            f"{company['operatorName']}: "
            f"{company['coveredLineCount']}/{company['physicalLineCount']} covered, "
            f"{company['inactiveLineCount']} inactive, "
            f"{company['missingLineCount']} missing"
        )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
