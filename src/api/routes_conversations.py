"""Conversaciones tipo ChatGPT — CRUD por usuario.

El alcance se valida por email (el usuario ya está autenticado por PIN en
la UI). Rate-limited con el limitador de auth para evitar abuso.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

from src.core.deps import get_pool
from src.core.security import limitar_auth
from src.storage import conversations as conv_store

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


class CrearPayload(BaseModel):
    user_id: str | None = None
    email: str = Field(..., min_length=5, max_length=180)
    title: str | None = Field(None, max_length=120)


class RenombrarPayload(BaseModel):
    email: str
    title: str = Field(..., min_length=1, max_length=120)


class BorrarPayload(BaseModel):
    email: str


@router.get("")
async def listar(
    email: str,
    limit: int = 50,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> list[dict]:
    """Lista las conversaciones del usuario."""
    return await conv_store.listar_conversaciones(pool, email, limit=limit)


@router.post("", dependencies=[Depends(limitar_auth)])
async def crear(
    payload: CrearPayload,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Crea una conversación nueva."""
    conv = await conv_store.crear_conversacion(
        pool, user_id=payload.user_id, email=payload.email, titulo=payload.title
    )
    if not conv:
        raise HTTPException(500, "No se pudo crear la conversación.")
    return conv


@router.get("/{conversation_id}/messages")
async def mensajes(
    conversation_id: str,
    limit: int = 100,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> list[dict]:
    """Mensajes de una conversación en orden cronológico."""
    return await conv_store.mensajes_de_conversacion(pool, conversation_id, limit=limit)


@router.patch("/{conversation_id}")
async def renombrar(
    conversation_id: str,
    payload: RenombrarPayload,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Renombra una conversación."""
    ok = await conv_store.renombrar_conversacion(
        pool, conversation_id, payload.email, payload.title
    )
    if not ok:
        raise HTTPException(404, "Conversación no encontrada.")
    return {"ok": True}


@router.delete("/{conversation_id}")
async def borrar(
    conversation_id: str,
    payload: BorrarPayload,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Borra una conversación y sus mensajes."""
    ok = await conv_store.borrar_conversacion(pool, conversation_id, payload.email)
    if not ok:
        raise HTTPException(404, "Conversación no encontrada.")
    return {"ok": True}
