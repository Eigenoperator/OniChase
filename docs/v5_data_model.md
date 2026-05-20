# OniChase V5 Data Model

V5 needs a multimodal graph. Rail remains important, but it becomes one mode in a wider public-transportation network.

## Core Entities

### Transport Node

A transport node is any point where a player can board, alight, transfer, or be captured.

Fields:

- `id`
- `name`
- `modeTypes`
- `lat`
- `lon`
- `nodeType`
- `operatorIds`
- `sourceRefs`
- `captureGroupId`

Node types:

- `rail_station`
- `airport`
- `port`
- `bus_stop`
- `walking_anchor`

Stations with the same capture semantics can share a `captureGroupId`. V4 station groups become the initial rail capture groups.

### Transport Service

A transport service is a scheduled public transportation service.

Fields:

- `id`
- `mode`
- `operatorId`
- `routeName`
- `serviceName`
- `originNodeId`
- `destinationNodeId`
- `stops`
- `calendar`
- `fareRuleRefs`
- `sourceRefs`
- `confidence`

Modes:

- `rail`
- `walking`
- `flight`
- `ferry`
- `bus_long_distance`
- `bus_local`

Walking is represented as a generated service-like edge for planner consistency, but it is not a public timetable service.

### Scheduled Stop

Fields:

- `nodeId`
- `sequence`
- `arrivalTimeSec`
- `departureTimeSec`
- `boardingAllowed`
- `alightingAllowed`
- `minimumBoardingBufferSec`
- `minimumTransferBufferSec`

### Movement Leg

A planned or executed leg records what the player committed to.

Fields:

- `mode`
- `serviceId`
- `fromNodeId`
- `toNodeId`
- `departTimeSec`
- `arriveTimeSec`
- `distanceMeters`
- `fare`
- `revealPolicy`
- `sourceRefs`

## Walking Model

Walking edges are generated between nodes within the maximum `5 km` walking layer and then filtered at runtime by the active layer.

Fields:

- `fromNodeId`
- `toNodeId`
- `distanceMeters`
- `sourceWalkTimeSec`
- `sourceSpeedMetersPerSecond`
- `directed`
- `source`

Rules:

- Walking can connect any station to any other station within the selected layer.
- Supported initial layers are `500`, `1000`, `2000`, `3000`, and `5000` meters.
- The first generated artifact is `data/v5_walking_edges.json.gz`; its audit summary is `data/v5_walking_edge_audit.json`.
- The v1 distance model is station-group centroid Haversine distance, not road-network walking geometry.
- Gameplay walking time is calculated at runtime from `distanceMeters / walkingSpeedMetersPerSecondFor(playerId, context)`.
- The current default returned by the speed function is `5 km/h` (`1.389 m/s`).
- Walking speed is a continuous function, not a fixed option set, because later stamina/fatigue systems may reduce a player's current speed.
- Walking can later connect stations, airports, ports, and bus stops if node geometry supports it.
- Walking fare is always `0`.
- Walking speed is a gameplay rule, not a real-world claim.

## Flight Model

Flights are scheduled services with strict gameplay constraints.

Required data:

- Airport nodes.
- Flight number.
- Airline/operator.
- Origin airport.
- Destination airport.
- Scheduled departure.
- Scheduled arrival.
- Calendar.
- Fare source if available.

Gameplay fields:

- `advancePurchaseRequiredSec`: default `3600`.
- `revealOnPurchase`: `true`.
- `revealPayload`: undecided.
- `airportAccessBufferSec`: configurable.
- `airportExitBufferSec`: configurable.

Rule:

If a player buys a plane ticket, the opponent is notified immediately.

## Ferry And Ship Model

Ferry services are scheduled public transportation between port nodes.

Required data:

- Port nodes.
- Route/operator.
- Sailing timetable.
- Boarding and alighting ports.
- Calendar and seasonal notes.
- Fare rule if available.

Fields:

- `boardingBufferSec`
- `weatherOrSeasonNote`
- `vehicleType`

Gameplay rules:

- Ships do not require advance ticket purchase.
- Ships do not require an arrival-at-port buffer in the current rule set.
- Long-distance and night ferries reveal boarding to the opponent.
- Urban ferries and short island ferries do not reveal by default.
- Weather is not modeled; scheduled services run according to their calendar.
- Cross-day ferry arrivals are allowed and stored by carrying arrival minutes
  past 24:00, the same time-axis convention used by flights and night buses.
- Port names shown to players are real names, not artificial three-letter
  codes.

Urban ferries and long-distance ferries use the same service model, but the
`serviceClass` / `vehicleType` metadata decides reveal policy and UI grouping.

## Bus Model

Buses are first-class real scheduled services. V5 bus data must not be
hand-authored as gameplay shortcuts; it must come from public GTFS/GTFS-JP
feeds or operator/municipality official sources that can be rebuilt.

Initial release artifact:

- `data/v5_bus_gtfs_current_bundle.json.gz`
- `data/v5_bus_gtfs_audit.json`
- Builder: `scripts/ingest/build_v5_bus_gtfs_bundle.py`

Primary source:

- Public GTFS data repository feeds indexed by
  `data/v4_gtfs_repository_route_index.json`.
- Only GTFS `route_type=3` bus feeds are ingested by the first builder.
- Original feed metadata, license id, valid date range, page URL, and file URL
  are preserved as `sourceRefs`.

Buses are split into three gameplay service classes:

- `bus_airport`
- `bus_long_distance`
- `bus_local`

The class is metadata for planner grouping and UI. It must never alter the
source route, stop, trip, calendar, fare, or geometry data.

Gameplay fields:

- `advancePurchaseRequiredSec`: `0` for all bus classes in the current gameplay
  model.
- `revealOnPurchase`: `false` for all bus classes in the current gameplay
  model.
- `sameVehicleCapture`: `true`.
- `sameNodeCapture`: `true` at the same bus stop/capture node.
- `allowCrossDayArrival`: `true`.
- `accessMode`: walking connector from the current rail station, airport, port,
  or bus stop to the boarding bus stop.

Bus planning is anchored around the current player state or plan tail:

1. Find reachable bus stops around the current node using walking connectors.
2. Show route/direction candidates from those stops.
3. Show real departures after the effective current time.
4. Show alighting stops downstream on the selected trip.

The web client must not load the full bus GTFS timetable for map display. The
map uses the tiled `data/v5_bus_map_tiles/` layer; trip planning should use a
separate planner index so the 2M+ stop-time source table does not block
interaction.

### Long-Distance And Airport Bus

Use a scheduled-service model close to rail/ferry:

- Known terminal nodes.
- Fixed departure and arrival times.
- Seat/reservation policy when available.
- Route-level fare source.
- Airport buses are especially important because many airports have no rail
  station. They should be audited against every airport node, not only against
  feeds that happen to contain the word "airport".
- Highway/night buses do not need a gameplay ticket purchase in the current
  rule set. They are boarded like other buses after reaching the stop in time.
- Cross-day highway/night bus arrivals are allowed.
- Airport buses are freely selectable alongside rail airport access when both
  exist.

### Local Bus

Local buses need denser stop data and direction-sensitive routing:

- Stop pairs are closer together.
- Route variants are common.
- Timetable volume is much larger.
- Official data availability varies heavily by operator.
- Buses do not need advance purchase in the current gameplay model. They are
  boarded like rail after walking to the bus stop in time.
- The planner should only show local bus choices around the current player
  state or plan tail, not a nationwide list.

Local bus ingestion must preserve source confidence and should not overwrite better official data.

### Bus Stop Connectors

Bus stops connect to other modes through generated walking connectors:

- bus stop -> rail station group
- bus stop -> airport
- bus stop -> port, once ferry/port nodes exist

Connector rules:

- Coordinates are required; stops without coordinates are retained but cannot
  receive walking connectors.
- Connector distance is generated from geometry and never hand-prepared.
- GTFS `transfers.txt`, when present, is preserved as a source transfer table.
- Runtime walking speed uses the same continuous walking speed function as the
  walking system.
- The first connector generator uses Haversine distance, matching the current
  station walking layer. Road-network walking can replace this later without
  changing the public bundle schema.

## Fare Model

V5 fare remains a ledger:

- Fares count up.
- Fares do not restrict movement by default.
- Unknown fare stays unknown rather than estimated.

Fare source types:

- `ordinary_distance_table`
- `station_pair_table`
- `zone_table`
- `product_fare`
- `dynamic_or_search_result`
- `unknown`

Policy:

- Official sources are preferred.
- Aggregator sources may be tagged as fallback.
- Gameplay costs are separate from real fares.

## Reveal Model

Most movement is not automatically revealed.

Flight ticket purchase is the first explicit reveal rule:

- Buying a flight at least 1 hour in advance reveals the purchase immediately.
- The exact reveal payload is still open.

Candidate reveal payloads:

- `airport_pair_only`
- `departure_airport_and_time`
- `exact_flight`

## Capture Model

Capture remains node-based:

- Same station.
- Same transport node.
- Same capture group.

Nearby-distance capture is not part of the current v5 rule.

## Source Confidence

Every ingested source should record:

- `sourceType`: official, aggregator, manual_rule, synthetic.
- `sourceUrl`
- `retrievedAt`
- `validFrom`
- `validTo`
- `coverage`
- `knownLimitations`

Overlap rule:

When adding a new source, check overlap against existing data before replacing or merging it. New data must not silently erase old valid data.
