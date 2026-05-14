# OniChase V4 Release Notes

V4 moves OniChase from regional prototypes to a nationwide railway gameplay shell on real Japanese railway geometry and weekday timetable data.

## What Is In V4

- Nationwide MapLibre railway map with `9052` station groups and `21932` track centerlines.
- Compact browser timetable with `111969` playable weekday trips.
- Three-step planner: choose line, choose train, choose alighting station.
- In-train future planning: players can keep planning later legs while already riding.
- Live time filtering: departed trains are removed from planner choices without blank-list flicker.
- Selected-train highlighting based on the train's real physical path.
- Real fare ledger for planned/ridden legs, including ordinary fare, station-pair fare, composite fare, JR conventional limited express surcharge, and basic Shinkansen premium support.
- Global replay entry point.
- Optional room-server multiplayer using the shared gameplay loop.

## Data And Service Rules

- Ordinary through-running displays the future route segment while preserving route choice consistency.
- Non-Shinkansen coupled services are treated as the same train for gameplay when reviewed; selecting the coupled train goes directly to alighting stations rather than a branch picker.
- Shinkansen branch services keep visible route identity, with special handling for mini-Shinkansen equivalence.
- Sunrise, Narita Express, Kansai Airport/Kishuji Rapid, JR West named expresses, and selected airport/branch services have release-focused handling.
- Station grouping uses same-name transfer assumptions; different-name walking transfers are v5 work.
- Fare data is collected from official sources and release-covered for all `604 / 604` service routes. Special product fares and boundary-chart fares are documented in source notes rather than estimated.

## Release Gates

Current release evidence:

- Selected-train highlight gate: `111805` trips checked, `6` endpoint coverage failures. The failures are limited to start/end station coverage on a few Joetsu/Musashino/Echigo-Tokimeki-through cases and are recorded as known release limitations rather than broad path continuity failures.
- Fare coverage gate: `604 / 604` service routes covered, `0` missing routes, `failureCount: 0`.
- Shinkansen premium probe: 100 random Shinkansen leg samples produced 100 known fares after adding normal-season ordinary-car reserved-seat surcharge tables.
- Route choice audit: full stage scan completed with focused known-station, duplicate, global, and mini-Shinkansen stages.
- Planner interaction audit: 1/3, 2/3, 3/3, future planning, live filtering, and duplicate-click behavior are covered.
- Long-distance and sparse route-choice audits are retained as release snapshots.
- Performance gate: map ready p95 about `1309ms`, timetable ready p95 about `5757ms`, live planner render max about `61ms`.
- Map pan gate: `scripts/tests/v4_map_pan_performance_gate.js` covers Tokyo, Osaka, and a regional dense-label viewport using real MapLibre. Latest local run passed with p95 frame intervals around `50ms`.

## Known Limitations

See `docs/v4_known_limitations.md`.

The short version: v4 is rail-only, weekday-only, single-player works on public Pages, multiplayer needs a deployed room server, fare coverage is complete at the service-route level, and remaining trace suspect cases should be fixed by source-data improvement rather than front-end fabrication. Shinkansen premium support is intentionally a release-grade baseline, not a full ticketing engine for every add-on and seasonal exception.

## Rebuild Notes

See `docs/v4_release_data.md`.

The release bundle is rebuilt from `data/v4_japan_physical_map.json.gz` and `data/v4_current_weekday_train_instances.json.gz` using:

```bash
python3 scripts/ingest/build_v4_gameplay_bundle.py --write-full-timetable
```
