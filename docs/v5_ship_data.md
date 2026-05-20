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
- The artifact is intentionally empty until official ferry data is collected.
- No fake port or route is included.

