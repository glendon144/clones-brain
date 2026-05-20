# clones-brain

`clones-brain` is a local-first memory service for capturing, searching, recovering, exporting, and migrating thoughts without relying on Supabase as the canonical store.

Local memory is the master tape; cloud services are only radio towers.

## Why local-first

The existing hosted OpenBrain service is useful as a remote endpoint, but it should not be the only copy of memory. `clones-brain` keeps SQLite on disk as the source of truth and treats hosted services as optional import or sync targets.

## Project layout

```text
clones-brain/
  README.md
  requirements.txt
  schema.sql
  clones_brain/
  scripts/
  data/
  exports/
  logs/
```

The default database path is `data/clones-brain.db`.

## Setup

```bash
cd /home/gross/open-brain/clones-brain
python3 -m venv /home/gross/.venvs/clones-brain
source /home/gross/.venvs/clones-brain/bin/activate
pip install -r requirements.txt
scripts/init-db.sh
```

You can also point the service at another database:

```bash
export CLONES_BRAIN_DB=/path/to/other.db
scripts/init-db.sh
```

## Run the server

```bash
scripts/run-server.sh
```

The server binds to `127.0.0.1:8765` by default.

## Endpoints

### Health

```bash
curl -s http://127.0.0.1:8765/health | jq
```

### Capture a thought

```bash
curl -s http://127.0.0.1:8765/capture_thought \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Disk note",
    "body": "Optiplex has plenty of free disk space.",
    "thought_type": "observation",
    "source": "manual",
    "project": "clones-brain",
    "tags": ["ops", "optiplex"],
    "metadata": {"host": "optiplex"}
  }' | jq
```

### List recent thoughts

```bash
curl -s 'http://127.0.0.1:8765/list_recent?limit=20' | jq
```

### Search thoughts

```bash
curl -s http://127.0.0.1:8765/search_thoughts \
  -H 'Content-Type: application/json' \
  -d '{"query": "disk space optiplex", "limit": 10}' | jq
```

### Recover context

```bash
curl -s http://127.0.0.1:8765/recover_context \
  -H 'Content-Type: application/json' \
  -d '{"query": "optiplex status", "limit": 10, "max_chars": 12000}' | jq
```

### Export and import

```bash
curl -s http://127.0.0.1:8765/export_bundle > exports/local-backup.json
curl -s http://127.0.0.1:8765/import_bundle \
  -H 'Content-Type: application/json' \
  --data @exports/local-backup.json | jq
```

## Search behavior

Search prefers SQLite FTS5 and falls back to `LIKE` queries if FTS5 is unavailable. Embeddings are optional and disabled by default.

## Migration from hosted OpenBrain

The migration tool uses the hosted OpenBrain HTTP/MCP-style API rather than Supabase internals.

```bash
export OPENBRAIN_BASE_URL='https://lylmeseyluezpvclnllt.supabase.co/functions/v1/open-brain-mcp'
export OPENBRAIN_API_KEY="$(cat /home/gross/open-brain/claude_mcp_token)"
scripts/migrate-from-openbrain.sh
```

The migration code is defensive because deployed OpenBrain instances may expose different shapes. It currently tries these strategies in order:

1. JSON-RPC `tools/call` to `list_thoughts`
2. Broad search-style calls such as `search_thoughts` and `recover_context`
3. Direct REST-style paths like `/list_recent`, `/export_bundle`, `/search_thoughts`, and `/recover_context`

Raw responses are written to `exports/openbrain-migration-raw-YYYYMMDD-HHMMSS.json`. The importer normalizes records and skips duplicates by `external_id` or by title/body/timestamp fingerprints.

### Rehearsal notes

Two rehearsal imports have already been exercised locally:

- A 10-record hosted OpenBrain import rehearsal saved to `exports/openbrain-rehearsal-raw-20260520-143954.json`
- A Dream Server selective rehearsal that saved per-query raw exports under `exports/openbrain-selective-*-20260520-145106.json`

The current hosted OpenBrain APIs still return human-formatted SSE text blocks for some read paths. `clones-brain` therefore preserves hosted provenance in local `metadata` and skips duplicates using the local content-and-timestamp guard when stable hosted IDs are unavailable.

### recover_context normalization

`recover_context` now normalizes natural-language questions into durable search terms before falling back. For example, `What is the Dream Server and how does recover_context work?` is reduced to a keyword query that can still hit FTS5-backed local records.

### Expected response shapes

The migration layer understands these common shapes:

- `{"thoughts": [...]}`
- `{"contexts": [...]}`
- `{"items": [...]}`
- JSON-RPC results with `result.content[].text` containing newline-delimited summaries
- Bundles with a top-level `records` or `data` array

Some hosted OpenBrain deployments may only expose MCP tool responses formatted for humans. Those cases are marked with `TODO` comments in the code and may need endpoint-specific refinement after observing the real payloads.

## Cron heartbeat example

A local heartbeat can keep activity flowing into both services if you want to dual-write:

```cron
17 6 * * * /home/gross/open-brain/supabase/scripts/openbrain-heartbeat.sh
```

You can point that script or a similar one at `clones-brain` locally by POSTing to `/capture_thought`.

## Backup advice

SQLite makes backups simple:

```bash
cp data/clones-brain.db exports/clones-brain-$(date +%Y%m%d-%H%M%S).db
curl -s http://127.0.0.1:8765/export_bundle > exports/clones-brain-$(date +%Y%m%d-%H%M%S).json
```

Keep both filesystem-level DB snapshots and periodic JSON exports.

## Notes

- No Supabase, Postgres, Docker, or paid APIs are required for v1.
- Embeddings are optional and disabled by default.
- All scripts are designed to be safe to run repeatedly.
