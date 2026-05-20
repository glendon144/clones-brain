#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${CLONES_BRAIN_PYTHON:-/home/gross/.venvs/clones-brain/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON:-python3}"
fi
export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR}"
export CLONES_BRAIN_DB="${CLONES_BRAIN_DB:-$ROOT_DIR/data/clones-brain.db}"

"$PYTHON_BIN" - <<'PY'
from clones_brain.migration import migrate_from_openbrain
summary = migrate_from_openbrain()
print(f"records seen: {summary.records_seen}")
print(f"records imported: {summary.records_imported}")
print(f"records skipped as duplicates: {summary.records_skipped}")
print(f"errors: {len(summary.errors)}")
for error in summary.errors:
    print(f"- {error}")
print(f"raw export: {summary.raw_export_path}")
raise SystemExit(0 if summary.ok else 1)
PY
