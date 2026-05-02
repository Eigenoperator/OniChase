# V4 Subagent Challenge Guidelines

Use current official station names and add operator or route context when a station name is renamed, duplicated nationwide, or split between adjacent operators.

Known station-name rules checked against official/current sources:

- JR Joban Line uses `龍ケ崎市`; Kanto Railway Ryugasaki Line still uses `佐貫`. They are different-name adjacent stations, so do not treat them as transfer-equivalent in the current station-boundary model.
- Nishitetsu Tenjin Omuta Line terminal should be `西鉄福岡（天神）`, not plain `西鉄福岡`.
- Yui Rail's public station name is `県庁前`; nationwide tests must add route context `沖縄都市モノレール線` or `stationGroupId` because multiple `県庁前` stations exist.
- Use real rail stations in the modeled network. Do not make nearby different-name walking transfers such as `空港第2ビル`/`東成田` or `西武秩父`/`御花畑` pass as station-equivalent transfers.
- Avoid BRT, DMV, ferry, and substitute-bus-only links until those modes are modeled in the game.
- For same-name stations such as `郡山`, `大宮`, `寺田`, `県庁前`, and `福井`, include the operator/route context and prefer a waypoint that exists on the target route in the current V4 station identity data.
