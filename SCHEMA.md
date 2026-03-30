# SCHEMA

## Purpose

This document defines the first implementation-oriented data model for the game based on [rule/RULES_v0.5.md](/home/xincheng/toy/Chase/rule/RULES_v0.5.md).

The goal of this schema is to support:

- Real timetable-based movement
- Discrete capture checks
- Periodic planning pauses
- Timed information reveals
- Server-authoritative simulation

This is a technical schema draft, not a gameplay rule document.

## Design Principles

- Keep runtime state small and explicit.
- Separate static map data from per-match mutable state.
- Model player position only through the three legal carriers:
  - `NODE`
  - `TRAIN`
  - `WALK_EDGE`
- Use event-driven time progression instead of frame-based simulation.
- Make all movement and capture checks reproducible from static data plus match history.

## Data Layers

The system is split into three layers:

1. Static network data
2. Match configuration
3. Runtime match state

## 1. Static Network Data

### Node

Represents a gameplay node, not a raw real-world station object.

```ts
type NodeId = string;

type Node = {
  id: NodeId;
  name: string;
  names: {
    en: string;
    ja: string;
    zh_hans: string;
  };
  regionId: string;
  category: "normal" | "hub";
  operatorIds: string[];
  rawStopIds: string[];
  lat: number;
  lon: number;
  tags: string[];
};
```

Notes:

- `name` is the default English display name for internal tooling.
- `names` stores multilingual display labels for UI and localization.
- `rawStopIds` links the gameplay abstraction back to source transit data.
- `category` helps later balancing and visualization.
- `tags` can mark special cases such as `jr`, `metro`, `private`, `hub_split`.

### Service Calendar

Represents which timetable set is active.

```ts
type ServiceCalendarId = string;

type ServiceCalendar = {
  id: ServiceCalendarId;
  label: string;
  kind: "weekday";
  timezone: "Asia/Tokyo";
};
```

For v0.5, only `weekday` is required.

### Route

Represents a named transit line or service family for display and grouping.

```ts
type RouteId = string;

type Route = {
  id: RouteId;
  operatorId: string;
  shortName: string;
  longName: string;
  mode: "rail" | "subway" | "private_rail";
  color?: string;
};
```

### Trip

Represents one concrete train instance. This is the unit used by same-train capture.

Important modeling rule:

- a train instance must not be permanently glued to a single line
- one train may pass through multiple lines over its full run
- line identity should therefore be carried at the stop-time or segment level, not only on the trip root

```ts
type TripId = string;

type Trip = {
  id: TripId;
  serviceCalendarId: ServiceCalendarId;
  direction: 0 | 1;
  trainNumber?: string;
  operatorId?: string;
  serviceInstanceId?: string;
  stopTimes: TripStopTime[];
};

type TripStopTime = {
  sequence: number;
  nodeId: NodeId;
  routeId: RouteId;
  loopPassIndex?: number;
  arrivalTimeSec: number;
  departureTimeSec: number;
};
```

Notes:

- Time is stored as seconds from the match calendar base.
- `Trip` must be a concrete scheduled instance, not a frequency template.
- `routeId` on `TripStopTime` records which line the train is operating on at that stop.
- `loopPassIndex` is important for loop lines such as Yamanote, where the same station can appear multiple times in one continuous service record.
- `serviceInstanceId` can represent one continuous passenger service even when loop traversal causes repeated stations.

### Trip Segment

Represents a travel segment between two adjacent stop times inside one trip.

```ts
type TripSegmentId = string;

type TripSegment = {
  id: TripSegmentId;
  tripId: TripId;
  routeId: RouteId;
  fromNodeId: NodeId;
  toNodeId: NodeId;
  departTimeSec: number;
  arriveTimeSec: number;
  sequence: number;
};
```

This is useful for reveal logic such as `Tokyo -> Shinagawa segment`, and it preserves the possibility that one train changes line identity during a longer run.

For loop lines, segment identity must be based on sequence order, not only station pair names.

### Walk Edge

Represents an offline-generated walk connection between two gameplay nodes.

```ts
type WalkEdgeId = string;

type WalkEdge = {
  id: WalkEdgeId;
  fromNodeId: NodeId;
  toNodeId: NodeId;
  durationSec: number;
  bidirectional: boolean;
  source: "offline_precomputed";
  distanceMeters?: number;
  confidence?: "high" | "medium" | "low";
};
```

Constraints:

- `durationSec <= 900`
- Must come from offline preprocessing

### Network Bundle

Top-level static dataset loaded by the server.

```ts
type NetworkBundle = {
  version: string;
  generatedAt: string;
  calendar: ServiceCalendar;
  nodes: Node[];
  routes: Route[];
  trips: Trip[];
  tripSegments: TripSegment[];
  walkEdges: WalkEdge[];
};
```

## 2. Match Configuration

### MatchConfig

Defines one match mode and timing rules.

```ts
type MatchConfig = {
  id: string;
  label: string;
  mapVersion: string;
  timeScale: number;
  survivalDurationSec: number;
  planningPauseIntervalSec: number;
  planningPauseDurationSec: number;
  revealIntervalSec: number;
  runnerHeadStartSec: number;
  openingMode: "same_node_runner_head_start";
  captureMode: "automatic";
};
```

Recommended v0.5 defaults:

- `timeScale = 30`
- `survivalDurationSec = 172800` for 2 in-game days
- `planningPauseIntervalSec = 3600`
- `planningPauseDurationSec = 60`
- `revealIntervalSec = 3600`
- `runnerHeadStartSec = 3600`

### MatchSetup

Represents one instantiated match before it starts.

```ts
type MatchSetup = {
  matchId: string;
  configId: string;
  calendarId: ServiceCalendarId;
  startRealTimeIso: string;
  startGameTimeSec: number;
  sharedStartNodeId: NodeId;
  runnerPlayerId: string;
  hunterPlayerId: string;
};
```

## 3. Runtime Match State

### Position Carrier

Player position must always be represented by exactly one carrier.

```ts
type PositionCarrier =
  | {
      kind: "NODE";
      nodeId: NodeId;
    }
  | {
      kind: "TRAIN";
      tripId: TripId;
      segmentId: TripSegmentId;
    }
  | {
      kind: "WALK_EDGE";
      walkEdgeId: WalkEdgeId;
      direction: "forward" | "reverse";
      progress01: number;
    };
```

### PlayerPlan

Represents the private route plan entered during a planning pause.

```ts
type PlayerPlan = {
  version: number;
  createdAtGameTimeSec: number;
  steps: PlanStep[];
};

type PlanStep =
  | {
      kind: "BOARD_TRIP";
      tripId: TripId;
      boardNodeId: NodeId;
    }
  | {
      kind: "RIDE_TO_NODE";
      tripId: TripId;
      exitNodeId: NodeId;
    }
  | {
      kind: "WALK_TO_NODE";
      walkEdgeId: WalkEdgeId;
      targetNodeId: NodeId;
    }
  | {
      kind: "WAIT_AT_NODE";
      nodeId: NodeId;
      untilGameTimeSec?: number;
    };
```

Notes:

- Plans are replaceable at later pauses.
- `steps` are future intent, not guaranteed outcomes.
- The server validates each step against current runtime state.

### PlayerRuntimeState

```ts
type Side = "runner" | "hunter";

type PlayerRuntimeState = {
  playerId: string;
  side: Side;
  carrier: PositionCarrier;
  activePlan: PlayerPlan | null;
  lastRevealSeenAtGameTimeSec: number | null;
  lastRevealReceived: RevealSnapshot | null;
};
```

### Match Phase

```ts
type MatchPhase =
  | "runner_head_start"
  | "real_time"
  | "planning_pause"
  | "resolved";
```

### Reveal Snapshot

Represents the one-time information payload shown to a player.

```ts
type RevealSnapshot =
  | {
      kind: "NODE";
      nodeId: NodeId;
    }
  | {
      kind: "TRAIN_SEGMENT";
      fromNodeId: NodeId;
      toNodeId: NodeId;
    }
  | {
      kind: "LAST_DEPARTED_NODE";
      nodeId: NodeId;
    };
```

### Capture Event

```ts
type CaptureEvent = {
  gameTimeSec: number;
  reason: "same_node" | "same_trip" | "same_walk_edge";
  nodeId?: NodeId;
  tripId?: TripId;
  walkEdgeId?: WalkEdgeId;
};
```

### MatchRuntimeState

```ts
type MatchRuntimeState = {
  matchId: string;
  config: MatchConfig;
  phase: MatchPhase;
  gameTimeSec: number;
  realTimeStartedAtIso: string;
  nextPauseAtGameTimeSec: number;
  nextRevealAtGameTimeSec: number;
  runnerState: PlayerRuntimeState;
  hunterState: PlayerRuntimeState;
  winner: Side | null;
  captureEvent: CaptureEvent | null;
};
```

## 4. Event Model

To keep the simulation deterministic, runtime progression should be driven by scheduled events.

### MatchEvent

```ts
type MatchEvent =
  | {
      kind: "TRAIN_ARRIVAL";
      gameTimeSec: number;
      tripId: TripId;
      nodeId: NodeId;
    }
  | {
      kind: "TRAIN_DEPARTURE";
      gameTimeSec: number;
      tripId: TripId;
      nodeId: NodeId;
    }
  | {
      kind: "WALK_COMPLETE";
      gameTimeSec: number;
      playerId: string;
      walkEdgeId: WalkEdgeId;
      arriveNodeId: NodeId;
    }
  | {
      kind: "PAUSE_START";
      gameTimeSec: number;
    }
  | {
      kind: "PAUSE_END";
      gameTimeSec: number;
    }
  | {
      kind: "REVEAL";
      gameTimeSec: number;
    }
  | {
      kind: "CAPTURE";
      gameTimeSec: number;
    }
  | {
      kind: "TIME_LIMIT_REACHED";
      gameTimeSec: number;
    };
```

## 5. Minimal Capture Logic Mapping

The current rules map cleanly to the carrier model:

- Same node capture:
  - both `carrier.kind === "NODE"`
  - both have the same `nodeId`
- Same trip capture:
  - both `carrier.kind === "TRAIN"`
  - both have the same `tripId`
- Same walk edge capture:
  - both `carrier.kind === "WALK_EDGE"`
  - both have the same `walkEdgeId`

This is the main reason the carrier model should stay strict.

## 6. Minimal Reveal Logic Mapping

- If target is in `NODE`, reveal exact `nodeId`
- If target is in `TRAIN`, reveal `fromNodeId -> toNodeId` of the current segment
- If target is in `WALK_EDGE`, reveal the last departed node

## 7. Recommended Prototype Scope

For the first prototype, do not implement the full Tokyo network yet.

Start with:

- 8 to 20 gameplay nodes
- 2 to 4 rail corridors
- 1 to 3 important walk edges
- 1 weekday timetable bundle
- 1 fixed opening node
- 1 match mode

This is enough to validate:

- Trip boarding
- Automatic route execution
- Periodic pause planning
- Reveals
- Capture resolution

## 8. Open Questions For Next Step

These are schema-level questions that should be answered next:

1. Should `Node` keep one display name or support multilingual names from day one?
2. Should `TripStopTime` point directly to `NodeId`, or should we keep raw stop granularity separately and derive node-level stop times in preprocessing?
3. How should we validate a `PlayerPlan` when the player's current state no longer matches the plan assumptions?
4. Do we need a persisted event log as a first-class data structure in v0.1 of the prototype?
5. Which small Tokyo subnetwork should be used as the first test map?
