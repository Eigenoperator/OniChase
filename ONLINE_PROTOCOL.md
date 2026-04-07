# ONLINE PROTOCOL

## Room Object

```json
{
  "room_id": "AB12CD",
  "phase": "PLANNING",
  "start_time_hhmm": "06:00",
  "end_time_hhmm": "18:00",
  "current_game_minute": 360,
  "next_planning_minute": 420,
  "players": {
    "runner": {
      "connected": true,
      "display_name": "Runner",
      "ready": false,
      "start_station_id": "SG_TOKYO",
      "steps": []
    },
    "hunter": {
      "connected": true,
      "display_name": "Hunter",
      "ready": false,
      "start_station_id": "SG_SHIN_OSAKA",
      "steps": []
    }
  }
}
```

## Seat Names

- `runner`
- `hunter`

## Endpoints

### `POST /api/rooms`

Create a room.

Request:

```json
{
  "start_time_hhmm": "06:00",
  "end_time_hhmm": "18:00"
}
```

Response:

```json
{
  "room_id": "AB12CD",
  "phase": "PLANNING"
}
```

### `POST /api/rooms/{room_id}/join`

Claim a seat.

Request:

```json
{
  "seat": "runner",
  "display_name": "Scorp"
}
```

### `GET /api/rooms/{room_id}/state?seat=runner`

Fetch seat-scoped room state.

The server must filter visibility based on seat and current phase.

### `POST /api/rooms/{room_id}/plan`

Submit a full plan for one seat.

Request:

```json
{
  "seat": "runner",
  "start_station_id": "SG_TOKYO",
  "steps": [
    { "type": "BOARD_TRAIN", "trip_id": "TRIP_00002" },
    { "type": "RIDE_TO_STATION", "station_id": "SG_SHIN_OSAKA" }
  ]
}
```

### `POST /api/rooms/{room_id}/ready`

Mark ready or not ready.

Request:

```json
{
  "seat": "runner",
  "ready": true
}
```

### `POST /api/rooms/{room_id}/start`

Used only during planning. The server will start `LIVE` when both seats are ready.

Request:

```json
{
  "seat": "runner"
}
```

## Projection Rules

The state response should include:

- `room`
- `self`
- `opponent`
- `public_match`

`opponent` must already be filtered.

Example:

- hunter during planning sees runner station if runner is at node
- hunter during planning sees only coarse in-transit hint if runner is on train
- hunter during live sees no private runner location

## First Transport Decision

Use plain HTTP + polling first.

Reasons:

- simpler to debug
- easier to inspect with browser devtools and curl
- enough for turn-like planning and minute-based live progression

Later:

- keep the same room/state protocol
- replace polling with WebSocket push
