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
- Reusable v4 scripts added: `scripts/ingest/build_v4_japan_physical_map.py` and `scripts/ingest/audit_v4_station_identity.py`.
- Latest v4 identity audit reports `427` same-name split names, `0` multi-name station groups, and `0` line coverage warnings.
- v4 MapLibre-ready public GeoJSON layers now exist under `docs/data/v4_maplibre`: `track_centerlines`, `station_groups`, `physical_stations`, and `line_inventory`.
- v4 nationwide line inventory now lists `596` operator-line pairs, `552` unique line names, `178` operators, `0` stationless lines, and `0` trackless lines.
- Public `v4.html` now displays the nationwide physical railway map with MapLibre, the same `station-labels` source and hub/major/local label-layer logic as v3, optional physical station dots, line search, and selected-line highlighting.
- v4 map now includes two-level Japan outline-only coastline rendering, low-zoom `596`-feature track overview, lazy high-detail track loading, lazy physical-station loading, and high-zoom station dots for labels.
- v4 track-continuity audit reports `12` multi-component operator-line pairs out of `596`; the report is saved as `data/v4_track_continuity_audit.json`.
- v4 continuity warnings now have a dedicated review map at `docs/v4_continuity.html` plus generated SVG/GeoJSON highlight outputs.
- v4 overview tracks now fade out by zoom `7.65`, and exact physical `track_centerlines` take over from zoom `7.55` to avoid straight overview lines overlapping real geometry.

## In Progress
- Start nationwide timetable-source planning from the `596` operator-line inventory.
- Continue reducing v4 map ambiguity from same-operator colors by adding official per-line colors.
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

## Next
1. Review the 12 highlighted continuity warnings and classify each as real gap, legitimate multi-section line, or source artifact.
2. Add official per-line colors so same-operator nearby lines no longer look like broken segments.
3. Add an identity lookup that maps timetable stops to station groups while preserving physical stations for rendering.
