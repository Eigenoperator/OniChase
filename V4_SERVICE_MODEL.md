# V4 Service Model

This documents the train/service rules that v4 now depends on. These rules are gameplay axioms, not cosmetic labels.

## Ordinary Through-Running

普通の直通 is one train continuing across route identities without a public split/join portion choice. The UI should show the boarding-side physical/operating line label, not generic `直通`, `through`, `corridor`, or `service` metadata. Selected-train highlight follows the train's recorded future `lineTrace`, including the current section and all downstream sections.

Covered by:

- `scripts/tests/v4_route_choice_audit.js`: global train-label scan, route-choice/trace consistency, no generic metadata text.
- `scripts/tests/v4_selected_train_highlight_release_gate.js`: future stops covered by path, continuous selected-train path, mini-Shinkansen branch identity.

## Non-Shinkansen Coupled Services

直挂/併结 is not ordinary through-running. A coupled train has multiple public portions that share a physical segment and split/join later. From the shared side, v4 shows an umbrella row and then requires a portion choice; from the branch side, each portion appears as its own normal train. During the shared physical segment, game capture treats the coupled portions as `same_train`.

Registry source: `data/v4_coupled_service_registry.json`.

Release-covered families:

- `成田エクスプレス`
- `関空快速・紀州路快速`
- `サンライズ瀬戸・サンライズ出雲`
- `みどり・ハウステンボス`
- reviewed `ひだ` split/join cases where weekday evidence exists

Covered by:

- `python3 scripts/ingest/audit_v4_coupled_services.py`
- focused stage in `scripts/tests/v4_route_choice_audit.js`
- planner interaction audit for portion picker behavior

Latest coupled audit: `knownSeedsMissingServicePortions: 0`, `genericHighConfidenceCandidateCount: 0`.

## Shinkansen Exception

Coupled Shinkansen portions are a display exception. They should stay in their own route choices and train rows, but the capture engine still treats same physical shared-segment portions as `same_train`.

Rules:

- `はやぶさ` and `こまち` are not merged into an umbrella route row.
- `やまびこ` and `つばさ` are not merged into an umbrella route row.
- `こまち` branch identity remains `秋田新幹線`; it must not leak into ordinary `田沢湖線`/`奥羽線` labels.
- `つばさ` branch identity remains `山形新幹線`; it must not leak into ordinary `奥羽線` labels.

Covered by the route-choice `mini-shinkansen` stage and selected-train highlight gate.

## Sunrise

`サンライズ瀬戸・出雲` is a non-Shinkansen coupled service. Tokyo-side rows collapse to one umbrella train; portion choice exposes `サンライズ瀬戸 -> 高松` and `サンライズ出雲 -> 出雲市`. Seasonal `サンライズ出雲91/92` rows are filtered from normal weekday gameplay. `高松` must resolve to the Kagawa JR Shikoku station, not another same-name station.

Covered by focused route-choice checks at Tokyo, Yokohama, Okayama, Takamatsu, and Izumoshi.

## NEX

`成田エクスプレス` is a coupled service where shared Tokyo-side service can split toward airport-side portions. It uses the non-Shinkansen umbrella/portion rule, and reviewed path hints cover long Tokyo-to-airport no-stop segments over the real route chain.

Covered by coupled-service audit, route-choice focused checks, and selected-train highlight path coverage.

## Kanku/Kishuji Rapid

`関空快速・紀州路快速` is a coupled ordinary rapid service. Shared-side rows collapse into one umbrella row, then offer `関空快速 -> 関西空港` and `紀州路快速 -> 和歌山` portions. The selected-train path must use the real west-side Osaka Loop path via Nishikujo, then Hanwa/Kansai Airport line toward the airport, rather than guessing between endpoints.

Covered by coupled-service audit, planner portion checks, and selected-train highlighted path regressions.

## Named Limited Express

Named limited express and named liner families must not collapse into plain physical line rows. Regional names such as `みどり`, `ハウステンボス`, `ソニック`, `きりしま`, `うずしお`, `宗谷`, `サンダーバード`, `はるか`, `くろしお`, `あずさ`, `かいじ`, `富士回遊`, `ひたち`, and `ときわ` remain public train/service names when present.

Covered by route-choice global train-label scan, hub/sparse audits, and `scripts/tests/v4_limited_express_trace_suspect_audit.js`.
