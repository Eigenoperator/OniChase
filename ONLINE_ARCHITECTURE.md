# ONLINE ARCHITECTURE

## Goal

The first online version of OniChase should let two human players play the same `v2` match from separate browsers while the server remains authoritative over:

- room membership
- role ownership (`runner` / `hunter`)
- phase transitions (`PLANNING` / `LIVE` / `ENDED`)
- current game time
- accepted plans
- visibility filtering
- capture resolution

This avoids two critical problems:

1. clients seeing information they should not see
2. runner and hunter drifting into inconsistent local states

## Recommended Shape

Use a room-based authoritative server.

- frontend: browser UI derived from current `v2`
- server: Python in-memory room service
- transport: JSON over HTTP first, WebSocket later

The first milestone does not need login, persistence, or public matchmaking.

## Phase 1 Scope

Phase 1 should support:

- create a room
- join as `runner` or `hunter`
- inspect room state from one seat's perspective
- submit a full plan for one seat
- mark one seat as ready during planning
- start the live phase once both seats are ready

Phase 1 does not need:

- reconnect recovery
- spectator mode
- database persistence
- cross-room matchmaking
- production auth

## Authority Model

The server stores one canonical match state per room.

Clients never decide:

- whether a capture happened
- what the opponent can see
- when planning ends
- whether an hourly replanning breakpoint has been reached

Clients may only propose actions:

- plan submission
- ready/unready
- start vote

## State Projection

The server should never broadcast the exact same payload to both players.

Instead it should derive:

- `runner_view`
- `hunter_view`

For example in `hunter_view`:

- during `PLANNING`
  - if runner is at a station, reveal the station
  - if runner is on a train, reveal only the map marker / coarse in-transit position
- during `LIVE`
  - hide runner private state

## Room Lifecycle

1. Room is created.
2. Players claim seats.
3. Server enters initial `PLANNING`.
4. Both seats submit plans and become ready.
5. Server enters `LIVE`.
6. Every in-game hour the server returns to `PLANNING`.
7. The cycle repeats until capture or end time.

## Integration Path

Phase 1 should keep the current `v2` UI mostly intact.

Replace only these pieces:

- local test preset state
- local phase state
- local plan storage
- local replay/result source

With server-backed versions:

- room state fetch
- seat-scoped plan submission
- ready/start actions
- server-returned replay/result payload

## Recommended Next Steps

1. Add a minimal in-memory room server.
2. Define a room protocol in one document.
3. Keep the first transport simple: HTTP polling.
4. Upgrade to WebSocket only after the room flow is stable.
