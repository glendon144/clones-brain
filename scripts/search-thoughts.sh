#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${CLONES_BRAIN_BASE_URL:-http://127.0.0.1:8765}"
QUERY="${1:-sample}"
LIMIT="${2:-10}"

PAYLOAD="$(
python3 - "$QUERY" "$LIMIT" <<'PYJSON'
import json
import sys

query, limit_raw = sys.argv[1:]

try:
    limit = int(limit_raw)
except ValueError:
    raise SystemExit(f"Invalid limit: {limit_raw!r}")

print(json.dumps({"query": query, "limit": limit}, ensure_ascii=False))
PYJSON
)"

curl -sS "$BASE_URL/search_thoughts" \
  -H 'Content-Type: application/json' \
  -d "$PAYLOAD"
printf '\n'
