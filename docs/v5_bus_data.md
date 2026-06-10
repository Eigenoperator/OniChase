# OniChase V5 Bus Data

V5 bus is a nationwide real-data system. It is not an airport-access shortcut.
The target scope is:

- Airport access buses.
- Highway buses and night buses.
- Local route buses.
- Walking connectors from bus stops to rail stations, airports, and later ports.

This page describes the long-term bus data target. The current V5 release
exposes only airport buses and port-connector buses; see
`v5_release_contract.md` for the active release scope.

## Source Policy

The first source layer is GTFS/GTFS-JP because it carries the exact fields the
game needs: agencies, stops, routes, trips, calendars, stop times, fares,
shapes, and transfers.

Primary input:

- `data/v4_gtfs_repository_route_index.json`
- Source API: public GTFS data repository files endpoint.
- Selection rule: feeds marked `isBusOnly` with GTFS `route_type=3`.

Current index snapshot:

- 536 bus-only feeds.
- 457 feeds selected for the current bus bundle on `2026-05-16`.
- 73 feeds expired before `2026-05-16`.
- 4 feeds start after `2026-05-16`.
- 2 feed URLs are excluded because they are already handled by the rail GTFS
  override registry.
- 5,779 routes.
- 100,235 source stop rows.
- 2,419,631 source stop-time rows.

Current bundle result on `2026-05-16`:

- 454 feeds downloaded and parsed successfully.
- 3 selected feed URLs returned source errors and remain listed in
  `data/v5_bus_gtfs_audit.json`.
- 88,213 bus stops.
- 5,114 bus routes.
- 74,536 bus trips.
- 2,243,003 bus stop-time rows.
- 6,423 route shapes.
- 2,369 source transfer rows.
- 68,091 fare attributes.
- 2,427,804 fare rules.
- 106,929 bus-stop -> rail-station walking connectors.
- 420 bus-stop -> airport walking connectors.

Builder:

```bash
python scripts/ingest/build_v5_bus_gtfs_bundle.py
```

Debug/smoke example:

```bash
python scripts/ingest/build_v5_bus_gtfs_bundle.py \
  --max-feeds 5 \
  --skip-shapes \
  --output /tmp/v5_bus_smoke_bundle.json.gz \
  --audit-output /tmp/v5_bus_smoke_audit.json
```

Release output:

- `data/v5_bus_gtfs_current_bundle.json.gz`
- `data/v5_bus_gtfs_audit.json`
- `data/v5_airport_bus_access_audit.json`
- `data/v5_bus_map.geojson.gz`
- `data/v5_bus_map_audit.json`
- `data/v5_bus_map_tiles/manifest.json`
- `data/v5_bus_planner_tiles/manifest.json`
- `data/v5_bus_planner_tiles_audit.json`

The builder caches source zip files under `data/v5_bus_gtfs_cache/` so the
release bundle can be rebuilt even if a feed changes later. The cache should be
treated like source material, not as derived gameplay data.

Current-date builds should pass the target service date explicitly:

```bash
python scripts/ingest/build_v5_bus_gtfs_bundle.py --service-date 2026-05-16
```

Inactive feeds are skipped by default and recorded in the audit. Use
`--include-inactive` only for source investigation, never for a current playable
bundle.

Feeds already listed in `data/v4_manual_gtfs_feed_overrides.json` are also
skipped so a tram/rail feed that uses bus-like GTFS encoding cannot appear twice
as both rail and bus.

## Bundle Shape

The bundle preserves source ids with feed-scoped ids so different operators do
not collide:

- `busAgencyId`
- `busStopId`
- `busRouteId`
- `busTripId`
- `busServiceCalendarId`
- `busShapeId`
- `busFareId`

Main tables:

- `sourceFeeds`
- `agencies`
- `stops`
- `routes`
- `trips`
- `stopTimes`
- `calendars`
- `fareAttributes`
- `fareRules`
- `shapes`
- `transfers`
- `walkingConnectors`

## Service Classes

The builder adds a gameplay grouping field:

- `bus_airport`
- `bus_long_distance`
- `bus_local`

This is only a display/planning hint. It must not modify the real route,
timetable, fare, or stop data. Misclassified classes should be fixed by audit or
operator-specific rules, not by changing source facts.

## Gameplay Rules

The current V5 bus gameplay contract is:

- All real bus services are in scope nationwide.
- All bus classes are boarded like rail once the player can walk to the bus stop
  in time.
- Bus riding does not need advance purchase in the current gameplay model.
- Bus riding does not create an opponent reveal.
- Players on the same bus are caught by the same-vehicle capture rule.
- Players at the same bus stop are caught by the same-node capture rule.
- Bus stop transfers always use walking time from coordinates.
- Cross-day night buses are allowed.
- Airport rail access and airport buses are both valid choices when both exist.
- Missing fare data should be collected from real sources. Do not fabricate bus
  fares as release facts.
- Bus planning is local-context first: show reachable stops/routes around the
  current player position or plan tail, not an unsorted nationwide bus list.

## Walking Connectors

Bus stop connectors are generated from coordinates:

- bus stop -> rail station group
- bus stop -> airport
- bus stop -> port

The first generator uses Haversine distance to match the current walking system.
Runtime walking time still comes from the shared walking speed function.

Port connector generation:

```bash
python scripts/ingest/build_v5_port_connectors.py
python scripts/ingest/build_v5_bus_planner_tiles.py
```

Current port connector audit:

- 374 ship/ferry port nodes scanned.
- 1,103 bus stop -> port walking connectors are available in the bus planner
  tiles.
- 263 ports have at least one rail, bus, or airport access node within 2 km.
- 111 ports remain connector gaps in the current rail/bus/airport source layer;
  they are listed in `data/v5_port_connector_audit.json` and should be cleared
  by adding real local bus/port access data rather than fake walking links.

Airport connector audit:

```bash
python scripts/ingest/audit_v5_airport_bus_access.py
```

This produces one row per airport and separates:

- airport covered by GTFS airport-class bus route
- nearby GTFS bus stop but no airport-class route
- only wider search-radius stops
- no GTFS bus stop in search radius

Current airport access audit on `2026-05-16`:

- 17 airports covered by GTFS airport-class bus routes.
- 2 airports have a bus stop within 2 km but no airport-class route.
- 4 airports have bus stops only within the wider 5 km review radius.
- 53 airports have no GTFS bus stop within 5 km in this first source layer.

## Bus Map Layer

The browser does not load the full GTFS bundle for map display. The full bundle
contains the timetable and fare source tables, including more than two million
stop-time rows, so it is too heavy for an interactive map layer.

The map-facing layer is generated separately:

```bash
python scripts/ingest/build_v5_bus_map.py
```

Current output on `2026-05-16`:

- 98,266 GeoJSON features.
- 8,809 bus route line features.
- 89,457 bus stop point features.
- 534 spatial bus-map tiles at `0.25` degree resolution.
- 158 KB tile manifest.
- Largest gzipped tile is about 489 KB; median tile feature count is about 107.
- Route lines by class:
  - 324 airport-bus lines.
  - 126 long-distance/highway/night-bus lines.
  - 8,359 local-bus lines.
- Stop points by class:
  - 2,648 airport-bus stops.
  - 1,052 long-distance/highway/night-bus stops.
  - 85,757 local-bus stops.

The V5 web page does not load `docs/data/v5_bus_map.geojson.gz` at runtime.
That full file remains a rebuild/debug artifact. Runtime bus-map display loads
`docs/data/v5_bus_map_tiles/manifest.json` first, then only the nearby tile
files around the current player position or plan tail. Dense local bus stops and
labels are still zoom-gated so the railway/flight map does not become unreadable
or slow.

## Bus Planner Layer

The playable bus planner uses a second tiled dataset. It is intentionally
separate from the visual map layer because planning needs departures, downstream
stops, walking connectors, and fare hints, while map drawing only needs lines
and stop points.

Builder:

```bash
python scripts/ingest/build_v5_bus_planner_tiles.py
```

Current output on `2026-05-16`:

- Service date: `2026-05-16` Saturday.
- 467 planner tiles at `0.25` degree resolution.
- 28,767 active bus trips for the service date.
- 711,463 indexed stop-time rows.
- 112,947 walking connectors.
- 4,586 routes with GTFS fare-rule coverage.
- Official non-GTFS local bus augmentation includes port connector buses such
  as 小豆島オリーブバス 坂手線, 直島町営バス, 上島町町有バス,
  大崎上島循環線, 西鉄バス 志賀島島内線, 青森ねぶたん号,
  苫小牧西港フェリーターミナル連絡バス, 新潟交通 E11 臨港町線,
  福井鉄道フェリー線, and 苫小牧東港連絡バス, imported only from
  official or operator-published timetable sources with real stop coordinates.

Runtime flow:

- Choose reachable bus stop within the active walking threshold.
- Choose route/direction.
- Choose a real future bus departure.
- Choose a downstream bus stop.
- The plan stores walking to the bus stop, bus boarding, bus riding, and walking
  back from a bus stop to rail as separate actions.
- Same-bus and same-bus-stop capture are part of the event simulation.

## Known First-Layer Limits

- GTFS repository coverage is broad but not all Japanese buses.
- Some airport limousine, highway, port-access, and island local buses may not
  publish GTFS; those need official operator parsers.
- Reservation rules are not guaranteed by GTFS and need route/operator audits.
- Port connectors are generated from the ferry node dataset at the active 2 km
  threshold. Ports beyond that threshold require real bus/rail connector data,
  not synthetic long walking edges.
- Bus fares use GTFS fare rules when available. Missing fare rules remain
  unknown rather than estimated.
- The first playable bus layer is service-date based. More weekday switching
  and operator-specific missing-source parsers are still needed.
