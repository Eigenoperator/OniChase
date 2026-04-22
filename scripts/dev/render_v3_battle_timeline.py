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

OPERATOR_JA_LABELS = {
    "keikyu": "京急",
    "keio": "京王",
    "keisei": "京成",
    "odakyu": "小田急",
    "rinkai": "東京臨海高速鉄道",
    "seibu": "西武",
    "tama_monorail": "多摩都市モノレール",
    "tobu": "東武",
    "tokyo_monorail": "東京モノレール",
    "tokyu": "東急",
    "tsukuba_express": "首都圏新都市鉄道",
    "yurikamome": "ゆりかもめ",
}
PRIVATE_ROUTE_PREFIX_OPERATOR_IDS = frozenset(OPERATOR_JA_LABELS)
PHYSICAL_ALIAS_OPERATOR_LABELS = {
    "みなとみらい21線": "横浜高速鉄道",
    "小田原線": "小田急",
    "埼玉高速鉄道線": "埼玉高速鉄道",
    "相鉄いずみ野線": "相鉄",
    "相鉄本線": "相鉄",
}
ROUTE_JA_LABELS = {
    "JR_EAST_CHUO_RAPID": "中央線快速",
    "JR_EAST_CHUO_SOBU_LOCAL": "中央・総武線各駅停車",
    "JR_EAST_JOBAN_RAPID": "常磐線快速",
    "JR_NARITA": "成田線",
    "JR_OME": "青梅線",
    "JR_UCHIBO": "内房線",
    "JR_SOTOBO": "外房線",
    "JR_TOGANE": "東金線",
    "JR_KASHIMA": "鹿島線",
    "JR_ITO": "伊東線",
    "JR_JOETSU_LOCAL": "上越線",
    "JR_RYOMO": "両毛線",
    "JR_TOHOKU": "宇都宮線",
    "JR_EAST_KEIHIN_TOHOKU_NEGISHI": "京浜東北線・根岸線",
    "JR_EAST_KEIYO_MUSASHINO": "京葉線・武蔵野線",
    "JR_EAST_SAIKYO_KAWAGOE": "埼京線・川越線",
    "JR_EAST_SHONAN_SHINJUKU": "湘南新宿ライン",
    "JR_EAST_SOBU_RAPID": "総武快速線",
    "JR_EAST_TOKAIDO": "東海道線",
    "JR_EAST_UENO_TOKYO": "上野東京ライン",
    "JR_EAST_YOKOSUKA": "横須賀線",
    "JR_YAMANOTE": "山手線",
    "RINKAI": "りんかい線",
    "SHINKANSEN_AKITA": "秋田新幹線",
    "SHINKANSEN_HOKURIKU": "北陸新幹線",
    "SHINKANSEN_JOETSU": "上越新幹線",
    "SHINKANSEN_KYUSHU": "九州新幹線",
    "SHINKANSEN_NISHI_KYUSHU": "西九州新幹線",
    "SHINKANSEN_TOHOKU_HOKKAIDO": "東北・北海道新幹線",
    "SHINKANSEN_TOKAIDO_SANYO": "東海道・山陽新幹線",
    "SHINKANSEN_YAMAGATA": "山形新幹線",
    "TAMA_MONORAIL": "多摩モノレール線",
    "TOEI_ARAKAWA": "都電荒川線",
    "TOEI_ASAKUSA": "都営浅草線",
    "TOEI_MITA": "都営三田線",
    "TOEI_NIPPORI_TONERI": "日暮里・舎人ライナー",
    "TOEI_OEDO": "都営大江戸線",
    "TOEI_SHINJUKU": "都営新宿線",
    "TOKYO_MONORAIL_HANEDA": "東京モノレール羽田空港線",
    "Tokyu": "東急線",
    "YURIKAMOME": "ゆりかもめ",
    "2号線日比谷線": "日比谷線",
    "3号線銀座線": "銀座線",
    "4号線丸ノ内線": "丸ノ内線",
    "4号線丸ノ内線分岐線": "丸ノ内線方南町支線",
    "5号線東西線": "東西線",
    "6号線三田線": "三田線",
    "7号線南北線": "南北線",
    "8号線有楽町線": "有楽町線",
    "9号線千代田線": "千代田線",
    "10号線新宿線": "新宿線",
    "11号線半蔵門線": "半蔵門線",
    "12号線大江戸線": "大江戸線",
    "13号線副都心線": "副都心線",
}

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
    short_name: str


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


def route_display_name(route: dict[str, Any], name: str) -> str:
    label = ROUTE_JA_LABELS.get(str(name or ""), str(name or ""))
    operator = PHYSICAL_ALIAS_OPERATOR_LABELS.get(str(route.get("shortName") or ""))
    if not operator and route.get("operatorId") in PRIVATE_ROUTE_PREFIX_OPERATOR_IDS:
        operator = OPERATOR_JA_LABELS.get(str(route.get("operatorId") or ""))
    if operator and label and not label.startswith(operator):
        return f"{operator}{label}"
    return label


def route_styles(bundle: dict[str, Any]) -> dict[str, RouteStyle]:
    styles: dict[str, RouteStyle] = {}
    for route in bundle.get("serviceRoutes", []):
        route_id = route.get("id")
        if not route_id:
            continue
        short_name = route.get("shortName") or route.get("longName") or route_id
        title = route_display_name(route, short_name)
        styles[route_id] = RouteStyle(
            color=route.get("color") or "#667487",
            text_color=route.get("textColor") or "#ffffff",
            title=title,
            short_name=str(short_name),
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


def display_trip_label(ride: Ride, style: RouteStyle) -> str:
    if ride.trip_label in {ride.route_title, style.short_name}:
        return style.title
    return ride.trip_label


def player_rides(plan: dict[str, Any]) -> list[Ride]:
    rides: list[Ride] = []
    for index, leg in enumerate(plan.get("legs", []), start=1):
        rides.append(
            Ride(
                index=index,
                route_id=leg.get("routeId") or "",
                route_title=leg.get("routeTitle") or leg.get("requestedRoute") or "Line",
                trip_label=leg.get("tripLabel") or leg.get("tripId") or "Train",
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
            title=f"Start {plan.get('startStation') or plan.get('start') or ''}",
            subtitle="Planning",
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
                [f"Alight {ride.trip_label}" for ride in alights] + [f"Board {ride.trip_label}" for ride in boards]
            )
            moments.append(Moment(minute=minute, title=f"Transfer {station}", subtitle=subtitle, kind="transfer"))
        elif boards:
            ride = boards[0]
            moments.append(Moment(minute=minute, title=f"Board {ride.from_station}", subtitle=ride.trip_label, kind="board"))
        elif alights:
            ride = alights[0]
            moments.append(Moment(minute=minute, title=f"Alight {ride.to_station}", subtitle=f"Alight {ride.trip_label}", kind="alight"))
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
    style = styles.get(ride.route_id, RouteStyle("#667487", "#ffffff", ride.route_title, ride.route_title))
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
    route_title = style.title
    trip_label = display_trip_label(ride, style)
    title = f"{route_title}"
    if trip_label and trip_label != route_title:
        title = f"{route_title} · {trip_label}"
    lines = [
        f"{ride.from_station} -> {ride.to_station}",
        f"{minutes_to_hhmm(ride.board_minute)} - {minutes_to_hhmm(ride.alight_minute)}",
    ]
    elements.extend(render_card_text(card_x, card_y, card_width, title, lines, align=align))
    return elements


def ride_card_bottom(ride: Ride, start_minute: int, px_per_minute: float) -> float:
    y1 = y_for_minute(ride.board_minute, start_minute, px_per_minute)
    y2 = y_for_minute(ride.alight_minute, start_minute, px_per_minute)
    mid = (min(y1, y2) + max(y1, y2)) / 2
    return max(TOP_MARGIN + 8, mid - 86 / 2) + 86


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
    text_anchor = "end" if side == "runner" else "start"
    marker_color = {
        "start": "#0f766e",
        "board": "#2563eb",
        "alight": "#7c3aed",
        "transfer": "#db2777",
    }.get(moment.kind, "#475569")
    fill = mix(marker_color, "#ffffff", 0.9)
    text_x = marker_x + marker_width - 12 if side == "runner" else marker_x + 12
    connector_end = marker_x + marker_width if side == "runner" else marker_x
    return [
        f'<line x1="{connector_end}" y1="{label_y:.1f}" x2="{track_x}" y2="{event_y:.1f}" stroke="{mix(marker_color, "#ffffff", 0.35)}" stroke-width="1.6" />',
        f'<circle cx="{track_x}" cy="{event_y:.1f}" r="4.8" fill="{marker_color}" stroke="#ffffff" stroke-width="2" />',
        f'<rect x="{marker_x}" y="{label_y - 23:.1f}" width="{marker_width}" height="46" rx="{CARD_RADIUS}" fill="{fill}" stroke="{mix(marker_color, "#0f172a", 0.18)}" />',
        svg_text(text_x, label_y - 4, minutes_to_hhmm(moment.minute), size=11, weight=900, fill=marker_color, anchor=text_anchor),
        svg_text(text_x, label_y + 12, moment.title, size=12, weight=800, fill="#182335", anchor=text_anchor),
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


def leg_route_title(leg: dict[str, Any], styles: dict[str, RouteStyle]) -> str:
    style = styles.get(leg.get("routeId") or "")
    return style.title if style else leg.get("routeTitle") or leg.get("requestedRoute") or "Line"


def plan_route_chain(plan: dict[str, Any], styles: dict[str, RouteStyle]) -> str:
    names = [leg_route_title(leg, styles) for leg in plan.get("legs", [])]
    return " -> ".join(names) if names else "No plan"


def game_title(game: dict[str, Any]) -> str:
    return f"Game {game.get('index')} · Room {game.get('room_id', '')}"


def game_route_summary(game: dict[str, Any], styles: dict[str, RouteStyle]) -> str:
    return f"Runner: {plan_route_chain(game['runner_plan'], styles)} · Hunter: {plan_route_chain(game['hunter_plan'], styles)}"


def capture_label(game: dict[str, Any]) -> str:
    capture = game.get("capture_summary", "none")
    return "No capture" if capture == "none" else str(capture)


def render_header(game: dict[str, Any], height: float, styles: dict[str, RouteStyle]) -> list[str]:
    subtitle = f"{game_route_summary(game, styles)} · {capture_label(game)} · {game.get('online_phase', 'LIVE')}"
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
    runner_rides = player_rides(game["runner_plan"])
    hunter_rides = player_rides(game["hunter_plan"])
    runner_moments = player_moments(game["runner_plan"])
    hunter_moments = player_moments(game["hunter_plan"])
    runner_moment_layout = layout_moments(runner_moments, start_minute, px_per_minute)
    hunter_moment_layout = layout_moments(hunter_moments, start_minute, px_per_minute)
    base_height = TOP_MARGIN + (end_minute - start_minute) * px_per_minute + BOTTOM_MARGIN
    max_content_y = y_for_minute(end_minute, start_minute, px_per_minute)
    for ride in runner_rides + hunter_rides:
        max_content_y = max(max_content_y, ride_card_bottom(ride, start_minute, px_per_minute))
    for _moment, label_y in runner_moment_layout + hunter_moment_layout:
        max_content_y = max(max_content_y, label_y + 23)
    height = max(base_height, max_content_y + BOTTOM_MARGIN)
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
    elements.extend(render_header(game, height, styles))
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
    for moment, label_y in runner_moment_layout:
        elements.extend(render_moment(moment, label_y, "runner", start_minute, px_per_minute))
    for moment, label_y in hunter_moment_layout:
        elements.extend(render_moment(moment, label_y, "hunter", start_minute, px_per_minute))
    elements.append("</g>")
    elements.append(svg_text(SVG_WIDTH / 2, height - 22, "Generated from v3 public battle records", size=12, weight=650, fill="#8a97a8", anchor="middle"))
    elements.append("</g></svg>")
    return "\n".join(elements) + "\n"


def write_index(output_dir: Path, generated: list[tuple[dict[str, Any], Path]], styles: dict[str, RouteStyle]) -> Path:
    rows = []
    for game, svg_path in generated:
        rows.append(
            f'<section class="game"><h2>{esc(game_title(game))}</h2>'
            f'<p>{esc(game_route_summary(game, styles))} · {esc(capture_label(game))} · phase <code>{esc(game.get("online_phase", ""))}</code></p>'
            f'<img src="{esc(svg_path.name)}" alt="Game {game.get("index")} timeline"></section>'
        )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>v3 Public Battle Timeline</title>
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
    <h1>v3 Public Battle Timeline</h1>
    <p>Time runs down the center. Runner is on the left, Hunter is on the right. Ride intervals use route colors, and station or transfer callouts stay attached to their event times.</p>
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
    parser.add_argument("--px-per-minute", type=float, default=14.0)
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
    index_path = write_index(output_dir, generated, styles)
    print(f"wrote {index_path}")


if __name__ == "__main__":
    main()
