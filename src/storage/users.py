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
    pin: str,
    organization: str | None = None,
    role: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Crea un usuario nuevo con PIN. Retorna (user_id, error, recovery_code).

    El recovery_code se retorna en texto plano UNA sola vez (se guarda
    hasheado); el caller debe mostrárselo al usuario para que lo guarde.
    """
    from src.core.security import (
        generar_recovery_code,
        hashear_pin,
        pin_valido,
    )

    email = (email or "").strip()
    name = (name or "").strip()

    if not email_valido(email):
        return None, "email_invalido", None
    if not name:
        return None, "nombre_requerido", None
    if not pin_valido(pin):
        return None, "pin_invalido", None

    recovery_code = generar_recovery_code()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO users
                      (email, name, organization, role, pin_hash, recovery_code_hash)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        email, name, organization, role,
                        hashear_pin(pin.strip()),
                        hashear_pin(recovery_code),
                    ),
                )
                row = await cur.fetchone()
                return (str(row[0]) if row else None), None, recovery_code
    except Exception as e:  # noqa: BLE001
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            return None, "email_duplicado", None
        logger.exception("registrar_usuario falló")
        return None, "error_interno", None


async def login_usuario(
    pool: AsyncConnectionPool, email: str, pin: str
) -> tuple[dict | None, str | None]:
    """Login con email + PIN. Retorna (perfil, error).

    Bootstrap: si el usuario existe pero no tiene PIN (legacy de la
    migración 006, o tras un reset de admin), el primer login fija el PIN
    provisto y genera un recovery_code nuevo que se incluye en el perfil
    bajo la clave "recovery_code" (única vez que viaja en texto plano).
    """
    from src.core.security import (
        generar_recovery_code,
        hashear_pin,
        pin_valido,
        verificar_pin,
    )

    if not email_valido(email) or not pin_valido(pin):
        return None, "credenciales_invalidas"

    recovery_nuevo: str | None = None
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, pin_hash FROM users
                WHERE LOWER(email) = LOWER(%s)
                """,
                (email,),
            )
            row = await cur.fetchone()
            if not row:
                # Mensaje genérico — no revelar si el email existe
                return None, "credenciales_invalidas"
            uid, pin_hash = str(row[0]), row[1]

            if pin_hash is None:
                # Usuario legacy o post-reset: este login define su PIN
                recovery_nuevo = generar_recovery_code()
                await cur.execute(
                    "UPDATE users SET pin_hash = %s, recovery_code_hash = %s WHERE id = %s",
                    (hashear_pin(pin.strip()), hashear_pin(recovery_nuevo), uid),
                )
            elif not verificar_pin(pin.strip(), pin_hash):
                return None, "credenciales_invalidas"

            await cur.execute(
                """
                UPDATE users
                SET last_login_at = NOW(),
                    last_activity_at = NOW(),
                    n_sessions = n_sessions + 1
                WHERE id = %s
                RETURNING id, email, name, organization, role, n_queries_total,
                          status, daily_query_limit
                """,
                (uid,),
            )
            row = await cur.fetchone()
            if not row:
                return None, "credenciales_invalidas"
            perfil = {
                "id": str(row[0]),
                "email": row[1],
                "name": row[2],
                "organization": row[3],
                "role": row[4],
                "n_queries_total": int(row[5] or 0),
                "status": row[6],
                "daily_query_limit": int(row[7] or 0),
            }
            if recovery_nuevo:
                perfil["recovery_code"] = recovery_nuevo
            return perfil, None


async def recuperar_pin(
    pool: AsyncConnectionPool, email: str, recovery_code: str, nuevo_pin: str
) -> tuple[bool, str | None, str | None]:
    """Resetea el PIN usando el código de recuperación.

    El código es de UN solo uso: al usarse se rota y el nuevo se retorna
    en texto plano para que el usuario lo guarde.
    Retorna (ok, error, nuevo_recovery_code).
    """
    from src.core.security import (
        generar_recovery_code,
        hashear_pin,
        normalizar_recovery_code,
        pin_valido,
        verificar_pin,
    )

    if not email_valido(email) or not pin_valido(nuevo_pin):
        return False, "credenciales_invalidas", None

    codigo = normalizar_recovery_code(recovery_code)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, recovery_code_hash FROM users WHERE LOWER(email) = LOWER(%s)",
                (email,),
            )
            row = await cur.fetchone()
            if not row or not row[1] or not verificar_pin(codigo, row[1]):
                # Genérico: no revelar si el email existe o si el código expiró
                return False, "credenciales_invalidas", None
            uid = str(row[0])

            nuevo_codigo = generar_recovery_code()
            await cur.execute(
                """
                UPDATE users
                SET pin_hash = %s, recovery_code_hash = %s
                WHERE id = %s
                """,
                (hashear_pin(nuevo_pin.strip()), hashear_pin(nuevo_codigo), uid),
            )
            logger.info("PIN recuperado con código para user %s", uid)
            return True, None, nuevo_codigo


async def admin_reset_pin(
    pool: AsyncConnectionPool, email: str
) -> tuple[bool, str | None]:
    """Reset de admin: borra el PIN (el próximo login lo define de nuevo).

    Invalida también el recovery_code anterior. Retorna (ok, error).
    """
    if not email_valido(email):
        return False, "email_invalido"
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE users
                SET pin_hash = NULL, recovery_code_hash = NULL
                WHERE LOWER(email) = LOWER(%s)
                RETURNING id
                """,
                (email,),
            )
            row = await cur.fetchone()
            if not row:
                return False, "no_encontrado"
            logger.info("PIN reseteado por admin para user %s", row[0])
            return True, None


async def borrar_usuario(
    pool: AsyncConnectionPool, email: str, pin: str
) -> tuple[bool, str | None]:
    """Borra al usuario y sus consultas (derecho de supresión, Ley 29733).

    Las encuestas se conservan anonimizadas (user_id queda NULL por el FK
    ON DELETE SET NULL; el email denormalizado se limpia explícitamente).
    """
    from src.core.security import pin_valido, verificar_pin

    if not email_valido(email) or not pin_valido(pin):
        return False, "credenciales_invalidas"

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, pin_hash FROM users WHERE LOWER(email) = LOWER(%s)",
                (email,),
            )
            row = await cur.fetchone()
            if not row or not verificar_pin(pin.strip(), row[1]):
                return False, "credenciales_invalidas"
            uid = str(row[0])

            # Anonimizar encuestas (conservar métricas agregadas sin PII)
            await cur.execute(
                "UPDATE feedback_surveys SET email = NULL WHERE user_id = %s",
                (uid,),
            )
            # Borrar el feedback like/dislike (contiene email + pregunta + comentario)
            await cur.execute(
                "DELETE FROM response_feedback WHERE LOWER(email) = LOWER(%s)",
                (email,),
            )
            # Borrar historial de consultas (alias = email en query_log)
            await cur.execute(
                "DELETE FROM query_log WHERE LOWER(alias) = LOWER(%s)",
                (email,),
            )
            await cur.execute(
                "DELETE FROM user_sessions WHERE LOWER(alias) = LOWER(%s)",
                (email,),
            )
            # Borrar conversaciones del usuario (por email, además del cascade por FK)
            await cur.execute(
                "DELETE FROM conversations WHERE LOWER(email) = LOWER(%s)",
                (email,),
            )
            # Borrar el usuario (FK pone user_id NULL en surveys / cascade en conv)
            await cur.execute("DELETE FROM users WHERE id = %s", (uid,))
            logger.info("Usuario %s eliminado a pedido (derecho de supresión)", uid)
            return True, None


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


async def estado_acceso(pool: AsyncConnectionPool, email: str) -> dict | None:
    """Devuelve {status, daily_query_limit, usadas_hoy} para gating de acceso."""
    if not email_valido(email):
        return None
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT u.status, u.daily_query_limit,
                       (SELECT COUNT(*) FROM query_log q
                        WHERE LOWER(q.alias) = LOWER(u.email)
                          AND q.created_at >= date_trunc('day', NOW())) AS usadas_hoy
                FROM users u
                WHERE LOWER(u.email) = LOWER(%s)
                """,
                (email,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "status": row[0],
                "daily_query_limit": int(row[1] or 0),
                "usadas_hoy": int(row[2] or 0),
            }


async def listar_pendientes(pool: AsyncConnectionPool, limit: int = 100) -> list[dict]:
    """Usuarios con status='pending' para que el admin apruebe."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, email, name, organization, role, created_at
                FROM users WHERE status = 'pending'
                ORDER BY created_at ASC LIMIT %s
                """,
                (limit,),
            )
            filas = await cur.fetchall()
    return [
        {
            "id": str(r[0]), "email": r[1], "name": r[2],
            "organization": r[3], "role": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
        }
        for r in filas
    ]


async def set_status_usuario(
    pool: AsyncConnectionPool, email: str, status: str
) -> bool:
    """Aprueba o rechaza un usuario (status in 'approved'/'rejected'/'pending')."""
    if status not in ("approved", "rejected", "pending"):
        return False
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE users
                SET status = %s,
                    approved_at = CASE WHEN %s = 'approved' THEN NOW() ELSE approved_at END
                WHERE LOWER(email) = LOWER(%s)
                """,
                (status, status, email),
            )
            return cur.rowcount > 0


async def set_limite_diario(
    pool: AsyncConnectionPool, email: str, limite: int
) -> bool:
    """Ajusta el límite de consultas por día de un usuario."""
    if limite < 0:
        return False
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE users SET daily_query_limit = %s WHERE LOWER(email) = LOWER(%s)",
                (limite, email),
            )
            return cur.rowcount > 0


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
