#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="${CLONES_BRAIN_DB:-$ROOT_DIR/data/clones-brain.db}"
SCHEMA_PATH="${CLONES_BRAIN_SCHEMA:-$ROOT_DIR/schema.sql}"
PYTHON_BIN="${CLONES_BRAIN_PYTHON:-/home/gross/.venvs/clones-brain/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON:-python3}"
fi
export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR}"

mkdir -p "$(dirname "$DB_PATH")"
"$PYTHON_BIN" - <<PY
from pathlib import Path
from clones_brain.db import init_db
init_db(schema_path=Path(r'''$SCHEMA_PATH'''), db_path=Path(r'''$DB_PATH'''))
print(f"initialized {Path(r'''$DB_PATH''')}")
PY
