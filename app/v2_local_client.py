#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.engine.simulate_match_from_train_instances import build_result

BUNDLE_PATH = ROOT / "data" / "shinkansen_v2_bundle.json"
TRAINS_PATH = ROOT / "data" / "shinkansen_v2_weekday_train_instances_merged.json"

RUNNER_COLOR = "#dc4d62"
HUNTER_COLOR = "#2d6cdf"
BG = "#f2eee5"
PANEL = "#fffaf3"
INK = "#1c2733"
MUTED = "#677383"
LINE = "#d4cab8"
ACCENT = "#cc8b2c"
PLAN_COLOR = "#d04f61"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def hhmm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def minutes_to_hhmm(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def stop_departure_minutes(stop: dict[str, Any]) -> int:
    return hhmm_to_minutes(stop.get("departure_hhmm") or stop["arrival_hhmm"])


def stop_arrival_minutes(stop: dict[str, Any]) -> int:
    return hhmm_to_minutes(stop.get("arrival_hhmm") or stop["departure_hhmm"])


def format_train_label(train: dict[str, Any]) -> str:
    service_name = train.get("service_name")
    service_number = train.get("service_number")
    if service_name and service_number not in (None, ""):
        return f"{service_name} {service_number}"
    if service_name:
        return str(service_name)
    if train.get("display_name"):
        return str(train["display_name"])
    return str(train["train_number"])


class OniChaseV2Client:
    def __init__(self) -> None:
        self.bundle = load_json(BUNDLE_PATH)
        self.train_dataset = load_json(TRAINS_PATH)
        self.stations = self.bundle["stations"]
        self.routes = self.bundle["routes"]
        self.station_map = {station["id"]: station for station in self.stations}
        self.train_map = {train["train_number"]: train for train in self.train_dataset["train_instances"]}
        self.route_map = {route["id"]: route for route in self.routes}

        self.players = {
            "runner": {
                "start_station_id": "TOKYO",
                "input_mode": "plan",
                "steps": [],
            },
            "hunter": {
                "start_station_id": "SHIN_OSAKA",
                "input_mode": "actions",
                "passive_hold": True,
                "steps": [{"type": "WAIT_UNTIL", "until_hhmm": "07:00"}],
            },
        }
        self.active_mode = "runner"
        self.pending_board_train_numbers = {"runner": None, "hunter": None}

        self.start_time = "06:00"
        self.end_time = "07:00"
        self.phase = "PLANNING"
        self.planning_seconds_remaining = 60
        self.current_game_minute = hhmm_to_minutes(self.start_time)
        self.clock_running = False
        self.tick_job: str | None = None

        self.selected_station_id: str | None = self.players["runner"]["start_station_id"]
        self.map_pan_x = 0.0
        self.map_pan_y = 0.0
        self.map_scale = 1.0
        self._drag_last: tuple[int, int] | None = None
        self._drag_distance = 0.0
        self.map_coords: dict[str, tuple[float, float]] = {}
        self.project_map_coords()

        self.root = tk.Tk()
        self.root.title("OniChase V2 Client")
        self.root.configure(bg=BG)
        self.root.geometry("1560x980")
        self.root.minsize(1320, 860)
        self.setup_fonts()
        self.setup_styles()

        self.clock_var = tk.StringVar()
        self.hud_var = tk.StringVar()
        self.info_var = tk.StringVar()
        self.train_var = tk.StringVar()
        self.plan_var = tk.StringVar()
        self.result_var = tk.StringVar()
        self.result_detail_var = tk.StringVar()
        self.train_detail_var = tk.StringVar()
        self.latest_result: dict[str, Any] | None = None
        self.selected_result_event_index = 0
        self.live_capture: dict[str, Any] | None = None
        self.build_ui()
        self.apply_test_preset()

    def setup_fonts(self) -> None:
        family = "Helvetica"
        self.fonts = {
            "title": tkfont.Font(family=family, size=22, weight="bold"),
            "subtitle": tkfont.Font(family=family, size=11),
            "body": tkfont.Font(family=family, size=11),
            "body_bold": tkfont.Font(family=family, size=11, weight="bold"),
            "small": tkfont.Font(family=family, size=9),
            "small_bold": tkfont.Font(family=family, size=9, weight="bold"),
            "clock": tkfont.Font(family=family, size=18, weight="bold"),
            "map_title": tkfont.Font(family=family, size=20, weight="bold"),
            "station": tkfont.Font(family=family, size=8),
            "station_selected": tkfont.Font(family=family, size=9, weight="bold"),
        }

    def setup_styles(self) -> None:
        self.style = ttk.Style(self.root)
        self.style.configure("TButton", font=self.fonts["body"])

    def project_map_coords(self) -> None:
        lats = [station["lat"] for station in self.stations]
        lons = [station["lon"] for station in self.stations]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        width = 980
        height = 760
        pad_x = 90
        pad_y = 70
        self.map_coords = {}
        for station in self.stations:
            x = pad_x + ((station["lon"] - min_lon) / (max_lon - min_lon)) * width
            y = pad_y + ((max_lat - station["lat"]) / (max_lat - min_lat)) * height
            self.map_coords[station["id"]] = (x, y)

    def build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top = tk.Frame(self.root, bg=PANEL, highlightbackground=LINE, highlightthickness=1, padx=18, pady=14)
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        top.columnconfigure(0, weight=1)

        tk.Label(top, text="OniChase V2 Client", bg=PANEL, fg=INK, font=self.fonts["title"]).grid(row=0, column=0, sticky="w")
        tk.Label(
            top,
            text="Nationwide Shinkansen playable shell with the same phase loop as v1: planning, live execution, capture, simulation, and replay.",
            bg=PANEL,
            fg=MUTED,
            font=self.fonts["subtitle"],
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.clock_label = tk.Label(top, textvariable=self.clock_var, bg="#b8441f", fg="white", padx=16, pady=10, font=self.fonts["clock"])
        self.clock_label.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 12))

        buttons = tk.Frame(top, bg=PANEL)
        buttons.grid(row=0, column=2, rowspan=2, sticky="e")
        ttk.Button(buttons, text="Runner Mode", command=lambda: self.set_active_mode("runner")).grid(row=0, column=0, padx=4)
        ttk.Button(buttons, text="Hunter Mode", command=lambda: self.set_active_mode("hunter")).grid(row=0, column=1, padx=4)
        ttk.Button(buttons, text="Load Test Preset", command=self.apply_test_preset).grid(row=0, column=2, padx=4)
        ttk.Button(buttons, text="Start Game", command=self.start_match_now).grid(row=0, column=3, padx=4)
        ttk.Button(buttons, text="Pause/Resume", command=self.toggle_clock_running).grid(row=0, column=4, padx=4)

        shell = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=BG, sashrelief=tk.RAISED, sashwidth=10, bd=0)
        shell.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        left = tk.Frame(shell, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        info_row = tk.Frame(left, bg=PANEL)
        info_row.grid(row=0, column=0, sticky="ew", padx=16, pady=16)
        for idx in range(3):
            info_row.columnconfigure(idx, weight=1)
        self.hud_label = self.make_card(info_row, self.hud_var)
        self.hud_label.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.info_label = self.make_card(info_row, self.info_var)
        self.info_label.grid(row=0, column=1, sticky="nsew", padx=4)
        self.train_label = self.make_card(info_row, self.train_var)
        self.train_label.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        map_frame = tk.Frame(left, bg=PANEL)
        map_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))
        map_frame.rowconfigure(0, weight=1)
        map_frame.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(map_frame, bg="#f7f2e9", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<ButtonPress-1>", self.on_map_press)
        self.canvas.bind("<B1-Motion>", self.on_map_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_map_release)
        self.canvas.bind("<MouseWheel>", self.on_map_wheel)
        self.canvas.bind("<Button-4>", lambda event: self.on_map_wheel_linux(event, 1))
        self.canvas.bind("<Button-5>", lambda event: self.on_map_wheel_linux(event, -1))

        self.quick_label = tk.Label(left, textvariable=self.plan_var, justify="left", anchor="w", bg="#1d2129", fg="white", padx=18, pady=14, font=self.fonts["body"])
        self.quick_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))

        right = tk.Frame(shell, bg=BG, width=440)
        right.grid_propagate(False)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        self.plan_card = tk.Frame(right, bg=PANEL, highlightbackground=LINE, highlightthickness=1, padx=12, pady=12)
        self.plan_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.plan_card.columnconfigure(0, weight=1)

        body = tk.Frame(right, bg=BG)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.right_pane = tk.PanedWindow(body, orient=tk.VERTICAL, bg=BG, sashrelief=tk.RAISED, sashwidth=8, bd=0)
        self.right_pane.grid(row=0, column=0, sticky="nsew")

        self.action_card = tk.Frame(self.right_pane, bg=PANEL, highlightbackground=LINE, highlightthickness=1, padx=12, pady=12)
        self.action_card.columnconfigure(0, weight=1)

        self.result_container = tk.Frame(self.right_pane, bg=BG)
        self.result_container.columnconfigure(0, weight=1)
        self.result_container.rowconfigure(1, weight=1)
        self.result_summary_label = self.make_card(self.result_container, self.result_var, width=48)
        self.result_summary_label.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        result_body = tk.Frame(self.result_container, bg=BG)
        result_body.grid(row=1, column=0, sticky="nsew")
        result_body.columnconfigure(0, weight=1)
        result_body.rowconfigure(0, weight=1)
        self.result_event_list = tk.Listbox(
            result_body,
            activestyle="none",
            exportselection=False,
            font=self.fonts["small"],
            bg=PANEL,
            fg=INK,
            highlightthickness=1,
            highlightbackground=LINE,
            selectbackground="#dfead2",
            selectforeground=INK,
        )
        self.result_event_list.grid(row=0, column=0, sticky="nsew")
        result_scrollbar = ttk.Scrollbar(result_body, orient="vertical", command=self.result_event_list.yview)
        result_scrollbar.grid(row=0, column=1, sticky="ns")
        self.result_event_list.configure(yscrollcommand=result_scrollbar.set)
        self.result_event_list.bind("<<ListboxSelect>>", self.on_result_event_select)
        self.result_detail_label = self.make_card(self.result_container, self.result_detail_var, width=48)
        self.result_detail_label.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        self.right_pane.add(self.action_card, minsize=320, stretch="always")
        self.right_pane.add(self.result_container, minsize=220)

        shell.add(left, minsize=820, stretch="always")
        shell.add(right, minsize=360)

    def make_card(self, parent: tk.Widget, variable: tk.StringVar, width: int | None = None) -> tk.Label:
        return tk.Label(
            parent,
            textvariable=variable,
            justify="left",
            anchor="nw",
            bg=PANEL,
            fg=INK,
            padx=14,
            pady=12,
            width=width,
            font=self.fonts["body"],
            highlightbackground=LINE,
            highlightthickness=1,
        )

    def transform(self, station_id: str) -> tuple[float, float]:
        x, y = self.map_coords[station_id]
        return (x * self.map_scale + self.map_pan_x, y * self.map_scale + self.map_pan_y)

    def find_station_at(self, x: float, y: float) -> str | None:
        best: tuple[float, str] | None = None
        for station in self.stations:
            sx, sy = self.transform(station["id"])
            distance = math.dist((x, y), (sx, sy))
            if distance <= 18 and (best is None or distance < best[0]):
                best = (distance, station["id"])
        return best[1] if best else None

    def on_map_press(self, event: tk.Event[tk.Misc]) -> None:
        self._drag_last = (event.x, event.y)
        self._drag_distance = 0.0

    def on_map_drag(self, event: tk.Event[tk.Misc]) -> None:
        if not self._drag_last:
            return
        dx = event.x - self._drag_last[0]
        dy = event.y - self._drag_last[1]
        self.map_pan_x += dx
        self.map_pan_y += dy
        self._drag_distance += abs(dx) + abs(dy)
        self._drag_last = (event.x, event.y)
        self.render_map()

    def on_map_release(self, event: tk.Event[tk.Misc]) -> None:
        if self._drag_distance < 8:
            station_id = self.find_station_at(event.x, event.y)
            if station_id:
                self.selected_station_id = station_id
                self.render()
        self._drag_last = None
        self._drag_distance = 0.0

    def on_map_wheel(self, event: tk.Event[tk.Misc]) -> None:
        delta = 1 if event.delta > 0 else -1
        self.zoom_map(delta)

    def on_map_wheel_linux(self, event: tk.Event[tk.Misc], direction: int) -> None:
        self.zoom_map(direction)

    def zoom_map(self, direction: int) -> None:
        factor = 1.1 if direction > 0 else 0.9
        self.map_scale = max(0.45, min(2.3, self.map_scale * factor))
        self.render_map()

    def visible_game_minute(self) -> int:
        if self.phase == "PLANNING":
            return hhmm_to_minutes(self.start_time)
        return self.current_game_minute

    def reset_match_flow(self, auto_start: bool = True) -> None:
        if self.tick_job:
            self.root.after_cancel(self.tick_job)
            self.tick_job = None
        self.phase = "PLANNING"
        self.live_capture = None
        self.planning_seconds_remaining = 60
        self.current_game_minute = hhmm_to_minutes(self.start_time)
        self.clock_running = auto_start
        if auto_start:
            self.schedule_tick()

    def schedule_tick(self) -> None:
        if self.tick_job:
            self.root.after_cancel(self.tick_job)
        if self.clock_running:
            self.tick_job = self.root.after(1000, self.on_tick)

    def on_tick(self) -> None:
        self.tick_job = None
        if not self.clock_running:
            return
        if self.phase == "PLANNING":
            self.planning_seconds_remaining = max(0, self.planning_seconds_remaining - 1)
            if self.planning_seconds_remaining == 0:
                self.phase = "LIVE"
                self.check_live_capture()
        elif self.phase == "LIVE":
            end_minute = hhmm_to_minutes(self.end_time)
            if self.current_game_minute < end_minute:
                self.current_game_minute += 1
                self.check_live_capture()
            else:
                self.phase = "ENDED"
                self.clock_running = False
        self.render()
        if self.clock_running:
            self.schedule_tick()

    def start_match_now(self) -> None:
        if self.phase != "PLANNING":
            self.set_result_message("ACTION", ["The game can only be started manually during PLANNING."])
            self.render()
            return
        self.phase = "LIVE"
        self.current_game_minute = hhmm_to_minutes(self.start_time)
        self.clock_running = True
        self.live_capture = None
        self.check_live_capture()
        if not self.live_capture:
            self.schedule_tick()
        self.set_result_message("ACTION", ["Planning ended early and the live game started immediately."])
        self.render()

    def toggle_clock_running(self) -> None:
        self.clock_running = not self.clock_running
        if self.clock_running:
            self.schedule_tick()
        elif self.tick_job:
            self.root.after_cancel(self.tick_job)
            self.tick_job = None
        self.render()

    def set_active_mode(self, mode: str) -> None:
        self.active_mode = mode
        self.selected_station_id = self.players[mode]["start_station_id"]
        self.render()

    def apply_test_preset(self) -> None:
        if self.active_mode == "hunter":
            self.start_time = "07:00"
            self.end_time = "08:00"
            self.players["runner"] = {
                "start_station_id": "TOKYO",
                "input_mode": "actions",
                "passive_hold": True,
                "steps": [{"type": "WAIT_UNTIL", "until_hhmm": self.end_time}],
            }
            self.players["hunter"] = {
                "start_station_id": "SHIN_OSAKA",
                "input_mode": "actions",
                "steps": [],
            }
        else:
            self.start_time = "06:00"
            self.end_time = "07:00"
            self.players["runner"] = {
                "start_station_id": "TOKYO",
                "input_mode": "plan",
                "steps": [],
            }
            self.players["hunter"] = {
                "start_station_id": "SHIN_OSAKA",
                "input_mode": "actions",
                "passive_hold": True,
                "steps": [{"type": "WAIT_UNTIL", "until_hhmm": self.end_time}],
            }
        self.pending_board_train_numbers = {"runner": None, "hunter": None}
        self.selected_station_id = self.players[self.active_mode]["start_station_id"]
        self.latest_result = None
        self.selected_result_event_index = 0
        self.reset_match_flow(auto_start=True)
        self.render()

    def active_player(self) -> dict[str, Any]:
        return self.players[self.active_mode]

    def clear_pending_board_train(self, player_id: str | None = None) -> None:
        self.pending_board_train_numbers[player_id or self.active_mode] = None

    def pending_board_train_number(self, player_id: str | None = None) -> str | None:
        return self.pending_board_train_numbers[player_id or self.active_mode]

    def find_boarding_stop(self, train: dict[str, Any], station_id: str, earliest_minute: int) -> dict[str, Any] | None:
        candidates = []
        for stop in train["stop_times"]:
            if stop.get("station_id") != station_id:
                continue
            departure_minute = stop_departure_minutes(stop)
            if departure_minute < earliest_minute:
                continue
            candidates.append((departure_minute, stop))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def find_alight_stop(self, train: dict[str, Any], boarded_sequence: int, station_id: str) -> dict[str, Any] | None:
        for stop in train["stop_times"]:
            if stop["sequence"] <= boarded_sequence:
                continue
            if stop.get("station_id") == station_id:
                return stop
        return None

    def preview_player(self, player_id: str, time_cap_minute: int | None = None) -> dict[str, Any]:
        player = self.players[player_id]
        current_minute = hhmm_to_minutes(self.start_time)
        current_state: dict[str, Any] = {"kind": "NODE", "station_id": player["start_station_id"]}
        current_train: dict[str, Any] | None = None
        current_board_stop: dict[str, Any] | None = None
        resolved_steps: list[dict[str, Any]] = []
        if time_cap_minute is None:
            time_cap_minute = None

        for step in player["steps"]:
            step_type = step["type"]
            if step_type == "WAIT_UNTIL":
                target_minute = hhmm_to_minutes(step["until_hhmm"])
                if time_cap_minute is not None and target_minute > time_cap_minute:
                    break
                current_minute = target_minute
                resolved_steps.append(step)
                continue

            if step_type == "BOARD_TRAIN":
                if current_state["kind"] != "NODE":
                    return self.error_preview(player_id, current_minute, current_state, "Cannot board while not at a station.", resolved_steps)
                train = self.train_map.get(step["train_number"])
                if not train:
                    return self.error_preview(player_id, current_minute, current_state, f"Unknown train {step['train_number']}.", resolved_steps)
                board_stop = self.find_boarding_stop(train, current_state["station_id"], current_minute)
                if not board_stop:
                    return self.error_preview(player_id, current_minute, current_state, f"Train {step['train_number']} is not catchable.", resolved_steps)
                board_minute = stop_departure_minutes(board_stop)
                if time_cap_minute is not None and board_minute > time_cap_minute:
                    break
                current_minute = board_minute
                current_state = {"kind": "TRAIN", "train_number": train["train_number"]}
                current_train = train
                current_board_stop = board_stop
                resolved_steps.append(step)
                continue

            if step_type == "RIDE_TO_STATION":
                if current_state["kind"] != "TRAIN" or current_train is None or current_board_stop is None:
                    return self.error_preview(player_id, current_minute, current_state, "Cannot ride while not on a train.", resolved_steps)
                alight_stop = self.find_alight_stop(current_train, current_board_stop["sequence"], step["station_id"])
                if not alight_stop:
                    return self.error_preview(player_id, current_minute, current_state, f"{current_train['train_number']} does not reach {step['station_id']}.", resolved_steps)
                arrival_minute = stop_arrival_minutes(alight_stop)
                if time_cap_minute is not None and arrival_minute > time_cap_minute:
                    current_minute = time_cap_minute
                    position = self.train_location_on_map(current_train["train_number"], time_cap_minute)
                    return {
                        "player_id": player_id,
                        "current_minute": current_minute,
                        "current_time": minutes_to_hhmm(current_minute),
                        "current_state": {"kind": "TRAIN", "train_number": current_train["train_number"]},
                        "current_train": current_train,
                        "current_board_stop": current_board_stop,
                        "map_station_id": position.get("anchor_station_id") if position else None,
                        "map_position": position.get("position") if position else None,
                        "resolved_steps": resolved_steps,
                        "start_station_id": player["start_station_id"],
                        "error": None,
                    }
                current_minute = arrival_minute
                current_state = {"kind": "NODE", "station_id": alight_stop["station_id"]}
                current_train = None
                current_board_stop = None
                resolved_steps.append(step)
                continue

        map_station_id = current_state.get("station_id")
        map_position = None
        if current_state["kind"] == "NODE" and map_station_id in self.map_coords:
            x, y = self.map_coords[map_station_id]
            map_position = (x, y)
        elif current_state["kind"] == "TRAIN":
            position = self.train_location_on_map(current_state["train_number"], time_cap_minute or current_minute)
            if position:
                map_station_id = position["anchor_station_id"]
                map_position = position["position"]

        return {
            "player_id": player_id,
            "current_minute": current_minute,
            "current_time": minutes_to_hhmm(current_minute),
            "current_state": current_state,
            "current_train": current_train,
            "current_board_stop": current_board_stop,
            "map_station_id": map_station_id,
            "map_position": map_position,
            "resolved_steps": resolved_steps,
            "start_station_id": player["start_station_id"],
            "error": None,
        }

    def error_preview(self, player_id: str, current_minute: int, current_state: dict[str, Any], message: str, resolved_steps: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "player_id": player_id,
            "current_minute": current_minute,
            "current_time": minutes_to_hhmm(current_minute),
            "current_state": current_state,
            "current_train": None,
            "current_board_stop": None,
            "map_station_id": current_state.get("station_id"),
            "map_position": None,
            "resolved_steps": resolved_steps,
            "start_station_id": self.players[player_id]["start_station_id"],
            "error": message,
        }

    def active_preview(self) -> dict[str, Any]:
        return self.preview_player(self.active_mode, self.visible_game_minute())

    def plan_cursor_preview(self, player_id: str | None = None) -> dict[str, Any]:
        target = player_id or self.active_mode
        if self.phase == "PLANNING" and self.current_replay_event() is None:
            return self.preview_player(target, None)
        return self.preview_player(target, self.visible_game_minute())

    def departures_for_station(self, station_id: str, current_minute: int) -> list[tuple[int, dict[str, Any], dict[str, Any]]]:
        departures: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
        for train in self.train_dataset["train_instances"]:
            for stop in train["stop_times"]:
                if stop.get("station_id") != station_id:
                    continue
                departure_minute = stop_departure_minutes(stop)
                if departure_minute < current_minute:
                    continue
                departures.append((departure_minute, train, stop))
                break
        departures.sort(key=lambda item: (item[0], format_train_label(item[1]), item[1]["train_number"]))
        return departures[:100]

    def add_board_and_ride_steps(self, train_number: str, station_id: str) -> None:
        preview = self.plan_cursor_preview()
        if preview["error"]:
            self.set_result_message("ACTION", [preview["error"]])
            self.render()
            return
        if preview["current_state"]["kind"] != "NODE":
            self.set_result_message("ACTION", ["You can only choose a new train while currently at a station."])
            self.render()
            return
        station_from = preview["current_state"]["station_id"]
        minute = preview["current_minute"]
        train = self.train_map.get(train_number)
        if not train:
            self.set_result_message("ACTION", [f"Unknown train {train_number}."])
            self.render()
            return
        board_stop = self.find_boarding_stop(train, station_from, minute)
        if not board_stop:
            self.set_result_message("ACTION", [f"Train {train_number} is not catchable from the current state."])
            self.render()
            return
        alight_stop = self.find_alight_stop(train, board_stop["sequence"], station_id)
        if not alight_stop:
            self.set_result_message("ACTION", [f"Train {train_number} does not reach {station_id} later."])
            self.render()
            return
        removed = self.truncate_future_steps_to_current()
        self.active_player()["steps"].append({"type": "BOARD_TRAIN", "train_number": train_number})
        self.active_player()["steps"].append({"type": "RIDE_TO_STATION", "station_id": station_id})
        self.clear_pending_board_train()
        self.reset_passive_hold_if_needed()
        note = f"Trimmed {removed} future step(s) before branching." if removed else "Added a fresh boarding branch."
        self.set_result_message(
            "ACTION",
            [
                f"Planned {train_number} from {station_from} to {station_id}.",
                f"Depart {minutes_to_hhmm(stop_departure_minutes(board_stop))}  Arrive {alight_stop.get('arrival_hhmm') or alight_stop.get('departure_hhmm')}.",
                note,
            ],
        )
        self.render()

    def add_wait_step(self) -> None:
        preview = self.plan_cursor_preview()
        if preview["error"]:
            self.set_result_message("ACTION", [preview["error"]])
            self.render()
            return
        if preview["current_state"]["kind"] != "NODE":
            self.set_result_message("ACTION", ["You can only wait while currently at a station."])
            self.render()
            return
        target_minute = min(preview["current_minute"] + 5, hhmm_to_minutes(self.end_time))
        if target_minute <= preview["current_minute"]:
            self.set_result_message("ACTION", ["No room left in the match clock for an extra wait step."])
            self.render()
            return
        removed = self.truncate_future_steps_to_current()
        self.active_player()["steps"].append({"type": "WAIT_UNTIL", "until_hhmm": minutes_to_hhmm(target_minute)})
        self.clear_pending_board_train()
        self.reset_passive_hold_if_needed()
        note = f"Trimmed {removed} future step(s) before adding the new branch." if removed else "Appended to the current future plan."
        self.set_result_message("ACTION", [f"Added WAIT_UNTIL {minutes_to_hhmm(target_minute)}.", note])
        self.render()

    def truncate_future_steps_to_current(self) -> int:
        if self.phase == "PLANNING" and self.current_replay_event() is None:
            return 0
        preview = self.active_preview()
        resolved_count = len(preview["resolved_steps"])
        steps = self.active_player()["steps"]
        removed = max(0, len(steps) - resolved_count)
        if removed:
            self.active_player()["steps"] = list(steps[:resolved_count])
        return removed

    def reset_passive_hold_if_needed(self) -> None:
        active_player = self.active_player()
        if active_player.get("passive_hold"):
            active_player["passive_hold"] = False

    def set_start_to_selected(self) -> None:
        if not self.selected_station_id:
            self.set_result_message("ACTION", ["Select a station first."])
            return
        active_player = self.active_player()
        active_player["start_station_id"] = self.selected_station_id
        active_player["steps"] = []
        self.clear_pending_board_train()
        self.reset_passive_hold_if_needed()
        self.set_result_message("ACTION", [f"{self.active_mode.title()} start moved to {self.selected_station_id}."])
        self.render()

    def undo_last_step(self) -> None:
        steps = self.active_player()["steps"]
        if not steps:
            self.set_result_message("ACTION", ["No step to undo."])
            self.render()
            return
        removed = steps.pop()
        self.clear_pending_board_train()
        self.reset_passive_hold_if_needed()
        self.set_result_message("ACTION", [f"Removed last step: {removed['type']}."])
        self.render()

    def clear_active_plan(self) -> None:
        self.active_player()["steps"] = []
        self.clear_pending_board_train()
        self.reset_passive_hold_if_needed()
        self.set_result_message("ACTION", [f"Cleared all steps for {self.active_mode}."])
        self.render()

    def build_scenario(self) -> dict[str, Any]:
        players_payload: dict[str, Any] = {}
        for player_id, player in self.players.items():
            payload: dict[str, Any] = {"start_station_id": player["start_station_id"]}
            if player.get("input_mode", "actions") == "plan":
                payload["plan"] = {"steps": list(player["steps"])}
            else:
                payload["actions"] = list(player["steps"])
            players_payload[player_id] = payload
        return {
            "id": "v2-local-client-live",
            "start_time_hhmm": self.start_time,
            "end_time_hhmm": self.end_time,
            "players": players_payload,
        }

    def run_simulation(self) -> None:
        try:
            result = build_result(self.build_scenario(), self.train_dataset)
        except Exception as exc:
            self.set_result_message("SIMULATION", [f"Failed to simulate: {exc}"])
            self.render()
            return
        self.latest_result = result
        self.selected_result_event_index = 0
        capture = result["capture"]
        lines = [f"Scenario: {result['scenario_id']}", f"Events: {len(result['match_event_log'])}"]
        if capture is None:
            lines.append("Capture: none")
        elif capture["type"] == "same_node":
            lines.append(f"Capture: same_node at {capture['station_id']} {capture['time_hhmm']}")
        else:
            lines.append(f"Capture: same_train on {capture['train_number']} {capture['time_hhmm']}")
        self.result_var.set("SIMULATION\n\n" + "\n".join(lines))
        self.refresh_result_event_list()
        self.render()

    def refresh_result_event_list(self) -> None:
        self.result_event_list.delete(0, tk.END)
        if not self.latest_result:
            self.result_event_list.insert(tk.END, "No replay yet. Run Simulation first.")
            self.result_detail_var.set("EVENT DETAIL\n\nNo replay event selected.")
            return
        for event in self.latest_result["match_event_log"]:
            parts = [event["time_hhmm"], event["type"]]
            if event.get("player_id"):
                parts.append(event["player_id"])
            if event.get("station_id"):
                parts.append(event["station_id"])
            if event.get("train_number"):
                parts.append(event["train_number"])
            if event.get("capture_type"):
                parts.append(event["capture_type"])
            self.result_event_list.insert(tk.END, "  ".join(parts))
        self.result_event_list.selection_clear(0, tk.END)
        self.result_event_list.selection_set(self.selected_result_event_index)
        self.result_event_list.see(self.selected_result_event_index)
        self.update_result_detail()

    def on_result_event_select(self, _event: tk.Event) -> None:
        selection = self.result_event_list.curselection()
        if not selection:
            return
        self.selected_result_event_index = int(selection[0])
        self.update_result_detail()
        self.render()

    def update_result_detail(self) -> None:
        if not self.latest_result or not self.latest_result["match_event_log"]:
            self.result_detail_var.set("EVENT DETAIL\n\nNo replay event selected.")
            return
        event = self.latest_result["match_event_log"][self.selected_result_event_index]
        lines = ["EVENT DETAIL", "", f"Time: {event['time_hhmm']}", f"Type: {event['type']}"]
        if event.get("player_id"):
            lines.append(f"Player: {event['player_id']}")
        if event.get("station_id"):
            lines.append(f"Station: {event['station_id']}")
        if event.get("train_number"):
            lines.append(f"Train: {event['train_number']}")
        if event.get("capture_type"):
            lines.append(f"Capture: {event['capture_type']}")
        state_after = event.get("state_after")
        if state_after:
            lines.extend(["", f"Runner after: {self.format_carrier(state_after.get('runner', {}))}", f"Hunter after: {self.format_carrier(state_after.get('hunter', {}))}"])
        self.result_detail_var.set("\n".join(lines))

    def current_replay_event(self) -> dict[str, Any] | None:
        if not self.latest_result or not self.latest_result.get("match_event_log"):
            return None
        return self.latest_result["match_event_log"][max(0, min(self.selected_result_event_index, len(self.latest_result["match_event_log"]) - 1))]

    def format_carrier(self, state: dict[str, Any]) -> str:
        if state.get("kind") == "NODE":
            return state.get("station_id", "unknown")
        if state.get("kind") == "TRAIN":
            return f"on {state.get('train_number', 'unknown train')}"
        return "unknown"

    def set_result_message(self, title: str, lines: list[str]) -> None:
        self.result_var.set(title + "\n\n" + "\n".join(lines))
        self.result_detail_var.set("")
        self.latest_result = None
        self.selected_result_event_index = 0
        self.refresh_result_event_list()

    def detect_live_capture(self) -> dict[str, Any] | None:
        if self.phase != "LIVE":
            return None
        visible_minute = self.visible_game_minute()
        runner_preview = self.preview_player("runner", visible_minute)
        hunter_preview = self.preview_player("hunter", visible_minute)
        runner_state = runner_preview["current_state"]
        hunter_state = hunter_preview["current_state"]
        if runner_state["kind"] == "TRAIN" and hunter_state["kind"] == "TRAIN" and runner_state.get("train_number") == hunter_state.get("train_number"):
            return {
                "type": "same_train",
                "time_hhmm": minutes_to_hhmm(visible_minute),
                "train_number": runner_state["train_number"],
            }
        if runner_state["kind"] == "NODE" and hunter_state["kind"] == "NODE" and runner_state.get("station_id") == hunter_state.get("station_id"):
            return {
                "type": "same_node",
                "time_hhmm": minutes_to_hhmm(visible_minute),
                "station_id": runner_state["station_id"],
            }
        return None

    def check_live_capture(self) -> None:
        capture = self.detect_live_capture()
        if not capture:
            return
        visible_minute = self.visible_game_minute()
        capture["runner_state_text"] = self.format_state(self.preview_player("runner", visible_minute))
        capture["hunter_state_text"] = self.format_state(self.preview_player("hunter", visible_minute))
        self.live_capture = capture
        self.phase = "ENDED"
        self.clock_running = False
        self.set_result_message("GAME END", self.capture_summary_lines(capture))
        self.result_detail_var.set("\n".join(self.capture_detail_lines(capture)))

    def capture_summary_lines(self, capture: dict[str, Any]) -> list[str]:
        lines = [f"Hunter caught the runner at {capture['time_hhmm']}.", f"Capture type: {capture['type']}."]
        if capture["type"] == "same_node":
            lines.append(f"Station: {capture['station_id']}.")
        else:
            lines.append(f"Train: {capture['train_number']}.")
        return lines

    def capture_detail_lines(self, capture: dict[str, Any]) -> list[str]:
        lines = ["CAPTURE DETAIL", "", f"Time: {capture['time_hhmm']}", f"Rule: {capture['type']}"]
        if capture["type"] == "same_node":
            lines.append(f"Meeting Point: {capture['station_id']}")
        else:
            lines.append(f"Same Train: {capture['train_number']}")
        lines.extend(["", f"Runner: {capture.get('runner_state_text', 'unknown')}", f"Hunter: {capture.get('hunter_state_text', 'unknown')}"])
        return lines

    def replay_preview_from_state(self, player_id: str, state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        current_state = dict(state)
        map_station_id = current_state.get("station_id")
        map_position = None
        if current_state.get("kind") == "NODE" and map_station_id in self.map_coords:
            map_position = self.map_coords[map_station_id]
        elif current_state.get("kind") == "TRAIN":
            loc = self.train_location_on_map(current_state["train_number"], event["time_minute"])
            if loc:
                map_station_id = loc["anchor_station_id"]
                map_position = loc["position"]
        return {
            "player_id": player_id,
            "current_minute": event["time_minute"],
            "current_time": event["time_hhmm"],
            "current_state": current_state,
            "current_train": self.train_map.get(current_state.get("train_number")) if current_state.get("kind") == "TRAIN" else None,
            "current_board_stop": None,
            "map_station_id": map_station_id,
            "map_position": map_position,
            "resolved_steps": [],
            "start_station_id": self.players[player_id]["start_station_id"],
            "error": None,
            "replay_focus": True,
        }

    def current_preview_for_map(self, player_id: str) -> dict[str, Any]:
        event = self.current_replay_event()
        if event:
            state_after = event.get("state_after", {})
            if player_id in state_after:
                return self.replay_preview_from_state(player_id, state_after[player_id], event)
        return self.preview_player(player_id, self.visible_game_minute())

    def should_show_player(self, player_id: str) -> bool:
        event = self.current_replay_event()
        if event:
            return True
        if self.phase == "PLANNING":
            return True
        if self.phase in {"LIVE", "ENDED"}:
            return player_id == self.active_mode
        return True

    def hunter_runner_text(self, preview: dict[str, Any]) -> str:
        state = preview["current_state"]
        if state["kind"] == "NODE":
            return f"Runner at {state['station_id']}"
        return "Runner location hidden in text while on a train."

    def format_state(self, preview: dict[str, Any]) -> str:
        state = preview["current_state"]
        if state["kind"] == "NODE":
            return f"at {state['station_id']} {preview['current_time']}"
        return f"on {state['train_number']} {preview['current_time']}"

    def train_location_on_map(self, train_number: str, time_minute: int) -> dict[str, Any] | None:
        train = self.train_map.get(train_number)
        if not train:
            return None
        stops = train["stop_times"]
        for index, stop in enumerate(stops):
            arr = stop_arrival_minutes(stop)
            dep = stop_departure_minutes(stop)
            station_id = stop["station_id"]
            if arr <= time_minute <= dep:
                if station_id in self.map_coords:
                    x, y = self.map_coords[station_id]
                    return {"anchor_station_id": station_id, "position": (x, y)}
            if dep < time_minute and index + 1 < len(stops):
                next_stop = stops[index + 1]
                next_arr = stop_arrival_minutes(next_stop)
                if dep <= time_minute <= next_arr:
                    a = self.map_coords.get(station_id)
                    b = self.map_coords.get(next_stop["station_id"])
                    if not a or not b:
                        return None
                    if next_arr == dep:
                        return {"anchor_station_id": next_stop["station_id"], "position": b}
                    ratio = (time_minute - dep) / (next_arr - dep)
                    x = a[0] + (b[0] - a[0]) * ratio
                    y = a[1] + (b[1] - a[1]) * ratio
                    return {"anchor_station_id": next_stop["station_id"], "position": (x, y)}
        last_station_id = stops[-1]["station_id"]
        if last_station_id in self.map_coords:
            return {"anchor_station_id": last_station_id, "position": self.map_coords[last_station_id]}
        return None

    def render_clock(self) -> None:
        if self.phase == "PLANNING":
            self.clock_label.configure(bg="#b8441f")
            self.clock_var.set(f"PLANNING\n{self.planning_seconds_remaining:02d}s\nGame starts {self.start_time}")
        elif self.phase == "LIVE":
            self.clock_label.configure(bg="#163d2c")
            self.clock_var.set(f"LIVE\n{minutes_to_hhmm(self.current_game_minute)}\nWindow {self.start_time} -> {self.end_time}")
        else:
            self.clock_label.configure(bg="#2a2f38")
            self.clock_var.set(f"ENDED\n{minutes_to_hhmm(self.visible_game_minute())}\nWindow {self.start_time} -> {self.end_time}")

    def render_hud(self) -> None:
        active_preview = self.plan_cursor_preview()
        self.hud_var.set(
            "\n".join(
                [
                    f"Mode: {self.active_mode.upper()}",
                    f"Start: {self.players[self.active_mode]['start_station_id']}",
                    f"Cursor: {self.format_state(active_preview)}",
                    f"Steps: {len(self.players[self.active_mode]['steps'])}",
                ]
            )
        )
        runner_preview = self.current_preview_for_map("runner")
        hunter_preview = self.current_preview_for_map("hunter")
        if self.active_mode == "hunter":
            runner_line = self.hunter_runner_text(runner_preview) if self.phase == "PLANNING" else "Runner hidden during LIVE."
        else:
            runner_line = self.format_state(runner_preview)
        self.info_var.set(
            "\n".join(
                [
                    f"Runner: {runner_line}",
                    f"Hunter: {self.format_state(hunter_preview) if self.phase == 'PLANNING' or self.active_mode == 'hunter' else 'Hidden during LIVE.'}",
                    f"Selected: {self.selected_station_id or '-'}",
                ]
            )
        )
        active_train = active_preview.get("current_train")
        if active_train and active_preview.get("current_board_stop"):
            lines = [format_train_label(active_train), "Upcoming stops:"]
            boarded_sequence = active_preview["current_board_stop"]["sequence"]
            for stop in active_train["stop_times"]:
                if stop["sequence"] <= boarded_sequence:
                    continue
                lines.append(f"- {stop['station_id']} {stop.get('arrival_hhmm') or stop.get('departure_hhmm')}")
            self.train_var.set("\n".join(lines[:12]))
        else:
            self.train_var.set("TRAIN OUTLOOK\n\nNot on a train right now.")

    def render_plan_board(self) -> None:
        lines = [f"{self.active_mode.upper()} PLAN BOARD", ""]
        steps = self.players[self.active_mode]["steps"]
        if not steps:
            lines.append("No plan yet.")
        else:
            current_station = self.players[self.active_mode]["start_station_id"]
            pending_train = None
            leg_index = 1
            for step in steps:
                if step["type"] == "WAIT_UNTIL":
                    lines.append(f"WAIT until {step['until_hhmm']}")
                    continue
                if step["type"] == "BOARD_TRAIN":
                    pending_train = step["train_number"]
                    continue
                if step["type"] == "RIDE_TO_STATION":
                    lines.append(f"LEG {leg_index}: {current_station} -> {pending_train or '?'} -> {step['station_id']}")
                    current_station = step["station_id"]
                    pending_train = None
                    leg_index += 1
        self.plan_var.set("\n".join(lines))

    def render_action_card(self) -> None:
        for child in self.action_card.winfo_children():
            child.destroy()
        preview = self.plan_cursor_preview()
        tk.Label(self.action_card, text=f"{self.active_mode.upper()} ACTIONS", bg=PANEL, fg=INK, font=self.fonts["body_bold"]).grid(row=0, column=0, sticky="w")
        tk.Label(
            self.action_card,
            text=f"Current: {self.format_state(preview)}",
            bg=PANEL,
            fg=MUTED,
            font=self.fonts["small"],
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 10))

        button_row = tk.Frame(self.action_card, bg=PANEL)
        button_row.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(button_row, text="Set Start Here", command=self.set_start_to_selected).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(button_row, text="Wait +5m", command=self.add_wait_step).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(button_row, text="Undo", command=self.undo_last_step).grid(row=0, column=2, padx=2, pady=2)
        ttk.Button(button_row, text="Clear Plan", command=self.clear_active_plan).grid(row=0, column=3, padx=2, pady=2)
        ttk.Button(button_row, text="Run Simulation", command=self.run_simulation).grid(row=0, column=4, padx=2, pady=2)

        station_id = self.selected_station_id or preview["current_state"].get("station_id") or self.players[self.active_mode]["start_station_id"]
        departures = []
        if preview["current_state"]["kind"] == "NODE":
            departures = self.departures_for_station(station_id, preview["current_minute"])

        tk.Label(self.action_card, text="STEP 1  Choose Your Train", bg=PANEL, fg=INK, font=self.fonts["body_bold"]).grid(row=3, column=0, sticky="w")
        dep_list = tk.Listbox(self.action_card, font=self.fonts["small"], activestyle="none", height=10)
        dep_list.grid(row=4, column=0, sticky="ew")
        for departure_minute, train, _stop in departures[:40]:
            dep_list.insert(tk.END, f"{minutes_to_hhmm(departure_minute)}  {format_train_label(train)}  |  {train['train_number']}")
        if departures:
            def choose_train() -> None:
                selection = dep_list.curselection()
                if not selection:
                    return
                self.pending_board_train_numbers[self.active_mode] = dep_list.get(selection[0]).split(" | ")[-1]
                self.render()
            ttk.Button(self.action_card, text="Choose This Train", command=choose_train).grid(row=5, column=0, sticky="w", pady=(6, 10))
        selected_train_number = self.pending_board_train_number()
        detail_lines = ["Select a departure to preview the remaining stop list."]
        destinations: list[dict[str, Any]] = []
        if selected_train_number and preview["current_state"]["kind"] == "NODE":
            train = self.train_map.get(selected_train_number)
            if train:
                board_stop = self.find_boarding_stop(train, station_id, preview["current_minute"])
                if board_stop:
                    detail_lines = [format_train_label(train), f"Board at {station_id} {minutes_to_hhmm(stop_departure_minutes(board_stop))}", "Remaining stops:"]
                    for stop in train["stop_times"]:
                        if stop["sequence"] <= board_stop["sequence"]:
                            continue
                        detail_lines.append(f"- {stop['station_id']} {stop.get('arrival_hhmm') or stop.get('departure_hhmm')}")
                        destinations.append(stop)
        tk.Label(self.action_card, text="\n".join(detail_lines[:14]), bg=PANEL, fg=MUTED, font=self.fonts["small"], justify="left", anchor="w").grid(row=6, column=0, sticky="ew", pady=(0, 10))

        tk.Label(self.action_card, text="STEP 2  Choose Destination", bg=PANEL, fg=INK, font=self.fonts["body_bold"]).grid(row=7, column=0, sticky="w")
        dest_list = tk.Listbox(self.action_card, font=self.fonts["small"], activestyle="none", height=10)
        dest_list.grid(row=8, column=0, sticky="ew")
        for stop in destinations:
            dest_list.insert(tk.END, f"{stop.get('arrival_hhmm') or stop.get('departure_hhmm')}  {stop['station_id']}")
        def ride_here() -> None:
            if not selected_train_number:
                return
            selection = dest_list.curselection()
            if not selection:
                return
            station_choice = dest_list.get(selection[0]).split()[-1]
            self.add_board_and_ride_steps(selected_train_number, station_choice)
        ttk.Button(self.action_card, text="Ride Here", command=ride_here).grid(row=9, column=0, sticky="w", pady=(6, 0))

    def render_result(self) -> None:
        if not self.result_var.get():
            self.result_var.set("RESULT\n\nNo result yet.")
        self.refresh_result_event_list()

    def current_map_preview(self, player_id: str) -> dict[str, Any]:
        return self.current_preview_for_map(player_id)

    def render_map(self) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(18, 18, text="V2 BOARD", anchor="nw", fill=INK, font=self.fonts["map_title"])
        self.canvas.create_text(18, 44, text=f"{len(self.routes)} routes  |  {self.bundle['train_count']} real weekday trains", anchor="nw", fill=MUTED, font=self.fonts["subtitle"])
        for route in self.routes:
            points = []
            for station_id in route["station_ids"]:
                x, y = self.transform(station_id)
                points.extend([x, y])
            if len(points) >= 4:
                self.canvas.create_line(*points, fill=route["color"], width=5, capstyle=tk.ROUND, joinstyle=tk.ROUND)

        active_steps = self.players[self.active_mode]["steps"]
        current_station = self.players[self.active_mode]["start_station_id"]
        pending_train = None
        for step in active_steps:
            if step["type"] == "BOARD_TRAIN":
                pending_train = step["train_number"]
                continue
            if step["type"] == "RIDE_TO_STATION":
                fx, fy = self.transform(current_station)
                tx, ty = self.transform(step["station_id"])
                self.canvas.create_line(fx, fy, tx, ty, fill=PLAN_COLOR, width=3, dash=(8, 6))
                current_station = step["station_id"]
                pending_train = None

        for station in self.stations:
            station_id = station["id"]
            x, y = self.transform(station_id)
            is_selected = station_id == self.selected_station_id
            radius = 6 if station.get("is_interchange") else 4
            outline = ACCENT if is_selected else "#ffffff"
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill="#ffffff", outline=outline, width=2)
            self.canvas.create_text(x + 8, y - 9, text=station["name"], anchor="w", fill=INK if is_selected else MUTED, font=self.fonts["station_selected"] if is_selected else self.fonts["station"])

        previews = {
            "runner": self.current_map_preview("runner"),
            "hunter": self.current_map_preview("hunter"),
        }
        for player_id, color in (("runner", RUNNER_COLOR), ("hunter", HUNTER_COLOR)):
            if not self.should_show_player(player_id):
                continue
            preview = previews[player_id]
            pos = preview.get("map_position")
            if not pos:
                continue
            x, y = pos
            x, y = x * self.map_scale + self.map_pan_x, y * self.map_scale + self.map_pan_y
            self.canvas.create_oval(x - 10, y - 10, x + 10, y + 10, fill=color, outline="white", width=3)
            label = player_id.upper()
            if preview["current_state"]["kind"] == "TRAIN":
                sub = preview["current_state"]["train_number"]
            else:
                sub = preview["current_state"].get("station_id", "")
            self.canvas.create_rectangle(x + 14, y - 20, x + 170, y + 18, fill=PANEL, outline=color, width=2)
            self.canvas.create_text(x + 22, y - 8, text=label, anchor="w", fill=color, font=self.fonts["small_bold"])
            self.canvas.create_text(x + 22, y + 7, text=sub, anchor="w", fill=INK, font=self.fonts["small"])

        if self.live_capture:
            capture = self.live_capture
            text = "CAUGHT"
            if capture["type"] == "same_node" and capture.get("station_id") in self.map_coords:
                x, y = self.transform(capture["station_id"])
            else:
                loc = self.train_location_on_map(capture["train_number"], hhmm_to_minutes(capture["time_hhmm"])) if capture["type"] == "same_train" else None
                if loc:
                    x, y = loc["position"]
                    x, y = x * self.map_scale + self.map_pan_x, y * self.map_scale + self.map_pan_y
                else:
                    x, y = 200, 120
            self.canvas.create_rectangle(x - 56, y - 34, x + 56, y + 2, fill="#2d0f12", outline="#f3b5bc", width=2)
            self.canvas.create_text(x, y - 16, text=text, fill="white", font=self.fonts["body_bold"])

    def render(self) -> None:
        self.render_clock()
        self.render_hud()
        self.render_plan_board()
        self.render_action_card()
        self.render_result()
        self.render_map()

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    client = OniChaseV2Client()
    client.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
