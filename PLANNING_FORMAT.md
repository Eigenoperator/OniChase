# PLANNING FORMAT

## Purpose

This document defines the next-layer planning-friendly input format on top of the primitive simulator actions.

The goal is to let the simulator accept a short candidate plan instead of only fully resolved actions.

## Relationship To `SIMULATION_INPUT.md`

- `SIMULATION_INPUT.md` defines the primitive execution actions
- this document defines a higher-level planning wrapper that the simulator can resolve into primitive actions

## Player Input Modes

A player can now use either:

- `actions`
- `plan`

### Direct Action Mode

```json
{
  "start_station_id": "TOKYO",
  "actions": [
    { "type": "WAIT_UNTIL", "until_hhmm": "08:04" },
    { "type": "BOARD_TRAIN", "train_number": "720G" },
    { "type": "RIDE_TO_STATION", "station_id": "UENO" }
  ]
}
```

### Planning Mode

```json
{
  "start_station_id": "TOKYO",
  "plan": {
    "id": "runner_plan_v0_1",
    "steps": [
      { "type": "WAIT_UNTIL", "until_hhmm": "08:04" },
      {
        "type": "BOARD_ANY_OF",
        "candidates": [
          { "train_number": "774G" },
          { "train_number": "720G" }
        ]
      },
      { "type": "RIDE_TO_STATION", "station_id": "UENO" }
    ]
  }
}
```

## Supported Planning Step Types

### `WAIT_UNTIL`

Unchanged from primitive action mode.

### `BOARD_ANY_OF`

This is the first planning-friendly candidate step.

```json
{
  "type": "BOARD_ANY_OF",
  "candidates": [
    { "train_number": "774G" },
    { "train_number": "720G" }
  ]
}
```

Resolution rule:

- evaluate candidates in the listed order
- pick the first train that is catchable from the player's current station and current time
- if none are catchable, the scenario is invalid

The resolved result is recorded into:

- `players.<id>.resolved_actions`
- `match_event_log` as a `PLAN_RESOLUTION` event

### `RIDE_TO_STATION`

Unchanged from primitive action mode.

## Event Log Impact

Planning mode adds one new player-local event type:

- `PLAN_RESOLUTION`

This event records:

- which planning step was resolved
- which train was chosen
- which candidates were rejected and why

## Replay-Oriented Event Distinction

Each event now carries:

- `event_scope`
  - `PLAYER_LOCAL`
  - `MATCH_GLOBAL`
- `timeline_lane`
  - `runner`
  - `hunter`
  - `match`
- `event_family`
  - `LIFECYCLE`
  - `POSITION`
  - `MOVEMENT`
  - `PLANNING`
  - `RESOLUTION`

This is meant to make future UI replay views much easier to build.
