from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CaptureThoughtRequest(BaseModel):
    title: str | None = None
    body: str = Field(min_length=1)
    thought_type: str = "observation"
    source: str | None = None
    project: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    external_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=200)


class RecoverContextRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=200)
    max_chars: int = Field(default=12000, ge=200, le=200000)


class ImportRecord(BaseModel):
    external_id: str | None = None
    title: str | None = None
    body: str = Field(min_length=1)
    thought_type: str = "observation"
    source: str | None = None
    project: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class ImportBundleRequest(BaseModel):
    thoughts: list[ImportRecord] = Field(default_factory=list)


class ThoughtRecord(BaseModel):
    id: int
    external_id: str | None = None
    title: str | None = None
    body: str
    thought_type: str
    source: str | None = None
    project: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class MigrationSummary(BaseModel):
    ok: bool
    records_seen: int
    records_imported: int
    records_skipped: int
    errors: list[str] = Field(default_factory=list)
    raw_export_path: str
