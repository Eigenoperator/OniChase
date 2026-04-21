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
- Added the first standalone MapLibre renderer spike at `docs/v3_maplibre.html`: WebGL track/service layers, MapLibre label collision, station click, route highlight, route-stop highlight, and lazy timetable-driven departure rows.
- Fixed v3 MapLibre route/track/service colors: generated bundles and tiles now carry per-line colors from the physical-line data plus route aliases and operator fallbacks instead of the old default blue.
- Added the missing full `埼玉高速鉄道線` real geometry toward `浦和美園` with SR blue `#00A6E9`; color QA now reports no missing, white, transparent, or fallback-gray colors in bundles or generated tiles.
- Promoted the MapLibre renderer to the official public `v3.html`; the old v2-style v3 page and separate `v3_maplibre.html` website are removed from the generated site.
- Connected the first v2-style gameplay shell into v3 MapLibre: role switching, clock, planning/live, hourly replanning, plan board, train outlook, selected-train path/stops, player markers, live capture, and local replay simulation now run on the real Tokyo data.
- Made the room server dataset-configurable: `--dataset shinkansen` remains the default, while `--dataset v3-tokyo` loads the Tokyo map bundle plus deferred timetable and reports duplicate trip-id counts in `/health`.
- Added the first v3 multiplayer entry flow: `v3.html` now has a single-player entry, a v3 Tokyo room lobby, room creation/join/copy, ready/unready, a main-board Room panel, and online plan sync against the dataset-configurable server.
- Prepared the v3 Render deployment path: `render.yaml` now declares separate v2 and v3 room services, and `docs/data/v3_online_config.json` points to the expected `onichase-v3-room-server` HTTPS endpoint.
- Cleaned the v3 multiplayer entry: removed developer/test copy, moved Ready/Unready into a dedicated post-create Ready Room, and replaced raw network errors with player-facing offline text.
- Simplified the v3 gameplay sidebar: removed visible Room/Result/Replay/debug route panels and replaced the train picker with a three-layer `line -> train -> destination stop` planner.
- Switched v3 visible station, line, and train names to Japanese-original first across MapLibre labels and the gameplay sidebar.
- Tightened v3 train choices and selected-train highlighting: regular trains hide opaque numbers, row subtitles show origin/terminal/next stop, and map highlight uses real geometry only.
- Refined v3 destination rows: terminal-only trains are filtered out, stop choices show time/station only, and transfer route chips use existing line colors.

## In Progress
- Continue hardening `v2` online playtest details: room state, ready/planning/live sync, single-player and multiplayer parity.
- Stabilize `v3` MapLibre gameplay UX: dense Tokyo click behavior, destination-stop selection, player marker clarity, and map/planner readability.
- Bring up the actual Render `onichase-v3-room-server` service and verify its `/health` reports `dataset_name = v3-tokyo`.

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
1. Create or sync the Render service named `onichase-v3-room-server`; the expected public URL currently returns `Not Found` until Render provisions it.
2. After `/health` returns `dataset_name = v3-tokyo`, manually play public `v3.html` online with two browsers through the new Ready Room flow.
3. Continue MapLibre UX/performance work: smarter label priority, denser Tokyo click targets, selected-service visibility, and tile/vector migration planning.
