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
- `serviceCalendar`
- `sourceRefs`
- `dedupeConfidence`

`marketingFlights` is an array because one physical flight may be sold under multiple airline codes.

## Service Calendar

Every flight record must carry an explicit machine-readable service calendar.

Fields:

- `servicePeriod.start`
- `servicePeriod.end`
- `operatingDates`
- `operatingWeekdays`
- `operatingWeekdayNames`
- `calendarParseStatus`
- `calendarParseError`

`operatingWeekdays` uses ISO weekday numbers: Monday is `1`, Sunday is `7`.

If an official timetable gives date ranges such as `7/1-31,8/7-16運航`, the collector expands them into exact operating dates and derives weekdays from those dates. If a collector cannot parse a source calendar note, it must mark the record as `unparsed`; it must not silently guess weekday service.

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
- Skymark, AIRDO, StarFlyer, IBEX, Toki Air, FDA, Jetstar Japan, and Spring Japan now have operator-published v5 artifacts.
- Solaseed, ORC, AMX, and JAC currently have fallback artifacts split from ANA's official all-area timetable by `operatingCarrier`; they are marked as derived sources and should be replaced when their own machine-readable/current route timetables are parsed.
- JAL/JTA/RAC remain the largest missing official group source. JAL publishes operation notices and route-query pages, but a full static 2026 summer machine-readable domestic timetable has not yet been confirmed.
- Peach's official 2026 summer page lists domestic routes and directs users to flight search for details; no full static timetable source has been confirmed yet.
- Jetstar and Spring are marked `implemented_partial_calendar` where PDF row parsing succeeds but some complex Japanese notes still need a dedicated parser.

Aggregator-derived data must not overwrite official data without an overlap audit.
