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

    # Limpiar runs zombies (status='running' > 30 min sin actualización)
    # Causados por crashes del proceso anterior o deploys mientras procesaba.
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE ingestion_runs
                    SET status='aborted', finished_at=NOW()
                    WHERE status='running' AND started_at < NOW() - INTERVAL '30 minutes'
                    """
                )
                if cur.rowcount > 0:
                    import logging
                    logging.getLogger(__name__).info(
                        "Cleanup startup: %d runs zombies marcados como aborted",
                        cur.rowcount,
                    )
    except Exception:  # noqa: BLE001
        pass  # no bloquear startup

    # LLM provider (singleton)
    app.state.llm = get_llm_provider()

    # Ingestion scheduler (APScheduler con cron por fuente).
    # Se puede apagar con SCHEDULER_ENABLED=false para no consumir cuota del
    # LLM (embeddings de re-ingestas). Las consultas siguen funcionando; solo
    # se detiene la ingesta automática y el discovery. La ingesta manual por
    # /v1/ingest sigue disponible.
    import os
    import logging
    _scheduler_on = os.environ.get("SCHEDULER_ENABLED", "true").lower() not in (
        "false", "0", "no", "off"
    )
    scheduler = IngestionScheduler(pool=pool, llm=app.state.llm)
    app.state.ingestion_scheduler = scheduler
    if _scheduler_on:
        try:
            await scheduler.start()
        except Exception as exc:  # noqa: BLE001
            # No bloquear arranque si scheduler falla; queda /v1/ingest/scan manual
            logging.getLogger(__name__).warning("Scheduler no inició: %s", exc)
    else:
        logging.getLogger(__name__).warning(
            "SCHEDULER_ENABLED=false — ingesta automática DESACTIVADA "
            "(no se consumirá cuota del LLM en background)."
        )

    try:
        yield
    finally:
        if _scheduler_on:
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
