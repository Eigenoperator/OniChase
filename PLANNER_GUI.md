# PLANNER GUI

## Purpose

This document explains the planning-first local GUI.

Unlike the replay-oriented debug GUI, this page is meant to help design and assemble playable route plans against the real Yamanote timetable.

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

## Recommended Launch

```bash
cd /home/xincheng/toy/Chase
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/planner.html
```

## Current Scope

The first version focuses on planning and scenario assembly, not on full in-browser match simulation.

It already supports:

- `WAIT_UNTIL`
- `BOARD_TRAIN`
- `BOARD_ANY_OF`
- `RIDE_TO_STATION`

## Intended Next Step

This page is the base for a future in-browser planning loop where Scorp can:

- build both sides' plans
- compare route ideas quickly
- later trigger local simulation directly from the same interface
