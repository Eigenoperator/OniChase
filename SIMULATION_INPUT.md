# SIMULATION INPUT

## Purpose

This document defines the first minimal action schema for the real timetable simulator.

The goal is not to model the full hidden-planning game yet.

The goal is to support:

- waiting at a station
- boarding one concrete train instance
- riding that train to a concrete station
- checking same-node and same-train capture from real timetable data

## Scenario Shape

```json
{
  "id": "sample_match_v0_1",
  "label": "Sample real-timetable chase scenario",
  "dataset_id": "yamanote_weekday_train_instances_merged_v0_1",
  "start_time_hhmm": "08:00",
  "end_time_hhmm": "08:20",
  "players": {
    "runner": {
      "start_station_id": "TOKYO",
      "actions": []
    },
    "hunter": {
      "start_station_id": "UENO",
      "actions": []
    }
  }
}
```

## Action Types

### `WAIT_UNTIL`

The player stays at the current station until the specified time.

```json
{
  "type": "WAIT_UNTIL",
  "until_hhmm": "08:04"
}
```

Constraints:

- the player must currently be at a station
- `until_hhmm` must be greater than or equal to the current player time

### `BOARD_TRAIN`

The player boards one concrete train instance by train number.

```json
{
  "type": "BOARD_TRAIN",
  "train_number": "720G"
}
```

Resolution rules:

- the player must currently be at a station
- the train must stop at that station
- the selected departure must be at or after the player's current time
- if the same train visits the station multiple times, the simulator chooses the earliest valid departure after the current time

### `RIDE_TO_STATION`

The player remains on the currently boarded train until the target station.

```json
{
  "type": "RIDE_TO_STATION",
  "station_id": "NISHI_NIPPORI"
}
```

Optional loop disambiguation:

```json
{
  "type": "RIDE_TO_STATION",
  "station_id": "OSAKI",
  "loop_pass_index": 2
}
```

Resolution rules:

- the player must currently be on a train
- the target station must appear later in the same train instance
- if `loop_pass_index` is omitted, the simulator chooses the first later occurrence of the station

## Runtime Result Shape

The simulator outputs:

- normalized action log
- per-player occupancy intervals
- match-level event log
- state snapshot for both players at each event time
- first capture event if one occurs
- final player states

Two capture types are supported in this first simulator:

- `same_node`
- `same_train`

## Boundary Resolution Policy

The current simulator resolves capture in an event-driven way instead of by scanning full interval overlap first.

Capture checks run immediately after these event types:

- `SCENARIO_START`
- `START_AT_STATION`
- `BOARD_TRAIN`
- `ALIGHT_TRAIN`

Current capture priority:

1. `same_train`
2. `same_node`

This means:

- boarding into a train already occupied by the other player triggers `same_train`
- alighting into a station where the other player is already waiting triggers `same_node`
- the simulator currently stops the match event log at the first capture event

Confirmed boundary ruling from `RULES_v0.6`:

- if one player alights into a node and the other boards away from that same node in the same minute:
  - capture succeeds if they are tied to the same train instance
  - capture fails if they are tied to different train instances

## Match Event Log

The simulator produces a single `match_event_log` sorted by in-game time.

Each event includes:

- `time_hhmm`
- `type`
- optional `player_id`
- event-specific payload such as `station_id` or `train_number`
- `state_before` for both players immediately before the event
- `state_after` for both players immediately after the event
- `state_snapshot` as a convenience alias for `state_after`

This is meant to support:

- debugging
- replay inspection
- future UI timeline rendering
- later capture-priority validation

This `before/after` split is important when multiple events happen at the same minute, such as:

- one player finishing a wait
- then boarding a train
- then immediately triggering capture

## Notes

- This is intentionally smaller than the final match engine.
- Walking, planning pause, reveal logic, and hidden information are not included yet.
- The schema is reusable for any rail dataset built as train instances plus canonical stations.
- The next planning-friendly layer is defined in [PLANNING_FORMAT.md](/home/xincheng/toy/Chase/PLANNING_FORMAT.md).
