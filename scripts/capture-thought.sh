#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${CLONES_BRAIN_BASE_URL:-http://127.0.0.1:8765}"
BODY="${1:-This is a sample clones-brain thought captured from the shell.}"
TITLE="${CLONES_BRAIN_TITLE:-Shell Capture}"

curl -sS "$BASE_URL/capture_thought" \
  -H 'Content-Type: application/json' \
  -d @- <<JSON
{
  "title": "$TITLE",
  "body": "$BODY",
  "thought_type": "observation",
  "source": "scripts/capture-thought.sh",
  "project": "clones-brain",
  "tags": ["shell", "sample"],
  "metadata": {"script": "capture-thought.sh"}
}
JSON
printf '\n'
