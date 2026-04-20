# STATUS

## Current Focus
Stabilize the main `v2` online playtest while turning `v3` into a real Tokyo map + timetable substrate that reuses the `v2` UI and gameplay path.

## Done
- `v1` Yamanote real-data prototype is complete enough for baseline playtests: real stations, weekday trains, planning, live capture, replay, and hunter visibility.
- Main `v2` is the current nationwide Shinkansen playable build: GIS-first map, real weekday train instances, planning/live/capture/replay, and public online room flow via Render.
- `v3` now has the first unified train index: `39450` normalized real trains across `16` operators, with manifest, unified train schema, and station departure lookup.
- Public `v3` now reuses the `v2` UI code path and loads `docs/data/v3_tokyo_bundle.json`: `1529` stations, `302` service routes, `4147` track centerlines, and `39318` v2-compatible trip instances.
- `v3` is published at `https://eigenoperator.github.io/OniChase/v3.html`; public URL smoke test passes for Tokyo station departures, train selection, and downstream stop choices.
- Backfilled `diary/DIARY-2026-04-19.md` and trimmed this status file back under the 50-line handoff limit.

## In Progress
- Continue hardening `v2` online playtest details: room state, ready/planning/live sync, single-player and multiplayer parity.
- Stabilize `v3` map + timetable identity before gameplay migration: station grouping, line/route mapping, dense Tokyo click behavior, and route-card count.
- Validate `v3` on the reused `v2` gameplay path: chained planning, live simulation, capture, replay, and default runner/hunter starts.

## Blockers
- No usable Notion tool/config exists in this repo/session, so true Notion updates remain blocked.
- `JR Central` still lacks a direct train-detail page like `JR East / JR West`; deeper precision still needs station-grid aggregation.
- `docs/data/v3_tokyo_bundle.json` is below GitHub's hard limit but above the recommended `50MB`; future v3 work should consider chunking or gzip loading before the bundle grows again.

## Decisions
- [2026-04-07] GIS-first Shinkansen became the main `v2`; public site keeps `v1`, `v2`, and now the new Tokyo `v3` sandbox.
- [2026-04-13] `v3 phase 1` means real Tokyo-area map + real train data, preserving physical station locations rather than faking interchange coordinates.
- [2026-04-19] `v3` UI interactions reuse the main `v2` code; `v3` owns data adapters and Tokyo real-data quality, not a separate interaction layer.
- [2026-04-20] Before new feature work, enforce axioms: backfill missing diary, keep `STATUS.md` under 50 lines, and record meaningful changes in daily memory.

## Next
1. Build a reusable `v3` QA/audit script for station-group and line-route quality: top departure stations, map stations with no trains, trains with no map point, tiny routes, huge routes, and ambiguous same-name stations.
2. Use that audit to fix `v3_tokyo_bundle.json` identity issues, especially dense central Tokyo and route fragmentation.
3. After v3 identity stabilizes, test and migrate the `v2` chase loop on v3: multi-leg planning, live capture, replay, and online parity.
