# V4 Finish Checklist

This is the release gate list for finishing `v4`. Keep it capped at 10 items. A task is finished only when its pass criteria are met and the result is recorded in `STATUS.md`, `HISTORY.md`, diary, or memory as appropriate.

## Latest Local Release Evidence

Recorded on 2026-05-06 after the current gameplay bundle rebuild:

- Gate 7 planner interaction: `node scripts/tests/v4_planner_interaction_audit.js --page-url http://127.0.0.1:4177/docs/v4.html --output data/v4_planner_interaction_release.json` passed with `ok: true`, `failureCount: 0`, and no console/page errors.
- Gate 1 route-choice: `node scripts/tests/v4_route_choice_audit.js --page-url http://127.0.0.1:4177/docs/v4.html --output data/v4_route_choice_audit_release.json` passed with `anomalyCount: 0`, `9052` station groups, `111215` trips, and `1590564` route-choice/label rows.
- Gate 2 selected-train highlight: `node scripts/tests/v4_selected_train_highlight_release_gate.js --page-url http://127.0.0.1:4177/docs/v4.html --shard-count 8 --progress-every 5000 --shard-timeout-ms 360000 --max-retries 1 --output data/v4_selected_train_highlight_release.json` passed with `failureCount: 0`, `111215` checked trips, and `829737` future-stop coverage cases.
- Gate 3 coupled/through-running: `python3 scripts/ingest/audit_v4_coupled_services.py` passed with `knownSeedsMissingServicePortions: 0`, `genericHighConfidenceCandidateCount: 0`; focused browser route-choice passed with `anomalyCount: 0`.
- Gate 4 long-distance playability: `node scripts/tests/v4_long_distance_playability_audit.js --page-url http://127.0.0.1:4177/docs/v4.html --fixed-count 300 --random-count 700 --output data/v4_long_distance_release.json` passed `1000/1000` cases with `3612` waypoint station-surface audits and `anomalyCount: 0`.
- Gate 5 same-name station disambiguation: `node scripts/tests/v4_same_name_station_audit.js --page-url http://127.0.0.1:4177/docs/v4.html --output data/v4_same_name_station_release.json` passed `15` cases across `7` ambiguous names with `anomalyCount: 0`.
- Gate 6 ordinary-train coverage: sparse route-choice and hub audits passed with `0` anomalies; sparse checked `9052` stations / `11848` route choices, hub checked `21/21` hubs.
- Data/source hardening: `python3 scripts/ingest/audit_v4_data_quality.py --browser-audit-json data/v4_route_choice_audit_release.json --fail-on-error` passes with `errorCount: 0` and `warningCount: 0`. Source rebuild, service model, and trace-quality contracts are documented in `V4_DATA_REBUILD.md`, `V4_SERVICE_MODEL.md`, and `V4_TRACE_QUALITY.md`.

Fixes made during this pass: adjacent bad trace ranges can fall back to the reviewed physical segment without rewriting long multi-stop traces; `サンライズ瀬戸` branch synthesis pins `高松` to the Kagawa JR Shikoku station instead of same-name stations; selected-train/route-choice/planner release scripts now write JSON output files; `みどり`, `ハウステンボス`, `宗谷`, `ソニック`, `きりしま`, `うずしお`, and related regional named limited-express families are separated from plain line rows; broad JR Hokkaido bracketed service-group labels fall back to their physical line instead of leaking into route choices.

## 1. Route-Choice Release Gate

Goal: make `v4_route_choice_audit.js` the canonical nationwide route-choice gate.

Current state: release-green as of 2026-05-06. The audit has staged scans for `global`, `duplicates`, `known`, `mini-shinkansen`, and `focused`, and the latest full run reports `0` anomalies.

Required before finish:
- Document the exact full command and expected runtime.
- Keep full `0 anomalies` as a release blocker.
- Preserve focused checks for Shinkansen branches, coupled services, Sunrise, airport lines, and known limited-express cases.

Pass command:

```bash
cd /home/xincheng/toy/Chase
python3 -m http.server 4177
node scripts/tests/v4_route_choice_audit.js --page-url http://127.0.0.1:4177/docs/v4.html --output data/v4_route_choice_audit_release.json
```

Pass criteria: `anomalyCount: 0`, no timeout, and runtime remains reasonable for local release validation.

## 2. Selected-Train Highlight Gate

Goal: selected-train map/station highlighting must trust the train's real future physical path and remain continuous.

Current state: release-green as of 2026-05-06. The audit checks continuity, recorded future trace coverage, mini-Shinkansen identity, and reviewed path hints.

Required before finish:
- Run the selected-train audit at release sample size or full configured size.
- Confirm no missing future stops from highlighted path.
- Confirm no disconnected highlight fragments.
- Confirm no ordinary-line leakage for `つばさ`/`こまち`.

Pass command:

```bash
cd /home/xincheng/toy/Chase
python3 -m http.server 4177
node scripts/tests/v4_selected_train_highlight_release_gate.js --page-url http://127.0.0.1:4177/docs/v4.html --shard-count 8 --progress-every 5000 --shard-timeout-ms 360000 --max-retries 1 --output data/v4_selected_train_highlight_release.json
```

Pass criteria: `failureCount: 0` or equivalent zero-failure report.

## 3. Coupled-Service And Through-Running Gate

Goal: keep ordinary through-running, non-Shinkansen coupled services, and Shinkansen coupled exceptions separate.

Current state: release-green as of 2026-05-06. Active rules cover `成田エクスプレス`, `関空快速・紀州路快速`, `サンライズ瀬戸・出雲`, `みどり`/`ハウステンボス`, and Shinkansen exceptions.

Required before finish:
- Confirm non-Shinkansen coupled services use umbrella row plus portion picker from the coupled/shared side.
- Confirm uncoupled branch-side departures appear as normal single portions.
- Confirm Shinkansen coupled services do not merge UI route choices or rows.
- Confirm all coupled portions still count as `same_train` during shared physical windows.
- Review any remaining registry family that lacks weekday evidence and either add source coverage or mark it intentionally scoped out.

Pass commands:

```bash
cd /home/xincheng/toy/Chase
python3 scripts/ingest/audit_v4_coupled_services.py
node scripts/tests/v4_route_choice_audit.js --page-url http://127.0.0.1:4177/docs/v4.html --stages focused --output data/v4_coupled_focused_release.json
```

Pass criteria: no missing required coupled family, no Shinkansen umbrella UI rows, and no broken `same_train` equivalence edges.

## 4. Long-Distance Playability Gate

Goal: prove the current nationwide gameplay surface can plan realistic long-distance and obscure-station routes.

Current state: release-green as of 2026-05-06. The latest local pass reached `1000/1000` playable fixed/random cases with `3612` waypoint audits and `0` anomalies.

Required before finish:
- Run at least `1000` total long-distance cases, mixing fixed, novelty-biased, and random route-chain cases.
- Include obscure stations and under-tested operators.
- Audit every reached origin, transfer, and destination station surface during those routes.
- Classify every failure into data missing, station-name ambiguity, reality-disconnected/unsupported service, or true gameplay bug.

Pass command:

```bash
cd /home/xincheng/toy/Chase
node scripts/tests/v4_long_distance_playability_audit.js --page-url http://127.0.0.1:4177/docs/v4.html --fixed-count 300 --random-count 700 --output data/v4_long_distance_release.json
```

Pass criteria: no unclassified failures, no planner crash, and no new systemic route-choice defect.

## 5. Same-Name Station Disambiguation Gate

Goal: avoid testing or routing against the wrong same-name station.

Current state: release-green as of 2026-05-06. `scripts/tests/v4_same_name_station_audit.js` covers `高松`, `小倉`, `大宮`, `府中`, `郡山`, `福井`, and `寺田` with prefecture/route disambiguation.

Required before finish:
- Add or run same-name station audit cases where station name alone is ambiguous.
- Ensure release audits can specify prefecture/operator/location where needed.
- Confirm UI/debug tooling exposes enough station context for diagnosis.
- Confirm automated tests do not silently pick the wrong same-name station.

Pass criteria: all release-critical same-name cases either resolve by explicit station group/prefecture/operator or are documented as unsupported ambiguity.

Pass command:

```bash
cd /home/xincheng/toy/Chase
node scripts/tests/v4_same_name_station_audit.js --page-url http://127.0.0.1:4177/docs/v4.html --output data/v4_same_name_station_release.json
```

## 6. Ordinary-Train Coverage Gate

Goal: prevent a v4 release that only looks good for Shinkansen and limited express while ordinary trains are missing.

Current state: release-green as of 2026-05-06. Several ordinary coverage problems have been fixed, including 湖西線 and 関西空港線-related cases; latest sparse and hub audits report `0` anomalies.

Required before finish:
- Spot-check JR East, JR West, JR Central, JR Kyushu/Shikoku/Hokkaido, major private railways, subways, and a few local/branch lines.
- Prioritize lines previously affected by source overlap, split pages, or endpoint-line misclassification.
- Confirm single-station shuttles and short branches are represented where real service exists.
- Confirm ordinary trains are not misclassified as limited express.

Candidate commands:

```bash
cd /home/xincheng/toy/Chase
node scripts/tests/v4_sparse_route_choice_audit.js --page-url http://127.0.0.1:4177/docs/v4.html --output data/v4_sparse_route_choice_release.json
node scripts/tests/v4_hub_data_audit.js --page-url http://127.0.0.1:4177/docs/v4.html --output data/v4_hub_data_release.json
```

Pass criteria: no suspicious sparse route choices, no missing major ordinary-service surface, and all intentionally sparse services documented.

## 7. Planner Interaction Gate

Goal: freeze the core gameplay planning interaction as an executable regression.

Current state: release-green as of 2026-05-06. A formal script exists at `scripts/tests/v4_planner_interaction_audit.js` and is treated as a release gate.

Required before finish:
- Confirm `1/3` line choice always appears, even when only one line exists.
- Confirm `2/3` train choice and coupled portion picker work.
- Confirm `3/3` alighting choice works.
- Confirm player can plan the next leg while already on a train.
- Confirm live time removes departed trains without flicker or duplicate button actions.

Pass command:

```bash
cd /home/xincheng/toy/Chase
node scripts/tests/v4_planner_interaction_audit.js --page-url http://127.0.0.1:4177/docs/v4.html --output data/v4_planner_interaction_release.json
```

Pass criteria: zero failures and no console/page errors.

## 8. Performance Gate

Goal: keep v4 playable despite nationwide data size.

Current state: release-green locally as of 2026-05-06. `scripts/tests/v4_performance_gate.js` measures repeated local load timing and the live planner refresh path.

Required before finish:
- Measure DOM ready, map bundle ready, timetable ready, and route-choice audit runtime.
- Confirm no major regression from coupled-service equivalence, timetable decode, or route-choice cache changes.
- Confirm right-side planner does not visibly flicker during live-time updates.
- Confirm online GitHub Pages load is not meaningfully worse than local load.

Pass criteria: timetable ready remains within the current local target range, route-choice audit finishes reliably, and no visible planner flicker in basic live play.

Pass command:

```bash
cd /home/xincheng/toy/Chase
node scripts/tests/v4_performance_gate.js --page-url http://127.0.0.1:4177/docs/v4.html --runs 3 --output data/v4_performance_release.json
```

Latest pass: `ok: true`, `failureCount: 0`; p95 map ready `1293ms`, p95 timetable ready `5810ms`, p95 timetable load `4548ms`; compact timetable gzip is `8563073` bytes; planner live refresh retained future rows, removed departed rows, had `0` empty mutations, and max render was `85.4ms`.

## 9. Release Notes And Known Limitations Gate

Goal: make the v4 release honest and reproducible.

Current state: source-data reproducibility, service model, and trace-quality release thresholds are documented. Final release notes still need to package them into a public-facing narrative.

Required before finish:
- Create final v4 release notes from `V4_DATA_REBUILD.md`, `V4_SERVICE_MODEL.md`, `V4_TRACE_QUALITY.md`, and latest Gate 1-8 JSON evidence.
- State supported gameplay scope.
- State known unsupported cases: different-name walking transfers, BRT/DMV/substitute services, some weekend/holiday-only trains, and local-only MLIT source regeneration.
- List canonical validation commands and latest passing outputs.
- Explain Render room-server deployment remains forbidden unless explicitly reversed.

Pass criteria: a tester can read the release notes and know what v4 does, what it does not do, and how to rerun the release checks.

## 10. GitHub Pages Final Acceptance Gate

Goal: validate the actual public web build, not only local `docs/v4.html`.

Current state: local checks are strong; final public-page acceptance still needs an explicit pass.

Required before finish:
- Open the GitHub Pages `v4.html` URL after the final push.
- Confirm bundle caching does not serve stale data.
- Smoke-test Tokyo Shinkansen, Sunrise, Kansai airport services, a long-distance route, route highlight, selected-train highlight, and planner flow.
- Confirm local and online behavior match for the same probes.

Pass criteria: public Pages v4 passes the same core probes as local v4, with no stale bundle or deployment mismatch.
