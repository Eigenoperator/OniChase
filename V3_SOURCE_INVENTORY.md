# V3 SOURCE INVENTORY

## Purpose

This document defines the first concrete source plan for `v3 phase 1`.

It answers:

- where real line geometry should come from
- where real station information should come from
- where real service / timetable information should come from
- what fields we need for each station before gameplay is attached

This is an execution inventory, not a final completeness claim.

Current machine-readable output generated from this source plan:

- `data/v3_tokyo_timetable_source_registry.json`

Recent collected batches already produced from this source plan:

- `data/v3_tokyo_jreast_core_weekday_train_instances.json`
- `data/v3_tokyo_toei_weekday_train_instances.json`
- `data/v3_tokyo_rinkai_weekday_train_instances.json`
- `data/v3_tokyo_yurikamome_weekday_train_instances.json`

## Phase 1 Rule

`v3 phase 1` is still about two things first:

1. draw the larger real map
2. collect the real train data

Gameplay can come later.

## Canonical Station Principle

For `v3`, we must not treat every interchange as one fake merged map point.

We should collect two linked objects:

- `physical_station`
- `station_group`

Meaning:

- `physical_station` stores one real station location for one operator / one physical station object
- `station_group` stores the transfer-capable logical grouping used by gameplay and UI

Example:

- `JR Shinjuku`
- `Odakyu Shinjuku`
- `Keio Shinjuku`

may belong to one `station_group`, but they must stay as distinct `physical_station` records with their own real coordinates.

## What We Need For Each Physical Station

Every `physical_station` should try to collect at least:

- `physical_station_id`
- `station_group_id`
- `name_ja`
- `name_en`
- `operator_id`
- `line_ids`
- `lat`
- `lon`
- `source_geometry_id`
- `source_stop_id`
- `is_interchange_component`
- `label_rank`
- `tags`

Recommended optional fields:

- `station_code`
- `prefecture`
- `ward_or_city`
- `elevation` if available later
- `platform_scope_hint`
- `note_about_transfer_relationship`

## What We Need For Each Station Group

Every `station_group` should try to collect:

- `station_group_id`
- `primary_name_ja`
- `primary_name_en`
- `physical_station_ids`
- `group_centroid_lat`
- `group_centroid_lon`
- `group_type`
- `interchange_kind`
- `operator_ids`
- `line_ids`
- `label_rank`

## Source Types

We need four source types in parallel:

1. physical geometry sources
2. station identity / stop sources
3. timetable / service sources
4. validation sources

## 1. Physical Geometry Sources

### Source A: MLIT N02 Rail Geometry

Current chosen release for Shinkansen real-geometry extraction:

- `N02-24`

Use as the first nationwide geometry baseline for:

- line centerlines
- station points
- operator names
- line names
- station grouping hints

Why it matters:

- real geometry
- nationwide consistency
- strong first baseline for both JR and private rail

Phase-1 usage:

- first-pass `physical_station`
- first-pass `track_centerline`
- first-pass operator / line naming normalization
- first-pass `real route polyline` import into `data/v3_real_geometry_routes.json`

## 2. Station Identity / Stop Sources

### Source B: GTFS / GTFS-like Stop Data

Use where available for:

- stop identifiers
- multilingual names
- route membership
- service-layer stop identity

This is especially useful when:

- one physical station has multiple service-layer stop IDs
- one operator distinguishes platforms or sub-stations
- we need a stronger join between geometry and timetable

### Source C: Official Station Pages

Use as a validation / enrichment source for:

- official English naming
- station codes
- operator-specific station identity
- interchange descriptions

This is especially important for:

- same-name stations across different companies
- major hubs where grouping can easily be over-merged

## 3. Timetable / Service Sources

### Source D: Existing V2 Shinkansen Pipeline

Reuse for:

- nationwide Shinkansen train instances
- real train names
- stop sequences
- stop times

This remains the first guaranteed service-data base in `v3`.

### Source E: Tokyo-Area GTFS / GTFS-RT Feeds

Use where available for:

- routes
- trips
- stop_times
- calendars
- realtime later

This is the preferred source family for Tokyo-area urban rail where feed quality is strong enough.

### Source F: Official Operator Timetable Pages

Fallback or supplement when GTFS is incomplete, missing, or operationally weaker than official pages.

Use for:

- exact train names
- exact stop times
- service pattern validation
- line-specific edge cases

### Source G: Tokyo Metro / Toei / Urban-Rail Official Sources

For the Tokyo-area full urban rail phase, we should explicitly prepare collection paths for:

- Tokyo Metro
- Toei
- Rinkai Line
- Yurikamome
- Tokyo Monorail
- Tama Monorail
- Tsukuba Express
- Toden Arakawa

These systems should be treated as first-class phase-1 sources rather than deferred add-ons.

## 4. Validation Sources

Use a second source whenever possible to validate:

- station names
- operator ownership
- line membership
- interchange grouping
- suspicious coordinates

Typical validation sources:

- official route maps
- official station pages
- already proven `v2` train-instance outputs

## Phase-1 Operator Source Plan

## Shinkansen

### `Shinkansen / JR Central`

Geometry:

- `N02` baseline geometry

Service:

- existing `v2` official timetable ingestion

Validation:

- official JR Central station and timetable pages

### `Shinkansen / JR East`

Geometry:

- `N02`

Service:

- existing `v2` JR East Shinkansen ingestion

Validation:

- official JR East timetable / station pages

### `Shinkansen / JR Hokkaido`

Geometry:

- `N02`

Service:

- reused `v2` Shinkansen service bundle

Validation:

- official station / timetable references as needed

## JR East Conventional

### `JR East`

Geometry:

- `N02` for full-line geometry and real station positions

Station identity:

- GTFS or GTFS-like stop data where available
- official station pages for name and grouping validation

Service:

- GTFS first where available
- official timetable pages as fallback

Priority lines:

- Yamanote
- Keihin-Tohoku
- Chuo Rapid
- Chuo-Sobu
- Sobu Rapid
- Yokosuka
- Tokaido
- Ueno-Tokyo
- Saikyo
- Shonan-Shinjuku
- Joban Rapid / Local
- Keiyo

## Private Rail Operators

Because private-rail scope is at the company level, source planning should also happen at the company level.

### `Tokyu`

Geometry:

- `N02`

Station / service:

- GTFS / GTFS-like feed where available
- official route / station pages for validation

### `Odakyu`

Geometry:

- `N02`

Station / service:

- GTFS / GTFS-like feed where available
- official route / station pages for validation

### `Keio`

Geometry:

- `N02`

Station / service:

- GTFS / GTFS-like feed where available
- official route / station pages for validation

### `Keikyu`

Geometry:

- `N02`

Station / service:

- GTFS / GTFS-like feed where available
- official route / station pages for validation

### `Tobu`

Geometry:

- `N02`

Station / service:

- GTFS / GTFS-like feed where available
- official route / station pages for validation

### `Seibu`

Geometry:

- `N02`

Station / service:

- GTFS / GTFS-like feed where available
- official route / station pages for validation

### `Keisei`

Geometry:

- `N02`

Station / service:

- GTFS / GTFS-like feed where available
- official route / station pages for validation

## First Build Order

1. build `physical_station` + `station_group` for all Shinkansen stations already in `v2`
2. build `physical_station` + `station_group` for the first Tokyo-core JR lines
3. validate major interchange groups:
   - Tokyo
   - Shinagawa
   - Ueno
   - Omiya
   - Shinjuku
   - Shibuya
   - Ikebukuro
   - Akihabara
   - Yokohama
4. add the first private-rail company station groups
5. attach service data company by company

## First Geometry Integration Status

The `v3` builder now has a dedicated real-geometry override slot:

- `data/v3_real_geometry_routes.json`

Meaning:

- if a route appears there with a real `polyline`, bundle generation should use that geometry
- if a route is still missing there, bundle generation falls back to the older station-sequence polyline

This lets us upgrade to real geometry incrementally without breaking the existing pipeline.

## Immediate Questions To Resolve

- Which Tokyo-area operators in phase 1 have usable GTFS or GTFS-like service feeds that are good enough for canonical service ingestion?
- Which operators require official timetable-page scraping instead?
- Which interchange groups need multiple `physical_station` objects even when names are almost identical?
- Which line and station names need an early normalization table before geometry and service ingestion can safely merge?

## Definition Of Done For This File

This file is good enough for phase 1 when:

- every included operator has a planned geometry source
- every included operator has a planned service source
- station collection fields are explicit
- `physical_station` versus `station_group` responsibilities are explicit

## Current Concrete Registry

The first machine-readable timetable-source registry for `v3 phase 1` now exists at:

- `data/v3_tokyo_timetable_source_registry.json`

It records, per operator:

- source readiness
- source kind
- official entry URL
- whole-company scope rule
- reusable ingestion scripts where already available
