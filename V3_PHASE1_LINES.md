# V3 PHASE 1 LINES

## Purpose

This document lists the concrete line families that should enter `v3 phase 1`.

The rule is:

- if a line enters scope, it enters as a whole line
- we do not include arbitrary chopped fragments as if they were whole lines

This is a scope file, not a data-completeness claim.
Some lines may take longer to ingest, but the intended phase-1 line set should already be explicit.

## Included In V3 Phase 1

Each line should be read together with its operator / system tag.

## JR / Shinkansen

### Shinkansen

- `Shinkansen / JR Central` - Tokaido Shinkansen
- `Shinkansen / JR East` - Tohoku Shinkansen
- `Shinkansen / JR Hokkaido` - Hokkaido Shinkansen
- `Shinkansen / JR East` - Joetsu Shinkansen
- `Shinkansen / JR East + JR West` - Hokuriku Shinkansen
- `Shinkansen / JR East` - Yamagata Shinkansen
- `Shinkansen / JR East` - Akita Shinkansen

Reason:

- the current `v2` foundation already depends on nationwide real Shinkansen data
- these lines are the intercity backbone entering and leaving the Tokyo core
- removing any of them would make the enlarged Tokyo-area map structurally misleading

### JR East Conventional Rail

- `JR East` - Yamanote Line
- `JR East` - Keihin-Tohoku Line
- `JR East` - Chuo Line (Rapid)
- `JR East` - Chuo-Sobu Line (local through the Tokyo core)
- `JR East` - Sobu Rapid Line
- `JR East` - Yokosuka Line
- `JR East + JR Central` - Tokaido Line
- `JR East` - Ueno-Tokyo Line
- `JR East` - Saikyo Line
- `JR East` - Shonan-Shinjuku Line
- `JR East` - Joban Line (Rapid)
- `JR East` - Joban Line (Local)
- `JR East` - Keiyo Line

Reason:

- together these lines define the first meaningful JR Tokyo-core rail structure
- they connect the biggest transfer hubs that matter for future gameplay
- they also create the first realistic overlap between intercity access and dense commuter play

## Private Rail

### Tokyu

- `Tokyu` - Toyoko Line
- `Tokyu` - Den-en-toshi Line

### Odakyu

- `Odakyu` - Odawara Line

### Keio

- `Keio` - Keio Line
- `Keio` - Keio New Line

### Keikyu

- `Keikyu` - Main Line

### Tobu

- `Tobu` - Tojo Line
- `Tobu` - Isesaki Line (Tokyo Skytree / Asakusa side trunk)

### Seibu

- `Seibu` - Ikebukuro Line
- `Seibu` - Shinjuku Line

### Keisei

- `Keisei` - Main Line

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
- every included line should carry an explicit operator/system tag in planning and ingestion discussions

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
