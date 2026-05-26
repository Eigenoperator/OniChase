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
  - 28 additional long-distance, island-trunk, and major regional route groups from official
    operator sources, including 太平洋フェリー, 商船三井さんふらわあ,
    新日本海フェリー, 阪九フェリー, 名門大洋フェリー, 東京九州フェリー,
    オーシャン東九フェリー, 宮崎カーフェリー, シルバーフェリー,
    津軽海峡フェリー, 佐渡汽船, 小笠原海運, 東海汽船, 四国開発フェリー,
    ジャンボフェリー, 小豆島フェリー, and 瀬戸内海汽船/石崎汽船.
  - Current artifact coverage is now 35 route groups, 62 ports, 84
    directional route segments, and 62 explicit timetable trips.
  - The long-distance batch is intentionally `timetable_calendar_fare_pending`
    because seasonal fare/calendar parsers must be implemented before boarding.
- Fourth batch promoted into the source/map artifact:
  - 35 additional official public route groups covering Hokkaido island routes,
    Izu/Ogasawara feeders, Hokuriku/local island ferries, major Kyushu/Shikoku
    crossings, Okinawa remote-island ferries, Yaeyama routes, and Oki Kisen.
  - Current artifact coverage is now 70 route groups, 134 ports, 208
    directional route segments, and 62 explicit timetable trips.
  - This batch is intentionally `official_route_and_ports_collected_timetable_calendar_fare_pending`.
    It is visible on the Ship Map as real source/port/route coverage, but it is
    not promoted to playable boarding until timetable, calendar, fare, and port
    connector checks are attached.
- Fifth collection batch:
  - Added `data/v5_ship_expansion_to_150_source_inventory.json` with 80 more
    official MLIT-discovered public/municipal scheduled ferry source entries.
  - Overall ship collection now has 150 official source entries covered by
    either promoted map route groups or source-inventory records.
  - These 80 entries are source-only for now. They are intentionally blocked
    from the Ship Map until precise official port names and real port
    coordinates are verified; city/island route text must not be converted into
    fake port nodes.
- Sixth map-promotion batch:
  - Added `data/v5_ship_expansion_150_map_batch1_official.json` with 30
    reviewed local and island route groups promoted from the 150-source pool.
  - Current Ship Map coverage is now 100 route groups, 190 ports, 284
    directional route segments, and 62 explicit timetable trips.
  - These 30 newly mapped groups remain
    `official_route_and_ports_collected_timetable_calendar_fare_pending`; they
    are visible as real port/route geography but are not boardable until
    timetable, calendar, fare, and connector checks are complete.
- Seventh source-completion batch:
  - Added `data/v5_ship_expansion_to_193_source_inventory.json` with the final
    60 MLIT public/municipal scheduled ferry source entries not already
    represented by promoted sources or the 150-source inventory.
  - Current MLIT source coverage is now 193/193 public/municipal scheduled
    ship/ferry candidates. The 6 `review_transport_or_sightseeing` entries are
    still excluded from this public-transport source baseline.
  - These final 60 entries are source-only and remain blocked from Ship Map and
    playable promotion until precise ports, coordinates, timetables, calendars,
    fares, and connectors are verified.
- Eighth map-completion batch:
  - Added `data/v5_ship_map_to_193_official.json` with 93 additional MLIT
    public/municipal candidate route groups promoted to Ship Map visibility.
  - Current Ship Map coverage is now 193 route groups, 374 ports, 568
    directional route segments, and 62 explicit timetable trips.
  - This batch is explicitly
    `map_visible_needs_precise_port_timetable_calendar_fare_connector_review`.
    It completes visual coverage, but all newly added route-text-derived
    endpoints must be reviewed against exact official pier names before they can
    become playable.
- First playable boarding bundle:
  - Added `docs/data/v5_ship_timetable_current_bundle.json` and
    `data/v5_ship_playable_promotion_audit.json`.
  - Only routes with explicit official trip times and a known adult passenger
    fare are promoted to gameplay boarding.
  - The first playable cut promoted 6 directional routes and 62 sailings:
    青函フェリー, 津エアポートライン, and 神戸-関空ベイ・シャトル.
  - V5 gameplay uses walking access from the current rail/bus node to the
    origin port. At the destination port, gameplay now chooses the nearest
    generated rail, bus-stop, or airport access node within the configurable
    port-access radius, so a player can continue from ports that have real
    nearby connector data.
- 400-sailing playable batch:
  - Added `data/v5_ship_playable_400_batch_official.json` with official
    high-frequency timetables and fares for JR西日本宮島フェリー, 宮島松大汽船,
    桜島フェリー, 有明フェリー, and 南海フェリー.
- 500-sailing playable batch:
  - Added `data/v5_ship_playable_500_batch_official.json` with official
    timetables and fares for 福岡市営渡船 and 小豆島フェリー.
  - Current playable ship bundle is now 26 directional routes and 536 explicit
    official sailings.
  - The remaining 542 map-visible directional routes stay visible but are not
    boardable because they still need exact timetable/fare/calendar promotion.
- No fake port or route is included.
- Port connector artifact:
  - `data/v5_port_connectors.json`
  - `docs/data/v5_port_connectors.json`
  - `data/v5_port_connector_audit.json`
  - `docs/data/v5_port_connector_audit.json`
  - `data/v5_ship_port_access_priority_audit.json`
  - `docs/data/v5_ship_port_access_priority_audit.json`
  - Current coverage: 374 ports scanned; 206 have rail/bus/airport access
    within 2 km; 168 remain connector gaps pending real local bus or access
    data.
  - Added official local-bus connector source `data/v5_port_connector_official_bus_source.json`
    for 小豆島オリーブバス 坂手線（土庄港 ⇔ 坂手港ターミナル前）,
    直島町営バス（宮浦港 ⇔ つつじ荘）, and 大分バス 佐賀関線
    （大分駅前 ⇔ 佐賀関）. These are playable bus trips with
    real stop coordinates and official timetable sources, then linked to ports
    through generated 2 km port connectors.
  - Added official Setouchi port-connector bus source
    `data/v5_setouchi_port_connector_official_bus_source.json` for
    上島町町有バス（上弓削港 ⇔ 立石港務所） and 大崎上島循環線
    （大西港・明石港・白水港周辺）. This clears 2 km access for
    上弓削港, 白水港, 大西港, and 明石 without inventing fake walking edges.
  - The priority audit separates ports that need real mainland/large-island
    connector collection from remote or small-island cases that can be recorded
    as local-island connector gaps. Port names are not enough for collection:
    ambiguous names such as 大島港 must be checked with route/operator and
    coordinates before adding access data.
  - Current no-2 km access triage after identity review:
    - 168 total no-access ports.
    - 0 must resolve port identity first; the previous ambiguous port-name
      red lights have been split by operator/route context.
    - 126 are high-priority real connector collection candidates.
    - 6 are lower-priority real connector candidates.
    - 36 are remote/small-island local access records.
    - 160 playable-affected ports still need connector decisions.
  - Reservation-sensitive rule: reservation-demand access such as 江田島北部線
    / おれんじ号 must not be promoted as an ordinary bus until the bus model
    can expose reservation requirements. These can be collected, but gameplay
    must show them differently from normal fixed-route bus service.
  - Connector collection rule: never add a bus/rail connector to a suspicious
    same-name port. Fix `portName + operator/route context + coordinate` first,
    then attach official bus/rail access.
  - Identity cleanup batch:
    - Replaced weak same-name geocoder matches for major ports including
      戸畑, 神湊, 長崎港, 佐伯, 呼子, 三津浜港, 青森港, 新潟港,
      大洗港, 宮崎港, 苫小牧西港, 白水港, 笠岡, 尾道港, 福江港,
      平戸港, 瀬相, 生間, 笛吹, and 郷ノ首.
    - Corrected the 三洋汽船 source label `飛鳥` to the real route name
      `飛島` using official 三洋汽船 and 笠岡観光WEB route context.
  - Route/operator-specific identity split:
    - Cleared the remaining 5 identity-first red lights: 大島港, 姫島, 久賀,
      因島西浜港, and 柳.
    - Generic same-name endpoints now resolve to distinct playable/map ports
      such as 宗像大島港, 新居浜大島港, 壱岐大島港, 的山港,
      大分姫島港, 糸島姫島港, 周防大島久賀港, 五島久賀港,
      西浜港, 小値賀柳港, and 佐世保柳港.
    - The old ambiguous endpoint names have 0 promoted sailings in the current
      timetable bundle, so later connector work cannot accidentally attach a
      mainland bus stop to the wrong island port.

## Current Official Source Files

- `data/v5_ship_seikan_ferry_official.json`
- `data/v5_ship_priority_batch_official.json`
- `data/v5_ship_long_distance_batch_official.json`
- `data/v5_ship_expansion_to_70_official.json`
- `data/v5_ship_expansion_to_150_source_inventory.json`
- `data/v5_ship_expansion_150_map_batch1_official.json`
- `data/v5_ship_expansion_to_193_source_inventory.json`
- `data/v5_ship_map_to_193_official.json`
- `data/v5_ship_playable_400_batch_official.json`
- `data/v5_ship_playable_500_batch_official.json`
- Builder: `scripts/ingest/build_v5_ship_map.py`
- Playable timetable builder: `scripts/ingest/build_v5_ship_timetable_bundle.py`
