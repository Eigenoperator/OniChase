# V2 LOCAL CLIENT

## Purpose

This document tracks the first local playable shell for `v2`.

The goal is not to ship the full nationwide game yet.

The goal is to let us:

- open the nationwide Shinkansen board
- click stations on the real `v2` map
- browse real departures from the selected station
- inspect the full remaining stop list of a selected train
- chain route legs into a first plan board

## Files

- [app/v2_local_client.py](/home/xincheng/toy/Chase/app/v2_local_client.py)
- [START_ONICHASE_V2_CLIENT.sh](/home/xincheng/toy/Chase/START_ONICHASE_V2_CLIENT.sh)
- [data/shinkansen_v2_bundle.json](/home/xincheng/toy/Chase/data/shinkansen_v2_bundle.json)

## Current Scope

The current `v2` client already provides:

- a nationwide Shinkansen schematic rendered from real station coordinates
- route coloring by Shinkansen family
- station clicking plus live player markers on the nationwide map
- `runner / hunter` mode switching
- `PLANNING / LIVE / ENDED` phase flow with a visible in-game clock
- manual `Start Game` and pause/resume controls
- a current plan cursor station and time
- upcoming departures from the selected station after the current plan cursor time
- train preview with downstream stop list
- destination selection from the selected train's downstream stops
- a plan board that chains route legs from the current cursor
- live capture checks and `GAME END` feedback
- result summary and replay event list from the generic train-instance simulator
- the same result / replay layer is now also being mirrored onto the `v2` web client

## Launch

```bash
cd /home/xincheng/toy/Chase
./START_ONICHASE_V2_CLIENT.sh
```

## Next

The next stage is to deepen actual `v2` gameplay:

- make local and web `v2` parity tighter
- keep polishing hidden-information rules and map feedback
- richer route-leg editing beyond the current "select train -> select destination stop" flow
- expand replay detail and result readability even further
