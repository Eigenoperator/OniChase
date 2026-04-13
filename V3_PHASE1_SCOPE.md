# V3 PHASE 1 SCOPE

## Purpose

This document defines the concrete scope of the first real `v3` build-out.

`v3 phase 1` does **not** try to make the next fully playable version immediately.
Its job is to establish the larger real-world map and data base that can later carry gameplay.

For now, `v2` remains the playable mainline.

## Phase 1 Goal

Build the first enlarged real-position rail map and service-data base for the future Tokyo-area version.

The two core deliverables are:

1. a larger real-position map
2. a larger real train dataset

## Core Rule

All station positions must stay real.

`v3 phase 1` must not solve density by inventing fake coordinates or manually moving stations away from their real place.
Readability must come from:

- better data structure
- multi-scale rendering
- label rules
- operator/route layering
- performance work

## Geographic Scope

`v3 phase 1` should cover the greater Tokyo approach area instead of only the nationwide Shinkansen network.

### Included Region

The initial geography should include:

- Tokyo Station
- Shinagawa
- Ueno
- Omiya
- Shinjuku
- Shibuya
- Akihabara
- Ikebukuro
- Yokohama / Shin-Yokohama
- Chiba-side approach where needed for JR structure

This is not yet “all of Kanto”.
It is the first operational Tokyo-area rail core plus the Shinkansen approach spine.

## Operator Scope

### Included First

- JR East
- JR Central
- JR East / JR Central Shinkansen approach sections

### Included Selectively In Phase 1

Only the private railways that matter directly for the Tokyo core transfer picture:

- Keikyu
- Keio
- Odakyu
- Tokyu
- Tobu
- Seibu
- Keisei

### Deferred

- full Tokyo Metro detail
- full Toei detail
- every suburban branch and rural continuation
- bus, tram, or non-rail modes

## Line Scope

### JR / Shinkansen Lines That Should Be In Phase 1

- Tokaido Shinkansen Tokyo approach
- Tohoku / Hokuriku / Joetsu Shinkansen Tokyo approach
- Yamanote Line
- Keihin-Tohoku Line
- Chuo rapid core section
- Sobu rapid / Yokosuka corridor through Tokyo
- Ueno-Tokyo approach structure where relevant

### Private Rail Lines That Should Enter Phase 1

Only the trunk segments needed to express real transfer and escape structure near the Tokyo core:

- Keikyu main approach into Shinagawa
- Tokyu Toyoko / Den-en-toshi trunk approach
- Odakyu trunk into Shinjuku
- Keio trunk into Shinjuku
- Tobu trunk into Ikebukuro / Asakusa-side approach as needed
- Seibu trunk into Ikebukuro / Shinjuku-side approach as needed
- Keisei trunk into Ueno / east approach as needed

## Station Scope

### Tier A: Must-Have Major Hubs

- Tokyo
- Shinagawa
- Ueno
- Omiya
- Shinjuku
- Shibuya
- Ikebukuro
- Akihabara
- Yokohama
- Shin-Yokohama

### Tier B: Secondary Structure Stations

Stations that define corridor structure and realistic transfer opportunities, for example:

- Kanda
- Yurakucho
- Hamamatsucho
- Tamachi
- Nippori
- Tabata
- Yoyogi
- Ebisu
- Osaki
- Kawasaki

### Tier C: Feeder / Private-Rail Anchors

Only where needed to make the first Tokyo-area network readable and strategically meaningful.

## Data Scope

## 1. Physical Map Data

Phase 1 must produce a canonical physical rail bundle with:

- real station coordinates
- real line geometry
- operator ownership
- station grouping
- interchange edges

Minimum outputs:

- `physical_stations`
- `station_groups`
- `track_centerlines`
- `pathways` or transfer edges

## 2. Service Data

Phase 1 must collect real service data for the included lines.

Minimum outputs:

- real route family names
- real service names where applicable
- concrete trip instances
- stop sequences
- stop times

For Shinkansen, reuse and extend the current `v2` train-instance pipeline.

For Tokyo-area urban lines, phase 1 may temporarily accept:

- GTFS where available
- official operator timetable pages
- route-level and stop-time level data before full gameplay ingestion

## 3. Rendering Data

Phase 1 must generate map-ready data for multiple zoom levels.

Minimum outputs:

- low-zoom corridor geometry
- mid-zoom service geometry
- station label ranks
- route label ranks
- tile or tile-ready outputs

## Concrete Deliverables

By the end of `v3 phase 1`, we should have:

1. one real-position Tokyo-area rail map that is larger than `v2`
2. one canonical map/data bundle for the Tokyo-area pilot
3. one first service-data bundle for the included lines
4. one multi-scale rendering pass that stays readable without moving stations

## Explicitly Out Of Scope

`v3 phase 1` should **not** yet require:

- full playable runner/hunter gameplay on the entire new network
- full online multiplayer on the expanded Tokyo-area map
- AI opponent work
- final visual polish
- all Kanto lines
- all Tokyo Metro / Toei detail
- full station-internal platform modeling

## Recommended Build Order

1. lock the geographic boundary
2. build the physical station + line bundle
3. build the operator/line inventory
4. attach real train/service data
5. render the first enlarged map
6. only then decide what gameplay subset moves onto it first

## Definition Of Success

`v3 phase 1` is successful if:

- the map is clearly larger than the current Shinkansen-only `v2`
- all displayed station positions remain real
- the first Tokyo-area rail core is structurally correct
- the first service bundle is real enough to support later gameplay integration
- performance and rendering are still controllable
