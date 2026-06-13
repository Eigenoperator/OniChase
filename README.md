# OniChase

OniChase is a public-transit chase game prototype built on real Japanese railway timetable data.

Current focus:

- keep `v2` nationwide Shinkansen online playtest healthy
- stabilize `v3` Tokyo MapLibre gameplay on real physical geometry and real timetable bundles
- bring `v4` nationwide real physical railway data into the shared MapLibre gameplay shell
- grow `v5` from the v4 shell into multimodal gameplay with walking transfers and domestic flight layers
- audit planner-facing departure correctness, through-running boundaries, and data identity
- keep single-player and multiplayer on the same gameplay loop

## Online Playtest

The GitHub Pages site currently exposes only the active public playtest pages:

- custom domain target: `https://onichase.xincheng2004.com/`
- landing page: `https://eigenoperator.github.io/OniChase/`
- `v1` Yamanote client: `https://eigenoperator.github.io/OniChase/v1.html`
- `v2` GIS Shinkansen client: `https://eigenoperator.github.io/OniChase/v2.html`
- `v3` Tokyo network map: `https://eigenoperator.github.io/OniChase/v3.html`
- `v4` Japan nationwide gameplay: `https://eigenoperator.github.io/OniChase/v4.html`
- `v5` multimodal Japan gameplay shell: `https://eigenoperator.github.io/OniChase/v5.html`

Version focus:

- `v4` is the stable nationwide railway gameplay build.
- `v5` is the active multimodal build based on v4. It currently keeps the railway gameplay shell, adds walking-transfer planning, domestic flight gameplay, airport bus access, and the first independent Ship Map scaffold for real ferry data.

Browser source pages:

- `v1` source: [ui/web_client.html](/home/xincheng/toy/Chase/ui/web_client.html)
- `v2` source: [ui/v2_web_client.html](/home/xincheng/toy/Chase/ui/v2_web_client.html)
- `v3` local mirror: [ui/v3_maplibre.html](/home/xincheng/toy/Chase/ui/v3_maplibre.html)
- `v3` public/source-of-truth page: [docs/v3.html](/home/xincheng/toy/Chase/docs/v3.html)
- `v4` public nationwide gameplay page: [docs/v4.html](/home/xincheng/toy/Chase/docs/v4.html)
- `v5` public multimodal gameplay page: [docs/v5.html](/home/xincheng/toy/Chase/docs/v5.html)
- landing page output: [docs/index.html](/home/xincheng/toy/Chase/docs/index.html)
- Pages workflow: [.github/workflows/deploy-pages.yml](/home/xincheng/toy/Chase/.github/workflows/deploy-pages.yml)

V4 release closeout:

- release notes: [docs/v4_release_notes.md](/home/xincheng/toy/Chase/docs/v4_release_notes.md)
- release data contract: [docs/v4_release_data.md](/home/xincheng/toy/Chase/docs/v4_release_data.md)
- known limitations: [docs/v4_known_limitations.md](/home/xincheng/toy/Chase/docs/v4_known_limitations.md)

## Local Test Build

The main current playtest target is the native local client:

- [app/local_client.py](/home/xincheng/toy/Chase/app/local_client.py)

Quick start:

```bash
git clone https://github.com/Eigenoperator/OniChase.git
cd OniChase
./START_ONICHASE_CLIENT.sh
```

If `tkinter` is missing on your system, see:

- [DEPLOYMENT.md](/home/xincheng/toy/Chase/DEPLOYMENT.md)

Key entry points:

- `STATUS.md`
- `AXIOMS.md`
- `V3_RELEASE_CANDIDATE_NOTES.md`
- `SCHEMA.md`
- `STATE_MACHINE.md`
- `SIMULATION_INPUT.md`
- `PLANNING_FORMAT.md`
- `ui/web_client.html`
- `ui/v2_web_client.html`
- `ui/v3_maplibre.html`
- `docs/index.html`
- `docs/v1.html`
- `docs/v2.html`
- `docs/v3.html`
- `docs/v4.html`
- `docs/v5.html`

Workspace layout:

- `app/` native local client and future desktop-facing app code
- `ui/` browser source pages and playtest-facing web client code
- `docs/` generated static web bundle for GitHub Pages publishing
- `scripts/engine/` simulation and game-engine entry scripts
- `scripts/ingest/` timetable ingestion, normalization, validation, and rendering tools
- `scripts/dev/` local developer utilities such as the local site launcher and web bundle builder
- `data/` real timetable datasets, scenarios, and simulation results

Local testing and setup:

- [DEPLOYMENT.md](/home/xincheng/toy/Chase/DEPLOYMENT.md)
- [LOCAL_CLIENT.md](/home/xincheng/toy/Chase/LOCAL_CLIENT.md)

## Online Prototype

- architecture: [ONLINE_ARCHITECTURE.md](/home/xincheng/toy/Chase/ONLINE_ARCHITECTURE.md)
- protocol: [ONLINE_PROTOCOL.md](/home/xincheng/toy/Chase/ONLINE_PROTOCOL.md)
- room server: [scripts/engine/v2_online_room_server.py](/home/xincheng/toy/Chase/scripts/engine/v2_online_room_server.py)
- `v2` web client: [ui/v2_web_client.html](/home/xincheng/toy/Chase/ui/v2_web_client.html)
- `v3` web client mirror: [ui/v3_maplibre.html](/home/xincheng/toy/Chase/ui/v3_maplibre.html)
- deployment: [ONLINE_DEPLOYMENT.md](/home/xincheng/toy/Chase/ONLINE_DEPLOYMENT.md)

Quick start:

```bash
./START_ONICHASE_V2_SERVER.sh
```

Then open:

- local/public `v2` page: `https://eigenoperator.github.io/OniChase/v2.html`
- local/public `v3` page: `https://eigenoperator.github.io/OniChase/v3.html`

For a local `v3` room server:

```bash
cd /home/xincheng/toy/Chase
python3 scripts/engine/v2_online_room_server.py --dataset v3-tokyo
```

Current multiplayer flow:

- one player opens `v2`, chooses `Runner`, and clicks `Create Room`
- the second player opens `v2`, chooses `Hunter`, enters the room code, and clicks `Join Room`
- both players build plans, click `Ready`, then either side can click `Start Game`
- the room server is authoritative for phase changes, live time progression, hourly replanning, and capture

Public multiplayer note:

- the public `v2` page reads its default room-server URL from [docs/data/v2_online_config.json](/home/xincheng/toy/Chase/docs/data/v2_online_config.json)
- the public `v3` page reads its default room-server URL from [docs/data/v3_online_config.json](/home/xincheng/toy/Chase/docs/data/v3_online_config.json)
- the public `v4` page reads its default room-server URL from [docs/data/v4_online_config.json](/home/xincheng/toy/Chase/docs/data/v4_online_config.json)
- until that file points to a public deployment, single-player works immediately but multiplayer room creation will remain unconfigured on the public site

## Audit And Regression

- unified v3 audit entry: [scripts/ingest/run_v3_data_quality_audits.py](/home/xincheng/toy/Chase/scripts/ingest/run_v3_data_quality_audits.py)
- planner-facing departure audit: [scripts/ingest/audit_v3_planner_departures.py](/home/xincheng/toy/Chase/scripts/ingest/audit_v3_planner_departures.py)
- map/timetable coverage audit: [scripts/ingest/audit_v3_map_timetable_coverage.py](/home/xincheng/toy/Chase/scripts/ingest/audit_v3_map_timetable_coverage.py)
- generated bundle audit: [scripts/ingest/audit_v3_tokyo_bundle.py](/home/xincheng/toy/Chase/scripts/ingest/audit_v3_tokyo_bundle.py)
- raw train dataset audit: [scripts/ingest/audit_v3_train_datasets.py](/home/xincheng/toy/Chase/scripts/ingest/audit_v3_train_datasets.py)
- planner warning summary: [scripts/ingest/summarize_v3_planner_departure_audit.py](/home/xincheng/toy/Chase/scripts/ingest/summarize_v3_planner_departure_audit.py)
- public display-name audit: [scripts/dev/audit_v3_display_names.py](/home/xincheng/toy/Chase/scripts/dev/audit_v3_display_names.py)
- v4 physical-map builder: [scripts/ingest/build_v4_japan_physical_map.py](/home/xincheng/toy/Chase/scripts/ingest/build_v4_japan_physical_map.py)
- v4 MapLibre source exporter: [scripts/ingest/build_v4_maplibre_sources.py](/home/xincheng/toy/Chase/scripts/ingest/build_v4_maplibre_sources.py)
- v4 nationwide line inventory: [scripts/ingest/build_v4_line_inventory.py](/home/xincheng/toy/Chase/scripts/ingest/build_v4_line_inventory.py)
- v4 land outline builder: [scripts/ingest/build_v4_land_outline.py](/home/xincheng/toy/Chase/scripts/ingest/build_v4_land_outline.py)
- v4 track continuity audit: [scripts/ingest/audit_v4_track_continuity.py](/home/xincheng/toy/Chase/scripts/ingest/audit_v4_track_continuity.py)
- v4 Yui Rail official timetable collector: [scripts/ingest/collect_v4_yuirail_official_train_instances.py](/home/xincheng/toy/Chase/scripts/ingest/collect_v4_yuirail_official_train_instances.py)
- v4 Hankyu official timetable collector: [scripts/ingest/collect_v4_hankyu_official_train_instances.py](/home/xincheng/toy/Chase/scripts/ingest/collect_v4_hankyu_official_train_instances.py)
- v4 Nankai official timetable collector: [scripts/ingest/collect_v4_nankai_official_train_instances.py](/home/xincheng/toy/Chase/scripts/ingest/collect_v4_nankai_official_train_instances.py)
- v4 Osaka Metro official station-timetable reconstruction collector: [scripts/ingest/collect_v4_osaka_metro_official_train_instances.py](/home/xincheng/toy/Chase/scripts/ingest/collect_v4_osaka_metro_official_train_instances.py)
- v4 Iyotetsu official route-search reconstruction collector: [scripts/ingest/collect_v4_iyotetsu_official_train_instances.py](/home/xincheng/toy/Chase/scripts/ingest/collect_v4_iyotetsu_official_train_instances.py)
- v4 Keihan official all-train PDF reconstruction collector: [scripts/ingest/collect_v4_keihan_official_train_instances.py](/home/xincheng/toy/Chase/scripts/ingest/collect_v4_keihan_official_train_instances.py)
- v4 Nagoya City Subway official diagram JSON reconstruction collector: [scripts/ingest/collect_v4_nagoya_subway_official_train_instances.py](/home/xincheng/toy/Chase/scripts/ingest/collect_v4_nagoya_subway_official_train_instances.py)
- v4 Hiroden official tram CGI reconstruction collector: [scripts/ingest/collect_v4_hiroden_official_train_instances.py](/home/xincheng/toy/Chase/scripts/ingest/collect_v4_hiroden_official_train_instances.py)
- v4 Shintetsu official all-train PDF reconstruction collector: [scripts/ingest/collect_v4_shintetsu_official_train_instances.py](/home/xincheng/toy/Chase/scripts/ingest/collect_v4_shintetsu_official_train_instances.py)
- v4 Kobe City Subway official CSV open-data collector: [scripts/ingest/collect_v4_kobe_subway_official_train_instances.py](/home/xincheng/toy/Chase/scripts/ingest/collect_v4_kobe_subway_official_train_instances.py)
- browser regression tests: [scripts/tests](/home/xincheng/toy/Chase/scripts/tests)
- v4 real MapLibre pan performance gate: [scripts/tests/v4_map_pan_performance_gate.js](/home/xincheng/toy/Chase/scripts/tests/v4_map_pan_performance_gate.js)
- v4 coupled-train display gate: [scripts/tests/v4_coupled_train_display_audit.js](/home/xincheng/toy/Chase/scripts/tests/v4_coupled_train_display_audit.js)
- v5 real ship interaction gate: [scripts/tests/v5_ship_interaction_audit.js](/home/xincheng/toy/Chase/scripts/tests/v5_ship_interaction_audit.js)

Useful commands:

```bash
cd /home/xincheng/toy/Chase
python3 scripts/ingest/run_v3_data_quality_audits.py --list
python3 scripts/ingest/run_v3_data_quality_audits.py --checks planner-departures
python3 scripts/ingest/run_v3_data_quality_audits.py --checks all --strict
python3 -m unittest scripts.tests.test_v3_planner_departure_audit
python3 -m http.server 8765 --directory . >/tmp/chase_http.log 2>&1 &
node scripts/tests/v5_ship_interaction_audit.js --page-url http://127.0.0.1:8765/docs/v5.html
```
