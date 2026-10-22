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

## 2026-10-21

### AI Dream Communicator Deluxe — First Packaged End-to-End Memory Recovery

- A PyInstaller-packaged build of AI Dream Communicator Deluxe launched successfully with Qt WebEngine working inside the frozen executable.
- From the packaged app, **Recover Memory Weave** retrieved previously captured browser context (real browsing history, not synthetic test data).
- The app emitted a portable context capsule holding three references, each with timestamp, title, URL, and excerpt.
- The capsule was pasted into an independent ChatGPT conversation. That instance interpreted it, recognized one reference as an email, searched the user's connected Gmail, and retrieved the real message: Toru Tagawa's Sept 28, 2026 "Letter to the Musicians" (Sierra Vista Symphony), then extracted the rehearsal schedule from it.
- Chain proven: packaged executable -> Qt WebEngine -> Recover Memory Weave -> capsule -> separate model instance -> authoritative retrieval from Gmail.

### Architectural principle: memory as actionable references

- The capsule did not contain the email. It held just enough (title, timestamp, URL, excerpt) for a reader to recognize the reference and fetch the authoritative content itself.
- Memory can be a collection of actionable references rather than a large store of duplicated content.
- Consequences: smaller context windows per operation; information can cross application and model boundaries; memory discovery is separated from authoritative retrieval.
- Fits the clones-brain stance: local memory is the master tape, and capsules are the lightweight pointers handed to other systems.

### Scope and limits (stated honestly)

- This shows one successful end-to-end run of one packaging configuration and one recovery path.
- It does not establish that every packaging configuration or every recovery operation works reliably. Repeatability, other machines, and other capsule consumers remain untested.
- Retrieval was performed by ChatGPT via its own Gmail connector, not by the packaged app.

### Provenance

- Milestone summary supplied by ChatGPT after the test; suggested development-history label: "AI Dream Communicator Deluxe — First Packaged End-to-End Memory Recovery, October 21, 2026."
- Thematic note: the test material was a letter from an orchestra conductor. The app remembered where the music was and handed the reference to another musician, who found the score. Sending just enough to make the next action possible, rather than shipping the whole archive, is the point (cf. Artt Frank's restraint).
