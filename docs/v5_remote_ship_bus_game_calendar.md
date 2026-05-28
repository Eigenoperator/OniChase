# V5 Remote Ship-Bus Game Calendar

## Decision

Remote ship-port bus connectors use a weekday-default game calendar.

- Default game day type: `weekday`
- Supported precision: `weekday_weekend`
- Weekend data is collected when available, but the current playable game view stays weekday-only.
- Seasonal variants are preserved as source/display metadata.
- Demand-responsive, reservation-only, tourist-only, hotel shuttle, taxi-only, and non-public services are not auto-planning bus connectors.

## Display Rules

The game should not expose a weekday/weekend toggle yet.

- `weekday` is the default and only active game day type for now.
- Weekend data remains in source records for future game-time windows such as Friday-Sunday.
- If `serviceProfile.seasonalVariant` is true, keep the source marker; no UI is required now.
- Do not show demand-responsive transport as a normal timetable option.

## Planning Rules

The planner should use the weekday default for current gameplay.

- `weekday`: Monday-Friday trips are eligible.
- `weekend`: collected in source but not active in current gameplay.
- `monday_to_saturday`: eligible for weekday and Saturday-like weekend windows, but not Sunday.
- `seasonal_variants`: eligible by day type, with source notes retained until a later date-range model exists.

## Source Fields

Remote source routes may include:

- `serviceDays`: source-level service-day string used by augmentation.
- `serviceProfile.calendarPrecision`: currently `weekday_weekend`.
- `serviceProfile.defaultPlayDayType`: currently `weekday`.
- `serviceProfile.supportedDayTypes`: `["weekday"]` or `["weekday", "weekend"]`.
- `serviceProfile.weekendCoverage`: `saturday_sunday`, `saturday_only`, or `not_scheduled`.
- `serviceProfile.seasonalVariant`: boolean marker for source-visible seasonal behavior.
- `serviceProfile.displayPolicy`: currently `use_weekday_default_only_keep_weekend_as_source_data`.

## Current Quality Gates

Use these lightweight checks before asking for heavy promotion:

```bash
python3 scripts/ingest/collect_v5_remote_small_island_ship_port_bus_sources.py
python3 scripts/ingest/audit_v5_remote_ship_bus_readiness.py
python3 scripts/ingest/audit_v5_remote_ship_bus_transfer_windows.py
python3 scripts/ingest/build_v5_remote_ship_bus_quality_queues.py
```

The readiness gate should have:

- `noTripRouteCount: 0`
- `missingServiceProfileRouteCount: 0`
- `missingPortAnchorRouteCount: 0`
- `pendingPortCount: 0`
- `noBusWithoutSourceCount: 0`

Weak transfer windows and manual coordinate reviews are tracked in `data/v5_remote_ship_bus_quality_review_queue.json`.
Remote/small-island ship-bus transfer checks use a 5-180 minute window because low-frequency island buses can still be useful after a longer wait.
