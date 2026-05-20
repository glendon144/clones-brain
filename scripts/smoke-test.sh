#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
DB_PATH="$TMP_DIR/smoke.db"
LOG_PATH="$TMP_DIR/server.log"
PORT="18765"
PYTHON_BIN="${CLONES_BRAIN_PYTHON:-/home/gross/.venvs/clones-brain/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON:-python3}"
fi
export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR}"
export CLONES_BRAIN_DB="$DB_PATH"
export CLONES_BRAIN_PORT="$PORT"
export CLONES_BRAIN_HOST="127.0.0.1"
trap 'if [[ -n "${SERVER_PID:-}" ]]; then kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; fi; rm -rf "$TMP_DIR"' EXIT

"$ROOT_DIR/scripts/init-db.sh" >/dev/null
"$PYTHON_BIN" -m uvicorn clones_brain.server:app --host 127.0.0.1 --port "$PORT" >"$LOG_PATH" 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 30); do
  if curl -sS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

curl -sS "http://127.0.0.1:$PORT/capture_thought" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Smoke","body":"Smoke test thought for clones-brain search","tags":["smoke"]}' >/dev/null

SEARCH_OUTPUT="$(curl -sS "http://127.0.0.1:$PORT/search_thoughts" -H 'Content-Type: application/json' -d '{"query":"Smoke test thought","limit":5}')"
SEARCH_OUTPUT="$SEARCH_OUTPUT" "$PYTHON_BIN" - <<'PY'
import json
import os
payload = json.loads(os.environ["SEARCH_OUTPUT"])
thoughts = payload.get("thoughts") or []
if not thoughts:
    raise SystemExit("search returned no thoughts")
if "Smoke test thought" not in thoughts[0].get("body", ""):
    raise SystemExit("expected captured thought missing from search")
print("smoke test passed")
PY
