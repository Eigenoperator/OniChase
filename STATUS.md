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
- v4 route-choice QA now globally scans all `9052` station groups for segment mismatches, virtual-corridor leaks, generic `路線`, remote Yokohama through routes/labels, selected-train label violations, JR East northern-trunk scope, major-station Shinkansen visibility, transfer-equivalent station group route completeness, reviewed limited-express train-number presence, and post-train-selection alighting availability; latest route-choice scan reports `1617356` rows/choices/labels and `0` anomalies.
- v4 nationwide hub data audit now checks `21` player-relevant hubs from 東京 through 札幌/那覇空港 with route-count floors and same-name disambiguation guards; latest run reports `21/21` hubs checked and `0` anomalies.
- v4 long-distance playability audit now validates `30` real staged routes and audits each reached origin/transfer/final station surface, including remote endpoints such as 白浜, 宇和島, 枕崎, 稚内, 根室, 大湊, 女川, 奥多摩, 南小谷, 境港, 奈半利, and 宿毛; latest run reports `30/30` playable, `72` waypoint station surfaces checked, and `0` anomalies.
- v4 selected-train labels now keep 名古屋鉄道 trains on their own `名鉄（...線）` route for the whole trip (`0` Meitetsu label mismatches), and Kintetsu recollection now preserves station-context T7 pages: `52969` station-page departures audit with `0` internal missing trains/context rows; `304` cross-operator through rows are classified as covered by Osaka Metro/Kyoto subway/Hanshin-side sources.
- v4 branded-prefix transfer audit now scans `65` JR/private candidate interchanges: `4` reviewed direct including `蒲田`/`京急蒲田`, `48` active unreviewed direct, and `13` nearby walking candidates needing review.
- v4 v3-release-candidate quality audit now scans all old-source lines still retained in v4: `39605` retained trains across `108` lines, with `291` hard anomalies all from Tokyo Metro Chiyoda old Shinjuku-group rows rematched onto Marunouchi Shinjuku.
- v4 coupled split/join registry is now wired into the website: paired same-station departures on a shared segment and official combined train-title rows collapse into an umbrella `A・B` row, then require a second portion choice before downstream stops; coupled trip pairs also count as `same_train` during their detected shared time window.
- v4 coupled-service audit now finds gameplay evidence for `16/18` registered families: `11` with paired trip evidence and `5` with official combined-title evidence. The data-source fixes restored JR West `まいづる`, `関空快速`, inferred `紀州路快速`, Odakyu/Tobu named limited expresses, and Sunrise combined titles into the compact timetable. The remaining `2` gaps are Odakyu weekday-source gaps: `はこね・えのしま` has both portions but no weekday pair, and `メトロえのしま` is visible only in Sunday cache, not the current weekday collection.
- v4 limited-express UI regression checks now explicitly cover the reviewed train-number cases at 敦賀, 京都, 新大阪, 白浜, 新宿, 大船, 成田空港, 松本, and 大月, including `サンダーバード`, `はるか`, `くろしお`, `成田エクスプレス`, `あずさ`, `かいじ`, and `富士回遊`.
- v4 transfer-equivalent matching now caps reviewed direct interchange pairs at `5km`, preventing broad name pairs such as `JR小倉`/`小倉` from linking unrelated same-name stations across regions.
- v4 load-performance issue was traced to coupled same-train equivalence initialization, not network fetch: local browser profiling showed timetable readiness stuck around `45s`, with `buildCoupledTripEquivalences` alone taking about `44.5s`. The website now caches per-trip coupled search labels/station sets and buckets candidate comparisons by split/join station and time; the same local path is now about `5.3s` total (`~2.0s` map ready, `~3.3s` timetable ready). The map bundle was also slimmed by deriving `serviceGeometry` from `trackCenterlines`, reducing `docs/data/v4_gameplay_map_bundle.json.gz` from about `12.7M` to `9.2M`.
- v4 first-map load was further profiled and optimized: the remaining initial delay came from the map bundle and third-party map assets. The gameplay builder no longer repeats per-track `stationGroupIds` or legacy `gameNodes`, reducing `docs/data/v4_gameplay_map_bundle.json.gz` to about `4.9M` (`~28.1M` JSON text). MapLibre JS/CSS and the first OpenMapTiles glyph PBFs are now vendored under `docs/assets/vendor`, removing first-load dependency on `unpkg.com` and `fonts.openmaptiles.org`. Local browser timing now shows DOM ready around `45ms` and map bundle ready around `1.35s`; route-choice audit remains clean.
- Pages web bundle was slimmed by pruning unreferenced `docs/data` artifacts; local `docs/` now builds to about `44M` while v4 still loads and passes the 青梅 probe.
- Render v4 room-server deployment is forbidden unless Scorp explicitly reverses the axiom; push-triggered server deploy is disabled after repeated failures.

## In Progress
- Promote the v4 nationwide gameplay bundle into a public playtest pass.
- Continue hardening the remaining Odakyu coupled-service gaps by adding a weekend/holiday timetable source or explicitly scoping those registry entries away from weekday gameplay.
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
1. Decide whether v4 gameplay should ingest weekend/holiday Odakyu Romancecar sources so `はこね・えのしま` and `メトロはこね・メトロえのしま` can be represented when they do not exist in the current weekday source.
