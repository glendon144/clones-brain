from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from .config import load_settings
from .db import connect_db, import_bundle, init_db
from .models import ImportRecord, MigrationSummary


@dataclass
class RawCapture:
    strategy: str
    payload: dict[str, Any] | None
    response: Any
    error: str | None = None


class OpenBrainMigrator:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.base_url = (self.settings.openbrain_base_url or "").rstrip("/")
        self.api_key = self.settings.openbrain_api_key
        self.timeout = 45

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["x-brain-key"] = self.api_key
        return headers

    def _parse_response(self, response: requests.Response) -> Any:
        text = response.text.strip()
        if not text:
            return {}
        if text.startswith("{") or text.startswith("["):
            return response.json()
        for line in text.splitlines():
            if line.startswith("data: "):
                candidate = line[6:].strip()
                if candidate.startswith("{") or candidate.startswith("["):
                    return json.loads(candidate)
        return {"raw_text": text}

    def _post_jsonrpc(self, tool_name: str, arguments: dict[str, Any]) -> RawCapture:
        payload = {
            "jsonrpc": "2.0",
            "id": f"migration-{tool_name}",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        try:
            response = requests.post(self.base_url, params={"key": self.api_key} if self.api_key else None, headers=self._headers(), json=payload, timeout=self.timeout)
            response.raise_for_status()
            return RawCapture(strategy=f"jsonrpc:{tool_name}", payload=payload, response=self._parse_response(response))
        except Exception as exc:
            return RawCapture(strategy=f"jsonrpc:{tool_name}", payload=payload, response=None, error=str(exc))

    def _post_rest(self, path: str, payload: dict[str, Any] | None = None) -> RawCapture:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        try:
            response = requests.post(url, params={"key": self.api_key} if self.api_key else None, headers=self._headers(), json=payload or {}, timeout=self.timeout)
            response.raise_for_status()
            return RawCapture(strategy=f"rest:{path}", payload=payload, response=self._parse_response(response))
        except Exception as exc:
            return RawCapture(strategy=f"rest:{path}", payload=payload, response=None, error=str(exc))

    def _get_rest(self, path: str) -> RawCapture:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        try:
            response = requests.get(url, params={"key": self.api_key} if self.api_key else None, headers=self._headers(), timeout=self.timeout)
            response.raise_for_status()
            return RawCapture(strategy=f"get:{path}", payload=None, response=self._parse_response(response))
        except Exception as exc:
            return RawCapture(strategy=f"get:{path}", payload=None, response=None, error=str(exc))

    def collect(self) -> list[RawCapture]:
        if not self.base_url:
            raise RuntimeError("OPENBRAIN_BASE_URL is required for migration")

        captures: list[RawCapture] = []
        captures.append(self._post_jsonrpc("list_thoughts", {"limit": 250}))
        captures.append(self._post_jsonrpc("search_thoughts", {"query": "the OR a OR project OR note", "limit": 100}))
        captures.append(self._post_jsonrpc("recover_context", {"query": "system project notes memory", "limit": 100, "max_chars": 50000}))
        captures.append(self._get_rest("/list_recent?limit=250"))
        captures.append(self._get_rest("/export_bundle"))
        captures.append(self._post_rest("/search_thoughts", {"query": "system", "limit": 100}))
        captures.append(self._post_rest("/recover_context", {"query": "project", "limit": 100, "max_chars": 50000}))
        return captures


def _extract_text_blocks(data: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(data, dict):
        if isinstance(data.get("raw_text"), str):
            texts.append(data["raw_text"])
        result = data.get("result")
        if isinstance(result, dict):
            for item in result.get("content", []) or []:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    texts.append(item["text"])
        for key in ("combined_context", "body", "text"):
            value = data.get(key)
            if isinstance(value, str):
                texts.append(value)
    elif isinstance(data, list):
        for item in data:
            texts.extend(_extract_text_blocks(item))
    return texts


def _normalize_record(item: dict[str, Any], fallback_source: str) -> ImportRecord | None:
    body = item.get("body") or item.get("content") or item.get("text")
    if not body or not isinstance(body, str):
        return None
    raw_tags = item.get("tags") or item.get("topics") or []
    if isinstance(raw_tags, str):
        tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
    else:
        tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {"raw_metadata": metadata} if metadata is not None else {}
    return ImportRecord(
        external_id=str(item.get("external_id") or item.get("id")) if item.get("external_id") or item.get("id") else None,
        title=item.get("title"),
        body=body,
        thought_type=item.get("thought_type") or item.get("type") or "observation",
        source=item.get("source") or fallback_source,
        project=item.get("project") or item.get("workspace"),
        tags=tags,
        metadata=metadata,
        created_at=item.get("created_at") or item.get("timestamp"),
        updated_at=item.get("updated_at") or item.get("created_at") or item.get("timestamp"),
    )


def _normalize_from_text(text: str, source: str) -> list[ImportRecord]:
    records: list[ImportRecord] = []
    for line in text.splitlines():
        candidate = line.strip().lstrip("-*").strip()
        if len(candidate) < 20:
            continue
        # TODO: Refine this parser if the hosted deployment only exposes human-formatted summaries.
        records.append(
            ImportRecord(
                title=None,
                body=candidate,
                thought_type="reference",
                source=source,
                project="openbrain-import",
                tags=["openbrain", "summary-import"],
                metadata={"parsed_from": "text_block"},
            )
        )
    return records


def _normalize_payload(data: Any, source: str) -> list[ImportRecord]:
    records: list[ImportRecord] = []
    if isinstance(data, dict):
        for key in ("thoughts", "contexts", "items", "records", "data"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        normalized = _normalize_record(item, source)
                        if normalized:
                            records.append(normalized)
        result = data.get("result")
        if isinstance(result, dict):
            records.extend(_normalize_payload(result, source))
        for text in _extract_text_blocks(data):
            records.extend(_normalize_from_text(text, source))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                normalized = _normalize_record(item, source)
                if normalized:
                    records.append(normalized)
    return records


def save_raw_export(captures: list[RawCapture], export_dir: Path | None = None) -> Path:
    settings = load_settings()
    target_dir = Path(export_dir or settings.export_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = target_dir / f"openbrain-migration-raw-{timestamp}.json"
    payload = [
        {
            "strategy": capture.strategy,
            "payload": capture.payload,
            "response": capture.response,
            "error": capture.error,
        }
        for capture in captures
    ]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def migrate_from_openbrain() -> MigrationSummary:
    settings = load_settings()
    init_db(db_path=settings.db_path)
    migrator = OpenBrainMigrator()
    captures = migrator.collect()
    raw_path = save_raw_export(captures)

    normalized: list[ImportRecord] = []
    errors: list[str] = []
    for capture in captures:
        if capture.error:
            errors.append(f"{capture.strategy}: {capture.error}")
            continue
        normalized.extend(_normalize_payload(capture.response, capture.strategy))

    deduped: list[ImportRecord] = []
    seen: set[tuple[str | None, str | None, str, str | None]] = set()
    for record in normalized:
        key = (record.external_id, record.title, record.body, record.created_at)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)

    conn = connect_db(settings.db_path)
    try:
        result = import_bundle(conn, deduped)
        conn.commit()
    finally:
        conn.close()

    return MigrationSummary(
        ok=not errors and not result["errors"],
        records_seen=len(normalized),
        records_imported=result["imported"],
        records_skipped=result["skipped"] + (len(normalized) - len(deduped)),
        errors=errors + result["errors"],
        raw_export_path=str(raw_path),
    )
