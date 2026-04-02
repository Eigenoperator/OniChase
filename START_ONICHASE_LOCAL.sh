#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

LOG_FILE="${ROOT_DIR}/.onichase-launch.log"

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Launching OniChase local client..."
  echo "Root: $ROOT_DIR"
  python3 scripts/dev/run_local_site.py --page ui/planner.html
} >>"$LOG_FILE" 2>&1
