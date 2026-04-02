#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def hhmm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def minutes_to_hhmm(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def build_train_lookup(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {train["train_number"]: train for train in dataset["train_instances"]}


def stop_time_value(stop_time: dict[str, Any], key: str) -> int | None:
    raw_value = stop_time.get(key)
    if raw_value is None:
        return None
    return hhmm_to_minutes(raw_value)


def stop_departure_minutes(stop_time: dict[str, Any]) -> int | None:
    return stop_time_value(stop_time, "departure_hhmm") or stop_time_value(stop_time, "arrival_hhmm")


def stop_arrival_minutes(stop_time: dict[str, Any]) -> int | None:
    return stop_time_value(stop_time, "arrival_hhmm") or stop_time_value(stop_time, "departure_hhmm")


def make_interval(
    kind: str,
    start_minute: int,
    end_minute: int,
    station_id: str | None = None,
    train_number: str | None = None,
) -> dict[str, Any]:
    interval = {
        "kind": kind,
        "start_hhmm": minutes_to_hhmm(start_minute),
        "end_hhmm": minutes_to_hhmm(end_minute),
        "start_minute": start_minute,
        "end_minute": end_minute,
    }
    if station_id is not None:
        interval["station_id"] = station_id
    if train_number is not None:
        interval["train_number"] = train_number
    return interval


def event_sort_key(event: dict[str, Any]) -> tuple[int, int, str]:
    priority_order = {
        "SCENARIO_START": 0,
        "START_AT_STATION": 1,
        "WAIT_UNTIL": 2,
        "PLAN_RESOLUTION": 3,
        "BOARD_TRAIN": 4,
        "ALIGHT_TRAIN": 5,
        "CAPTURE": 6,
        "SCENARIO_END": 7,
    }
    return (
        event["time_minute"],
        priority_order.get(event["type"], 99),
        event.get("player_id", ""),
    )


def format_event(
    time_minute: int,
    event_type: str,
    player_id: str | None = None,
    **payload: Any,
) -> dict[str, Any]:
    event = {
        "time_hhmm": minutes_to_hhmm(time_minute),
        "time_minute": time_minute,
        "type": event_type,
        "event_scope": "MATCH_GLOBAL" if event_type in {"SCENARIO_START", "CAPTURE", "SCENARIO_END"} else "PLAYER_LOCAL",
        "timeline_lane": player_id or "match",
        "event_family": classify_event_family(event_type),
    }
    if player_id is not None:
        event["player_id"] = player_id
    event.update(payload)
    return event


def classify_event_family(event_type: str) -> str:
    if event_type in {"SCENARIO_START", "SCENARIO_END"}:
        return "LIFECYCLE"
    if event_type == "CAPTURE":
        return "RESOLUTION"
    if event_type in {"START_AT_STATION", "WAIT_UNTIL"}:
        return "POSITION"
    if event_type in {"BOARD_TRAIN", "ALIGHT_TRAIN"}:
        return "MOVEMENT"
    if event_type == "PLAN_RESOLUTION":
        return "PLANNING"
    return "GENERIC"


def find_boarding_stop(train: dict[str, Any], station_id: str, earliest_minute: int) -> dict[str, Any]:
    candidates = []
    for stop_time in train["stop_times"]:
        if stop_time.get("station_id") != station_id:
            continue
        departure_minute = stop_departure_minutes(stop_time)
        if departure_minute is None or departure_minute < earliest_minute:
            continue
        candidates.append((departure_minute, stop_time))

    if not candidates:
        raise ValueError(
            f"Train {train['train_number']} has no valid boarding stop at {station_id} after {minutes_to_hhmm(earliest_minute)}."
        )

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def select_board_candidate(
    dataset: dict[str, Any],
    station_id: str,
    earliest_minute: int,
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    train_lookup = build_train_lookup(dataset)
    rejected: list[dict[str, Any]] = []

    for candidate in candidates:
        train_number = candidate["train_number"]
        train = train_lookup.get(train_number)
        if train is None:
            rejected.append({"train_number": train_number, "reason": "unknown_train"})
            continue
        try:
            board_stop = find_boarding_stop(train, station_id, earliest_minute)
        except ValueError:
            rejected.append({"train_number": train_number, "reason": "not_catchable_from_current_state"})
            continue
        return train, board_stop, rejected

    raise ValueError(
        f"No candidate train is catchable from {station_id} after {minutes_to_hhmm(earliest_minute)}."
    )


def extract_player_steps(player_data: dict[str, Any]) -> list[dict[str, Any]]:
    if "plan" in player_data:
        return player_data["plan"]["steps"]
    return player_data.get("actions", [])


def find_alighting_stop(
    train: dict[str, Any],
    boarded_sequence: int,
    station_id: str,
    loop_pass_index: int | None,
) -> dict[str, Any]:
    for stop_time in train["stop_times"]:
        if stop_time["sequence"] <= boarded_sequence:
            continue
        if stop_time.get("station_id") != station_id:
            continue
        if loop_pass_index is not None and stop_time.get("loop_pass_index") != loop_pass_index:
            continue
        return stop_time

    suffix = f" with loop_pass_index={loop_pass_index}" if loop_pass_index is not None else ""
    raise ValueError(
        f"Train {train['train_number']} does not reach {station_id}{suffix} after sequence {boarded_sequence}."
    )


def expand_player_plan(player_id: str, player_data: dict[str, Any], scenario: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any]:
    train_lookup = build_train_lookup(dataset)
    current_minute = hhmm_to_minutes(scenario["start_time_hhmm"])
    end_minute = hhmm_to_minutes(scenario["end_time_hhmm"])
    current_station_id = player_data["start_station_id"]
    current_train: dict[str, Any] | None = None
    current_board_stop: dict[str, Any] | None = None

    intervals: list[dict[str, Any]] = []
    resolved_actions: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = [
        format_event(
            current_minute,
            "START_AT_STATION",
            player_id=player_id,
            station_id=current_station_id,
            carrier_after={"kind": "NODE", "station_id": current_station_id},
        )
    ]

    for step_index, action in enumerate(extract_player_steps(player_data), start=1):
        action_type = action["type"]

        if action_type == "WAIT_UNTIL":
            resolved_actions.append({"step_index": step_index, **action})
            if current_station_id is None:
                raise ValueError(f"{player_id} cannot WAIT_UNTIL while not at a station.")
            target_minute = hhmm_to_minutes(action["until_hhmm"])
            if target_minute < current_minute:
                raise ValueError(f"{player_id} cannot wait backwards in time.")
            intervals.append(make_interval("NODE", current_minute, target_minute, station_id=current_station_id))
            events.append(format_event(target_minute, "WAIT_UNTIL", player_id=player_id, station_id=current_station_id))
            current_minute = target_minute
            continue

        if action_type in {"BOARD_TRAIN", "BOARD_ANY_OF"}:
            if current_station_id is None:
                raise ValueError(f"{player_id} cannot {action_type} while already on a train.")

            if action_type == "BOARD_TRAIN":
                train_number = action["train_number"]
                train = train_lookup.get(train_number)
                if train is None:
                    raise ValueError(f"{player_id} references unknown train {train_number}.")
                board_stop = find_boarding_stop(train, current_station_id, current_minute)
                resolved_actions.append({"step_index": step_index, **action})
            else:
                train, board_stop, rejected = select_board_candidate(
                    dataset,
                    current_station_id,
                    current_minute,
                    action["candidates"],
                )
                train_number = train["train_number"]
                events.append(
                    format_event(
                        current_minute,
                        "PLAN_RESOLUTION",
                        player_id=player_id,
                        step_index=step_index,
                        plan_step_type="BOARD_ANY_OF",
                        chosen_train_number=train_number,
                        rejected_candidates=rejected,
                    )
                )
                resolved_actions.append(
                    {
                        "step_index": step_index,
                        "type": "BOARD_TRAIN",
                        "source_plan_type": "BOARD_ANY_OF",
                        "train_number": train_number,
                        "rejected_candidates": rejected,
                    }
                )

            board_minute = stop_departure_minutes(board_stop)
            if board_minute is None:
                raise ValueError(f"{player_id} found no departure time for train {train_number} at {current_station_id}.")
            if board_minute > current_minute:
                intervals.append(make_interval("NODE", current_minute, board_minute, station_id=current_station_id))
            events.append(
                format_event(
                    board_minute,
                    "BOARD_TRAIN",
                    player_id=player_id,
                    station_id=current_station_id,
                    train_number=train_number,
                    sequence=board_stop["sequence"],
                    loop_pass_index=board_stop.get("loop_pass_index"),
                    carrier_after={"kind": "TRAIN", "train_number": train_number},
                )
            )
            current_minute = board_minute
            current_train = train
            current_board_stop = board_stop
            current_station_id = None
            continue

        if action_type == "RIDE_TO_STATION":
            resolved_actions.append({"step_index": step_index, **action})
            if current_train is None or current_board_stop is None:
                raise ValueError(f"{player_id} cannot RIDE_TO_STATION while not on a train.")
            alight_stop = find_alighting_stop(
                current_train,
                current_board_stop["sequence"],
                action["station_id"],
                action.get("loop_pass_index"),
            )
            arrival_minute = stop_arrival_minutes(alight_stop)
            if arrival_minute is None:
                raise ValueError(f"{player_id} found no arrival time when riding train {current_train['train_number']}.")
            intervals.append(
                make_interval(
                    "TRAIN",
                    current_minute,
                    arrival_minute,
                    train_number=current_train["train_number"],
                )
            )
            events.append(
                format_event(
                    arrival_minute,
                    "ALIGHT_TRAIN",
                    player_id=player_id,
                    station_id=alight_stop["station_id"],
                    train_number=current_train["train_number"],
                    sequence=alight_stop["sequence"],
                    loop_pass_index=alight_stop.get("loop_pass_index"),
                    carrier_after={"kind": "NODE", "station_id": alight_stop["station_id"]},
                )
            )
            current_minute = arrival_minute
            current_station_id = alight_stop["station_id"]
            current_train = None
            current_board_stop = None
            continue

        raise ValueError(f"Unsupported action type: {action_type}")

    if current_train is not None:
        raise ValueError(f"{player_id} ends the scenario while still on train {current_train['train_number']}.")

    if current_station_id is not None and current_minute < end_minute:
        intervals.append(make_interval("NODE", current_minute, end_minute, station_id=current_station_id))

    return {
        "player_id": player_id,
        "start_station_id": player_data["start_station_id"],
        "input_mode": "plan" if "plan" in player_data else "actions",
        "resolved_actions": resolved_actions,
        "intervals": intervals,
        "events": events,
        "final_time_hhmm": minutes_to_hhmm(max(current_minute, end_minute if current_station_id is not None else current_minute)),
        "final_station_id": current_station_id,
    }


def find_first_capture(runner: dict[str, Any], hunter: dict[str, Any]) -> dict[str, Any] | None:
    captures: list[dict[str, Any]] = []

    for runner_interval in runner["intervals"]:
        for hunter_interval in hunter["intervals"]:
            overlap_start = max(runner_interval["start_minute"], hunter_interval["start_minute"])
            overlap_end = min(runner_interval["end_minute"], hunter_interval["end_minute"])
            if overlap_start > overlap_end:
                continue

            if (
                runner_interval["kind"] == "NODE"
                and hunter_interval["kind"] == "NODE"
                and runner_interval.get("station_id") == hunter_interval.get("station_id")
            ):
                captures.append(
                    {
                        "type": "same_node",
                        "time_hhmm": minutes_to_hhmm(overlap_start),
                        "station_id": runner_interval["station_id"],
                    }
                )

            if (
                runner_interval["kind"] == "TRAIN"
                and hunter_interval["kind"] == "TRAIN"
                and runner_interval.get("train_number") == hunter_interval.get("train_number")
            ):
                captures.append(
                    {
                        "type": "same_train",
                        "time_hhmm": minutes_to_hhmm(overlap_start),
                        "train_number": runner_interval["train_number"],
                    }
                )

    if not captures:
        return None

    captures.sort(key=lambda capture: (hhmm_to_minutes(capture["time_hhmm"]), capture["type"]))
    return captures[0]


def state_at_time(player: dict[str, Any], time_minute: int) -> dict[str, Any]:
    for interval in player["intervals"]:
        start_minute = interval["start_minute"]
        end_minute = interval["end_minute"]
        if start_minute <= time_minute < end_minute:
            if interval["kind"] == "NODE":
                return {"kind": "NODE", "station_id": interval["station_id"]}
            return {"kind": "TRAIN", "train_number": interval["train_number"]}

    start_minute = hhmm_to_minutes(player["events"][0]["time_hhmm"])
    if time_minute <= start_minute:
        return {"kind": "NODE", "station_id": player["start_station_id"]}
    if player["final_station_id"] is not None:
        return {"kind": "NODE", "station_id": player["final_station_id"]}
    return {"kind": "UNKNOWN"}


def clone_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "runner": dict(state["runner"]),
        "hunter": dict(state["hunter"]),
    }


def apply_event_to_state(state: dict[str, Any], event: dict[str, Any]) -> None:
    player_id = event.get("player_id")
    if event["type"] == "START_AT_STATION" and player_id:
        state[player_id] = {"kind": "NODE", "station_id": event["station_id"]}
        return
    if event["type"] == "BOARD_TRAIN" and player_id:
        state[player_id] = {"kind": "TRAIN", "train_number": event["train_number"]}
        return
    if event["type"] == "ALIGHT_TRAIN" and player_id:
        state[player_id] = {"kind": "NODE", "station_id": event["station_id"]}
        return


def build_match_event_log(
    scenario: dict[str, Any],
    runner: dict[str, Any],
    hunter: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    start_minute = hhmm_to_minutes(scenario["start_time_hhmm"])
    end_minute = hhmm_to_minutes(scenario["end_time_hhmm"])
    events: list[dict[str, Any]] = [
        format_event(start_minute, "SCENARIO_START", scenario_id=scenario["id"]),
        *runner["events"],
        *hunter["events"],
    ]
    events.sort(key=event_sort_key)

    running_state = {
        "runner": {"kind": "NODE", "station_id": runner["start_station_id"]},
        "hunter": {"kind": "NODE", "station_id": hunter["start_station_id"]},
    }
    resolved_capture: dict[str, Any] | None = None
    resolved_events: list[dict[str, Any]] = []

    for event in events:
        event["state_before"] = clone_state(running_state)
        apply_event_to_state(running_state, event)
        event["state_after"] = clone_state(running_state)
        event["state_snapshot"] = clone_state(running_state)
        resolved_events.append(event)

        capture = detect_capture_after_event(event, running_state)
        if capture is not None:
            capture_event = format_event(
                event["time_minute"],
                "CAPTURE",
                capture_type=capture["type"],
                trigger_event_type=event["type"],
                trigger_player_id=event.get("player_id"),
                **{k: v for k, v in capture.items() if k != "type"},
            )
            capture_event["state_before"] = clone_state(running_state)
            capture_event["state_after"] = clone_state(running_state)
            capture_event["state_snapshot"] = clone_state(running_state)
            resolved_events.append(capture_event)
            resolved_capture = {
                "type": capture["type"],
                "time_hhmm": capture_event["time_hhmm"],
                **{k: v for k, v in capture.items() if k != "type"},
            }
            break

    if resolved_capture is None:
        end_event = format_event(end_minute, "SCENARIO_END", scenario_id=scenario["id"])
        end_event["state_before"] = clone_state(running_state)
        end_event["state_after"] = clone_state(running_state)
        end_event["state_snapshot"] = clone_state(running_state)
        resolved_events.append(end_event)

    return resolved_events, resolved_capture


def detect_capture_after_event(event: dict[str, Any], running_state: dict[str, Any]) -> dict[str, Any] | None:
    if event["type"] not in {"SCENARIO_START", "START_AT_STATION", "BOARD_TRAIN", "ALIGHT_TRAIN"}:
        return None

    runner_state = running_state["runner"]
    hunter_state = running_state["hunter"]

    if (
        runner_state["kind"] == "TRAIN"
        and hunter_state["kind"] == "TRAIN"
        and runner_state.get("train_number") == hunter_state.get("train_number")
    ):
        return {"type": "same_train", "train_number": runner_state["train_number"]}

    if (
        runner_state["kind"] == "NODE"
        and hunter_state["kind"] == "NODE"
        and runner_state.get("station_id") == hunter_state.get("station_id")
    ):
        return {"type": "same_node", "station_id": runner_state["station_id"]}

    return None


def build_result(scenario: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any]:
    runner = expand_player_plan("runner", scenario["players"]["runner"], scenario, dataset)
    hunter = expand_player_plan("hunter", scenario["players"]["hunter"], scenario, dataset)
    match_event_log, capture = build_match_event_log(scenario, runner, hunter)

    return {
        "scenario_id": scenario["id"],
        "dataset_id": dataset["id"],
        "capture": capture,
        "match_event_log": match_event_log,
        "players": {
            "runner": runner,
            "hunter": hunter,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate a minimal two-player match from real train-instance data.")
    parser.add_argument("--dataset", required=True, help="Path to the merged train-instance dataset JSON file.")
    parser.add_argument("--scenario", required=True, help="Path to the scenario JSON file.")
    parser.add_argument("--output", help="Optional path to write the result JSON.")
    args = parser.parse_args()

    dataset = load_json(Path(args.dataset))
    scenario = load_json(Path(args.scenario))
    result = build_result(scenario, dataset)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote: {output_path}")

    print(f"Scenario: {result['scenario_id']}")
    if result["capture"] is None:
        print("Capture: none")
    else:
        capture = result["capture"]
        if capture["type"] == "same_node":
            print(f"Capture: same_node at {capture['station_id']} {capture['time_hhmm']}")
        else:
            print(f"Capture: same_train on {capture['train_number']} {capture['time_hhmm']}")
    print("Event log:")
    for event in result["match_event_log"]:
        summary = event["type"]
        if event.get("capture_type"):
            summary += f" {event['capture_type']}"
        if event.get("player_id"):
            summary += f" {event['player_id']}"
        if event.get("trigger_event_type"):
            summary += f" trigger={event['trigger_event_type']}"
        if event.get("station_id"):
            summary += f" station={event['station_id']}"
        if event.get("train_number"):
            summary += f" train={event['train_number']}"
        print(f"- {event['time_hhmm']} {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
