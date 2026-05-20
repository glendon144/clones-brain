from __future__ import annotations

import sqlite3
from typing import Any


def has_fts5(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("select 1 from thoughts_fts limit 1")
        return True
    except sqlite3.Error:
        return False


def search_thought_rows(conn: sqlite3.Connection, query: str, limit: int) -> tuple[list[sqlite3.Row], str]:
    if has_fts5(conn):
        sql = """
        select t.*, bm25(thoughts_fts) as score
        from thoughts_fts
        join thoughts t on t.id = thoughts_fts.rowid
        where thoughts_fts match ?
        order by score asc, t.created_at desc
        limit ?
        """
        try:
            rows = conn.execute(sql, (query, limit)).fetchall()
            return rows, "fts5"
        except sqlite3.Error:
            pass

    wildcard = f"%{query}%"
    sql = """
    select *,
      case
        when body like ? then 1.0
        when title like ? then 0.8
        when tags like ? then 0.5
        else 0.1
      end as score
    from thoughts
    where body like ? or title like ? or tags like ?
    order by score desc, created_at desc
    limit ?
    """
    rows = conn.execute(sql, (wildcard, wildcard, wildcard, wildcard, wildcard, wildcard, limit)).fetchall()
    return rows, "like"


def build_context_bundle(rows: list[dict[str, Any]], max_chars: int) -> tuple[list[dict[str, Any]], str]:
    contexts: list[dict[str, Any]] = []
    chunks: list[str] = []
    current_size = 0

    for row in rows:
        title = row.get("title") or "Untitled"
        body = row.get("body") or ""
        snippet = f"[{row['id']}] {title}\n{body}"
        if chunks and current_size + len(snippet) + 2 > max_chars:
            break
        current_size += len(snippet) + 2
        score = row.get("score")
        contexts.append({
            "id": row["id"],
            "title": row.get("title"),
            "body": body,
            "score": score,
        })
        chunks.append(snippet)

    return contexts, "\n\n".join(chunks)
