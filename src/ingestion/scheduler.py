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

from src.graph.builder import reconstruir_completo
from src.ingestion.background_worker import tick as background_tick
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
        self._registrar_background_worker()
        self._registrar_graph_rebuild()
        self.scheduler.start()
        logger.info("IngestionScheduler started with %d jobs", len(self.scheduler.get_jobs()))

    def _registrar_background_worker(self) -> None:
        """Job dedicado: tick del worker de ingesta automática cada 10 min."""
        self.scheduler.add_job(
            self._tick_background,
            trigger=CronTrigger.from_crontab("*/10 * * * *", timezone="UTC"),
            id="background:tick",
            name="background ingestion tick",
            replace_existing=True,
            misfire_grace_time=600,
            coalesce=True,
            max_instances=1,
        )

    async def _tick_background(self) -> None:
        try:
            res = await background_tick(pool=self.pool, llm=self.llm)
            logger.info("Background tick: %s", res.get("action"))
        except Exception:
            logger.exception("Falló tick del background worker")

    def _registrar_graph_rebuild(self) -> None:
        """Reconstruye el knowledge graph al inicio de cada hora."""
        self.scheduler.add_job(
            self._rebuild_grafo,
            trigger=CronTrigger.from_crontab("5 * * * *", timezone="UTC"),
            id="graph:rebuild",
            name="rebuild knowledge graph",
            replace_existing=True,
            misfire_grace_time=1800,
            coalesce=True,
            max_instances=1,
        )

    async def _rebuild_grafo(self) -> None:
        try:
            res = await reconstruir_completo(self.pool)
            logger.info(
                "Graph rebuild: %d docs, %d ops nodo, %d ops arista",
                res.get("documentos_procesados", 0),
                res.get("operaciones_nodo", 0),
                res.get("operaciones_arista", 0),
            )
        except Exception:
            logger.exception("Falló rebuild del grafo")
            return

        # Tras rebuild, los nodos topic se borran en truncate_all → re-descubrir.
        try:
            from src.graph.topics import descubrir_topicos
            n_topicos = max(8, min(20, res.get("documentos_procesados", 0) // 20))
            topics_res = await descubrir_topicos(
                self.pool, self.llm, n_topicos=n_topicos
            )
            logger.info(
                "Topics rebuild: %d clusters sobre %d chunks",
                topics_res.get("n_topicos", 0),
                topics_res.get("chunks_clusterizados", 0),
            )
        except Exception:
            logger.exception("Falló descubrir_topicos tras rebuild")

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
