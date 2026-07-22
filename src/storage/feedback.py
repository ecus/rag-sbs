"""Feedback por respuesta (like/dislike + comentario) y settings globales."""

from __future__ import annotations

import logging

from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)


async def guardar_voto(
    pool: AsyncConnectionPool,
    *,
    email: str | None,
    conversation_id: str | None,
    question: str | None,
    answer: str | None,
    vote: str,
    comment: str | None = None,
) -> str | None:
    """Registra un like/dislike de una respuesta."""
    if vote not in ("up", "down"):
        return None
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO response_feedback
                      (email, conversation_id, question, answer, vote, comment)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        email, conversation_id,
                        (question or "")[:2000], (answer or "")[:6000],
                        vote, (comment or None),
                    ),
                )
                row = await cur.fetchone()
                return str(row[0]) if row else None
    except Exception:  # noqa: BLE001
        logger.exception("guardar_voto falló")
        return None


async def resumen_feedback(pool: AsyncConnectionPool, limit: int = 100) -> dict:
    """Agregado de feedback + los dislikes con comentario para revisar."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                  SUM(CASE WHEN vote='up' THEN 1 ELSE 0 END) AS likes,
                  SUM(CASE WHEN vote='down' THEN 1 ELSE 0 END) AS dislikes
                FROM response_feedback
                """
            )
            agg = await cur.fetchone()
            await cur.execute(
                """
                SELECT email, question, answer, comment, created_at
                FROM response_feedback
                WHERE vote = 'down'
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            filas = await cur.fetchall()
    return {
        "likes": int(agg[0] or 0),
        "dislikes": int(agg[1] or 0),
        "dislikes_detalle": [
            {
                "email": r[0],
                "question": r[1],
                "answer": (r[2] or "")[:400],
                "comment": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in filas
        ],
    }


# ---------------------------------------------------------------------------
# Settings globales
# ---------------------------------------------------------------------------

async def get_setting(pool: AsyncConnectionPool, key: str, default: str = "0") -> str:
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
            row = await cur.fetchone()
            return row[0] if row else default


async def get_settings(pool: AsyncConnectionPool) -> dict:
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT key, value FROM app_settings")
            filas = await cur.fetchall()
    return {k: v for k, v in filas}


async def set_setting(pool: AsyncConnectionPool, key: str, value: str) -> None:
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = NOW()
                """,
                (key, value, value),
            )


async def conteos_globales(pool: AsyncConnectionPool) -> tuple[int, int]:
    """(consultas_hoy, consultas_ultima_hora) globales para límites."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                  COUNT(*) FILTER (WHERE created_at >= date_trunc('day', NOW())),
                  COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 hour')
                FROM query_log
                """
            )
            row = await cur.fetchone()
            return int(row[0] or 0), int(row[1] or 0)
