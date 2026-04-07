# V3 SHINKANSEN SCOPE

## Purpose

This document defines what `v3` means now that the project has decided to keep using the nationwide Shinkansen map instead of switching immediately to Tokyo full-map gameplay.

`v3` is not a new route family.
It is a new map-and-data architecture layer on top of the same Shinkansen gameplay surface already explored in `v2`.

## Core Definition

`v2` and `v3` share the same broad network:

- nationwide Shinkansen map
- real train names
- real train instances

But they do not share the same technical ambition.

### V2

Focus:

- make the nationwide Shinkansen version playable
- validate route planning, capture, and phase loop
- keep the client readable

Map character:

- game-oriented
- simplified
- still allowed to use project-specific visual shortcuts

### V3

Focus:

- turn the same Shinkansen space into a GIS-first transport product foundation
- separate physical geometry from service data
- support multi-scale rendering
- support stronger map/timetable linkage

Map character:

- real-world geometry aware
- zoom-sensitive
- more modern and map-like
- better prepared for future dense-city versions

## What V3 Must Add

### 1. Physical Geometry Layer

`v3` must represent:

- real station positions
- real route geometry
- station grouping
- future pathway-ready structure

### 2. Service Layer Coupling

`v3` must make it easier to link:

- train instance
- map path
- stop sequence
- timetable view

### 3. Multi-Scale Representation

`v3` should not use one fixed line drawing at all zoom levels.

It should support:

- simplified corridor view
- separated service path view
- more detailed geometry view

### 4. Better Map Interaction

`v3` should improve:

- route readability
- station label behavior
- selected train path readability
- future map/timetable hover coupling

## What V3 Does Not Need To Change

`v3` does not need to replace everything from `v2`.

It should continue to reuse:

- planning format
- simulation engine direction
- train-instance model
- runner / hunter phase loop
- capture logic

So `v3` is primarily:

- a data-layer upgrade
- a map-layer upgrade
- a presentation-layer upgrade

not a full gameplay restart.

## First V3 Milestones

### Milestone 1

Lock the GIS architecture and canonical schema.

Outputs:

- `V3_GIS_ARCHITECTURE.md`
- `V3_GIS_SCHEMA.md`

### Milestone 2

Define the first small `V3TransitBundle` for Shinkansen.

It does not need every future field.
It needs enough to prove:

- physical geometry
- service geometry
- trip linkage
- label and zoom metadata

### Milestone 3

Render the first GIS-style Shinkansen map representation.

Goals:

- cleaner zoom behavior
- better line separation
- stronger service highlighting
- less manual SVG hacking

### Milestone 4

Connect map and timetable views more tightly.

Examples:

- hover one train, highlight its path
- click one station group, show service patterns
- later support replay coupling

## Decision

`v3` is now defined as:

`GIS-first nationwide Shinkansen`

This means:

- we keep the Shinkansen network
- we upgrade the architecture
- we do not jump to Tokyo full-map gameplay yet
