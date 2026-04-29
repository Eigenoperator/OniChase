#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_BUNDLE = ROOT / "docs" / "data" / "v4_gameplay_map_bundle.json.gz"
DEFAULT_TIMETABLE = ROOT / "docs" / "data" / "v4_gameplay_timetable_compact.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_planner_corridor_audit.json"

ROUTE_JA_LABELS = {
    "SHINKANSEN_AKITA": "秋田新幹線",
    "SHINKANSEN_HOKURIKU": "北陸新幹線",
    "SHINKANSEN_JOETSU": "上越新幹線",
    "SHINKANSEN_KYUSHU": "九州新幹線",
    "SHINKANSEN_NISHI_KYUSHU": "西九州新幹線",
    "SHINKANSEN_SANYO_KYUSHU": "山陽・九州新幹線",
    "SHINKANSEN_TOHOKU_HOKKAIDO": "東北・北海道新幹線",
    "SHINKANSEN_TOKAIDO_SANYO": "東海道・山陽新幹線",
    "SHINKANSEN_YAMAGATA": "山形新幹線",
}

VIRTUAL_SANYO_KYUSHU_ROUTE_ID = "VIRTUAL_SHINKANSEN_SANYO_KYUSHU"
VIRTUAL_CORRIDOR_ROUTES = {
    VIRTUAL_SANYO_KYUSHU_ROUTE_ID: {
        "id": VIRTUAL_SANYO_KYUSHU_ROUTE_ID,
        "operatorId": "shinkansen",
        "operatorName": "JR Shinkansen",
        "shortName": "SHINKANSEN_SANYO_KYUSHU",
        "longName": "JR Shinkansen SHINKANSEN_SANYO_KYUSHU",
        "color": "#0072bc",
        "textColor": "#ffffff",
        "mode": "shinkansen",
        "tags": {
            "source": "v4_virtual_corridor",
            "sourceOperatorId": "shinkansen",
            "lineName": "SHINKANSEN_SANYO_KYUSHU",
            "displayRule": "operating_corridor",
            "physicalLines": ["山陽新幹線", "九州新幹線"],
        },
    },
}

TRANSFER_EQUIVALENCE_RADIUS_M = 700
TRANSFER_PREFIX_RE = re.compile(
    r"^(?:JR|ＪＲ|東京メトロ|都営|東京モノレール|モノレール|京急|京成|京王|小田急|東急|東武|西武|相鉄|近鉄|名鉄|阪急|阪神|京阪|南海|西鉄|京福|叡山|りんかい|ゆりかもめ)"
)
DEFAULT_INTERCHANGE_TRANSFER_MINUTES = 0
REVIEWED_DIRECT_NAME_SETS = {
    frozenset(("名古屋", "名鉄名古屋")),
    frozenset(("名古屋", "近鉄名古屋")),
    frozenset(("名鉄名古屋", "近鉄名古屋")),
    frozenset(("蒲田", "京急蒲田")),
}
REVIEWED_NOT_DIRECT_NAME_SETS: set[frozenset[str]] = set()

SANYO_SHINKANSEN_STATIONS = {
    "新大阪",
    "新神戸",
    "西明石",
    "姫路",
    "相生",
    "岡山",
    "新倉敷",
    "福山",
    "新尾道",
    "三原",
    "東広島",
    "広島",
    "新岩国",
    "徳山",
    "新山口",
    "厚狭",
    "新下関",
    "小倉",
    "博多",
}

KYUSHU_SHINKANSEN_STATIONS = {
    "博多",
    "新鳥栖",
    "久留米",
    "筑後船小屋",
    "新大牟田",
    "新玉名",
    "熊本",
    "新八代",
    "新水俣",
    "出水",
    "川内",
    "鹿児島中央",
}

HOKKAIDO_SHINKANSEN_STATIONS = {"新函館北斗", "木古内", "奥津軽いまべつ"}

HUBS = [
    {
        "name": "東京",
        "prefecture": "東京都",
        "expected": ["東海道・山陽新幹線", "東北・北海道新幹線", "上越新幹線", "北陸新幹線"],
        "forbidden": ["東海道新幹線", "山陽新幹線"],
    },
    {
        "name": "新大阪",
        "prefecture": "大阪府",
        "expected": ["東海道・山陽新幹線", "山陽・九州新幹線"],
        "forbidden": ["東海道新幹線", "山陽新幹線", "九州新幹線"],
    },
    {
        "name": "博多",
        "prefecture": "福岡県",
        "expected": ["東海道・山陽新幹線", "山陽・九州新幹線", "九州新幹線"],
        "forbidden": ["山陽新幹線"],
    },
    {
        "name": "鹿児島中央",
        "prefecture": "鹿児島県",
        "expected": ["山陽・九州新幹線", "九州新幹線"],
        "forbidden": ["山陽新幹線"],
    },
    {
        "name": "大宮",
        "prefecture": "埼玉県",
        "expected": ["東北・北海道新幹線", "上越新幹線", "北陸新幹線"],
        "forbidden": ["京都線", "千里線"],
    },
    {
        "name": "新函館北斗",
        "prefecture": "北海道",
        "expected": ["東北・北海道新幹線"],
        "forbidden": ["東北新幹線", "北海道新幹線", "秋田新幹線"],
    },
]


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def seconds_to_hhmm(seconds: int) -> str:
    minutes = seconds // 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def hhmm_to_seconds(value: str) -> int:
    hour, minute = value.split(":")
    return (int(hour) * 60 + int(minute)) * 60


def decode_compact_timetable(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("format") != "v3-timetable-compact-v1":
        return payload.get("tripInstances", [])
    station_group_ids = payload.get("stationGroupIds", [])
    route_ids = payload.get("routeIds", [])
    service_names = payload.get("serviceNames", [])
    trips: list[dict[str, Any]] = []
    for row in payload.get("trips", []):
        trips.append(
            {
                "id": row[0],
                "routeId": route_ids[row[1]] if row[1] < len(route_ids) else "",
                "serviceName": service_names[row[2]] if row[2] < len(service_names) else "",
                "serviceNumber": row[3] or "",
                "lineTrace": [
                    {
                        "fromSequence": trace[0],
                        "toSequence": trace[1],
                        "routeId": route_ids[trace[2]] if trace[2] < len(route_ids) else "",
                    }
                    for trace in (row[5] if len(row) > 5 else []) or []
                ],
                "stopTimes": [
                    {
                        "sequence": index + 1,
                        "stationGroupId": station_group_ids[stop[0]] if stop[0] < len(station_group_ids) else "",
                        "arrivalTimeSec": stop[1],
                        "departureTimeSec": stop[2],
                    }
                    for index, stop in enumerate(row[4] or [])
                ],
            }
        )
    return trips


class PlannerCorridorAuditor:
    def __init__(self, map_bundle: dict[str, Any], timetable_payload: dict[str, Any]) -> None:
        self.station_groups = {group["id"]: group for group in map_bundle.get("stationGroups", [])}
        self.physical_station_by_group_id = {}
        for station in map_bundle.get("physicalStations", []):
            self.physical_station_by_group_id.setdefault(station.get("stationGroupId"), station)
        self.routes = {route["id"]: route for route in map_bundle.get("serviceRoutes", [])}
        self.routes.update(VIRTUAL_CORRIDOR_ROUTES)
        self.trips = decode_compact_timetable(timetable_payload)
        self.transfer_equivalent_group_ids = self.build_transfer_equivalent_groups()
        self.trips_by_station_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for trip in self.trips:
            seen = set()
            for stop in trip.get("stopTimes", []):
                station_group_id = stop.get("stationGroupId")
                if not station_group_id or station_group_id in seen:
                    continue
                seen.add(station_group_id)
                self.trips_by_station_group[station_group_id].append(trip)

    def normalized_transfer_station_name(self, name: str) -> str:
        normalized = re.sub(r"\s+", "", str(name or ""))
        normalized = TRANSFER_PREFIX_RE.sub("", normalized)
        return re.sub(r"駅$", "", normalized)

    def transfer_key_for_group(self, station_group_id: str) -> str:
        group = self.station_groups.get(station_group_id, {})
        station = self.physical_station_by_group_id.get(station_group_id, {})
        return self.normalized_transfer_station_name(
            group.get("names", {}).get("ja")
            or group.get("primaryName")
            or station.get("names", {}).get("ja")
            or station.get("name")
            or station_group_id
        )

    def station_group_coordinate(self, station_group_id: str) -> tuple[float, float] | None:
        group = self.station_groups.get(station_group_id, {})
        centroid = group.get("centroid") or {}
        if isinstance(centroid.get("lon"), (int, float)) and isinstance(centroid.get("lat"), (int, float)):
            return float(centroid["lon"]), float(centroid["lat"])
        station = self.physical_station_by_group_id.get(station_group_id, {})
        if isinstance(station.get("lon"), (int, float)) and isinstance(station.get("lat"), (int, float)):
            return float(station["lon"]), float(station["lat"])
        return None

    def coordinate_distance_meters(self, left: tuple[float, float] | None, right: tuple[float, float] | None) -> float:
        if not left or not right:
            return math.inf
        lon1, lat1 = map(math.radians, left)
        lon2, lat2 = map(math.radians, right)
        d_lon = lon2 - lon1
        d_lat = lat2 - lat1
        a = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * (math.sin(d_lon / 2) ** 2)
        return 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def build_transfer_equivalent_groups(self) -> dict[str, set[str]]:
        by_key: dict[str, list[str]] = defaultdict(list)
        equivalents = {station_group_id: {station_group_id} for station_group_id in self.station_groups}
        for station_group_id in self.station_groups:
            key = self.transfer_key_for_group(station_group_id)
            if key:
                by_key[key].append(station_group_id)
        for group_ids in by_key.values():
            for left_index, left_group_id in enumerate(group_ids):
                for right_group_id in group_ids[left_index + 1 :]:
                    left_name = self.display_name_for_group(left_group_id)
                    right_name = self.display_name_for_group(right_group_id)
                    if frozenset((left_name, right_name)) in REVIEWED_NOT_DIRECT_NAME_SETS:
                        continue
                    reviewed_direct = frozenset((left_name, right_name)) in REVIEWED_DIRECT_NAME_SETS
                    distance = self.coordinate_distance_meters(
                        self.station_group_coordinate(left_group_id),
                        self.station_group_coordinate(right_group_id),
                    )
                    if reviewed_direct or distance <= TRANSFER_EQUIVALENCE_RADIUS_M:
                        equivalents[left_group_id].add(right_group_id)
                        equivalents[right_group_id].add(left_group_id)
        return equivalents

    def display_name_for_group(self, station_group_id: str) -> str:
        group = self.station_groups.get(station_group_id, {})
        return group.get("names", {}).get("ja") or group.get("primaryName") or station_group_id

    def station_group_id_by_name_and_prefecture(self, name: str, prefecture: str) -> str | None:
        matches = [
            group
            for group in self.station_groups.values()
            if (group.get("names", {}).get("ja") or group.get("primaryName")) == name
        ]
        selected = next(
            (group for group in matches if prefecture in (group.get("tags", {}).get("prefectureNamesJa") or [])),
            matches[0] if matches else None,
        )
        return selected.get("id") if selected else None

    def route_title(self, route_id: str) -> str:
        route = self.routes.get(route_id, {})
        for candidate in (route.get("shortName"), route.get("longName"), route_id):
            if candidate in ROUTE_JA_LABELS:
                return ROUTE_JA_LABELS[candidate]
        for candidate in (route.get("shortName"), route.get("longName"), route_id):
            if candidate:
                return str(candidate)
        return "路線"

    def route_subtitle(self, route_id: str) -> str:
        route = self.routes.get(route_id, {})
        return route.get("operatorName") or route.get("operatorId") or route_id

    def route_id_by_short_name(self, short_name: str) -> str | None:
        return next((route_id for route_id, route in self.routes.items() if route.get("shortName") == short_name), None)

    def is_shinkansen_corridor_route(self, route_id: str) -> bool:
        route = self.routes.get(route_id, {})
        return route.get("operatorId") == "shinkansen" and str(route.get("shortName") or "").startswith("SHINKANSEN_")

    def trip_uses_station_set(self, trip: dict[str, Any], station_set: set[str], boundary: str) -> bool:
        for stop in trip.get("stopTimes", []):
            name = self.display_name_for_group(stop.get("stationGroupId", ""))
            if name != boundary and name in station_set:
                return True
        return False

    def route_choice_ids_for_trip(self, trip: dict[str, Any]) -> list[str]:
        route_id = trip.get("routeId") or ""
        route = self.routes.get(route_id, {})
        short_name = str(route.get("shortName") or "")
        if self.is_shinkansen_corridor_route(route_id) and short_name in {"SHINKANSEN_AKITA", "SHINKANSEN_YAMAGATA"}:
            has_hokkaido_segment = self.trip_uses_station_set(trip, HOKKAIDO_SHINKANSEN_STATIONS, "")
            if has_hokkaido_segment:
                return [self.route_id_by_short_name("SHINKANSEN_TOHOKU_HOKKAIDO") or route_id]
        if self.is_shinkansen_corridor_route(route_id) and short_name in {"SHINKANSEN_TOKAIDO_SANYO", "SHINKANSEN_KYUSHU"}:
            has_sanyo = self.trip_uses_station_set(trip, SANYO_SHINKANSEN_STATIONS, "博多")
            has_kyushu = self.trip_uses_station_set(trip, KYUSHU_SHINKANSEN_STATIONS, "博多")
            if has_sanyo and has_kyushu:
                return [VIRTUAL_SANYO_KYUSHU_ROUTE_ID]
        return [route_id] if route_id else []

    def is_corridor_choice_id(self, route_id: str) -> bool:
        if route_id == VIRTUAL_SANYO_KYUSHU_ROUTE_ID:
            return True
        return self.is_shinkansen_corridor_route(route_id)

    def available_departures(self, station_group_id: str, after_seconds: int) -> list[dict[str, Any]]:
        rows = []
        seen = set()
        for search_group_id in self.transfer_equivalent_group_ids.get(station_group_id, {station_group_id}):
            for trip in self.trips_by_station_group.get(search_group_id, []):
                if not any(self.is_corridor_choice_id(route_id) for route_id in self.route_choice_ids_for_trip(trip)):
                    continue
                stops = trip.get("stopTimes", [])
                for index, stop in enumerate(stops):
                    if stop.get("stationGroupId") != search_group_id:
                        continue
                    departure = stop.get("departureTimeSec")
                    if departure is None or departure < after_seconds or index >= len(stops) - 1:
                        continue
                    key = (trip.get("id"), index, departure)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "trip": trip,
                            "boardStop": stop,
                            "departureSec": departure,
                            "departureHhmm": seconds_to_hhmm(departure),
                            "searchStationGroupId": search_group_id,
                        }
                    )
                    break
        rows.sort(key=lambda row: (row["departureSec"], self.route_title(row["trip"].get("routeId", ""))))
        return rows

    def available_route_departures(self, station_group_id: str, route_id: str, after_seconds: int, limit: int = 8) -> list[dict[str, Any]]:
        rows = [
            row
            for row in self.available_departures(station_group_id, after_seconds)
            if route_id in self.route_choice_ids_for_trip(row["trip"])
        ]
        return rows[:limit]

    def route_choices_from_departures(self, departures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_route: dict[str, dict[str, Any]] = {}
        for row in departures:
            for route_id in self.route_choice_ids_for_trip(row["trip"]):
                current = by_route.setdefault(
                    route_id,
                    {
                        "routeId": route_id,
                        "firstDepartureSec": row["departureSec"],
                        "firstDeparture": row["departureHhmm"],
                        "trainCount": 0,
                    },
                )
                current["firstDepartureSec"] = min(current["firstDepartureSec"], row["departureSec"])
                current["firstDeparture"] = seconds_to_hhmm(current["firstDepartureSec"])
                current["trainCount"] += 1
        return sorted(by_route.values(), key=lambda item: (item["firstDepartureSec"], self.route_title(item["routeId"])))

    def sample_row(self, row: dict[str, Any], route_id: str) -> dict[str, Any]:
        trip = row["trip"]
        stops = trip.get("stopTimes", [])
        board_sequence = row["boardStop"].get("sequence", 0)
        next_stop = next((stop for stop in stops if stop.get("sequence", 0) > board_sequence), {})
        return {
            "departure": row["departureHhmm"],
            "routeChoice": self.route_title(route_id),
            "tripRoute": self.route_title(trip.get("routeId", "")),
            "serviceName": trip.get("serviceName") or "",
            "serviceNumber": trip.get("serviceNumber") or "",
            "origin": self.display_name_for_group(stops[0].get("stationGroupId", "")) if stops else "",
            "terminal": self.display_name_for_group(stops[-1].get("stationGroupId", "")) if stops else "",
            "next": self.display_name_for_group(next_stop.get("stationGroupId", "")) if next_stop else "",
        }

    def audit_hub(self, hub: dict[str, Any], after_seconds: int) -> dict[str, Any]:
        station_group_id = self.station_group_id_by_name_and_prefecture(hub["name"], hub["prefecture"])
        if not station_group_id:
            return {**hub, "stationGroupId": None, "choices": [], "warnings": [{"kind": "missing_station_group"}]}
        departures = self.available_departures(station_group_id, after_seconds)
        choices = []
        for choice in self.route_choices_from_departures(departures):
            route_id = choice["routeId"]
            samples = [
                self.sample_row(row, route_id)
                for row in self.available_route_departures(station_group_id, route_id, after_seconds)
            ]
            choices.append(
                {
                    "routeId": route_id,
                    "title": self.route_title(route_id),
                    "subtitle": self.route_subtitle(route_id),
                    "firstDeparture": choice["firstDeparture"],
                    "trainCount": choice["trainCount"],
                    "samples": samples,
                }
            )
        choice_titles = [choice["title"] for choice in choices]
        surfaced_route_ids = {choice["routeId"] for choice in choices}
        unsurfaced_route_ids = {
            route_id
            for row in departures
            for route_id in self.route_choice_ids_for_trip(row["trip"])
            if route_id not in surfaced_route_ids
        }
        warnings = []
        for title in hub.get("expected", []):
            if title not in choice_titles:
                warnings.append({"kind": "expected_missing", "title": title})
        for title in hub.get("forbidden", []):
            if title in choice_titles:
                warnings.append({"kind": "forbidden_present", "title": title})
        for title in sorted({title for title in choice_titles if choice_titles.count(title) > 1}):
            warnings.append({"kind": "duplicate_choice_title", "title": title})
        for choice in choices:
            if choice["trainCount"] > 0 and not choice["samples"]:
                warnings.append({"kind": "visible_but_unboardable", "title": choice["title"]})
        for route_id in sorted(unsurfaced_route_ids):
            warnings.append({"kind": "boardable_but_unsurfaced", "routeId": route_id, "title": self.route_title(route_id)})
        return {
            "name": hub["name"],
            "prefecture": hub["prefecture"],
            "stationGroupId": station_group_id,
            "expected": hub.get("expected", []),
            "forbidden": hub.get("forbidden", []),
            "departureCount": len(departures),
            "choices": choices,
            "warnings": warnings,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit v4 planner route choices against corridor display rules.")
    parser.add_argument("--map-bundle", type=Path, default=DEFAULT_MAP_BUNDLE)
    parser.add_argument("--timetable", type=Path, default=DEFAULT_TIMETABLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--after", default="06:00")
    args = parser.parse_args()

    auditor = PlannerCorridorAuditor(load_json(args.map_bundle), load_json(args.timetable))
    hubs = [auditor.audit_hub(hub, hhmm_to_seconds(args.after)) for hub in HUBS]
    warnings = [warning for hub in hubs for warning in hub["warnings"]]
    payload = {
        "schema": "onichase.v4.planner_corridor_audit.v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "mapBundle": str(args.map_bundle.relative_to(ROOT)),
        "timetable": str(args.timetable.relative_to(ROOT)),
        "after": args.after,
        "summary": {
            "hubCount": len(hubs),
            "warningCount": len(warnings),
        },
        "routeDisplayLayers": {
            "physicalLine": "真实基础设施线路和站点几何。用于地图绘制、站点 identity、真实路径高亮和移动几何。",
            "operatingService": "真实车次/时刻表 route 与列车服务族。用于保持一辆车跨直通区间时仍然是同一个 trip。",
            "uiCorridor": "玩家视角的走廊显示名。用于把乘客理解为同一服务走廊的多条物理线合并成一个可选项。",
        },
        "hubs": hubs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}: hubs={payload['summary']['hubCount']} warnings={payload['summary']['warningCount']}")


if __name__ == "__main__":
    main()
