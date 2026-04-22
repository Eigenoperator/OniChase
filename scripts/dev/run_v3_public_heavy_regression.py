#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.run_v3_public_battle_records import DEFAULT_OUTPUT_DIR, DEFAULT_PAGE_URL, DEFAULT_ROOM_SERVER


DEFAULT_LOG_DIR = Path("/tmp/onichase-v3-heavy-regression-logs")


def run_command(command: list[str]) -> str:
    print("+ " + " ".join(command), flush=True)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert process.stdout is not None
    lines: list[str] = []
    for line in process.stdout:
        print(line, end="", flush=True)
        lines.append(line)
    code = process.wait()
    output = "".join(lines)
    if code:
        raise RuntimeError(f"command failed with exit code {code}: {' '.join(command)}")
    return output


def extract_json_path(output: str) -> Path:
    for line in reversed(output.splitlines()):
        if line.startswith("JSON: "):
            return Path(line.split("JSON: ", 1)[1].strip())
    raise RuntimeError("battle-record command did not print a JSON path")


def validate_records(records_path: Path, min_legs: int) -> dict[str, object]:
    payload = json.loads(records_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    requested = int(payload.get("requested_count") or 0)
    completed = int(payload.get("completed_count") or 0)
    failures = payload.get("failures") or []
    if completed != requested:
        errors.append(f"completed_count {completed} != requested_count {requested}")
    if failures:
        errors.append(f"{len(failures)} failures recorded")
    for game in payload.get("games", []):
        index = game.get("index")
        runner_legs = len(game.get("runner_plan", {}).get("legs", []))
        hunter_legs = len(game.get("hunter_plan", {}).get("legs", []))
        if runner_legs < min_legs:
            errors.append(f"game {index}: runner has {runner_legs} legs < {min_legs}")
        if hunter_legs < min_legs:
            errors.append(f"game {index}: hunter has {hunter_legs} legs < {min_legs}")
        if game.get("issues"):
            errors.append(f"game {index}: issues={game['issues']}")
        expected_capture = game.get("expected_capture")
        actual_capture = (game.get("result", {}).get("capture") or {}).get("type") or "none"
        if expected_capture and expected_capture != actual_capture:
            errors.append(f"game {index}: expected capture {expected_capture}, got {actual_capture}")
        if game.get("online_phase") not in {"LIVE", "ENDED"}:
            errors.append(f"game {index}: online phase {game.get('online_phase')}")
    if errors:
        print("heavy regression validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    return {
        "requested": requested,
        "completed": completed,
        "rooms": [game.get("room_id") for game in payload.get("games", [])],
    }


def sibling_markdown(records_path: Path) -> Path:
    return records_path.with_suffix(".md")


def default_timeline_dir(records_path: Path) -> Path:
    stem = records_path.stem.replace("v3_public_battle_records_", "v3_battle_timelines_")
    return records_path.parent / stem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or validate the v3 public heavy battle regression suite.")
    parser.add_argument("--records", type=Path, help="Validate/render an existing records JSON instead of running new browser games.")
    parser.add_argument("--page-url", default=DEFAULT_PAGE_URL)
    parser.add_argument("--room-server-url", default=DEFAULT_ROOM_SERVER)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--min-legs", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--timeline-dir", type=Path)
    parser.add_argument("--skip-render", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"v3 heavy regression started at {started}", flush=True)
    if args.records:
        records_path = args.records
    else:
        output = run_command(
            [
                sys.executable,
                "scripts/dev/run_v3_public_battle_records.py",
                "--mode",
                "heavy",
                "--count",
                str(args.count),
                "--page-url",
                args.page_url,
                "--room-server-url",
                args.room_server_url,
                "--output-dir",
                str(args.output_dir),
                "--log-dir",
                str(args.log_dir),
            ]
        )
        records_path = extract_json_path(output)

    summary = validate_records(records_path, args.min_legs)
    timeline_dir = args.timeline_dir or default_timeline_dir(records_path)
    if not args.skip_render:
        run_command(
            [
                sys.executable,
                "scripts/dev/render_v3_battle_timeline.py",
                "--records",
                str(records_path),
                "--output-dir",
                str(timeline_dir),
                "--game",
                "all",
            ]
        )
    audit_surfaces = [sibling_markdown(records_path)]
    if not args.skip_render:
        audit_surfaces.append(timeline_dir)
    run_command(
        [
            sys.executable,
            "scripts/dev/audit_v3_display_names.py",
            *[item for surface in audit_surfaces for item in ("--surface", str(surface))],
        ]
    )
    print(
        "v3 heavy regression passed: "
        f"{summary['completed']}/{summary['requested']} games, records={records_path}, timelines={timeline_dir}",
        flush=True,
    )


if __name__ == "__main__":
    main()
