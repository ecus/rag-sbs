"""Endpoints del worker de ingesta en background.

- GET  /v1/background/status   → métricas live (costo, docs, cola, caps)
- POST /v1/background/start    → enabled=true
- POST /v1/background/pause    → enabled=false
- POST /v1/background/scrape   → dispara descubrimiento manual (SBS/BCRP)
- POST /v1/background/tick     → ejecuta una iteración del worker ya
- POST /v1/background/config   → actualiza un cap (max_docs_total, max_cost_*)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

from src.core.deps import get_llm, get_pool
from src.ingestion.background_worker import _estado_actual, _leer_config, tick
from src.llm import LLMProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/background", tags=["background"])


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

async def _set_config(pool: AsyncConnectionPool, key: str, value: Any) -> None:
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO background_config (key, value, updated_at)
                VALUES (%s, %s::jsonb, NOW())
                ON CONFLICT (key) DO UPDATE
                  SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (key, json.dumps(value)),
            )


async def _insertar_descubiertas(
    pool: AsyncConnectionPool, fuentes: list[Any], discovered_by: str
) -> int:
    insertados = 0
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            for f in fuentes:
                try:
                    await cur.execute(
                        """
                        INSERT INTO pending_sources
                          (url, name_hint, title_hint, issuer, document_type,
                           domain, discovered_by, priority)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (url) DO NOTHING
                        """,
                        (
                            f.url, f.name_hint, f.title_hint, f.issuer,
                            f.document_type, f.domain, discovered_by, f.priority,
                        ),
                    )
                    if cur.rowcount > 0:
                        insertados += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("No se pudo insertar %s: %s", f.url, exc)
    return insertados


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("/status")
async def status_background(
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    async with pool.connection() as conn:
        cfg = await _leer_config(conn)
        estado = await _estado_actual(conn)
    return {"config": cfg, "estado": estado}


@router.post("/start")
async def start_background(
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    await _set_config(pool, "enabled", True)
    return {"ok": True, "enabled": True}


@router.post("/pause")
async def pause_background(
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    await _set_config(pool, "enabled", False)
    return {"ok": True, "enabled": False}


class ConfigUpdate(BaseModel):
    key: str
    value: Any


@router.post("/config")
async def update_config(
    update: ConfigUpdate,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    permitidos = {
        "enabled", "max_docs_total", "max_cost_total", "max_cost_daily",
        "docs_per_tick", "schedule_until",
    }
    if update.key not in permitidos:
        raise HTTPException(400, f"Key no permitida: {update.key}")
    await _set_config(pool, update.key, update.value)
    return {"ok": True, "key": update.key, "value": update.value}


class ScrapeRequest(BaseModel):
    sbs: bool = True
    bcrp: bool = True
    max_urls_sbs: int = 800
    max_urls_bcrp: int = 200
    verify_http: bool = True
    max_candidatos_sbs: int = 30000
    concurrencia_sbs: int = 30


@router.post("/scrape")
async def scrape_now(
    req: ScrapeRequest,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Dispara los scrapers SBS/BCRP y encola lo descubierto."""
    resumen: dict[str, int] = {}
    if req.sbs:
        from src.ingestion.scrapers.sbs import descubrir_sbs
        fuentes = await descubrir_sbs(
            max_urls=req.max_urls_sbs,
            verify_http=req.verify_http,
            max_candidatos=req.max_candidatos_sbs,
            concurrencia=req.concurrencia_sbs,
        )
        resumen["sbs_descubiertas"] = len(fuentes)
        resumen["sbs_encoladas"] = await _insertar_descubiertas(
            pool, fuentes, discovered_by="scraper:sbs"
        )
    if req.bcrp:
        from src.ingestion.scrapers.bcrp import descubrir_bcrp
        fuentes = await descubrir_bcrp(
            max_urls=req.max_urls_bcrp, verify_http=req.verify_http
        )
        resumen["bcrp_descubiertas"] = len(fuentes)
        resumen["bcrp_encoladas"] = await _insertar_descubiertas(
            pool, fuentes, discovered_by="scraper:bcrp"
        )
    return {"ok": True, "resumen": resumen}


@router.post("/tick")
async def tick_now(
    pool: AsyncConnectionPool = Depends(get_pool),
    llm: LLMProvider = Depends(get_llm),
) -> dict:
    """Ejecuta una iteración del worker inmediatamente (debug/manual)."""
    resultado = await tick(pool=pool, llm=llm)
    return resultado
