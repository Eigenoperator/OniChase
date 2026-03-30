# YAMANOTE IMPLEMENTATION PLAN

## Purpose

This document defines the implementation plan for replacing the coarse `Candidate B` prototype map with a real-data Yamanote Line test map.

The new direction is:

- use the real JR Yamanote Line
- use real stations
- use real train-instance timetable data

This is a more valuable testbed because the player must choose behavior against actual scheduled trains, not abstract edges only.

## Core Interpretation

For implementation purposes, "timetable of each car" is interpreted as:

- timetable of each train run / train instance

not:

- per-railcar interior data

The gameplay-critical unit is the individual train service instance that players can board.

Important modeling preference:

- a train instance should not be permanently bound to one line field
- line identity should be recorded per stop-time row
- this keeps future through-services across multiple lines representable as one train object

## Why This Replaces Candidate B

`Candidate B` was useful as a graph prototype, but it abstracts away the most important system:

- real train choice under real timetable constraints

If the player cannot choose from actual train departures and actual station stop sequences, the movement game is still too far from the final design.

So the new first real test map should be:

- the full Yamanote Line

## Scope of the New Test Map

### Included

- all Yamanote Line stations
- real station names
- both directions:
  - inner loop (`内回り`)
  - outer loop (`外回り`)
- weekday timetable first
- train-instance stop-time records

### Excluded for the first Yamanote pass

- other JR lines
- Tokyo Metro / Toei lines
- walking edges
- major-station internal node splitting
- holiday timetable

This keeps the first real-data step manageable.

## Official Data Source Strategy

Primary source:

- JR East official timetable pages

Official timetable entry point:

- `https://timetables.jreast.co.jp/en/`

Relevant official page types:

1. station timetable pages for Yamanote Line stations
2. stop-list / train-detail pages when available
3. station information pages for canonical station naming

## Required Data Model Shift

The current bundle model is graph-first.

For Yamanote real-data simulation, we need a train-first layer:

### Static Station Data

```ts
type Station = {
  id: string;
  code?: string;
  names: {
    en: string;
    ja: string;
    zh_hans: string;
  };
  line_ids: string[];
};
```

### Train Instance

```ts
type TrainInstance = {
  id: string;
  direction: "inner" | "outer";
  service_day: "weekday";
  train_number?: string;
  operator_id?: string;
  service_instance_id?: string;
  stop_times: TrainStopTime[];
};
```

### Train Stop Time

```ts
type TrainStopTime = {
  station_id: string;
  line_id: string;
  loop_pass_index?: number;
  arrival_hhmm?: string;
  departure_hhmm: string;
  platform?: string;
  sequence: number;
};
```

Why `line_id` belongs on `TrainStopTime`:

- some future trains may continue across multiple lines
- a single train instance should remain one object even if line branding changes during the run
- the player should choose a concrete train and then observe which line it is on at each stop

Why loop-aware fields are needed on Yamanote:

- the Yamanote Line is a loop
- the same station may appear more than once in one continuous service record
- some trains do not end operation after exactly one loop
- therefore train identity must not be cut by "one lap"
- stop-time identity must use `sequence` and optionally `loop_pass_index`, not just `station_id`

### Yamanote Bundle

```ts
type YamanoteBundle = {
  id: string;
  version: string;
  line: {
    id: "JR_YAMANOTE";
    color: string;
    names: {
      en: string;
      ja: string;
      zh_hans: string;
    };
  };
  stations: Station[];
  train_instances: TrainInstance[];
};
```

## Implementation Phases

## Phase 1: Real Yamanote Station Backbone

Goal:

- create the canonical station list for the whole Yamanote Line

Tasks:

- define all real Yamanote stations in order
- assign English, Japanese, and Chinese names
- store official line color

Output:

- `data/yamanote_stations.json`

## Phase 2: Official Timetable Capture Strategy

Goal:

- decide the exact extraction path from JR East official pages

Tasks:

- identify one direction-specific station timetable page structure
- identify how to map departures into train instances
- identify whether a train-detail page exists for each run

Main risk:

- station timetable pages show departures per station, but full train-instance reconstruction may require joining information across multiple official pages

Output:

- `YAMANOTE_TIMETABLE_EXTRACTION.md`

## Phase 3: Train-Instance Database

Goal:

- create the first real train-instance dataset for weekday Yamanote service

Tasks:

- ingest official times
- reconstruct each train run in stop sequence order
- preserve repeated stations when the same train continues past one full loop
- store one record per train instance

Output:

- `data/yamanote_weekday_train_instances.json`

## Phase 4: Simulation Core Refactor

Goal:

- replace edge-only movement with real departure choice

Tasks:

- let players choose among future departures at a station
- move by train instance, not abstract edge only
- support staying on a train across multiple stops
- support getting off at any served stop

Output:

- updated simulator capable of:
  - station waiting
  - boarding a specific train instance
  - riding until chosen alighting station
  - same-train capture checks

## Phase 5: First Yamanote Test Match

Goal:

- run a full simplified match on the real Yamanote line

Tasks:

- select starting station
- select starting time
- execute scripted runner and hunter plans
- verify movement and capture outcomes against timetable reality

## Code Plan

## Data Files

- `data/yamanote_stations.json`
- `data/yamanote_weekday_train_instances.json`
- `data/yamanote_bundle.json`

## Scripts

- `scripts/validate_station_dataset.py`
- `scripts/build_jreast_train_instances_from_station_timetable.py`
- `scripts/parse_jreast_train_detail.py`

## Suggested Build Order

1. station list
2. station validator
3. timetable extraction plan
4. train-instance builder
5. train-instance validator
6. real-data simulator

## Immediate Next Step

The next concrete step should be:

- build `data/yamanote_stations.json`

This is the smallest correct foundation for the new real-data direction.
