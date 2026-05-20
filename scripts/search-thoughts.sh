#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${CLONES_BRAIN_BASE_URL:-http://127.0.0.1:8765}"
QUERY="${1:-sample}"
LIMIT="${2:-10}"

curl -sS "$BASE_URL/search_thoughts" \
  -H 'Content-Type: application/json' \
  -d @- <<JSON
{
  "query": "$QUERY",
  "limit": $LIMIT
}
JSON
printf '\n'
