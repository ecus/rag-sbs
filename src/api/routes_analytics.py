"""Analytics: consultas por usuario, memoria persistente, dashboard, export."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

from src.core.deps import get_pool
from src.storage import query_log

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/dashboard")
async def dashboard(
    dias: int = 30,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Métricas para el dashboard admin (RF-015)."""
    dias = max(1, min(dias, 365))
    return await query_log.metricas_dashboard(pool, dias=dias)


@router.get("/export")
async def export_logs(
    desde: str,
    hasta: str,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> StreamingResponse:
    """Exporta el log de consultas por período a CSV (RNF-021).

    Fechas en formato YYYY-MM-DD (inclusive ambas).
    """
    filas = await query_log.export_query_log(pool, desde, hasta)
    buf = io.StringIO()
    campos = ["fecha", "usuario", "consulta", "confianza", "n_fuentes",
              "latencia_ms", "tokens_in", "tokens_out", "client_ip"]
    writer = csv.DictWriter(buf, fieldnames=campos)
    writer.writeheader()
    for f in filas:
        writer.writerow(f)
    buf.seek(0)
    nombre = f"consultas_{desde}_a_{hasta}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


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
