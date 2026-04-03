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
SELECTED = "#c48a29"


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
        self.pending_board_train_numbers = {"runner": None, "hunter": None}
        self.start_time = "06:00"
        self.end_time = "07:00"
        self.map_coords: dict[str, tuple[float, float, float]] = {}
        self.map_pan_x = 0.0
        self.map_pan_y = 0.0
        self.map_scale = 1.12
        self._drag_last: tuple[int, int] | None = None
        self._drag_start: tuple[int, int] | None = None
        self._drag_distance = 0.0
        self.selected_station_id: str | None = self.players["runner"]["start_station_id"]
        self.compute_map_coords()

        self.root = tk.Tk()
        self.root.title("OniChase Local Client")
        self.root.configure(bg=BG)
        self.root.geometry("1500x920")
        self.root.minsize(1280, 820)
        self._right_panel_hover = False
        self.settings_window: tk.Toplevel | None = None
        self.font_size_offset = 10
        self.font_size_var = tk.IntVar(value=self.font_size_offset)
        self.phase = "PLANNING"
        self.planning_seconds_remaining = 60
        self.current_game_minute = hhmm_to_minutes(self.start_time)
        self.clock_running = False
        self.tick_job: str | None = None
        self.setup_fonts()
        self.setup_styles()

        self.clock_var = tk.StringVar()
        self.hud_var = tk.StringVar()
        self.test_var = tk.StringVar()
        self.train_var = tk.StringVar()
        self.quick_var = tk.StringVar()
        self.plan_var = tk.StringVar()
        self.result_var = tk.StringVar()
        self.result_detail_var = tk.StringVar()
        self.latest_result: dict[str, Any] | None = None
        self.selected_result_event_index: int = 0
        self.last_action_card_signature: tuple[Any, ...] | None = None

        self.build_ui()
        self.reset_match_flow(auto_start=True)
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

    def setup_fonts(self) -> None:
        family = "Helvetica"
        self.fonts = {
            "title": tkfont.Font(family=family, size=22, weight="bold"),
            "clock": tkfont.Font(family=family, size=20, weight="bold"),
            "clock_small": tkfont.Font(family=family, size=12, weight="bold"),
            "subtitle": tkfont.Font(family=family, size=11),
            "body": tkfont.Font(family=family, size=11),
            "body_bold": tkfont.Font(family=family, size=11, weight="bold"),
            "small": tkfont.Font(family=family, size=10),
            "small_bold": tkfont.Font(family=family, size=10, weight="bold"),
            "action_title": tkfont.Font(family=family, size=16, weight="bold"),
            "action_card": tkfont.Font(family=family, size=12, weight="bold"),
            "action_meta": tkfont.Font(family=family, size=10),
            "map_title": tkfont.Font(family=family, size=22, weight="bold"),
            "map_subtitle": tkfont.Font(family=family, size=12),
            "station": tkfont.Font(family=family, size=9),
            "station_selected": tkfont.Font(family=family, size=10, weight="bold"),
            "waypoint": tkfont.Font(family=family, size=9, weight="bold"),
        }

    def setup_styles(self) -> None:
        self.style = ttk.Style(self.root)
        self.style.configure("TButton", font=self.fonts["body"])

    def apply_font_size(self, offset: int) -> None:
        self.font_size_offset = offset
        size_map = {
            "title": 22,
            "clock": 20,
            "clock_small": 12,
            "subtitle": 11,
            "body": 11,
            "body_bold": 11,
            "small": 10,
            "small_bold": 10,
            "action_title": 16,
            "action_card": 12,
            "action_meta": 10,
            "map_title": 22,
            "map_subtitle": 12,
            "station": 9,
            "station_selected": 10,
            "waypoint": 9,
        }
        for key, base_size in size_map.items():
            self.fonts[key].configure(size=max(8, base_size + offset))
        self.style.configure("TButton", font=self.fonts["body"])
        self.render()

    def open_settings(self) -> None:
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        window.title("Settings")
        window.configure(bg=PANEL)
        window.geometry("360x180")
        window.resizable(False, False)
        self.settings_window = window

        frame = tk.Frame(window, bg=PANEL, padx=18, pady=18)
        frame.pack(fill="both", expand=True)

        title = tk.Label(frame, text="Settings", bg=PANEL, fg=INK, font=self.fonts["body_bold"], anchor="w")
        title.pack(anchor="w")

        desc = tk.Label(
            frame,
            text="UI Font Size",
            bg=PANEL,
            fg=MUTED,
            font=self.fonts["body"],
            anchor="w",
        )
        desc.pack(anchor="w", pady=(12, 6))

        scale = tk.Scale(
            frame,
            from_=-3,
            to=12,
            orient="horizontal",
            resolution=1,
            variable=self.font_size_var,
            command=self.on_font_size_change,
            bg=PANEL,
            fg=INK,
            highlightthickness=0,
            font=self.fonts["small"],
        )
        scale.pack(fill="x")

        value_label = tk.Label(
            frame,
            textvariable=self.font_size_var,
            bg=PANEL,
            fg=INK,
            font=self.fonts["body"],
            anchor="w",
        )
        value_label.pack(anchor="w", pady=(8, 0))

    def on_font_size_change(self, value: str) -> None:
        self.apply_font_size(int(float(value)))

    def build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        topbar = tk.Frame(self.root, bg=PANEL, padx=18, pady=14, highlightbackground=LINE, highlightthickness=1)
        topbar.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        topbar.columnconfigure(0, weight=1)
        topbar.columnconfigure(1, weight=0)
        topbar.columnconfigure(2, weight=0)

        title = tk.Label(topbar, text="OniChase Local Client", bg=PANEL, fg=INK, font=self.fonts["title"])
        title.grid(row=0, column=0, sticky="w")
        subtitle = tk.Label(
            topbar,
            text="Local playtest shell for the real Yamanote timetable. No browser, no local website, just the board.",
            bg=PANEL,
            fg=MUTED,
            font=self.fonts["subtitle"],
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.clock_label = tk.Label(
            topbar,
            textvariable=self.clock_var,
            justify="left",
            anchor="w",
            bg="#b8441f",
            fg="white",
            padx=18,
            pady=12,
            font=self.fonts["clock"],
        )
        self.clock_label.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 12))

        button_bar = tk.Frame(topbar, bg=PANEL)
        button_bar.grid(row=0, column=2, rowspan=2, sticky="e")
        ttk.Button(button_bar, text="Runner Mode", command=lambda: self.set_active_mode("runner")).grid(row=0, column=0, padx=4)
        ttk.Button(button_bar, text="Hunter Mode", command=lambda: self.set_active_mode("hunter")).grid(row=0, column=1, padx=4)
        ttk.Button(button_bar, text="Load Test Preset", command=self.apply_test_preset).grid(row=0, column=2, padx=4)
        ttk.Button(button_bar, text="Start Match", command=self.start_match_now).grid(row=0, column=3, padx=4)
        ttk.Button(button_bar, text="Pause/Resume", command=self.toggle_clock_running).grid(row=0, column=4, padx=4)
        ttk.Button(button_bar, text="Settings", command=self.open_settings).grid(row=0, column=5, padx=4)

        shell = tk.PanedWindow(
            self.root,
            orient=tk.HORIZONTAL,
            bg=BG,
            sashrelief=tk.RAISED,
            sashwidth=10,
            bd=0,
        )
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
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)

        self.quick_label = tk.Label(
            left,
            textvariable=self.quick_var,
            justify="left",
            anchor="w",
            bg="#1d2129",
            fg="white",
            padx=18,
            pady=14,
            font=self.fonts["body"],
        )
        self.quick_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))

        right = tk.Frame(shell, bg=BG, width=420)
        right.grid_propagate(False)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self.right_canvas = tk.Canvas(right, bg=BG, highlightthickness=0, width=420)
        self.right_canvas.grid(row=0, column=0, sticky="nsew")
        right_scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.right_canvas.yview)
        right_scrollbar.grid(row=0, column=1, sticky="ns")
        self.right_canvas.configure(yscrollcommand=right_scrollbar.set)

        self.right_scroll_frame = tk.Frame(self.right_canvas, bg=BG)
        self.right_canvas_window = self.right_canvas.create_window((0, 0), window=self.right_scroll_frame, anchor="nw")
        self.right_scroll_frame.bind("<Configure>", self.on_right_frame_configure)
        self.right_canvas.bind("<Configure>", self.on_right_canvas_configure)
        self.bind_right_panel_hover(self.right_canvas)
        self.bind_right_panel_hover(self.right_scroll_frame)
        self.root.bind_all("<MouseWheel>", self.on_right_panel_mouse_wheel)
        self.root.bind_all("<Button-4>", self.on_right_panel_mouse_wheel)
        self.root.bind_all("<Button-5>", self.on_right_panel_mouse_wheel)

        self.right_pane = tk.PanedWindow(
            self.right_scroll_frame,
            orient=tk.VERTICAL,
            bg=BG,
            sashrelief=tk.RAISED,
            sashwidth=8,
            bd=0,
        )
        self.right_pane.grid(row=0, column=0, sticky="nsew")
        self.right_scroll_frame.columnconfigure(0, weight=1)
        self.right_scroll_frame.rowconfigure(0, weight=1)
        self.bind_right_panel_hover(self.right_pane)

        self.info_stack = tk.Frame(self.right_pane, bg=BG)
        self.info_stack.columnconfigure(0, weight=1)
        self.plan_card = tk.Frame(self.info_stack, bg=PANEL, highlightbackground=LINE, highlightthickness=1, padx=12, pady=12)
        self.plan_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.plan_card.columnconfigure(0, weight=1)

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
        self.bind_right_panel_hover(self.result_event_list)

        self.result_detail_label = self.make_card(self.result_container, self.result_detail_var, width=48)
        self.result_detail_label.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        self.right_pane.add(self.info_stack, minsize=220, stretch="always")
        self.right_pane.add(self.action_card, minsize=180)
        self.right_pane.add(self.result_container, minsize=160)

        shell.add(left, minsize=760, stretch="always")
        shell.add(right, minsize=320)

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

    def render_plan_board(self, cursor_preview: dict[str, Any], resolved_count: int) -> None:
        for child in self.plan_card.winfo_children():
            child.destroy()

        header = tk.Frame(self.plan_card, bg="#8c4d19", padx=10, pady=8)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        title = tk.Label(
            header,
            text=f"{self.active_mode.upper()} PLAN BOARD",
            bg="#8c4d19",
            fg="white",
            font=self.fonts["action_title"],
            anchor="w",
            justify="left",
        )
        title.pack(anchor="w")
        sub = tk.Label(
            header,
            text="This is the route you are building now.",
            bg="#8c4d19",
            fg="#fff1df",
            font=self.fonts["small"],
            anchor="w",
            justify="left",
        )
        sub.pack(anchor="w", pady=(3, 0))

        summary = tk.Label(
            self.plan_card,
            text=(
                f"Cursor: {self.format_state(cursor_preview)}\n"
                f"Planned legs: {len(self.players[self.active_mode]['steps'])}\n"
                f"Resolved now: {resolved_count}"
            ),
            bg=PANEL,
            fg=MUTED,
            font=self.fonts["small"],
            anchor="w",
            justify="left",
        )
        summary.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        steps = self.players[self.active_mode]["steps"]
        if not steps:
            empty = tk.Label(
                self.plan_card,
                text="No plan yet. Start by choosing the first train.",
                bg=PANEL,
                fg=INK,
                font=self.fonts["body"],
                anchor="w",
                justify="left",
            )
            empty.grid(row=2, column=0, sticky="ew")
            return

        chain_station = self.players[self.active_mode]["start_station_id"]
        pending_train_number = None
        row = 2
        leg_index = 1
        for step_index, step in enumerate(steps, start=1):
            is_done = step_index <= resolved_count
            if step["type"] == "WAIT_UNTIL":
                card = tk.Frame(self.plan_card, bg="#f3ede2", highlightbackground=LINE, highlightthickness=1, padx=10, pady=8)
                card.grid(row=row, column=0, sticky="ew", pady=(0, 6))
                label = tk.Label(
                    card,
                    text=f"WAIT  until {step['until_hhmm']}",
                    bg="#f3ede2",
                    fg=INK,
                    font=self.fonts["body_bold"],
                    anchor="w",
                    justify="left",
                )
                label.pack(anchor="w")
                meta = tk.Label(
                    card,
                    text=f"Status: {'DONE' if is_done else 'NEXT'}",
                    bg="#f3ede2",
                    fg=MUTED,
                    font=self.fonts["small"],
                    anchor="w",
                    justify="left",
                )
                meta.pack(anchor="w", pady=(4, 0))
                row += 1
                continue

            if step["type"] == "BOARD_TRAIN":
                pending_train_number = step["train_number"]
                continue

            if step["type"] == "RIDE_TO_STATION":
                accent = "#e5f2dc" if not is_done else "#d7e4f8"
                card = tk.Frame(self.plan_card, bg=accent, highlightbackground=LINE, highlightthickness=1, padx=10, pady=8)
                card.grid(row=row, column=0, sticky="ew", pady=(0, 6))
                top = tk.Label(
                    card,
                    text=f"LEG {leg_index}  {'DONE' if is_done else 'NEXT'}",
                    bg=accent,
                    fg=INK,
                    font=self.fonts["small_bold"],
                    anchor="w",
                    justify="left",
                )
                top.pack(anchor="w")
                main = tk.Label(
                    card,
                    text=f"{self.station_map[chain_station]['names']['en']}  ->  {pending_train_number or '?'}  ->  {self.station_map[step['station_id']]['names']['en']}",
                    bg=accent,
                    fg=INK,
                    font=self.fonts["body_bold"],
                    anchor="w",
                    justify="left",
                    wraplength=330,
                )
                main.pack(anchor="w", pady=(4, 0))
                row += 1
                chain_station = step["station_id"]
                pending_train_number = None
                leg_index += 1
                continue

            fallback = tk.Label(
                self.plan_card,
                text=f"{step_index}. {step['type']}",
                bg=PANEL,
                fg=INK,
                font=self.fonts["body"],
                anchor="w",
                justify="left",
            )
            fallback.grid(row=row, column=0, sticky="ew", pady=(0, 6))
            row += 1

    def on_right_frame_configure(self, _event: tk.Event) -> None:
        self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all"))

    def on_right_canvas_configure(self, event: tk.Event) -> None:
        self.right_canvas.itemconfigure(self.right_canvas_window, width=event.width)

    def bind_right_panel_hover(self, widget: tk.Widget) -> None:
        widget.bind("<Enter>", self.on_right_panel_enter, add="+")
        widget.bind("<Leave>", self.on_right_panel_leave, add="+")

    def on_right_panel_enter(self, _event: tk.Event) -> None:
        self._right_panel_hover = True

    def on_right_panel_leave(self, _event: tk.Event) -> None:
        pointer_widget = self.root.winfo_containing(self.root.winfo_pointerx(), self.root.winfo_pointery())
        self._right_panel_hover = self.is_widget_in_right_panel(pointer_widget)

    def is_widget_in_right_panel(self, widget: tk.Widget | None) -> bool:
        current = widget
        while current is not None:
            if current == self.right_canvas or current == self.right_scroll_frame:
                return True
            current = current.master
        return False

    def on_right_panel_mouse_wheel(self, event: tk.Event) -> None:
        if not self._right_panel_hover:
            return
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1
        self.right_canvas.yview_scroll(delta, "units")

    def apply_right_pane_layout(self, emphasize_actions: bool) -> None:
        try:
            self.right_pane.update_idletasks()
            pane_height = self.right_pane.winfo_height()
            if pane_height <= 0:
                return
            if emphasize_actions:
                info_height = 240
                result_top = max(info_height + 260, pane_height - 190)
            else:
                info_height = 300
                result_top = max(info_height + 180, pane_height - 190)
            self.right_pane.sash_place(0, 0, info_height)
            self.right_pane.sash_place(1, 0, result_top)
        except tk.TclError:
            return

    def reset_match_flow(self, auto_start: bool = True) -> None:
        if self.tick_job:
            self.root.after_cancel(self.tick_job)
            self.tick_job = None
        self.phase = "PLANNING"
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
        elif self.phase == "LIVE":
            end_minute = hhmm_to_minutes(self.end_time)
            if self.current_game_minute < end_minute:
                self.current_game_minute += 1
            else:
                self.phase = "ENDED"
                self.clock_running = False
        self.render()
        if self.clock_running:
            self.schedule_tick()

    def start_match_now(self) -> None:
        self.phase = "LIVE"
        self.current_game_minute = hhmm_to_minutes(self.start_time)
        self.clock_running = True
        self.schedule_tick()
        self.render()

    def toggle_clock_running(self) -> None:
        self.clock_running = not self.clock_running
        if self.clock_running:
            self.schedule_tick()
        elif self.tick_job:
            self.root.after_cancel(self.tick_job)
            self.tick_job = None
        self.render()

    def visible_game_minute(self) -> int:
        if self.phase == "PLANNING":
            return hhmm_to_minutes(self.start_time)
        return self.current_game_minute

    def apply_test_preset(self) -> None:
        self.active_mode = "runner"
        self.start_time = "06:00"
        self.end_time = "07:00"
        self.pending_board_train_numbers = {"runner": None, "hunter": None}
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
        self.reset_match_flow(auto_start=True)
        self.render()

    def set_active_mode(self, mode: str) -> None:
        self.active_mode = mode
        self.render()

    def active_player(self) -> dict[str, Any]:
        return self.players[self.active_mode]

    def active_preview(self) -> dict[str, Any]:
        return self.preview_player(self.active_mode, self.visible_game_minute())

    def plan_cursor_preview(self, player_id: str | None = None) -> dict[str, Any]:
        target = player_id or self.active_mode
        if self.phase == "PLANNING" and self.current_replay_event() is None:
            return self.preview_player(target, None)
        return self.preview_player(target, self.visible_game_minute())

    def pending_board_train_number(self) -> str | None:
        return self.pending_board_train_numbers[self.active_mode]

    def clear_pending_board_train(self, player_id: str | None = None) -> None:
        target = player_id or self.active_mode
        self.pending_board_train_numbers[target] = None

    def choose_another_train(self) -> None:
        self.clear_pending_board_train()
        self.set_result_message(
            "ACTION",
            [
                "Cleared the current train selection.",
                "Choose another departure in STEP 1.",
            ],
        )
        self.render()
        self.root.after_idle(lambda: self.right_canvas.yview_moveto(0.0))

    def set_pending_board_train(self, train_number: str) -> None:
        self.pending_board_train_numbers[self.active_mode] = train_number
        self.set_result_message(
            "ACTION",
            [
                f"Selected train {train_number}.",
                "Now choose where you want to get off in STEP 2 below.",
            ],
        )
        self.render()
        self.root.after_idle(lambda: self.right_canvas.yview_moveto(1.0))

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

    def set_result_message(self, title: str, lines: list[str]) -> None:
        self.result_var.set(title + "\n\n" + "\n".join(lines))
        self.result_detail_var.set("")
        self.latest_result = None
        self.selected_result_event_index = 0
        self.refresh_result_event_list()

    def set_start_to_selected(self) -> None:
        if not self.selected_station_id:
            self.set_result_message("ACTION", ["Select a station first."])
            return
        active_player = self.active_player()
        active_player["start_station_id"] = self.selected_station_id
        active_player["steps"] = []
        self.clear_pending_board_train()
        self.reset_passive_hold_if_needed()
        self.set_result_message(
            "ACTION",
            [
                f"{self.active_mode.title()} start moved to {self.station_map[self.selected_station_id]['names']['en']}.",
                "Existing steps were cleared so the plan stays consistent.",
            ],
        )
        self.render()

    def add_board_train_step(self, train_number: str) -> None:
        preview = self.plan_cursor_preview()
        if preview["error"]:
            self.set_result_message("ACTION", [preview["error"]])
            self.render()
            return
        if preview["current_state"]["kind"] != "NODE":
            self.set_result_message("ACTION", ["You can only board while currently at a station."])
            self.render()
            return
        station_id = preview["current_state"]["station_id"]
        minute = preview["current_minute"]
        train = self.train_map.get(train_number)
        if not train:
            self.set_result_message("ACTION", [f"Unknown train {train_number}."])
            self.render()
            return
        best_stop = self.find_boarding_stop(train, station_id, minute)
        if not best_stop:
            self.set_result_message("ACTION", [f"Train {train_number} is not catchable from the current state."])
            self.render()
            return
        removed = self.truncate_future_steps_to_current()
        self.active_player()["steps"].append({"type": "BOARD_TRAIN", "train_number": train_number})
        self.clear_pending_board_train()
        self.reset_passive_hold_if_needed()
        note = f"Trimmed {removed} future step(s) before adding the new branch." if removed else "Appended to the current future plan."
        self.set_result_message(
            "ACTION",
            [
                f"Added BOARD_TRAIN {train_number}.",
                f"Departure: {minutes_to_hhmm(stop_departure_minutes(best_stop))} from {self.station_map[station_id]['names']['en']}.",
                note,
            ],
        )
        self.render()

    def add_ride_to_station_step(self, station_id: str) -> None:
        preview = self.plan_cursor_preview()
        if preview["error"]:
            self.set_result_message("ACTION", [preview["error"]])
            self.render()
            return
        if preview["current_state"]["kind"] != "TRAIN":
            self.set_result_message("ACTION", ["You can only add RIDE_TO_STATION while currently on a train."])
            self.render()
            return
        if preview["current_board_stop"] is None or preview["current_train"] is None:
            self.set_result_message("ACTION", ["Current train context is incomplete."])
            self.render()
            return
        alight_stop = self.find_alight_stop(
            preview["current_train"],
            preview["current_board_stop"]["sequence"],
            station_id,
            None,
        )
        if not alight_stop:
            self.set_result_message("ACTION", ["That train does not reach the selected station later."])
            self.render()
            return
        removed = self.truncate_future_steps_to_current()
        self.active_player()["steps"].append({"type": "RIDE_TO_STATION", "station_id": station_id})
        self.clear_pending_board_train()
        self.reset_passive_hold_if_needed()
        note = f"Trimmed {removed} future step(s) before adding the new branch." if removed else "Appended to the current future plan."
        self.set_result_message(
            "ACTION",
            [
                f"Added RIDE_TO_STATION {self.station_map[station_id]['names']['en']}.",
                f"Arrival: {alight_stop.get('arrival_hhmm') or alight_stop.get('departure_hhmm')}.",
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
        self.set_result_message(
            "ACTION",
            [
                f"Added WAIT_UNTIL {minutes_to_hhmm(target_minute)}.",
                f"Current station: {self.station_map[preview['current_state']['station_id']]['names']['en']}.",
                note,
            ],
        )
        self.render()

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
        alight_stop = self.find_alight_stop(train, board_stop["sequence"], station_id, None)
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
                f"Planned {train_number} from {self.station_map[station_from]['names']['en']} to {self.station_map[station_id]['names']['en']}.",
                f"Depart {minutes_to_hhmm(stop_departure_minutes(board_stop))}  Arrive {alight_stop.get('arrival_hhmm') or alight_stop.get('departure_hhmm')}.",
                note,
            ],
        )
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
            input_mode = player.get("input_mode", "actions")
            payload: dict[str, Any] = {
                "start_station_id": player["start_station_id"],
            }
            if input_mode == "plan":
                payload["plan"] = {"steps": list(player["steps"])}
            else:
                payload["actions"] = list(player["steps"])
            players_payload[player_id] = payload
        return {
            "id": "local-client-live",
            "start_time_hhmm": self.start_time,
            "end_time_hhmm": self.end_time,
            "players": players_payload,
        }

    def run_simulation(self) -> None:
        try:
            scenario = self.build_scenario()
            result = build_result(scenario, self.train_data)
        except Exception as exc:
            self.set_result_message("SIMULATION", [f"Failed to simulate: {exc}"])
            self.render()
            return

        self.latest_result = result
        self.selected_result_event_index = 0
        capture = result["capture"]
        lines = [
            f"Scenario: {result['scenario_id']}",
            f"Events: {len(result['match_event_log'])}",
        ]
        if capture is None:
            lines.append("Capture: none")
        elif capture["type"] == "same_node":
            lines.append(f"Capture: same_node at {capture['station_id']} {capture['time_hhmm']}")
        else:
            lines.append(f"Capture: same_train on {capture['train_number']} {capture['time_hhmm']}")
        lines.append("")
        lines.append("Recent events:")
        for event in result["match_event_log"][-6:]:
            parts = [event["time_hhmm"], event["type"]]
            if event.get("player_id"):
                parts.append(event["player_id"])
            if event.get("station_id"):
                parts.append(event["station_id"])
            if event.get("train_number"):
                parts.append(event["train_number"])
            if event.get("capture_type"):
                parts.append(event["capture_type"])
            lines.append("- " + " ".join(parts))
        self.set_result_message("SIMULATION", lines)
        self.latest_result = result
        self.selected_result_event_index = 0
        self.refresh_result_event_list()
        self.render()

    def on_result_event_select(self, _event: tk.Event) -> None:
        selection = self.result_event_list.curselection()
        if not selection:
            return
        self.selected_result_event_index = int(selection[0])
        self.update_result_detail()
        self.render()

    def refresh_result_event_list(self) -> None:
        self.result_event_list.delete(0, tk.END)
        if not self.latest_result:
            self.result_event_list.insert(tk.END, "No replay yet. Run Simulation first.")
            self.result_event_list.selection_clear(0, tk.END)
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

        max_index = len(self.latest_result["match_event_log"]) - 1
        self.selected_result_event_index = max(0, min(self.selected_result_event_index, max_index))
        self.result_event_list.selection_clear(0, tk.END)
        self.result_event_list.selection_set(self.selected_result_event_index)
        self.result_event_list.see(self.selected_result_event_index)
        self.update_result_detail()

    def update_result_detail(self) -> None:
        if not self.latest_result or not self.latest_result["match_event_log"]:
            self.result_detail_var.set("EVENT DETAIL\n\nNo replay event selected.")
            return
        event = self.latest_result["match_event_log"][self.selected_result_event_index]
        lines = [
            "EVENT DETAIL",
            "",
            f"Time: {event['time_hhmm']}",
            f"Type: {event['type']}",
        ]
        if event.get("player_id"):
            lines.append(f"Player: {event['player_id']}")
        if event.get("station_id"):
            lines.append(f"Station: {event['station_id']}")
        if event.get("train_number"):
            lines.append(f"Train: {event['train_number']}")
        if event.get("capture_type"):
            lines.append(f"Capture: {event['capture_type']}")
        if event.get("trigger_event_type"):
            lines.append(f"Trigger: {event['trigger_event_type']}")
        state_after = event.get("state_after")
        if state_after:
            runner_state = state_after.get("runner", {})
            hunter_state = state_after.get("hunter", {})
            lines.extend(
                [
                    "",
                    f"Runner after: {self.format_carrier(runner_state)}",
                    f"Hunter after: {self.format_carrier(hunter_state)}",
                ]
            )
        self.result_detail_var.set("\n".join(lines))

    def current_replay_event(self) -> dict[str, Any] | None:
        if not self.latest_result or not self.latest_result.get("match_event_log"):
            return None
        events = self.latest_result["match_event_log"]
        index = max(0, min(self.selected_result_event_index, len(events) - 1))
        return events[index]

    def train_anchor_station_id(self, train_number: str, time_minute: int) -> str | None:
        train = self.train_map.get(train_number)
        if not train:
            return None
        best_station_id = None
        best_distance = None
        for stop in train["stop_times"]:
            for key in ("arrival_hhmm", "departure_hhmm"):
                raw = stop.get(key)
                if not raw:
                    continue
                stop_minute = hhmm_to_minutes(raw)
                distance = abs(stop_minute - time_minute)
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best_station_id = stop["station_id"]
        return best_station_id

    def replay_preview_from_state(self, player_id: str, state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        current_state = dict(state)
        map_station_id = None
        current_train = None
        if current_state.get("kind") == "NODE":
            map_station_id = current_state.get("station_id")
        elif current_state.get("kind") == "TRAIN":
            current_train = self.train_map.get(current_state["train_number"])
            map_station_id = self.train_anchor_station_id(current_state["train_number"], event["time_minute"])
        return {
            "player_id": player_id,
            "current_time": event["time_hhmm"],
            "current_minute": event["time_minute"],
            "current_state": current_state,
            "current_train": current_train,
            "current_board_stop": None,
            "events": [],
            "resolved_steps": [],
            "start_station_id": self.players[player_id]["start_station_id"],
            "error": None,
            "map_station_id": map_station_id,
            "replay_focus": True,
        }

    def format_carrier(self, state: dict[str, Any]) -> str:
        if not state:
            return "unknown"
        if state.get("kind") == "NODE":
            station_id = state.get("station_id")
            if not station_id:
                return "node"
            return self.station_map.get(station_id, {"names": {"en": station_id}})["names"]["en"]
        if state.get("kind") == "TRAIN":
            return f"Train {state.get('train_number', '?')}"
        return state.get("kind", "unknown")

    def on_map_drag_start(self, event: tk.Event) -> None:
        self._drag_last = (event.x, event.y)
        self._drag_start = (event.x, event.y)
        self._drag_distance = 0.0

    def on_map_drag_move(self, event: tk.Event) -> None:
        if self._drag_last is None:
            self._drag_last = (event.x, event.y)
            return
        last_x, last_y = self._drag_last
        dx = event.x - last_x
        dy = event.y - last_y
        self._drag_distance += abs(dx) + abs(dy)
        self.map_pan_x += dx
        self.map_pan_y += dy
        self.canvas.move("board", dx, dy)
        self._drag_last = (event.x, event.y)

    def on_map_drag_end(self, event: tk.Event) -> None:
        if self._drag_distance < 6:
            self.select_station_at_canvas_point(event.x, event.y)
        self._drag_last = None
        self._drag_start = None
        self._drag_distance = 0.0

    def on_mouse_wheel(self, event: tk.Event) -> None:
        if getattr(event, "num", None) == 4:
            factor = 1.1
        elif getattr(event, "num", None) == 5:
            factor = 1 / 1.1
        else:
            factor = 1.1 if event.delta > 0 else 1 / 1.1

        next_scale = max(0.65, min(2.6, self.map_scale * factor))
        factor = next_scale / self.map_scale
        if abs(factor - 1.0) < 1e-6:
            return

        cursor_x = event.x
        cursor_y = event.y
        self.map_pan_x = cursor_x - factor * (cursor_x - self.map_pan_x)
        self.map_pan_y = cursor_y - factor * (cursor_y - self.map_pan_y)
        self.map_scale = next_scale
        self.render()

    def select_station_at_canvas_point(self, canvas_x: float, canvas_y: float) -> None:
        raw_x = (canvas_x - self.map_pan_x) / self.map_scale
        raw_y = (canvas_y - self.map_pan_y) / self.map_scale
        best_station = None
        best_distance = None
        for station in self.stations:
            x, y, _ = self.map_coords[station["id"]]
            distance = math.hypot(raw_x - x, raw_y - y)
            if best_distance is None or distance < best_distance:
                best_station = station["id"]
                best_distance = distance
        if best_station and best_distance is not None and best_distance <= 20:
            self.selected_station_id = best_station
            self.handle_station_click(best_station)
            self.render()

    def handle_station_click(self, station_id: str) -> None:
        preview = self.plan_cursor_preview()
        if preview["error"]:
            return
        pending_context = self.pending_departure_context(preview)
        if preview["current_state"]["kind"] == "NODE" and pending_context:
            valid_station_ids = {item["station_id"] for item in pending_context["destinations"]}
            if station_id in valid_station_ids:
                self.add_board_and_ride_steps(pending_context["train"]["train_number"], station_id)
                return
        if preview["current_state"]["kind"] == "TRAIN":
            if station_id == (preview["current_board_stop"] or {}).get("station_id"):
                return
            alight_stop = self.find_alight_stop(
                preview["current_train"],
                preview["current_board_stop"]["sequence"],
                station_id,
                None,
            )
            if alight_stop:
                self.add_ride_to_station_step(station_id)

    def preview_player(self, player_id: str, time_cap_minute: int | None = None) -> dict[str, Any]:
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
                    if time_cap_minute is not None and target > time_cap_minute:
                        current_minute = time_cap_minute
                        break
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
                    board_minute = stop_departure_minutes(board_stop)
                    if time_cap_minute is not None and board_minute > time_cap_minute:
                        current_minute = time_cap_minute
                        break
                    current_minute = board_minute
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
                    board_minute = stop_departure_minutes(board_stop)
                    if time_cap_minute is not None and board_minute > time_cap_minute:
                        current_minute = time_cap_minute
                        break
                    current_minute = board_minute
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
                    arrival_minute = stop_arrival_minutes(alight_stop)
                    if time_cap_minute is not None and arrival_minute > time_cap_minute:
                        current_minute = time_cap_minute
                        break
                    current_minute = arrival_minute
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

    def available_departures(self, preview: dict[str, Any]) -> list[dict[str, Any]]:
        if preview["error"] or preview["current_state"]["kind"] != "NODE":
            return []
        station_id = preview["current_state"]["station_id"]
        minute = preview["current_minute"]
        departures: list[dict[str, Any]] = []
        for train in self.train_data["train_instances"]:
            board_stop = self.find_boarding_stop(train, station_id, minute)
            if not board_stop:
                continue
            departures.append(
                {
                    "train_number": train["train_number"],
                    "departure_hhmm": minutes_to_hhmm(stop_departure_minutes(board_stop)),
                    "direction_label": train.get("direction_label", "unknown"),
                    "board_stop": board_stop,
                }
            )
        departures.sort(key=lambda item: (item["departure_hhmm"], item["train_number"]))
        return departures[:8]

    def available_destinations(self, preview: dict[str, Any]) -> list[dict[str, Any]]:
        if preview["error"] or preview["current_state"]["kind"] != "TRAIN":
            return []
        destinations: list[dict[str, Any]] = []
        for stop in self.future_train_stops(preview):
            destinations.append(
                {
                    "station_id": stop["station_id"],
                    "label": self.station_map[stop["station_id"]]["names"]["en"],
                    "arrival_hhmm": stop.get("arrival_hhmm") or stop.get("departure_hhmm"),
                    "sequence": stop["sequence"],
                }
            )
        return destinations

    def pending_departure_context(self, preview: dict[str, Any]) -> dict[str, Any] | None:
        train_number = self.pending_board_train_number()
        if not train_number or preview["error"] or preview["current_state"]["kind"] != "NODE":
            return None
        station_id = preview["current_state"]["station_id"]
        minute = preview["current_minute"]
        train = self.train_map.get(train_number)
        if not train:
            return None
        board_stop = self.find_boarding_stop(train, station_id, minute)
        if not board_stop:
            return None
        destinations = []
        for stop in train["stop_times"]:
            if stop["sequence"] <= board_stop["sequence"]:
                continue
            destinations.append(
                {
                    "station_id": stop["station_id"],
                    "label": self.station_map[stop["station_id"]]["names"]["en"],
                    "arrival_hhmm": stop.get("arrival_hhmm") or stop.get("departure_hhmm"),
                    "sequence": stop["sequence"],
                }
            )
            if stop["station_id"] == board_stop["station_id"]:
                break
        return {
            "train": train,
            "board_stop": board_stop,
            "destinations": destinations,
        }

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
        lines = []
        for stop in self.future_train_stops(preview):
            station = self.station_map[stop["station_id"]]["names"]["en"]
            hhmm = stop.get("arrival_hhmm") or stop.get("departure_hhmm")
            lines.append(f"{hhmm}  {station}")
        return lines

    def future_train_stops(self, preview: dict[str, Any]) -> list[dict[str, Any]]:
        train = preview["current_train"]
        board_stop = preview["current_board_stop"]
        if not train or not board_stop:
            return []

        boarded_station_id = board_stop["station_id"]
        future_stops: list[dict[str, Any]] = []
        for stop in train["stop_times"]:
            if stop["sequence"] <= board_stop["sequence"]:
                continue
            future_stops.append(stop)
            if stop["station_id"] == boarded_station_id:
                break
        return future_stops

    def format_state(self, preview: dict[str, Any]) -> str:
        state = preview["current_state"]
        if state["kind"] == "NODE":
            return self.station_map[state["station_id"]]["names"]["en"]
        anchor_station_id = preview.get("map_station_id")
        if anchor_station_id:
            return f"Train {state['train_number']} near {self.station_map[anchor_station_id]['names']['en']}"
        return f"Train {state['train_number']}"

    def render(self) -> None:
        visible_minute = self.visible_game_minute()
        runner_preview = self.preview_player("runner", visible_minute)
        hunter_preview = self.preview_player("hunter", visible_minute)
        replay_event = self.current_replay_event()
        replay_mode = replay_event is not None
        if replay_mode:
            runner_preview = self.replay_preview_from_state("runner", replay_event["state_after"]["runner"], replay_event)
            hunter_preview = self.replay_preview_from_state("hunter", replay_event["state_after"]["hunter"], replay_event)
        previews = {"runner": runner_preview, "hunter": hunter_preview}
        active_preview = previews[self.active_mode]
        passive_preview = previews["hunter" if self.active_mode == "runner" else "runner"]
        opponent_hidden = self.phase == "LIVE" and not replay_mode
        display_minute = replay_event["time_minute"] if replay_mode else visible_minute

        if self.phase == "PLANNING":
            self.clock_label.configure(bg="#b8441f", fg="white")
            self.clock_var.set(
                f"PLANNING\n{self.planning_seconds_remaining:02d}s left\n"
                f"Game starts {self.start_time}\n"
                "Both sides visible"
            )
        elif self.phase == "LIVE":
            self.clock_label.configure(bg="#163d2c", fg="white")
            self.clock_var.set(
                f"LIVE\n{minutes_to_hhmm(self.current_game_minute)}\n"
                "Opponent hidden\n"
                "Plan editable"
            )
        else:
            self.clock_label.configure(bg="#2a2f38", fg="white")
            self.clock_var.set(
                f"ENDED\n{minutes_to_hhmm(self.current_game_minute)}\n"
                "Match clock stopped\n"
                "Replay available"
            )

        self.hud_var.set(
            f"{self.active_mode.upper()} HUD\n\n"
            f"Phase: {self.phase}\n"
            f"Time: {minutes_to_hhmm(display_minute)}\n"
            f"Location: {self.format_state(active_preview)}\n"
            f"Mode: {self.players[self.active_mode]['input_mode']}\n"
            f"Resolved steps: {len(active_preview['resolved_steps'])}\n"
            f"Status: {('Replay focus: ' + replay_event['type']) if replay_mode else (active_preview['error'] or 'Ready')}"
        )
        self.test_var.set(
            "MATCH FLOW\n\n"
            f"Planning: 60 real seconds\n"
            f"Live clock: 1 game minute / sec\n"
            f"Runner start: {self.station_map[self.players['runner']['start_station_id']]['names']['en']}\n"
            f"Hunter start: {self.station_map[self.players['hunter']['start_station_id']]['names']['en']}\n"
            f"Visibility: {'Replay override: both visible' if replay_mode else ('Both visible' if self.phase == 'PLANNING' else 'Opponent hidden')}"
        )
        cursor_preview = self.plan_cursor_preview()
        pending_context = self.pending_departure_context(cursor_preview)
        upcoming = self.current_train_upcoming(active_preview)
        if pending_context:
            upcoming = [
                f"{pending_context['board_stop'].get('departure_hhmm') or pending_context['board_stop'].get('arrival_hhmm')}  BOARD {self.station_map[pending_context['board_stop']['station_id']]['names']['en']}",
                *[
                    f"{item['arrival_hhmm']}  {item['label']}"
                    for item in pending_context["destinations"][:12]
                ],
            ]
        self.train_var.set(
            "TRAIN OUTLOOK\n\n"
            + ("\n".join(upcoming) if upcoming else "Not currently on a train.")
        )
        self.quick_var.set(
            (
                f"ACTIVE SIDE: {self.active_mode.upper()}   |   CURRENT: {self.format_state(active_preview)}   |   OPPONENT: {self.format_state(passive_preview) if not opponent_hidden else 'Hidden'}\n"
                + (f"REPLAY FOCUS: {replay_event['time_hhmm']} {replay_event['type']}\n" if replay_mode else "")
                + f"ROUTE PREVIEW: {' -> '.join(self.station_map[s]['names']['en'] for s in self.planned_station_ids(active_preview)) or 'No route yet'}\n"
                + "MAP: drag to move, wheel to zoom, click a station; on-train clicks can directly set where to get off"
            )
        )
        active_steps = self.players[self.active_mode]["steps"]
        resolved_count = len(active_preview["resolved_steps"])
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
                marker = "DONE" if idx <= resolved_count else "NEXT"
                rendered_steps.append(f"{idx}. [{marker}] {desc}")
            plan_text = "\n".join(rendered_steps)
        else:
            plan_text = "No plan yet. This first local client is only a shell; editing tools come next."
        self.plan_var.set(plan_text)
        self.render_plan_board(cursor_preview, resolved_count)

        self.render_action_card(cursor_preview)
        self.root.after_idle(lambda: self.apply_right_pane_layout(bool(pending_context) or cursor_preview["current_state"]["kind"] == "TRAIN"))
        self.draw_map(runner_preview, hunter_preview, opponent_hidden)

    def render_selected_station_text(self, active_preview: dict[str, Any]) -> str:
        if not self.selected_station_id:
            return "SELECTED STATION\n\nNo station selected."

        station = self.station_map[self.selected_station_id]
        active_player = self.players[self.active_mode]
        upcoming = []
        if active_preview["current_state"]["kind"] == "NODE" and active_preview["current_state"]["station_id"] == self.selected_station_id:
            upcoming = self.available_options(active_preview)[:4]

        return (
            "SELECTED STATION\n\n"
            f"{station['names']['en']} / {station['names']['ja']}\n"
            f"ID: {station['id']}\n"
            f"Order: {station['order']}\n"
            f"Active side start: {active_player['start_station_id']}\n"
            + (
                f"Departures here:\n- " + "\n- ".join(upcoming)
                if upcoming
                else "Click this station to inspect it. If you are on a train and this stop is reachable, clicking it can add the ride step directly."
            )
        )

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

    def make_action_banner(self, parent: tk.Widget, title: str, subtitle: str, accent: str) -> tk.Frame:
        frame = tk.Frame(parent, bg=accent, padx=14, pady=12)
        title_label = tk.Label(frame, text=title, bg=accent, fg="white", font=self.fonts["action_title"], anchor="w", justify="left")
        title_label.pack(anchor="w")
        subtitle_label = tk.Label(
            frame,
            text=subtitle,
            bg=accent,
            fg="#fff7ef",
            font=self.fonts["body"],
            anchor="w",
            justify="left",
            wraplength=360,
        )
        subtitle_label.pack(anchor="w", pady=(6, 0))
        self.bind_right_panel_hover(frame)
        self.bind_right_panel_hover(title_label)
        self.bind_right_panel_hover(subtitle_label)
        return frame

    def add_train_choice_button(self, row: int, departure: dict[str, Any], selected: bool) -> int:
        accent = "#f5efe2" if not selected else "#173b2f"
        fg = INK if not selected else "white"
        meta_fg = MUTED if not selected else "#d7f2e6"
        wrapper = tk.Frame(self.action_card, bg=accent, highlightbackground=YAMANOTE_COLOR, highlightthickness=3 if selected else 1, padx=12, pady=10)
        wrapper.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        wrapper.columnconfigure(0, weight=1)
        top = tk.Label(
            wrapper,
            text=f"{departure['departure_hhmm']}   {departure['train_number']}",
            bg=accent,
            fg=fg,
            font=self.fonts["action_card"],
            anchor="w",
            justify="left",
        )
        top.grid(row=0, column=0, sticky="ew")
        route_preview = self.train_preview_text(departure["train_number"], departure["board_stop"])
        meta = tk.Label(
            wrapper,
            text=f"{departure['direction_label']}\n{route_preview}",
            bg=accent,
            fg=meta_fg,
            font=self.fonts["action_meta"],
            anchor="w",
            justify="left",
            wraplength=340,
        )
        meta.grid(row=1, column=0, sticky="ew", pady=(6, 8))
        button_text = "Selected" if selected else "Choose This Train"
        button = tk.Button(
            wrapper,
            text=button_text,
            command=lambda train_number=departure["train_number"]: self.set_pending_board_train(train_number),
            bg="#fffaf2" if not selected else "#f0c75e",
            fg=INK,
            activebackground="#f0c75e",
            relief="flat",
            padx=12,
            pady=6,
            font=self.fonts["body_bold"],
        )
        button.grid(row=2, column=0, sticky="ew")
        for widget in (wrapper, top, meta, button):
            self.bind_right_panel_hover(widget)
        return row + 1

    def train_preview_text(self, train_number: str, board_stop: dict[str, Any] | None) -> str:
        train = self.train_map.get(train_number)
        if not train or not board_stop:
            return "Route preview unavailable."
        labels = []
        for stop in train["stop_times"]:
            if stop["sequence"] <= board_stop["sequence"]:
                continue
            labels.append(self.station_map[stop["station_id"]]["names"]["en"])
            if len(labels) >= 6:
                break
        if not labels:
            return "No downstream stops."
        return " -> ".join(labels)

    def bind_horizontal_drag_scroll(self, canvas: tk.Canvas) -> None:
        canvas.bind("<ButtonPress-1>", lambda event, c=canvas: c.scan_mark(event.x, event.y), add="+")
        canvas.bind("<B1-Motion>", lambda event, c=canvas: c.scan_dragto(event.x, event.y, gain=1), add="+")
        self.bind_right_panel_hover(canvas)

    def render_destination_strip(self, row: int, destinations: list[dict[str, Any]], command_builder) -> int:
        instruction = tk.Label(
            self.action_card,
            text="Choose a destination below. Click `Ride Here` on the station you want.",
            bg=PANEL,
            fg=INK,
            font=self.fonts["body_bold"],
            anchor="w",
            justify="left",
            wraplength=360,
        )
        instruction.grid(row=row, column=0, sticky="ew", pady=(2, 6))
        self.bind_right_panel_hover(instruction)
        row += 1

        visible_list_label = tk.Label(
            self.action_card,
            text="Visible destination list",
            bg=PANEL,
            fg=INK,
            font=self.fonts["small_bold"],
            anchor="w",
            justify="left",
        )
        visible_list_label.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        self.bind_right_panel_hover(visible_list_label)
        row += 1

        visible_list = tk.Frame(self.action_card, bg=PANEL)
        visible_list.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        visible_list.columnconfigure(0, weight=1)
        self.bind_right_panel_hover(visible_list)

        for index, destination in enumerate(destinations, start=1):
            button = tk.Button(
                visible_list,
                text=f"{index}. {destination['arrival_hhmm']}  {destination['label']}  -  Ride Here",
                command=command_builder(destination["station_id"]),
                bg="#e8f2e0",
                fg=INK,
                activebackground="#cfe5c5",
                relief="flat",
                anchor="w",
                padx=12,
                pady=8,
                font=self.fonts["body"],
            )
            button.grid(row=index - 1, column=0, sticky="ew", pady=(0, 4))
            self.bind_right_panel_hover(button)
        row += 1

        hint = tk.Label(
            self.action_card,
            text="You can drag left/right here, or directly click the highlighted stations on the left map.",
            bg=PANEL,
            fg=MUTED,
            font=self.fonts["small"],
            anchor="w",
            justify="left",
        )
        hint.grid(row=row, column=0, sticky="ew", pady=(4, 6))
        self.bind_right_panel_hover(hint)
        row += 1

        strip_holder = tk.Frame(self.action_card, bg=PANEL)
        strip_holder.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        strip_holder.columnconfigure(0, weight=1)
        strip_canvas = tk.Canvas(strip_holder, bg=PANEL, highlightbackground=LINE, highlightthickness=1, height=156)
        strip_canvas.grid(row=0, column=0, sticky="ew")
        inner = tk.Frame(strip_canvas, bg=PANEL)
        window_id = strip_canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _event, c=strip_canvas: c.configure(scrollregion=c.bbox("all")))
        strip_canvas.bind("<Configure>", lambda event, c=strip_canvas, w=window_id: c.itemconfigure(w, height=event.height - 16))
        x_scrollbar = ttk.Scrollbar(strip_holder, orient="horizontal", command=strip_canvas.xview)
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        strip_canvas.configure(xscrollcommand=x_scrollbar.set)
        self.bind_horizontal_drag_scroll(strip_canvas)
        self.bind_right_panel_hover(x_scrollbar)

        for index, destination in enumerate(destinations):
            card = tk.Frame(inner, bg="#f4f0e6", highlightbackground=LINE, highlightthickness=1, padx=12, pady=10)
            card.grid(row=0, column=index, sticky="ns", padx=(0, 8))
            time_label = tk.Label(card, text=destination["arrival_hhmm"], bg="#f4f0e6", fg=INK, font=self.fonts["action_card"])
            time_label.pack(anchor="w")
            station_label = tk.Label(card, text=destination["label"], bg="#f4f0e6", fg=INK, font=self.fonts["body_bold"])
            station_label.pack(anchor="w", pady=(4, 2))
            action_button = tk.Button(
                card,
                text="Ride Here",
                command=command_builder(destination["station_id"]),
                bg="#dff0d6",
                fg=INK,
                activebackground="#bddfb0",
                relief="flat",
                padx=10,
                pady=6,
                font=self.fonts["body"],
            )
            action_button.pack(anchor="w", pady=(8, 0), fill="x")
            for widget in (card, time_label, station_label, action_button):
                self.bind_right_panel_hover(widget)
        return row + 1

    def render_action_card(self, preview: dict[str, Any]) -> None:
        signature = (
            self.active_mode,
            preview["current_state"].get("kind"),
            preview["current_state"].get("station_id"),
            preview["current_state"].get("train_number"),
            preview["current_minute"],
            self.pending_board_train_number(),
            self.selected_station_id,
            tuple(
                (
                    step.get("type"),
                    step.get("until_hhmm"),
                    step.get("train_number"),
                    step.get("station_id"),
                )
                for step in self.players[self.active_mode]["steps"]
            ),
            self.font_size_offset,
        )
        if signature == self.last_action_card_signature:
            return
        self.last_action_card_signature = signature
        for child in self.action_card.winfo_children():
            child.destroy()

        row = 0
        if self.selected_station_id:
            set_start_button = ttk.Button(self.action_card, text="Set Start To Selected Station", command=self.set_start_to_selected)
            set_start_button.grid(row=row, column=0, sticky="ew")
            self.bind_right_panel_hover(set_start_button)
            row += 1

        if preview["current_state"]["kind"] == "NODE":
            departures = self.available_departures(preview)
            station_name = self.station_map[preview["current_state"]["station_id"]]["names"]["en"]
            pending_context = self.pending_departure_context(preview)
            banner = self.make_action_banner(
                self.action_card,
                "STEP 1  Choose Your Train",
                f"You are at {station_name} at {preview['current_time']}. Pick a real departure first, then pick where to get off.",
                "#2d5d47",
            )
            banner.grid(row=row, column=0, sticky="ew", pady=(10, 10))
            row += 1
            if departures and not pending_context:
                row = self.add_section_header(row, "Upcoming Departures")
                for departure in departures:
                    row = self.add_train_choice_button(
                        row,
                        departure,
                        selected=(departure["train_number"] == self.pending_board_train_number()),
                    )
            if pending_context:
                selected_train = pending_context["train"]
                compact = tk.Frame(self.action_card, bg="#f5efe2", highlightbackground=YAMANOTE_COLOR, highlightthickness=2, padx=12, pady=10)
                compact.grid(row=row, column=0, sticky="ew", pady=(0, 8))
                compact.columnconfigure(0, weight=1)
                compact_title = tk.Label(
                    compact,
                    text=f"Selected train  {selected_train['train_number']}",
                    bg="#f5efe2",
                    fg=INK,
                    font=self.fonts["action_card"],
                    anchor="w",
                    justify="left",
                )
                compact_title.grid(row=0, column=0, sticky="ew")
                compact_meta = tk.Label(
                    compact,
                    text=f"{pending_context['board_stop'].get('departure_hhmm') or pending_context['board_stop'].get('arrival_hhmm')}  {selected_train.get('direction_label', 'unknown')}",
                    bg="#f5efe2",
                    fg=MUTED,
                    font=self.fonts["action_meta"],
                    anchor="w",
                    justify="left",
                )
                compact_meta.grid(row=1, column=0, sticky="ew", pady=(4, 8))
                change_button = tk.Button(
                    compact,
                    text="Choose Another Train",
                    command=self.choose_another_train,
                    bg="#fffaf2",
                    fg=INK,
                    activebackground="#f0c75e",
                    relief="flat",
                    padx=10,
                    pady=6,
                    font=self.fonts["body"],
                )
                change_button.grid(row=2, column=0, sticky="ew")
                for widget in (compact, compact_title, compact_meta, change_button):
                    self.bind_right_panel_hover(widget)
                selected_banner = self.make_action_banner(
                    self.action_card,
                    f"STEP 2  Ride {selected_train['train_number']} To",
                    f"{pending_context['board_stop'].get('departure_hhmm') or pending_context['board_stop'].get('arrival_hhmm')} departure · {selected_train.get('direction_label', 'unknown')}. Drag the route strip if the service is long.",
                    "#b8441f",
                )
                selected_banner.grid(row=row, column=0, sticky="ew", pady=(6, 10))
                row += 1
                row = self.render_destination_strip(
                    row,
                    pending_context["destinations"],
                    lambda station_id: (lambda station_id=station_id, train_number=selected_train["train_number"]: self.add_board_and_ride_steps(train_number, station_id)),
                )
            wait_label = f"Wait 5 minutes from {preview['current_time']}"
            wait_button = ttk.Button(self.action_card, text=wait_label, command=self.add_wait_step)
            wait_button.grid(row=row, column=0, sticky="ew", pady=(8, 0))
            self.bind_right_panel_hover(wait_button)
            row += 1

        if preview["current_state"]["kind"] == "TRAIN":
            train_number = preview["current_state"]["train_number"]
            banner = self.make_action_banner(
                self.action_card,
                f"Ride Train {train_number}",
                "Choose where to get off. The stop strip below can be dragged left and right if the route is long.",
                "#214f88",
            )
            banner.grid(row=row, column=0, sticky="ew", pady=(10, 10))
            row += 1
            destinations = self.available_destinations(preview)
            if destinations:
                row = self.render_destination_strip(
                    row,
                    destinations,
                    lambda station_id: (lambda station_id=station_id: self.add_ride_to_station_step(station_id)),
                )

        row = self.add_section_header(row, "Plan Controls")
        controls = tk.Frame(self.action_card, bg=PANEL)
        controls.grid(row=row, column=0, sticky="ew")
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        self.bind_right_panel_hover(controls)
        undo_button = ttk.Button(controls, text="Undo Step", command=self.undo_last_step)
        undo_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        clear_button = ttk.Button(controls, text="Clear Plan", command=self.clear_active_plan)
        clear_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.bind_right_panel_hover(undo_button)
        self.bind_right_panel_hover(clear_button)
        run_button = ttk.Button(self.action_card, text="Run Simulation", command=self.run_simulation)
        run_button.grid(row=row + 1, column=0, sticky="ew", pady=(8, 0))
        self.bind_right_panel_hover(run_button)

    def add_section_header(self, row: int, text: str) -> int:
        label = tk.Label(
            self.action_card,
            text=text,
            anchor="w",
            justify="left",
            bg=PANEL,
            fg=INK,
            font=self.fonts["small_bold"],
        )
        label.grid(row=row, column=0, sticky="ew", pady=(10, 6))
        self.bind_right_panel_hover(label)
        return row + 1

    def action_card_helper_text(self, preview: dict[str, Any]) -> str:
        if preview["error"]:
            return preview["error"]
        if preview["current_state"]["kind"] == "NODE":
            station_name = self.station_map[preview["current_state"]["station_id"]]["names"]["en"]
            return f"You are currently at {station_name}. Choose one of the upcoming departures below to board."
        train_number = preview["current_state"]["train_number"]
        return f"You are currently on train {train_number}. Choose a downstream station below, or click a reachable station on the map to get off there."

    def draw_map(self, runner_preview: dict[str, Any], hunter_preview: dict[str, Any], opponent_hidden: bool) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(46, 36, text="JR Yamanote Line", anchor="w", fill=INK, font=self.fonts["map_title"], tags=("board",))
        self.canvas.create_text(46, 64, text="Drag with left mouse button to move the map", anchor="w", fill=MUTED, font=self.fonts["map_subtitle"], tags=("board",))

        coords = [self.map_coords[station["id"]] for station in self.stations]
        loop_points = [value for coord in coords for value in coord[:2]]
        first = coords[0]
        loop_points.extend(first[:2])
        self.canvas.create_line(*loop_points, width=34, fill="#d9ebc6", smooth=True, tags=("board",))
        self.canvas.create_line(*loop_points, width=14, fill=YAMANOTE_COLOR, smooth=True, tags=("board",))

        self.draw_plan_trace(self.preview_player(self.active_mode), self.active_mode, faded=False)
        self.draw_plan_trace(self.preview_player("hunter" if self.active_mode == "runner" else "runner"), "hunter" if self.active_mode == "runner" else "runner", faded=True)
        self.draw_pending_train_route(self.plan_cursor_preview())

        replay_event = self.current_replay_event()
        if replay_event:
            self.canvas.create_text(
                46,
                92,
                text=f"Replay Focus: {replay_event['time_hhmm']}  {replay_event['type']}",
                anchor="w",
                fill=SELECTED,
                font=self.fonts["map_subtitle"],
                tags=("board",),
            )
        pending_context = self.pending_departure_context(self.plan_cursor_preview())
        if pending_context:
            self.canvas.create_text(
                46,
                92 if not replay_event else 118,
                text=f"STEP 2: Click a highlighted station for {pending_context['train']['train_number']}, or use Ride Here on the right",
                anchor="w",
                fill=SELECTED,
                font=self.fonts["map_subtitle"],
                tags=("board",),
            )

        runner_station = (
            runner_preview["current_state"].get("station_id")
            or runner_preview.get("map_station_id")
            or ((runner_preview.get("current_board_stop") or {}).get("station_id"))
        )
        hunter_station = (
            hunter_preview["current_state"].get("station_id")
            or hunter_preview.get("map_station_id")
            or ((hunter_preview.get("current_board_stop") or {}).get("station_id"))
        )

        for station in self.stations:
            station_id = station["id"]
            x, y, angle = self.map_coords[station_id]
            outline = SELECTED if station_id == self.selected_station_id else YAMANOTE_COLOR
            width = 5 if station_id == self.selected_station_id else 4
            self.canvas.create_oval(x - 12, y - 12, x + 12, y + 12, fill="white", outline=outline, width=width, tags=("board",))
            label_x = x + math.cos(angle) * 34
            label_y = y + math.sin(angle) * 34
            label_fill = SELECTED if station_id == self.selected_station_id else INK
            label_font = self.fonts["station_selected"] if station_id == self.selected_station_id else self.fonts["station"]
            self.canvas.create_text(label_x, label_y, text=station["names"]["en"], fill=label_fill, font=label_font, tags=("board",))

            if station_id == runner_station:
                self.canvas.create_oval(x + 8, y - 26, x + 26, y - 8, fill=RUNNER_COLOR, outline="white", width=3, tags=("board",))
            if station_id == hunter_station and (not opponent_hidden or self.active_mode == "hunter"):
                self.canvas.create_oval(x - 26, y - 26, x - 8, y - 8, fill=HUNTER_COLOR, outline="white", width=3, tags=("board",))

        self.canvas.create_text(812, 720, text="Runner", fill=INK, font=self.fonts["body_bold"], anchor="w", tags=("board",))
        self.canvas.create_oval(778, 710, 796, 728, fill=RUNNER_COLOR, outline="white", width=3, tags=("board",))
        if not opponent_hidden or self.active_mode == "hunter":
            self.canvas.create_text(812, 748, text="Hunter", fill=INK, font=self.fonts["body_bold"], anchor="w", tags=("board",))
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
            self.canvas.create_text(x, y + 1, text=str(index), fill="white", font=self.fonts["waypoint"], tags=("board",))

    def draw_pending_train_route(self, preview: dict[str, Any]) -> None:
        pending_context = self.pending_departure_context(preview)
        if not pending_context:
            return
        station_ids = [pending_context["board_stop"]["station_id"], *[item["station_id"] for item in pending_context["destinations"]]]
        line_points = []
        for station_id in station_ids:
            x, y, _ = self.map_coords[station_id]
            line_points.extend([x, y])
        if len(line_points) < 4:
            return
        self.canvas.create_line(*line_points, fill=SELECTED, width=10, dash=(14, 8), smooth=True, tags=("board",))
        for station_id in station_ids:
            x, y, _ = self.map_coords[station_id]
            self.canvas.create_oval(x - 8, y - 8, x + 8, y + 8, fill=SELECTED, outline="white", width=2, tags=("board",))
        for index, station_id in enumerate(station_ids[1:], start=1):
            x, y, _ = self.map_coords[station_id]
            self.canvas.create_oval(x - 18, y - 18, x + 18, y + 18, outline=SELECTED, width=3, dash=(4, 4), tags=("board",))
            self.canvas.create_text(x, y - 22, text=str(index), fill=SELECTED, font=self.fonts["small_bold"], tags=("board",))

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    OniChaseLocalClient().run()
