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
- `walkTimeSec`
- `speedMetersPerSecond`
- `directed`
- `source`

Rules:

- Walking can connect any station to any other station within the selected layer.
- Supported initial layers are `500`, `1000`, `2000`, `3000`, and `5000` meters.
- The first generated artifact is `data/v5_walking_edges.json.gz`; its audit summary is `data/v5_walking_edge_audit.json`.
- The v1 distance model is station-group centroid Haversine distance, not road-network walking geometry.
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

Urban ferries and long-distance ferries use the same service model, but may have different default buffers.

## Bus Model

Buses are split into two classes.

### Long-Distance And Airport Bus

Use a scheduled-service model close to rail/ferry:

- Known terminal nodes.
- Fixed departure and arrival times.
- Seat/reservation policy when available.
- Route-level fare source.

### Local Bus

Local buses need denser stop data and direction-sensitive routing:

- Stop pairs are closer together.
- Route variants are common.
- Timetable volume is much larger.
- Official data availability varies heavily by operator.

Local bus ingestion must preserve source confidence and should not overwrite better official data.

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
