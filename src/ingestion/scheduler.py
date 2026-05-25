"""Scheduler: APScheduler con cron por fuente.

ADR-004: APScheduler en local + Cloud Scheduler/Run Job en cloud (Sprint 3).
Aquí: corre dentro del proceso FastAPI. min_instances=1 cuando se despliegue.

Cada fuente registra un job individual con su propio cron_expr/timezone.
Refresh: cuando se crean/actualizan/eliminan fuentes vía API, se llama a
`reload_jobs()` para sincronizar.
"""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from psycopg_pool import AsyncConnectionPool

from src.ingestion.pipeline import run_scan
from src.ingestion.repository import IngestionRepository
from src.llm import LLMProvider

logger = logging.getLogger(__name__)


class IngestionScheduler:
    """Adapter sobre APScheduler para nuestras fuentes."""

    def __init__(self, pool: AsyncConnectionPool, llm: LLMProvider) -> None:
        self.pool = pool
        self.llm = llm
        self.scheduler = AsyncIOScheduler()

    async def start(self) -> None:
        await self.reload_jobs()
        self.scheduler.start()
        logger.info("IngestionScheduler started with %d jobs", len(self.scheduler.get_jobs()))

    async def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def reload_jobs(self) -> None:
        """Sincroniza jobs con doc_sources actuales en BD."""
        # Limpia
        for job in list(self.scheduler.get_jobs()):
            self.scheduler.remove_job(job.id)

        async with self.pool.connection() as conn:
            repo = IngestionRepository(conn)
            fuentes = await repo.list_sources(only_enabled=True)

        for fuente in fuentes:
            self._registrar_job_para(fuente)

    def _registrar_job_para(self, source: dict[str, Any]) -> None:
        try:
            disparador = CronTrigger.from_crontab(
                source["cron_expr"], timezone=source["timezone"]
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Cron inválido en fuente %s (%s): %s — saltada",
                source["name"], source["cron_expr"], exc,
            )
            return

        self.scheduler.add_job(
            self._escanear_una,
            trigger=disparador,
            id=f"scan:{source['name']}",
            name=f"scan {source['name']}",
            args=[source["name"]],
            replace_existing=True,
            misfire_grace_time=600,  # 10 min
            coalesce=True,
        )

    async def _escanear_una(self, source_name: str) -> None:
        """Job target: scan de una fuente puntual."""
        try:
            await run_scan(
                pool=self.pool,
                llm=self.llm,
                source_filter=[source_name],
                force=False,
                dry_run=False,
                triggered_by=f"cron:{source_name}",
            )
        except Exception:
            logger.exception("Falló scan de %s", source_name)
