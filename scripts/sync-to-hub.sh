#!/usr/bin/env bash
# One-way push: this host's clones-brain -> a hub node's clones-brain.
#
# Why this exists: clones-brain instances are loopback-only and independent.
# Captures land only on whichever host the agent happened to run on, so the
# hub node (blues) silently stopped receiving anything on 2026-07-04 while
# m2 kept accumulating. Nothing was broken -- no propagation had ever been
# built. This is that missing piece.
#
# Safe to run repeatedly. The hub's import_bundle dedups via thought_exists()
# on external_id, then (title, body, created_at), then (title, body), so
# re-running only ever adds what is genuinely missing. Imports do not re-enqueue
# for sync and embeddings are disabled server-side, so this is cheap.
#
# One-way by design: the hub accumulates, local stores are never modified.
#
#   ./sync-to-hub.sh              # push to the default hub (blues)
#   ./sync-to-hub.sh --dry-run    # show what would be pushed, change nothing
#   CLONES_BRAIN_HUB_SSH=jazz ./sync-to-hub.sh
set -euo pipefail

LOCAL_URL="${CLONES_BRAIN_BASE_URL:-http://127.0.0.1:8765}"
HUB_SSH="${CLONES_BRAIN_HUB_SSH:-blues}"
HUB_URL="${CLONES_BRAIN_HUB_URL:-http://127.0.0.1:8765}"
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

HOST_TAG="$(hostname -s)"
export HOST_TAG

echo "local: $LOCAL_URL"
echo "hub:   $HUB_SSH ($HUB_URL)"

if ! curl -sS -m 10 -o /dev/null "$LOCAL_URL/health"; then
  echo "ERROR: local clones-brain is not reachable at $LOCAL_URL" >&2
  exit 1
fi

hub_before="$(ssh -o BatchMode=yes "$HUB_SSH" "curl -sS -m 10 '$HUB_URL/health'" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["thought_count"])')" || {
  echo "ERROR: hub clones-brain is not reachable via $HUB_SSH" >&2
  exit 1
}

# Stamp external_id as "<host>:<local id>" so provenance survives the hop and
# re-runs dedup exactly even if a title is later reused. The local `id` itself
# is dropped: ids are per-node and meaningless on the hub.
payload="$(curl -sS -m 120 "$LOCAL_URL/export_bundle" | python3 -c '
import json, os, sys

tag = os.environ["HOST_TAG"]
bundle = json.load(sys.stdin)
out = []
for t in bundle.get("thoughts", []):
    local_id = t.pop("id", None)
    if not t.get("external_id") and local_id is not None:
        t["external_id"] = f"{tag}:{local_id}"
    out.append(t)
json.dump({"thoughts": out}, sys.stdout)
')"

count="$(printf '%s' "$payload" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["thoughts"]))')"
echo "local thoughts: $count"
echo "hub thoughts before: $hub_before"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "(dry run -- nothing sent)"
  exit 0
fi

printf '%s' "$payload" | ssh -o BatchMode=yes "$HUB_SSH" \
  "curl -sS -m 600 -X POST '$HUB_URL/import_bundle' -H 'Content-Type: application/json' -d @-" \
  | python3 -c '
import json, sys
r = json.load(sys.stdin)
print("imported:", r.get("imported"), " skipped:", r.get("skipped"))
errs = r.get("errors") or []
if errs:
    print("errors:", len(errs))
    for e in errs[:5]:
        print("  ", e)
    sys.exit(1)
'

hub_after="$(ssh -o BatchMode=yes "$HUB_SSH" "curl -sS -m 10 '$HUB_URL/health'" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["thought_count"])')"
echo "hub thoughts after: $hub_after"
