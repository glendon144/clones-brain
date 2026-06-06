from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "clones-brain.db"
DEFAULT_EXPORT_DIR = ROOT_DIR / "exports"
DEFAULT_LOG_DIR = ROOT_DIR / "logs"
DEFAULT_SCHEMA_PATH = ROOT_DIR / "schema.sql"


@dataclass(frozen=True)
class Settings:
    db_path: Path
    export_dir: Path
    log_dir: Path
    schema_path: Path
    host: str
    port: int
    chunk_size: int
    chunk_overlap: int
    embeddings_enabled: bool
    openbrain_base_url: str | None
    openbrain_project_id: str | None
    openbrain_api_key: str | None


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache
def load_settings() -> Settings:
    """
    Load and cache the application settings.

    Reading environment variables and default paths from disk can be relatively
    expensive if done on every request. Decorating this function with
    ``@lru_cache`` ensures that the ``Settings`` object is created once and
    reused for all subsequent calls. FastAPI will call this function through
    dependencies, and the cached result improves performance while still
    allowing overrides during testing.
    """
    db_path = Path(os.getenv("CLONES_BRAIN_DB", DEFAULT_DB_PATH)).expanduser()
    export_dir = Path(os.getenv("CLONES_BRAIN_EXPORT_DIR", DEFAULT_EXPORT_DIR)).expanduser()
    log_dir = Path(os.getenv("CLONES_BRAIN_LOG_DIR", DEFAULT_LOG_DIR)).expanduser()
    schema_path = Path(os.getenv("CLONES_BRAIN_SCHEMA", DEFAULT_SCHEMA_PATH)).expanduser()
    return Settings(
        db_path=db_path,
        export_dir=export_dir,
        log_dir=log_dir,
        schema_path=schema_path,
        host=os.getenv("CLONES_BRAIN_HOST", "127.0.0.1"),
        port=int(os.getenv("CLONES_BRAIN_PORT", "8765")),
        chunk_size=max(200, int(os.getenv("CLONES_BRAIN_CHUNK_SIZE", "900"))),
        chunk_overlap=max(0, int(os.getenv("CLONES_BRAIN_CHUNK_OVERLAP", "120"))),
        embeddings_enabled=_env_bool("CLONES_BRAIN_ENABLE_EMBEDDINGS", False),
        openbrain_base_url=os.getenv("OPENBRAIN_BASE_URL"),
        openbrain_project_id=os.getenv("OPENBRAIN_PROJECT_ID"),
        openbrain_api_key=os.getenv("OPENBRAIN_API_KEY"),
    )
