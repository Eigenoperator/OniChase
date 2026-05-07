# OniChase V4 Release Data

This file defines the minimum reproducible data contract for the v4 release. V4 does not promise one-command nationwide re-collection from the public internet; it does require that the release bundle can be rebuilt from the checked-in source artifacts listed here.

## Release Source Of Truth

The static website reads these files from `docs/data/`:

- `v4_gameplay_map_bundle.json.gz`: MapLibre railway substrate used by `docs/v4.html`.
- `v4_gameplay_timetable_compact.json.gz`: browser timetable source used by the planner and live gameplay.
- `v4_gameplay_manifest.json`: generated counts, source file names, defaults, and train normalization stats.
- `v4_coupled_service_registry.json`: reviewed coupled-service rules used by v4 gameplay.
- `v4_transfer_equivalence_review.json`: same-name transfer review data. Different-name walking transfers are intentionally not enabled in v4.
- `v4_online_config.json`: optional room-server endpoint. Empty `server_url` means public multiplayer is not configured.

The canonical working copies live in `data/` with the same names. `docs/data/` is the GitHub Pages deployment copy.

## Required Rebuild Inputs

These artifacts are required to rebuild the current v4 gameplay bundle:

- `data/v4_japan_physical_map.json.gz`
- `data/v4_current_weekday_train_instances.json.gz`
- `data/v4_coupled_service_registry.json`
- `data/v4_transfer_equivalence_review.json`
- `scripts/ingest/build_v4_gameplay_bundle.py`
- `scripts/ingest/build_v4_maplibre_sources.py`
- `scripts/ingest/v4_visual_identity.py`

Room-server multiplayer additionally requires:

- `data/v4_room_server_bundle.json.gz`
- `data/v4_room_server_trips.sqlite`
- `scripts/engine/v2_online_room_server.py`

## Optional But Preserved Inputs

The official-source caches under `data/v4_*_official_cache/`, `data/v4_navitime_non_jr_cache/`, and JR cache directories are not loaded by the website. They are preserved because v4 data fixes often need to compare new collection output against existing source pages. When adding new data, check overlap with the current merged data before replacing old records.

## Rebuild Command

Use this to rebuild the deployed browser bundle from the current release inputs:

```bash
python3 scripts/ingest/build_v4_gameplay_bundle.py --write-full-timetable
```

Expected outputs:

- `data/v4_gameplay_map_bundle.json.gz`
- `data/v4_gameplay_timetable_compact.json.gz`
- `data/v4_gameplay_timetable_bundle.json.gz`
- `data/v4_gameplay_manifest.json`
- matching copies under `docs/data/`

Current manifest baseline:

- station groups: `9052`
- physical stations: `10239`
- track centerlines: `21932`
- service routes: `604`
- compact trips: `111969`
- skipped trains: `309`

## Release Audit Artifacts

The v4 release evidence is summarized by these JSON files:

- `data/v4_selected_train_highlight_release.json`
- `data/v4_route_choice_audit_release.json`
- `data/v4_planner_interaction_release.json`
- `data/v4_sparse_route_choice_release.json`
- `data/v4_long_distance_release.json`
- `data/v4_coupled_focused_release.json`
- `data/v4_hub_data_release.json`
- `data/v4_performance_release.json`
- `data/v4_map_pan_performance_release.json`

Do not treat these audit outputs as gameplay source of truth. They are release evidence and regression snapshots.

Coupled-train display is also guarded by `scripts/tests/v4_coupled_train_display_audit.js`.
