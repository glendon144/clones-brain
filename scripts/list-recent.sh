#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${CLONES_BRAIN_BASE_URL:-http://127.0.0.1:8765}"
LIMIT="${1:-20}"

curl -sS "$BASE_URL/list_recent?limit=$LIMIT"
printf '\n'
