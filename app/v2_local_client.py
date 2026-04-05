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

BUNDLE_PATH = ROOT / "data" / "shinkansen_v2_bundle.json"
TRAINS_PATH = ROOT / "data" / "shinkansen_v2_weekday_train_instances_merged.json"

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


class OniChaseV2Client:
    def __init__(self) -> None:
        self.bundle = load_json(BUNDLE_PATH)
        self.train_dataset = load_json(TRAINS_PATH)
        self.stations = self.bundle["stations"]
        self.routes = self.bundle["routes"]
        self.station_map = {station["id"]: station for station in self.stations}
        self.train_map = {train["train_number"]: train for train in self.train_dataset["train_instances"]}
        self.station_route_map = {station["id"]: station.get("route_ids", []) for station in self.stations}

        self.current_station_id = "TOKYO"
        self.current_minute = hhmm_to_minutes("07:00")
        self.selected_station_id: str | None = self.current_station_id
        self.selected_train_number: str | None = None
        self.selected_destination_station_id: str | None = None
        self.plan_segments: list[dict[str, Any]] = []

        self.map_pan_x = 0.0
        self.map_pan_y = 0.0
        self.map_scale = 1.0
        self._drag_last: tuple[int, int] | None = None
        self._drag_start: tuple[int, int] | None = None
        self._drag_distance = 0.0

        self.root = tk.Tk()
        self.root.title("OniChase V2 Client")
        self.root.configure(bg=BG)
        self.root.geometry("1520x940")
        self.root.minsize(1280, 820)

        self.setup_fonts()
        self.setup_styles()

        self.title_var = tk.StringVar()
        self.station_var = tk.StringVar()
        self.plan_cursor_var = tk.StringVar()
        self.train_detail_var = tk.StringVar()

        self.project_map_coords()
        self.build_ui()
        self.render()

    def setup_fonts(self) -> None:
        family = "Helvetica"
        self.fonts = {
            "title": tkfont.Font(family=family, size=22, weight="bold"),
            "subtitle": tkfont.Font(family=family, size=11),
            "body": tkfont.Font(family=family, size=11),
            "body_bold": tkfont.Font(family=family, size=11, weight="bold"),
            "small": tkfont.Font(family=family, size=9),
            "small_bold": tkfont.Font(family=family, size=9, weight="bold"),
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
        width = 920
        height = 760
        pad_x = 90
        pad_y = 70
        self.map_coords: dict[str, tuple[float, float]] = {}
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
            text="Nationwide Shinkansen board shell. Click a station, browse real departures, and chain route legs from the live plan cursor.",
            bg=PANEL,
            fg=MUTED,
            font=self.fonts["subtitle"],
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        controls = tk.Frame(top, bg=PANEL)
        controls.grid(row=0, column=1, rowspan=2, sticky="e")

        tk.Label(controls, text="Cursor Time", bg=PANEL, fg=MUTED, font=self.fonts["small"]).grid(row=0, column=0, sticky="w")
        self.time_entry = tk.Entry(controls, width=6, font=self.fonts["body"])
        self.time_entry.insert(0, minutes_to_hhmm(self.current_minute))
        self.time_entry.grid(row=1, column=0, sticky="w", padx=(0, 8))
        ttk.Button(controls, text="Apply Time", command=self.apply_time_entry).grid(row=1, column=1, padx=(0, 8))
        ttk.Button(controls, text="Reset Plan", command=self.reset_plan).grid(row=1, column=2)

        body = ttk.PanedWindow(self.root, orient="horizontal")
        body.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        left = tk.Frame(body, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        right = tk.Frame(body, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        body.add(left, weight=4)
        body.add(right, weight=2)

        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        tk.Label(left, text="V2 BOARD", bg=PANEL, fg=INK, font=self.fonts["map_title"]).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        tk.Label(left, textvariable=self.title_var, bg=PANEL, fg=MUTED, font=self.fonts["subtitle"]).grid(row=0, column=0, sticky="e", padx=16, pady=(16, 4))

        self.canvas = tk.Canvas(left, bg="#f7f2e9", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.canvas.bind("<ButtonPress-1>", self.on_map_press)
        self.canvas.bind("<B1-Motion>", self.on_map_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_map_release)
        self.canvas.bind("<MouseWheel>", self.on_map_wheel)
        self.canvas.bind("<Button-4>", lambda event: self.on_map_wheel_linux(event, 1))
        self.canvas.bind("<Button-5>", lambda event: self.on_map_wheel_linux(event, -1))

        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)
        tk.Label(right, text="PLAN CURSOR", bg=PANEL, fg=INK, font=self.fonts["body_bold"]).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        tk.Label(right, textvariable=self.plan_cursor_var, bg=PANEL, fg=MUTED, justify="left", anchor="w", font=self.fonts["body"]).grid(row=1, column=0, sticky="ew", padx=16)
        tk.Label(right, text="SELECTED STATION", bg=PANEL, fg=INK, font=self.fonts["body_bold"]).grid(row=2, column=0, sticky="w", padx=16, pady=(16, 4))
        tk.Label(right, textvariable=self.station_var, bg=PANEL, fg=MUTED, justify="left", anchor="w", font=self.fonts["body"]).grid(row=3, column=0, sticky="new", padx=16)

        lists = ttk.PanedWindow(right, orient="vertical")
        lists.grid(row=4, column=0, sticky="nsew", padx=12, pady=(8, 12))

        departures_frame = tk.Frame(lists, bg=PANEL)
        plan_frame = tk.Frame(lists, bg=PANEL)
        lists.add(departures_frame, weight=3)
        lists.add(plan_frame, weight=2)

        departures_frame.columnconfigure(0, weight=1)
        departures_frame.rowconfigure(1, weight=2)
        departures_frame.rowconfigure(4, weight=2)
        tk.Label(departures_frame, text="UPCOMING DEPARTURES", bg=PANEL, fg=INK, font=self.fonts["body_bold"]).grid(row=0, column=0, sticky="w")
        self.departures_list = tk.Listbox(departures_frame, font=self.fonts["small"], activestyle="none")
        self.departures_list.grid(row=1, column=0, sticky="nsew", pady=(6, 8))
        self.departures_list.bind("<<ListboxSelect>>", self.on_departure_select)
        dep_scroll = tk.Scrollbar(departures_frame, orient="vertical", command=self.departures_list.yview)
        dep_scroll.grid(row=1, column=1, sticky="ns", pady=(6, 8))
        self.departures_list.configure(yscrollcommand=dep_scroll.set)

        tk.Label(departures_frame, textvariable=self.train_detail_var, bg=PANEL, fg=MUTED, justify="left", anchor="w", font=self.fonts["small"]).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        tk.Label(departures_frame, text="DESTINATION OPTIONS", bg=PANEL, fg=INK, font=self.fonts["body_bold"]).grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.destinations_list = tk.Listbox(departures_frame, font=self.fonts["small"], activestyle="none")
        self.destinations_list.grid(row=4, column=0, sticky="nsew", pady=(6, 8))
        self.destinations_list.bind("<<ListboxSelect>>", self.on_destination_select)
        dest_scroll = tk.Scrollbar(departures_frame, orient="vertical", command=self.destinations_list.yview)
        dest_scroll.grid(row=4, column=1, sticky="ns", pady=(6, 8))
        self.destinations_list.configure(yscrollcommand=dest_scroll.set)
        ttk.Button(departures_frame, text="Add Selected Leg To Plan", command=self.add_selected_train_to_plan).grid(row=5, column=0, sticky="w")

        plan_frame.columnconfigure(0, weight=1)
        plan_frame.rowconfigure(1, weight=1)
        tk.Label(plan_frame, text="PLAN BOARD", bg=PANEL, fg=INK, font=self.fonts["body_bold"]).grid(row=0, column=0, sticky="w")
        self.plan_list = tk.Listbox(plan_frame, font=self.fonts["small"], activestyle="none")
        self.plan_list.grid(row=1, column=0, sticky="nsew", pady=(6, 8))
        plan_scroll = tk.Scrollbar(plan_frame, orient="vertical", command=self.plan_list.yview)
        plan_scroll.grid(row=1, column=1, sticky="ns", pady=(6, 8))
        self.plan_list.configure(yscrollcommand=plan_scroll.set)

    def apply_time_entry(self) -> None:
        value = self.time_entry.get().strip()
        try:
            self.current_minute = hhmm_to_minutes(value)
        except Exception:
            return
        self.selected_train_number = None
        self.render()

    def reset_plan(self) -> None:
        self.plan_segments.clear()
        self.current_station_id = "TOKYO"
        self.current_minute = hhmm_to_minutes("07:00")
        self.selected_station_id = self.current_station_id
        self.selected_train_number = None
        self.time_entry.delete(0, tk.END)
        self.time_entry.insert(0, "07:00")
        self.render()

    def on_map_press(self, event: tk.Event[tk.Misc]) -> None:
        self._drag_last = (event.x, event.y)
        self._drag_start = (event.x, event.y)
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
                self.selected_train_number = None
                self.render()
        self._drag_last = None
        self._drag_start = None
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

    def transform(self, station_id: str) -> tuple[float, float]:
        x, y = self.map_coords[station_id]
        return (x * self.map_scale + self.map_pan_x, y * self.map_scale + self.map_pan_y)

    def find_station_at(self, x: float, y: float) -> str | None:
        best: tuple[float, str] | None = None
        for station in self.stations:
            sx, sy = self.transform(station["id"])
            distance = math.dist((x, y), (sx, sy))
            if distance <= 18:
                if best is None or distance < best[0]:
                    best = (distance, station["id"])
        return best[1] if best else None

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
        departures.sort(key=lambda item: (item[0], item[1].get("display_name", ""), item[1]["train_number"]))
        return departures[:80]

    def on_departure_select(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        selection = self.departures_list.curselection()
        if not selection:
            self.selected_train_number = None
            self.selected_destination_station_id = None
            self.render()
            return
        label = self.departures_list.get(selection[0])
        train_number = label.split(" | ")[-1]
        self.selected_train_number = train_number
        self.selected_destination_station_id = None
        self.render()

    def on_destination_select(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        selection = self.destinations_list.curselection()
        if not selection:
            self.selected_destination_station_id = None
            return
        label = self.destinations_list.get(selection[0])
        self.selected_destination_station_id = label.split(" | ")[-1]
        self.render()

    def downstream_destinations(self, station_id: str, current_minute: int, train_number: str | None) -> list[dict[str, Any]]:
        if not train_number:
            return []
        departures = self.departures_for_station(station_id, current_minute)
        match = None
        for departure_minute, train, stop in departures:
            if train["train_number"] == train_number:
                match = (departure_minute, train, stop)
                break
        if not match:
            return []
        _departure_minute, train, stop = match
        return [candidate for candidate in train["stop_times"] if candidate["sequence"] > stop["sequence"]]

    def add_selected_train_to_plan(self) -> None:
        if not self.selected_train_number or not self.selected_destination_station_id:
            return
        station_id = self.selected_station_id or self.current_station_id
        departures = self.departures_for_station(station_id, self.current_minute)
        match = None
        for departure_minute, train, stop in departures:
            if train["train_number"] == self.selected_train_number:
                match = (departure_minute, train, stop)
                break
        if not match:
            return
        departure_minute, train, stop = match
        downstream = []
        for candidate in train["stop_times"]:
            if candidate["sequence"] <= stop["sequence"]:
                continue
            downstream.append(candidate)
        if not downstream:
            return
        destination = next((candidate for candidate in downstream if candidate["station_id"] == self.selected_destination_station_id), None)
        if not destination:
            return
        self.plan_segments.append(
            {
                "from_station_id": station_id,
                "departure_hhmm": minutes_to_hhmm(departure_minute),
                "train_number": train["train_number"],
                "display_name": train.get("display_name", train["train_number"]),
                "to_station_id": destination["station_id"],
                "arrival_hhmm": destination.get("arrival_hhmm") or destination.get("departure_hhmm"),
            }
        )
        self.current_station_id = destination["station_id"]
        self.current_minute = hhmm_to_minutes(destination.get("arrival_hhmm") or destination.get("departure_hhmm"))
        self.selected_station_id = self.current_station_id
        self.selected_train_number = None
        self.selected_destination_station_id = None
        self.time_entry.delete(0, tk.END)
        self.time_entry.insert(0, minutes_to_hhmm(self.current_minute))
        self.render()

    def render(self) -> None:
        current_station = self.station_map[self.current_station_id]
        selected_station = self.station_map[self.selected_station_id] if self.selected_station_id else current_station
        self.title_var.set(f"{len(self.routes)} routes  |  {self.bundle['train_count']} real weekday trains")
        self.station_var.set(
            "\n".join(
                [
                    f"{selected_station['name']}  [{selected_station['id']}]",
                    f"Routes: {', '.join(selected_station.get('route_ids', [])) or '-'}",
                    f"Category: {selected_station.get('category', 'station')}",
                ]
            )
        )
        self.plan_cursor_var.set(
            "\n".join(
                [
                    f"Current station: {current_station['name']} [{self.current_station_id}]",
                    f"Current time: {minutes_to_hhmm(self.current_minute)}",
                    f"Planned legs: {len(self.plan_segments)}",
                ]
            )
        )

        self.render_departures()
        self.render_plan_board()
        self.render_map()

    def render_departures(self) -> None:
        station_id = self.selected_station_id or self.current_station_id
        departures = self.departures_for_station(station_id, self.current_minute)
        self.departures_list.delete(0, tk.END)
        self.destinations_list.delete(0, tk.END)
        selected_train = self.train_map.get(self.selected_train_number) if self.selected_train_number else None
        detail_lines = ["Select a departure to preview its full remaining stop list."]
        for departure_minute, train, stop in departures:
            label = f"{minutes_to_hhmm(departure_minute)}  {train.get('display_name', train['train_number'])}  |  {train['train_number']}"
            self.departures_list.insert(tk.END, label)
        if selected_train:
            detail_lines = [f"{selected_train.get('display_name', selected_train['train_number'])}"]
            boarding_stop = None
            for stop in selected_train["stop_times"]:
                if stop.get("station_id") == station_id and stop_departure_minutes(stop) >= self.current_minute:
                    boarding_stop = stop
                    break
            if boarding_stop:
                detail_lines.append(f"Board at {station_id} {minutes_to_hhmm(stop_departure_minutes(boarding_stop))}")
                detail_lines.append("Remaining stops:")
                for stop in selected_train["stop_times"]:
                    if stop["sequence"] <= boarding_stop["sequence"]:
                        continue
                    detail_lines.append(
                        f"- {stop['station_id']}  {stop.get('arrival_hhmm') or stop.get('departure_hhmm')}"
                    )
        self.train_detail_var.set("\n".join(detail_lines[:18]))
        destinations = self.downstream_destinations(station_id, self.current_minute, self.selected_train_number)
        for stop in destinations:
            label = f"{stop.get('arrival_hhmm') or stop.get('departure_hhmm')}  {stop['station_id']}  |  {stop['station_id']}"
            self.destinations_list.insert(tk.END, label)
        if self.selected_destination_station_id:
            for index, stop in enumerate(destinations):
                if stop["station_id"] == self.selected_destination_station_id:
                    self.destinations_list.selection_clear(0, tk.END)
                    self.destinations_list.selection_set(index)
                    self.destinations_list.activate(index)
                    break

    def render_plan_board(self) -> None:
        self.plan_list.delete(0, tk.END)
        if not self.plan_segments:
            self.plan_list.insert(tk.END, "No legs yet. Select a station, then pick a departure.")
            return
        for index, segment in enumerate(self.plan_segments, start=1):
            self.plan_list.insert(
                tk.END,
                f"{index}. {segment['from_station_id']} {segment['departure_hhmm']}  ->  {segment['display_name']}  ->  {segment['to_station_id']} {segment['arrival_hhmm']}",
            )

    def render_map(self) -> None:
        self.canvas.delete("all")
        for route in self.routes:
            points = []
            for station_id in route["station_ids"]:
                x, y = self.transform(station_id)
                points.extend([x, y])
            if len(points) >= 4:
                self.canvas.create_line(
                    *points,
                    fill=route["color"],
                    width=4,
                    capstyle=tk.ROUND,
                    joinstyle=tk.ROUND,
                )

        for station in self.stations:
            station_id = station["id"]
            x, y = self.transform(station_id)
            is_selected = station_id == self.selected_station_id
            is_cursor = station_id == self.current_station_id
            radius = 6 if station.get("is_interchange") else 4
            outline = ACCENT if is_selected else "#ffffff"
            fill = PLAN_COLOR if is_cursor else "#ffffff"
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline=outline, width=2)
            self.canvas.create_text(
                x + 7,
                y - 10,
                text=station["name"],
                anchor="w",
                fill=INK if is_selected else MUTED,
                font=self.fonts["station_selected"] if is_selected else self.fonts["station"],
            )

        for segment in self.plan_segments:
            from_x, from_y = self.transform(segment["from_station_id"])
            to_x, to_y = self.transform(segment["to_station_id"])
            self.canvas.create_line(
                from_x,
                from_y,
                to_x,
                to_y,
                fill=PLAN_COLOR,
                width=3,
                dash=(8, 6),
            )

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    client = OniChaseV2Client()
    client.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
