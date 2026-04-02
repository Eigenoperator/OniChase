# ENGINE ARCHITECTURE

## Purpose

This document defines the engine boundary strategy for OniChase.

The goal is:

- keep the current implementation fast to iterate
- keep the runtime model clear
- avoid coupling the frontend directly to Python internals
- preserve a clean migration path if a future high-performance core is written in Rust

This is not a gameplay rule document.

## Core Principle

Do not optimize too early by changing language first.

Instead:

1. keep data schema independent
2. keep rules independent
3. keep simulation input/output independent
4. make the frontend talk to the engine only through JSON contracts

If these boundaries stay clean, the engine core can later move from Python to Rust without forcing a full rewrite of the planner client, data files, or match definitions.

## Target Layer Split

The project should be treated as five layers:

1. Data layer
2. Rule layer
3. Engine layer
4. Interface layer
5. Frontend layer

Each layer should have a different responsibility.

## 1. Data Layer

This layer defines what the world is.

Examples:

- stations / nodes
- routes
- train instances
- stop-times
- walk edges
- service calendars

This layer must remain:

- static
- versioned
- engine-agnostic
- frontend-agnostic

Recommended rule:

- the same dataset JSON should be loadable by Python tools, Rust tools, and frontend viewers without changing its meaning

Current related files:

- [SCHEMA.md](/home/xincheng/toy/Chase/SCHEMA.md)
- [data/yamanote_stations.json](/home/xincheng/toy/Chase/data/yamanote_stations.json)
- [data/yamanote_weekday_train_instances_merged.json](/home/xincheng/toy/Chase/data/yamanote_weekday_train_instances_merged.json)

## 2. Rule Layer

This layer defines what the game means.

Examples:

- legal player carriers
- planning pause behavior
- reveal timing
- capture rules
- same-minute boundary rulings

This layer must not be hidden inside implementation details.

Recommended rule:

- game rules live in versioned rule documents first
- engine code only implements already-confirmed rule documents

This is important because a future Rust core should implement the same rule set, not a different one rediscovered from Python code.

Current related files:

- [rule/RULES_v0.5.md](/home/xincheng/toy/Chase/rule/RULES_v0.5.md)
- [rule/RULES_v0.6.md](/home/xincheng/toy/Chase/rule/RULES_v0.6.md)
- [STATE_MACHINE.md](/home/xincheng/toy/Chase/STATE_MACHINE.md)

## 3. Engine Layer

This layer defines how the rules are executed over data.

Examples:

- plan resolution
- event generation
- time advancement
- occupancy state transitions
- capture checks
- match result construction

This is the layer that may start in Python and later gain Rust replacements.

Recommended split inside the engine:

- `resolver`
  - expands planning steps into executable actions
- `simulator`
  - advances state through time and emits events
- `adjudicator`
  - decides capture / victory / boundary outcomes
- `validator`
  - checks scenario shape and dataset consistency

Important constraint:

- engine code should consume structured JSON-like input and return structured JSON-like output
- engine code should not depend on browser DOM, HTML state, or frontend-specific objects

Current related files:

- [scripts/engine/simulate_match_from_train_instances.py](/home/xincheng/toy/Chase/scripts/engine/simulate_match_from_train_instances.py)
- [scripts/ingest/validate_train_instances_dataset.py](/home/xincheng/toy/Chase/scripts/ingest/validate_train_instances_dataset.py)

## 4. Interface Layer

This layer is the contract between tools and the engine.

Examples:

- scenario JSON
- planning JSON
- result JSON
- replay event log JSON

This layer is the most important migration boundary.

If the interface is stable:

- Python can run the engine today
- Rust can run the same scenario tomorrow
- the frontend does not need to care which runtime produced the result

Recommended interface rule:

- treat engine input/output files as product contracts, not temporary debug blobs

Current interface documents:

- [SIMULATION_INPUT.md](/home/xincheng/toy/Chase/SIMULATION_INPUT.md)
- [PLANNING_FORMAT.md](/home/xincheng/toy/Chase/PLANNING_FORMAT.md)

Recommended future documents:

- `RESULT_SCHEMA.md`
- `REPLAY_SCHEMA.md`
- `DATASET_SCHEMA.md`

## 5. Frontend Layer

This layer defines what the player sees and edits.

Examples:

- map rendering
- plan editing
- current time HUD
- upcoming stops panel
- route trace visualization
- replay timeline

The frontend should not contain authoritative game rules.

The frontend may:

- prepare scenario JSON
- display planner hints
- render engine results
- submit plan edits

The frontend should not:

- become the only source of rule truth
- encode hidden special-case capture logic that the engine does not share

Current related files:

- [ui/planner.html](/home/xincheng/toy/Chase/ui/planner.html)
- [PLANNER_GUI.md](/home/xincheng/toy/Chase/PLANNER_GUI.md)

## Recommended JSON Boundaries

### A. Dataset Boundary

Input:

- static map / timetable JSON

Must answer:

- what stations exist
- what train instances exist
- when each train reaches each stop

Must not answer:

- who wins
- whether a player captures another player

### B. Scenario Boundary

Input:

- start time
- end time
- player start states
- player actions or planning steps

Must be fully serializable to JSON and stored independently of runtime code.

### C. Result Boundary

Output:

- resolved actions
- match event log
- final states
- first capture if present

Recommended property:

- replay should be renderable from result JSON alone

## What Stays Safe To Keep In Python

Python is still a very good fit for:

- data cleaning
- timetable extraction
- schema validation
- rapid engine iteration
- rule experiments
- offline bulk simulation
- balance tooling

This means the current Python choice is not a dead end.

## What Might Later Move To Rust

If performance becomes a real issue, these are the best candidates for migration:

- bulk path search
- candidate-plan expansion at scale
- large Monte Carlo simulation batches
- authoritative online match execution
- replay generation for many simultaneous matches

Recommended migration order:

1. keep Python as reference engine
2. identify hotspots with measurement
3. reimplement only the hotspot module in Rust
4. keep the same input/output JSON contract

This avoids rewriting everything at once.

## Anti-Patterns To Avoid

- Do not let the planner frontend become the rule engine.
- Do not hide official rule decisions only in Python code comments.
- Do not make dataset files depend on one implementation language.
- Do not return ad-hoc result objects that only one script understands.
- Do not mix raw extracted transit data and gameplay-normalized data without a documented boundary.

## Practical Near-Term Plan

The near-term architecture should be:

1. Keep authoritative simulation in Python.
2. Keep planner frontend speaking JSON only.
3. Strengthen the result schema and replay schema.
4. Add one execution bridge from the frontend to the local Python simulator.
5. Only consider a Rust core after real profiling shows Python is the bottleneck.

## Immediate Implementation Guidance

When adding new features:

- first decide whether it belongs to data, rules, engine, interface, or frontend
- write or update the schema/doc contract before hiding it in code
- prefer JSON files and documented structs over implicit shared state
- keep engine outputs deterministic and replay-friendly

If this discipline holds, OniChase can grow from a Python prototype into a multi-language production architecture without wasting current work.
