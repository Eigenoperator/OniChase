# LOCAL CLIENT

## Purpose

This document explains the first local desktop client prototype for OniChase.

The current implementation uses `tkinter`, not a browser and not a local website.

This choice is intentional:

- `PySide6` is not installed in the current environment
- `tkinter` is already available
- the goal right now is fast local playtest iteration

## Files

- [app/local_client.py](/home/xincheng/toy/Chase/app/local_client.py)
- [START_ONICHASE_CLIENT.sh](/home/xincheng/toy/Chase/START_ONICHASE_CLIENT.sh)
- [START_ONICHASE_CLIENT.desktop](/home/xincheng/toy/Chase/START_ONICHASE_CLIENT.desktop)

## Current Scope

The first local client prototype already provides:

- a native window
- a Yamanote loop map
- runner and hunter live readout
- active plan route drawing on the map
- a quick summary bar
- a right-side plan and option panel
- the current runner-plan test preset
- action buttons for `Set Start Here`, `Board Earliest`, `Ride To Selected`, `Wait +5m`, `Undo Step`, and `Clear Plan`
- in-window simulation via `Run Simulation`
- state-driven planning controls:
  - while at a station, the right panel lists upcoming departures from the current station
  - after boarding, the right panel lists downstream stations for the current train
  - clicking a reachable station on the map while on a train can directly add the ride step
  - the train outlook now shows the full remaining stop list for the current service; for loop services it shows one full loop ahead

## Launch

Double-click:

- [START_ONICHASE_CLIENT.desktop](/home/xincheng/toy/Chase/START_ONICHASE_CLIENT.desktop)

Or run:

```bash
cd /home/xincheng/toy/Chase
./START_ONICHASE_CLIENT.sh
```

If launch fails, inspect:

```text
/home/xincheng/toy/Chase/.onichase-client-launch.log
```

## Known Limits

This is still a shell, not the final playable client.

It still does not yet:

- support full free-form step editing from structured forms
- replay a finished match on a dedicated timeline
- replace the engine

The current goal is to establish the local native client structure first.
