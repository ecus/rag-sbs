"""Conversaciones tipo ChatGPT: hilos separados por usuario.

Cada hilo agrupa mensajes (en query_log via conversation_id). El historial
que se reinyecta al LLM se limita por ventana (ver MAX_TURNOS_CONTEXTO en la
UI) para controlar el costo del LLM.
"""

from __future__ import annotations

import logging
from typing import Any

from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

TITULO_MAX = 70


def _titulo_desde_query(texto: str) -> str:
    """Genera un título corto desde la primera pregunta (sin gastar LLM)."""
    t = " ".join((texto or "").strip().split())
    if not t:
        return "Nueva conversación"
    return t[:TITULO_MAX] + ("…" if len(t) > TITULO_MAX else "")


async def crear_conversacion(
    pool: AsyncConnectionPool,
    *,
    user_id: str | None,
    email: str | None,
    titulo: str | None = None,
) -> dict | None:
    """Crea una conversación nueva. Retorna el dict de la conversación."""
    title = (titulo or "").strip() or "Nueva conversación"
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO conversations (user_id, email, title)
                    VALUES (%s, %s, %s)
                    RETURNING id, title, created_at, updated_at
                    """,
                    (user_id, email, title[:TITULO_MAX]),
                )
                row = await cur.fetchone()
                return {
                    "id": str(row[0]),
                    "title": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                    "updated_at": row[3].isoformat() if row[3] else None,
                    "n_mensajes": 0,
                }
    except Exception:  # noqa: BLE001
        logger.exception("crear_conversacion falló")
        return None


async def listar_conversaciones(
    pool: AsyncConnectionPool, email: str, limit: int = 50
) -> list[dict]:
    """Lista conversaciones de un usuario (no archivadas), más reciente primero."""
    if not email:
        return []
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       (SELECT COUNT(*) FROM query_log q
                        WHERE q.conversation_id = c.id) AS n_mensajes
                FROM conversations c
                WHERE LOWER(c.email) = LOWER(%s) AND c.archived = FALSE
                ORDER BY c.updated_at DESC
                LIMIT %s
                """,
                (email, limit),
            )
            filas = await cur.fetchall()
    return [
        {
            "id": str(r[0]),
            "title": r[1],
            "created_at": r[2].isoformat() if r[2] else None,
            "updated_at": r[3].isoformat() if r[3] else None,
            "n_mensajes": int(r[4] or 0),
        }
        for r in filas
    ]


async def mensajes_de_conversacion(
    pool: AsyncConnectionPool, conversation_id: str, limit: int = 100
) -> list[dict]:
    """Mensajes de una conversación en orden cronológico.

    Retorna [{rol:'user',texto}, {rol:'assistant',texto}, ...].
    """
    if not conversation_id:
        return []
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT query_text, answer_text
                FROM query_log
                WHERE conversation_id = %s
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (conversation_id, limit),
            )
            filas = await cur.fetchall()
    mensajes: list[dict] = []
    for q, a in filas:
        if q:
            mensajes.append({"rol": "user", "texto": q})
        if a:
            mensajes.append({"rol": "assistant", "texto": a})
    return mensajes


async def renombrar_conversacion(
    pool: AsyncConnectionPool, conversation_id: str, email: str, titulo: str
) -> bool:
    """Renombra una conversación (validando dueño por email)."""
    title = (titulo or "").strip()
    if not conversation_id or not title:
        return False
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE conversations SET title = %s, updated_at = NOW()
                WHERE id = %s AND LOWER(email) = LOWER(%s)
                """,
                (title[:TITULO_MAX], conversation_id, email),
            )
            return cur.rowcount > 0


async def borrar_conversacion(
    pool: AsyncConnectionPool, conversation_id: str, email: str
) -> bool:
    """Borra una conversación y sus mensajes (validando dueño)."""
    if not conversation_id:
        return False
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Borrar mensajes asociados primero (query_log no tiene cascade hard)
            await cur.execute(
                "DELETE FROM query_log WHERE conversation_id = %s", (conversation_id,)
            )
            await cur.execute(
                "DELETE FROM conversations WHERE id = %s AND LOWER(email) = LOWER(%s)",
                (conversation_id, email),
            )
            return cur.rowcount > 0


async def tocar_conversacion(
    pool: AsyncConnectionPool, conversation_id: str, *, titulo_si_vacio: str | None = None
) -> None:
    """Actualiza updated_at; si la conversación aún tiene título por defecto y
    se pasa titulo_si_vacio, lo fija (auto-título con la primera pregunta)."""
    if not conversation_id:
        return
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                if titulo_si_vacio:
                    await cur.execute(
                        """
                        UPDATE conversations
                        SET updated_at = NOW(),
                            title = CASE
                                WHEN title = 'Nueva conversación' THEN %s
                                ELSE title END
                        WHERE id = %s
                        """,
                        (_titulo_desde_query(titulo_si_vacio), conversation_id),
                    )
                else:
                    await cur.execute(
                        "UPDATE conversations SET updated_at = NOW() WHERE id = %s",
                        (conversation_id,),
                    )
    except Exception:  # noqa: BLE001
        logger.exception("tocar_conversacion falló")
