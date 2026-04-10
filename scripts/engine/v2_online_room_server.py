#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import random
import string
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = ROOT / "data" / "v3_shinkansen_bundle.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def hhmm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def minutes_to_hhmm(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def stop_arrival_minutes(stop: dict[str, Any]) -> int:
    return int((stop.get("arrivalTimeSec") if stop.get("arrivalTimeSec") is not None else stop["departureTimeSec"]) / 60)


def stop_departure_minutes(stop: dict[str, Any]) -> int:
    return int((stop.get("departureTimeSec") if stop.get("departureTimeSec") is not None else stop["arrivalTimeSec"]) / 60)


def make_room_id() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(6))


def make_session_token() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(24))


BUNDLE = load_json(BUNDLE_PATH)
TRIP_LOOKUP = {trip["id"]: trip for trip in BUNDLE["tripInstances"]}
STATION_GROUP_LOOKUP = {group["id"]: group for group in BUNDLE["stationGroups"]}


@dataclass
class SeatState:
    seat: str
    connected: bool = False
    display_name: str | None = None
    session_token: str | None = None
    ready: bool = False
    start_station_id: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RoomState:
    room_id: str
    start_time_hhmm: str = "06:00"
    end_time_hhmm: str = "18:00"
    phase: str = "PLANNING"
    current_game_minute: int = 360
    next_planning_minute: int = 420
    players: dict[str, SeatState] = field(
        default_factory=lambda: {
            "runner": SeatState(seat="runner", start_station_id="SG_TOKYO"),
            "hunter": SeatState(seat="hunter", start_station_id="SG_SHIN_OSAKA"),
        }
    )
    phase_started_monotonic: float = field(default_factory=time.monotonic)
    planning_deadline_monotonic: float | None = None
    match_started: bool = False
    live_capture: dict[str, Any] | None = None

    def reset_ready(self) -> None:
        for player in self.players.values():
            player.ready = False


def station_group_label(station_group_id: str | None) -> str | None:
    if not station_group_id:
        return None
    group = STATION_GROUP_LOOKUP.get(station_group_id)
    if not group:
        return station_group_id
    return group.get("primaryName") or station_group_id


def find_boarding_stop(trip: dict[str, Any], station_group_id: str, earliest_minute: int) -> dict[str, Any] | None:
    matches = [
        stop for stop in trip["stopTimes"]
        if stop["stationGroupId"] == station_group_id and stop_departure_minutes(stop) >= earliest_minute
    ]
    if not matches:
        return None
    matches.sort(key=stop_departure_minutes)
    return matches[0]


def find_alight_stop(trip: dict[str, Any], boarded_sequence: int, station_group_id: str) -> dict[str, Any] | None:
    for stop in trip["stopTimes"]:
        if stop["sequence"] <= boarded_sequence:
            continue
        if stop["stationGroupId"] != station_group_id:
            continue
        return stop
    return None


def segment_position(from_station_group_id: str, to_station_group_id: str, progress: float) -> dict[str, Any]:
    return {
        "kind": "SEGMENT",
        "from_station_group_id": from_station_group_id,
        "to_station_group_id": to_station_group_id,
        "progress": max(0.0, min(1.0, progress)),
    }


def station_position(station_group_id: str) -> dict[str, Any]:
    return {"kind": "STATION", "station_group_id": station_group_id}


def preview_player_for_room(room: RoomState, seat: str, time_cap_minute: int) -> dict[str, Any]:
    player = room.players[seat]
    current_minute = hhmm_to_minutes(room.start_time_hhmm)
    current_state: dict[str, Any] = {"kind": "NODE", "station_group_id": player.start_station_id}
    current_trip: dict[str, Any] | None = None
    current_board_stop: dict[str, Any] | None = None

    for step in player.steps:
        if step["type"] == "WAIT_UNTIL":
            target_minute = hhmm_to_minutes(step["until_hhmm"])
            if target_minute > time_cap_minute:
                break
            current_minute = target_minute
            continue

        if step["type"] == "BOARD_TRAIN":
            if current_state["kind"] != "NODE":
                break
            trip = TRIP_LOOKUP.get(step["trip_id"])
            if trip is None:
                break
            board_stop = find_boarding_stop(trip, current_state["station_group_id"], current_minute)
            if board_stop is None:
                break
            board_minute = stop_departure_minutes(board_stop)
            if board_minute > time_cap_minute:
                break
            current_minute = board_minute
            current_state = {"kind": "TRAIN", "trip_id": trip["id"]}
            current_trip = trip
            current_board_stop = board_stop
            continue

        if step["type"] == "RIDE_TO_STATION":
            if current_state["kind"] != "TRAIN" or current_trip is None or current_board_stop is None:
                break
            alight_stop = find_alight_stop(current_trip, current_board_stop["sequence"], step["station_id"])
            if alight_stop is None:
                break
            arrival_minute = stop_arrival_minutes(alight_stop)
            if arrival_minute > time_cap_minute:
                previous_stop = current_board_stop
                next_stop = alight_stop
                departure_minute = stop_departure_minutes(previous_stop)
                if arrival_minute == departure_minute:
                    progress = 1.0
                else:
                    progress = (time_cap_minute - departure_minute) / (arrival_minute - departure_minute)
                return {
                    "time_hhmm": minutes_to_hhmm(time_cap_minute),
                    "kind": "TRAIN",
                    "trip_id": current_trip["id"],
                    "service_label": format_trip_label(current_trip),
                    "station_group_id": None,
                    "map_position": segment_position(previous_stop["stationGroupId"], next_stop["stationGroupId"], progress),
                }
            current_minute = arrival_minute
            current_state = {"kind": "NODE", "station_group_id": alight_stop["stationGroupId"]}
            current_trip = None
            current_board_stop = None

    if current_state["kind"] == "NODE":
        station_group_id = current_state["station_group_id"]
        return {
            "time_hhmm": minutes_to_hhmm(time_cap_minute),
            "kind": "NODE",
            "station_group_id": station_group_id,
            "station_label": station_group_label(station_group_id),
            "map_position": station_position(station_group_id),
        }

    trip = current_trip
    if trip is not None and current_board_stop is not None:
        next_stop = None
        for stop in trip["stopTimes"]:
            if stop["sequence"] > current_board_stop["sequence"]:
                next_stop = stop
                break
        if next_stop is not None:
            departure_minute = stop_departure_minutes(current_board_stop)
            arrival_minute = stop_arrival_minutes(next_stop)
            if arrival_minute == departure_minute:
                progress = 1.0
            else:
                progress = (time_cap_minute - departure_minute) / (arrival_minute - departure_minute)
            map_position = segment_position(current_board_stop["stationGroupId"], next_stop["stationGroupId"], progress)
        else:
            map_position = station_position(current_board_stop["stationGroupId"])
    else:
        map_position = None

    return {
        "time_hhmm": minutes_to_hhmm(time_cap_minute),
        "kind": "TRAIN",
        "trip_id": current_state["trip_id"],
        "service_label": format_trip_label(TRIP_LOOKUP[current_state["trip_id"]]),
        "station_group_id": None,
        "map_position": map_position,
    }


def format_trip_label(trip: dict[str, Any]) -> str:
    name = trip.get("serviceName") or trip["id"]
    number = trip.get("serviceNumber")
    return f"{name} {number}".strip()


def detect_capture_at_minute(room: RoomState, minute: int) -> dict[str, Any] | None:
    runner = preview_player_for_room(room, "runner", minute)
    hunter = preview_player_for_room(room, "hunter", minute)
    if runner["kind"] == "TRAIN" and hunter["kind"] == "TRAIN" and runner["trip_id"] == hunter["trip_id"]:
        return {"type": "same_train", "time_hhmm": minutes_to_hhmm(minute), "trip_id": runner["trip_id"]}
    if runner["kind"] == "NODE" and hunter["kind"] == "NODE" and runner["station_group_id"] == hunter["station_group_id"]:
        return {"type": "same_node", "time_hhmm": minutes_to_hhmm(minute), "station_group_id": runner["station_group_id"]}
    return None


def project_presence_for_viewer(room: RoomState, target_seat: str, viewer_seat: str) -> dict[str, Any]:
    preview = preview_player_for_room(room, target_seat, room.current_game_minute)
    if target_seat == viewer_seat:
        return {"visibility": "full", **preview}

    if room.phase == "LIVE":
        return {"visibility": "hidden", "kind": "HIDDEN", "time_hhmm": preview["time_hhmm"], "map_position": None}

    if preview["kind"] == "NODE":
        return {
            "visibility": "station",
            "kind": "NODE",
            "time_hhmm": preview["time_hhmm"],
            "station_group_id": preview["station_group_id"],
            "station_label": preview["station_label"],
            "map_position": preview["map_position"],
        }

    return {
        "visibility": "segment",
        "kind": "TRAIN",
        "time_hhmm": preview["time_hhmm"],
        "map_position": preview["map_position"],
    }


def advance_room(room: RoomState) -> None:
    if room.phase == "PLANNING" and room.match_started and room.planning_deadline_monotonic is not None:
        now = time.monotonic()
        if now >= room.planning_deadline_monotonic:
            room.phase = "LIVE"
            room.phase_started_monotonic = now
            room.planning_deadline_monotonic = None
            room.live_capture = detect_capture_at_minute(room, room.current_game_minute)
            if room.live_capture:
                room.phase = "ENDED"
        return
    if room.phase != "LIVE":
        return
    now = time.monotonic()
    elapsed_minutes = int(now - room.phase_started_monotonic)
    end_minute = hhmm_to_minutes(room.end_time_hhmm)
    if elapsed_minutes <= 0:
        return
    target_minute = min(room.current_game_minute + elapsed_minutes, end_minute)
    room.phase_started_monotonic = now

    while room.current_game_minute < target_minute and room.phase == "LIVE":
        room.current_game_minute += 1
        capture = detect_capture_at_minute(room, room.current_game_minute)
        if capture:
            room.live_capture = capture
            room.phase = "ENDED"
            room.match_started = True
            return
        if room.current_game_minute >= end_minute:
            room.phase = "ENDED"
            room.match_started = True
            return
        if room.current_game_minute >= room.next_planning_minute:
            room.phase = "PLANNING"
            room.reset_ready()
            room.planning_deadline_monotonic = time.monotonic() + 60
            room.next_planning_minute = min(room.next_planning_minute + 60, end_minute)
            return


class RoomRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rooms: dict[str, RoomState] = {}

    def create_room(self, start_time_hhmm: str, end_time_hhmm: str) -> RoomState:
        with self._lock:
            room_id = make_room_id()
            while room_id in self._rooms:
                room_id = make_room_id()
            room = RoomState(
                room_id=room_id,
                start_time_hhmm=start_time_hhmm,
                end_time_hhmm=end_time_hhmm,
                current_game_minute=hhmm_to_minutes(start_time_hhmm),
                next_planning_minute=min(hhmm_to_minutes(start_time_hhmm) + 60, hhmm_to_minutes(end_time_hhmm)),
                phase_started_monotonic=time.monotonic(),
            )
            self._rooms[room_id] = room
            return room

    def get(self, room_id: str) -> RoomState | None:
        with self._lock:
            room = self._rooms.get(room_id)
            if room:
                advance_room(room)
            return room

    def join(self, room_id: str, seat: str, display_name: str | None, session_token: str | None = None) -> tuple[RoomState, str]:
        with self._lock:
            room = self._rooms[room_id]
            advance_room(room)
            player = room.players[seat]
            if player.connected and player.session_token and player.session_token != session_token:
                raise ValueError("seat_occupied")
            player.connected = True
            if display_name:
                player.display_name = display_name
            if player.session_token is None:
                player.session_token = session_token or make_session_token()
            return room, player.session_token

    def authorize(self, room_id: str, seat: str, session_token: str | None) -> RoomState:
        with self._lock:
            room = self._rooms[room_id]
            advance_room(room)
            player = room.players[seat]
            if player.session_token is None or session_token != player.session_token:
                raise PermissionError("invalid_token")
            return room

    def submit_plan(self, room_id: str, seat: str, start_station_id: str | None, steps: list[dict[str, Any]]) -> RoomState:
        with self._lock:
            room = self._rooms[room_id]
            advance_room(room)
            player = room.players[seat]
            if start_station_id is not None:
                player.start_station_id = start_station_id
            player.steps = steps
            player.ready = False
            return room

    def set_ready(self, room_id: str, seat: str, ready: bool) -> RoomState:
        with self._lock:
            room = self._rooms[room_id]
            advance_room(room)
            room.players[seat].ready = ready
            if all(player.ready for player in room.players.values()):
                now = time.monotonic()
                if not room.match_started:
                    room.match_started = True
                    room.phase = "PLANNING"
                    room.phase_started_monotonic = now
                    room.planning_deadline_monotonic = now + 60
                    room.live_capture = None
                    room.reset_ready()
                elif room.phase == "PLANNING":
                    room.phase = "LIVE"
                    room.phase_started_monotonic = now
                    room.planning_deadline_monotonic = None
                    room.live_capture = detect_capture_at_minute(room, room.current_game_minute)
                    if room.live_capture:
                        room.phase = "ENDED"
            return room

    def try_start(self, room_id: str, seat: str) -> RoomState:
        with self._lock:
            room = self._rooms[room_id]
            advance_room(room)
            room.players[seat].ready = True
            if room.phase == "PLANNING" and room.match_started and all(player.ready for player in room.players.values()):
                room.phase = "LIVE"
                room.phase_started_monotonic = time.monotonic()
                room.planning_deadline_monotonic = None
                room.live_capture = detect_capture_at_minute(room, room.current_game_minute)
                if room.live_capture:
                    room.phase = "ENDED"
            return room


REGISTRY = RoomRegistry()


def room_payload(room: RoomState, viewer_seat: str | None = None) -> dict[str, Any]:
    players_summary = {
        seat: {
            "seat": player.seat,
            "connected": player.connected,
            "display_name": player.display_name,
            "ready": player.ready,
        }
        for seat, player in room.players.items()
    }
    payload = {
        "room_id": room.room_id,
        "phase": room.phase,
        "start_time_hhmm": room.start_time_hhmm,
        "end_time_hhmm": room.end_time_hhmm,
        "current_game_minute": room.current_game_minute,
        "current_time_hhmm": minutes_to_hhmm(room.current_game_minute),
        "next_planning_minute": room.next_planning_minute,
        "next_planning_hhmm": minutes_to_hhmm(room.next_planning_minute),
        "match_started": room.match_started,
        "capture": room.live_capture,
        "planning_seconds_remaining": (
            max(0, int(room.planning_deadline_monotonic - time.monotonic()))
            if room.phase == "PLANNING" and room.match_started and room.planning_deadline_monotonic is not None
            else None
        ),
        "players": players_summary,
        "viewer_seat": viewer_seat,
    }
    if viewer_seat in {"runner", "hunter"}:
        self_player = room.players[viewer_seat]
        other_seat = "hunter" if viewer_seat == "runner" else "runner"
        payload["self"] = {
            **players_summary[viewer_seat],
            "start_station_id": self_player.start_station_id,
            "steps": self_player.steps,
            "session_token": self_player.session_token,
            "presence": project_presence_for_viewer(room, viewer_seat, viewer_seat),
        }
        payload["opponent"] = {
            **players_summary[other_seat],
            "presence": project_presence_for_viewer(room, other_seat, viewer_seat),
        }
    return payload


class RoomRequestHandler(BaseHTTPRequestHandler):
    server_version = "OniChaseRoomServer/0.2"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path_parts = [part for part in parsed.path.split("/") if part]
        if parsed.path == "/health":
            self._send_json(HTTPStatus.OK, {"ok": True, "dataset_id": BUNDLE.get("metadata", {}).get("datasetId")})
            return
        if len(path_parts) == 4 and path_parts[0] == "api" and path_parts[1] == "rooms" and path_parts[3] == "state":
            room_id = path_parts[2]
            room = REGISTRY.get(room_id)
            if room is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "room_not_found"})
                return
            query = parse_qs(parsed.query)
            seat = query.get("seat", [None])[0]
            token = query.get("token", [None])[0]
            if seat in {"runner", "hunter"}:
                try:
                    room = REGISTRY.authorize(room_id, seat, token)
                except PermissionError:
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid_token"})
                    return
            self._send_json(HTTPStatus.OK, {"room": room_payload(room, seat)})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path_parts = [part for part in parsed.path.split("/") if part]
        body = self._read_json()

        if parsed.path == "/api/rooms":
            room = REGISTRY.create_room(
                start_time_hhmm=body.get("start_time_hhmm", "06:00"),
                end_time_hhmm=body.get("end_time_hhmm", "18:00"),
            )
            self._send_json(HTTPStatus.CREATED, {"room": room_payload(room), "bundle_metadata": BUNDLE.get("metadata", {})})
            return

        if len(path_parts) != 4 or path_parts[0] != "api" or path_parts[1] != "rooms":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        room_id = path_parts[2]
        action = path_parts[3]
        room = REGISTRY.get(room_id)
        if room is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "room_not_found"})
            return

        if action == "join":
            seat = body.get("seat")
            if seat not in {"runner", "hunter"}:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_seat"})
                return
            try:
                room, token = REGISTRY.join(room_id, seat, body.get("display_name"), body.get("token"))
            except ValueError:
                self._send_json(HTTPStatus.CONFLICT, {"error": "seat_occupied"})
                return
            self._send_json(HTTPStatus.OK, {"room": room_payload(room, seat), "token": token})
            return

        if action == "plan":
            seat = body.get("seat")
            if seat not in {"runner", "hunter"}:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_seat"})
                return
            try:
                REGISTRY.authorize(room_id, seat, body.get("token"))
            except PermissionError:
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid_token"})
                return
            room = REGISTRY.submit_plan(room_id, seat, body.get("start_station_id"), body.get("steps", []))
            self._send_json(HTTPStatus.OK, {"room": room_payload(room, seat)})
            return

        if action == "ready":
            seat = body.get("seat")
            if seat not in {"runner", "hunter"}:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_seat"})
                return
            try:
                REGISTRY.authorize(room_id, seat, body.get("token"))
            except PermissionError:
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid_token"})
                return
            room = REGISTRY.set_ready(room_id, seat, bool(body.get("ready", True)))
            self._send_json(HTTPStatus.OK, {"room": room_payload(room, seat)})
            return

        if action == "start":
            seat = body.get("seat")
            if seat not in {"runner", "hunter"}:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_seat"})
                return
            try:
                REGISTRY.authorize(room_id, seat, body.get("token"))
            except PermissionError:
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid_token"})
                return
            room = REGISTRY.try_start(room_id, seat)
            self._send_json(HTTPStatus.OK, {"room": room_payload(room, seat)})
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the OniChase v2 online room prototype server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), RoomRequestHandler)
    print(f"OniChase room server listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
