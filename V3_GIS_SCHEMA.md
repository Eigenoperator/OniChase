# V3 GIS SCHEMA

## Purpose

This document defines the first OniChase-specific canonical schema for `v3`.

It is not a raw-source schema.
It is the internal normalized model that should sit between:

- external geometry sources such as `N02`
- external service sources such as `GTFS`
- OniChase game abstractions and presentation layers

## Design Principles

- Separate physical place from service operation.
- Separate grouped station complexes from raw stop objects.
- Keep geometry and timetable joinable.
- Keep the schema stable enough that both Python and future Rust tools can load it.
- Allow multiple presentation representations at different zoom levels.

## Canonical Layers

1. Physical station layer
2. Station-group layer
3. Track / corridor layer
4. Service layer
5. Presentation layer
6. Game abstraction layer

## 1. Physical Station

Represents one physical station object as it exists in source geometry.

```ts
type PhysicalStationId = string;

type PhysicalStation = {
  id: PhysicalStationId;
  name: string;
  names: {
    en?: string;
    ja?: string;
    zh_hans?: string;
  };
  operatorIds: string[];
  lat: number;
  lon: number;
  sourceStopIds: string[];
  stationGroupId: string;
  tags: string[];
};
```

## 2. Station Group

Represents a grouped station complex suitable for game and UI use.

Examples:

- one simple station
- a multi-operator transfer hub
- nearby same-name entrances grouped as one complex

```ts
type StationGroupId = string;

type StationGroup = {
  id: StationGroupId;
  primaryName: string;
  names: {
    en?: string;
    ja?: string;
    zh_hans?: string;
  };
  physicalStationIds: PhysicalStationId[];
  centroid: {
    lat: number;
    lon: number;
  };
  category: "normal" | "hub" | "mega_hub";
  labelRank: number;
  tags: string[];
};
```

## 3. Track Centerline

Represents physical railway corridor geometry.

```ts
type TrackCenterlineId = string;

type TrackCenterline = {
  id: TrackCenterlineId;
  operatorId: string;
  lineName: string;
  mode: "rail" | "subway" | "shinkansen" | "private_rail";
  polyline: {
    lat: number;
    lon: number;
  }[];
  stationGroupIds: StationGroupId[];
  tags: string[];
};
```

This is a physical layer object, not a player-facing route.

## 4. Pathway

Represents within-station or between-station-group traversal links.

```ts
type PathwayId = string;

type Pathway = {
  id: PathwayId;
  fromStationGroupId: StationGroupId;
  toStationGroupId: StationGroupId;
  durationSec: number;
  bidirectional: boolean;
  kind: "in_station" | "surface_transfer" | "gate_transfer";
  tags: string[];
};
```

This is where future high-detail interchange complexity can live without polluting the rule layer.

## 5. Service Route

Represents a named service family or display route.

```ts
type ServiceRouteId = string;

type ServiceRoute = {
  id: ServiceRouteId;
  operatorId: string;
  shortName: string;
  longName: string;
  color?: string;
  textColor?: string;
  mode: "rail" | "subway" | "shinkansen" | "private_rail";
};
```

## 6. Service Pattern

Represents one reusable stop pattern before expansion into concrete trip instances.

```ts
type ServicePatternId = string;

type ServicePattern = {
  id: ServicePatternId;
  routeId: ServiceRouteId;
  label: string;
  stationGroupIds: StationGroupId[];
  shapeId?: string;
  tags: string[];
};
```

## 7. Trip Instance

Represents one concrete scheduled train.

```ts
type TripInstanceId = string;

type TripInstance = {
  id: TripInstanceId;
  routeId: ServiceRouteId;
  servicePatternId?: ServicePatternId;
  serviceName?: string;
  serviceNumber?: string;
  operatorId?: string;
  directionId?: string;
  stopTimes: TripStopTime[];
};

type TripStopTime = {
  sequence: number;
  stationGroupId: StationGroupId;
  physicalStationId?: PhysicalStationId;
  arrivalTimeSec: number;
  departureTimeSec: number;
  shapeDistTraveled?: number;
};
```

Important:

- `stationGroupId` is the minimum authoritative join for gameplay and UI
- `physicalStationId` is optional but useful later for detailed station logic
- `shapeDistTraveled` is the main bridge to map/timetable synchronization

## 8. Service Geometry

Represents the map geometry used to draw a service.

```ts
type ServiceGeometryId = string;

type ServiceGeometry = {
  id: ServiceGeometryId;
  routeId: ServiceRouteId;
  representation: "corridor" | "service_path" | "detailed_track";
  minZoom: number;
  maxZoom: number;
  polyline: {
    lat: number;
    lon: number;
  }[];
  offsetRank?: number;
};
```

This is not necessarily identical to raw track centerlines.
It is the rendered path representation for one zoom band.

## 9. Label Representation

```ts
type LabelRepresentation = {
  stationGroupId: StationGroupId;
  minZoom: number;
  maxZoom: number;
  labelRank: number;
  displayNameJa?: string;
  displayNameEn?: string;
  labelPoint?: {
    lat: number;
    lon: number;
  };
};
```

This lets us separate:

- where the station physically is
- where the label should be placed
- when the label should appear

## 10. Game Node

`v3` should still have an explicit game-layer node instead of assuming every station group is automatically a gameplay node.

```ts
type GameNodeId = string;

type GameNode = {
  id: GameNodeId;
  stationGroupIds: StationGroupId[];
  primaryStationGroupId: StationGroupId;
  category: "normal" | "hub" | "split_hub";
  revealName: string;
  tags: string[];
};
```

This keeps the game free to:

- split giant hubs
- merge tiny nearby stops
- expose simplified reveal names

## 11. V3 Bundle

```ts
type V3TransitBundle = {
  version: string;
  generatedAt: string;
  physicalStations: PhysicalStation[];
  stationGroups: StationGroup[];
  trackCenterlines: TrackCenterline[];
  pathways: Pathway[];
  serviceRoutes: ServiceRoute[];
  servicePatterns: ServicePattern[];
  tripInstances: TripInstance[];
  serviceGeometry: ServiceGeometry[];
  labelRepresentations: LabelRepresentation[];
  gameNodes: GameNode[];
};
```

## Minimal First Pilot

For the first `v3` pilot, we do not need the whole final schema filled.

Minimum useful subset:

- `physicalStations`
- `stationGroups`
- `trackCenterlines`
- `serviceRoutes`
- `tripInstances`
- one basic `serviceGeometry`
- one basic `labelRepresentations`
- one first-pass `gameNodes`

## Immediate Consequence

`v3` should not begin from a client mock alone.

It should begin by producing the first small `V3TransitBundle` for one Shinkansen pilot slice.
