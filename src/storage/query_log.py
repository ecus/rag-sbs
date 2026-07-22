"""Persistencia de consultas para analytics y memoria por usuario."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)


async def asegurar_session(
    pool: AsyncConnectionPool, alias: str, user_agent: str | None = None
) -> None:
    """Crea (o actualiza last_seen_at) de un alias de usuario."""
    if not alias:
        return
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO user_sessions (alias, user_agent)
                VALUES (%s, %s)
                ON CONFLICT (LOWER(alias)) DO UPDATE
                  SET last_seen_at = NOW()
                """,
                (alias, user_agent),
            )


async def log_query(
    pool: AsyncConnectionPool,
    *,
    alias: str,
    query_text: str,
    answer_text: str | None = None,
    confidence: str | None = None,
    n_sources: int = 0,
    latency_ms: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    options: dict[str, Any] | None = None,
    sources_summary: list[dict] | None = None,
    client_ip: str | None = None,
    conversation_id: str | None = None,
) -> UUID | None:
    """Registra una consulta + respuesta en query_log."""
    if not alias:
        return None
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO query_log
                      (alias, query_text, answer_text, confidence, n_sources,
                       latency_ms, tokens_in, tokens_out, options, sources_summary,
                       client_ip, conversation_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        alias, query_text, answer_text, confidence, n_sources,
                        latency_ms, tokens_in, tokens_out,
                        Jsonb(options or {}),
                        Jsonb(sources_summary or []),
                        client_ip, conversation_id,
                    ),
                )
                row = await cur.fetchone()
                return row[0] if row else None
    except Exception:  # noqa: BLE001
        logger.exception("query_log insert falló (alias=%s)", alias)
        return None


async def historial_reciente(
    pool: AsyncConnectionPool, alias: str, limit: int = 6
) -> list[dict]:
    """Últimas N consultas de un alias para reconstruir memoria.

    Retorna lista [{rol: 'user', texto}, {rol: 'assistant', texto}, ...]
    en orden cronológico (más viejo primero).
    """
    if not alias:
        return []
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT query_text, answer_text
                FROM query_log
                WHERE alias = %s AND answer_text IS NOT NULL
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (alias, limit),
            )
            filas = await cur.fetchall()
    # Orden cronológico (oldest first)
    filas.reverse()
    historial = []
    for q, a in filas:
        historial.append({"rol": "user", "texto": q})
        if a:
            historial.append({"rol": "assistant", "texto": a})
    return historial


async def resumen_por_usuario(
    pool: AsyncConnectionPool, limit: int = 20
) -> list[dict]:
    """Top usuarios con # consultas y última actividad."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT alias,
                       COUNT(*) AS total,
                       MAX(created_at) AS ultima,
                       SUM(CASE WHEN confidence='alta' THEN 1 ELSE 0 END) AS conf_alta,
                       SUM(CASE WHEN confidence='sin_evidencia' THEN 1 ELSE 0 END) AS sin_ev,
                       AVG(latency_ms) AS lat_avg
                FROM query_log
                GROUP BY alias
                ORDER BY ultima DESC
                LIMIT %s
                """,
                (limit,),
            )
            filas = await cur.fetchall()
    return [
        {
            "alias": r[0],
            "total": int(r[1]),
            "ultima": r[2].isoformat() if r[2] else None,
            "conf_alta": int(r[3] or 0),
            "sin_evidencia": int(r[4] or 0),
            "lat_avg_ms": int(r[5] or 0),
        }
        for r in filas
    ]


async def metricas_dashboard(pool: AsyncConnectionPool, dias: int = 30) -> dict:
    """Métricas para el dashboard admin (RF-015): consultas/día, temas top,
    documentos más referenciados, distribución de confianza."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Consultas por día
            await cur.execute(
                """
                SELECT date_trunc('day', created_at)::date AS dia, COUNT(*)
                FROM query_log
                WHERE created_at >= NOW() - (%s || ' days')::interval
                GROUP BY dia ORDER BY dia
                """,
                (dias,),
            )
            por_dia = [
                {"dia": r[0].isoformat(), "consultas": int(r[1])}
                for r in await cur.fetchall()
            ]

            # Documentos más referenciados (unnest de sources_summary)
            await cur.execute(
                """
                SELECT elem->>'title' AS titulo, COUNT(*) AS refs
                FROM query_log q,
                     jsonb_array_elements(q.sources_summary) elem
                WHERE q.created_at >= NOW() - (%s || ' days')::interval
                  AND elem->>'title' IS NOT NULL AND elem->>'title' <> ''
                GROUP BY titulo ORDER BY refs DESC LIMIT 15
                """,
                (dias,),
            )
            top_docs = [
                {"documento": r[0], "referencias": int(r[1])}
                for r in await cur.fetchall()
            ]

            # Temas / consultas más frecuentes
            await cur.execute(
                """
                SELECT LOWER(TRIM(query_text)) AS q, COUNT(*) AS n
                FROM query_log
                WHERE created_at >= NOW() - (%s || ' days')::interval
                  AND query_text IS NOT NULL AND LENGTH(TRIM(query_text)) > 3
                GROUP BY q ORDER BY n DESC, MAX(created_at) DESC LIMIT 15
                """,
                (dias,),
            )
            top_consultas = [
                {"consulta": r[0][:100], "veces": int(r[1])}
                for r in await cur.fetchall()
            ]

            # Distribución de confianza
            await cur.execute(
                """
                SELECT COALESCE(confidence, 's/d') AS c, COUNT(*)
                FROM query_log
                WHERE created_at >= NOW() - (%s || ' days')::interval
                GROUP BY c ORDER BY COUNT(*) DESC
                """,
                (dias,),
            )
            confianza = [
                {"confianza": r[0], "n": int(r[1])} for r in await cur.fetchall()
            ]

            # Totales
            await cur.execute(
                """
                SELECT COUNT(*), COUNT(DISTINCT LOWER(alias)),
                       ROUND(AVG(latency_ms))
                FROM query_log
                WHERE created_at >= NOW() - (%s || ' days')::interval
                """,
                (dias,),
            )
            tot = await cur.fetchone()

    return {
        "consultas_por_dia": por_dia,
        "top_documentos": top_docs,
        "top_consultas": top_consultas,
        "distribucion_confianza": confianza,
        "total_consultas": int(tot[0] or 0),
        "usuarios_activos": int(tot[1] or 0),
        "latencia_avg_ms": int(tot[2] or 0),
        "dias": dias,
    }


async def export_query_log(
    pool: AsyncConnectionPool, desde: str, hasta: str, limit: int = 50000
) -> list[dict]:
    """Exporta query_log en un rango de fechas (RNF-021). Formato tabular."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT created_at, alias, query_text, confidence, n_sources,
                       latency_ms, tokens_in, tokens_out, client_ip
                FROM query_log
                WHERE created_at >= %s::date AND created_at < (%s::date + INTERVAL '1 day')
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (desde, hasta, limit),
            )
            filas = await cur.fetchall()
    return [
        {
            "fecha": r[0].isoformat() if r[0] else "",
            "usuario": r[1] or "",
            "consulta": (r[2] or "").replace("\n", " "),
            "confianza": r[3] or "",
            "n_fuentes": int(r[4] or 0),
            "latencia_ms": int(r[5] or 0),
            "tokens_in": int(r[6] or 0),
            "tokens_out": int(r[7] or 0),
            "client_ip": r[8] or "",
        }
        for r in filas
    ]


async def queries_de_usuario(
    pool: AsyncConnectionPool, alias: str, limit: int = 50
) -> list[dict]:
    """Historial completo de un alias con metadatos."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, query_text, answer_text, confidence,
                       n_sources, latency_ms, options, created_at
                FROM query_log
                WHERE alias = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (alias, limit),
            )
            filas = await cur.fetchall()
    return [
        {
            "id": str(r[0]),
            "query": r[1],
            "answer": r[2],
            "confidence": r[3],
            "n_sources": int(r[4] or 0),
            "latency_ms": int(r[5] or 0),
            "options": r[6] or {},
            "created_at": r[7].isoformat() if r[7] else None,
        }
        for r in filas
    ]
