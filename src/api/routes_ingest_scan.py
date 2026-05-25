"""Endpoints del módulo de ingesta automática.

  POST   /v1/ingest/scan
  GET    /v1/ingest/runs
  GET    /v1/ingest/runs/{id}
  GET    /v1/ingest/sources
  POST   /v1/ingest/sources
  PUT    /v1/ingest/sources/{name}
  DELETE /v1/ingest/sources/{name}
  GET    /v1/ingest/events                (changes detectados pendientes de notificación)
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from psycopg_pool import AsyncConnectionPool

from src.core.deps import get_llm, get_pool
from src.ingestion.models import (
    ChangeEvent,
    DocSource,
    DocSourceCreate,
    DocSourceUpdate,
    IngestionRun,
    ScanRequest,
    ScanResponse,
)
from src.ingestion.pipeline import run_scan
from src.ingestion.repository import IngestionRepository
from src.llm import LLMProvider

router = APIRouter(prefix="/v1/ingest", tags=["ingest-scan"])


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

@router.post("/scan", response_model=ScanResponse, status_code=202)
async def scan(
    payload: ScanRequest,
    background: BackgroundTasks,
    request: Request,
    pool: AsyncConnectionPool = Depends(get_pool),
    llm: LLMProvider = Depends(get_llm),
) -> ScanResponse:
    """Dispara un scan asíncrono. Retorna 202 con run_id; consultar via /runs/{id}."""
    # Crear run inmediatamente para tener run_id que devolver
    async with pool.connection() as conn:
        repo = IngestionRepository(conn)
        run_id = await repo.create_run(
            triggered_by="manual",
            source_filter=payload.sources,
            dry_run=payload.dry_run,
        )

    # Background: ejecutar el scan completo. APScheduler también puede dispararlo
    # según cron, pero aquí es manual on-demand.
    async def _ejecutar_en_background() -> None:
        # NOTA: la función run_scan crea SU PROPIO run_id. Para consistencia,
        # llamamos a process_source manualmente. Versión MVP: dejamos run_scan
        # crear su run y usamos el mismo state. En siguiente iteración
        # refactorizamos para aceptar run_id externo.
        await run_scan(
            pool=pool,
            llm=llm,
            source_filter=payload.sources,
            force=payload.force,
            dry_run=payload.dry_run,
            triggered_by="manual",
        )

    background.add_task(_ejecutar_en_background)

    return ScanResponse(
        run_id=run_id,
        status="running",
        scheduled_at=datetime.now(timezone.utc),
    )


@router.get("/runs", response_model=list[IngestionRun])
async def list_runs(
    limit: int = 50,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> list[IngestionRun]:
    async with pool.connection() as conn:
        repo = IngestionRepository(conn)
        filas = await repo.list_runs(limit=limit)
    return [IngestionRun(**f) for f in filas]


@router.get("/runs/{run_id}", response_model=IngestionRun)
async def get_run(
    run_id: UUID,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> IngestionRun:
    async with pool.connection() as conn:
        repo = IngestionRepository(conn)
        fila = await repo.get_run(run_id)
    if not fila:
        raise HTTPException(404, "run no encontrado")
    return IngestionRun(**fila)


# ---------------------------------------------------------------------------
# Sources CRUD
# ---------------------------------------------------------------------------

@router.get("/sources", response_model=list[DocSource])
async def list_sources(
    only_enabled: bool = False,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> list[DocSource]:
    async with pool.connection() as conn:
        repo = IngestionRepository(conn)
        filas = await repo.list_sources(only_enabled=only_enabled)
    return [DocSource(**f) for f in filas]


@router.post("/sources", response_model=DocSource, status_code=201)
async def create_source(
    payload: DocSourceCreate,
    request: Request,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> DocSource:
    async with pool.connection() as conn:
        repo = IngestionRepository(conn)
        fila = await repo.upsert_source(payload.model_dump(mode="json"))

    # Refresh scheduler jobs si está activo
    sched = getattr(request.app.state, "ingestion_scheduler", None)
    if sched:
        await sched.reload_jobs()

    return DocSource(**fila)


@router.put("/sources/{name}", response_model=DocSource)
async def update_source(
    name: str,
    payload: DocSourceUpdate,
    request: Request,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> DocSource:
    async with pool.connection() as conn:
        repo = IngestionRepository(conn)
        existente = await repo.get_source(name)
        if not existente:
            raise HTTPException(404, "fuente no encontrada")
        merged = {**existente, **payload.model_dump(mode="json", exclude_none=True)}
        merged["name"] = name
        # url puede venir como HttpUrl-string
        if merged.get("url") is None:
            merged["url"] = existente["url"]
        merged["url"] = str(merged["url"])
        fila = await repo.upsert_source(merged)

    sched = getattr(request.app.state, "ingestion_scheduler", None)
    if sched:
        await sched.reload_jobs()

    return DocSource(**fila)


@router.delete("/sources/{name}", status_code=204)
async def delete_source(
    name: str,
    request: Request,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> None:
    async with pool.connection() as conn:
        repo = IngestionRepository(conn)
        ok = await repo.delete_source(name)
    if not ok:
        raise HTTPException(404, "fuente no encontrada")

    sched = getattr(request.app.state, "ingestion_scheduler", None)
    if sched:
        await sched.reload_jobs()


# ---------------------------------------------------------------------------
# Change events
# ---------------------------------------------------------------------------

@router.get("/events", response_model=list[ChangeEvent])
async def list_unnotified_events(
    limit: int = 100,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> list[ChangeEvent]:
    async with pool.connection() as conn:
        repo = IngestionRepository(conn)
        filas = await repo.list_unnotified_events(limit=limit)
    # Filtrar campos extra inyectados (source_name, source_url) que no van en el schema
    eventos = []
    for f in filas:
        f.pop("source_name", None)
        f.pop("source_url", None)
        eventos.append(ChangeEvent(**f))
    return eventos
