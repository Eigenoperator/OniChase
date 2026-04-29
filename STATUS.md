# STATUS

## Current Focus
Turn the expanded `v4` nationwide rail data into a stable gameplay/playtest checkpoint.

## Done
- `v1` is archived as the early Yamanote real-data prototype.
- Main `v2` remains the nationwide Shinkansen playable build with planning/live/capture/replay and Render-backed online rooms.
- Public `v3` is frozen as the Tokyo MapLibre release-candidate baseline at `https://eigenoperator.github.io/OniChase/v3.html`.
- `v3` baseline data: `1804` station groups, `2194` physical stations, `113` service routes, `4612` track centerlines, and `41186` v2-compatible trip instances.
- `v3` core suite passes `30` tests; remaining `9` external/homonym data edges are documented for v4.
- `v4` physical map builds from local MLIT N02-2024 with `10239` physical stations, `9052` station groups, `21932` track centerlines, and `178` operators after manual physical-station overrides.
- `station_identity_v2` preserves physical station coordinates while grouping gameplay/interchange identity by N02 group code first; same-name stations are not globally collapsed.
- Latest v4 identity audit reports `427` same-name split names, `0` multi-name station groups, and `0` line coverage warnings.
- Public `v4.html` displays the nationwide physical railway map with MapLibre, Japan outline layers, overview/detail track switching, station labels, optional physical station dots, line search, and selected-line highlighting.
- v4 line inventory lists `596` operator-line pairs, `552` unique line names, `178` operators, `0` stationless lines, and `0` trackless lines.
- v4 track-continuity audit uses 500m endpoint snap and reports `6` reviewed multi-component operator-line pairs, `0` unreviewed.
- v4 line rendering uses line-level color when known and falls back to company color; current inventory marks `152` line-specific colors and `444` company fallbacks.
- Current v4 structured train collection has `120425` weekday train instances across `22` source collections and `179` operators after the global station-match-distance quality gate.
- v4 train health audit is clean: `0` duplicate service ids, `0` duplicate signatures, `0` short trains, `0` missing station-group stops, `0` missing physical-station stops, and `0` bad time-order trains.
- v4 gameplay bundle now exports `120420` playable compact trips, `618` service routes/patterns, and skips only `5` short gameplay trips.
- v4 room-server bundle now has `9052` station groups and `120420` SQLite-backed trips.
- v4 planner corridor audit passes the first `6` major hub checks with `0` warnings.
- Local v4 browser probes pass axioms/entry/replay checks and confirm stop-level display routes: 東京/神田/秋葉原 no longer expose stray `東北線`, 鎌倉 exposes `湘南新宿ライン` instead of raw `東北線`, 鎌倉 `横須賀線・総武快速線` now stitches same-operator Tokyo splits such as `492S -> 493F` through to 千葉, 御茶ノ水/新宿 split orange `中央線快速` from yellow `中央・総武線各駅停車`, and 立川 splits `青梅線`/`中央線` by outgoing segment.
- v4 through-service display audit covers all browser-stitched trips: `678` stitched through trips, `0` stale `東海道線+総武線` / `総武線+東海道線` labels, and expected labels for `横須賀線・総武快速線`, `京急`/`都営浅草線`, and `京成`/`都営浅草線`.
- Reusable v4 through-service audit reports `1026` split-trip candidates: `942` covered by existing browser rules, `52` confirmed direct-service rules, `26` reviewed likely reused-number/data-context non-UI cases, and `6` still needing review.
- v4 route-choice QA now globally scans all `9052` station groups for segment mismatches, virtual-corridor leaks, generic `路線`, remote Yokohama through routes/labels, selected-train label violations, JR East northern-trunk scope, major-station Shinkansen visibility, transfer-equivalent station group route completeness, and post-train-selection alighting availability; latest route-choice scan reports `1695906` rows, `1696259` choices/labels, and `0` anomalies.
- v4 selected-train labels now keep 名古屋鉄道 trains on their own `名鉄（...線）` route for the whole trip (`0` Meitetsu label mismatches), and Kintetsu recollection now preserves station-context T7 pages: `52969` station-page departures audit with `0` internal missing trains/context rows; `304` cross-operator through rows are classified as covered by Osaka Metro/Kyoto subway/Hanshin-side sources.
- v4 branded-prefix transfer audit now scans `65` JR/private candidate interchanges: `4` reviewed direct including `蒲田`/`京急蒲田`, `48` active unreviewed direct, and `13` nearby walking candidates needing review.
- v4 v3-release-candidate quality audit now scans all old-source lines still retained in v4: `39605` retained trains across `108` lines, with `291` hard anomalies all from Tokyo Metro Chiyoda old Shinjuku-group rows rematched onto Marunouchi Shinjuku.
- Pages web bundle was slimmed by pruning unreferenced `docs/data` artifacts; local `docs/` now builds to about `44M` while v4 still loads and passes the 青梅 probe.
- Render v4 room-server deployment is forbidden unless Scorp explicitly reverses the axiom; push-triggered server deploy is disabled after repeated failures.

## In Progress
- Promote the v4 nationwide gameplay bundle into a public playtest pass.
- Review whether the meter-scale 肥薩線 N02 fragment should remain visible or be hidden in rendered geometry.

## Blockers
- Raw MLIT N02-2024 source files are local-only and ignored by git; regenerated v4 artifacts require those local files or a documented download step.
- Large collection caches remain local-only and should not be committed.

## Decisions
- [2026-04-07] GIS-first Shinkansen became the main `v2`; old prototypes stay archived.
- [2026-04-13] Physical map stations must keep real locations; gameplay station groups may allow transfers without faking map coordinates.
- [2026-04-24] `v3` is frozen as a release candidate; remaining external/homonym identity work belongs to `v4`.
- [2026-04-25] `v4` starts from nationwide N02 physical geometry plus `station_identity_v2`, not from another Tokyo-only hand-built map.
- [2026-04-25] v4 timetable stop matching should reuse the v3 station alias/station-group method, not invent a separate identity system.

## Next
1. Run visual/manual v4 playtest QA from major hubs plus branch/corridor stations: Tokyo, Osaka, Nagoya, Fukuoka, Sapporo, Hiroshima, 青梅, 立川, and 御茶ノ水.
