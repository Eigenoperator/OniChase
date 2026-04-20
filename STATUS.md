# STATUS

## Current Focus
Stabilize the main `v2` online playtest while turning `v3` into a real Tokyo map + timetable substrate that reuses the `v2` UI and gameplay path.

## Done
- `v1` Yamanote real-data prototype is complete enough for baseline playtests: real stations, weekday trains, planning, live capture, replay, and hunter visibility.
- Main `v2` is the current nationwide Shinkansen playable build: GIS-first map, real weekday train instances, planning/live/capture/replay, and public online room flow via Render.
- `v3` now has the first unified train index: `39450` normalized real trains across `16` operators, with manifest, unified train schema, and station departure lookup.
- Public `v3` now reuses the `v2` UI code path with `1673` station groups, `2039` physical stations, `108` service routes, `4147` track centerlines, and all `39450` v2-compatible trip instances.
- `v3` is published at `https://eigenoperator.github.io/OniChase/v3.html`; public URL smoke test passes for Tokyo station departures, train selection, and downstream stop choices.
- Backfilled `diary/DIARY-2026-04-19.md` and trimmed this status file back under the 50-line handoff limit.
- Added reusable `v3_station_identity` and `v3_route_identity` layers; audit now reports `0` unmapped train station keys, `0` trains with unmapped stops, `0` collapsed duplicate map names, and `0` tiny routes.
- Optimized v3 map/site performance locally: `v3.html` now opens with `v3_tokyo_map_bundle.json.gz` (`1.3M`) and delayed `v3_tokyo_timetable_bundle.json.gz` (`5.4M`), uses dedicated Tokyo GeoJSON tiles under `docs/data/v3_tokyo_tiles`, indexed timetable lookups, and lightweight SVG scale refresh during wheel zoom.

## In Progress
- Continue hardening `v2` online playtest details: room state, ready/planning/live sync, single-player and multiplayer parity.
- Stabilize `v3` route geometry linkage, dense Tokyo click behavior, and gameplay migration on the reused `v2` UI path after the performance split.
- Validate `v3` on the reused `v2` gameplay path: chained planning, live simulation, capture, replay, and default runner/hunter starts.

## Blockers
- No usable Notion tool/config exists in this repo/session, so true Notion updates remain blocked.
- `JR Central` still lacks a direct train-detail page like `JR East / JR West`; deeper precision still needs station-grid aggregation.
- Firefox exists locally, but headless screenshot times out in this machine's SWGL renderer; current v3 verification is static JS, bundle decode, generated tile audit, and localhost resource smoke tests until manual browser testing or a stronger browser harness is available.

## Decisions
- [2026-04-07] GIS-first Shinkansen became the main `v2`; public site keeps `v1`, `v2`, and now the new Tokyo `v3` sandbox.
- [2026-04-13] `v3 phase 1` means real Tokyo-area map + real train data, preserving physical station locations rather than faking interchange coordinates.
- [2026-04-19] `v3` UI interactions reuse the main `v2` code; `v3` owns data adapters and Tokyo real-data quality, not a separate interaction layer.
- [2026-04-20] Before new feature work, enforce axioms: backfill missing diary, keep `STATUS.md` under 50 lines, and record meaningful changes in daily memory.

## Next
1. Manually test `https://eigenoperator.github.io/OniChase/v3.html` after push: first paint, zoom/pan smoothness, delayed timetable load, station departures, and train selection.
2. Test the reused `v2` chase loop on v3 data in a real browser: chained planning, live movement, capture, and replay.
3. Link v3 service geometry more precisely to train routes so selected trains can highlight real paths instead of only station stops.
