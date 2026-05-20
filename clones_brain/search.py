from __future__ import annotations

import re
import sqlite3
from typing import Any

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "work",
}


def _tokenize_query(query: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", query.lower())


def normalize_query_text(query: str) -> str:
    tokens = _tokenize_query(query)
    kept: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if len(token) <= 1 or token in STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        kept.append(token)
    return " ".join(kept) if kept else query.strip()


def _build_fts_candidates(query: str) -> list[str]:
    candidates: list[str] = []
    raw = query.strip()
    normalized = normalize_query_text(query)
    for candidate in (raw, normalized):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _build_like_candidates(query: str) -> list[str]:
    candidates: list[str] = []
    raw = query.strip()
    normalized = normalize_query_text(query)
    joined = "%".join(normalized.split()) if normalized else ""
    for candidate in (raw, normalized, joined):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


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
        for candidate in _build_fts_candidates(query):
            try:
                rows = conn.execute(sql, (candidate, limit)).fetchall()
                if rows:
                    mode = "fts5" if candidate == query.strip() else "fts5-normalized"
                    return rows, mode
            except sqlite3.Error:
                continue

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
    for candidate in _build_like_candidates(query):
        wildcard = f"%{candidate}%"
        rows = conn.execute(sql, (wildcard, wildcard, wildcard, wildcard, wildcard, wildcard, limit)).fetchall()
        if rows:
            mode = "like" if candidate == query.strip() else "like-normalized"
            return rows, mode
    return [], "like"


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
