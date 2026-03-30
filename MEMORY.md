## Long-Term Memory

## Identity And Collaboration

- User name: Scorp
- Assistant name: Anon
- Conversation language with user: Chinese
- Working language for code, docs, papers, and records: English
- Collaboration focus: game design and game development

## Workflow System

- Canonical workflow rules live in `AXIOMS.md`
- Session handoff status lives in `STATUS.md`
- Stable historical milestones live in `HISTORY.md`
- Raw daily session logging lives in `memory/MEMORY-YYYY-MM-DD.md`
- Curated continuity across sessions belongs in this file, `MEMORY.md`

## Stable Project Rules

- Always read `STATUS.md` before starting work
- Always update `STATUS.md` before ending work
- Daily memory entries use full timestamps
- Stable project rules must be written into `AXIOMS.md`, not left only in chat
- If a rule should change, ask Scorp first
- Never edit an existing rule document in place; create a new versioned rule file instead
- Scripts should target the real game architecture and real production data flow, not throwaway test-map logic

## Current Game Direction

- The active gameplay rule baseline is `rule/RULES_v0.5.md`
- The current implementation direction is a Japanese public transit chase game
- The main technical test map is now the real JR Yamanote Line
- The project no longer uses the coarse `Candidate B` test-map branch

## Current Technical Baseline

- `SCHEMA.md` defines the first implementation-oriented data model
- `STATE_MACHINE.md` defines the first minimal match state machine
- `YAMANOTE_IMPLEMENTATION_PLAN.md` defines the real-data implementation plan for the Yamanote Line

## Current Data Direction

- `data/yamanote_stations.json` is the first real-data foundation file
- The Yamanote dataset currently stores 30 real stations
- Each station should carry English, Japanese, and Chinese names
- The next major data goal is a real train-instance timetable layer sourced from JR East official timetable pages

## Current Visualization Direction

- `visuals/yamanote_line.svg` is the current line overview visualization
- Visuals should support gameplay thinking, not just look decorative

## Important Context For Future Sessions

- The map is considered the hardest and most important part of the game
- Real train choice matters, so timetable realism is not optional in the long-term direction
- The current implementation phase is still data-layer-first, not UI-first
