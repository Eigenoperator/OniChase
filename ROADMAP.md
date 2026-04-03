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

### V3: Tokyo Full Map

`V3` is the large-scale urban version.

Scope:

- Tokyo network
- complicated lines
- complicated transfers
- complicated timetable interactions
- the highest-density information game in the roadmap

Purpose:

- realize the full original vision of the project
- combine the rules validated in `V1` with the multi-line planning lessons from `V2`
- support a much richer pursuit-and-evasion experience with real urban rail complexity

Risks:

- UI clarity becomes much harder
- path planning becomes much heavier
- data modeling for stations, interchanges, and geometry becomes much more important

## Current Priority

The project is currently in `V1`.

That means current work should primarily optimize for:

- Yamanote gameplay quality
- hunter / runner usability
- information presentation
- planning flow
- local and online playtest stability

## Expansion Rule

We should not move to `V2` or `V3` just because a larger map sounds exciting.

We should move only when `V1` has answered these questions well enough:

1. Is the core chase loop fun?
2. Is the current plan UX understandable?
3. Is hunter information readable but not overpowered?
4. Can we explain the game clearly to a new player?

Only after that should the project scale outward.
