#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import random
import string
import threading
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


def make_room_id() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(6))


@dataclass
class SeatState:
    seat: str
    connected: bool = False
    display_name: str | None = None
    ready: bool = False
    start_station_id: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)

    def to_public(self) -> dict[str, Any]:
        return {
            "seat": self.seat,
            "connected": self.connected,
            "display_name": self.display_name,
            "ready": self.ready,
            "start_station_id": self.start_station_id,
            "steps": self.steps,
        }


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
    match_started: bool = False
    last_result: dict[str, Any] | None = None

    def reset_ready(self) -> None:
        for seat in self.players.values():
            seat.ready = False

    def to_public(self, viewer_seat: str | None = None) -> dict[str, Any]:
        other_seat = "hunter" if viewer_seat == "runner" else "runner"
        players_public = {seat: player.to_public() for seat, player in self.players.items()}
        payload = {
            "room_id": self.room_id,
            "phase": self.phase,
            "start_time_hhmm": self.start_time_hhmm,
            "end_time_hhmm": self.end_time_hhmm,
            "current_game_minute": self.current_game_minute,
            "current_time_hhmm": minutes_to_hhmm(self.current_game_minute),
            "next_planning_minute": self.next_planning_minute,
            "next_planning_hhmm": minutes_to_hhmm(self.next_planning_minute),
            "match_started": self.match_started,
            "players": players_public,
            "viewer_seat": viewer_seat,
        }
        if viewer_seat in {"runner", "hunter"}:
            payload["self"] = players_public[viewer_seat]
            payload["opponent"] = self._project_opponent_for(viewer_seat)
        return payload

    def _project_opponent_for(self, viewer_seat: str) -> dict[str, Any]:
        opponent = self.players["hunter" if viewer_seat == "runner" else "runner"]
        projected = opponent.to_public()
        if viewer_seat == "hunter" and self.phase == "LIVE":
            projected["steps"] = []
            projected["private_visibility"] = "hidden_during_live"
        return projected


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
            )
            self._rooms[room_id] = room
            return room

    def get(self, room_id: str) -> RoomState | None:
        with self._lock:
            return self._rooms.get(room_id)

    def join(self, room_id: str, seat: str, display_name: str | None) -> RoomState:
        with self._lock:
            room = self._rooms[room_id]
            player = room.players[seat]
            player.connected = True
            if display_name:
                player.display_name = display_name
            return room

    def submit_plan(self, room_id: str, seat: str, start_station_id: str | None, steps: list[dict[str, Any]]) -> RoomState:
        with self._lock:
            room = self._rooms[room_id]
            player = room.players[seat]
            if start_station_id is not None:
                player.start_station_id = start_station_id
            player.steps = steps
            player.ready = False
            return room

    def set_ready(self, room_id: str, seat: str, ready: bool) -> RoomState:
        with self._lock:
            room = self._rooms[room_id]
            room.players[seat].ready = ready
            return room

    def try_start(self, room_id: str) -> RoomState:
        with self._lock:
            room = self._rooms[room_id]
            if all(player.ready for player in room.players.values()):
                room.phase = "LIVE"
                room.match_started = True
            return room


REGISTRY = RoomRegistry()
BUNDLE = load_json(BUNDLE_PATH)


class RoomRequestHandler(BaseHTTPRequestHandler):
    server_version = "OniChaseRoomServer/0.1"

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
        if len(path_parts) == 4 and path_parts[:3] == ["api", "rooms", path_parts[2]] and path_parts[3] == "state":
            room_id = path_parts[2]
            room = REGISTRY.get(room_id)
            if room is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "room_not_found"})
                return
            query = parse_qs(parsed.query)
            seat = query.get("seat", [None])[0]
            self._send_json(HTTPStatus.OK, {"room": room.to_public(seat)})
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
            self._send_json(HTTPStatus.CREATED, {"room": room.to_public(), "bundle_metadata": BUNDLE.get("metadata", {})})
            return

        if len(path_parts) != 4 or path_parts[:2] != ["api", "rooms"]:
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
            room = REGISTRY.join(room_id, seat, body.get("display_name"))
            self._send_json(HTTPStatus.OK, {"room": room.to_public(seat)})
            return

        if action == "plan":
            seat = body.get("seat")
            if seat not in {"runner", "hunter"}:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_seat"})
                return
            room = REGISTRY.submit_plan(
                room_id,
                seat,
                body.get("start_station_id"),
                body.get("steps", []),
            )
            self._send_json(HTTPStatus.OK, {"room": room.to_public(seat)})
            return

        if action == "ready":
            seat = body.get("seat")
            if seat not in {"runner", "hunter"}:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_seat"})
                return
            room = REGISTRY.set_ready(room_id, seat, bool(body.get("ready", True)))
            self._send_json(HTTPStatus.OK, {"room": room.to_public(seat)})
            return

        if action == "start":
            seat = body.get("seat")
            if seat not in {"runner", "hunter"}:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_seat"})
                return
            room = REGISTRY.set_ready(room_id, seat, True)
            room = REGISTRY.try_start(room_id)
            self._send_json(HTTPStatus.OK, {"room": room.to_public(seat)})
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
