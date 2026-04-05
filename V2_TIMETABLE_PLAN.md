# V2 Timetable Plan

## Goal

`v2` will use:

- the full Shinkansen map
- all Shinkansen lines on the `v2` map
- real trains
- real timetables

This is not a simplified timetable layer.  
The player should choose real train services with real identities, such as:

- `Nozomi 1`
- `Hikari 507`
- `Kodama 715`
- `Hayabusa 5`
- `Komachi 23`
- `Yamabiko 127`
- `Tsubasa 129`
- `Kagayaki 503`
- `Hakutaka 561`
- `Tsurugi 24`
- `Sakura 549`
- `Mizuho 601`
- `Tsubame 327`
- `Kamome 37`

## Scope

`v2` covers the Shinkansen network shown on the current `v2` map:

- `Tohoku`
- `Hokkaido`
- `Yamagata`
- `Akita`
- `Joetsu`
- `Hokuriku`
- `Tokaido`
- `Sanyo`
- `Kyushu`
- `Nishi-Kyushu`

`GALA Yuzawa` is treated as a branch segment inside the `Joetsu` family, not as a full peer main line.

## Data Principles

### 1. Keep real train identity

Each train instance must preserve:

- service family / train type
- service name
- service number
- full display name

For example:

```json
{
  "service_name": "Nozomi",
  "service_number": "1",
  "display_name": "Nozomi 1"
}
```

Or:

```json
{
  "service_name": "Kagayaki",
  "service_number": "503",
  "display_name": "Kagayaki 503"
}
```

We should not flatten everything into anonymous `train_number` only.

### 2. Keep train-instance storage

`v2` continues the `train instance` model already proven in `v1`.

Each record should represent one real service instance with:

- `display_name`
- `service_name`
- `service_number`
- `operator`
- `route_family`
- `stop_times[]`

Each stop should keep:

- `station_id`
- `arrival_hhmm`
- `departure_hhmm`
- `line_id`

This allows future through-services and keeps the engine aligned with player choice:

`Which exact train am I boarding?`

### 3. Keep line on stop, not train root

As already decided earlier in the project:

- do not glue a train to one single line
- store `line_id` per stop or segment

This matters because `v2` includes:

- branch joins / splits
- services that conceptually belong to one train identity while operating through multiple route families

## Official Source Strategy

We should prefer official operator sources and treat third-party sources as fallback only.

### JR East

Use JR East timetable pages for:

- `Tohoku`
- `Hokkaido`
- `Yamagata`
- `Akita`
- `Joetsu`
- `Hokuriku`

Primary official entry:

- `JR East Timetable`: <https://timetables.jreast.co.jp/en/index.html>

Useful official station entry example:

- `Tokyo Station Timetable`: <https://timetables.jreast.co.jp/en/timetable/list1039.html>

### JR Central

Use JR Central official timetable pages for:

- `Tokaido`

Primary official entry:

- `JR Central Timetable`: <https://global.jr-central.co.jp/en/info/timetable/index.html>

Important note from JR Central:

- their basic timetable pages do not list every extra train
- we must treat this as a real ingestion constraint, not ignore it

### JR West

Use JR West official timetable / Shinkansen service pages for:

- `Sanyo`
- western-side through-services into `Kyushu`

Primary official family entry:

- `JR West Shinkansen`: <https://www.jr-odekake.net/shinkansen/>

### JR Kyushu

Use JR Kyushu official timetable pages for:

- `Kyushu`
- `Nishi-Kyushu`

Useful official entries:

- `JR Kyushu Train Page`: <https://www.jrkyushu.co.jp/english/train/index.html>
- `Nishi Kyushu Shinkansen KAMOME`: <https://www.jrkyushu.co.jp/english/train/shinkansen_kamome.html>

Important note:

- JR Kyushu English pages often expose `major trains` timetables
- this may not be enough for the final all-trains target
- we may need Japanese timetable pages or another official path if the English side is incomplete

## Ingestion Phases

### Phase 1: Route-family inventory

Create one file that defines:

- route families
- operators
- official source entry pages
- representative service families

Planned output:

- `data/shinkansen_v2_source_inventory.json`

### Phase 2: Station timetable entry discovery

For each route family, record:

- official station timetable entry pages
- weekday / holiday variants
- direction variants

Planned output:

- `data/shinkansen_v2_station_timetable_inventory.json`

### Phase 3: Train-detail discovery

For each station timetable family:

- discover minute links
- follow them to train-detail pages where available
- preserve operator-specific page identity

Planned output:

- raw HTML cache or normalized discovery JSON

### Phase 4: Normalize to full train instances

Merge operator-specific raw discoveries into one unified dataset:

- canonical `station_id`
- canonical `line_id`
- real `display_name`
- stop sequence
- arrival / departure times

Planned output:

- `data/shinkansen_v2_train_instances_raw.json`
- `data/shinkansen_v2_train_instances_normalized.json`

### Phase 5: Validate and merge

Run the same style of checks we already use for `v1`:

- duplicate identities
- stop ordering
- unresolved station IDs
- impossible time jumps
- line continuity

Planned output:

- `data/shinkansen_v2_train_instances_merged.json`

## Real-World Naming Rules

The player-facing name should always be the real service name.

Preferred order:

1. `display_name`
2. `service_name + service_number`
3. operator-specific fallback identifier

Bad:

- `TRAIN_001`
- `TOKAIDO_044`
- `eastbound_service_12`

Good:

- `Nozomi 1`
- `Kagayaki 503`
- `Hayabusa 7`
- `Komachi 21`
- `Mizuho 615`

## Complexity Boundary Between V2 And V3

`v2` is still simpler than `v3`, but not because timetable is fake.

`v2` simplification should come from:

- cleaner station graph
- fewer intra-station micro-nodes
- fewer walking / transfer edge complications

`v2` should not simplify by removing real train identity or replacing real timetables with placeholders.

## Immediate Next Steps

1. Build `data/shinkansen_v2_source_inventory.json`
2. List official source entry pages for every Shinkansen route family
3. Check which operators expose full train-detail pages and which only expose major/basic timetable pages
4. Decide the fallback strategy where official pages do not expose complete all-trains detail directly
