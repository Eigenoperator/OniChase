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

Under the current project rule, private rail scope should be decided at the company level:

- if we include a private-rail company, we should intend to include that operator's whole rail network
- phase 1 should therefore be very selective about which private-rail companies enter at all

### Private-Rail Companies Proposed For Phase 1

- `Tokyu` - whole Tokyu rail network
- `Odakyu` - whole Odakyu rail network
- `Keio` - whole Keio rail network
- `Keikyu` - whole Keikyu rail network
- `Tobu` - whole Tobu rail network
- `Seibu` - whole Seibu rail network
- `Keisei` - whole Keisei rail network

## Metro / Urban Rail Systems

### Tokyo Metro

- `Tokyo Metro` - Ginza Line
- `Tokyo Metro` - Marunouchi Line
- `Tokyo Metro` - Hibiya Line
- `Tokyo Metro` - Tozai Line
- `Tokyo Metro` - Chiyoda Line
- `Tokyo Metro` - Yurakucho Line
- `Tokyo Metro` - Hanzomon Line
- `Tokyo Metro` - Namboku Line
- `Tokyo Metro` - Fukutoshin Line

### Toei

- `Toei` - Asakusa Line
- `Toei` - Mita Line
- `Toei` - Shinjuku Line
- `Toei` - Oedo Line
- `Toei` - Toden Arakawa Line

### Other Tokyo Urban Rail

- `TWR` - Rinkai Line
- `Yurikamome` - Tokyo Waterfront New Transit Waterfront Line
- `Tokyo Monorail` - Haneda Airport Line

Reason:

- these operators are the first private-rail companies that materially affect the Tokyo core and major transfer strategy
- because scope should not cherry-pick only one or two lines from a private-rail company, the real phase-1 decision is whether to include the company at all
- this makes operator/data-source planning cleaner than pretending that a company is “partly in”

## Explicitly Deferred From Phase 1

### Other Private Railways

- private-rail companies not yet selected for phase 1
- any selected private-rail company branch families that remain technically pending should still be treated as part of intended scope, not as a different scope decision

### Other JR Lines

- very remote branch lines that do not materially change the first Tokyo-core transfer picture

## Why Metro And Urban Rail Are Included

The current `v3` direction is no longer “Tokyo core plus selected trunks”.
It is the first truthful Tokyo-area full urban rail foundation.

That means:

- Tokyo Metro should enter as a full company network
- Toei rail should enter as a full company/system network
- Rinkai, Yurikamome, Tokyo Monorail, and Toden Arakawa should also be treated as first-class Tokyo urban rail systems

This will raise station density and rendering difficulty, but it matches the actual project direction more honestly than postponing the urban systems that define Tokyo transfer reality.

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
3. Tokyo Metro / Toei / Rinkai / Yurikamome / Tokyo Monorail / Toden Arakawa
4. Included private-rail companies
5. Remaining included JR conventional lines

## Definition Of Done For This File

This file is done when:

- every line in `v3 phase 1` is either explicitly included or explicitly deferred
- no line is represented as an arbitrary half-line scope shortcut
