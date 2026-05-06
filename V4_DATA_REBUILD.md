# V4 Data Rebuild Contract

This is the minimum reproducibility contract for publishing v4. It is not yet a one-command nationwide scrape from zero; it documents the required local raw inputs, the release source-of-truth artifacts, and the command chain that rebuilds the current web bundle.

## Release Source Of Truth

The public v4 web release is defined by these generated artifacts:

- `data/v4_japan_physical_map.json.gz`: physical railway/station identity source for v4.
- `data/v4_current_weekday_train_instances.json.gz`: merged weekday train-instance source after source overlap/dedupe rules.
- `data/v4_gameplay_manifest.json` and `docs/data/v4_gameplay_manifest.json`: release manifest and counts.
- `docs/data/v4_gameplay_map_bundle.json.gz`: public map/gameplay network bundle.
- `docs/data/v4_gameplay_timetable_compact.json.gz`: public compact timetable used by `docs/v4.html`.
- `docs/data/v4_gameplay_timetable_bundle.json.gz`: full public timetable debug artifact when built with `--write-full-timetable`.

Current manifest counts, generated `2026-05-06T22:46:12+00:00`: `10239` physical stations, `9052` station groups, `21932` track centerlines, `604` service routes/patterns, `111969` compact trips, and `309` skipped short/foreign/no-gameplay trains.

## Required Local Inputs

These are intentionally local/cache artifacts and are not all committed:

- MLIT N02-2024 railway geometry:
  - `data/raw_n02_24/UTF-8/N02-24_Station.geojson`
  - `data/raw_n02_24/UTF-8/N02-24_RailroadSection.geojson`
- Prefecture/land boundary cache:
  - `data/raw_boundaries/geoBoundaries-JPN-ADM1_simplified.geojson`
- Baseline and current timetable sources:
  - `data/v4_existing_v3_weekday_train_instances.json.gz`
  - `data/v4_gtfs_weekday_train_instances.json.gz`
  - `data/v4_jreast_official_weekday_train_instances.json.gz`
  - `data/v4_jreast_tohoku_official_weekday_train_instances.json.gz`
  - `data/v4_jreast_joban_official_weekday_train_instances.json.gz`
  - `data/v4_jreast_nex_official_weekday_train_instances.json.gz`
  - `data/v4_jreast_chuo_official_weekday_train_instances.json.gz`
  - `data/v4_jreast_core_gap_official_weekday_train_instances.json.gz`
  - `data/v4_jreast_residual_gap_official_weekday_train_instances.json.gz`
  - `data/v4_jrcentral_navitime_weekday_train_instances.json.gz`
  - `data/v4_jrwest_official_weekday_train_instances.json.gz`
  - `data/v4_jrhokkaido_vtime_weekday_train_instances.json.gz`
  - `data/v4_jrshikoku_navitime_weekday_train_instances.json.gz`
  - `data/v4_jrkyushu_navitime_weekday_train_instances.json.gz`
  - `data/v4_kintetsu_official_weekday_train_instances.json.gz`
  - `data/v4_meitetsu_official_weekday_train_instances.json.gz`
  - `data/v4_yuirail_official_weekday_train_instances.json.gz`
  - `data/v4_hankyu_official_weekday_train_instances.json.gz`
  - `data/v4_nankai_official_weekday_train_instances.json.gz`
  - `data/v4_osaka_metro_official_weekday_train_instances.json.gz`
  - `data/v4_iyotetsu_official_weekday_train_instances.json.gz`
  - `data/v4_keihan_official_weekday_train_instances.json.gz`
  - `data/v4_nagoya_subway_official_weekday_train_instances.json.gz`
  - `data/v4_hiroden_official_weekday_train_instances.json.gz`
  - `data/v4_shintetsu_official_weekday_train_instances.json.gz`
  - `data/v4_kobe_subway_official_weekday_train_instances.json.gz`
  - `data/v4_navitime_non_jr_weekday_train_instances.json.gz`
  - `data/v4_special_manual_weekday_train_instances.json.gz`

Rule: when adding a new source file, check overlap against older sources before merging. New data must not mask older line-specific variants, coupled portions, or endpoint-specific routes.

## Rebuild Commands

Run from the repository root:

```bash
python3 scripts/ingest/build_v4_japan_physical_map.py
python3 scripts/ingest/build_v4_current_train_collection.py
python3 scripts/ingest/audit_v4_current_train_health.py
python3 scripts/ingest/build_v4_gameplay_bundle.py --write-full-timetable
python3 scripts/ingest/audit_v4_data_quality.py --browser-audit-json data/v4_route_choice_audit_release.json --fail-on-error
```

If route-choice release JSON is stale or absent, start a local server and regenerate it before the data-quality audit:

```bash
python3 -m http.server 4177
node scripts/tests/v4_route_choice_audit.js --page-url http://127.0.0.1:4177/docs/v4.html --output data/v4_route_choice_audit_release.json
```

The current release-candidate data-quality result is `data/v4_data_quality_audit.json` with `errorCount: 0` and `warningCount: 0`.

## Publish Threshold

Before v4 release, the rebuild is acceptable only if:

- manifest counts are intentional and recorded,
- current train health has no duplicate service ids, missing station stops, short train instances, or bad time ordering,
- data-quality audit exits with `0` errors and `0` warnings,
- route-choice and selected-train release audits remain green against the rebuilt public `docs/data` artifacts.
