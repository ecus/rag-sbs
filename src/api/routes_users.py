"""Registro de usuarios + encuesta de satisfacción.

Seguridad:
- Login/registro con rate limit por IP (anti fuerza bruta).
- Login con email + PIN; respuesta genérica 401 (no revela si el email existe).
- Campo honeypot `website` en registro/encuesta (anti-bot básico).
- /survey/summary solo con X-Admin-Key.
- /me/delete: derecho de supresión (borra usuario + consultas, anonimiza encuestas).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, Field

from src.core.deps import get_pool
from src.core.security import limitar_auth, limitar_encuesta, verificar_admin
from src.storage import users as users_store

router = APIRouter(prefix="/v1/users", tags=["users"])


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------

class RegistrationPayload(BaseModel):
    email: str = Field(..., min_length=5, max_length=180)
    name: str = Field(..., min_length=1, max_length=120)
    pin: str = Field(..., min_length=4, max_length=8)
    organization: str | None = Field(None, max_length=160)
    role: str | None = Field(None, max_length=80)
    website: str | None = None  # honeypot — los humanos lo dejan vacío


class LoginPayload(BaseModel):
    email: str
    pin: str = Field(..., min_length=4, max_length=8)


class DeleteMePayload(BaseModel):
    email: str
    pin: str = Field(..., min_length=4, max_length=8)


class SurveyPayload(BaseModel):
    user_id: str | None = None
    email: str | None = None
    rating_overall: int | None = Field(None, ge=1, le=5)
    rating_accuracy: int | None = Field(None, ge=1, le=5)
    rating_speed: int | None = Field(None, ge=1, le=5)
    rating_ux: int | None = Field(None, ge=1, le=5)
    use_case: str | None = Field(None, max_length=500)
    would_recommend: str | None = Field(None, max_length=20)
    favorite_feature: str | None = Field(None, max_length=500)
    missing_feature: str | None = Field(None, max_length=500)
    comments: str | None = Field(None, max_length=2000)
    session_duration_min: int | None = Field(None, ge=0, le=24 * 60)
    n_queries_session: int | None = Field(None, ge=0, le=1000)
    closed_reason: str | None = "manual"     # "manual"/"timeout"/"browser"
    website: str | None = None  # honeypot


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("/register", dependencies=[Depends(limitar_auth)])
async def register(
    payload: RegistrationPayload,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Registra un nuevo usuario con PIN. Falla si el email ya existe."""
    if payload.website:
        # Honeypot rellenado → bot. Responder como éxito sin hacer nada.
        return {"ok": True, "user": None}

    user_id, error = await users_store.registrar_usuario(
        pool,
        email=payload.email,
        name=payload.name,
        pin=payload.pin,
        organization=payload.organization,
        role=payload.role,
    )
    if error == "email_invalido":
        raise HTTPException(400, "El email no tiene un formato válido.")
    if error == "nombre_requerido":
        raise HTTPException(400, "El nombre es requerido.")
    if error == "pin_invalido":
        raise HTTPException(400, "El PIN debe tener entre 4 y 8 dígitos.")
    if error == "email_duplicado":
        raise HTTPException(
            409, "Este email ya está registrado. Por favor inicie sesión."
        )
    if error or not user_id:
        raise HTTPException(500, "No se pudo registrar el usuario.")

    # Auto-login inmediato
    perfil, _ = await users_store.login_usuario(pool, payload.email, payload.pin)
    return {"ok": True, "user": perfil}


@router.post("/login", dependencies=[Depends(limitar_auth)])
async def login(
    payload: LoginPayload,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Login con email + PIN. Respuesta genérica si falla (anti-enumeración)."""
    perfil, error = await users_store.login_usuario(pool, payload.email, payload.pin)
    if error or not perfil:
        raise HTTPException(401, "Email o PIN incorrectos.")
    # Memoria persistente: se entrega solo tras autenticar con PIN
    from src.storage import query_log as _qlog
    memoria = await _qlog.historial_reciente(pool, perfil["email"], limit=20)
    return {"ok": True, "user": perfil, "memory": memoria}


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


@router.post("/survey", dependencies=[Depends(limitar_encuesta)])
async def enviar_encuesta(
    payload: SurveyPayload,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Guarda la respuesta de la encuesta de salida."""
    if payload.website:
        return {"ok": True, "id": None}  # honeypot → descartar silencioso

    data = payload.model_dump(exclude={"website"})
    sid = await users_store.guardar_encuesta(
        pool,
        user_id=payload.user_id,
        email=payload.email,
        payload=data,
    )
    if not sid:
        raise HTTPException(500, "No se pudo guardar la encuesta.")
    return {"ok": True, "id": sid}


@router.post("/me/delete", dependencies=[Depends(limitar_auth)])
async def borrar_mis_datos(
    payload: DeleteMePayload,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Derecho de supresión: borra usuario + historial de consultas.

    Las encuestas quedan anonimizadas (sin email ni user_id) para
    conservar las métricas agregadas de calidad.
    """
    ok, error = await users_store.borrar_usuario(pool, payload.email, payload.pin)
    if not ok:
        raise HTTPException(401, "Email o PIN incorrectos.")
    return {"ok": True}


@router.get("/survey/summary", dependencies=[Depends(verificar_admin)])
async def survey_summary(
    limit: int = 100,
    pool: AsyncConnectionPool = Depends(get_pool),
) -> dict:
    """Agregado de encuestas — solo administración (X-Admin-Key)."""
    return await users_store.resumen_encuestas(pool, limit=limit)
