# ROADMAP

## Purpose

This document defines OniChase's current product roadmap across the first three public gameplay versions.

It is not a rule file.
It is a scope and sequencing document, so we can keep implementation decisions aligned with the intended growth path of the game.

## Version Plan

### V1: Yamanote Line

`V1` is the first playable rules-and-UX validation version.

Scope:

- one line only
- one loop map
- real Yamanote stations
- real Yamanote timetable
- runner / hunter asymmetric play
- planning and live phases
- same-node and same-train capture

Purpose:

- validate whether the core chase game is actually fun
- validate whether planning a route under incomplete information is readable
- validate whether hunter mode and runner mode are both understandable
- validate the client UX before the map gets much larger

Not the goal of V1:

- real Tokyo full-network complexity
- multi-line transfer-heavy balance
- full reveal system tuning
- geographically realistic city map rendering

### V2: Shinkansen Network

`V2` is the first multi-line strategic expansion.

Scope:

- whole Shinkansen map
- multiple lines
- simpler and more fixed timetable structure than Tokyo commuter rail
- longer-distance chase and interception planning

Purpose:

- validate the game after moving from one line to multiple lines
- test whether the core system still works when route branching becomes meaningful
- introduce larger-scale strategy without immediately jumping into Tokyo timetable complexity

Why Shinkansen comes before Tokyo:

- it gives us a multi-line map sooner
- the network is strategically interesting but structurally cleaner
- it is a better bridge between `V1` and full Tokyo than jumping directly from Yamanote to urban rail chaos

Not the goal of V2:

- dense local commuter transfers
- huge same-station ambiguity
- full metropolitan schedule density

### V3: GIS Shinkansen

`V3` is the GIS-first upgrade of the nationwide Shinkansen version.

Scope:

- whole Shinkansen map
- real physical geometry
- real service geometry
- multi-scale map rendering
- stronger map / timetable linkage
- a more modern transit-map presentation layer than `v2`

Purpose:

- keep the same nationwide Shinkansen gameplay scope as `v2`
- upgrade the map and data stack from a game-oriented board to a GIS-oriented transit model
- prove the long-term architecture before moving to a denser urban system later

Risks:

- GIS and timetable integration become much more demanding
- map readability becomes harder as geometry becomes more real
- station grouping and multi-scale rendering become more important

## Current Priority

The project is currently transitioning from `V2` playability work into the first `V3` architecture track.

That means current work should primarily optimize for:

- `v2` playable stability
- `v2` client flow quality
- `v3` GIS architecture correctness
- reusable geometry and service contracts
- long-term map/timetable linkage

## Expansion Rule

We should not change version scope casually once a version is already carrying real data and clients.

For the current roadmap:

1. `V2` proves the nationwide Shinkansen game loop with real trains.
2. `V3` upgrades the same network into a GIS-first architecture.
3. A later city-scale version can build on that architecture instead of starting from scratch.
