"""Dependencias FastAPI: pool de conexiones, LLM provider, lifecycle.

Patrón: el lifespan de FastAPI crea recursos compartidos (pool DB, cliente LLM)
una vez al startup y los limpia al shutdown. Las routes los consumen vía Depends.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from psycopg_pool import AsyncConnectionPool

from src.config import get_settings
from src.ingestion.scheduler import IngestionScheduler
from src.llm import LLMProvider, get_llm_provider
from src.storage import PgVectorStore


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Setup/teardown de recursos compartidos."""
    settings = get_settings()

    # Postgres pool: psycopg_pool maneja reconexiones, sizing, etc.
    # Convertimos DSN sqlalchemy a psycopg (sin "+psycopg")
    dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://")

    pool = AsyncConnectionPool(
        conninfo=dsn,
        min_size=1,
        max_size=10,
        open=False,
        configure=PgVectorStore.setup_connection,
    )
    await pool.open()
    app.state.pg_pool = pool

    # LLM provider (singleton)
    app.state.llm = get_llm_provider()

    # Ingestion scheduler (APScheduler con cron por fuente)
    scheduler = IngestionScheduler(pool=pool, llm=app.state.llm)
    app.state.ingestion_scheduler = scheduler
    try:
        await scheduler.start()
    except Exception as exc:  # noqa: BLE001
        # No bloquear arranque si scheduler falla; queda /v1/ingest/scan manual
        import logging
        logging.getLogger(__name__).warning("Scheduler no inició: %s", exc)

    try:
        yield
    finally:
        await scheduler.shutdown()
        await pool.close()
        if hasattr(app.state.llm, "close"):
            await app.state.llm.close()


# -----------------------------------------------------------------------------
# Dependencias inyectables vía Depends()
# -----------------------------------------------------------------------------

async def get_pool(request: Request) -> AsyncConnectionPool:
    """Pool de Postgres compartido."""
    return request.app.state.pg_pool


async def get_llm(request: Request) -> LLMProvider:
    """LLM provider compartido."""
    return request.app.state.llm
