#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "data" / "v3_tokyo_bundle.json.gz"
DEFAULT_MAP_OUTPUT = ROOT / "data" / "v3_tokyo_map_bundle.json.gz"
DEFAULT_TIMETABLE_OUTPUT = ROOT / "data" / "v3_tokyo_timetable_bundle.json.gz"


def load_json(path: Path) -> dict[str, Any]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_gz(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with path.open("wb") as raw_handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as handle:
            handle.write(raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--map-output", type=Path, default=DEFAULT_MAP_OUTPUT)
    parser.add_argument("--timetable-output", type=Path, default=DEFAULT_TIMETABLE_OUTPUT)
    args = parser.parse_args()

    bundle = load_json(args.source)
    trips = bundle.get("tripInstances", [])
    map_bundle = dict(bundle)
    map_bundle["tripInstances"] = []
    map_bundle["metadata"] = {
        **(bundle.get("metadata") or {}),
        "deferredTimetable": True,
        "deferredTripCount": len(trips),
    }
    timetable_bundle = {
        "version": bundle.get("version"),
        "generatedAt": bundle.get("generatedAt"),
        "sourceBundle": args.source.name,
        "tripInstances": trips,
    }

    write_json_gz(args.map_output, map_bundle)
    write_json_gz(args.timetable_output, timetable_bundle)
    print(json.dumps({
        "source": str(args.source.relative_to(ROOT)) if args.source.is_relative_to(ROOT) else str(args.source),
        "map_output": str(args.map_output.relative_to(ROOT)) if args.map_output.is_relative_to(ROOT) else str(args.map_output),
        "timetable_output": str(args.timetable_output.relative_to(ROOT)) if args.timetable_output.is_relative_to(ROOT) else str(args.timetable_output),
        "map_bytes": args.map_output.stat().st_size,
        "timetable_bytes": args.timetable_output.stat().st_size,
        "trip_instances": len(trips),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
