#!/bin/sh
#
# pull_clones_brain_from_blues.sh
#
# Pull a consistent clones-brain SQLite snapshot from blues.clonesvr.com
# and install it as the local clones-brain database on macOS.
#
# Defaults assume:
#   remote: gross@blues.clonesvr.com:/home/gross/src/clones-brain/data/clones-brain.db
#   local:  $HOME/src/clones-brain/data/clones-brain.db
#
# The remote database is NOT modified or stopped.
# A SQLite backup snapshot is created remotely, copied, verified locally,
# and then installed after stopping the local launchd service.
#

set -eu

say() { printf '%s\n' "pull-clones-brain: $*"; }
die() { printf '%s\n' "pull-clones-brain: ERROR: $*" >&2; exit 1; }

REMOTE_HOST="${REMOTE_HOST:-blues.clonesvr.com}"
REMOTE_USER="${REMOTE_USER:-gross}"
REMOTE_BASE="${REMOTE_BASE:-/home/gross/src/clones-brain/data}"
REMOTE_DB="${REMOTE_DB:-${REMOTE_BASE}/clones-brain.db}"
REMOTE_SNAPSHOT="${REMOTE_SNAPSHOT:-${REMOTE_BASE}/clones-brain-transfer.db}"

LOCAL_BASE="${LOCAL_BASE:-${HOME}/src/clones-brain/data}"
LOCAL_DB="${LOCAL_DB:-${LOCAL_BASE}/clones-brain.db}"
LOCAL_INCOMING="${LOCAL_INCOMING:-${LOCAL_BASE}/clones-brain-transfer.db}"

LAUNCH_LABEL="${LAUNCH_LABEL:-com.clonesvr.cognitionos.clones-brain}"
LAUNCH_PLIST="${LAUNCH_PLIST:-${HOME}/Library/LaunchAgents/${LAUNCH_LABEL}.plist}"
DOMAIN="gui/$(id -u)"

SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"

command -v ssh >/dev/null 2>&1 || die "ssh not found"
command -v scp >/dev/null 2>&1 || die "scp not found"
command -v sqlite3 >/dev/null 2>&1 || die "local sqlite3 not found"

mkdir -p "${LOCAL_BASE}"

say "checking remote database on ${SSH_TARGET}"
ssh "${SSH_TARGET}" "test -f '${REMOTE_DB}'" \
    || die "remote database not found at ${REMOTE_DB}"

say "creating consistent SQLite snapshot on blues"

ssh "${SSH_TARGET}" \
    REMOTE_DB="${REMOTE_DB}" \
    REMOTE_SNAPSHOT="${REMOTE_SNAPSHOT}" \
    'sh -s' <<'REMOTE'
set -eu

if command -v sqlite3 >/dev/null 2>&1; then
    rm -f "${REMOTE_SNAPSHOT}"
    sqlite3 "${REMOTE_DB}" ".backup '${REMOTE_SNAPSHOT}'"
else
    PY=$(command -v python3 || command -v python || true)
    [ -n "${PY}" ] || {
        echo "Neither sqlite3 nor Python is available remotely." >&2
        exit 1
    }

    rm -f "${REMOTE_SNAPSHOT}"
    REMOTE_DB="${REMOTE_DB}" REMOTE_SNAPSHOT="${REMOTE_SNAPSHOT}" "${PY}" - <<'PY'
import os
import sqlite3

src_path = os.environ["REMOTE_DB"]
dst_path = os.environ["REMOTE_SNAPSHOT"]

src = sqlite3.connect(src_path)
dst = sqlite3.connect(dst_path)

try:
    src.backup(dst)
finally:
    dst.close()
    src.close()
PY
fi

test -s "${REMOTE_SNAPSHOT}"
REMOTE

say "copying snapshot to ${LOCAL_INCOMING}"
rm -f "${LOCAL_INCOMING}"
scp "${SSH_TARGET}:${REMOTE_SNAPSHOT}" "${LOCAL_INCOMING}"

say "checking downloaded database integrity"
integrity="$(sqlite3 "${LOCAL_INCOMING}" 'PRAGMA integrity_check;')"
[ "${integrity}" = "ok" ] || die "SQLite integrity check failed: ${integrity}"
say "integrity check: ok"

remote_count="$(ssh "${SSH_TARGET}" "
if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 '${REMOTE_SNAPSHOT}' 'SELECT count(*) FROM thoughts;' 2>/dev/null || true
fi
")"

local_count="$(sqlite3 "${LOCAL_INCOMING}" 'SELECT count(*) FROM thoughts;' 2>/dev/null || true)"

if [ -n "${remote_count}" ]; then
    say "remote snapshot thought count: ${remote_count}"
fi
if [ -n "${local_count}" ]; then
    say "downloaded thought count: ${local_count}"
fi

if [ -f "${LAUNCH_PLIST}" ]; then
    say "stopping local clones-brain LaunchAgent"
    launchctl bootout "${DOMAIN}" "${LAUNCH_PLIST}" >/dev/null 2>&1 || true
else
    say "warning: LaunchAgent plist not found at ${LAUNCH_PLIST}"
fi

stamp="$(date +%Y%m%d-%H%M%S)"

if [ -f "${LOCAL_DB}" ]; then
    backup="${LOCAL_DB}.before-blues-${stamp}"
    say "preserving current local database as ${backup}"
    cp -p "${LOCAL_DB}" "${backup}"
fi

rm -f "${LOCAL_DB}-wal" "${LOCAL_DB}-shm"

say "installing snapshot as ${LOCAL_DB}"
mv "${LOCAL_INCOMING}" "${LOCAL_DB}"

if [ -f "${LAUNCH_PLIST}" ]; then
    say "starting local clones-brain LaunchAgent"
    launchctl bootstrap "${DOMAIN}" "${LAUNCH_PLIST}"
    launchctl enable "${DOMAIN}/${LAUNCH_LABEL}" >/dev/null 2>&1 || true
    launchctl kickstart -k "${DOMAIN}/${LAUNCH_LABEL}"
fi

say "waiting for local clones-brain health"
tmp_health="/tmp/clones-brain-health.$$"
tries=0
while [ "${tries}" -lt 15 ]; do
    if curl -fsS --max-time 2 http://127.0.0.1:8765/health >"${tmp_health}" 2>/dev/null; then
        cat "${tmp_health}"
        rm -f "${tmp_health}"
        printf '\n'
        say "local clones-brain is healthy"
        break
    fi
    tries=$((tries + 1))
    sleep 1
done

if [ "${tries}" -ge 15 ]; then
    rm -f "${tmp_health}" 2>/dev/null || true
    die "local clones-brain did not become healthy"
fi

say "cleaning up remote transfer snapshot"
ssh "${SSH_TARGET}" "rm -f '${REMOTE_SNAPSHOT}'" || \
    say "warning: could not remove remote transfer snapshot"

say "done"
