# OniChase V5 Bus Data

V5 bus is a nationwide real-data system. It is not an airport-access shortcut.
The target scope is:

- Airport access buses.
- Highway buses and night buses.
- Local route buses.
- Walking connectors from bus stops to rail stations, airports, and later ports.

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
- 5,779 routes.
- 100,235 source stop rows.
- 2,419,631 source stop-time rows.

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

The builder caches source zip files under `data/v5_bus_gtfs_cache/` so the
release bundle can be rebuilt even if a feed changes later. The cache should be
treated like source material, not as derived gameplay data.

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

## Walking Connectors

Bus stop connectors are generated from coordinates:

- bus stop -> rail station group
- bus stop -> airport
- bus stop -> port, after ferry/port nodes exist

The first generator uses Haversine distance to match the current walking system.
Runtime walking time still comes from the shared walking speed function.

## Known First-Layer Limits

- GTFS repository coverage is broad but not all Japanese buses.
- Some airport limousine and highway buses may not publish GTFS; those need
  official operator parsers.
- Reservation rules are not guaranteed by GTFS and need route/operator audits.
- Port connectors wait for the ferry node dataset.
- The bus UI is not connected yet; this document and builder establish the real
  data substrate first.
