# V4 Subagent Challenge Guidelines

Use current official station names and add operator or route context when a station name is renamed, duplicated nationwide, or split between adjacent operators.

Known station-name rules checked against official/current sources:

- JR Joban Line uses `龍ケ崎市`; Kanto Railway Ryugasaki Line still uses `佐貫`. For JR-to-Ryugasaki challenges, route via `龍ケ崎市` then `佐貫`, and treat them as transfer-equivalent in the game data.
- Nishitetsu Tenjin Omuta Line terminal should be `西鉄福岡（天神）`, not plain `西鉄福岡`.
- Yui Rail's public station name is `県庁前`; nationwide tests must add route context `沖縄都市モノレール線` or `stationGroupId` because multiple `県庁前` stations exist.
- Use real boundary/interchange stations, not nearby termini: use `京成佐倉` then `東成田`, or `空港第2ビル`/`東成田`, for Shibayama Railway; do not use JR `佐倉` or `成田空港` as the transfer point.
- For Seibu Chichibu to Chichibu Railway, use `西武秩父` and `御花畑` as adjacent transfer-equivalent stations.
- Avoid BRT, DMV, ferry, and substitute-bus-only links until those modes are modeled in the game.
- For same-name stations such as `郡山`, `大宮`, `寺田`, `県庁前`, and `福井`, include the operator/route context and prefer a waypoint that exists on the target route in the current V4 station identity data.
