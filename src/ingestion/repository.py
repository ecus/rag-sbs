"""Acceso a datos: doc_sources, ingestion_runs, change_events."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class IngestionRepository:
    """Repository pattern sobre las 3 tablas de ingesta."""

    def __init__(self, conn: AsyncConnection) -> None:
        self.conn = conn

    # -------------------------------------------------------------------------
    # doc_sources
    # -------------------------------------------------------------------------

    async def list_sources(
        self, *, only_enabled: bool = False, names: list[str] | None = None
    ) -> list[dict]:
        sql = "SELECT * FROM doc_sources WHERE 1=1"
        parametros: list[Any] = []
        if only_enabled:
            sql += " AND enabled = true"
        if names:
            sql += " AND name = ANY(%s)"
            parametros.append(names)
        sql += " ORDER BY name"
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(sql, parametros)
            return list(await cursor.fetchall())

    async def get_source(self, name: str) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute("SELECT * FROM doc_sources WHERE name = %s", (name,))
            return await cursor.fetchone()

    async def upsert_source(self, payload: dict) -> dict:
        """Insert or update (idempotente por name)."""
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                INSERT INTO doc_sources
                    (name, url, source_type, domain, document_type, cron_expr,
                     timezone, enabled, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    url = EXCLUDED.url,
                    source_type = EXCLUDED.source_type,
                    domain = EXCLUDED.domain,
                    document_type = EXCLUDED.document_type,
                    cron_expr = EXCLUDED.cron_expr,
                    timezone = EXCLUDED.timezone,
                    enabled = EXCLUDED.enabled,
                    metadata = EXCLUDED.metadata,
                    updated_at = now()
                RETURNING *
                """,
                (
                    payload["name"],
                    payload["url"],
                    payload.get("source_type", "direct_pdf"),
                    payload.get("domain"),
                    payload.get("document_type"),
                    payload.get("cron_expr", "0 2 * * *"),
                    payload.get("timezone", "America/Lima"),
                    payload.get("enabled", True),
                    Jsonb(payload.get("metadata", {})),
                ),
            )
            fila = await cursor.fetchone()
            assert fila is not None
            return fila

    async def update_check_state(
        self,
        *,
        source_id: UUID,
        etag: str | None,
        last_modified: str | None,
        content_hash: str | None,
        status: str,
        changed: bool,
    ) -> None:
        """Actualiza cache de detección tras una verificación."""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                UPDATE doc_sources
                SET last_etag = %s,
                    last_modified = %s,
                    last_hash = COALESCE(%s, last_hash),
                    last_status = %s,
                    last_checked_at = now(),
                    last_changed_at = CASE WHEN %s THEN now() ELSE last_changed_at END,
                    updated_at = now()
                WHERE id = %s
                """,
                (etag, last_modified, content_hash, status, changed, source_id),
            )

    async def delete_source(self, name: str) -> bool:
        async with self.conn.cursor() as cursor:
            await cursor.execute("DELETE FROM doc_sources WHERE name = %s", (name,))
            return cursor.rowcount > 0

    # -------------------------------------------------------------------------
    # ingestion_runs
    # -------------------------------------------------------------------------

    async def create_run(
        self, *, triggered_by: str, source_filter: list[str], dry_run: bool
    ) -> UUID:
        run_id = uuid4()
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO ingestion_runs
                    (id, status, triggered_by, source_filter, dry_run)
                VALUES (%s, 'running', %s, %s, %s)
                """,
                (run_id, triggered_by, Jsonb(source_filter), dry_run),
            )
        return run_id

    async def update_run(self, run_id: UUID, **fields: Any) -> None:
        if not fields:
            return
        # JSONB fields que requieren wrap
        campos_json = {"errors"}
        columnas = []
        valores: list[Any] = []
        for clave, valor in fields.items():
            columnas.append(f"{clave} = %s")
            valores.append(Jsonb(valor) if clave in campos_json else valor)
        valores.append(run_id)
        sql = f"UPDATE ingestion_runs SET {', '.join(columnas)} WHERE id = %s"
        async with self.conn.cursor() as cursor:
            await cursor.execute(sql, valores)

    async def list_runs(self, limit: int = 50) -> list[dict]:
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                "SELECT * FROM ingestion_runs ORDER BY started_at DESC LIMIT %s",
                (limit,),
            )
            return list(await cursor.fetchall())

    async def get_run(self, run_id: UUID) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute("SELECT * FROM ingestion_runs WHERE id = %s", (run_id,))
            return await cursor.fetchone()

    # -------------------------------------------------------------------------
    # change_events
    # -------------------------------------------------------------------------

    async def insert_change_event(
        self,
        *,
        source_id: UUID,
        run_id: UUID | None,
        event_type: str,
        document_id: UUID | None = None,
        summary: str | None = None,
        details: dict | None = None,
    ) -> UUID:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO change_events
                    (source_id, run_id, event_type, document_id, summary, details)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    source_id,
                    run_id,
                    event_type,
                    document_id,
                    summary,
                    Jsonb(details or {}),
                ),
            )
            fila = await cursor.fetchone()
            assert fila is not None
            return fila[0]

    async def list_unnotified_events(self, limit: int = 100) -> list[dict]:
        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT ce.*, ds.name AS source_name, ds.url AS source_url
                FROM change_events ce
                JOIN doc_sources ds ON ds.id = ce.source_id
                WHERE notified = false
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(await cursor.fetchall())

    async def mark_event_notified(self, event_id: UUID) -> None:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE change_events SET notified = true WHERE id = %s", (event_id,)
            )
