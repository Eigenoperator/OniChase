#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import socket
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_PAGE_URL = "https://eigenoperator.github.io/OniChase/v3.html"
DEFAULT_ROOM_SERVER = "https://onichase-v3-room-server.onrender.com"
DEFAULT_OUTPUT_DIR = Path("reports")
DEFAULT_BUNDLE = Path("docs/data/v3_tokyo_map_bundle.json.gz")

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


SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "Tokaido to Toyoko regression",
        "runner": {
            "start": "東京",
            "legs": [
                {"route": "東海道線", "to": "横浜"},
                {"route": "東急東横線", "to": "菊名"},
            ],
        },
        "hunter": {
            "start": "新宿",
            "legs": [
                {"route": "丸ノ内線", "to": "四ツ谷"},
                {"route": "南北線", "to": "目黒"},
            ],
        },
    },
    {
        "name": "Yamanote to Keikyu / Odakyu to Inokashira",
        "runner": {
            "start": "東京",
            "legs": [
                {"route": "山手線", "to": "品川"},
                {"route": "京急本線", "to": "京急蒲田"},
            ],
        },
        "hunter": {
            "start": "新宿",
            "legs": [
                {"route": "小田急小田原線", "to": "下北沢"},
                {"route": "京王井の頭線", "to": "渋谷"},
            ],
        },
    },
    {
        "name": "Marunouchi to Namboku / Chuo to Tozai",
        "runner": {
            "start": "東京",
            "legs": [
                {"route": "丸ノ内線", "to": "四ツ谷"},
                {"route": "南北線", "to": "駒込"},
            ],
        },
        "hunter": {
            "start": "中野",
            "legs": [
                {"route": "東西線", "to": "大手町"},
                {"route": "丸ノ内線", "to": "東京"},
            ],
        },
    },
    {
        "name": "Keiyo to Yurakucho / Toei Shinjuku to Mita",
        "runner": {
            "start": "東京",
            "legs": [
                {"route": "京葉線・武蔵野線", "to": "新木場"},
                {"route": "有楽町線", "to": "豊洲"},
            ],
        },
        "hunter": {
            "start": "新宿三丁目",
            "legs": [
                {"route": "都営新宿線", "to": "神保町"},
                {"route": "都営三田線", "to": "大手町"},
            ],
        },
    },
    {
        "name": "Sobu rapid to Hanzomon / Yamanote to Seibu",
        "runner": {
            "start": "東京",
            "legs": [
                {"route": "総武快速線", "to": "錦糸町"},
                {"route": "半蔵門線", "to": "渋谷"},
            ],
        },
        "hunter": {
            "start": "新宿",
            "legs": [
                {"route": "山手線", "to": "高田馬場"},
                {"route": "西武新宿線", "to": "西武新宿"},
            ],
        },
    },
    {
        "name": "Joetsu Shinkansen to Keihin-Tohoku / Saikyo transfer",
        "runner": {
            "start": "東京",
            "legs": [
                {"route": "上越新幹線", "to": "大宮"},
                {"route": "京浜東北線・根岸線", "to": "北浦和"},
            ],
        },
        "hunter": {
            "start": "新宿",
            "legs": [
                {"route": "埼京線・川越線", "to": "赤羽"},
                {"route": "京浜東北線・根岸線", "to": "王子"},
            ],
        },
    },
    {
        "name": "Tokaido Shinkansen to Tokyu Shin-Yokohama",
        "runner": {
            "start": "東京",
            "legs": [
                {"route": "東海道・山陽新幹線", "to": "新横浜"},
                {"route": "東急新横浜線", "to": "日吉"},
            ],
        },
        "hunter": {
            "start": "新宿",
            "legs": [
                {"route": "丸ノ内線", "to": "中野坂上"},
                {"route": "丸ノ内線", "to": "池袋"},
            ],
        },
    },
    {
        "name": "Yokosuka to Toyoko chain / Oedo branch",
        "runner": {
            "start": "東京",
            "legs": [
                {"route": "横須賀線", "to": "武蔵小杉"},
                {"route": "東急東横線", "to": "渋谷"},
                {"route": "東急東横線", "to": "綱島"},
            ],
        },
        "hunter": {
            "start": "新宿",
            "legs": [
                {"route": "都営大江戸線", "to": "豊島園"},
                {"route": "都営大江戸線", "to": "練馬春日町"},
            ],
        },
    },
    {
        "name": "Ueno-Tokyo to Chiyoda / Keio to Inokashira",
        "runner": {
            "start": "東京",
            "legs": [
                {"route": "上野東京ライン", "to": "北千住"},
                {"route": "千代田線", "to": "大手町"},
            ],
        },
        "hunter": {
            "start": "新宿",
            "legs": [
                {"route": "京王線", "to": "明大前"},
                {"route": "京王井の頭線", "to": "吉祥寺"},
            ],
        },
    },
    {
        "name": "Keikyu-Asakusa-Keisei through-corridor audit",
        "runner": {
            "start": "品川",
            "legs": [
                {"route": "京急本線", "to": "泉岳寺"},
                {"route": "都営浅草線", "to": "押上"},
                {"route": "京成押上線", "to": "青砥"},
            ],
        },
        "hunter": {
            "start": "渋谷",
            "legs": [
                {"route": "銀座線", "to": "表参道"},
                {"route": "半蔵門線", "to": "押上"},
            ],
        },
    },
]


BATTLE_HELPER_JS = r"""
(() => {
  const version = '2026-04-22-public-battle-records-private-route-prefixes';
  if (window.__oniBattle && window.__oniBattle.version === version) return;
  const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
  const norm = (value) => String(value || '')
    .normalize('NFKC')
    .replace(/[・･\s()（）_\-]/gu, '')
    .replace(/^(?:JR|ＪＲ|東京メトロ|都営|京急|京成|京王|小田急|東急|東武|西武|相鉄)/u, '')
    .replace(/駅$/u, '');

  function routeLabels(routeId) {
    const route = state.routeById.get(routeId);
    if (!route) return [routeId];
    const ja = routeJapaneseName(routeId);
    const op = operatorJaLabel(route.operatorId);
    return [
      routeId,
      route.shortName,
      route.longName,
      ja,
      op && ja ? `${op}${ja}` : '',
      route.shortName && op ? `${op}${route.shortName}` : '',
    ].filter(Boolean);
  }

  function routeMatches(routeId, query) {
    const q = norm(query);
    return routeLabels(routeId).some((label) => {
      const n = norm(label);
      return n === q || n.includes(q) || q.includes(n);
    });
  }

  function stationLabels(stationGroupId) {
    const group = state.stationGroupById.get(stationGroupId);
    const station = state.stationByGroupId.get(stationGroupId);
    const label = state.labelByGroupId.get(stationGroupId);
    return [
      stationGroupId,
      label?.displayNameJa,
      group?.names?.ja,
      group?.primaryName,
      station?.names?.ja,
      station?.name,
    ].filter(Boolean);
  }

  function findStation(query) {
    const q = norm(query);
    const exact = [];
    const fuzzy = [];
    state.stationGroupById.forEach((_group, stationGroupId) => {
      const labels = stationLabels(stationGroupId).map(norm);
      if (labels.some((label) => label === q)) exact.push(stationGroupId);
      else if (labels.some((label) => label.includes(q) || q.includes(label))) fuzzy.push(stationGroupId);
    });
    const match = exact[0] || fuzzy[0];
    if (!match) throw new Error(`Station not found: ${query}`);
    return match;
  }

  function candidateRouteIds(stationGroupId, minute, seat) {
    const preview = { currentState: { kind: 'NODE', stationGroupId }, currentMinute: minute };
    return routeChoicesFromDepartures(availableDepartures(preview, seat)).map((choice) => choice.routeId);
  }

  function findRoute(query, stationGroupId, minute, seat) {
    const q = norm(query);
    const local = stationGroupId ? candidateRouteIds(stationGroupId, minute, seat) : [];
    const ordered = [...local, ...state.routeById.keys()].filter((routeId, index, list) => list.indexOf(routeId) === index);
    const exact = ordered.find((routeId) => routeLabels(routeId).some((label) => norm(label) === q));
    if (exact) return exact;
    const fuzzy = ordered.find((routeId) => routeMatches(routeId, query));
    if (fuzzy) return fuzzy;
    throw new Error(`Route not found: ${query}`);
  }

  function destinationStop(trip, boardStop, destinationGroupId) {
    const destIds = new Set(equivalentStationGroupIds(destinationGroupId));
    return (trip.stopTimes || []).find((stop) => stop.sequence > boardStop.sequence && destIds.has(stop.stationGroupId)) || null;
  }

  function resolveLeg(seat, currentStationId, currentMinute, leg) {
    const destinationId = findStation(leg.to);
    const routeQueries = Array.isArray(leg.route) ? leg.route : [leg.route];
    const earliest = effectiveDepartureMinute(seat, currentMinute);
    const errors = [];
    for (const routeQuery of routeQueries) {
      let routeId = null;
      try {
        routeId = findRoute(routeQuery, currentStationId, currentMinute, seat);
      } catch (error) {
        errors.push(String(error));
        continue;
      }
      const rows = departuresForStationGroup(currentStationId, earliest, { routeId });
      for (const row of rows) {
        if (!hasDownstreamStop(row.trip, row.stop)) continue;
        const alightStop = destinationStop(row.trip, row.stop, destinationId);
        if (!alightStop) continue;
        return {
          requestedRoute: routeQuery,
          routeId,
          routeTitle: routeTitle(routeId),
          trip: row.trip,
          tripId: row.trip.id,
          tripLabel: formatTripLabelForBoarding({ trip: row.trip, boardStop: row.stop, routeIds: row.routeIds }, routeId),
          boardStop: row.stop,
          boardStationId: row.stop.stationGroupId,
          boardStation: displayNameForGroup(row.stop.stationGroupId),
          boardHhmm: minutesToHhmm(stopDepartureMinutes(row.stop)),
          alightStop,
          alightStationId: alightStop.stationGroupId,
          alightStation: displayNameForGroup(alightStop.stationGroupId),
          alightHhmm: minutesToHhmm(stopArrivalMinutes(alightStop)),
        };
      }
      errors.push(`No ${routeQuery} train from ${displayNameForGroup(currentStationId)} to ${leg.to} after ${minutesToHhmm(earliest)}`);
    }
    throw new Error(errors.join('; ') || `Cannot resolve leg to ${leg.to}`);
  }

  async function ensureReady(timeoutMs = 90000) {
    const started = Date.now();
    while (!state.bundle || !state.map) {
      if (Date.now() - started > timeoutMs) throw new Error('Timed out waiting for map bundle');
      await wait(250);
    }
    ensureTimetableLoaded();
    while (state.timetableStatus !== 'ready') {
      if (state.timetableStatus === 'error') throw new Error('Timetable failed to load');
      if (Date.now() - started > timeoutMs) throw new Error(`Timed out waiting for timetable (${state.timetableStatus})`);
      await wait(500);
    }
    return snapshot();
  }

  function snapshot() {
    return {
      roomId: state.online.roomId,
      seat: state.online.seat,
      phase: state.phase,
      matchStarted: Boolean(state.online.lastRoom?.match_started),
      currentTime: minutesToHhmm(state.currentGameMinute),
      timetableStatus: state.timetableStatus,
      tripCount: state.tripById.size,
      serverUrl: state.online.serverUrl,
      players: JSON.parse(JSON.stringify(state.players)),
      room: state.online.lastRoom,
    };
  }

  async function createRoom(seat, serverUrl) {
    state.online.serverUrl = serverUrl;
    setLobbySeat(seat);
    await createRoomAndJoinSeat();
    await ensureReady();
    return snapshot();
  }

  async function joinRoom(seat, roomId, serverUrl) {
    state.online.serverUrl = serverUrl;
    setLobbySeat(seat);
    roomIdInput.value = roomId;
    await joinExistingRoom();
    await ensureReady();
    return snapshot();
  }

  function setPlan(seat, spec) {
    const startStationId = findStation(spec.start);
    const player = state.players[seat] || { input_mode: 'plan', steps: [] };
    player.start_station_id = startStationId;
    player.input_mode = 'plan';
    player.steps = [];
    state.players[seat] = player;
    state.activeMode = seat;
    let currentStationId = startStationId;
    let currentMinute = hhmmToMinutes(state.startTime);
    const legs = [];
    for (const leg of spec.legs || []) {
      const resolved = resolveLeg(seat, currentStationId, currentMinute, leg);
      player.steps.push({ type: 'BOARD_TRAIN', trip_id: resolved.tripId });
      player.steps.push({ type: 'RIDE_TO_STATION', station_id: resolved.alightStationId });
      legs.push({
        requestedRoute: resolved.requestedRoute,
        routeId: resolved.routeId,
        routeTitle: resolved.routeTitle,
        tripId: resolved.tripId,
        tripLabel: resolved.tripLabel,
        fromStationId: resolved.boardStationId,
        fromStation: resolved.boardStation,
        boardHhmm: resolved.boardHhmm,
        toStationId: resolved.alightStationId,
        toStation: resolved.alightStation,
        alightHhmm: resolved.alightHhmm,
      });
      currentStationId = resolved.alightStationId;
      currentMinute = stopArrivalMinutes(resolved.alightStop);
    }
    clearPendingTrip(seat);
    invalidateSimulation();
    renderGame();
    return {
      seat,
      start: spec.start,
      start_station_id: startStationId,
      startStation: displayNameForGroup(startStationId),
      steps: JSON.parse(JSON.stringify(player.steps)),
      legs,
      finalStationId: currentStationId,
      finalStation: displayNameForGroup(currentStationId),
      finalHhmm: minutesToHhmm(currentMinute),
    };
  }

  async function planAndSubmit(seat, spec) {
    const plan = setPlan(seat, spec);
    await submitCurrentPlanToRoom();
    await wait(250);
    return { plan, snapshot: snapshot(), planBoardText: planBoardEl.innerText };
  }

  async function readySeat() {
    await markSeatReady();
    await wait(350);
    return snapshot();
  }

  async function waitForPhase(expectedPhase, timeoutMs = 90000) {
    const started = Date.now();
    while (state.phase !== expectedPhase) {
      if (onlineActive()) {
        try { await syncRoomState(); } catch (_error) {}
      }
      if (Date.now() - started > timeoutMs) throw new Error(`Timed out waiting for ${expectedPhase}; currently ${state.phase}`);
      await wait(500);
    }
    return snapshot();
  }

  function resultForPlans(scenarioId, runnerPlan, hunterPlan) {
    const scenario = {
      id: scenarioId,
      start_time_hhmm: state.startTime,
      end_time_hhmm: state.endTime,
      players: {
        runner: { start_station_id: runnerPlan.start_station_id, plan: { steps: runnerPlan.steps } },
        hunter: { start_station_id: hunterPlan.start_station_id, plan: { steps: hunterPlan.steps } },
      },
    };
    const runner = expandPlayerPlan('runner', scenario.players.runner, scenario);
    const hunter = expandPlayerPlan('hunter', scenario.players.hunter, scenario);
    const match = buildMatchEventLog(scenario, runner, hunter);
    const eventLog = match.match_event_log.map((event) => ({
      ...event,
      station_label: event.station_group_id ? displayNameForGroup(event.station_group_id) : null,
      trip_label: event.trip_id ? formatTripLabel(state.tripById.get(event.trip_id) || { serviceName: event.trip_id }) : null,
    }));
    const capture = match.capture ? {
      ...match.capture,
      station_label: match.capture.station_group_id ? displayNameForGroup(match.capture.station_group_id) : null,
      trip_label: match.capture.trip_id ? formatTripLabel(state.tripById.get(match.capture.trip_id) || { serviceName: match.capture.trip_id }) : null,
    } : null;
    return {
      scenario_id: scenario.id,
      dataset_id: state.bundle?.metadata?.datasetId || 'v3_tokyo',
      capture,
      match_event_log: eventLog,
      players: { runner, hunter },
    };
  }

  window.__oniBattle = {
    version,
    ensureReady,
    snapshot,
    createRoom,
    joinRoom,
    setPlan,
    planAndSubmit,
    readySeat,
    waitForPhase,
    resultForPlans,
  };
})();
"""


@dataclass
class Driver:
    name: str
    port: int
    width: int
    height: int
    log_dir: Path
    session_id: str | None = None
    process: subprocess.Popen[bytes] | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_dir / f"geckodriver-{self.name}-{self.port}.log"
        log_file = log_path.open("wb")
        self.process = subprocess.Popen(
            ["geckodriver", "--host", "127.0.0.1", "--port", str(self.port)],
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        self._wait_status()
        response = self.request(
            "POST",
            "/session",
            {
                "capabilities": {
                    "alwaysMatch": {
                        "browserName": "firefox",
                        "moz:firefoxOptions": {"args": ["-headless"]},
                    }
                }
            },
            timeout=30,
        )
        self.session_id = response["sessionId"]
        self.request(
            "POST",
            f"/session/{self.session_id}/window/rect",
            {"width": self.width, "height": self.height, "x": 0, "y": 0},
            timeout=10,
        )
        self.request(
            "POST",
            f"/session/{self.session_id}/timeouts",
            {"script": 180000, "pageLoad": 180000, "implicit": 0},
            timeout=10,
        )

    def _wait_status(self) -> None:
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                self.request("GET", "/status", None, timeout=2)
                return
            except Exception:
                time.sleep(0.2)
        raise RuntimeError(f"{self.name} geckodriver did not start on port {self.port}")

    def request(self, method: str, path: str, payload: Any | None, timeout: float = 60) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
        decoded = json.loads(body.decode("utf-8")) if body else {}
        if "value" in decoded:
            value = decoded["value"]
            if isinstance(value, dict) and value.get("error"):
                raise RuntimeError(f"{value.get('error')}: {value.get('message')}")
            return value
        return decoded

    def navigate(self, url: str) -> None:
        assert self.session_id
        self.request("POST", f"/session/{self.session_id}/url", {"url": url}, timeout=180)

    def execute(self, script: str, args: list[Any] | None = None, timeout: float = 60) -> Any:
        assert self.session_id
        return self.request(
            "POST",
            f"/session/{self.session_id}/execute/sync",
            {"script": script, "args": args or []},
            timeout=timeout,
        )

    def execute_async(self, script: str, args: list[Any] | None = None, timeout: float = 180) -> Any:
        assert self.session_id
        return self.request(
            "POST",
            f"/session/{self.session_id}/execute/async",
            {"script": script, "args": args or []},
            timeout=timeout,
        )

    def quit(self) -> None:
        if self.session_id:
            try:
                self.request("DELETE", f"/session/{self.session_id}", None, timeout=10)
            except Exception:
                pass
            self.session_id = None
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            self.process = None


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def js_async(expression: str) -> str:
    return (
        "const done = arguments[arguments.length - 1];"
        "(async () => {"
        f"return ({expression});"
        "})().then((value) => done({ok: true, value}), "
        "(error) => {"
        "const message = error && error.message ? error.message : String(error);"
        "const stack = error && error.stack ? String(error.stack) : '';"
        "done({ok: false, error: stack && !stack.includes(message) ? `${message}\\n${stack}` : (stack || message)});"
        "});"
    )


def unwrap_async(result: dict[str, Any]) -> Any:
    if result.get("ok"):
        return result.get("value")
    raise RuntimeError(result.get("error") or "unknown browser error")


def inject_helper(driver: Driver) -> None:
    script = """
    const helper = arguments[0];
    const node = document.createElement('script');
    node.textContent = helper;
    document.documentElement.appendChild(node);
    node.remove();
    return Boolean(window.__oniBattle);
    """
    deadline = time.time() + 120
    last_error = ""
    while time.time() < deadline:
        try:
            if driver.execute(script, [BATTLE_HELPER_JS], timeout=10):
                return
        except Exception as error:
            last_error = str(error)
        time.sleep(0.5)
    raise RuntimeError(f"Could not inject battle helper into {driver.name}: {last_error}")


def call_helper(driver: Driver, expression: str, timeout: float = 180) -> Any:
    return unwrap_async(driver.execute_async(js_async(expression), timeout=timeout))


def load_json_maybe_gz(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as file:
            return json.load(file)
    return json.loads(path.read_text(encoding="utf-8"))


def route_display_name(route: dict[str, Any], name: str) -> str:
    label = ROUTE_JA_LABELS.get(str(name or ""), str(name or ""))
    operator = PHYSICAL_ALIAS_OPERATOR_LABELS.get(str(route.get("shortName") or ""))
    if not operator and route.get("operatorId") in PRIVATE_ROUTE_PREFIX_OPERATOR_IDS:
        operator = OPERATOR_JA_LABELS.get(str(route.get("operatorId") or ""))
    if operator and label and not label.startswith(operator):
        return f"{operator}{label}"
    return label


def route_title_lookup(bundle_path: Path = DEFAULT_BUNDLE) -> dict[str, dict[str, str]]:
    bundle = load_json_maybe_gz(bundle_path)
    lookup: dict[str, dict[str, str]] = {}
    for route in bundle.get("serviceRoutes", []):
        route_id = str(route.get("id") or "")
        if not route_id:
            continue
        short_name = str(route.get("shortName") or route.get("longName") or route_id)
        lookup[route_id] = {
            "short_name": short_name,
            "display_name": route_display_name(route, short_name),
        }
    return lookup


def display_leg_route_title(leg: dict[str, Any], route_titles: dict[str, dict[str, str]]) -> str:
    route = route_titles.get(str(leg.get("routeId") or ""))
    return route["display_name"] if route else str(leg.get("routeTitle") or leg.get("requestedRoute") or "路線")


def display_leg_trip_label(leg: dict[str, Any], route_titles: dict[str, dict[str, str]]) -> str:
    route = route_titles.get(str(leg.get("routeId") or ""))
    trip_label = str(leg.get("tripLabel") or leg.get("tripId") or "列車")
    if route and trip_label in {str(leg.get("routeTitle") or ""), route["short_name"]}:
        return route["display_name"]
    return trip_label


def game_trip_title_lookup(game: dict[str, Any], route_titles: dict[str, dict[str, str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for plan_key in ("runner_plan", "hunter_plan"):
        for leg in game.get(plan_key, {}).get("legs", []):
            trip_id = str(leg.get("tripId") or "")
            if trip_id:
                lookup[trip_id] = display_leg_trip_label(leg, route_titles)
    return lookup


def event_text(event: dict[str, Any], trip_titles: dict[str, str] | None = None) -> str:
    player = event.get("player_id")
    subject = {"runner": "Runner", "hunter": "Hunter"}.get(player, "Match")
    event_type = event.get("type")
    if event_type == "SCENARIO_START":
        return f"{event['time_hhmm']} 对局开始"
    if event_type == "SCENARIO_END":
        return f"{event['time_hhmm']} 对局结束"
    if event_type == "START_AT_STATION":
        station = event.get("station_label") or event.get("station_group_id")
        return f"{event['time_hhmm']} {subject} 从 {station} 出发"
    if event_type == "BOARD_TRAIN":
        station = event.get("station_label") or event.get("station_group_id")
        trip = (trip_titles or {}).get(str(event.get("trip_id") or "")) or event.get("trip_label") or event.get("trip_id")
        return f"{event['time_hhmm']} {subject} 在 {station} 上车 {trip}"
    if event_type == "ALIGHT_TRAIN":
        station = event.get("station_label") or event.get("station_group_id")
        trip = (trip_titles or {}).get(str(event.get("trip_id") or "")) or event.get("trip_label") or event.get("trip_id")
        return f"{event['time_hhmm']} {subject} 在 {station} 下车 {trip}"
    if event_type == "WAIT_UNTIL":
        station = event.get("station_label") or event.get("station_group_id")
        return f"{event['time_hhmm']} {subject} 在 {station} 等待"
    if event_type == "CAPTURE":
        detail = event.get("station_label") or event.get("trip_label") or event.get("station_group_id") or event.get("trip_id") or ""
        return f"{event['time_hhmm']} 抓捕成立 {event.get('capture_type')} {detail}".strip()
    return f"{event.get('time_hhmm', '')} {event_type}"


def format_plan(plan: dict[str, Any], route_titles: dict[str, dict[str, str]]) -> list[str]:
    lines = [f"起点: {plan['startStation']}"]
    for index, leg in enumerate(plan["legs"], start=1):
        route_title = display_leg_route_title(leg, route_titles)
        trip_label = display_leg_trip_label(leg, route_titles)
        lines.append(
            f"{index}. {route_title} / {trip_label}: "
            f"{leg['fromStation']} {leg['boardHhmm']} -> {leg['toStation']} {leg['alightHhmm']}"
        )
    return lines


def make_markdown(payload: dict[str, Any], route_titles: dict[str, dict[str, str]] | None = None) -> str:
    route_titles = route_titles or route_title_lookup()
    lines = [
        "# v3 公网对战记录",
        "",
        f"- 开始时间: {payload['run_started_at']}",
        f"- 页面: {payload['page_url']}",
        f"- 房间服务器: {payload['room_server_url']}",
        f"- 请求局数: {payload['requested_count']}",
        f"- 完成局数: {payload['completed_count']}",
        "",
    ]
    for game in payload["games"]:
        capture_display = "无" if game["capture_summary"] == "none" else game["capture_summary"]
        lines.extend(
            [
                f"## 第 {game['index']} 局: {game['scenario_name']}",
                "",
                f"- 房间: `{game['room_id']}`",
                f"- 最终在线阶段: `{game['online_phase']}`",
                f"- 抓捕结果: `{capture_display}`",
                "",
                "### Runner",
                "",
            ]
        )
        lines.extend(f"- {line}" for line in format_plan(game["runner_plan"], route_titles))
        lines.extend(["", "### Hunter", ""])
        lines.extend(f"- {line}" for line in format_plan(game["hunter_plan"], route_titles))
        lines.extend(["", "### 战况时间线", ""])
        trip_titles = game_trip_title_lookup(game, route_titles)
        for event in game["event_log"]:
            lines.append(f"- {event_text(event, trip_titles)}")
        if game.get("issues"):
            lines.extend(["", "### 问题", ""])
            lines.extend(f"- {issue}" for issue in game["issues"])
        lines.append("")
    if payload.get("failures"):
        lines.extend(["## 失败记录", ""])
        for failure in payload["failures"]:
            lines.append(f"- 第 {failure['index']} 局: {failure['error']}")
    return "\n".join(lines).rstrip() + "\n"


def capture_summary(result: dict[str, Any]) -> str:
    capture = result.get("capture")
    if not capture:
        return "无"
    if capture.get("type") == "same_node":
        station = capture.get("station_label") or capture.get("station_group_id")
        return f"same_node at {station} {capture.get('time_hhmm')}"
    if capture.get("type") == "same_train":
        trip = capture.get("trip_label") or capture.get("trip_id")
        return f"same_train on {trip} {capture.get('time_hhmm')}"
    return json.dumps(capture, ensure_ascii=False)


def run_game(
    index: int,
    scenario: dict[str, Any],
    page_url: str,
    room_server_url: str,
    log_dir: Path,
    viewport_swap: bool,
) -> dict[str, Any]:
    runner_size = (1280, 900) if not viewport_swap else (430, 900)
    hunter_size = (430, 900) if not viewport_swap else (1280, 900)
    runner = Driver(f"g{index}-runner", find_free_port(), runner_size[0], runner_size[1], log_dir)
    hunter = Driver(f"g{index}-hunter", find_free_port(), hunter_size[0], hunter_size[1], log_dir)
    try:
        runner.start()
        hunter.start()
        runner.navigate(page_url)
        hunter.navigate(page_url)
        inject_helper(runner)
        inject_helper(hunter)
        call_helper(runner, "__oniBattle.ensureReady()", timeout=120)
        call_helper(hunter, "__oniBattle.ensureReady()", timeout=120)

        created = call_helper(runner, f"__oniBattle.createRoom('runner', {json.dumps(room_server_url)})", timeout=120)
        room_id = created["roomId"]
        call_helper(hunter, f"__oniBattle.joinRoom('hunter', {json.dumps(room_id)}, {json.dumps(room_server_url)})", timeout=120)

        runner_plan_response = call_helper(
            runner,
            f"__oniBattle.planAndSubmit('runner', {json.dumps(scenario['runner'], ensure_ascii=False)})",
            timeout=120,
        )
        hunter_plan_response = call_helper(
            hunter,
            f"__oniBattle.planAndSubmit('hunter', {json.dumps(scenario['hunter'], ensure_ascii=False)})",
            timeout=120,
        )

        call_helper(runner, "__oniBattle.readySeat()", timeout=60)
        call_helper(hunter, "__oniBattle.readySeat()", timeout=60)
        call_helper(runner, "__oniBattle.waitForPhase('PLANNING', 90000)", timeout=100)
        call_helper(hunter, "__oniBattle.waitForPhase('PLANNING', 90000)", timeout=100)
        call_helper(runner, "__oniBattle.readySeat()", timeout=60)
        call_helper(hunter, "__oniBattle.readySeat()", timeout=60)
        live_snapshot = call_helper(runner, "__oniBattle.waitForPhase('LIVE', 90000)", timeout=100)
        call_helper(hunter, "__oniBattle.waitForPhase('LIVE', 90000)", timeout=100)

        runner_plan = runner_plan_response["plan"]
        hunter_plan = hunter_plan_response["plan"]
        result = unwrap_async(
            runner.execute_async(
                js_async("__oniBattle.resultForPlans(arguments[0], arguments[1], arguments[2])"),
                [f"public-v3-battle-{index:02d}-{room_id}", runner_plan, hunter_plan],
                timeout=60,
            )
        )
        issues: list[str] = []
        if live_snapshot.get("phase") != "LIVE":
            issues.append(f"Room did not reach LIVE; phase={live_snapshot.get('phase')}")
        if len(runner_plan.get("legs", [])) != len(scenario["runner"].get("legs", [])):
            issues.append("Runner resolved fewer legs than requested")
        if len(hunter_plan.get("legs", [])) != len(scenario["hunter"].get("legs", [])):
            issues.append("Hunter resolved fewer legs than requested")

        return {
            "index": index,
            "scenario_name": scenario["name"],
            "room_id": room_id,
            "viewport": {"runner": runner_size, "hunter": hunter_size},
            "online_phase": live_snapshot.get("phase"),
            "online_time": live_snapshot.get("currentTime"),
            "runner_plan": runner_plan,
            "hunter_plan": hunter_plan,
            "runner_plan_board_text": runner_plan_response.get("planBoardText"),
            "hunter_plan_board_text": hunter_plan_response.get("planBoardText"),
            "capture_summary": capture_summary(result),
            "result": result,
            "event_log": result.get("match_event_log", []),
            "issues": issues,
        }
    finally:
        runner.quit()
        hunter.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run public v3 two-browser battle experiments and record replay event data.")
    parser.add_argument("--page-url", default=DEFAULT_PAGE_URL)
    parser.add_argument("--room-server-url", default=DEFAULT_ROOM_SERVER)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument(
        "--scenario-indexes",
        default="",
        help="Comma-separated 1-based scenario indexes to run. Overrides --count when provided.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log-dir", type=Path, default=Path("/tmp/onichase-v3-public-battle-logs"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = datetime.now().astimezone()
    route_titles = route_title_lookup()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.log_dir.mkdir(parents=True, exist_ok=True)
    if args.scenario_indexes.strip():
        indexes = [int(item.strip()) for item in args.scenario_indexes.split(",") if item.strip()]
        scenarios = [SCENARIOS[index - 1] for index in indexes]
    else:
        indexes = list(range(1, min(args.count, len(SCENARIOS)) + 1))
        scenarios = SCENARIOS[: args.count]
    payload: dict[str, Any] = {
        "run_started_at": started.isoformat(timespec="seconds"),
        "page_url": args.page_url,
        "room_server_url": args.room_server_url,
        "requested_count": len(scenarios),
        "completed_count": 0,
        "games": [],
        "failures": [],
    }
    stamp = started.strftime("%Y%m%d_%H%M%S")
    json_path = args.output_dir / f"v3_public_battle_records_{stamp}.json"
    md_path = args.output_dir / f"v3_public_battle_records_{stamp}.md"

    for ordinal, (index, scenario) in enumerate(zip(indexes, scenarios), start=1):
        print(f"[{ordinal}/{len(scenarios)}] scenario {index}: {scenario['name']}", flush=True)
        try:
            game = run_game(
                index=index,
                scenario=scenario,
                page_url=args.page_url,
                room_server_url=args.room_server_url,
                log_dir=args.log_dir,
                viewport_swap=index % 2 == 0,
            )
            payload["games"].append(game)
            payload["completed_count"] = len(payload["games"])
            print(
                f"  room={game['room_id']} phase={game['online_phase']} "
                f"events={len(game['event_log'])} capture={game['capture_summary']}",
                flush=True,
            )
        except Exception as error:
            failure = {"index": index, "scenario_name": scenario["name"], "error": str(error)}
            payload["failures"].append(failure)
            print(f"  FAILED: {error}", flush=True)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        md_path.write_text(make_markdown(payload, route_titles), encoding="utf-8")

    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    if payload["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
