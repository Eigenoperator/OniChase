# OniChase V4 Known Limitations

V4 is a nationwide railway gameplay release. It is not a full Japanese mobility simulator.

## Scope

- Rail only. Walking transfers, buses, aircraft, and ferries are v5 work.
- Weekday timetable data only.
- Public GitHub Pages supports single-player immediately. Multiplayer requires a deployed room server and a non-empty `docs/data/v4_online_config.json` `server_url`.
- Different-name walking transfers are intentionally disabled in v4, even when real-world transfer is possible.

## Data Model Limits

- Most gameplay uses station groups and reviewed same-name transfers. This is good enough for rail gameplay but does not model station-building walking distance.
- Through-running and coupled services are modeled for gameplay, but the source data remains mixed: some services are direct in source data, some are stitched, and some are coupled for win-condition equivalence.
- Non-Shinkansen coupled services use coupled-equivalence rules for gameplay and do not show an extra branch picker after a coupled train is selected. Shinkansen branch services keep their route identities visible while still supporting coupled train equivalence where required.
- Sunrise, Narita Express, Kansai Airport/Kishuji Rapid, mini-Shinkansen, and selected JR West limited express cases have explicit handling. New cases should be added to audits before being trusted.

## Fare Limits

- V4 has a real fare ledger, not an estimated one. Current release coverage is `604 / 604` service routes with `failureCount: 0` in `data/v4_fare_rule_coverage_audit.json`.
- Route-level fare coverage does not mean every operator publishes the same kind of fare. Some sources are ordinary distance tables, some are exact station-pair tables, and a few are official product or boundary-chart fares.
- とさでん交通 is represented from the official numbered-ticket boundary chart and city uniform zone, not a full stop-by-stop OD matrix.
- 別府ラクテンチ and 黒部峡谷鉄道 are represented from current official product fares because their public pages do not publish a normal complete one-way railway matrix for the in-game route shape.
- Limited express fare is modeled as ordinary base fare plus a collected limited express surcharge. JR conventional limited express uses the published reserved ordinary-car normal-season surcharge as the current default.
- Shinkansen premium fare now uses collected normal-season ordinary-car reserved-seat surcharge tables by area. Nozomi/Mizuho/Hayabusa/Komachi train-specific add-ons, seasonality, Green/GranClass, special short sections, and complex through-Shinkansen exceptions are not fully modeled in v4.

## Trace And Highlight Limits

- Selected-train highlighting now trusts the train's real physical path. If source stop traces are incomplete, the highlight can only be as good as the trace.
- The latest selected-train release gate checked `111805` selected trips and found `6` endpoint coverage failures. These are currently limited to start/end station coverage on a few Joetsu/Musashino/Echigo-Tokimeki-through cases, not a broad path continuity regression.
- Traditional limited express traces have been improved, but remaining suspects should be treated as source limitations unless a specific route is promoted into the release gate.
- Some virtual/synthetic Shinkansen or source-bridge traces are skipped by focused trace audits when they are not meaningful physical rail paths.

## Performance Limits

- Loading is acceptable for v4 on modern desktop browsers, with the current local release gate around `1.3s` map ready and `5.8s` timetable ready.
- Dense station labels appear early by design. The default map mode is corridor, not service, to keep dragging smooth.
- Map pan performance is now guarded by `scripts/tests/v4_map_pan_performance_gate.js`, but GPU/browser differences can still affect real devices.

## Multiplayer Limits

- The room server is a prototype Python HTTP service using polling, not a production realtime backend.
- Public Pages has `server_url` empty by default, so room creation is disabled until a server is deployed.
- The room server is authoritative for phase, live time, planning windows, plans, and capture. Browser local state should be treated as client UI state.

## Release Rule

If a new data source is added, check overlap with existing source data before ingesting it. New data replacing old data without overlap review is a known high-risk failure mode.
