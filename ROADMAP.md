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

### V3: Tokyo Real Network

`V3` is the dense-network upgrade that keeps the `v2` gameplay shell but moves the game onto the real Tokyo-area railway network.

Scope:

- real Tokyo-area rail map with physical station geometry preserved
- shared `planning / live / capture / replay` gameplay with `v2`
- MapLibre rendering, real service geometry, and denser line identity rules
- real commuter, subway, through-running, and transfer-heavy timetable structure
- online and single-player parity on the same core loop
- real physical geometry
- stronger map / timetable / planner linkage than `v2`

Purpose:

- prove that OniChase still works when the railway network becomes transfer-dense and through-running-heavy
- keep `v3` on the same game rules as `v2`, rather than inventing a separate Tokyo-only ruleset
- harden the long-term data architecture: station groups, physical stations, route identity, and planner-visible departures
- make the real-map presentation layer production-worthy enough for repeated public playtests

Risks:

- route identity and through-running boundaries become much more demanding than in Shinkansen-only play
- map readability and performance both become harder once the network is dense
- planner-visible departures can drift from physical reality unless auditing stays reusable and automated

## Current Priority

The project is currently in a split state:

- `v2` remains the stable nationwide public playtest baseline
- `v3` is the active forward path for map/data/gameplay integration

That means current work should primarily optimize for:

- `v2` playable stability and online reliability
- `v3` Tokyo gameplay correctness on the real network
- reusable planner/data audits, especially line -> train -> stop visibility
- top-level docs and public clients matching the actual current architecture

## Expansion Rule

We should not change version scope casually once a version is already carrying real data and clients.

For the current roadmap:

1. `V2` proves the nationwide Shinkansen game loop with real trains.
2. `V3` proves the same game loop on the real Tokyo dense network with the same core rules.
3. Later expansion should grow outward from the stable `v3` data/gameplay architecture instead of branching into a separate incompatible product.
