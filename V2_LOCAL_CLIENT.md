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
- station clicking
- a current plan cursor station and time
- upcoming departures from the selected station after the cursor time
- train preview with downstream stop list
- a minimal plan board that chains route legs from the current cursor

## Launch

```bash
cd /home/xincheng/toy/Chase
./START_ONICHASE_V2_CLIENT.sh
```

## Next

The next stage is to turn this shell into actual `v2` gameplay:

- runner / hunter sides
- start presets
- hidden-information rules
- capture checks
- route-leg editing instead of always riding to the terminal stop
