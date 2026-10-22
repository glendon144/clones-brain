#!/bin/sh
#
# find_clones_brain_hosts.sh
#
# Probe likely Tailscale hosts for a running Clones Brain service and/or
# an existing clones-brain SQLite database.
#
# Usage:
#   ./find_clones_brain_hosts.sh
#   HOSTS="jazz m2 inspiron blues" ./find_clones_brain_hosts.sh
#
# Optional:
#   REMOTE_USER=gross
#

set -u

REMOTE_USER="${REMOTE_USER:-gross}"
HOSTS="${HOSTS:-jazz m2 inspiron blues}"

probe_host()
{
    host="$1"
    target="${REMOTE_USER}@${host}"

    echo
    echo "============================================================"
    echo "HOST: ${host}"
    echo "============================================================"

    if ! ssh -o BatchMode=yes -o ConnectTimeout=6 "${target}" 'printf ok' >/dev/null 2>&1; then
        echo "SSH: unavailable or key auth failed"
        return
    fi

    echo "SSH: reachable"

    ssh -o BatchMode=yes -o ConnectTimeout=6 "${target}" 'sh -s' <<'REMOTE'
echo
echo "--- hostname ---"
hostname 2>/dev/null || true

echo
echo "--- Clones Brain health on localhost:8765 ---"
if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 3 http://127.0.0.1:8765/health 2>/dev/null || echo "no HTTP response"
elif command -v ftp >/dev/null 2>&1; then
    ftp -q 2 -o - http://127.0.0.1:8765/health 2>/dev/null || echo "no HTTP response"
else
    echo "curl/ftp unavailable"
fi

echo
echo "--- listeners on port 8765 ---"
if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:8765 -sTCP:LISTEN 2>/dev/null || echo "no listener found"
elif command -v sockstat >/dev/null 2>&1; then
    sockstat -4 -6 -l 2>/dev/null | grep 8765 || echo "no listener found"
elif command -v netstat >/dev/null 2>&1; then
    netstat -an 2>/dev/null | grep '[.:]8765 ' || echo "no listener found"
else
    echo "no supported listener tool found"
fi

echo
echo "--- likely Clones Brain processes ---"
ps auxww 2>/dev/null | grep -E '[c]lones[_-]brain|[u]vicorn.*8765|[u]vicorn.*clones_brain' || echo "no matching process found"

echo
echo "--- likely database files ---"
for root in "$HOME" /home/gross /Users/gross; do
    [ -d "$root" ] || continue
    find "$root" -type f \( \
        -name 'clones-brain.db' -o \
        -name 'clones_brain.db' -o \
        -name '*clones*brain*.db' -o \
        -name '*clones*brain*.sqlite' -o \
        -name '*clones*brain*.sqlite3' \
    \) 2>/dev/null
done | sort -u

echo
echo "--- CLONES_BRAIN_DB configuration references ---"
for root in "$HOME/src" "$HOME/open-brain" /home/gross/src /Users/gross/src; do
    [ -d "$root" ] || continue
    grep -R -n -m 20 'CLONES_BRAIN_DB' "$root" 2>/dev/null
done | head -50

echo
echo "--- candidate DB thought counts ---"
for root in "$HOME" /home/gross /Users/gross; do
    [ -d "$root" ] || continue
    find "$root" -type f \( \
        -name 'clones-brain.db' -o \
        -name 'clones_brain.db' -o \
        -name '*clones*brain*.db' \
    \) 2>/dev/null
done | sort -u | while IFS= read -r db; do
    [ -n "$db" ] || continue
    printf '%s : ' "$db"

    if command -v sqlite3 >/dev/null 2>&1; then
        count=$(sqlite3 "$db" 'SELECT count(*) FROM thoughts;' 2>/dev/null)
        if [ -n "$count" ]; then
            echo "$count thoughts"
        else
            echo "SQLite file, but no readable thoughts table"
        fi
    elif command -v python3 >/dev/null 2>&1; then
        DB_PATH="$db" python3 - <<'PY'
import os, sqlite3
p = os.environ["DB_PATH"]
try:
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    cur = con.execute("SELECT count(*) FROM thoughts")
    print(f"{cur.fetchone()[0]} thoughts")
except Exception as e:
    print(f"unreadable/no thoughts table: {e}")
finally:
    try: con.close()
    except: pass
PY
    else
        echo "found, but sqlite3/python3 unavailable to count"
    fi
done
REMOTE
}

for host in ${HOSTS}; do
    probe_host "$host"
done
