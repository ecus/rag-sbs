"""Seguridad de la API: admin key, rate limiting por IP, hash de PIN.

Sin dependencias externas — solo stdlib. Suficiente para una instancia única;
si algún día hay réplicas, mover el rate limiter a Redis.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


# =============================================================================
# Admin API key — protege endpoints de administración
# =============================================================================

def _admin_key() -> str | None:
    return os.environ.get("ADMIN_API_KEY") or None


def _admin_email() -> str:
    return os.environ.get("ADMIN_EMAIL", "eurrutia489@gmail.com").strip().lower()


def _token_secret() -> str:
    # Secreto para firmar el token de sesión admin. JWT_SECRET si existe,
    # si no la propia admin key (siempre hay uno u otro en prod).
    return os.environ.get("JWT_SECRET") or _admin_key() or "insecure-dev-secret"


def emitir_token_admin(email: str, ttl_seg: int = 8 * 3600) -> str:
    """Token de sesión admin firmado (HMAC-SHA256), sin dependencias externas.

    Se emite SOLO al hacer login la cuenta admin. Formato: base64(payload).sig
    """
    payload = {"email": email.strip().lower(), "exp": int(time.time()) + ttl_seg}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(_token_secret().encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def verificar_token_admin(token: str) -> bool:
    """Valida firma, expiración y que el email sea el admin."""
    try:
        raw, sig = token.split(".", 1)
        esperada = hmac.new(_token_secret().encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, esperada):
            return False
        pad = "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(raw + pad))
        if int(payload.get("exp", 0)) < int(time.time()):
            return False
        return payload.get("email") == _admin_email()
    except Exception:
        return False


async def verificar_admin(request: Request) -> None:
    """Dependency de endpoints admin. Acepta DOS formas de autenticación:

    1. `Authorization: Bearer <token>` — token de sesión admin (SPA React).
    2. `X-Admin-Key` con ADMIN_API_KEY — compatibilidad (UI Streamlit).

    Si ADMIN_API_KEY no está configurada, queda BLOQUEADO (fail-closed).
    """
    # 1. Token de sesión admin (Bearer)
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        if verificar_token_admin(auth[7:].strip()):
            return

    # 2. X-Admin-Key (retrocompatible)
    esperada = _admin_key()
    if not esperada:
        raise HTTPException(503, "Administración deshabilitada (ADMIN_API_KEY no configurada).")
    recibida = request.headers.get("x-admin-key", "")
    if not hmac.compare_digest(recibida, esperada):
        logger.warning(
            "Intento de acceso admin rechazado desde %s a %s",
            _ip_cliente(request), request.url.path,
        )
        raise HTTPException(401, "Clave de administración inválida.")


# =============================================================================
# Rate limiting — sliding window en memoria, por IP
# =============================================================================

def _ip_cliente(request: Request) -> str:
    """IP real del cliente (Caddy setea X-Real-IP)."""
    return (
        request.headers.get("x-real-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )


class _SlidingWindow:
    """Limita a `max_requests` por `window_sec` por clave (IP)."""

    def __init__(self, max_requests: int, window_sec: int) -> None:
        self.max_requests = max_requests
        self.window_sec = window_sec
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_gc = time.monotonic()

    def permitir(self, clave: str) -> tuple[bool, int]:
        """Retorna (permitido, segundos_para_reintentar)."""
        ahora = time.monotonic()
        cola = self._hits[clave]
        # Purga del propio bucket
        while cola and cola[0] <= ahora - self.window_sec:
            cola.popleft()
        # GC global cada 5 min para que IPs viejas no acumulen memoria
        if ahora - self._last_gc > 300:
            self._last_gc = ahora
            vacias = [k for k, v in self._hits.items() if not v]
            for k in vacias:
                del self._hits[k]
        if len(cola) >= self.max_requests:
            retry = int(cola[0] + self.window_sec - ahora) + 1
            return False, max(retry, 1)
        cola.append(ahora)
        return True, 0


# Límites por tipo de endpoint
_LIMITE_QUERY = _SlidingWindow(max_requests=10, window_sec=60)      # consultas LLM
_LIMITE_AUTH = _SlidingWindow(max_requests=10, window_sec=60)       # login/registro
_LIMITE_ENCUESTA = _SlidingWindow(max_requests=5, window_sec=300)   # encuestas


def _verificar_limite(limiter: _SlidingWindow, request: Request, nombre: str) -> None:
    ip = _ip_cliente(request)
    permitido, retry = limiter.permitir(ip)
    if not permitido:
        logger.warning("Rate limit %s excedido por %s", nombre, ip)
        raise HTTPException(
            429,
            f"Demasiadas solicitudes. Reintente en {retry} segundos.",
            headers={"Retry-After": str(retry)},
        )


async def limitar_query(request: Request) -> None:
    """Dependency: máx 10 consultas LLM por minuto por IP."""
    _verificar_limite(_LIMITE_QUERY, request, "query")


async def limitar_auth(request: Request) -> None:
    """Dependency: máx 10 intentos de login/registro por minuto por IP."""
    _verificar_limite(_LIMITE_AUTH, request, "auth")


async def limitar_encuesta(request: Request) -> None:
    """Dependency: máx 5 encuestas por 5 minutos por IP."""
    _verificar_limite(_LIMITE_ENCUESTA, request, "survey")


# =============================================================================
# PIN — hash con PBKDF2 (stdlib, sin dependencias)
# =============================================================================

_PBKDF2_ITERS = 200_000


def hashear_pin(pin: str) -> str:
    """Hash de PIN con salt aleatorio. Formato: pbkdf2$<iters>$<salt>$<hash>."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", pin.encode(), bytes.fromhex(salt), _PBKDF2_ITERS
    )
    return f"pbkdf2${_PBKDF2_ITERS}${salt}${dk.hex()}"


def verificar_pin(pin: str, almacenado: str | None) -> bool:
    """Compara un PIN contra el hash almacenado (constant-time)."""
    if not almacenado:
        return False
    try:
        _esquema, iters_s, salt, esperado = almacenado.split("$")
        dk = hashlib.pbkdf2_hmac(
            "sha256", pin.encode(), bytes.fromhex(salt), int(iters_s)
        )
        return hmac.compare_digest(dk.hex(), esperado)
    except (ValueError, TypeError):
        return False


def pin_valido(pin: str) -> bool:
    """PIN de 4 a 8 dígitos."""
    p = (pin or "").strip()
    return p.isdigit() and 4 <= len(p) <= 8


# =============================================================================
# Código de recuperación de PIN — un solo uso, se muestra una única vez
# =============================================================================

# Alfabeto sin caracteres ambiguos (sin 0/O, 1/I/L)
_ALFABETO_RECOVERY = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def generar_recovery_code() -> str:
    """Código legible tipo XXXX-XXXX (ej. 7K3M-9XQ2)."""
    chars = [secrets.choice(_ALFABETO_RECOVERY) for _ in range(8)]
    return f"{''.join(chars[:4])}-{''.join(chars[4:])}"


def normalizar_recovery_code(codigo: str) -> str:
    """Tolera minúsculas, espacios y guion faltante al ingresarlo."""
    limpio = (codigo or "").strip().upper().replace(" ", "").replace("-", "")
    if len(limpio) == 8:
        return f"{limpio[:4]}-{limpio[4:]}"
    return (codigo or "").strip().upper()
