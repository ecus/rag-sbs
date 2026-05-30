"""Worker de ingesta en background.

Procesa la cola ``pending_sources`` con rate limiting estricto:
- Tope diario de costo Gemini estimado
- Tope total de costo acumulado
- Tope total de documentos procesados
- Plazo (schedule_until)

Si cualquiera de los caps se alcanza, el worker se detiene automáticamente.

Es invocado por APScheduler con frecuencia configurable (default cada 10 min).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from psycopg_pool import AsyncConnectionPool

from src.ingestion.pipeline import process_source
from src.ingestion.repository import IngestionRepository
from src.llm import LLMProvider

logger = logging.getLogger(__name__)


# Pricing actual (mayo 2026) — Gemini Tier 1
# Embeddings: $0.00015 / 1k tokens
# Generación: $0.075 / 1M input + $0.30 / 1M output (Flash)
# Asumimos ~500 tokens/chunk para embeddings y ~36 chunks/doc avg.
_PRECIO_EMBED_POR_1K = 0.00015


async def _leer_config(conn) -> dict[str, Any]:
    """Lee la configuración del worker desde background_config."""
    async with conn.cursor() as cur:
        await cur.execute("SELECT key, value FROM background_config")
        cfg = {k: v for k, v in await cur.fetchall()}
    return cfg


async def _estado_actual(conn) -> dict[str, Any]:
    """Retorna métricas acumuladas y del día."""
    today = datetime.now(timezone.utc).date()
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT docs_processed, chunks_processed, estimated_cost, last_doc_at
            FROM cost_tracker WHERE day = %s
            """,
            (today,),
        )
        row_today = await cur.fetchone()
        if row_today:
            today_data = {
                "docs": row_today[0],
                "chunks": row_today[1],
                "cost": float(row_today[2] or 0),
                "last": row_today[3],
            }
        else:
            today_data = {"docs": 0, "chunks": 0, "cost": 0.0, "last": None}

        await cur.execute(
            """
            SELECT
              COALESCE(SUM(docs_processed), 0) AS docs,
              COALESCE(SUM(chunks_processed), 0) AS chunks,
              COALESCE(SUM(estimated_cost), 0) AS cost
            FROM cost_tracker
            """
        )
        row_total = await cur.fetchone()
        total_data = {
            "docs": int(row_total[0] or 0),
            "chunks": int(row_total[1] or 0),
            "cost": float(row_total[2] or 0),
        }

        await cur.execute(
            "SELECT status, COUNT(*) FROM pending_sources GROUP BY status"
        )
        queue_data = {s: c for s, c in await cur.fetchall()}

    return {
        "today": today_data,
        "total": total_data,
        "queue": queue_data,
    }


async def _registrar_costo(
    conn, *, docs: int, chunks: int, cost: float
) -> None:
    today = datetime.now(timezone.utc).date()
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO cost_tracker (day, docs_processed, chunks_processed, estimated_cost, last_doc_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (day) DO UPDATE
                SET docs_processed = cost_tracker.docs_processed + EXCLUDED.docs_processed,
                    chunks_processed = cost_tracker.chunks_processed + EXCLUDED.chunks_processed,
                    estimated_cost = cost_tracker.estimated_cost + EXCLUDED.estimated_cost,
                    last_doc_at = NOW()
            """,
            (today, docs, chunks, cost),
        )


def _calcular_costo(chunks: int, tokens_por_chunk: int = 500) -> float:
    """Costo estimado de embeddings para N chunks."""
    return (chunks * tokens_por_chunk / 1000) * _PRECIO_EMBED_POR_1K


def _tomar_valor(cfg: dict, key: str, default: Any) -> Any:
    val = cfg.get(key)
    if val is None:
        return default
    return val


async def tick(
    *,
    pool: AsyncConnectionPool,
    llm: LLMProvider,
) -> dict[str, Any]:
    """Una iteración del worker.

    Devuelve un dict con métricas y acción tomada.
    """
    async with pool.connection() as conn:
        cfg = await _leer_config(conn)
        estado = await _estado_actual(conn)

    # 1. ¿Habilitado?
    if not _tomar_valor(cfg, "enabled", True):
        return {"action": "skip", "reason": "disabled", "estado": estado}

    # 2. ¿Pasó el plazo?
    schedule_until = _tomar_valor(cfg, "schedule_until", None)
    if schedule_until:
        try:
            limite = datetime.fromisoformat(schedule_until.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > limite:
                return {
                    "action": "skip",
                    "reason": f"past_schedule (limit={schedule_until})",
                    "estado": estado,
                }
        except (ValueError, AttributeError):
            pass

    # 3. ¿Excedió costo total?
    max_cost_total = float(_tomar_valor(cfg, "max_cost_total", 9.50))
    if estado["total"]["cost"] >= max_cost_total:
        return {
            "action": "skip",
            "reason": f"cost_cap_total (${estado['total']['cost']:.2f} >= ${max_cost_total})",
            "estado": estado,
        }

    # 4. ¿Excedió costo del día?
    max_cost_daily = float(_tomar_valor(cfg, "max_cost_daily", 1.50))
    if estado["today"]["cost"] >= max_cost_daily:
        return {
            "action": "skip",
            "reason": f"cost_cap_daily (${estado['today']['cost']:.2f} >= ${max_cost_daily})",
            "estado": estado,
        }

    # 5. ¿Excedió documentos totales?
    max_docs_total = int(_tomar_valor(cfg, "max_docs_total", 2000))
    if estado["total"]["docs"] >= max_docs_total:
        return {
            "action": "skip",
            "reason": f"doc_cap_total ({estado['total']['docs']} >= {max_docs_total})",
            "estado": estado,
        }

    # 6. Tomar N candidatos de la cola
    docs_per_tick = int(_tomar_valor(cfg, "docs_per_tick", 3))
    # Ajustar por costo restante del día
    cost_remaining_today = max_cost_daily - estado["today"]["cost"]
    # ~$0.0027 por doc avg
    max_docs_by_cost = max(1, int(cost_remaining_today / 0.005))
    docs_to_take = min(docs_per_tick, max_docs_by_cost)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE pending_sources
                SET status = 'processing'
                WHERE id IN (
                    SELECT id FROM pending_sources
                    WHERE status = 'pending'
                    ORDER BY priority ASC, discovered_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, url, name_hint, title_hint, issuer, document_type, domain
                """,
                (docs_to_take,),
            )
            candidatos = await cur.fetchall()

    if not candidatos:
        return {
            "action": "skip",
            "reason": "queue_empty",
            "estado": estado,
        }

    # 7. Procesar cada candidato
    resultados = []
    for cid, url, name_hint, title_hint, issuer, doc_type, domain in candidatos:
        try:
            # Encolar como source y procesarlo via process_source existente
            async with pool.connection() as conn:
                repo = IngestionRepository(conn)
                fuente = await repo.upsert_source({
                    "name": name_hint or f"auto-{cid}",
                    "url": url,
                    "source_type": "direct_pdf",
                    "domain": domain,
                    "document_type": doc_type or "resolucion",
                    "cron_expr": "0 2 * * *",
                    "metadata": {
                        "title": title_hint or "Documento auto-descubierto",
                        "issuer": issuer,
                        "auto_discovered": True,
                    },
                })

            from src.ingestion.downloader import Downloader
            async with pool.connection() as conn:
                repo_run = IngestionRepository(conn)
                run_id = await repo_run.create_run(
                    triggered_by="background_worker",
                    source_filter=[fuente["name"]],
                    dry_run=False,
                )
            async with Downloader() as descargador:
                resultado = await process_source(
                    fuente,
                    pool=pool,
                    llm=llm,
                    downloader=descargador,
                    force=False,
                    dry_run=False,
                    run_id=run_id,
                )

            chunks_count = getattr(resultado, "chunks_indexed", 0) or 0
            cost = _calcular_costo(chunks_count)

            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE pending_sources
                        SET status='completed',
                            chunks_count=%s,
                            estimated_cost=%s,
                            processed_at=NOW()
                        WHERE id=%s
                        """,
                        (chunks_count, cost, cid),
                    )
                await _registrar_costo(
                    conn, docs=1, chunks=chunks_count, cost=cost
                )

            resultados.append({
                "url": url,
                "chunks": chunks_count,
                "cost": cost,
                "status": "ok",
            })
            logger.info(
                "Worker procesó %s: %d chunks, $%.4f",
                url, chunks_count, cost,
            )

        except Exception as exc:  # noqa: BLE001
            logger.warning("Worker falló procesando %s: %s", url, exc)
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE pending_sources
                        SET status='failed',
                            error_msg=%s,
                            processed_at=NOW()
                        WHERE id=%s
                        """,
                        (str(exc)[:500], cid),
                    )
            resultados.append({
                "url": url,
                "status": "failed",
                "error": str(exc)[:200],
            })

    return {
        "action": "processed",
        "docs_processed": len(candidatos),
        "results": resultados,
        "estado": estado,
    }
