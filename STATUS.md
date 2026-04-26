# STATUS

## Current Focus
Build `v4` from the frozen `v3` Tokyo MapLibre release candidate, starting with nationwide real physical rail geometry and safer station identity.

## Done
- `v1` is archived as the early Yamanote real-data prototype.
- Main `v2` remains the nationwide Shinkansen playable build with planning/live/capture/replay and Render-backed online rooms.
- Public `v3` is frozen as the Tokyo MapLibre release-candidate baseline at `https://eigenoperator.github.io/OniChase/v3.html`.
- `v3` baseline data: `1804` station groups, `2194` physical stations, `113` service routes, `4612` track centerlines, and `41186` v2-compatible trip instances.
- `v3` core suite passes `30` tests; data-quality has no hard integrity failures, no visible no-boardable station/route warnings, and only `9` known external/homonym unsurfaced-stop warnings.
- `V3_RELEASE_CANDIDATE_NOTES.md` documents the frozen v3 baseline and moves external-line/homonym identity edges into v4.
- `v4` first data slice now builds from local MLIT N02-2024: `10235` physical stations, `9048` station groups, `21932` track centerlines, and `178` operators.
- `station_identity_v2` now preserves physical station coordinates while grouping gameplay/interchange identity by N02 group code first; same-name stations are not globally collapsed.
- `station_identity_v2` now adds prefecture/location notes to every v4 physical station and station group, with `10235/10235` physical stations assigned.
- Reusable v4 scripts added: `scripts/ingest/build_v4_japan_physical_map.py` and `scripts/ingest/audit_v4_station_identity.py`.
- Latest v4 identity audit reports `427` same-name split names, `0` multi-name station groups, and `0` line coverage warnings.
- v4 MapLibre-ready public GeoJSON layers now exist under `docs/data/v4_maplibre`: `track_centerlines`, `station_groups`, `physical_stations`, and `line_inventory`.
- v4 nationwide line inventory now lists `596` operator-line pairs, `552` unique line names, `178` operators, `0` stationless lines, and `0` trackless lines.
- Public `v4.html` now displays the nationwide physical railway map with MapLibre, the same `station-labels` source and hub/major/local label-layer logic as v3, optional physical station dots, line search, and selected-line highlighting.
- v4 map now includes two-level Japan outline-only coastline rendering, low-zoom `596`-feature track overview, lazy high-detail track loading, lazy physical-station loading, and high-zoom station dots for labels.
- v4 track-continuity audit now uses 500m endpoint snap and reports `6` reviewed multi-component operator-line pairs, `0` unreviewed.
- v4 continuity warnings now have a dedicated review map at `docs/v4_continuity.html` plus generated SVG/GeoJSON highlight outputs.
- v4 overview tracks now fade out by zoom `7.65`, and exact physical `track_centerlines` take over from zoom `7.55` to avoid straight overview lines overlapping real geometry.
- v4 line rendering now uses line-level color when known and falls back to company color; current inventory marks `152` line-specific colors and `444` company fallbacks, audited by `scripts/ingest/audit_v4_line_colors.py`.
- Reusable v4 timetable work now includes source discovery, ODPT CKAN resource discovery, and the first GTFS collector; `12` structured GTFS/GTFS-JP feed files are audited and `10` operators currently produce `4439` weekday train instances with `0` unmatched stops.

## In Progress
- Expand v4 timetable collection beyond the current public GTFS/GTFS-JP feeds into ODPT token-gated GTFS/API and official timetable-page collectors.
- Expand the official per-line color table beyond the first v3/Tokyo/Shinkansen seed set.
- If coastline performance regresses again, convert the two-level outline GeoJSON contract into PMTiles.

## Blockers
- Raw MLIT N02-2024 source files are local-only and ignored by git; regenerated v4 artifacts require those local files or a documented download step.
- v3 still has `9` non-fatal external/homonym data edges: Fujikyu `赤坂`, Mito-line `大和`, Oito-line `有明`, and Hakone Tozan beyond `小田原`.
- Large collection caches remain local-only and should not be committed.

## Decisions
- [2026-04-07] GIS-first Shinkansen became the main `v2`; old prototypes stay archived.
- [2026-04-13] Physical map stations must keep real locations; gameplay station groups may allow transfers without faking map coordinates.
- [2026-04-19] `v3` reuses the v2 gameplay path; it owns data adapters and Tokyo real-data quality, not a separate ruleset.
- [2026-04-24] `v3` is frozen as a release candidate; remaining external/homonym identity work belongs to `v4`.
- [2026-04-25] `v4` starts from nationwide N02 physical geometry plus `station_identity_v2`, not from another Tokyo-only hand-built map.
- [2026-04-25] v4 timetable stop matching should reuse the v3 station alias/station-group method, not invent a separate identity system.

## Next
1. Decide whether to hide or keep the reviewed meter-scale 肥薩線 N02 fragment in rendered geometry.
2. Continue filling missing official per-line colors for non-Tokyo regional operators.
3. Continue v4 timetable ingestion by resolving ODPT token access for Tokyo Metro/TWR/Tama Monorail/MIR/Yokohama Municipal and writing official-page collectors for operators without public GTFS.
