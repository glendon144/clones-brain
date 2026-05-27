#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${CLONES_BRAIN_BASE_URL:-http://127.0.0.1:8765}"

TITLE="${CLONES_BRAIN_TITLE:-Shell Capture}"
BODY=""
THOUGHT_TYPE="observation"
SOURCE="scripts/capture-thought.sh"
PROJECT="clones-brain"
TAGS="shell"
METADATA_JSON='{}'

usage() {
  cat <<'EOF'
Usage:
  scripts/capture-thought.sh [OPTIONS] [BODY]

Options:
  --title TITLE          Title for the thought
  --body BODY            Body text for the thought
  --type TYPE            Thought type, default: observation
  --source SOURCE        Source label, default: scripts/capture-thought.sh
  --project PROJECT      Project name, default: clones-brain
  --tags TAGS            Comma-separated tags, default: shell
  --metadata JSON        Metadata JSON object, default: {}
  --stdin                Read body from stdin
  -h, --help             Show this help

Examples:
  scripts/capture-thought.sh "A quick thought."

  scripts/capture-thought.sh \
    --title "InterBroker apprenticeship model" \
    --project "interbroker" \
    --tags "interbroker,apprenticeship,publishing" \
    --body "Inner Broker observes and questions; Outer Broker publishes only with consent."

  printf 'Long body...\n' | scripts/capture-thought.sh \
    --title "Long note" \
    --project "interbroker" \
    --tags "interbroker,notes" \
    --stdin
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)
      TITLE="${2:?Missing value for --title}"
      shift 2
      ;;
    --body)
      BODY="${2:?Missing value for --body}"
      shift 2
      ;;
    --type|--thought-type)
      THOUGHT_TYPE="${2:?Missing value for --type}"
      shift 2
      ;;
    --source)
      SOURCE="${2:?Missing value for --source}"
      shift 2
      ;;
    --project)
      PROJECT="${2:?Missing value for --project}"
      shift 2
      ;;
    --tags)
      TAGS="${2:?Missing value for --tags}"
      shift 2
      ;;
    --metadata)
      METADATA_JSON="${2:?Missing value for --metadata}"
      shift 2
      ;;
    --stdin)
      BODY="$(cat)"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ -z "$BODY" ]]; then
        BODY="$1"
      else
        BODY+=$'\n'"$1"
      fi
      shift
      ;;
  esac
done

if [[ $# -gt 0 ]]; then
  EXTRA_BODY="$*"
  if [[ -z "$BODY" ]]; then
    BODY="$EXTRA_BODY"
  else
    BODY+=$'\n'"$EXTRA_BODY"
  fi
fi

if [[ -z "${BODY//[[:space:]]/}" ]]; then
  echo "Error: body is empty. Provide BODY, --body, or --stdin." >&2
  usage >&2
  exit 2
fi

python3 - "$TITLE" "$BODY" "$THOUGHT_TYPE" "$SOURCE" "$PROJECT" "$TAGS" "$METADATA_JSON" <<'PY' | \
curl -sS "$BASE_URL/capture_thought" \
  -H 'Content-Type: application/json' \
  -d @-
import json
import sys

title, body, thought_type, source, project, tags_csv, metadata_raw = sys.argv[1:]

tags = [tag.strip() for tag in tags_csv.split(",") if tag.strip()]

try:
    metadata = json.loads(metadata_raw)
except json.JSONDecodeError as exc:
    raise SystemExit(f"Invalid --metadata JSON: {exc}")

if not isinstance(metadata, dict):
    raise SystemExit("--metadata must be a JSON object")

metadata.setdefault("script", "capture-thought.sh")

payload = {
    "title": title,
    "body": body,
    "thought_type": thought_type,
    "source": source,
    "project": project,
    "tags": tags,
    "metadata": metadata,
}

print(json.dumps(payload, ensure_ascii=False))
PY

printf '\n'
