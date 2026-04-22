# STATUS

## Current Focus
Stabilize public `v3` Tokyo gameplay on the MapLibre page while keeping `v2` online playtest healthy.

## Done
- `v1` Yamanote real-data prototype is complete enough for baseline playtests: real stations, weekday trains, planning, live capture, replay, and hunter visibility.
- Main `v2` is the current nationwide Shinkansen playable build: GIS-first map, real weekday train instances, planning/live/capture/replay, and public online room flow via Render.
- Public `v3` is the official MapLibre Tokyo page at `https://eigenoperator.github.io/OniChase/v3.html`, using the real Tokyo map/timetable bundles and the shared v2-style gameplay path.
- `v3` data foundation includes `1760` station groups, `2142` physical stations, `108` service routes, `4612` track centerlines, and `40738` v2-compatible trip instances.
- `v3` MapLibre gameplay now has role switching, planning/live timing, hourly replanning, plan board, train outlook, selected-train path/stops, player markers, live capture, replay simulation, and Japanese-original display.
- `v3` multiplayer client has single-player entry, v3 Tokyo room lobby, Ready Room, room code copy, ready/unready, leave-room cleanup, and online plan sync.
- v3 planner is now a three-layer `line -> train -> destination stop` flow with line-specific station highlights, compact transfer-symbol grids, better train filtering, and real-geometry selected-train highlights.
- Recent local work tightened departure route matching, optimized MapLibre loading, and generated large v3 data/script changes that are still dirty in the worktree.
- v3 data/script stable set was rebuilt and audited: unified trains `41186`, duplicate unified ids `0`, duplicate unified signatures `0`, rendered lines without trips `0`, and local/public v3 room `/health` both report `dataset_name = v3-tokyo`.
- Committed and pushed the validated v3 stable set in `c66264e` (`Validate v3 Tokyo timetable bundle`).

## In Progress
- Continue hardening `v2` online playtest details: room state, ready/planning/live sync, single-player and multiplayer parity.
- Stabilize `v3` MapLibre gameplay UX: dense Tokyo click behavior, destination-stop selection, player marker clarity, and map/planner readability.

## Blockers
- No usable Notion tool/config exists in this repo/session, so true Notion updates remain blocked.
- `JR Central` still lacks a direct train-detail page like `JR East / JR West`; deeper precision still needs station-grid aggregation.
- Firefox exists locally, but headless screenshot times out in this machine's SWGL renderer; current v3 verification is static JS, bundle decode, generated tile audit, and localhost resource smoke tests until manual browser testing or a stronger browser harness is available.
- Large untracked source caches are intentionally not part of the stable commit: `data/v3_external/`, `data/v3_tokyo_jreast_core_cache/`, and `data/v3_tokyo_rinkai_cache/`.

## Decisions
- [2026-04-07] GIS-first Shinkansen became the main `v2`; public site keeps `v1`, `v2`, and now the new Tokyo `v3` sandbox.
- [2026-04-13] `v3 phase 1` means real Tokyo-area map + real train data, preserving physical station locations rather than faking interchange coordinates.
- [2026-04-19] `v3` UI interactions reuse the main `v2` code; `v3` owns data adapters and Tokyo real-data quality, not a separate interaction layer.
- [2026-04-20] Before new feature work, enforce axioms: backfill missing diary, keep `STATUS.md` under 50 lines, and record meaningful changes in daily memory.

## Next
1. Manually play public `v3.html` online with two browsers through the Ready Room flow now that the v3 room server health endpoint is live.
2. Continue MapLibre UX/performance work: dense Tokyo click targets, selected-service visibility, label priority, and tile/vector migration planning.
