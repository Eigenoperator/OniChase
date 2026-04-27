#!/usr/bin/env python3

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI_DIR = ROOT / "ui"
DOCS_DIR = ROOT / "docs"
DOCS_DATA_DIR = DOCS_DIR / "data"
NOJEKYLL = DOCS_DIR / ".nojekyll"

V1_SOURCE_HTML = UI_DIR / "web_client.html"
V2_SOURCE_HTML = UI_DIR / "v2_web_client.html"
V3_MAPLIBRE_SOURCE_HTML = DOCS_DIR / "v3.html"
V4_MAPLIBRE_SOURCE_HTML = DOCS_DIR / "v4.html"
V3_LOCAL_MIRROR_HTML = UI_DIR / "v3_maplibre.html"
INDEX_HTML = DOCS_DIR / "index.html"
V1_TARGET_HTML = DOCS_DIR / "v1.html"
V2_TARGET_HTML = DOCS_DIR / "v2.html"
V3_TARGET_HTML = DOCS_DIR / "v3.html"
V4_TARGET_HTML = DOCS_DIR / "v4.html"

DATA_FILES = [
    ROOT / "data" / "yamanote_stations.json",
    ROOT / "data" / "yamanote_weekday_train_instances_merged.json",
    ROOT / "data" / "shinkansen_v2_bundle.json",
    ROOT / "data" / "shinkansen_v2_weekday_train_instances_merged.json",
    ROOT / "data" / "v3_tokyo_phase1_service_views.json",
    ROOT / "data" / "v3_train_manifest.json",
    ROOT / "data" / "v3_trains_unified.json.gz",
    ROOT / "data" / "v3_station_departures.json.gz",
    ROOT / "data" / "v3_tokyo_bundle.json.gz",
    ROOT / "data" / "v3_tokyo_map_bundle.json.gz",
    ROOT / "data" / "v3_tokyo_timetable_bundle.json.gz",
    ROOT / "data" / "v3_tokyo_timetable_compact.json.gz",
    ROOT / "data" / "v4_gameplay_map_bundle.json.gz",
    ROOT / "data" / "v4_gameplay_timetable_bundle.json.gz",
    ROOT / "data" / "v4_gameplay_timetable_compact.json.gz",
    ROOT / "data" / "v4_gameplay_manifest.json",
]


def build_landing_page() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>OniChase</title>
  <style>
    :root {
      --bg: #f4eee2;
      --ink: #1f2933;
      --muted: #687382;
      --line: #d9cfbd;
      --panel: rgba(255, 251, 244, 0.94);
      --shadow: 0 20px 52px rgba(31, 41, 51, 0.12);
      --shadow-soft: 0 12px 28px rgba(31, 41, 51, 0.08);
      --v1: #80c241;
      --v2: #cc8b2c;
      --v3: #1565c0;
      --v4: #0f766e;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 14% 14%, rgba(128, 194, 65, 0.18), transparent 24%),
        radial-gradient(circle at 84% 16%, rgba(204, 139, 44, 0.14), transparent 22%),
        linear-gradient(180deg, #fbf8f2 0%, var(--bg) 100%);
    }
    .page {
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 32px;
    }
    .shell {
      width: min(1120px, 100%);
      display: grid;
      gap: 22px;
    }
    .hero {
      border: 1px solid rgba(217, 207, 189, 0.95);
      border-radius: 32px;
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 32px;
    }
    .hero h1 {
      margin: 0;
      font-size: 48px;
      letter-spacing: 0.04em;
    }
    .hero p {
      margin: 10px 0 0;
      max-width: 780px;
      font-size: 16px;
      line-height: 1.6;
      color: var(--muted);
    }
    .cards {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 22px;
    }
    .card {
      border: 1px solid rgba(217, 207, 189, 0.95);
      border-radius: 28px;
      background: var(--panel);
      box-shadow: var(--shadow-soft);
      padding: 26px;
      display: grid;
      gap: 16px;
    }
    .eyebrow {
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }
    .card.v1 .eyebrow { color: var(--v1); }
    .card.v2 .eyebrow { color: var(--v2); }
    .card.v3 .eyebrow { color: var(--v3); }
    .card.v4 .eyebrow { color: var(--v4); }
    .card h2 {
      margin: 0;
      font-size: 30px;
    }
    .card p {
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }
    .meta {
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.5;
    }
    .actions {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }
    a.button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 150px;
      padding: 13px 16px;
      border-radius: 14px;
      text-decoration: none;
      font-weight: 800;
      color: #1f2933;
      box-shadow: var(--shadow-soft);
    }
    .card.v1 a.button { background: #dff1c4; }
    .card.v2 a.button { background: #f6dfba; }
    .card.v3 a.button { background: #d8e7fb; }
    .card.v4 a.button { background: #cdece7; }
    @media (max-width: 900px) {
      .cards { grid-template-columns: 1fr; }
      .hero h1 { font-size: 38px; }
    }
  </style>
</head>
<body>
  <main class="page">
    <div class="shell">
      <section class="hero">
        <h1>OniChase</h1>
        <p>Choose a version. <strong>V1</strong> is the archived Yamanote prototype. <strong>V2</strong> is the current playable nationwide Shinkansen build. <strong>V3</strong> is the official Tokyo MapLibre gameplay release candidate. <strong>V4</strong> brings the same gameplay shell to the nationwide real railway map.</p>
      </section>
      <section class="cards">
        <article class="card v1">
          <div class="eyebrow">V1</div>
          <h2>Yamanote Line</h2>
          <p>Single-line, round-loop prototype. Best for validating the core chase loop, planning flow, hunter information rules, and capture timing.</p>
          <div class="meta">
            <div>Map: Yamanote line</div>
            <div>Scope: real weekday loop timetable</div>
            <div>Play style: compact and readable</div>
          </div>
          <div class="actions">
            <a class="button" href="./v1.html">Open V1</a>
          </div>
        </article>
        <article class="card v2">
          <div class="eyebrow">V2</div>
          <h2>GIS Shinkansen</h2>
          <p>Main nationwide Shinkansen playable build. Uses the stronger GIS-first map, route diagram, planning flow, simulation, capture, and replay on one page.</p>
          <div class="meta">
            <div>Map: nationwide Shinkansen</div>
            <div>Scope: GIS-first + real weekday train instances</div>
            <div>Play style: large-scale route planning and replay</div>
          </div>
          <div class="actions">
            <a class="button" href="./v2.html">Open V2</a>
          </div>
        </article>
        <article class="card v3">
          <div class="eyebrow">V3</div>
          <h2>Tokyo MapLibre</h2>
          <p>Official v3 Tokyo urban rail map with WebGL rendering, collision-aware labels, official line colors, real geometry, and lazy timetable-linked departures.</p>
          <div class="meta">
            <div>Map: Tokyo urban rail</div>
            <div>Scope: MapLibre + real geometry + real train departures</div>
            <div>Use: inspect the current v3 map-data linkage</div>
          </div>
          <div class="actions">
            <a class="button" href="./v3.html">Open V3</a>
          </div>
        </article>
        <article class="card v4">
          <div class="eyebrow">V4</div>
          <h2>Japan Gameplay</h2>
          <p>Nationwide real physical railway substrate with station identity v2, MapLibre layers, real weekday timetable data, and the v3 single/multiplayer planning loop.</p>
          <div class="meta">
            <div>Map: all-Japan physical rail geometry</div>
            <div>Scope: 21,932 track centerlines, 10,239 physical stations, 122,263 trips</div>
            <div>Use: single-player or two-player room playtest</div>
          </div>
          <div class="actions">
            <a class="button" href="./v4.html">Open V4</a>
          </div>
        </article>
      </section>
    </div>
  </main>
</body>
</html>
"""


def build() -> None:
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    v1_html = V1_SOURCE_HTML.read_text(encoding="utf-8").replace("__DATA_BASE__", "./data")
    v2_html = V2_SOURCE_HTML.read_text(encoding="utf-8").replace("__DATA_BASE__", "./data")
    v3_html = V3_MAPLIBRE_SOURCE_HTML.read_text(encoding="utf-8")
    v4_html = V4_MAPLIBRE_SOURCE_HTML.read_text(encoding="utf-8")
    INDEX_HTML.write_text(build_landing_page(), encoding="utf-8")
    V1_TARGET_HTML.write_text(v1_html, encoding="utf-8")
    V2_TARGET_HTML.write_text(v2_html, encoding="utf-8")
    V3_TARGET_HTML.write_text(v3_html, encoding="utf-8")
    V4_TARGET_HTML.write_text(v4_html, encoding="utf-8")
    V3_LOCAL_MIRROR_HTML.write_text(v3_html, encoding="utf-8")
    old_v3_maplibre = DOCS_DIR / "v3_maplibre.html"
    if old_v3_maplibre.exists():
        old_v3_maplibre.unlink()
    NOJEKYLL.write_text("", encoding="utf-8")
    for path in DATA_FILES:
        shutil.copy2(path, DOCS_DATA_DIR / path.name)


if __name__ == "__main__":
    build()
