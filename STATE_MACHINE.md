# STATE MACHINE

## Purpose

This document defines the minimum match state machine for the game described in [rule/RULES_v0.5.md](/home/xincheng/toy/Chase/rule/RULES_v0.5.md) and the runtime model defined in [SCHEMA.md](/home/xincheng/toy/Chase/SCHEMA.md).

The goal is to answer one question clearly:

How does one match progress from start to finish?

## Core Idea

The match is a server-authoritative discrete simulation with:

- a small set of global match phases
- player-local position carriers
- scheduled events
- deterministic resolution of reveal and capture

At the top level, the match moves through only four global phases:

1. `RUNNER_HEAD_START`
2. `REAL_TIME`
3. `PLANNING_PAUSE`
4. `RESOLVED`

## 1. Global Match Phases

### `RUNNER_HEAD_START`

The Runner starts alone from the shared opening node and gets a 1-hour real-time head start under the normal time scale.

Properties:

- Runner can move normally
- Hunter is not yet active in the world
- Capture cannot happen yet
- Reveal does not fire yet

Exit condition:

- Head start duration reaches `runnerHeadStartSec`

Next phase:

- `REAL_TIME`

### `REAL_TIME`

This is the default active gameplay phase.

Properties:

- Both Runner and Hunter are active
- Plans auto-execute
- Train and walking events resolve
- Reveal events can fire
- Capture checks are enabled

Exit conditions:

- A planning pause starts
- Capture occurs
- Survival time limit is reached

Next phase:

- `PLANNING_PAUSE`
- `RESOLVED`

### `PLANNING_PAUSE`

This is the synchronized secret-planning window.

Properties:

- World time progression is frozen
- Both players submit or revise private plans
- No movement occurs
- No capture occurs during the pause itself

Exit condition:

- Pause timer reaches `planningPauseDurationSec`

Next phase:

- `REAL_TIME`

### `RESOLVED`

Terminal phase.

Properties:

- Match is over
- Winner is fixed
- No further events are processed except post-match persistence

Entry conditions:

- Hunter captures Runner
- Runner survives until time limit

## 2. Phase Diagram

```text
┌─────────────────────┐
│ RUNNER_HEAD_START   │
└─────────┬───────────┘
          │ head start ends
          v
┌─────────────────────┐
│ REAL_TIME           │◄──────────────┐
└──────┬────────┬─────┘               │
       │        │                     │
       │        │ pause start         │ pause end
       │        v                     │
       │   ┌─────────────────────┐    │
       │   │ PLANNING_PAUSE      │────┘
       │   └─────────────────────┘
       │
       │ capture or time limit
       v
┌─────────────────────┐
│ RESOLVED            │
└─────────────────────┘
```

## 3. Player-Local State

Global phase alone is not enough. Each player also has a local runtime state.

Each player always has:

- one `carrier`
- zero or one active plan
- last reveal payload received

### Carrier State

From [SCHEMA.md](/home/xincheng/toy/Chase/SCHEMA.md), a player can be on exactly one carrier:

- `NODE`
- `TRAIN`
- `WALK_EDGE`

This is not a separate global match phase. It is a local sub-state inside the current global phase.

Examples:

- During `REAL_TIME`, Runner may be on `TRAIN` while Hunter is on `NODE`
- During `PLANNING_PAUSE`, both carriers are frozen and preserved

## 4. Event Types That Drive State Changes

The match advances through scheduled events.

### Match-Level Events

- `HEAD_START_END`
- `PAUSE_START`
- `PAUSE_END`
- `REVEAL`
- `TIME_LIMIT_REACHED`
- `CAPTURE`

### Movement Events

- `TRAIN_DEPARTURE`
- `TRAIN_ARRIVAL`
- `WALK_START`
- `WALK_COMPLETE`
- `PLAN_COMMITTED`
- `PLAN_INVALIDATED`

## 5. Transition Rules

### A. Match Start

Initial state:

- phase = `RUNNER_HEAD_START`
- Runner carrier = opening node
- Hunter carrier = opening node, but inactive until head start ends
- first head-start timer scheduled

Server actions:

1. Create match state
2. Place both players at the shared start node
3. Mark Hunter as inactive for world interaction
4. Allow Runner plan execution
5. Schedule `HEAD_START_END`

### B. `RUNNER_HEAD_START` -> `REAL_TIME`

Trigger:

- `HEAD_START_END`

Server actions:

1. Activate Hunter
2. Schedule the first reveal
3. Schedule the first planning pause
4. Enable capture checks from this point forward
5. Transition phase to `REAL_TIME`

### C. `REAL_TIME` Internal Loop

While in `REAL_TIME`, the server repeatedly processes the earliest valid event.

Typical loop:

1. Advance `gameTimeSec` to next event time
2. Resolve movement event if any
3. Update player carrier
4. Check capture
5. If no capture, process reveal or pause event if due
6. Continue until a phase transition happens

### D. `REAL_TIME` -> `PLANNING_PAUSE`

Trigger:

- `PAUSE_START`

Server actions:

1. Freeze world progression
2. Preserve both players' current carrier states
3. Open secret planning input for both players
4. Start pause countdown
5. Transition phase to `PLANNING_PAUSE`

### E. `PLANNING_PAUSE` -> `REAL_TIME`

Trigger:

- `PAUSE_END`

Server actions:

1. Lock both submitted plans
2. Validate them against current carrier states
3. Keep valid plans
4. Reject or truncate invalid plan steps
5. Schedule future movement events implied by valid plans
6. Schedule next pause
7. Transition phase back to `REAL_TIME`

### F. `REAL_TIME` -> `RESOLVED` by Capture

Trigger:

- `CAPTURE`

Server actions:

1. Store `captureEvent`
2. Set `winner = "hunter"`
3. Transition phase to `RESOLVED`
4. Stop future movement and reveal processing

### G. `REAL_TIME` -> `RESOLVED` by Survival

Trigger:

- `TIME_LIMIT_REACHED`

Server actions:

1. Set `winner = "runner"`
2. Transition phase to `RESOLVED`
3. Stop future movement and reveal processing

## 6. Capture Check State Machine

Capture is not its own long-lived phase. It is an interrupt-style resolution check that runs after every relevant movement event.

### Capture Check Inputs

- Runner carrier
- Hunter carrier
- current `gameTimeSec`

### Capture Check Order

Recommended order:

1. same-trip capture
2. same-node capture
3. same-walk-edge capture

Reason:

- same-trip is the strongest identity match
- same-node is next
- same-walk-edge is edge-based overlap

### Capture Check Logic

```text
if both on same trip:
  CAPTURE(reason = same_trip)
else if both on same node:
  CAPTURE(reason = same_node)
else if both on same walk edge:
  CAPTURE(reason = same_walk_edge)
else:
  continue match
```

## 7. Reveal State Machine

Reveal is a timed interrupt inside `REAL_TIME`.

Trigger:

- `REVEAL`

Server actions:

1. Inspect Runner carrier and generate a reveal payload for Hunter
2. Inspect Hunter carrier and generate a reveal payload for Runner
3. Store both reveal payloads as one-time snapshots
4. Schedule the next reveal

Reveal mapping:

- target in `NODE` -> reveal exact node
- target in `TRAIN` -> reveal current segment
- target in `WALK_EDGE` -> reveal last departed node

Important:

- Reveal does not change phase
- Reveal does not pause the world
- Reveal does not persist as a permanent map marker in core rules

## 8. Planning State Machine

Planning is the only phase where both players make explicit route decisions.

### Planning Input Flow

1. Pause starts
2. Each player edits a private plan
3. Each player submits or lets timer expire
4. Pause ends
5. Server validates plans
6. Simulation resumes

### Plan Validation Outcomes

A submitted plan can be:

- `VALID`
- `PARTIALLY_VALID`
- `INVALID`

Recommended handling:

- `VALID`: keep all steps
- `PARTIALLY_VALID`: keep valid prefix only
- `INVALID`: discard and leave player in passive default behavior

### Passive Default Behavior

If no valid plan exists after a pause:

- if on `NODE`, stay at node
- if on `TRAIN`, remain on trip until a valid exit point from existing plan or forced end state
- if on `WALK_EDGE`, finish the current walk edge first

This avoids impossible mid-edge or mid-trip teleports.

## 9. Example Match Timeline

Example high-level timeline:

1. Match starts at shared node `S`
2. Runner enters `RUNNER_HEAD_START`
3. Runner boards a train and moves away
4. Head start ends
5. Hunter becomes active at `S`
6. Match enters `REAL_TIME`
7. Both players move through trains, nodes, and walking edges
8. First reveal fires
9. First planning pause starts
10. Both submit new plans
11. Match resumes
12. A later movement event places both on the same node
13. Capture fires
14. Match enters `RESOLVED`

## 10. Implementation Notes

### Why This State Machine Is Small

The design stays manageable because:

- global phases are only four
- player location is compressed into one carrier union
- most complexity lives in scheduled events, not extra phases

### Why Event-Driven Simulation Fits

This game is timetable-based, not physics-based.

So the right question is not:

- where are players every frame?

It is:

- what is the next meaningful event?

That makes event-driven simulation the natural fit.

### Why `PLANNING_PAUSE` Is Global

The pause must be global because:

- both players plan simultaneously
- both players must be frozen against the same world state
- fairness depends on synchronized hidden planning

## 11. Recommended Next Document

The next technical document should be one of these:

1. `MATCH_FLOW.md`
2. `PROTOTYPE_SCOPE.md`
3. `EVENT_RULES.md`

My recommendation:

- write `PROTOTYPE_SCOPE.md` next, so we can choose the first Tokyo mini-network and start building data.
