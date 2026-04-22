#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import html
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_RECORDS = Path("reports/v3_public_battle_records_20260422_143910.json")
DEFAULT_BUNDLE = Path("docs/data/v3_tokyo_map_bundle.json.gz")
DEFAULT_OUTPUT_DIR = Path("reports/v3_battle_timelines_20260422_143910")

SVG_WIDTH = 1280
TOP_MARGIN = 156
BOTTOM_MARGIN = 88
LEFT_CARD_X = 92
LEFT_CARD_WIDTH = 354
LEFT_MARKER_X = 462
LEFT_MARKER_WIDTH = 132
RUNNER_TRACK_X = 604
TIME_AXIS_X = 640
HUNTER_TRACK_X = 676
RIGHT_MARKER_X = 694
RIGHT_MARKER_WIDTH = 132
RIGHT_CARD_X = 844
RIGHT_CARD_WIDTH = 354
CARD_RADIUS = 8


@dataclass(frozen=True)
class RouteStyle:
    color: str
    text_color: str
    title: str


@dataclass(frozen=True)
class Ride:
    index: int
    route_id: str
    route_title: str
    trip_label: str
    from_station: str
    to_station: str
    board_minute: int
    alight_minute: int


@dataclass(frozen=True)
class Moment:
    minute: int
    title: str
    subtitle: str
    kind: str


def load_json_maybe_gz(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as file:
            return json.load(file)
    return json.loads(path.read_text(encoding="utf-8"))


def hhmm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def minutes_to_hhmm(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-").lower()
    return cleaned or "timeline"


def route_styles(bundle: dict[str, Any]) -> dict[str, RouteStyle]:
    styles: dict[str, RouteStyle] = {}
    for route in bundle.get("serviceRoutes", []):
        route_id = route.get("id")
        if not route_id:
            continue
        title = route.get("shortName") or route.get("longName") or route_id
        styles[route_id] = RouteStyle(
            color=route.get("color") or "#667487",
            text_color=route.get("textColor") or "#ffffff",
            title=title,
        )
    return styles


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    if len(value) != 6:
        return (102, 116, 135)
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def mix(color: str, other: str, amount: float) -> str:
    left = hex_to_rgb(color)
    right = hex_to_rgb(other)
    ratio = max(0.0, min(1.0, amount))
    return rgb_to_hex(tuple(round(left[index] * (1 - ratio) + right[index] * ratio) for index in range(3)))


def luminance(color: str) -> float:
    rgb = [channel / 255 for channel in hex_to_rgb(color)]
    linear = [value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4 for value in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def readable_text_color(background: str) -> str:
    return "#102033" if luminance(background) > 0.54 else "#ffffff"


def player_rides(plan: dict[str, Any]) -> list[Ride]:
    rides: list[Ride] = []
    for index, leg in enumerate(plan.get("legs", []), start=1):
        rides.append(
            Ride(
                index=index,
                route_id=leg.get("routeId") or "",
                route_title=leg.get("routeTitle") or leg.get("requestedRoute") or "路線",
                trip_label=leg.get("tripLabel") or leg.get("tripId") or "列車",
                from_station=leg.get("fromStation") or "",
                to_station=leg.get("toStation") or "",
                board_minute=hhmm_to_minutes(leg["boardHhmm"]),
                alight_minute=hhmm_to_minutes(leg["alightHhmm"]),
            )
        )
    return rides


def player_moments(plan: dict[str, Any]) -> list[Moment]:
    rides = player_rides(plan)
    start_minute = 360
    moments = [
        Moment(
            minute=start_minute,
            title=f"起点 {plan.get('startStation') or plan.get('start') or ''}",
            subtitle="准备阶段",
            kind="start",
        )
    ]
    by_minute: dict[int, list[tuple[str, Ride]]] = {}
    for ride in rides:
        by_minute.setdefault(ride.board_minute, []).append(("board", ride))
        by_minute.setdefault(ride.alight_minute, []).append(("alight", ride))

    for minute in sorted(by_minute):
        events = by_minute[minute]
        boards = [ride for action, ride in events if action == "board"]
        alights = [ride for action, ride in events if action == "alight"]
        if boards and alights:
            station = boards[0].from_station or alights[0].to_station
            subtitle = " / ".join(
                [f"下 {ride.trip_label}" for ride in alights] + [f"上 {ride.trip_label}" for ride in boards]
            )
            moments.append(Moment(minute=minute, title=f"换乘 {station}", subtitle=subtitle, kind="transfer"))
        elif boards:
            ride = boards[0]
            moments.append(Moment(minute=minute, title=f"上车 {ride.from_station}", subtitle=ride.trip_label, kind="board"))
        elif alights:
            ride = alights[0]
            moments.append(Moment(minute=minute, title=f"到达 {ride.to_station}", subtitle=f"下 {ride.trip_label}", kind="alight"))
    return moments


def time_bounds(game: dict[str, Any], padding_minutes: int = 8) -> tuple[int, int]:
    minutes = [360]
    for plan_key in ("runner_plan", "hunter_plan"):
        for ride in player_rides(game[plan_key]):
            minutes.extend([ride.board_minute, ride.alight_minute])
    capture = game.get("result", {}).get("capture")
    if capture and capture.get("time_hhmm"):
        minutes.append(hhmm_to_minutes(capture["time_hhmm"]))
    start = math.floor((min(minutes) - 3) / 5) * 5
    end = math.ceil((max(minutes) + padding_minutes) / 5) * 5
    return start, max(end, start + 45)


def y_for_minute(minute: int, start_minute: int, px_per_minute: float) -> float:
    return TOP_MARGIN + (minute - start_minute) * px_per_minute


def svg_text(
    x: float,
    y: float,
    text: str,
    *,
    size: int = 16,
    weight: int = 600,
    fill: str = "#162235",
    anchor: str = "start",
    extra: str = "",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}" {extra}>{esc(text)}</text>'
    )


def wrap_label(value: str, max_chars: int) -> list[str]:
    text = str(value)
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current = ""
    for char in text:
        if len(current) >= max_chars:
            chunks.append(current)
            current = char
        else:
            current += char
    if current:
        chunks.append(current)
    return chunks[:3]


def render_card_text(x: float, y: float, width: float, title: str, lines: list[str], align: str = "left") -> list[str]:
    anchor = "end" if align == "right" else "start"
    text_x = x + width - 18 if align == "right" else x + 18
    elements = [svg_text(text_x, y + 25, title, size=18, weight=800, anchor=anchor)]
    cursor = y + 49
    for line in lines:
        for wrapped in wrap_label(line, 28 if width > 180 else 13):
            elements.append(svg_text(text_x, cursor, wrapped, size=13, weight=650, fill="#657386", anchor=anchor))
            cursor += 17
    return elements


def render_ride(
    ride: Ride,
    side: str,
    start_minute: int,
    px_per_minute: float,
    styles: dict[str, RouteStyle],
) -> list[str]:
    y1 = y_for_minute(ride.board_minute, start_minute, px_per_minute)
    y2 = y_for_minute(ride.alight_minute, start_minute, px_per_minute)
    if y2 < y1:
        y1, y2 = y2, y1
    style = styles.get(ride.route_id, RouteStyle("#667487", "#ffffff", ride.route_title))
    color = style.color
    pale = mix(color, "#ffffff", 0.86)
    track_x = RUNNER_TRACK_X if side == "runner" else HUNTER_TRACK_X
    card_x = LEFT_CARD_X if side == "runner" else RIGHT_CARD_X
    card_width = LEFT_CARD_WIDTH if side == "runner" else RIGHT_CARD_WIDTH
    card_h = 86
    mid = (y1 + y2) / 2
    card_y = max(TOP_MARGIN + 8, mid - card_h / 2)
    stripe_x = card_x + card_width - 9 if side == "runner" else card_x
    align = "right" if side == "runner" else "left"
    connector_start = card_x + card_width if side == "runner" else card_x

    elements = [
        f'<line x1="{track_x}" y1="{y1:.1f}" x2="{track_x}" y2="{y2:.1f}" stroke="{color}" stroke-width="10" stroke-linecap="round" />',
        f'<line x1="{track_x}" y1="{y1:.1f}" x2="{track_x}" y2="{y2:.1f}" stroke="#ffffff" stroke-opacity="0.62" stroke-width="3" stroke-linecap="round" />',
        f'<circle cx="{track_x}" cy="{y1:.1f}" r="7" fill="{color}" stroke="#ffffff" stroke-width="3" />',
        f'<circle cx="{track_x}" cy="{y2:.1f}" r="7" fill="{color}" stroke="#ffffff" stroke-width="3" />',
        f'<line x1="{connector_start}" y1="{mid:.1f}" x2="{track_x}" y2="{mid:.1f}" stroke="{mix(color, "#ffffff", 0.42)}" stroke-width="2" stroke-dasharray="4 5" />',
        f'<rect x="{card_x}" y="{card_y:.1f}" width="{card_width}" height="{card_h}" rx="{CARD_RADIUS}" fill="{pale}" stroke="{mix(color, "#1f2937", 0.18)}" stroke-width="1.2" />',
        f'<rect x="{stripe_x}" y="{card_y:.1f}" width="9" height="{card_h}" rx="4.5" fill="{color}" />',
    ]
    title = f"{ride.route_title}"
    if ride.trip_label and ride.trip_label != ride.route_title:
        title = f"{ride.route_title} · {ride.trip_label}"
    lines = [
        f"{ride.from_station} -> {ride.to_station}",
        f"{minutes_to_hhmm(ride.board_minute)} - {minutes_to_hhmm(ride.alight_minute)}",
    ]
    elements.extend(render_card_text(card_x, card_y, card_width, title, lines, align=align))
    return elements


def layout_moments(moments: list[Moment], start_minute: int, px_per_minute: float, min_gap: float = 54) -> list[tuple[Moment, float]]:
    laid_out: list[tuple[Moment, float]] = []
    previous_y = -1_000_000.0
    for moment in sorted(moments, key=lambda item: (item.minute, item.kind)):
        event_y = y_for_minute(moment.minute, start_minute, px_per_minute)
        label_y = max(event_y, previous_y + min_gap)
        laid_out.append((moment, label_y))
        previous_y = label_y
    return laid_out


def render_moment(moment: Moment, label_y: float, side: str, start_minute: int, px_per_minute: float) -> list[str]:
    event_y = y_for_minute(moment.minute, start_minute, px_per_minute)
    track_x = RUNNER_TRACK_X if side == "runner" else HUNTER_TRACK_X
    marker_x = LEFT_MARKER_X if side == "runner" else RIGHT_MARKER_X
    marker_width = LEFT_MARKER_WIDTH if side == "runner" else RIGHT_MARKER_WIDTH
    align = "right" if side == "runner" else "left"
    marker_color = {
        "start": "#0f766e",
        "board": "#2563eb",
        "alight": "#7c3aed",
        "transfer": "#db2777",
    }.get(moment.kind, "#475569")
    fill = mix(marker_color, "#ffffff", 0.9)
    text_x = marker_x + marker_width - 12 if align == "right" else marker_x + 12
    connector_end = marker_x + marker_width if side == "runner" else marker_x
    return [
        f'<line x1="{connector_end}" y1="{label_y:.1f}" x2="{track_x}" y2="{event_y:.1f}" stroke="{mix(marker_color, "#ffffff", 0.35)}" stroke-width="1.6" />',
        f'<circle cx="{track_x}" cy="{event_y:.1f}" r="4.8" fill="{marker_color}" stroke="#ffffff" stroke-width="2" />',
        f'<rect x="{marker_x}" y="{label_y - 23:.1f}" width="{marker_width}" height="46" rx="{CARD_RADIUS}" fill="{fill}" stroke="{mix(marker_color, "#0f172a", 0.18)}" />',
        svg_text(text_x, label_y - 4, minutes_to_hhmm(moment.minute), size=11, weight=900, fill=marker_color, anchor=align),
        svg_text(text_x, label_y + 12, moment.title, size=12, weight=800, fill="#182335", anchor=align),
    ]


def render_axis(start_minute: int, end_minute: int, px_per_minute: float, event_minutes: list[int]) -> list[str]:
    y_start = y_for_minute(start_minute, start_minute, px_per_minute)
    y_end = y_for_minute(end_minute, start_minute, px_per_minute)
    elements = [
        f'<line x1="{TIME_AXIS_X}" y1="{y_start:.1f}" x2="{TIME_AXIS_X}" y2="{y_end:.1f}" stroke="#b9c5d5" stroke-width="3" stroke-linecap="round" />'
    ]
    tick = math.ceil(start_minute / 10) * 10
    while tick <= end_minute:
        y = y_for_minute(tick, start_minute, px_per_minute)
        is_hour = tick % 60 == 0
        tick_len = 24 if is_hour else 14
        elements.extend(
            [
                f'<line x1="{TIME_AXIS_X - tick_len}" y1="{y:.1f}" x2="{TIME_AXIS_X + tick_len}" y2="{y:.1f}" stroke="#d4dce8" stroke-width="1.2" />',
                svg_text(TIME_AXIS_X, y + 4, minutes_to_hhmm(tick), size=12 if is_hour else 10, weight=800 if is_hour else 650, fill="#667487", anchor="middle"),
            ]
        )
        tick += 10
    for minute in sorted(set(event_minutes)):
        if minute < start_minute or minute > end_minute:
            continue
        y = y_for_minute(minute, start_minute, px_per_minute)
        elements.extend(
            [
                f'<line x1="72" y1="{y:.1f}" x2="1208" y2="{y:.1f}" stroke="#e7edf5" stroke-width="1" />',
                f'<rect x="{TIME_AXIS_X - 31}" y="{y - 13:.1f}" width="62" height="26" rx="8" fill="#ffffff" stroke="#cfd8e5" />',
                svg_text(TIME_AXIS_X, y + 4, minutes_to_hhmm(minute), size=12, weight=900, fill="#334155", anchor="middle"),
            ]
        )
    return elements


def plan_route_chain(plan: dict[str, Any]) -> str:
    names = [leg.get("routeTitle") or leg.get("requestedRoute") or "路線" for leg in plan.get("legs", [])]
    return " -> ".join(names) if names else "未规划"


def game_title(game: dict[str, Any]) -> str:
    return f"第 {game.get('index')} 局 · Room {game.get('room_id', '')}"


def game_route_summary(game: dict[str, Any]) -> str:
    return f"Runner: {plan_route_chain(game['runner_plan'])} · Hunter: {plan_route_chain(game['hunter_plan'])}"


def capture_label(game: dict[str, Any]) -> str:
    capture = game.get("capture_summary", "none")
    return "无抓捕" if capture == "none" else str(capture)


def render_header(game: dict[str, Any], height: float) -> list[str]:
    subtitle = f"{game_route_summary(game)} · {capture_label(game)} · {game.get('online_phase', 'LIVE')}"
    return [
        '<rect x="0" y="0" width="1280" height="100%" fill="#f5f7fb" />',
        '<rect x="34" y="26" width="1212" height="96" rx="8" fill="#ffffff" stroke="#d8e0eb" />',
        svg_text(64, 66, game_title(game), size=26, weight=900, fill="#102033"),
        svg_text(64, 96, subtitle, size=14, weight=750, fill="#667487"),
        f'<rect x="92" y="128" width="502" height="42" rx="8" fill="#fff1f2" stroke="#fecdd3" />',
        svg_text(343, 155, "RUNNER", size=16, weight=950, fill="#be123c", anchor="middle"),
        f'<rect x="686" y="128" width="502" height="42" rx="8" fill="#eff6ff" stroke="#bfdbfe" />',
        svg_text(937, 155, "HUNTER", size=16, weight=950, fill="#1d4ed8", anchor="middle"),
        f'<rect x="{TIME_AXIS_X - 43}" y="128" width="86" height="42" rx="8" fill="#f8fafc" stroke="#d8e0eb" />',
        svg_text(TIME_AXIS_X, 155, "TIME", size=15, weight=950, fill="#475569", anchor="middle"),
        f'<rect x="34" y="{height - 48:.1f}" width="1212" height="1" fill="#dfe7f1" />',
    ]


def game_svg(game: dict[str, Any], styles: dict[str, RouteStyle], px_per_minute: float) -> str:
    start_minute, end_minute = time_bounds(game)
    height = TOP_MARGIN + (end_minute - start_minute) * px_per_minute + BOTTOM_MARGIN
    runner_rides = player_rides(game["runner_plan"])
    hunter_rides = player_rides(game["hunter_plan"])
    runner_moments = player_moments(game["runner_plan"])
    hunter_moments = player_moments(game["hunter_plan"])
    event_minutes = [
        *(ride.board_minute for ride in runner_rides + hunter_rides),
        *(ride.alight_minute for ride in runner_rides + hunter_rides),
        *(moment.minute for moment in runner_moments + hunter_moments),
    ]
    elements: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{height:.0f}" viewBox="0 0 {SVG_WIDTH} {height:.0f}" role="img" aria-label="Battle timeline">',
        "<defs>",
        '<filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#64748b" flood-opacity="0.16"/></filter>',
        "</defs>",
        '<g font-family="Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">',
    ]
    elements.extend(render_header(game, height))
    elements.append('<g opacity="0.96">')
    elements.extend(render_axis(start_minute, end_minute, px_per_minute, event_minutes))
    elements.append("</g>")
    elements.append('<g filter="url(#softShadow)">')
    for ride in runner_rides:
        elements.extend(render_ride(ride, "runner", start_minute, px_per_minute, styles))
    for ride in hunter_rides:
        elements.extend(render_ride(ride, "hunter", start_minute, px_per_minute, styles))
    elements.append("</g>")
    elements.append("<g>")
    for moment, label_y in layout_moments(runner_moments, start_minute, px_per_minute):
        elements.extend(render_moment(moment, label_y, "runner", start_minute, px_per_minute))
    for moment, label_y in layout_moments(hunter_moments, start_minute, px_per_minute):
        elements.extend(render_moment(moment, label_y, "hunter", start_minute, px_per_minute))
    elements.append("</g>")
    elements.append(svg_text(SVG_WIDTH / 2, height - 22, "Generated from v3 public battle records", size=12, weight=650, fill="#8a97a8", anchor="middle"))
    elements.append("</g></svg>")
    return "\n".join(elements) + "\n"


def write_index(output_dir: Path, generated: list[tuple[dict[str, Any], Path]]) -> Path:
    rows = []
    for game, svg_path in generated:
        rows.append(
            f'<section class="game"><h2>{esc(game_title(game))}</h2>'
            f'<p>{esc(game_route_summary(game))} · {esc(capture_label(game))} · phase <code>{esc(game.get("online_phase", ""))}</code></p>'
            f'<img src="{esc(svg_path.name)}" alt="第 {game.get("index")} 局时间线"></section>'
        )
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>v3 公网对战时间线</title>
  <style>
    :root {{ color-scheme: light; --bg: #eef2f7; --text: #172033; --muted: #64748b; }}
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); }}
    header {{ padding: 32px clamp(20px, 5vw, 72px) 18px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(28px, 4vw, 44px); }}
    p {{ color: var(--muted); font-weight: 650; }}
    .game {{ margin: 22px auto 42px; width: min(1280px, calc(100vw - 32px)); }}
    .game h2 {{ margin: 0 0 4px; font-size: 22px; }}
    .game p {{ margin: 0 0 14px; }}
    img {{ display: block; width: 100%; height: auto; border: 1px solid #d6dfeb; border-radius: 8px; box-shadow: 0 18px 45px rgba(41, 52, 72, 0.14); background: white; }}
    code {{ background: #fff; border: 1px solid #d6dfeb; border-radius: 6px; padding: 2px 6px; }}
  </style>
</head>
<body>
  <header>
    <h1>v3 公网对战时间线</h1>
    <p>中间是时间流逝，左侧 Runner，右侧 Hunter。乘车区间使用线路颜色，站点和换乘贴在对应时间点。</p>
  </header>
  {''.join(rows)}
</body>
</html>
"""
    path = output_dir / "index.html"
    path.write_text(html_text, encoding="utf-8")
    return path


def selected_games(records: dict[str, Any], game_filter: str) -> list[dict[str, Any]]:
    games = records.get("games", [])
    if not game_filter or game_filter == "all":
        return games
    wanted = {int(item.strip()) for item in game_filter.split(",") if item.strip()}
    return [game for game in games if int(game.get("index", -1)) in wanted]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render v3 public battle records as reusable timeline SVG/HTML diagrams.")
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--game", default="all", help="Game index, comma-separated indexes, or 'all'.")
    parser.add_argument("--px-per-minute", type=float, default=9.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_json_maybe_gz(args.records)
    bundle = load_json_maybe_gz(args.bundle)
    styles = route_styles(bundle)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[tuple[dict[str, Any], Path]] = []
    for game in selected_games(records, args.game):
        room_id = game.get("room_id", "room")
        filename = f"game_{int(game.get('index', 0)):02d}_{slug(room_id)}.svg"
        svg_path = output_dir / filename
        svg_path.write_text(game_svg(game, styles, args.px_per_minute), encoding="utf-8")
        generated.append((game, svg_path))
        print(f"wrote {svg_path}")
    index_path = write_index(output_dir, generated)
    print(f"wrote {index_path}")


if __name__ == "__main__":
    main()
