# OniChase V5 Flight Data

V5 flight data is collected as real scheduled public transport. Flight schedules are current data, so every release artifact must keep source URLs, source dates, and collection timestamps.

## Gameplay Rules

- Both runner and hunter can use flights.
- A flight ticket can be bought from anywhere.
- A ticket must be bought at least `3600` seconds before scheduled departure.
- The player must reach the airport public node at least `1800` seconds before scheduled departure.
- Boarding state begins `900` seconds before scheduled departure.
- Destination airport exit buffer defaults to `600` seconds after arrival.
- Buying, changing, or canceling a flight ticket is revealed to the opponent immediately.
- Only one active flight ticket is allowed per player.
- All timing constants are configuration values, not hard-coded game facts.

## Airport IDs

Airport ids use IATA three-letter codes.

Examples:

- `HND`: Tokyo Haneda
- `NRT`: Tokyo Narita
- `KIX`: Kansai
- `ITM`: Osaka Itami
- `CTS`: Sapporo New Chitose

Large airports may later be split into terminal nodes. Terminal nodes keep the IATA prefix, for example `HND:T1T2` and `HND:T3`.

## Physical Flight Identity

The dataset stores one record per physical flight, not one record per marketed flight number.

Fields:

- `physicalFlightId`
- `operatingCarrier`
- `operatingFlightNumber`
- `marketingFlights`
- `originAirport`
- `destinationAirport`
- `departureTimeLocal`
- `arrivalTimeLocal`
- `calendarNote`
- `sourceRefs`
- `dedupeConfidence`

`marketingFlights` is an array because one physical flight may be sold under multiple airline codes.

## Codeshare Rule

Codeshare flights must not create duplicate playable flights.

Canonical grouping order:

1. If source provides operating carrier and operating flight number, group by operating carrier, operating flight number, airports, date/calendar, and scheduled times.
2. If source gives only a marketing flight number plus operating carrier, group by operating carrier, airports, scheduled times, and calendar note.
3. If operating carrier is unknown, keep the record but mark `dedupeConfidence: low`.

When two sources describe the same physical flight, merge their `marketingFlights` and `sourceRefs`.

## Initial Sources

Official or operator-published sources are preferred.

- ANA domestic timetable PDF: includes ANA marketed services and operating-company codes such as `AKX`, `ADO`, `IBEX`, `SNA`, `SFJ`, `ORC`, `JAC`, and `AMX`.
- JAL domestic timetable: covers JAL, JTA, RAC and lists domestic airport pairs and JAL group/codeshare notices.
- Independent carriers and airport official timetables are source candidates when their own flight numbers are needed for dedupe.

Aggregator-derived data must not overwrite official data without an overlap audit.

