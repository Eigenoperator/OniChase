# OniChase V5 Bus Collection Backlog

Generated from the current V5 bus audits on `2026-05-16`.

## Current Playable Source Layer

- GTFS bundle: 454 successfully parsed feeds.
- Bus stops: 88,213.
- Bus routes: 5,114.
- Bus trips: 74,536.
- Stop times: 2,243,003.
- Runtime planner tiles: 374 tiles.
- Saturday active trips in planner tiles: 23,580.
- Walking connectors: 107,349.
- Routes with GTFS fare-rule coverage: 4,536.

## Highest Priority Gap

Airport access is the most important missing data family because V5 flight
gameplay depends on reliable airport ground access.

Current airport access audit:

- 17 airports covered by GTFS airport-class bus routes.
- 2 airports have nearby GTFS bus stops but no airport-class route.
- 4 airports have GTFS bus stops only within the wider 5 km review radius.
- 53 airports have no GTFS bus stop within 5 km in this first source layer.

## First Airport-Bus Parser Targets

These airports have high flight volume and no GTFS bus stop coverage in the
current audit. They should be collected from official airport/operator pages
before lower-volume airports.

| Priority | Airport | Current status | Initial official source target |
| --- | --- | --- | --- |
| 1 | HND | no GTFS stop within 5 km | Haneda Airport express/route bus access page |
| 2 | CTS | no GTFS stop within 5 km | New Chitose Airport bus page; Hokkaido Chuo Bus airport liner |
| 3 | ITM | no GTFS stop within 5 km | Osaka Itami Airport bus page; Hankyu Kanko Bus/Hanshin/Kintetsu links |
| 4 | KIX | no GTFS stop within 5 km | Kansai Airport bus page; Kansai Airport Transportation Enterprise |
| 5 | KOJ | no GTFS stop within 5 km | Kagoshima Airport access bus operators |
| 6 | KMI | no GTFS stop within 5 km | Miyazaki Airport access bus operators |
| 7 | UKB | no GTFS stop within 5 km | Kobe Airport access bus operators |
| 8 | ISG | no GTFS stop within 5 km | Ishigaki Airport bus operators |
| 9 | NGS | no GTFS stop within 5 km | Nagasaki Airport access bus operators |
| 10 | KIJ | no GTFS stop within 5 km | Niigata Airport access bus operators |

## Official Source Seeds

- HND: `https://tokyo-haneda.com/en/access/bus/`
- CTS: `https://www.hokkaido-airports.com/en/new-chitose/access/bus/`
- CTS operator: `https://www.chuo-bus.co.jp/airport.en/`
- ITM: `https://www.osaka-airport.co.jp/en/access/from-airport/bus`
- KIX: `https://www.kansai-airport.or.jp/en/access/from-airport/bus`
- KIX operator: `https://www.kate.co.jp/en/`

## Parser Requirements

Each official parser should output the same normalized bus model as the GTFS
bundle:

- `busAgencyId`
- `busStopId`
- `busRouteId`
- `busTripId`
- `busServiceCalendarId`
- `stops`
- `routes`
- `trips`
- `stopTimes`
- `fareAttributes`
- `fareRules`
- `walkingConnectors`

Do not add airport-bus data as hardcoded map-only geometry. It must be playable:
departure times, stop order, fares, and airport/rail walking connectors all
need to exist.

## Data Conflict Axiom

When adding an official parser, check overlap with the existing GTFS source
layer before merging:

- Same operator + same route + similar stop sequence should not create duplicate
  ride choices.
- Official airport parser should win over stale or incomplete GTFS when both
  exist.
- If both sources are valid but represent different seasonal calendars, keep
  both only when service dates do not overlap.

