"""Modelos Pydantic del módulo de ingesta."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class DocSourceCreate(BaseModel):
    """Payload para registrar una fuente nueva."""

    name: str = Field(..., min_length=3, max_length=100)
    url: HttpUrl
    source_type: Literal["direct_pdf", "listing_html", "sitemap"] = "direct_pdf"
    domain: str | None = None
    document_type: str | None = None
    cron_expr: str = "0 2 * * *"  # daily 02:00
    timezone: str = "America/Lima"
    enabled: bool = True
    metadata: dict = Field(default_factory=dict)


class DocSourceUpdate(BaseModel):
    """Patch parcial."""

    url: HttpUrl | None = None
    source_type: Literal["direct_pdf", "listing_html", "sitemap"] | None = None
    domain: str | None = None
    document_type: str | None = None
    cron_expr: str | None = None
    timezone: str | None = None
    enabled: bool | None = None
    metadata: dict | None = None


class DocSource(BaseModel):
    """Vista completa de una fuente."""

    id: UUID
    name: str
    url: str
    source_type: str
    domain: str | None
    document_type: str | None
    cron_expr: str
    timezone: str
    enabled: bool
    last_etag: str | None
    last_modified: str | None
    last_hash: str | None
    last_status: str | None
    last_checked_at: datetime | None
    last_changed_at: datetime | None
    metadata: dict
    created_at: datetime
    updated_at: datetime


class IngestionRun(BaseModel):
    """Resumen de una ejecución del scheduler."""

    id: UUID
    started_at: datetime
    finished_at: datetime | None
    status: Literal["running", "completed", "failed", "partial"]
    sources_scanned: int
    docs_new: int
    docs_modified: int
    docs_unchanged: int
    errors: list[dict] = Field(default_factory=list)
    triggered_by: str | None
    dry_run: bool


class ScanRequest(BaseModel):
    """POST /v1/ingest/scan."""

    sources: list[str] = Field(default_factory=list, description="Filtra por nombres; vacío=todas")
    force: bool = Field(default=False, description="Ignora cache de hashes")
    dry_run: bool = Field(default=False, description="Detecta cambios sin upsert")


class ScanResponse(BaseModel):
    run_id: UUID
    status: str
    scheduled_at: datetime


class ChangeEvent(BaseModel):
    id: UUID
    source_id: UUID
    run_id: UUID | None
    event_type: Literal["new", "modified", "derogatorio", "parse_failed"]
    document_id: UUID | None
    summary: str | None
    details: dict
    notified: bool
    created_at: datetime
