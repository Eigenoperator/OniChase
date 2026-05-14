# OniChase V5 Plan

V5 expands OniChase from nationwide rail gameplay into a real Japanese public-transportation chase simulator. The target is not a minimal transport add-on. The target is a coherent multimodal game where trains, walking, aircraft, ferries, and buses are all first-class systems with explicit data contracts and gameplay rules.

## Product Direction

- Core direction: realistic Japanese transportation simulation first.
- Game rule: both runner and hunter can use all public transportation modes.
- V4 rail planning remains the railway baseline: choose line, choose train, choose alighting station.
- Non-rail modes can use mode-specific planning UI when the real workflow is different.
- Fares remain a count-up ledger in v5 unless a later rule explicitly turns cost into a constraint.
- Capture remains same node or same station. Distance-radius capture is not part of the current v5 rule.

## Modes

### Rail

Rail starts from v4:

- Nationwide railway substrate.
- Real weekday timetable.
- Three-step planner.
- Real path selected-train highlighting.
- Fare ledger and Shinkansen premium baseline.

V5 rail work should focus on integration with the multimodal graph, not rewriting the rail model.

### Walking

Walking becomes a real movement mode:

- Any station can connect by walking to any other station within `2 km`.
- Walking speed is fixed and may be faster than ordinary human walking for gameplay pacing.
- Walking edges are generated from station/node coordinates, not manually enumerated transfer pairs.
- Walking time is mandatory in planning and live simulation.
- Walking fare is `0`.

Walking is the first major v5 system because it changes the graph from line-only rail gameplay into a true multimodal network.

### Aircraft

Aircraft are intentionally powerful and strictly limited:

- Both players can use flights.
- Tickets must be bought at least `1 hour` before departure.
- Buying a plane ticket is immediately revealed to the opponent.
- Flight planning must include access to the airport, airport buffer time, flight time, and exit from the destination airport.
- Plane fares are counted in the ledger but do not constrain choices unless a later rule changes this.

Open design question:

- Whether the opponent sees only the airport pair, the exact flight, or the full planned air leg.

### Ferries And Ships

V5 should support all real public ferry/ship services that matter for Japanese mobility:

- Long-distance ferries.
- Island ferries.
- Urban ferries.
- Airport/port-access boats where they are public transportation.

Ship planning should include port nodes, sailing timetable, boarding buffer, and destination port arrival. Seasonal and weather-dependent operations should be represented when the source data supports it.

### Buses

V5 should include both long-distance and short-distance buses:

- Highway buses and airport buses are high-priority.
- City buses are also in scope, but the data burden is much higher.
- The data model must distinguish long-distance scheduled bus services from dense local route buses.

Bus planning UI may need a different workflow from trains because bus stops are denser, route names are less stable, and stop-direction matters more.

## Planning UX

Rail remains the v4 three-page flow:

1. Choose line.
2. Choose train.
3. Choose alighting station.

Other modes can diverge:

- Walking: choose reachable destination node, show time and distance.
- Aircraft: choose airport, choose flight, confirm ticket purchase and reveal.
- Ferry: choose port/route, choose sailing, choose destination port.
- Bus: likely choose stop/route/direction, then choose departure.

The planner should present mode choice as part of the current location context, not as a separate disconnected page.

## Time Rules

V5 uses real transfer time rather than instant switching:

- Walking time is calculated from distance and fixed walking speed.
- Rail-to-rail transfers keep station-change time.
- Airport access and boarding buffer are mandatory.
- Ferry boarding buffer is mandatory.
- Bus boarding is usually shorter but still nonzero.

Exact default transfer times are not fixed yet and should be tuned after the first multimodal graph exists.

## Data Strategy

Default policy: source strategy A.

- Use reliable official or operator-published sources whenever possible.
- Do not fabricate missing public-transport schedules.
- If a source is partial, mark the limitation in the data, do not silently fill it with guesses.

Fallback policy B can be considered case by case:

- Public aggregators may be used when official sources are inaccessible, fragmented, or not machine-readable.
- Aggregator-derived data must be tagged with source type and confidence.
- Aggregator data should not overwrite official data without an overlap audit.

Policy C is only for gameplay rules, not real transit facts:

- Manual gameplay rules may define buffers, reveal mechanics, walking speed, or capture logic.
- Manual rules must not pretend to be real timetable, fare, or route data.
- Any synthetic transport edge must be visibly marked as synthetic or rule-derived.

## V5 First Build Order

Recommended order:

1. Multimodal node model.
2. Walking edges between all station nodes within `2 km`.
3. Planner support for walking and transfer time.
4. Airport nodes and flight data model.
5. Plane ticket purchase rule with 1-hour advance purchase and opponent reveal.
6. Ferry/ship route model.
7. Highway/airport bus model.
8. Dense city-bus strategy.

This order makes walking the foundation before adding long-jump modes like aircraft.

## Open Questions

- Starting node policy: stations only, or any public transport node including airports, ports, and bus stops.
- Plane reveal detail: exact flight, airport pair, or only airport intent.
- Default walking speed.
- Default transfer buffers per mode.
- Whether flight and ferry availability should use weekday-only data initially or date-specific calendars.
- Whether city buses are national from the start or phased by region/operator reliability.
