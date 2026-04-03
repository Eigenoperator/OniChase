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
- a right-side planning and replay workspace
- the current runner-plan test preset
- action buttons for `Set Start Here`, `Board Earliest`, `Ride To Selected`, `Wait +5m`, `Undo Step`, and `Clear Plan`
- in-window simulation via `Run Simulation`
- state-driven planning controls:
  - while at a station, the right panel lists upcoming departures from the current station
  - after boarding, the right panel lists downstream stations for the current train
  - clicking a reachable station on the map while on a train can directly add the ride step
- the train outlook now shows the full remaining stop list for the current service; for loop services it shows one full loop ahead
- the entire right-side panel is now scrollable, so in smaller window sizes the player can use the mouse wheel to browse long action/result lists
- a `Settings` window is available from the top bar; for now it supports changing the UI font size
- the main layout now uses a draggable left-right divider, so the player can widen the right planning panel when needed
- the right column itself now also has draggable internal dividers, so `Info / Actions / Result` can be resized vertically
- the `Result` area now works as a replay panel: after `Run Simulation`, it shows a scrollable event list plus detail for the selected event
- the client now has explicit match flow:
  - `PLANNING` lasts 60 real seconds before the in-game clock starts
  - during planning, both player positions remain visible
  - after the match enters `LIVE`, the in-game clock advances and the opponent position is hidden
  - plan edits during `LIVE` automatically trim only the unresolved future steps, so the player can branch the rest of the route without rewriting already executed actions
  - the local playtest client now also has a `Start Game` button, so the user can manually end `PLANNING` early and begin `LIVE` immediately
  - this early-start button is a playtest convenience only; in the real multiplayer game, both players should agree before the game starts
- the current plan panel now marks `DONE` versus `NEXT` steps so the time flow is easier to read during playtests
- the replay panel is now map-linked:
  - selecting an event in the result list updates the map to that event's `state_after`
  - replay focus temporarily reveals both sides on the board, even if normal live mode would hide the opponent
  - if a replay event leaves a player on a train, the client anchors that train near the closest scheduled station at that replay time
- planning is now more player-facing:
  - while at a station, the right panel becomes a two-step flow: first choose a train, then choose a destination
  - during `PLANNING`, the planning controls now use a plan cursor instead of only the live current state, so the player can keep chaining multiple trains from the end of the already planned route
  - the chosen train is highlighted before commitment, instead of instantly appending a board step
  - the destination strip is horizontally draggable for long routes and now also has a visible horizontal scrollbar
  - the right panel now also shows a guaranteed visible vertical destination list, so Step 2 does not depend only on the horizontal strip rendering correctly
  - the chosen service is also highlighted on the map so the planned route reads more like a railway UI than a raw form
  - after choosing a train, the right panel auto-scrolls toward the destination strip so the next step is easier to discover
  - step 2 now has two valid inputs: click `Ride Here` in the destination strip, or click one of the highlighted destination stations on the left map
  - once a train is chosen, Step 1 collapses into a compact selected-train summary and the right pane automatically gives more height to the action area, so Step 2 has more room
- the match clock is now much more prominent, especially during `PLANNING`
- the upper-right plan board now also shows the current plan cursor location, so the player can tell where the next planned leg will start
- the upper-right plan board is now rendered as route cards rather than a plain text block, so chained train plans read more like a real transfer board
- the old `MATCH TABLE` and `IMMEDIATE OPTIONS` panels have been removed to keep the right side focused on planning, actions, and replay
- the plan board is now a fixed top-right region instead of part of the scrollable right-side body, so choosing trains and stations below no longer pushes it out of view
- hunter-mode visibility is now implemented in the client:
  - while the hunter is active during `PLANNING`, a runner at station is shown exactly
  - if the runner is currently riding, the hunter only gets a rough map cue with no textual route description
  - during `LIVE`, the hunter no longer sees the runner on the map or in the HUD
  - the hunter also no longer sees the runner's route trace on the map

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
