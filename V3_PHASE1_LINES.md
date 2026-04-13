# V3 PHASE 1 LINES

## Purpose

This document lists the concrete line families that should enter `v3 phase 1`.

The rule is:

- if a line enters scope, it enters as a whole line
- we do not include arbitrary chopped fragments as if they were whole lines

This is a scope file, not a data-completeness claim.
Some lines may take longer to ingest, but the intended phase-1 line set should already be explicit.

## Included In V3 Phase 1

## JR / Shinkansen

### Shinkansen

- Tokaido Shinkansen
- Tohoku Shinkansen
- Hokkaido Shinkansen
- Joetsu Shinkansen
- Hokuriku Shinkansen
- Yamagata Shinkansen
- Akita Shinkansen

Reason:

- the current `v2` foundation already depends on nationwide real Shinkansen data
- these lines are the intercity backbone entering and leaving the Tokyo core
- removing any of them would make the enlarged Tokyo-area map structurally misleading

### JR East Conventional Rail

- Yamanote Line
- Keihin-Tohoku Line
- Chuo Line (Rapid)
- Chuo-Sobu Line (local through the Tokyo core)
- Sobu Rapid Line
- Yokosuka Line
- Tokaido Line
- Ueno-Tokyo Line
- Saikyo Line
- Shonan-Shinjuku Line
- Joban Line (Rapid)
- Joban Line (Local)
- Keiyo Line

Reason:

- together these lines define the first meaningful JR Tokyo-core rail structure
- they connect the biggest transfer hubs that matter for future gameplay
- they also create the first realistic overlap between intercity access and dense commuter play

## Private Rail

### Tokyu

- Toyoko Line
- Den-en-toshi Line

### Odakyu

- Odawara Line

### Keio

- Keio Line
- Keio New Line

### Keikyu

- Main Line

### Tobu

- Tojo Line
- Isesaki Line (Tokyo Skytree / Asakusa side trunk)

### Seibu

- Ikebukuro Line
- Shinjuku Line

### Keisei

- Main Line

Reason:

- these are the first private-rail trunks that materially affect the Tokyo core and major transfer strategy
- phase 1 should show that OniChase can move beyond JR-only logic without immediately requiring every suburban branch in Kanto

## Explicitly Deferred From Phase 1

### Tokyo Metro

- all Tokyo Metro lines are deferred from phase 1

### Toei

- all Toei lines are deferred from phase 1

### Other Private Railways

- Keisei branch families beyond the main trunk
- Tobu branch families beyond the main trunks
- Seibu branch families beyond the main trunks
- other suburban operators not yet central to the first Tokyo-core pilot

### Other JR Lines

- very remote branch lines that do not materially change the first Tokyo-core transfer picture

## Why Metro Is Deferred

Phase 1 already becomes much larger than `v2` once we add:

- the full Shinkansen backbone
- the core JR Tokyo network
- the first major private-rail trunks

Adding all subway lines at the same time would dramatically increase:

- station density
- interchange complexity
- data-ingestion surface area
- rendering and performance difficulty

So phase 1 should prove the enlarged real-position rail map before going one layer denser.

## Operational Meaning

This line list means:

- map scope should include these whole lines
- geometry scope should include these whole lines
- service-data planning should assume these whole lines are eventual targets

It does **not** mean:

- all lines must be fully ingested on day one
- gameplay on all lines must be enabled immediately

## Immediate Build Order Inside The Included Set

1. Nationwide Shinkansen lines already proven in `v2`
2. Yamanote / Keihin-Tohoku / Chuo / Sobu / Yokosuka / Tokaido JR core
3. First private-rail trunks
4. Remaining included JR conventional lines

## Definition Of Done For This File

This file is done when:

- every line in `v3 phase 1` is either explicitly included or explicitly deferred
- no line is represented as an arbitrary half-line scope shortcut
