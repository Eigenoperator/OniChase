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

## In Progress
- Turn the v4 nationwide physical bundle into a MapLibre-renderable layer set.
- Design station identity v2 adapters from physical stations to gameplay station groups without breaking single-player/multiplayer parity.

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
1. Export v4 physical tracks/stations into MapLibre-friendly GeoJSON/PMTiles-style layer inputs.
2. Add an identity lookup that maps timetable stops to station groups while preserving physical stations for rendering.
3. Write the v4 source-download/regeneration note so another machine can rebuild the nationwide map.
