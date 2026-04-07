#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
python3 scripts/engine/v2_online_room_server.py "$@"
