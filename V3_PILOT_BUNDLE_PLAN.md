# V3 PILOT BUNDLE PLAN

## Purpose

This document defines the first concrete output of the `v3` track.

`v3` should not stay at the architecture-only level.
The first real deliverable should be a minimal but valid `V3TransitBundle` built from the existing nationwide Shinkansen data.

## Scope

The first pilot bundle uses:

- the full nationwide Shinkansen station set already assembled for `v2`
- the full Shinkansen route geometry order already assembled for `v2`
- the validated weekday train-instance dataset already assembled for `v2`

This means the first `v3` pilot does not invent a new rail network.
It upgrades the same national Shinkansen surface into a GIS-first structure.

## First Deliverables

1. `data/v3_shinkansen_bundle.json`
2. `scripts/ingest/build_v3_shinkansen_bundle.py`
3. `scripts/dev/render_v3_shinkansen_map.py`
4. `visuals/v3_shinkansen_multiscale_map.svg`

## Minimum Bundle Content

The first pilot bundle should include:

- `physicalStations`
- `stationGroups`
- `trackCenterlines`
- `pathways` (empty for now is acceptable)
- `serviceRoutes`
- `servicePatterns`
- `tripInstances`
- `serviceGeometry`
- `labelRepresentations`
- `gameNodes`

## First-Pass Simplifications

Allowed for the pilot:

- one-to-one mapping from `physicalStation` to `stationGroup`
- one-to-one mapping from `stationGroup` to `gameNode`
- one first-pass `servicePattern` per service route family
- route geometry built from ordered station coordinates instead of detailed track splines
- empty `pathways`

Not allowed:

- going back to hand-drawn route truth
- dropping real lat/lon
- dropping real train instances

## Bundle Goal

The first pilot bundle should prove:

1. the nationwide Shinkansen map can be expressed in the `v3` canonical schema
2. service geometry and train instances can coexist in the same bundle
3. the project can render multiple map representations from the same underlying bundle

## First Visualization Goal

The first `v3` image should not just redraw `v2`.

It should visibly show the intended `v3` shift:

- a lower-zoom corridor-style view
- a more service-oriented view
- cleaner station ranking and label control

This is enough to prove that `v3` is a map-system upgrade, not just a rebrand of `v2`.
