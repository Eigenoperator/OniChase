# V3 Release Candidate Notes

Date: 2026-04-24
Candidate: v3 Tokyo MapLibre gameplay baseline
Public page: `https://eigenoperator.github.io/OniChase/v3.html`

## Release Position

`v3` is ready to treat as a release candidate for the current Tokyo MapLibre milestone.

The point of this RC is not to declare the whole Kanto railway universe complete. It freezes the current playable Tokyo network layer, v2-style gameplay loop, real geometry renderer, and reusable audit path so future work can move into `v4` without destabilizing the current public page.

## Frozen In V3

- Public `v3.html` is the canonical v3 page; `ui/v3_maplibre.html` is only the local mirror synced from it.
- v3 keeps the same gameplay rules as v2: runner/hunter roles, planning/live phases, hourly replanning, plan board, live movement, same-node capture, same-train capture, and replay.
- Single-player and multiplayer must keep the same gameplay loop. Multiplayer is a transport/sync layer, not a separate ruleset.
- Map rendering is MapLibre-based and uses the real Tokyo map/timetable bundles.
- Planner flow is fixed as `line -> train -> destination stop`.
- Selected train highlighting follows real service/track geometry instead of straight station-to-station segments.
- Player-facing station, route, and train names are Japanese-original first.
- Current data foundation is `1804` station groups, `2194` physical stations, `113` service routes, `4612` track centerlines, and `41186` v2-compatible trip instances.

## Verified Baseline

Latest verified command set:

```bash
cd /home/xincheng/toy/Chase
python3 scripts/ingest/run_v3_data_quality_audits.py --checks all --max-samples 15
python3 -m unittest scripts.tests.test_v3_axioms scripts.tests.test_v3_entry_modes scripts.tests.test_v3_online_plan_revision scripts.tests.test_v3_page_build scripts.tests.test_v3_physical_through_running scripts.tests.test_v3_planner_departure_audit scripts.tests.test_v3_replay_record_schema scripts.tests.test_v3_replay_ui scripts.tests.test_v3_selected_train_highlight_golden
```

Current result:

- v3 core unittest suite: `30` tests passed.
- data-quality status: `WARN`, with no hard integrity failures.
- duplicate unified train ids: `0`.
- duplicate unified train signatures: `0`.
- rendered lines without trips: `0`.
- train stations without map groups: `0`.
- forbidden same-operator planner borrowing: `0`.
- visible station/route pairs with no boardable departure: `0`.
- planner unsurfaced boardable trip stops: `9`.

## Known Non-Blocking Warnings

The remaining `9` planner warnings are treated as known external/homonym data edges for this RC, not as v3 gameplay blockers.

- `中央線快速 / 赤坂`: `4` stops. These are Fujikyu-line `赤坂` stops, but the current station-group identity collapses them onto Tokyo Metro `赤坂`.
- `常磐線各駅停車 / 大和`: `3` stops. These are Mito-line-area `大和` stops, but the current station-group identity collapses them onto Kanagawa `大和`.
- `中央線 / 有明`: `1` stop. This is an Oito-line-area `有明` stop, but the current station-group identity collapses it onto Tokyo Bay `有明`.
- `小田原線 / 小田原`: `1` stop. This is an Odakyu Romancecar service continuing beyond `小田原` toward `箱根湯本`; v3 does not yet surface the Hakone Tozan physical route as a planner boarding line.

These warnings should be solved by station identity and out-of-scope external-line handling, not by loosening planner route matching. The current planner rule should remain strict: a visible boarding route must be physically and operationally credible at the selected station.

## Moved To V4

- Full homonym-safe station identity for same-name stations outside the Tokyo core.
- Full treatment of external through-service tails such as Fujikyu, Hakone Tozan, Mito Line, and Oito Line.
- More complete Kanto expansion beyond the current v3 Tokyo surface.
- Further map loading/performance work beyond the current MapLibre baseline.
- Product-level v4 UI redesign decisions after the v3 RC is frozen.

## Do Not Regress

- Do not reintroduce geometry-only boardability. Nearby track geometry is not enough to show a line as boardable.
- Do not merge Shinkansen and ordinary JR route identities just because stations/operators overlap.
- Do not expose through-service alias routes as transfer choices unless they are the physical boarding line at the current station.
- Do not let multiplayer diverge from single-player rules.
- Do not hide the remaining `9` warnings by filtering the audit unless the underlying station identity or external physical route issue is actually fixed.

## Next Handoff

The next natural step is to start `v4` planning from this stable point. `v4` should treat v3 as the playable baseline and focus on a cleaner data model for station identity, external-line boundaries, and larger network growth.
