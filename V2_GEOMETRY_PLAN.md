# V2 GEOMETRY PLAN

## Purpose

This document defines the implementation plan for `Plan A` for `v2`.

The key decision is:

- do not keep hand-drawing the full Shinkansen map as the main source of truth
- use real station coordinates and real route order as the base
- generate the map from data
- only then do limited visual cleanup

## Why We Need This

The current hand-edited `v2` SVG helped us discover strategic structure, but it is not stable enough to be the long-term map basis.

If we continue to hand-place the entire nationwide map:

- branch points will keep drifting
- overlapping lines will keep reappearing
- one correction will often break another section
- later gameplay integration will be harder because the map has no reusable geometry layer

So the rule for `v2` becomes:

`real geometry first, visual polish second`

## Core Pipeline

1. Define the station dataset
2. Define the route-order dataset
3. Build a geometry bundle
4. Render SVG from geometry
5. Apply limited cleanup only where needed

## Data We Need

### Station Dataset

Each station should contain:

```ts
type ShinkansenStation = {
  id: string;
  name: string;
  names: {
    en: string;
    ja: string;
    zh_hans: string;
  };
  lat: number;
  lon: number;
  category: "normal" | "hub";
  lines: string[];
};
```

### Route Dataset

Each line should contain:

```ts
type ShinkansenRoute = {
  id: string;
  name: string;
  color: string;
  stationIds: string[];
};
```

Notes:

- this is route geometry order, not timetable data
- branch correctness depends on these station sequences being right

## Geometry Layer

The `v2` map should move toward the same long-term direction already hinted in `SCHEMA.md`.

```ts
type MapGeometryBundle = {
  version: string;
  projectionHint: "wgs84";
  nodes: {
    nodeId: string;
    lat: number;
    lon: number;
  }[];
  routes: {
    routeId: string;
    polylineNodeIds: string[];
  }[];
};
```

For the first pass, route geometry can simply connect stations in order.

## Rendering Strategy

The renderer should:

1. load station and route data
2. project lat/lon to 2D canvas space
3. draw route lines
4. draw stations
5. place labels with simple offsets

The first generated map does not need to be beautiful.
It needs to be structurally correct.

## Allowed Cleanup

Allowed:

- label offsets
- hub marker scaling
- slight bend-point additions
- overlap reduction for labels

Not allowed:

- moving branch origins away from real split points
- redrawing entire lines by hand until they no longer follow real geography
- replacing geometry logic with pure illustration

## First Implementation Steps

### Step 1

Create:

- `data/shinkansen_v2_stations.json`
- `data/shinkansen_v2_routes.json`

### Step 2

Create:

- `scripts/dev/render_shinkansen_v2_from_geometry.py`

Output:

- `visuals/shinkansen_v2_map_real_geometry.svg`

### Step 3

Compare the geometry-rendered map against the current hand-drawn draft only to find:

- missing stations
- wrong station order
- wrong branch points
- bad label collisions

### Step 4

Once the geometry-driven map is trustworthy, the hand-drawn SVG should stop being the primary source of truth.

## Scope For The First Geometry Pass

The first pass only needs:

- currently open Shinkansen lines
- real open stations
- real route order
- real coordinates

It does not need:

- coastline background
- prefecture overlays
- non-Shinkansen rail
- perfect engineering alignment

## Decision

`Plan A` is now the chosen direction for `v2`.

That means:

- the current hand-edited SVG is only a temporary draft
- the future `v2` map should come from geometry data
- route correctness must come from datasets, not from repeated freehand correction
