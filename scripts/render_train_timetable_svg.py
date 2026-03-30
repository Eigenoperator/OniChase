#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


LEFT_MARGIN = 160
TOP_MARGIN = 70
RIGHT_MARGIN = 60
BOTTOM_MARGIN = 80
HOUR_WIDTH = 140
STATION_GAP = 28


def load_json(path: Path) -> dict[str, Any]:
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


def build_station_layout(stations_data: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    ordered_stations = sorted(stations_data["stations"], key=lambda station: station["order"])
    station_index = {station["id"]: idx for idx, station in enumerate(ordered_stations)}
    return ordered_stations, station_index


def infer_direction(train: dict[str, Any], station_index: dict[str, int], station_count: int) -> str:
    if train.get("direction_label") in {"clockwise", "counterclockwise"}:
        return train["direction_label"]

    stop_times = [stop for stop in train.get("stop_times", []) if stop.get("station_id") in station_index]
    for first, second in zip(stop_times, stop_times[1:]):
        first_idx = station_index[first["station_id"]]
        second_idx = station_index[second["station_id"]]
        if first_idx == second_idx:
            continue
        forward = (second_idx - first_idx) % station_count
        backward = (first_idx - second_idx) % station_count
        if forward == 1:
            return "counterclockwise"
        if backward == 1:
            return "clockwise"
        if forward < backward:
            return "counterclockwise"
        return "clockwise"
    return "unknown"


def build_polyline_points(
    train: dict[str, Any],
    station_index: dict[str, int],
    station_count: int,
    min_minutes: int,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    previous_index: int | None = None
    y_offset = 0.0

    for stop_time in train.get("stop_times", []):
        station_id = stop_time.get("station_id")
        if station_id not in station_index:
            continue
        minutes = stop_time_minutes(stop_time)
        if minutes is None:
            continue

        current_index = station_index[station_id]
        if previous_index is not None:
            if current_index == 0 and previous_index == station_count - 1:
                y_offset += station_count * STATION_GAP
            elif current_index == station_count - 1 and previous_index == 0:
                y_offset -= station_count * STATION_GAP

        x = LEFT_MARGIN + (minutes - min_minutes) / 60 * HOUR_WIDTH
        y = TOP_MARGIN + current_index * STATION_GAP + y_offset
        points.append((x, y))
        previous_index = current_index

    return points


def render_svg(dataset: dict[str, Any], stations_data: dict[str, Any], title: str) -> str:
    ordered_stations, station_index = build_station_layout(stations_data)
    station_count = len(ordered_stations)

    all_minutes = [
        minutes
        for train in dataset["train_instances"]
        for stop_time in train.get("stop_times", [])
        for minutes in [stop_time_minutes(stop_time)]
        if minutes is not None
    ]
    min_minutes = min(all_minutes)
    max_minutes = max(all_minutes)

    width = LEFT_MARGIN + RIGHT_MARGIN + int((max_minutes - min_minutes) / 60 * HOUR_WIDTH) + 20
    height = TOP_MARGIN + BOTTOM_MARGIN + STATION_GAP * (station_count - 1)

    hour_ticks = list(range((min_minutes // 60) * 60, ((max_minutes + 59) // 60) * 60 + 1, 60))

    colors = {
        "clockwise": "#1f5aa6",
        "counterclockwise": "#80c241",
        "unknown": "#999999",
    }

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: 'Helvetica Neue', Arial, sans-serif; fill: #1f2933; }",
        ".axis { stroke: #d0d7de; stroke-width: 1; }",
        ".station-label { font-size: 11px; }",
        ".hour-label { font-size: 11px; }",
        ".title { font-size: 20px; font-weight: 700; }",
        ".subtitle { font-size: 12px; fill: #52606d; }",
        ".legend { font-size: 12px; }",
        "</style>",
        '<rect width="100%" height="100%" fill="#fcfcf8" />',
        f'<text x="{LEFT_MARGIN}" y="30" class="title">{title}</text>',
        f'<text x="{LEFT_MARGIN}" y="48" class="subtitle">{dataset["id"]} • {len(dataset["train_instances"])} trains</text>',
    ]

    for hour in hour_ticks:
        x = LEFT_MARGIN + (hour - min_minutes) / 60 * HOUR_WIDTH
        parts.append(f'<line x1="{x:.2f}" y1="{TOP_MARGIN - 16}" x2="{x:.2f}" y2="{height - BOTTOM_MARGIN + 8}" class="axis" />')
        parts.append(f'<text x="{x - 14:.2f}" y="{TOP_MARGIN - 24}" class="hour-label">{hour // 60:02d}:00</text>')

    for idx, station in enumerate(ordered_stations):
        y = TOP_MARGIN + idx * STATION_GAP
        label = f'{station["names"]["en"]} / {station["names"]["ja"]}'
        parts.append(f'<line x1="{LEFT_MARGIN - 8}" y1="{y:.2f}" x2="{width - RIGHT_MARGIN}" y2="{y:.2f}" class="axis" />')
        parts.append(f'<text x="12" y="{y + 4:.2f}" class="station-label">{label}</text>')

    for train in dataset["train_instances"]:
        direction = infer_direction(train, station_index, station_count)
        color = colors[direction]
        points = build_polyline_points(train, station_index, station_count, min_minutes)
        if len(points) < 2:
            continue
        point_string = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        parts.append(
            f'<polyline points="{point_string}" fill="none" stroke="{color}" stroke-width="1.6" stroke-opacity="0.38" stroke-linecap="round" stroke-linejoin="round" />'
        )

    legend_y = height - 26
    parts.append(f'<line x1="{LEFT_MARGIN}" y1="{legend_y}" x2="{LEFT_MARGIN + 28}" y2="{legend_y}" stroke="{colors["counterclockwise"]}" stroke-width="3" />')
    parts.append(f'<text x="{LEFT_MARGIN + 36}" y="{legend_y + 4}" class="legend">Counterclockwise</text>')
    parts.append(f'<line x1="{LEFT_MARGIN + 170}" y1="{legend_y}" x2="{LEFT_MARGIN + 198}" y2="{legend_y}" stroke="{colors["clockwise"]}" stroke-width="3" />')
    parts.append(f'<text x="{LEFT_MARGIN + 206}" y="{legend_y + 4}" class="legend">Clockwise</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a time-space SVG diagram from a train-instance dataset.")
    parser.add_argument("--dataset", required=True, help="Path to the train-instance dataset JSON file.")
    parser.add_argument("--stations", required=True, help="Path to the canonical station dataset JSON file.")
    parser.add_argument("--output", required=True, help="Path to write the output SVG.")
    parser.add_argument("--title", required=True, help="Human-readable title for the SVG.")
    args = parser.parse_args()

    dataset = load_json(Path(args.dataset))
    stations_data = load_json(Path(args.stations))
    svg = render_svg(dataset, stations_data, args.title)
    output_path = Path(args.output)
    output_path.write_text(svg + "\n", encoding="utf-8")
    print(f"Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
