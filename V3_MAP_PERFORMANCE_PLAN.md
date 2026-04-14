# V3 Map Performance Plan

## Goal

Bring the `v3` Tokyo map from "reasonably optimized SVG app" to a map architecture that can approach the interaction feel of a modern production map product.

The target is not perfect parity with Google Maps internals, but these user-facing outcomes:

- drag feels immediate
- wheel zoom feels continuous
- low zoom stays clean
- high zoom reveals detail without blocking
- the map becomes clear again within a short moment after movement stops

## Current State

Today `v3` already has:

- real station positions
- real line geometry
- multiscale label rules
- cached projected paths
- cached marker and label visibility by zoom bucket
- delayed refine rendering after wheel interaction

This is enough for a prototype, but not enough for Tokyo-scale rail rendering with Google-Maps-like feel.

The current bottlenecks are:

- SVG/DOM redraw cost is still too high
- labels still depend on runtime collision logic
- all visible geometry is still built in one page context
- low zoom and high zoom still share too much of the same render path

## Principles

- Real station positions must remain real
- Real line geometry must remain real
- We solve clutter with representation, not fake coordinates
- Single-player and multiplayer gameplay parity remains unrelated but untouched

## Phase 1: Stabilize Current SVG Map

This phase improves the current `v3` page without changing the stack.

### 1. Zoom-tier render layers

Split the map into explicit render tiers:

- Tier A: overview
  - only Shinkansen trunks
  - only top hubs
  - no ordinary station dots
- Tier B: metro overview
  - major JR / private / metro trunks
  - hub labels only
- Tier C: local detail
  - most stations and labels
- Tier D: close detail
  - dense station markers
  - service-family emphasis

This removes the need to compute everything for every zoom level.

### 2. Precomputed label candidates

For every station, precompute:

- label anchor candidates
- label rank
- low/mid/high zoom visibility eligibility
- shinkansen / hub / interchange flags

Then at runtime:

- choose from a small prepared set
- avoid expensive full collision work on every interaction

### 3. Geometry buckets

Pre-split current geometry into:

- low zoom merged trunks
- medium zoom route paths
- high zoom detailed physical lines

This is still SVG, but it reduces visual complexity per frame.

## Phase 2: Move To Tile-Based Rendering

This is the first phase that can realistically move us toward Google-Maps-like responsiveness.

### 1. Vector tile pipeline

Build proper multiscale vector tiles for:

- physical lines
- service-family overlays
- station candidates
- label candidates

Recommended output:

- PMTiles or static tile pyramid

### 2. Separate tile layers

Use independent tile layers for:

- overview trunks
- detailed rail geometry
- stations
- labels
- service overlays

Then the client only loads what the current viewport and zoom need.

### 3. Stop full-page geometry rebuilds

The browser should not rebuild all visible geometry on each interaction.

Instead:

- viewport motion should only move existing rendered tiles
- new tiles load incrementally
- refinement happens tile-by-tile

## Phase 3: Upgrade Rendering Stack

To get truly modern interaction, we should stop treating `v3` as a hand-rendered SVG app.

Recommended target:

- MapLibre GL JS
- vector tiles
- PMTiles for delivery

Why:

- GPU-backed rendering
- better scaling with large geometry counts
- more natural zoom behavior
- built-in symbol placement capabilities we can guide with our data

SVG can remain useful for:

- debug overlays
- export graphics
- special planning or replay overlays

But not as the long-term primary renderer for full Tokyo rail.

## Phase 4: Runtime Strategy

At runtime, the map should behave like this:

### Drag

- move instantly using current tiles/layers
- do not rerun full collision work while pointer is moving

### Wheel Zoom

- transform immediately
- request appropriate tile level
- refine shortly after movement settles

### Idle

- swap from coarse layer to finer layer
- update station and label visibility
- update service overlays

This is the map equivalent of progressive rendering.

## Data Work Required

To support this architecture, we need to produce:

- `track_centerline_low`
- `track_centerline_mid`
- `track_centerline_high`
- `station_candidates`
- `label_candidates`
- `service_overlay_segments`
- per-feature:
  - operator
  - line kind
  - zoom eligibility
  - label rank
  - station group / physical station linkage

## Recommended Order

### Step 1

Finish SVG-side zoom tiers and precomputed candidates.

### Step 2

Generate low/mid/high prebuilt map layers from current Tokyo rail geometry.

### Step 3

Build a static vector-tile or PMTiles prototype for the same Tokyo scope.

### Step 4

Render the same Tokyo map in a dedicated MapLibre page and compare responsiveness.

### Step 5

Migrate `v3` from SVG-first to tile-first once parity is acceptable.

## Immediate Next Task

The most practical next implementation step is:

**Build low/mid/high precomputed Tokyo rail geometry layers from the current real geometry dataset.**

That gives us the first meaningful performance jump without forcing an immediate renderer rewrite.
