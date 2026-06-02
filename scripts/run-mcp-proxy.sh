#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${CLONES_BRAIN_PROXY_PYTHON:-${PYTHON:-python3}}"
export CLONES_BRAIN_URL="${CLONES_BRAIN_URL:-http://127.0.0.1:8765}"
export CLONES_BRAIN_PROXY_HOST="${CLONES_BRAIN_PROXY_HOST:-127.0.0.1}"
export CLONES_BRAIN_PROXY_PORT="${CLONES_BRAIN_PROXY_PORT:-3001}"

mkdir -p "$ROOT_DIR/logs"

exec "$PYTHON_BIN" "$ROOT_DIR/clones_brain_mcp_proxy.py"
