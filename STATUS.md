# STATUS

## Current Focus
Stabilize public `v3` Tokyo gameplay on the MapLibre page while keeping `v2` online playtest healthy.

## Done
- `v1` Yamanote real-data prototype is complete enough for baseline playtests: real stations, weekday trains, planning, live capture, replay, and hunter visibility.
- Main `v2` is the current nationwide Shinkansen playable build: GIS-first map, real weekday train instances, planning/live/capture/replay, and public online room flow via Render.
- Public `v3` is the official MapLibre Tokyo page at `https://eigenoperator.github.io/OniChase/v3.html`, using the real Tokyo map/timetable bundles and the shared v2-style gameplay path.
- `v3` data foundation includes `1760` station groups, `2142` physical stations, `108` service routes, `4612` track centerlines, and `40738` v2-compatible trip instances.
- `v3` MapLibre gameplay now has role switching, planning/live timing, hourly replanning, plan board, train outlook, selected-train path/stops, player markers, live capture, replay simulation, and Japanese-original display.
- `v3` multiplayer client has single-player entry, v3 Tokyo room lobby, Ready Room, room code copy, ready/unready, leave-room cleanup, and online plan sync.
- v3 planner is now a three-layer `line -> train -> destination stop` flow with compact transfer grids, physical train filtering, and selected-train whole-future physical highlights.
- Recent local work tightened departure route matching, optimized MapLibre loading, and generated large v3 data/script changes that are still dirty in the worktree.
- v3 data/script stable set was rebuilt and audited: unified trains `41186`, duplicate unified ids `0`, duplicate unified signatures `0`, rendered lines without trips `0`, and local/public v3 room `/health` both report `dataset_name = v3-tokyo`.
- Committed and pushed the validated v3 stable set in `c66264e` (`Validate v3 Tokyo timetable bundle`).
- Local headless Firefox single-player smoke test passed the core v3 flow: load map/timetable, enter Runner mode, choose line/train/destination, generate a plan, start countdown, and transition into `LIVE`.
- v3 through-running display now classifies departures by the physical boarding line: Toyoko/Yokohama/Hiyoshi/Jiyugaoka no longer surface Tokyo Metro through-service aliases as separate line choices.
- v3 route matching now keeps Shinkansen and ordinary JR lines separate; shared station/operator families no longer make Tokaido Line and Tokaido Shinkansen borrow each other's trains.
- `AXIOMS.md` now records the through-running classification rule: Shinkansen routes stay separated by name, and non-Shinkansen through-running requires same physical track and platform.
- v3 implements that rule in route display: Tokyo Station again shows Yamanote/Keihin-Tohoku/Yokosuka/Tokaido separately, while Jiyugaoka keeps only Tokyu physical boarding lines.
- v3 through-running audit now covers Keikyu/Asakusa/Keisei, Tokyu/Fukutoshin/Seibu/Tobu, Meguro/Mita/Namboku/Sotetsu, Saitama Railway, and Minatomirai display boundaries.
- v3 Tokyo Metro route titles now use common line names (`丸ノ内線`, `有楽町線`, `副都心線`, etc.) instead of numbered legal names in the UI.
- Local two-browser v3 multiplayer smoke passed: Runner/Hunter created and joined one room, both ready states synced into Planning and then LIVE, and local/public room `/health` report `dataset_name = v3-tokyo`.
- v3 selected-train highlights now score trip identity, selected route identity, normalized corridor aliases, and physical endpoint service; public Pages smoke confirms 山手線 stays all 山手線 while 副都心線 through-services split onto 副都心線 -> 東急東横線 -> みなとみらい21線.
- v3 Current Plan ride legs now show the same route-color swatch as the line chooser.
- v3 Current Plan ride rows now keep the subline to boarding/alighting times only.
- Public v3 two-browser playtests now include 30 Render rooms; the latest 10/10 battle reports/timelines show public Japanese line names, private-operator prefixes, and no internal route or station ids.
- Heavy public v3 battle records now support generated 10-leg plans plus same-node/same-train capture checks; the latest 10/10 Render rooms completed with no issues.
- v3 player-facing P0 now includes first-class replay UI plus Tutorial / Advanced Setup entry modes with detailed demonstrations and browser regression coverage.

## In Progress
- Continue hardening `v2` online playtest details: room state, ready/planning/live sync, single-player and multiplayer parity.
- Stabilize `v3` MapLibre/reporting UX behind automated checks: remaining player-understanding copy/states, richer replay playback, easy single-player AI, and map/planner readability.

## Blockers
- `JR Central` still lacks a direct train-detail page like `JR East / JR West`; deeper precision still needs station-grid aggregation.
- Firefox/geckodriver works for headless DOM gameplay probes; use Playwright for local SVG screenshot/bounds checks when system Python lacks Selenium.
- No blocker for the selected-trip highlight fix; large untracked source caches remain local-only: `data/v3_external/`, `data/v3_tokyo_jreast_core_cache/`, and `data/v3_tokyo_rinkai_cache/`.

## Decisions
- [2026-04-07] GIS-first Shinkansen became the main `v2`; public site keeps `v1`, `v2`, and now the new Tokyo `v3` sandbox.
- [2026-04-13] `v3 phase 1` means real Tokyo-area map + real train data, preserving physical station locations rather than faking interchange coordinates.
- [2026-04-19] `v3` UI interactions reuse the main `v2` code; `v3` owns data adapters and Tokyo real-data quality, not a separate interaction layer.
- [2026-04-20] Before new feature work, enforce axioms: backfill missing diary, keep `STATUS.md` under 50 lines, and record meaningful changes in daily memory.

## Next
1. Run the v3 axiom/replay/page suites before changing bundle, through-running, filtering, selected-train highlight, capture, replay, or build-source logic; next product step is clearer plan-validity, capture, and through-service explanations.
2. Triage the remaining dirty v3 data/cache worktree and decide what is stable, ignored, or local-only.
3. Use the cleaned battle timelines to spot gameplay readability bugs, then continue MapLibre UX/performance work: dense Tokyo click targets, selected-service visibility, label priority, and tile/vector migration planning.
