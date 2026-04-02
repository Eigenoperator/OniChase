#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any


ROOT = Path(__file__).resolve().parent
STATIONS_PATH = ROOT / "data" / "yamanote_stations.json"
TRAINS_PATH = ROOT / "data" / "yamanote_weekday_train_instances_merged.json"

RUNNER_COLOR = "#dc4d62"
HUNTER_COLOR = "#2d6cdf"
YAMANOTE_COLOR = "#80c241"
BG = "#efe5d2"
INK = "#1f2933"
MUTED = "#697586"
PANEL = "#fffaf2"
LINE = "#dcd4c3"


def load_json(path: Path) -> dict[str, Any]:
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


class OniChaseLocalClient:
    def __init__(self) -> None:
        self.station_data = load_json(STATIONS_PATH)
        self.train_data = load_json(TRAINS_PATH)
        self.stations = sorted(self.station_data["stations"], key=lambda item: item["order"])
        self.station_map = {station["id"]: station for station in self.stations}
        self.train_map = {train["train_number"]: train for train in self.train_data["train_instances"]}

        self.active_mode = "runner"
        self.players = {
            "runner": {
                "start_station_id": "TOKYO",
                "input_mode": "plan",
                "steps": [],
            },
            "hunter": {
                "start_station_id": "SHINJUKU",
                "input_mode": "actions",
                "passive_hold": True,
                "steps": [{"type": "WAIT_UNTIL", "until_hhmm": "07:00"}],
            },
        }
        self.start_time = "06:00"
        self.end_time = "07:00"
        self.map_coords: dict[str, tuple[float, float, float]] = {}
        self.map_pan_x = 0.0
        self.map_pan_y = 0.0
        self.map_scale = 1.12
        self._drag_last: tuple[int, int] | None = None
        self.compute_map_coords()

        self.root = tk.Tk()
        self.root.title("OniChase Local Client")
        self.root.configure(bg=BG)
        self.root.geometry("1500x920")
        self.root.minsize(1280, 820)

        self.hud_var = tk.StringVar()
        self.test_var = tk.StringVar()
        self.train_var = tk.StringVar()
        self.quick_var = tk.StringVar()
        self.duel_var = tk.StringVar()
        self.plan_var = tk.StringVar()
        self.options_var = tk.StringVar()

        self.build_ui()
        self.render()

    def compute_map_coords(self) -> None:
        center_x = 510
        center_y = 395
        radius = 280
        start_angle_deg = 115
        for index, station in enumerate(self.stations):
            angle = math.radians(start_angle_deg + index * 360 / len(self.stations))
            x = center_x + math.cos(angle) * radius
            y = center_y + math.sin(angle) * radius
            self.map_coords[station["id"]] = (x, y, angle)

    def build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        topbar = tk.Frame(self.root, bg=PANEL, padx=18, pady=14, highlightbackground=LINE, highlightthickness=1)
        topbar.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        topbar.columnconfigure(0, weight=1)

        title = tk.Label(topbar, text="OniChase Local Client", bg=PANEL, fg=INK, font=("Helvetica", 22, "bold"))
        title.grid(row=0, column=0, sticky="w")
        subtitle = tk.Label(
            topbar,
            text="Local playtest shell for the real Yamanote timetable. No browser, no local website, just the board.",
            bg=PANEL,
            fg=MUTED,
            font=("Helvetica", 11),
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        button_bar = tk.Frame(topbar, bg=PANEL)
        button_bar.grid(row=0, column=1, rowspan=2, sticky="e")
        ttk.Button(button_bar, text="Runner Mode", command=lambda: self.set_active_mode("runner")).grid(row=0, column=0, padx=4)
        ttk.Button(button_bar, text="Hunter Mode", command=lambda: self.set_active_mode("hunter")).grid(row=0, column=1, padx=4)
        ttk.Button(button_bar, text="Load Test Preset", command=self.apply_test_preset).grid(row=0, column=2, padx=4)
        ttk.Button(button_bar, text="Refresh", command=self.render).grid(row=0, column=3, padx=4)

        shell = tk.Frame(self.root, bg=BG)
        shell.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        shell.columnconfigure(0, weight=1)
        shell.columnconfigure(1, weight=0)
        shell.rowconfigure(0, weight=1)

        left = tk.Frame(shell, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        info_row = tk.Frame(left, bg=PANEL)
        info_row.grid(row=0, column=0, sticky="ew", padx=16, pady=16)
        for idx in range(3):
            info_row.columnconfigure(idx, weight=1)

        self.hud_label = self.make_card(info_row, self.hud_var)
        self.hud_label.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.test_label = self.make_card(info_row, self.test_var)
        self.test_label.grid(row=0, column=1, sticky="nsew", padx=4)
        self.train_label = self.make_card(info_row, self.train_var)
        self.train_label.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        map_frame = tk.Frame(left, bg=PANEL)
        map_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))
        map_frame.rowconfigure(0, weight=1)
        map_frame.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(map_frame, bg="#f8f0e0", highlightthickness=0, width=1020, height=760)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.configure(cursor="fleur")
        self.canvas.bind("<ButtonPress-1>", self.on_map_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_map_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_map_drag_end)

        self.quick_label = tk.Label(
            left,
            textvariable=self.quick_var,
            justify="left",
            anchor="w",
            bg="#1d2129",
            fg="white",
            padx=18,
            pady=14,
            font=("Helvetica", 11),
        )
        self.quick_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))

        right = tk.Frame(shell, bg=BG, width=420)
        right.grid(row=0, column=1, sticky="ns")
        right.grid_propagate(False)
        right.columnconfigure(0, weight=1)

        self.duel_label = self.make_card(right, self.duel_var, width=48)
        self.duel_label.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.plan_label = self.make_card(right, self.plan_var, width=48)
        self.plan_label.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.options_label = self.make_card(right, self.options_var, width=48)
        self.options_label.grid(row=2, column=0, sticky="ew")

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
            font=("Helvetica", 11),
            highlightbackground=LINE,
            highlightthickness=1,
        )

    def apply_test_preset(self) -> None:
        self.active_mode = "runner"
        self.start_time = "06:00"
        self.end_time = "07:00"
        self.players["runner"] = {
            "start_station_id": "TOKYO",
            "input_mode": "plan",
            "steps": [],
        }
        self.players["hunter"] = {
            "start_station_id": "SHINJUKU",
            "input_mode": "actions",
            "passive_hold": True,
            "steps": [{"type": "WAIT_UNTIL", "until_hhmm": self.end_time}],
        }
        self.render()

    def set_active_mode(self, mode: str) -> None:
        self.active_mode = mode
        self.render()

    def on_map_drag_start(self, event: tk.Event) -> None:
        self._drag_last = (event.x, event.y)

    def on_map_drag_move(self, event: tk.Event) -> None:
        if self._drag_last is None:
            self._drag_last = (event.x, event.y)
            return
        last_x, last_y = self._drag_last
        dx = event.x - last_x
        dy = event.y - last_y
        self.map_pan_x += dx
        self.map_pan_y += dy
        self.canvas.move("board", dx, dy)
        self._drag_last = (event.x, event.y)

    def on_map_drag_end(self, _event: tk.Event) -> None:
        self._drag_last = None

    def preview_player(self, player_id: str) -> dict[str, Any]:
        player = self.players[player_id]
        current_minute = hhmm_to_minutes(self.start_time)
        current_station_id = player["start_station_id"]
        current_train = None
        current_board_stop = None
        events: list[dict[str, Any]] = [{"type": "START_AT_STATION", "station_id": current_station_id}]
        resolved_steps = []
        error = None

        for index, step in enumerate(player["steps"], start=1):
            try:
                if step["type"] == "WAIT_UNTIL":
                    target = hhmm_to_minutes(step["until_hhmm"])
                    if current_station_id is None:
                        raise ValueError("Cannot wait while on a train.")
                    if target < current_minute:
                        raise ValueError("Cannot wait backwards in time.")
                    current_minute = target
                    events.append({"type": "WAIT_UNTIL", "station_id": current_station_id})
                    resolved_steps.append({"step_index": index, **step})
                    continue

                if step["type"] == "BOARD_TRAIN":
                    train = self.train_map.get(step["train_number"])
                    if not train:
                        raise ValueError(f"Unknown train {step['train_number']}.")
                    board_stop = self.find_boarding_stop(train, current_station_id, current_minute)
                    if not board_stop:
                        raise ValueError(f"Cannot board {step['train_number']} from {current_station_id}.")
                    current_minute = stop_departure_minutes(board_stop)
                    current_train = train
                    current_board_stop = board_stop
                    events.append({"type": "BOARD_TRAIN", "station_id": current_station_id, "train_number": train["train_number"]})
                    resolved_steps.append({"step_index": index, **step})
                    current_station_id = None
                    continue

                if step["type"] == "BOARD_ANY_OF":
                    picked = None
                    rejected = []
                    for candidate in step.get("candidates", []):
                        train = self.train_map.get(candidate["train_number"])
                        if not train:
                            rejected.append(candidate["train_number"])
                            continue
                        board_stop = self.find_boarding_stop(train, current_station_id, current_minute)
                        if not board_stop:
                            rejected.append(candidate["train_number"])
                            continue
                        picked = (train, board_stop)
                        break
                    if not picked:
                        raise ValueError("No candidate train is catchable.")
                    train, board_stop = picked
                    current_minute = stop_departure_minutes(board_stop)
                    current_train = train
                    current_board_stop = board_stop
                    events.append({"type": "PLAN_RESOLUTION", "station_id": current_station_id, "train_number": train["train_number"]})
                    events.append({"type": "BOARD_TRAIN", "station_id": current_station_id, "train_number": train["train_number"]})
                    resolved_steps.append(
                        {
                            "step_index": index,
                            "type": "BOARD_TRAIN",
                            "source_plan_type": "BOARD_ANY_OF",
                            "train_number": train["train_number"],
                            "rejected_candidates": rejected,
                        }
                    )
                    current_station_id = None
                    continue

                if step["type"] == "RIDE_TO_STATION":
                    if not current_train or not current_board_stop:
                        raise ValueError("Not on a train.")
                    alight_stop = self.find_alight_stop(
                        current_train,
                        current_board_stop["sequence"],
                        step["station_id"],
                        step.get("loop_pass_index"),
                    )
                    if not alight_stop:
                        raise ValueError(f"Train {current_train['train_number']} does not reach {step['station_id']} later.")
                    current_minute = stop_arrival_minutes(alight_stop)
                    current_station_id = alight_stop["station_id"]
                    events.append(
                        {
                            "type": "ALIGHT_TRAIN",
                            "station_id": alight_stop["station_id"],
                            "train_number": current_train["train_number"],
                        }
                    )
                    resolved_steps.append({"step_index": index, **step})
                    current_train = None
                    current_board_stop = None
                    continue

                raise ValueError(f"Unsupported step type {step['type']}.")
            except Exception as exc:
                error = f"Step {index}: {exc}"
                break

        current_state = {"kind": "TRAIN", "train_number": current_train["train_number"]} if current_train else {"kind": "NODE", "station_id": current_station_id}
        return {
            "player_id": player_id,
            "current_time": minutes_to_hhmm(current_minute),
            "current_minute": current_minute,
            "current_state": current_state,
            "current_train": current_train,
            "current_board_stop": current_board_stop,
            "events": events,
            "resolved_steps": resolved_steps,
            "start_station_id": player["start_station_id"],
            "error": error,
        }

    def find_boarding_stop(self, train: dict[str, Any], station_id: str | None, earliest_minute: int) -> dict[str, Any] | None:
        if station_id is None:
            return None
        candidates = [
            stop
            for stop in train["stop_times"]
            if stop["station_id"] == station_id and stop_departure_minutes(stop) >= earliest_minute
        ]
        if not candidates:
            return None
        return sorted(candidates, key=stop_departure_minutes)[0]

    def find_alight_stop(
        self,
        train: dict[str, Any],
        boarded_sequence: int,
        station_id: str,
        loop_pass_index: int | None,
    ) -> dict[str, Any] | None:
        for stop in train["stop_times"]:
            if stop["sequence"] <= boarded_sequence:
                continue
            if stop["station_id"] != station_id:
                continue
            if loop_pass_index is not None and stop.get("loop_pass_index") != loop_pass_index:
                continue
            return stop
        return None

    def planned_station_ids(self, preview: dict[str, Any]) -> list[str]:
        station_ids: list[str] = []

        def push(station_id: str | None) -> None:
            if not station_id:
                return
            if station_ids and station_ids[-1] == station_id:
                return
            station_ids.append(station_id)

        push(preview["start_station_id"])
        for event in preview["events"]:
            push(event.get("station_id"))
        if preview["current_state"]["kind"] == "NODE":
            push(preview["current_state"]["station_id"])
        return station_ids

    def current_train_upcoming(self, preview: dict[str, Any]) -> list[str]:
        train = preview["current_train"]
        board_stop = preview["current_board_stop"]
        if not train or not board_stop:
            return []
        lines = []
        for stop in train["stop_times"]:
            if stop["sequence"] <= board_stop["sequence"]:
                continue
            station = self.station_map[stop["station_id"]]["names"]["en"]
            hhmm = stop.get("arrival_hhmm") or stop.get("departure_hhmm")
            lines.append(f"{hhmm}  {station}")
            if len(lines) >= 8:
                break
        return lines

    def format_state(self, preview: dict[str, Any]) -> str:
        state = preview["current_state"]
        if state["kind"] == "NODE":
            return self.station_map[state["station_id"]]["names"]["en"]
        return f"Train {state['train_number']}"

    def render(self) -> None:
        runner_preview = self.preview_player("runner")
        hunter_preview = self.preview_player("hunter")
        previews = {"runner": runner_preview, "hunter": hunter_preview}
        active_preview = previews[self.active_mode]
        passive_preview = previews["hunter" if self.active_mode == "runner" else "runner"]

        self.hud_var.set(
            f"{self.active_mode.upper()} HUD\n\n"
            f"Time: {active_preview['current_time']}\n"
            f"Location: {self.format_state(active_preview)}\n"
            f"Mode: {self.players[self.active_mode]['input_mode']}\n"
            f"Resolved steps: {len(active_preview['resolved_steps'])}\n"
            f"Status: {active_preview['error'] or 'Ready'}"
        )
        self.test_var.set(
            "PLAN TEST MODE\n\n"
            f"Game clock starts at {self.start_time}\n"
            f"Runner gets 1 minute before {self.start_time}\n"
            f"Runner start: {self.station_map[self.players['runner']['start_station_id']]['names']['en']}\n"
            f"Hunter start: {self.station_map[self.players['hunter']['start_station_id']]['names']['en']}\n"
            f"Hunter default: {'Hold position' if self.players['hunter'].get('passive_hold') else 'Editable'}"
        )
        upcoming = self.current_train_upcoming(active_preview)
        self.train_var.set(
            "TRAIN OUTLOOK\n\n"
            + ("\n".join(upcoming) if upcoming else "Not currently on a train.")
        )
        self.quick_var.set(
            f"ACTIVE SIDE: {self.active_mode.upper()}   |   CURRENT: {self.format_state(active_preview)}   |   OPPONENT: {self.format_state(passive_preview)}\n"
            f"ROUTE PREVIEW: {' -> '.join(self.station_map[s]['names']['en'] for s in self.planned_station_ids(active_preview)) or 'No route yet'}"
        )
        self.duel_var.set(
            "MATCH TABLE\n\n"
            f"Runner\n  Start: {self.station_map[self.players['runner']['start_station_id']]['names']['en']}\n  Live: {self.format_state(runner_preview)}\n  Steps: {len(self.players['runner']['steps'])}\n\n"
            f"Hunter\n  Start: {self.station_map[self.players['hunter']['start_station_id']]['names']['en']}\n  Live: {self.format_state(hunter_preview)}\n  Steps: {len(self.players['hunter']['steps'])}"
        )
        active_steps = self.players[self.active_mode]["steps"]
        if active_steps:
            rendered_steps = []
            for idx, step in enumerate(active_steps, start=1):
                if step["type"] == "WAIT_UNTIL":
                    desc = f"wait until {step['until_hhmm']}"
                elif step["type"] == "BOARD_TRAIN":
                    desc = f"board {step['train_number']}"
                elif step["type"] == "BOARD_ANY_OF":
                    desc = "board any of " + ", ".join(candidate["train_number"] for candidate in step.get("candidates", []))
                elif step["type"] == "RIDE_TO_STATION":
                    desc = "ride to " + self.station_map[step["station_id"]]["names"]["en"]
                else:
                    desc = step["type"]
                rendered_steps.append(f"{idx}. {desc}")
            plan_text = "\n".join(rendered_steps)
        else:
            plan_text = "No plan yet. This first local client is only a shell; editing tools come next."
        self.plan_var.set(f"{self.active_mode.upper()} PLAN\n\n{plan_text}")

        options = self.available_options(active_preview)
        self.options_var.set(
            "IMMEDIATE OPTIONS\n\n" + ("\n".join(options) if options else "No suggestion from the current state.")
        )
        self.draw_map(runner_preview, hunter_preview)

    def available_options(self, preview: dict[str, Any]) -> list[str]:
        if preview["error"]:
            return [preview["error"]]
        if preview["current_state"]["kind"] == "TRAIN":
            return [f"Stay on {preview['current_state']['train_number']}", *self.current_train_upcoming(preview)[:5]]
        station_id = preview["current_state"]["station_id"]
        minute = preview["current_minute"]
        suggestions = []
        for train in self.train_data["train_instances"]:
            board_stop = self.find_boarding_stop(train, station_id, minute)
            if not board_stop:
                continue
            suggestions.append(
                f"{train['train_number']} at {minutes_to_hhmm(stop_departure_minutes(board_stop))} · {train.get('direction_label', 'unknown')}"
            )
            if len(suggestions) >= 6:
                break
        return suggestions

    def draw_map(self, runner_preview: dict[str, Any], hunter_preview: dict[str, Any]) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(46, 36, text="JR Yamanote Line", anchor="w", fill=INK, font=("Helvetica", 22, "bold"), tags=("board",))
        self.canvas.create_text(46, 64, text="Drag with left mouse button to move the map", anchor="w", fill=MUTED, font=("Helvetica", 12), tags=("board",))

        coords = [self.map_coords[station["id"]] for station in self.stations]
        loop_points = [value for coord in coords for value in coord[:2]]
        first = coords[0]
        loop_points.extend(first[:2])
        self.canvas.create_line(*loop_points, width=34, fill="#d9ebc6", smooth=True, tags=("board",))
        self.canvas.create_line(*loop_points, width=14, fill=YAMANOTE_COLOR, smooth=True, tags=("board",))

        self.draw_plan_trace(self.preview_player(self.active_mode), self.active_mode, faded=False)
        self.draw_plan_trace(self.preview_player("hunter" if self.active_mode == "runner" else "runner"), "hunter" if self.active_mode == "runner" else "runner", faded=True)

        runner_station = runner_preview["current_state"].get("station_id") or runner_preview["current_board_stop"]["station_id"]
        hunter_station = hunter_preview["current_state"].get("station_id") or hunter_preview["current_board_stop"]["station_id"]

        for station in self.stations:
            station_id = station["id"]
            x, y, angle = self.map_coords[station_id]
            self.canvas.create_oval(x - 12, y - 12, x + 12, y + 12, fill="white", outline=YAMANOTE_COLOR, width=4, tags=("board",))
            label_x = x + math.cos(angle) * 34
            label_y = y + math.sin(angle) * 34
            self.canvas.create_text(label_x, label_y, text=station["names"]["en"], fill=INK, font=("Helvetica", 9), tags=("board",))

            if station_id == runner_station:
                self.canvas.create_oval(x + 8, y - 26, x + 26, y - 8, fill=RUNNER_COLOR, outline="white", width=3, tags=("board",))
            if station_id == hunter_station:
                self.canvas.create_oval(x - 26, y - 26, x - 8, y - 8, fill=HUNTER_COLOR, outline="white", width=3, tags=("board",))

        self.canvas.create_text(812, 720, text="Runner", fill=INK, font=("Helvetica", 11, "bold"), anchor="w", tags=("board",))
        self.canvas.create_oval(778, 710, 796, 728, fill=RUNNER_COLOR, outline="white", width=3, tags=("board",))
        self.canvas.create_text(812, 748, text="Hunter", fill=INK, font=("Helvetica", 11, "bold"), anchor="w", tags=("board",))
        self.canvas.create_oval(778, 738, 796, 756, fill=HUNTER_COLOR, outline="white", width=3, tags=("board",))
        self.canvas.scale("board", 0, 0, self.map_scale, self.map_scale)
        self.canvas.move("board", self.map_pan_x, self.map_pan_y)

    def draw_plan_trace(self, preview: dict[str, Any], player_id: str, faded: bool) -> None:
        station_ids = self.planned_station_ids(preview)
        if len(station_ids) < 2:
            return
        color = RUNNER_COLOR if player_id == "runner" else HUNTER_COLOR
        line_points = []
        for station_id in station_ids:
            x, y, _ = self.map_coords[station_id]
            line_points.extend([x, y])
        self.canvas.create_line(
            *line_points,
            fill=color,
            width=6 if faded else 8,
            dash=(6, 10) if faded else (12, 10),
            smooth=True,
            stipple="gray50" if faded else "",
            tags=("board",),
        )
        for index, station_id in enumerate(station_ids, start=1):
            x, y, _ = self.map_coords[station_id]
            self.canvas.create_oval(x - 10, y - 10, x + 10, y + 10, fill=color, outline="white", width=3, tags=("board",))
            self.canvas.create_text(x, y + 1, text=str(index), fill="white", font=("Helvetica", 9, "bold"), tags=("board",))

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    OniChaseLocalClient().run()
