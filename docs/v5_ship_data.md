# OniChase V5 Ship Data

V5 ship/ferry is a first-class public-transport mode. It follows the flight
map interaction pattern, but with lighter gameplay rules.

## Gameplay Contract

- Both runner and hunter can use ships.
- Ships do not require advance ticket purchase in the current rule set.
- Ships do not require an arrival-at-port buffer before departure.
- A player can board when their current plan tail is at the departure port
  access node before the scheduled departure.
- Long-distance and night ferries reveal boarding to the opponent.
- Short urban ferries and local island ferries do not reveal by default.
- Weather and cancellation handling are ignored for gameplay; published
  scheduled services are treated as operating when the calendar says they run.
- Cross-day arrivals are represented by adding 24 hours to the arrival minute.
  For example, a ferry departing 21:00 and arriving next day 06:00 is stored as
  departure `21:00`, arrival minute `30:00`.

## Nodes

Ports are independent transport nodes.

- Port nodes are not railway stations.
- Port nodes are not bus stops.
- Rail, bus, and walking access to ports must be represented by connectors.
- Same-name ports in different cities must remain separate.
- UI displays real port names; no artificial three-letter port code is used.

## Source Rules

Required real source data before a route becomes playable:

- Port coordinates.
- Operator.
- Route name.
- Directional timetable.
- Service calendar or explicit operating date note.
- Adult passenger fare.
- Source URL and retrieval timestamp.

Unknown fare stays unknown and blocks playable promotion for ship mode until a
real fare source is attached.

## Initial Runtime Artifact

The web runtime reads:

- `docs/data/v5_ship_map.geojson`

Current status:

- The Ship Map and planning UI scaffold are enabled.
- First official ferry source promoted into the map artifact:
  - 青函フェリー 青森フェリーターミナル ⇔ 函館フェリーターミナル
  - 2 ports, 2 directional routes, 16 daily trips
  - Adult passenger fare is stored from the official 2-season fare table
    (`¥2,700` normal season, `¥3,200` peak season)
- Second batch promoted into the source/map artifact:
  - 津エアポートライン 津なぎさまち ⇔ 中部国際空港高速船のりば
  - 神戸-関空ベイ・シャトル 神戸空港 ⇔ 関西空港
  - 南海フェリー 和歌山港 ⇔ 徳島港
  - 伊勢湾フェリー 鳥羽港 ⇔ 伊良湖港
  - 桜島フェリー 鹿児島港 ⇔ 桜島港
  - 有明フェリー 多比良港 ⇔ 長洲港
- Current artifact coverage: 7 route groups, 14 ports, 14 directional routes,
  and 62 explicit timetable trips. Some routes have official fare/port/service
  pattern data but still need detailed timetable parsing before boarding.
- Third batch promoted into the source/map artifact:
  - 23 additional long-distance and island-trunk route groups from official
    operator sources, including 太平洋フェリー, 商船三井さんふらわあ,
    新日本海フェリー, 阪九フェリー, 名門大洋フェリー, 東京九州フェリー,
    オーシャン東九フェリー, 宮崎カーフェリー, シルバーフェリー,
    津軽海峡フェリー, 佐渡汽船, 小笠原海運, and 東海汽船.
  - Current artifact coverage is now 30 route groups, 53 ports, 70
    directional route segments, and 62 explicit timetable trips.
  - The long-distance batch is intentionally `timetable_calendar_fare_pending`
    because seasonal fare/calendar parsers must be implemented before boarding.
- Boarding remains disabled until port connectors and ship-boarding gameplay
  guards are implemented.
- No fake port or route is included.

## Current Official Source Files

- `data/v5_ship_seikan_ferry_official.json`
- `data/v5_ship_priority_batch_official.json`
- `data/v5_ship_long_distance_batch_official.json`
- Builder: `scripts/ingest/build_v5_ship_map.py`
