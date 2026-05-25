"""GET /v1/health — checks de componentes."""

from fastapi import APIRouter, Depends, status
from psycopg_pool import AsyncConnectionPool

from src import __version__
from src.core.deps import get_llm, get_pool
from src.llm import LLMProvider

router = APIRouter(tags=["operational"])


@router.get("/v1/health")
async def health(
    pool: AsyncConnectionPool = Depends(get_pool),
    llm: LLMProvider = Depends(get_llm),
) -> dict:
    """Checa que DB y LLM provider estén disponibles.

    Retorna 200 con status="healthy" si todos OK,
    200 con status="degraded" si alguno falla (no 503 — degradación graceful).
    """
    chequeos: dict[str, str] = {}

    # DB
    try:
        async with pool.connection() as conn, conn.cursor() as cursor:
            await cursor.execute("SELECT 1")
            await cursor.fetchone()
        chequeos["db"] = "ok"
    except Exception as exc:  # noqa: BLE001
        chequeos["db"] = f"error: {type(exc).__name__}"

    # LLM
    try:
        ok = await llm.health()
        chequeos["llm"] = "ok" if ok else "unreachable"
    except Exception as exc:  # noqa: BLE001
        chequeos["llm"] = f"error: {type(exc).__name__}"

    estado_global = "healthy" if all(v == "ok" for v in chequeos.values()) else "degraded"

    return {
        "status": estado_global,
        "version": __version__,
        "checks": chequeos,
    }


@router.get("/v1/health/live", status_code=status.HTTP_200_OK)
async def liveness() -> dict:
    """Liveness probe (Kubernetes/Cloud Run): el proceso responde."""
    return {"status": "alive"}
