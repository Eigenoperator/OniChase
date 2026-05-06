# V4 Trace Quality Release Threshold

The v4 selected-train highlight rule is simple: trust the train's real recorded future physical path. Highlighting should be continuous and should cover every future stop pair. It should not infer a different path from only the origin and destination.

## Current Gate Results

Current release-candidate evidence:

- `data/v4_selected_train_highlight_release.json`: `failureCount: 0`, `111215` checked trips, `829737` future-stop coverage cases.
- `data/v4_route_choice_audit_release.json`: `anomalyCount: 0`.
- `data/v4_limited_express_trace_suspect_audit.json`: `111983` checked trips, `3368` named/shinkansen/limited candidates, `33424` adjacent stop pairs, `122` suspects, `122` reviewed suspects, `0` unreviewed suspects.

Release threshold: `unreviewedSuspectCount` must be `0`, selected-train release gate must have `failureCount: 0`, and route-choice/trace consistency must have `anomalyCount: 0`.

## High-Risk Traditional Limited Express

`ひたち`/`ときわ` conclusion: reviewed, releasable. The suspect audit still reports long stop-pair segments such as Ueno to Mito because these are real express skips, not missing intermediate stop data. JR East's public route page lists `HITACHI / TOKIWA` as Shinagawa/Tokyo/Ueno to Mito/Iwaki/Sendai service: https://www.jreast.co.jp/multi/en/traininformation/hitachi/ . Current builder rules map the physical route as:

- Shinagawa to Tokyo: `東海道線`
- Tokyo to Ueno: `東北線` / Ueno-Tokyo Line physical trunk
- Ueno or Sendai side to the next Joban stop: `常磐線`

Other reviewed conventional families:

- `サンダーバード`: Osaka/Kyoto/Tsuruga path uses `東海道線` then `湖西線`; dedicated Thunderbird audit verifies all current trips.
- `成田エクスプレス`: reviewed long Tokyo/Narita airport path hints.
- `あずさ`: reviewed Suwa/Matsumoto long physical segment via Shiojiri.
- `ひだ`: Nagoya/Maibara segment stays on `東海道線`, not `関西線`.
- `スペーシア日光`: reviewed Omiya/Tochigi path via Kurihashi and Tobu Nikko side.

## Source Limitations

These are acceptable v4 limitations if documented in release notes:

- The public gameplay source is weekday-focused; weekend/holiday-only or seasonal operations can be absent.
- Some local raw source caches are intentionally not committed, so source regeneration requires local cache possession or a future documented download step.
- A few broad source labels are normalized in the gameplay builder/browser display layer rather than preserved as exact raw public service text.
- Different-name walking transfers remain unsupported; trace audits should not use them to create hidden transfer edges.

## Audit Commands

```bash
node scripts/tests/v4_selected_train_highlight_release_gate.js --page-url http://127.0.0.1:4177/docs/v4.html --shard-count 8 --progress-every 5000 --shard-timeout-ms 360000 --max-retries 1 --output data/v4_selected_train_highlight_release.json
node scripts/tests/v4_limited_express_trace_suspect_audit.js --json-out data/v4_limited_express_trace_suspect_audit.json
node scripts/tests/v4_route_choice_audit.js --page-url http://127.0.0.1:4177/docs/v4.html --output data/v4_route_choice_audit_release.json
```

Use the suspect audit as a review queue. New unreviewed conventional limited-express suspects block release until they are either fixed in source/trace rules or explicitly classified as a source limitation.
