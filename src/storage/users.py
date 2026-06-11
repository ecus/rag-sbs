"""Registro de usuarios (email único) + encuestas de satisfacción."""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def email_valido(email: str) -> bool:
    return bool(EMAIL_RE.match((email or "").strip()))


async def email_existe(pool: AsyncConnectionPool, email: str) -> bool:
    """Verifica si un email ya está registrado (case-insensitive)."""
    if not email:
        return False
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM users WHERE LOWER(email) = LOWER(%s) LIMIT 1",
                (email,),
            )
            return (await cur.fetchone()) is not None


async def registrar_usuario(
    pool: AsyncConnectionPool,
    *,
    email: str,
    name: str,
    organization: str | None = None,
    role: str | None = None,
) -> tuple[str | None, str | None]:
    """Crea un usuario nuevo. Retorna (user_id, error)."""
    email = (email or "").strip()
    name = (name or "").strip()

    if not email_valido(email):
        return None, "email_invalido"
    if not name:
        return None, "nombre_requerido"

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO users (email, name, organization, role)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (email, name, organization, role),
                )
                row = await cur.fetchone()
                return (str(row[0]) if row else None), None
    except Exception as e:  # noqa: BLE001
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            return None, "email_duplicado"
        logger.exception("registrar_usuario falló")
        return None, "error_interno"


async def login_usuario(
    pool: AsyncConnectionPool, email: str
) -> dict | None:
    """Hace login por email. Actualiza last_login y n_sessions."""
    if not email_valido(email):
        return None
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE users
                SET last_login_at = NOW(),
                    last_activity_at = NOW(),
                    n_sessions = n_sessions + 1
                WHERE LOWER(email) = LOWER(%s)
                RETURNING id, email, name, organization, role, n_queries_total
                """,
                (email,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "id": str(row[0]),
                "email": row[1],
                "name": row[2],
                "organization": row[3],
                "role": row[4],
                "n_queries_total": int(row[5] or 0),
            }


async def tocar_actividad(pool: AsyncConnectionPool, user_id: str) -> None:
    """Actualiza solo last_activity_at del usuario (para timeout).

    NO incrementa contadores — usar `incrementar_queries` para eso.
    """
    if not user_id:
        return
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE users SET last_activity_at = NOW() WHERE id = %s",
                    (user_id,),
                )
    except Exception:  # noqa: BLE001
        logger.exception("tocar_actividad falló user_id=%s", user_id)


async def incrementar_queries(pool: AsyncConnectionPool, email: str) -> None:
    """Incrementa n_queries_total al registrar una consulta real."""
    if not email:
        return
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE users
                    SET n_queries_total = n_queries_total + 1,
                        last_activity_at = NOW()
                    WHERE LOWER(email) = LOWER(%s)
                    """,
                    (email,),
                )
    except Exception:  # noqa: BLE001
        logger.exception("incrementar_queries falló email=%s", email)


async def guardar_encuesta(
    pool: AsyncConnectionPool,
    *,
    user_id: str | None,
    email: str | None,
    payload: dict[str, Any],
) -> str | None:
    """Persiste una respuesta de la encuesta."""
    def _int_1_5(v: Any) -> int | None:
        try:
            n = int(v)
            return n if 1 <= n <= 5 else None
        except (TypeError, ValueError):
            return None

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO feedback_surveys
                      (user_id, email,
                       rating_overall, rating_accuracy, rating_speed, rating_ux,
                       use_case, would_recommend, favorite_feature, missing_feature, comments,
                       session_duration_min, n_queries_session, closed_reason)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id, email,
                        _int_1_5(payload.get("rating_overall")),
                        _int_1_5(payload.get("rating_accuracy")),
                        _int_1_5(payload.get("rating_speed")),
                        _int_1_5(payload.get("rating_ux")),
                        payload.get("use_case"),
                        payload.get("would_recommend"),
                        payload.get("favorite_feature"),
                        payload.get("missing_feature"),
                        payload.get("comments"),
                        payload.get("session_duration_min"),
                        payload.get("n_queries_session"),
                        payload.get("closed_reason") or "manual",
                    ),
                )
                row = await cur.fetchone()
                return str(row[0]) if row else None
    except Exception:  # noqa: BLE001
        logger.exception("guardar_encuesta falló")
        return None


async def resumen_encuestas(pool: AsyncConnectionPool, limit: int = 100) -> dict:
    """Métricas agregadas de las encuestas para analytics."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                  COUNT(*) AS n,
                  AVG(rating_overall) AS avg_overall,
                  AVG(rating_accuracy) AS avg_accuracy,
                  AVG(rating_speed) AS avg_speed,
                  AVG(rating_ux) AS avg_ux,
                  SUM(CASE WHEN would_recommend = 'si' THEN 1 ELSE 0 END) AS rec_si,
                  SUM(CASE WHEN would_recommend = 'no' THEN 1 ELSE 0 END) AS rec_no,
                  SUM(CASE WHEN would_recommend = 'tal_vez' THEN 1 ELSE 0 END) AS rec_tv
                FROM feedback_surveys
                """,
            )
            agg = await cur.fetchone()

            await cur.execute(
                """
                SELECT id, email, rating_overall, comments, missing_feature,
                       use_case, would_recommend, created_at
                FROM feedback_surveys
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            filas = await cur.fetchall()

    return {
        "total": int(agg[0] or 0),
        "avg_overall": round(float(agg[1] or 0), 2),
        "avg_accuracy": round(float(agg[2] or 0), 2),
        "avg_speed": round(float(agg[3] or 0), 2),
        "avg_ux": round(float(agg[4] or 0), 2),
        "recomendaria_si": int(agg[5] or 0),
        "recomendaria_no": int(agg[6] or 0),
        "recomendaria_tal_vez": int(agg[7] or 0),
        "recientes": [
            {
                "id": str(r[0]),
                "email": r[1],
                "rating": int(r[2] or 0),
                "comments": r[3],
                "missing": r[4],
                "use_case": r[5],
                "recommend": r[6],
                "created_at": r[7].isoformat() if r[7] else None,
            }
            for r in filas
        ],
    }
