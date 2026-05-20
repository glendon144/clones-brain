from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import load_settings
from .embeddings import get_embedding_provider
from .models import CaptureThoughtRequest, ImportRecord
from .search import search_thought_rows


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def connect_db(db_path: Path | None = None) -> sqlite3.Connection:
    settings = load_settings()
    path = Path(db_path or settings.db_path)
    ensure_parent(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    return conn


def init_db(schema_path: Path | None = None, db_path: Path | None = None) -> None:
    settings = load_settings()
    schema = Path(schema_path or settings.schema_path).read_text(encoding="utf-8")
    conn = connect_db(db_path)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


def _normalize_tags(tags: Iterable[str] | None) -> list[str]:
    if not tags:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        candidate = str(tag).strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(candidate)
    return cleaned


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    compact = " ".join(text.split())
    if len(compact) <= chunk_size:
        return [compact]

    chunks: list[str] = []
    start = 0
    stride = max(1, chunk_size - chunk_overlap)
    while start < len(compact):
        chunk = compact[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(compact):
            break
        start += stride
    return chunks or [compact]


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def row_to_thought(row: sqlite3.Row) -> dict[str, Any]:
    tags = [tag for tag in (row["tags"] or "").split(",") if tag]
    metadata = {}
    if row["metadata_json"]:
        try:
            metadata = json.loads(row["metadata_json"])
        except json.JSONDecodeError:
            metadata = {"raw": row["metadata_json"]}
    return {
        "id": row["id"],
        "external_id": row["external_id"],
        "title": row["title"],
        "body": row["body"],
        "thought_type": row["thought_type"],
        "source": row["source"],
        "project": row["project"],
        "tags": tags,
        "metadata": metadata,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def count_thoughts(conn: sqlite3.Connection) -> int:
    row = conn.execute("select count(*) as count from thoughts").fetchone()
    return int(row["count"] if row else 0)


def record_event(conn: sqlite3.Connection, event_type: str, thought_id: int | None, details: dict[str, Any]) -> None:
    conn.execute(
        "insert into events(event_type, thought_id, details_json, created_at) values (?, ?, ?, ?)",
        (event_type, thought_id, _json_dumps(details), utc_now_iso()),
    )


def enqueue_sync(conn: sqlite3.Connection, thought_id: int, target: str = "openbrain") -> None:
    now = utc_now_iso()
    conn.execute(
        "insert into sync_queue(thought_id, target, status, last_error, created_at, updated_at) values (?, ?, 'pending', null, ?, ?)",
        (thought_id, target, now, now),
    )


def thought_exists(conn: sqlite3.Connection, external_id: str | None, title: str | None, body: str, created_at: str | None) -> bool:
    if external_id:
        row = conn.execute("select 1 from thoughts where external_id = ? limit 1", (external_id,)).fetchone()
        if row:
            return True
    if created_at:
        row = conn.execute(
            "select 1 from thoughts where coalesce(title, '') = ? and body = ? and created_at = ? limit 1",
            (title or "", body, created_at),
        ).fetchone()
        if row:
            return True
    row = conn.execute(
        "select 1 from thoughts where coalesce(title, '') = ? and body = ? limit 1",
        (title or "", body),
    ).fetchone()
    return row is not None


def _insert_chunks(conn: sqlite3.Connection, thought_id: int, body: str) -> None:
    settings = load_settings()
    provider = get_embedding_provider()
    now = utc_now_iso()
    for idx, chunk in enumerate(_chunk_text(body, settings.chunk_size, settings.chunk_overlap)):
        embedding = provider.embed(chunk)
        conn.execute(
            "insert into chunks(thought_id, chunk_index, text, embedding_json, created_at) values (?, ?, ?, ?, ?)",
            (thought_id, idx, chunk, _json_dumps(embedding) if embedding is not None else None, now),
        )


def insert_thought(conn: sqlite3.Connection, payload: CaptureThoughtRequest | ImportRecord, enqueue_for_sync: bool = True) -> int:
    tags = _normalize_tags(payload.tags)
    created_at = payload.created_at or utc_now_iso()
    updated_at = payload.updated_at or created_at
    cursor = conn.execute(
        """
        insert into thoughts(
            external_id, title, body, thought_type, source, project, tags, metadata_json, created_at, updated_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.external_id,
            payload.title,
            payload.body,
            payload.thought_type or "observation",
            payload.source,
            payload.project,
            ",".join(tags),
            _json_dumps(payload.metadata),
            created_at,
            updated_at,
        ),
    )
    thought_id = int(cursor.lastrowid)
    _insert_chunks(conn, thought_id, payload.body)
    record_event(conn, "capture_thought", thought_id, {"source": payload.source, "project": payload.project})
    if enqueue_for_sync:
        enqueue_sync(conn, thought_id)
    return thought_id


def list_recent(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "select * from thoughts order by datetime(created_at) desc, id desc limit ?",
        (limit,),
    ).fetchall()
    return [row_to_thought(row) for row in rows]


def search_thoughts(conn: sqlite3.Connection, query: str, limit: int) -> tuple[list[dict[str, Any]], str]:
    rows, mode = search_thought_rows(conn, query, limit)
    results: list[dict[str, Any]] = []
    for row in rows:
        item = row_to_thought(row)
        item["score"] = row["score"] if "score" in row.keys() else None
        results.append(item)
    return results, mode


def export_bundle(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("select * from thoughts order by datetime(created_at) asc, id asc").fetchall()
    return {
        "ok": True,
        "exported_at": utc_now_iso(),
        "thoughts": [row_to_thought(row) for row in rows],
    }


def import_bundle(conn: sqlite3.Connection, records: list[ImportRecord]) -> dict[str, Any]:
    imported = 0
    skipped = 0
    errors: list[str] = []
    for record in records:
        if thought_exists(conn, record.external_id, record.title, record.body, record.created_at):
            skipped += 1
            continue
        try:
            insert_thought(conn, record, enqueue_for_sync=False)
            imported += 1
        except sqlite3.Error as exc:
            errors.append(str(exc))
    record_event(conn, "import_bundle", None, {"imported": imported, "skipped": skipped, "errors": len(errors)})
    return {"ok": not errors, "imported": imported, "skipped": skipped, "errors": errors}
