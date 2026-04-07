# V3 GIS ARCHITECTURE

## Purpose

This document defines the first architecture direction for `v3`.

`v3` is not just a larger map.
It is the point where OniChase starts treating rail data as a real multi-scale transit GIS instead of a manually drawn game board.

The goal is to support:

- real Tokyo rail geometry
- real service patterns and timetables
- multi-scale map rendering
- station-group and interchange modeling
- future map/timetable hover and replay linkage

This is an architecture document, not a gameplay rule file.

## Core Decision

`v3` should be built as two linked systems:

1. Physical network layer
2. Service operation layer

These two layers must stay separate, but they must be joinable through stable IDs and linear references.

## Layer Split

### 1. Physical Network Layer

This layer describes what exists in the city physically.

Examples:

- track centerlines
- station points
- station groups
- platform or pathway structures
- station level information

Recommended source direction:

- `N02` national rail geometry as the first baseline
- later additional sources for urban detail where needed

This layer answers:

- where a station is
- how lines physically run
- which nearby stops belong to one station complex

This layer does not answer:

- what train is running right now
- which service a player can board at 08:13

### 2. Service Operation Layer

This layer describes how trains operate over the physical network.

Examples:

- GTFS routes
- trips
- stop_times
- calendars
- GTFS realtime later

This layer answers:

- what service exists
- what the train name is
- when it stops
- what its ordered stop pattern is

This layer does not define:

- exact authoritative map geometry
- station-group spatial rules by itself

### 3. Game Abstraction Layer

OniChase still needs a game-facing layer above raw transit data.

Examples:

- gameplay node
- station group
- legal transfer edges
- reveal-friendly segment names
- carrier state

This layer is where raw transit data becomes playable game data.

It must remain explicit, because:

- one raw station may map to one gameplay node
- one large station complex may map to multiple gameplay nodes
- one transfer may be legal in GIS but intentionally simplified in the game

### 4. Presentation Layer

This layer decides what the player sees at each zoom level.

Examples:

- corridor view at low zoom
- separated service paths at medium zoom
- more realistic track geometry at high zoom
- major-only labels at low zoom
- dense station labels at high zoom

Important rule:

`v3` should not force one fixed geometry representation for every zoom level.

## Architecture Principle

The system should follow this pipeline:

`raw geometry + raw timetable`
-> `canonical transit model`
-> `game abstraction`
-> `map/timetable presentation`

This is the main difference from current `v1` and `v2`, where rendering is still much closer to project-specific game data.

## Recommended Stack

### Storage / Processing

- `PostGIS`
- offline geometry preprocessing scripts
- timetable ingestion scripts

### Map Delivery

- `MVT` during development
- `PMTiles` for packaged publishing

### Frontend Map

- `MapLibre GL JS`

### Timetable / Diagram

- `D3`

This stack is recommended because it supports:

- vector tiles
- zoom-based styling
- symbol collision handling
- multilingual labels
- custom synchronization with timetable visuals

## Why V3 Needs A Different Map Model

`v1` and `v2` can tolerate much more schematic rendering.

`v3` cannot, because Tokyo introduces:

- many shared corridors
- many same-name or near-name stations
- very dense interchange complexes
- route branches that overlap visually
- service patterns that diverge on one physical path

A manually edited single SVG stops scaling at this point.

So `v3` must move to:

- geometry data as source of truth
- service data as source of timetable truth
- generated map representations

## Multi-Scale Rule

The `v3` map should be hybrid rather than purely schematic or purely raw-geographic.

### Low Zoom

Show:

- simplified corridors
- major hubs
- strategic geography

Hide:

- dense local labels
- station-by-station detail

### Medium Zoom

Show:

- route branching
- important station groups
- service separation on shared corridors

### High Zoom

Show:

- more realistic geometry
- more station labels
- station-group detail
- future pathway or platform detail where needed

This allows the map to stay readable without breaking real-world structure.

## Canonical Join Rule

Map geometry and timetable must be joinable through one canonical reference system.

Minimum requirement:

- every stop must resolve to a physical or grouped station object
- every trip must resolve to service geometry
- every map-highlighted train must also exist in timetable space
- every timetable-hovered train must also resolve to map space

This is essential for:

- live train highlighting
- replay
- hover coupling
- future search / interception tooling

## What V3 Should Reuse

`v3` should reuse from earlier versions:

- game rule layer
- planning format
- scenario/result/replay boundaries
- train-instance based simulation model

`v3` should not reuse as source of truth:

- hand-placed schematic route SVGs
- one-off local map coordinate hacks

## Proposed Development Sequence

### Phase 1: Tokyo GIS Pilot

Pick one smaller Tokyo area and prove:

- physical geometry load
- GTFS service load
- station-group logic
- map/timetable linking

### Phase 2: Canonical Data Contracts

Lock:

- station group schema
- physical station schema
- service pattern schema
- geometry tile export shape

### Phase 3: Multi-Scale Rendering

Build:

- low zoom corridors
- medium zoom service separation
- high zoom detailed station view

### Phase 4: OniChase Integration

Connect:

- planning UI
- reveal UI
- replay
- simulation engine

## Immediate Decision For The Project

Starting now:

- `v1` remains the gameplay validation base
- `v2` remains the nationwide real-train bridge version
- `v3` starts its own architecture track using GIS-first assumptions

This means `v3` work can begin before `v2` is fully finished, but it should begin at the architecture and data-model level first.
