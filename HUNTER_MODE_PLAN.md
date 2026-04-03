# HUNTER MODE PLAN

## Purpose

This document defines the current working plan for `hunter mode` playtests in OniChase.

It does not change the formal game rules by itself.
It translates Scorp's current hunter-mode decisions into an implementation and test plan.

## Current Hunter Information Model

### Planning

During `PLANNING`, the hunter can see the runner's current location in this abstracted way:

- If the runner is at a station, show the exact station.
- If the runner is on a train, show only a rough between-stations position on the map, but do not reveal the exact train number or any textual route hint.

For the current Yamanote-only prototype, `on the line` effectively means:

- show that the runner is somewhere between visible stations on the loop,
- allow the hunter to infer the likely line from geography and map shape,
- but do not expose the concrete service identifier or add textual hints naming the line or the segment.

### Live

During `LIVE`, the hunter sees nothing about the runner's current location unless another rule later introduces a scheduled disclosure event.

## What `Reveal` Means

`Reveal` is a future gameplay system, not an always-on visibility rule.

In practical terms, it means:

- at specific scheduled moments,
- the game discloses some location information about the runner to the hunter.

Examples of future reveal designs could include:

- exact station reveal,
- line-only reveal,
- zone reveal,
- last-known-location reveal.

For the current hunter-mode test phase, we are not relying on a reveal system yet.
The working visibility rule is simply:

- `PLANNING`: hunter sees limited runner location info
- `LIVE`: hunter sees nothing

## Current Hunter Operation Model

The hunter's main movement operations are the same as the runner's:

- wait at station
- board train
- ride to station
- continue chaining multiple train legs during planning
- edit future plan while live play is running

There is no special hunter-only movement system in the current prototype.

## First Hunter Test Assumption

For the first focused hunter-mode playtests, assume:

- the runner is not moving
- the hunter is the side we actively play

This isolates the hunter-side experience and helps answer simpler questions first:

- Can the hunter plan smoothly?
- Is the hunter's information presentation clear enough?
- Is the hunter's map reading loop understandable?
- Can the hunter catch a stationary target without confusion?

## First Hunter Test Loop

### Test Setup

- Start at `06:00`
- Runner stays fixed at one chosen location
- Hunter is the active play side
- Use the real Yamanote timetable as usual

### Test Questions

1. Can the hunter understand what is known during `PLANNING` versus `LIVE`?
2. Can the hunter easily pick a starting station?
3. Can the hunter clearly choose trains and downstream stops?
4. Is the hunter's route plan readable on the map and in the plan board?
5. Once live play begins, does the loss of runner visibility still feel understandable rather than broken?

### Recommended First Cases

1. Runner fixed at a station, hunter tries to route there.
2. Runner fixed as `on the line`, hunter tries to infer and intercept.
3. Hunter starts far away and must plan multiple train legs.

## Implementation Priority

The next hunter-mode implementation work should focus on:

1. hunter-side visibility presentation during `PLANNING`
2. hunter-side playtest flow in local client
3. hunter-side playtest flow in web client
4. first dedicated stationary-runner hunter scenarios

## Temporary Scope Boundary

The current hunter-mode work does not yet require:

- a full reveal schedule system
- hunter-exclusive movement mechanics
- full asymmetric balance tuning

Those can come later after the first hunter-side usability tests.
