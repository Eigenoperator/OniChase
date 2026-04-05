#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


LEFT_MARGIN = 170
RIGHT_MARGIN = 60
TOP_MARGIN = 56
BOTTOM_MARGIN = 36
PANEL_HEADER = 30
PANEL_GAP = 34
HOUR_WIDTH = 120
STATION_GAP = 18

ROUTE_TITLES = {
    "TOHOKU": "Tohoku",
    "HOKKAIDO": "Hokkaido",
    "YAMAGATA": "Yamagata",
    "AKITA": "Akita",
    "JOETSU": "Joetsu",
    "GALA": "Joetsu Branch",
    "HOKURIKU": "Hokuriku",
    "TOKAIDO": "Tokaido",
    "SANYO": "Sanyo",
    "KYUSHU": "Kyushu",
    "NISHI_KYUSHU": "Nishi-Kyushu",
}

ROUTE_LINE_IDS = {
    "TOHOKU": {"SHINKANSEN_TOHOKU_HOKKAIDO"},
    "HOKKAIDO": {"SHINKANSEN_TOHOKU_HOKKAIDO"},
    "YAMAGATA": {"SHINKANSEN_TOHOKU_HOKKAIDO", "SHINKANSEN_YAMAGATA"},
    "AKITA": {"SHINKANSEN_TOHOKU_HOKKAIDO", "SHINKANSEN_AKITA"},
    "JOETSU": {"SHINKANSEN_JOETSU"},
    "GALA": {"SHINKANSEN_JOETSU"},
    "HOKURIKU": {"SHINKANSEN_HOKURIKU"},
    "TOKAIDO": {"SHINKANSEN_TOKAIDO_SANYO"},
    "SANYO": {"SHINKANSEN_TOKAIDO_SANYO"},
    "KYUSHU": {"SHINKANSEN_KYUSHU"},
    "NISHI_KYUSHU": {"SHINKANSEN_NISHI_KYUSHU"},
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def hhmm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def stop_time_minutes(stop_time: dict[str, Any]) -> int | None:
    value = stop_time.get("departure_hhmm") or stop_time.get("arrival_hhmm")
    if not value:
        return None
    return hhmm_to_minutes(value)


def build_station_lookup(stations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {station["id"]: station for station in stations}


def build_route_panels(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    panels: list[dict[str, Any]] = []
    for route in routes:
        panels.append(
            {
                "route_id": route["id"],
                "title": ROUTE_TITLES.get(route["id"], route["name"]),
                "color": route["color"],
                "station_ids": route["station_ids"],
                "line_ids": ROUTE_LINE_IDS.get(route["id"], set()),
            }
        )
    return panels


def relevant_stop_times(train: dict[str, Any], panel: dict[str, Any], station_ids: set[str]) -> list[dict[str, Any]]:
    line_ids = panel["line_ids"]
    matches = []
    for stop_time in train.get("stop_times", []):
        if stop_time.get("station_id") not in station_ids:
            continue
        if line_ids and stop_time.get("line_id") not in line_ids:
            continue
        if stop_time_minutes(stop_time) is None:
            continue
        matches.append(stop_time)
    return matches


def build_panel_points(
    stop_times: list[dict[str, Any]],
    station_index: dict[str, int],
    min_minutes: int,
    panel_top: float,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for stop_time in stop_times:
        station_id = stop_time["station_id"]
        if station_id not in station_index:
            continue
        minutes = stop_time_minutes(stop_time)
        if minutes is None:
            continue
        x = LEFT_MARGIN + (minutes - min_minutes) / 60 * HOUR_WIDTH
        y = panel_top + PANEL_HEADER + station_index[station_id] * STATION_GAP
        points.append((x, y))
    return points


def render_svg(dataset: dict[str, Any], stations: list[dict[str, Any]], routes: list[dict[str, Any]], title: str) -> str:
    trains = dataset["train_instances"]
    station_lookup = build_station_lookup(stations)
    panels = build_route_panels(routes)

    all_minutes = [
        minutes
        for train in trains
        for stop_time in train.get("stop_times", [])
        for minutes in [stop_time_minutes(stop_time)]
        if minutes is not None
    ]
    min_minutes = min(all_minutes)
    max_minutes = max(all_minutes)
    hour_ticks = list(range((min_minutes // 60) * 60, ((max_minutes + 59) // 60) * 60 + 1, 60))

    panel_layouts: list[dict[str, Any]] = []
    current_top = TOP_MARGIN
    for panel in panels:
        station_ids = panel["station_ids"]
        panel_height = PANEL_HEADER + (len(station_ids) - 1) * STATION_GAP + 10
        panel_layouts.append({**panel, "top": current_top, "height": panel_height})
        current_top += panel_height + PANEL_GAP

    width = LEFT_MARGIN + RIGHT_MARGIN + int((max_minutes - min_minutes) / 60 * HOUR_WIDTH) + 30
    height = int(current_top + BOTTOM_MARGIN)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: 'Helvetica Neue', Arial, sans-serif; fill: #17202a; }",
        ".title { font-size: 24px; font-weight: 700; }",
        ".subtitle { font-size: 12px; fill: #5f6c7b; }",
        ".panel-title { font-size: 16px; font-weight: 700; }",
        ".station-label { font-size: 10px; }",
        ".hour-label { font-size: 10px; fill: #5f6c7b; }",
        ".grid { stroke: #dde3ea; stroke-width: 1; }",
        ".panel-box { fill: #ffffff; stroke: #d5dde6; stroke-width: 1; rx: 16; ry: 16; }",
        "</style>",
        '<rect width="100%" height="100%" fill="#f8fafc" />',
        f'<text x="{LEFT_MARGIN}" y="28" class="title">{title}</text>',
        f'<text x="{LEFT_MARGIN}" y="46" class="subtitle">{dataset["id"]} • {len(trains)} real train instances • weekday</text>',
    ]

    for panel in panel_layouts:
        top = panel["top"]
        height_box = panel["height"]
        station_ids = panel["station_ids"]
        station_index = {station_id: idx for idx, station_id in enumerate(station_ids)}
        station_id_set = set(station_ids)
        panel_bottom = top + height_box

        parts.append(
            f'<rect x="18" y="{top - 12:.2f}" width="{width - 36}" height="{height_box + 18:.2f}" class="panel-box" />'
        )
        parts.append(f'<text x="{LEFT_MARGIN}" y="{top + 2:.2f}" class="panel-title" fill="{panel["color"]}">{panel["title"]}</text>')

        for hour in hour_ticks:
            x = LEFT_MARGIN + (hour - min_minutes) / 60 * HOUR_WIDTH
            parts.append(
                f'<line x1="{x:.2f}" y1="{top + 10:.2f}" x2="{x:.2f}" y2="{panel_bottom:.2f}" class="grid" />'
            )
            parts.append(
                f'<text x="{x - 14:.2f}" y="{top - 8:.2f}" class="hour-label">{hour // 60:02d}:00</text>'
            )

        for idx, station_id in enumerate(station_ids):
            station = station_lookup[station_id]
            y = top + PANEL_HEADER + idx * STATION_GAP
            parts.append(
                f'<line x1="{LEFT_MARGIN - 10}" y1="{y:.2f}" x2="{width - RIGHT_MARGIN}" y2="{y:.2f}" class="grid" />'
            )
            parts.append(
                f'<text x="22" y="{y + 3:.2f}" class="station-label">{station["names"]["en"]} / {station["names"]["ja"]}</text>'
            )

        train_count = 0
        for train in trains:
            stops = relevant_stop_times(train, panel, station_id_set)
            if len(stops) < 2:
                continue
            points = build_panel_points(stops, station_index, min_minutes, top)
            if len(points) < 2:
                continue
            train_count += 1
            point_string = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
            parts.append(
                f'<polyline points="{point_string}" fill="none" stroke="{panel["color"]}" stroke-width="1.5" stroke-opacity="0.42" stroke-linecap="round" stroke-linejoin="round" />'
            )

        parts.append(
            f'<text x="{width - RIGHT_MARGIN - 92}" y="{top + 2:.2f}" class="hour-label">{train_count} trains shown</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a multi-panel timetable SVG for the v2 Shinkansen dataset.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--stations", required=True)
    parser.add_argument("--routes", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()

    dataset = load_json(Path(args.dataset))
    stations = load_json(Path(args.stations))
    routes = load_json(Path(args.routes))
    svg = render_svg(dataset, stations, routes, args.title)
    Path(args.output).write_text(svg + "\n", encoding="utf-8")
    print(f"Wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
