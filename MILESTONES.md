# Milestones

## 2026-05-20

### Local-first service brought online

- Built the first working `clones-brain` service under `/home/gross/open-brain/clones-brain`.
- Kept the virtual environment outside the repo at `/home/gross/.venvs/clones-brain`.
- Initialized the local SQLite store at `data/clones-brain.db`.
- Verified the FastAPI service on `http://127.0.0.1:8765`.
- Verified `/health`, `/capture_thought`, `/list_recent`, `/search_thoughts`, `/recover_context`, export/import, and the smoke test.
- Confirmed local search works with SQLite FTS5.

### Hosted OpenBrain rehearsal import

- Ran a 10-record hosted OpenBrain rehearsal import without modifying hosted data.
- Saved the raw hosted response to `exports/openbrain-rehearsal-raw-20260520-143954.json`.
- Imported 10 hosted thoughts into the local SQLite database.
- Verified duplicate protection by re-importing the same rehearsal payload: imported `0`, skipped `10`.
- Verified the imported records locally through `list_recent`, `search_thoughts`, and `recover_context`.

### Dream Server selective rehearsal import

- Queried hosted OpenBrain for:
  - `Dream Server`
  - `Dream Capsule`
  - `dream capsules`
  - `DCCP`
  - `recover_context`
  - `dream_server_status`
  - `Dream Space`
  - `Protected Ambiguity`
- Saved each raw hosted response under `exports/openbrain-selective-*-20260520-145106.json`.
- Normalized matching hosted search results into local thoughts with import metadata.
- Added continuity-oriented tags including `imported-from-openbrain`, `dream-server`, `dream-capsule`, and `continuity` where applicable.
- Imported 7 distinct Dream Server-related records after batch dedupe.
- Verified local search for `Dream Server` and `DCCP`.

### recover_context normalization tightened

- Updated local search normalization so natural-language questions are reduced to durable search terms before fallback.
- The query `What is the Dream Server and how does recover_context work?` now resolves through `fts5-normalized` instead of returning an empty result.

### Important limitation

- The hosted OpenBrain `list_thoughts` and `search_thoughts` APIs currently expose human-formatted SSE text blocks rather than structured rows with stable hosted IDs.
- Because of that, `external_id` could not be truthfully populated from hosted IDs during these rehearsals.
- The imports preserve available hosted provenance in `metadata`, including source strategy, query term, visible topics/people/actions, sequence/order hints, and raw export paths.

### Architectural note

Local SQLite is the source of truth. Hosted OpenBrain remains useful as a relay, archive, and migration source, but not as the canonical store.
