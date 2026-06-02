#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${CLONES_BRAIN_PYTHON:-/Users/gross/.venvs/clones-brain/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON:-python3}"
fi

export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR}"
export CLONES_BRAIN_DB="${CLONES_BRAIN_DB:-$ROOT_DIR/data/clones-brain.db}"
export CLONES_BRAIN_HOST="${CLONES_BRAIN_HOST:-127.0.0.1}"
export CLONES_BRAIN_PORT="${CLONES_BRAIN_PORT:-8765}"

mkdir -p "$ROOT_DIR/logs"

exec "$PYTHON_BIN" -m uvicorn clones_brain.server:app --host "$CLONES_BRAIN_HOST" --port "$CLONES_BRAIN_PORT"
