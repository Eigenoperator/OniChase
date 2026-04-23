#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "v3.replay.collection.1"
REPLAY_SCHEMA_VERSION = "v3.replay.1"
DATASET_NAME = "v3-tokyo"
GAME_RULES_VERSION = "v3.rules.2026-04-22"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def player_plan(game: dict[str, Any], seat: str) -> dict[str, Any]:
    plan = game.get(f"{seat}_plan") or {}
    resolved = ((game.get("result") or {}).get("players") or {}).get(seat) or {}
    return {
        "seat": seat,
        "start_station_id": plan.get("start_station_id") or resolved.get("start_station_id"),
        "start_label": plan.get("startStation") or plan.get("start"),
        "final_station_id": plan.get("finalStationId") or resolved.get("final_station_id"),
        "final_label": plan.get("finalStation"),
        "final_hhmm": plan.get("finalHhmm"),
        "steps": plan.get("steps") or [],
        "legs": plan.get("legs") or [],
        "resolved_actions": resolved.get("resolved_actions") or [],
    }


def initial_state(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {}
    start = next((event for event in events if event.get("type") == "SCENARIO_START"), events[0])
    return {
        "time_hhmm": start.get("time_hhmm"),
        "time_minute": start.get("time_minute"),
        "carriers": start.get("state_after") or start.get("state_snapshot") or {},
    }


def phase_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event for event in events
        if event.get("event_family") == "LIFECYCLE" or event.get("type") in {"SCENARIO_START", "SCENARIO_END"}
    ]


def capture_checks(events: list[dict[str, Any]], result: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "CAPTURE":
            continue
        checks.append({
            "time_hhmm": event.get("time_hhmm"),
            "time_minute": event.get("time_minute"),
            "capture_type": event.get("capture_type"),
            "trigger_event_type": event.get("trigger_event_type"),
            "trigger_player_id": event.get("trigger_player_id"),
            "station_group_id": event.get("station_group_id"),
            "station_label": event.get("station_label"),
            "trip_id": event.get("trip_id"),
            "trip_label": event.get("trip_label"),
            "state_snapshot": event.get("state_snapshot") or event.get("state_after") or {},
        })
    capture = result.get("capture")
    if capture and not checks:
        checks.append({
            "time_hhmm": capture.get("time_hhmm"),
            "capture_type": capture.get("type"),
            "station_group_id": capture.get("station_group_id"),
            "station_label": capture.get("station_label"),
            "trip_id": capture.get("trip_id"),
            "trip_label": capture.get("trip_label"),
            "state_snapshot": {},
        })
    return checks


def normalize_game(game: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    result = game.get("result") or {}
    events = result.get("match_event_log") or game.get("event_log") or []
    scenario_id = result.get("scenario_id") or f"game-{game.get('index')}"
    capture = result.get("capture")
    return {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "record_id": scenario_id,
        "dataset_name": DATASET_NAME,
        "dataset_id": result.get("dataset_id") or source.get("dataset_id") or "",
        "dataset_version": result.get("dataset_version") or source.get("dataset_version") or "",
        "game_rules_version": GAME_RULES_VERSION,
        "source": {
            "kind": "v3_public_battle_record",
            "mode": source.get("mode"),
            "page_url": source.get("page_url"),
            "room_server_url": source.get("room_server_url"),
            "run_started_at": source.get("run_started_at"),
        },
        "room_id": game.get("room_id"),
        "scenario": {
            "id": scenario_id,
            "index": game.get("index"),
            "name": game.get("scenario_name"),
            "kind": game.get("scenario_kind"),
            "expected_capture": game.get("expected_capture"),
        },
        "players": {
            "runner": player_plan(game, "runner"),
            "hunter": player_plan(game, "hunter"),
        },
        "initial_state": initial_state(events),
        "plans": {
            "runner": {
                "start_station_id": player_plan(game, "runner")["start_station_id"],
                "steps": player_plan(game, "runner")["steps"],
                "legs": player_plan(game, "runner")["legs"],
            },
            "hunter": {
                "start_station_id": player_plan(game, "hunter")["start_station_id"],
                "steps": player_plan(game, "hunter")["steps"],
                "legs": player_plan(game, "hunter")["legs"],
            },
        },
        "phase_events": phase_events(events),
        "events": events,
        "capture_checks": capture_checks(events, result),
        "result": {
            "capture": capture,
            "capture_summary": game.get("capture_summary"),
            "online_phase": game.get("online_phase"),
            "online_time": game.get("online_time"),
            "issues": game.get("issues") or [],
        },
    }


def normalize_records(payload: dict[str, Any], source_path: Path | None = None) -> dict[str, Any]:
    source = {
        "mode": payload.get("mode"),
        "page_url": payload.get("page_url"),
        "room_server_url": payload.get("room_server_url"),
        "run_started_at": payload.get("run_started_at"),
        "source_path": str(source_path) if source_path else None,
    }
    replays = [normalize_game(game, source) for game in payload.get("games", [])]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generated_by": "scripts/dev/normalize_v3_replay_record.py",
        "source": source,
        "requested_count": payload.get("requested_count"),
        "completed_count": payload.get("completed_count"),
        "replays": replays,
    }


def validate_replay(replay: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    record_id = replay.get("record_id") or "<missing-record-id>"
    if replay.get("schema_version") != REPLAY_SCHEMA_VERSION:
        errors.append(f"{record_id}: schema_version is {replay.get('schema_version')}")
    if replay.get("dataset_name") != DATASET_NAME:
        errors.append(f"{record_id}: dataset_name is {replay.get('dataset_name')}")
    if not replay.get("dataset_id"):
        errors.append(f"{record_id}: missing dataset_id")
    for seat in ("runner", "hunter"):
        player = (replay.get("players") or {}).get(seat) or {}
        plan = (replay.get("plans") or {}).get(seat) or {}
        if not player.get("start_station_id"):
            errors.append(f"{record_id}: {seat} missing start_station_id")
        if not isinstance(plan.get("steps"), list):
            errors.append(f"{record_id}: {seat} plan steps are not a list")
    events = replay.get("events") or []
    if not events:
        errors.append(f"{record_id}: missing events")
    previous_minute = -1
    for index, event in enumerate(events):
        minute = event.get("time_minute")
        if not isinstance(minute, int):
            errors.append(f"{record_id}: event {index} missing integer time_minute")
            continue
        if minute < previous_minute:
            errors.append(f"{record_id}: event {index} is out of order")
        previous_minute = minute
        if "state_snapshot" not in event:
            errors.append(f"{record_id}: event {index} missing state_snapshot")
    capture = (replay.get("result") or {}).get("capture")
    checks = replay.get("capture_checks") or []
    expected_capture = (replay.get("scenario") or {}).get("expected_capture")
    actual_capture = (capture or {}).get("type") or "none"
    if expected_capture and expected_capture != actual_capture:
        errors.append(f"{record_id}: expected capture {expected_capture}, got {actual_capture}")
    if capture and not checks:
        errors.append(f"{record_id}: capture result exists but capture_checks is empty")
    if checks and capture and checks[-1].get("capture_type") != capture.get("type"):
        errors.append(f"{record_id}: capture_checks do not match capture result")
    if (replay.get("result") or {}).get("issues"):
        errors.append(f"{record_id}: replay has issues {(replay.get('result') or {}).get('issues')}")
    return errors


def validate_collection(collection: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if collection.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"collection schema_version is {collection.get('schema_version')}")
    replays = collection.get("replays") or []
    if not replays:
        errors.append("collection has no replays")
    completed = collection.get("completed_count")
    if completed is not None and completed != len(replays):
        errors.append(f"completed_count {completed} != replay count {len(replays)}")
    for replay in replays:
        errors.extend(validate_replay(replay))
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize v3 public battle records into canonical replay records.")
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = load_json(args.records)
    collection = normalize_records(payload, args.records)
    errors = validate_collection(collection)
    if errors:
        print("v3 replay record validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    if args.output and not args.validate_only:
        write_json(args.output, collection)
        print(f"Wrote {args.output}")
    print(f"v3 replay record validation passed: {len(collection['replays'])} replay(s)")


if __name__ == "__main__":
    main()
