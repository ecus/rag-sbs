"""Registro de usuarios + encuesta de satisfacción."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

from src.core.deps import get_pool
from src.storage import users as users_store

router = APIRouter(prefix="/v1/users", tags=["users"])


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------

class RegistrationPayload(BaseModel):
    email: str = Field(..., min_length=5, max_length=180)
    name: str = Field(..., min_length=1, max_length=120)
    organization: str | None = Field(None, max_length=160)
    role: str | None = Field(None, max_length=80)


class LoginPayload(BaseModel):
    email: str


class SurveyPayload(BaseModel):
    user_id: str | None = None
    email: str | None = None
    rating_overall: int | None = Field(None, ge=1, le=5)
    rating_accuracy: int | None = Field(None, ge=1, le=5)
    rating_speed: int | None = Field(None, ge=1, le=5)
    rating_ux: int | None = Field(None, ge=1, le=5)
    use_case: str | None = None
    would_recommend: str | None = None       # "si"/"no"/"tal_vez"
    favorite_feature: str | None = None
    missing_feature: str | None = None
    comments: str | None = None
    session_duration_min: int | None = None
    n_queries_session: int | None = None
    closed_reason: str | None = "manual"     # "manual"/"timeout"/"browser"


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("/check")
async def check_email(
    email: str,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Verifica si un email existe (para validación en frontend)."""
    if not users_store.email_valido(email):
        return {"valid": False, "exists": False}
    existe = await users_store.email_existe(pool, email)
    return {"valid": True, "exists": existe}


@router.post("/register")
async def register(
    payload: RegistrationPayload,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Registra un nuevo usuario. Falla si el email ya existe."""
    user_id, error = await users_store.registrar_usuario(
        pool,
        email=payload.email,
        name=payload.name,
        organization=payload.organization,
        role=payload.role,
    )
    if error == "email_invalido":
        raise HTTPException(400, "El email no tiene un formato válido.")
    if error == "nombre_requerido":
        raise HTTPException(400, "El nombre es requerido.")
    if error == "email_duplicado":
        raise HTTPException(
            409, "Este email ya está registrado. Por favor inicie sesión."
        )
    if error or not user_id:
        raise HTTPException(500, "No se pudo registrar el usuario.")

    # Auto-login inmediato
    perfil = await users_store.login_usuario(pool, payload.email)
    return {"ok": True, "user": perfil}


@router.post("/login")
async def login(
    payload: LoginPayload,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Login por email. No requiere password (registro básico)."""
    if not users_store.email_valido(payload.email):
        raise HTTPException(400, "Email inválido.")
    perfil = await users_store.login_usuario(pool, payload.email)
    if not perfil:
        raise HTTPException(404, "Email no registrado. Por favor regístrese.")
    return {"ok": True, "user": perfil}


@router.post("/activity")
async def actividad(
    payload: dict,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Marca actividad (resetea timeout) — llamado periódicamente."""
    user_id = (payload or {}).get("user_id")
    if not user_id:
        return {"ok": False}
    await users_store.tocar_actividad(pool, user_id)
    return {"ok": True}


@router.post("/survey")
async def enviar_encuesta(
    payload: SurveyPayload,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Guarda la respuesta de la encuesta de salida."""
    data = payload.model_dump()
    sid = await users_store.guardar_encuesta(
        pool,
        user_id=payload.user_id,
        email=payload.email,
        payload=data,
    )
    if not sid:
        raise HTTPException(500, "No se pudo guardar la encuesta.")
    return {"ok": True, "id": sid}


@router.get("/survey/summary")
async def survey_summary(
    limit: int = 100,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Agregado de encuestas para analytics."""
    return await users_store.resumen_encuestas(pool, limit=limit)
