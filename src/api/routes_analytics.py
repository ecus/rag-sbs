"""Analytics: consultas por usuario, memoria persistente."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

from src.core.deps import get_pool
from src.storage import query_log

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


class SessionRegister(BaseModel):
    alias: str
    user_agent: str | None = None


@router.post("/session")
async def registrar_session(
    payload: SessionRegister,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Registra o actualiza un alias de usuario."""
    alias = (payload.alias or "").strip()
    if not alias or len(alias) > 60:
        raise HTTPException(400, "alias requerido (1-60 chars)")
    await query_log.asegurar_session(pool, alias=alias, user_agent=payload.user_agent)
    return {"ok": True, "alias": alias}


@router.get("/users")
async def listar_usuarios(
    limit: int = 50,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> list[dict]:
    """Top usuarios con métricas agregadas."""
    return await query_log.resumen_por_usuario(pool, limit=limit)


@router.get("/user/{alias}/queries")
async def queries_de_usuario(
    alias: str,
    limit: int = 50,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> list[dict]:
    """Historial completo de un usuario."""
    return await query_log.queries_de_usuario(pool, alias=alias, limit=limit)


@router.get("/user/{alias}/memory")
async def memoria_usuario(
    alias: str,
    limit: int = 6,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> list[dict]:
    """Últimas N conversaciones para reconstruir memoria de sesión."""
    return await query_log.historial_reciente(pool, alias=alias, limit=limit)
