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

## Walking Connectors

Bus stop connectors are generated from coordinates:

- bus stop -> rail station group
- bus stop -> airport
- bus stop -> port, after ferry/port nodes exist

The first generator uses Haversine distance to match the current walking system.
Runtime walking time still comes from the shared walking speed function.

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

- 96,797 GeoJSON features.
- 8,584 bus route line features.
- 88,213 bus stop point features.
- Route lines by class:
  - 143 airport-bus lines.
  - 126 long-distance/highway/night-bus lines.
  - 8,315 local-bus lines.
- Stop points by class:
  - 1,512 airport-bus stops.
  - 1,052 long-distance/highway/night-bus stops.
  - 85,649 local-bus stops.

The V5 web page loads `docs/data/v5_bus_map.geojson.gz` only when bus mode is
opened. Airport and long-distance bus geometry is visible earlier; dense local
bus stops and labels are deliberately zoom-gated so the railway/flight map does
not become unreadable or slow.

## Known First-Layer Limits

- GTFS repository coverage is broad but not all Japanese buses.
- Some airport limousine and highway buses may not publish GTFS; those need
  official operator parsers.
- Reservation rules are not guaranteed by GTFS and need route/operator audits.
- Port connectors wait for the ferry node dataset.
- The bus map layer is connected, but bus riding is still blocked until route
  filtering, stop selection, and airport/highway-bus rules are audited.
