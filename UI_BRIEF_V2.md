# UI BRIEF V2

## Position

`OniChase v2` should feel like a Japanese Shinkansen wayfinding system transformed into a high-pressure two-player pursuit game.

This is not:

- a fantasy HUD
- a web admin dashboard
- a generic GIS viewer

This is:

- a modern railway information system
- a tactical route-planning interface
- a time-pressure driven pursuit board

## Core Experience

The player should always understand:

- what time it is now
- when the next planning window begins
- what train can be boarded next
- what the current plan chain is
- what is known or unknown about the opponent

## Primary Visual Layers

1. Time
2. Map
3. Planning rail
4. Plan board
5. Result / replay

Time must be the first visual layer, not a secondary label.

## Main Layout

The main play screen should read as:

- top command bar with phase, time, countdown, room/session status
- large left map canvas as the main stage
- right planning rail for current state, departures, stop ladder, and actions
- lower board for plan chain, replay, and event context

PC widescreen is the primary target.

## Phase Differentiation

### Planning

- higher information density
- expanded planning rail
- expanded plan board
- time frozen
- both player states more legible

### Live

- map becomes dominant
- planning rail becomes lighter and more compact
- current time and next planning countdown become stronger
- active route and player positions become the focal point

### Ended

- result card explains why the game ended
- replay and last critical minutes become easy to review

## Planning Rail

The right rail should feel like a hybrid of:

- a departure board
- a train selection panel
- a stop ladder
- a tactical route planner

The core sequence is:

`Station -> Departure -> Downstream Stops -> Add Leg -> Plan Board`

## Plan Board

The plan board is not a log.

It should read like:

- a route sheet
- a tactical itinerary
- a chain of legs

Each leg should make these fields immediately readable:

- departure time
- train name
- boarding station
- destination station
- current execution state

## Information Difference

Runner information should feel precise and calm.

Hunter information should feel partial, inferred, and pressure-driven.

Hunter visibility should distinguish:

- confirmed station intel
- corridor clue
- stale intel
- unknown

## Visual Direction

- dark control-room palette
- route colors retained but disciplined
- player colors separate from rail colors
- strong numeric clock
- dense but clean panel hierarchy
- minimal decorative effects
- sharp transitions around hourly planning

## Anti-Patterns

Avoid:

- fantasy cockpit styling
- generic dashboard grids
- over-literal GIS presentation
- overly playful subway map aesthetics

## Required Screens

1. Lobby / room entry
2. Planning default
3. Planning with train selected
4. Live runner
5. Live hunter
6. Ended / replay
