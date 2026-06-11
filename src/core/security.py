"""Seguridad de la API: admin key, rate limiting por IP, hash de PIN.

Sin dependencias externas — solo stdlib. Suficiente para una instancia única;
si algún día hay réplicas, mover el rate limiter a Redis.
"""

from __future__ import annotations

import hashlib
import hmac
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


async def verificar_admin(request: Request) -> None:
    """Dependency: exige header X-Admin-Key con la clave de ADMIN_API_KEY.

    Si ADMIN_API_KEY no está configurada, los endpoints admin quedan
    BLOQUEADOS (fail-closed), no abiertos.
    """
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
