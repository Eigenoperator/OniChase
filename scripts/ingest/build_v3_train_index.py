#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"

MANIFEST_PATH = DATA_DIR / "v3_train_manifest.json"
UNIFIED_TRAINS_PATH = DATA_DIR / "v3_trains_unified.json.gz"
DEPARTURES_PATH = DATA_DIR / "v3_station_departures.json.gz"


DATASET_SPECS = [
    ("jr_east", "JR East", DATA_DIR / "v3_tokyo_jreast_core_weekday_train_instances.json"),
    ("tokyo_metro", "Tokyo Metro", DATA_DIR / "v3_tokyo_tokyo_metro_weekday_train_instances.json.gz"),
    ("toei", "Toei", DATA_DIR / "v3_tokyo_toei_weekday_train_instances.json"),
    ("keio", "Keio", DATA_DIR / "v3_tokyo_keio_weekday_train_instances.json"),
    ("tokyu", "Tokyu", DATA_DIR / "v3_tokyo_tokyu_weekday_train_instances.json"),
    ("seibu", "Seibu", DATA_DIR / "v3_tokyo_seibu_weekday_train_instances.json"),
    ("keisei", "Keisei", DATA_DIR / "v3_tokyo_keisei_weekday_train_instances.json"),
    ("keikyu", "Keikyu", DATA_DIR / "v3_tokyo_keikyu_weekday_train_instances.json"),
    ("odakyu", "Odakyu", DATA_DIR / "v3_tokyo_odakyu_weekday_train_instances.json"),
    ("tobu", "Tobu", DATA_DIR / "v3_tokyo_tobu_weekday_train_instances.json"),
    ("rinkai", "Rinkai", DATA_DIR / "v3_tokyo_rinkai_weekday_train_instances.json"),
    ("yurikamome", "Yurikamome", DATA_DIR / "v3_tokyo_yurikamome_weekday_train_instances.json"),
    ("tokyo_monorail", "Tokyo Monorail", DATA_DIR / "v3_tokyo_tokyo_monorail_weekday_train_instances.json"),
    ("tama_monorail", "Tama Monorail", DATA_DIR / "v3_tokyo_tama_monorail_weekday_train_instances.json"),
    ("tsukuba_express", "Tsukuba Express", DATA_DIR / "v3_tokyo_tsukuba_express_weekday_train_instances.json"),
    ("shinkansen", "JR Shinkansen", DATA_DIR / "shinkansen_v2_weekday_train_instances_merged.json"),
]


def load_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[\-‐‑‒–—ー・･'’`]", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    return text


def station_key(value: Any) -> str:
    normalized = normalize_text(value)
    return normalized or "unknown_station"


def hhmm_to_minutes(value: Any) -> int | None:
    if not value:
        return None
    match = re.match(r"^(\d{1,2}):(\d{2})$", str(value))
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def titleize_roman_station(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", " ").replace("-", " ").split())


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def load_station_aliases() -> dict[str, set[str]]:
    aliases: dict[str, set[str]] = defaultdict(set)

    seed_path = DATA_DIR / "v3_jreast_station_seed.json"
    if seed_path.exists():
        seed = load_json(seed_path)
        for station in seed.get("stations", []):
            names = station.get("names", {})
            values = [
                station.get("id"),
                station.get("name"),
                names.get("en"),
                names.get("ja"),
                names.get("zh_hans"),
                titleize_roman_station(str(names.get("en") or station.get("id") or "")),
            ]
            keys = {station_key(value) for value in values if value}
            for key in keys:
                aliases[key].update(keys)

    gis_path = DATA_DIR / "v3_gis" / "stations.geojson"
    if gis_path.exists():
        geojson = load_json(gis_path)
        for feature in geojson.get("features", []):
            props = feature.get("properties", {})
            values = [
                props.get("id"),
                props.get("station_group_id"),
                props.get("name_en"),
                props.get("name_ja"),
                titleize_roman_station(str(props.get("name_en") or "")),
            ]
            keys = {station_key(value) for value in values if value}
            for key in keys:
                aliases[key].update(keys)

    for _, _, path in DATASET_SPECS:
        if not path.exists():
            continue
        payload = load_json(path)
        station_seed = payload.get("station_seed")
        if isinstance(station_seed, list):
            for station in station_seed:
                values = [
                    station.get("station_id"),
                    station.get("name_ja"),
                    station.get("name_en"),
                    station.get("name"),
                ]
                keys = {station_key(value) for value in values if value}
                for key in keys:
                    aliases[key].update(keys)

    return aliases


def canonical_key(raw_key: str, aliases: dict[str, set[str]]) -> str:
    group = aliases.get(raw_key)
    if not group:
        return raw_key
    return sorted(group, key=lambda item: (not re.search(r"[\u3040-\u30ff\u3400-\u9fff]", item), len(item), item))[0]


def train_identity(operator_id: str, source_id: str, train: dict[str, Any], index: int) -> str:
    natural = first_present(
        train.get("service_instance_id"),
        train.get("merge_key"),
        train.get("train_number"),
        train.get("display_name"),
        train.get("train_name_raw"),
    )
    if natural:
        digest = hashlib.sha1(f"{operator_id}|{source_id}|{natural}".encode("utf-8")).hexdigest()[:10]
        return f"{operator_id}:{str(natural).replace(' ', '_')}:{digest}"
    digest = hashlib.sha1(json.dumps(train, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:14]
    return f"{operator_id}:anonymous_{index}:{digest}"


def infer_line(train: dict[str, Any], stops: list[dict[str, Any]]) -> str | None:
    if train.get("line"):
        return train["line"]
    counts: dict[str, int] = defaultdict(int)
    for stop in stops:
        line = stop.get("line")
        if line:
            counts[str(line)] += 1
    if counts:
        return max(counts.items(), key=lambda item: item[1])[0]
    return None


def normalize_train(
    operator_id: str,
    operator_name: str,
    source_path: Path,
    source_id: str,
    service_day: str,
    train: dict[str, Any],
    index: int,
    aliases: dict[str, set[str]],
) -> dict[str, Any] | None:
    raw_stops = train.get("stop_times") or train.get("stops") or []
    stops: list[dict[str, Any]] = []
    for fallback_sequence, stop in enumerate(raw_stops, start=1):
        raw_name = first_present(stop.get("station_name_raw"), stop.get("station_name"), stop.get("name"), stop.get("station_id"))
        if not raw_name:
            continue
        raw_key = station_key(raw_name)
        key = canonical_key(raw_key, aliases)
        arrival = first_present(stop.get("arrival_hhmm"), stop.get("arrival"), stop.get("time"))
        departure = first_present(stop.get("departure_hhmm"), stop.get("departure"), arrival)
        line = first_present(stop.get("line_id"), stop.get("line"), train.get("line_id"))
        stops.append({
            "sequence": int(stop.get("sequence") or fallback_sequence),
            "station_id": stop.get("station_id"),
            "station_key": key,
            "station_name": raw_name,
            "line": line,
            "arrival": arrival,
            "departure": departure,
            "arrival_min": hhmm_to_minutes(arrival),
            "departure_min": hhmm_to_minutes(departure),
            "platform": stop.get("platform"),
        })
    if len(stops) < 2:
        return None
    stops.sort(key=lambda item: item["sequence"])
    train_id = train_identity(operator_id, source_id, train, index)
    service_name = first_present(train.get("service_name"), train.get("display_name"), train.get("train_name_raw"), operator_name)
    train_number = first_present(train.get("train_number"), train.get("service_number"), train.get("service_instance_id"), "")
    return {
        "id": train_id,
        "operator": operator_name,
        "operator_id": operator_id,
        "line": infer_line(train, stops),
        "train_number": train_number,
        "service_name": service_name,
        "direction": first_present(train.get("direction"), train.get("headsign"), stops[-1]["station_name"]),
        "stops": stops,
        "source": {
            "dataset_id": source_id,
            "data_file": str(source_path.relative_to(ROOT)),
            "url": train.get("source_url"),
        },
        "service_day": service_day,
    }


def departure_sort_key(entry: dict[str, Any]) -> tuple[int, str, str]:
    minute = entry.get("departure_min")
    return (minute if minute is not None else 10_000, entry.get("operator", ""), entry.get("train_id", ""))


def preferred_station_display_name(station_key_value: str, aliases: dict[str, set[str]], fallback: Any) -> str:
    candidates = set(aliases.get(station_key_value, set()))
    if fallback:
        candidates.add(str(fallback))
    japanese = [
        value
        for value in candidates
        if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", value)
        and not re.match(r"^[a-z_]+_", value, re.I)
    ]
    if japanese:
        return sorted(japanese, key=lambda item: (len(item), item))[0]
    return str(fallback or station_key_value)


def build() -> dict[str, Any]:
    aliases = load_station_aliases()
    manifest_operators: dict[str, dict[str, Any]] = {}
    trains: list[dict[str, Any]] = []
    departures: dict[str, dict[str, Any]] = {}

    for operator_id, operator_name, path in DATASET_SPECS:
        entry = {
            "operator": operator_name,
            "train_count": 0,
            "data_file": str(path.relative_to(ROOT)),
            "service_day": None,
            "status": "missing",
        }
        if not path.exists():
            manifest_operators[operator_id] = entry
            continue
        payload = load_json(path)
        source_trains = payload.get("train_instances") or payload.get("trains") or []
        service_day = payload.get("service_day") or "weekday"
        source_id = payload.get("id") or path.stem
        normalized_batch = []
        for index, train in enumerate(source_trains):
            normalized = normalize_train(operator_id, operator_name, path, source_id, service_day, train, index, aliases)
            if normalized:
                normalized_batch.append(normalized)
        trains.extend(normalized_batch)
        entry.update({
            "train_count": len(normalized_batch),
            "raw_train_count": len(source_trains),
            "service_day": service_day,
            "status": "ready" if normalized_batch else "empty",
        })
        manifest_operators[operator_id] = entry

    trains.sort(key=lambda item: (
        item["operator_id"],
        item["stops"][0].get("departure_min") if item["stops"] else 10_000,
        str(item.get("train_number") or ""),
        item["id"],
    ))

    for train in trains:
        destination = train["stops"][-1]["station_name"]
        for stop_index, stop in enumerate(train["stops"]):
            departure = stop.get("departure")
            if not departure:
                continue
            key = stop["station_key"]
            station = departures.setdefault(key, {
                "station_key": key,
                "display_name": preferred_station_display_name(key, aliases, stop["station_name"]),
                "aliases": sorted(aliases.get(key, {key})),
                "departures": [],
            })
            station["departures"].append({
                "time": departure,
                "departure_min": stop.get("departure_min"),
                "train_id": train["id"],
                "operator": train["operator"],
                "operator_id": train["operator_id"],
                "line": stop.get("line") or train.get("line"),
                "train_number": train.get("train_number"),
                "service_name": train.get("service_name"),
                "direction": train.get("direction"),
                "destination": destination,
                "stop_index": stop_index,
                "platform": stop.get("platform"),
            })

    for station in departures.values():
        station["departures"].sort(key=departure_sort_key)

    manifest = {
        "id": "v3_train_manifest_v0_1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "schema": {
            "manifest": "operator -> train_count -> data_file -> service_day -> status",
            "train": "operator / line / train_number / service_name / direction / stops / source / service_day",
        },
        "outputs": {
            "unified_trains": str(UNIFIED_TRAINS_PATH.relative_to(ROOT)),
            "station_departures": str(DEPARTURES_PATH.relative_to(ROOT)),
        },
        "operators": manifest_operators,
        "total_train_count": len(trains),
        "station_departure_count": len(departures),
    }

    unified = {
        "id": "v3_trains_unified_v0_1",
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "generated_at": manifest["generated_at"],
        "train_count": len(trains),
        "trains": trains,
    }

    departure_payload = {
        "id": "v3_station_departures_v0_1",
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "generated_at": manifest["generated_at"],
        "station_count": len(departures),
        "stations": dict(sorted(departures.items())),
    }

    write_json(MANIFEST_PATH, manifest)
    write_json(UNIFIED_TRAINS_PATH, unified)
    write_json(DEPARTURES_PATH, departure_payload)

    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_json(DOCS_DATA_DIR / MANIFEST_PATH.name, manifest)
    write_json(DOCS_DATA_DIR / UNIFIED_TRAINS_PATH.name, unified)
    write_json(DOCS_DATA_DIR / DEPARTURES_PATH.name, departure_payload)
    return manifest


def main() -> int:
    manifest = build()
    print(json.dumps({
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "total_train_count": manifest["total_train_count"],
        "station_departure_count": manifest["station_departure_count"],
        "operators": {
            key: {
                "train_count": value["train_count"],
                "service_day": value["service_day"],
                "status": value["status"],
            }
            for key, value in manifest["operators"].items()
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
