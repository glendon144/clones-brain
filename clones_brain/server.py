from __future__ import annotations

from contextlib import closing

from fastapi import FastAPI

from .config import load_settings
from .db import connect_db, count_thoughts, export_bundle, import_bundle, init_db, insert_thought, list_recent, search_thoughts, utc_now_iso
from .models import CaptureThoughtRequest, ImportBundleRequest, RecoverContextRequest, SearchRequest
from .search import build_context_bundle

app = FastAPI(title="clones-brain")


@app.on_event("startup")
def startup() -> None:
    settings = load_settings()
    init_db(db_path=settings.db_path)


@app.get("/health")
def health() -> dict[str, object]:
    settings = load_settings()
    with closing(connect_db(settings.db_path)) as conn:
        thought_count = count_thoughts(conn)
    return {
        "ok": True,
        "service": "clones-brain",
        "db_path": str(settings.db_path),
        "thought_count": thought_count,
        "time": utc_now_iso(),
    }


@app.post("/capture_thought")
def capture_thought(request: CaptureThoughtRequest) -> dict[str, object]:
    settings = load_settings()
    with closing(connect_db(settings.db_path)) as conn:
        thought_id = insert_thought(conn, request)
        conn.commit()
    return {"ok": True, "id": thought_id, "status": "captured"}


@app.get("/list_recent")
def get_list_recent(limit: int = 20) -> dict[str, object]:
    settings = load_settings()
    safe_limit = min(max(limit, 1), 200)
    with closing(connect_db(settings.db_path)) as conn:
        thoughts = list_recent(conn, safe_limit)
    return {"ok": True, "thoughts": thoughts, "count": len(thoughts)}


@app.post("/search_thoughts")
def post_search_thoughts(request: SearchRequest) -> dict[str, object]:
    settings = load_settings()
    with closing(connect_db(settings.db_path)) as conn:
        thoughts, mode = search_thoughts(conn, request.query, request.limit)
    return {"ok": True, "query": request.query, "mode": mode, "thoughts": thoughts, "count": len(thoughts)}


@app.post("/recover_context")
def recover_context(request: RecoverContextRequest) -> dict[str, object]:
    settings = load_settings()
    with closing(connect_db(settings.db_path)) as conn:
        thoughts, mode = search_thoughts(conn, request.query, request.limit)
    contexts, combined_context = build_context_bundle(thoughts, request.max_chars)
    return {
        "ok": True,
        "query": request.query,
        "mode": mode,
        "contexts": contexts,
        "combined_context": combined_context,
    }


@app.get("/export_bundle")
def get_export_bundle() -> dict[str, object]:
    settings = load_settings()
    with closing(connect_db(settings.db_path)) as conn:
        bundle = export_bundle(conn)
    return bundle


@app.post("/import_bundle")
def post_import_bundle(request: ImportBundleRequest) -> dict[str, object]:
    settings = load_settings()
    with closing(connect_db(settings.db_path)) as conn:
        result = import_bundle(conn, request.thoughts)
        conn.commit()
    return result
