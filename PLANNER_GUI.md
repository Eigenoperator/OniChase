# PLANNER GUI

## Purpose

This document explains the planning-first local GUI.

Unlike the replay-oriented debug GUI, this page is meant to help design and assemble playable route plans against the real Yamanote timetable.

The current UI is intentionally shaped like a lightweight client prototype:

- runner mode / hunter mode switch
- map as the primary screen
- a stronger match-table presentation for runner and hunter on the side
- the active player's current plan is drawn directly on the map as a dashed route trace with numbered waypoints
- top-left HUD for current time and current location
- a dedicated plan-test card for the current local planning assumptions
- a bottom quickbar that summarizes the active side, current position, route preview, and next important decision
- current-train next-stop list when the player is on a train
- right-side decision box showing the current plan

## File

- [planner.html](/home/xincheng/toy/Chase/planner.html)

## What It Does

- choose global scenario start and end time
- choose runner and hunter start stations
- switch each side between `actions` mode and `plan` mode
- inspect the current local state after the currently written steps
- browse catchable real departures from the current station
- browse future alight targets from the current train
- append steps directly from planner suggestions
- export a ready-to-use scenario JSON
- load the default runner-plan test preset with one click

## Recommended Launch

Double-click:

- [START_ONICHASE_LOCAL.desktop](/home/xincheng/toy/Chase/START_ONICHASE_LOCAL.desktop)

Or run:

```bash
cd /home/xincheng/toy/Chase
./START_ONICHASE_LOCAL.sh
```

Then open:

```text
http://127.0.0.1:8000/planner.html
```

If port `8000` is occupied, the launcher automatically moves to the next available nearby port and prints the final URL.

## Current Scope

The first version focuses on planning and scenario assembly, not on full in-browser match simulation.

It already supports:

- `WAIT_UNTIL`
- `BOARD_TRAIN`
- `BOARD_ANY_OF`
- `RIDE_TO_STATION`

## Default Local Plan Test

The current default local test mode is aimed at quickly iterating on runner planning:

- the in-game clock starts at `06:00`
- runner uses `plan` mode
- runner gets `1 minute` of out-of-game planning time before `06:00`
- hunter defaults to staying at the start station until match end
- runner can revise future steps at any time by editing or cutting later plan items in the client

## Current UI Goal

The planner is no longer meant to feel like a raw debug utility.

The current visual direction is:

- map-first
- readable at a glance
- strong distinction between runner and hunter
- good enough to support actual local playtesting, not only data editing

## Intended Next Step

This page is the base for a future in-browser planning loop where Scorp can:

- build both sides' plans
- compare route ideas quickly
- later trigger local simulation directly from the same interface
