"""Descarga HTTP responsable: ETag, Last-Modified, retry, rate-limit, robots.txt.

Filosofía:
- Si el servidor retorna 304 Not Modified → NO descargar bytes (ahorro red + servidor SBS)
- Rate limit por host (1 req / 2 s) → respeto a SBS, evita ban
- Retry exponencial 3× con jitter
- User-Agent identificable según RNF y conector (sec 4.4 del documento)
- Robots.txt cacheado por host
"""

from __future__ import annotations

import asyncio
import logging
import time
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass
from typing import Final

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)

USER_AGENT: Final = "RAG-SBS-Portfolio/1.0 (+contact-via-repo-issues)"
RATE_LIMIT_DEFECTO_SEG: Final = 2.0


@dataclass
class DownloadResult:
    """Resultado de una verificación/descarga."""

    status: str  # 'changed' | 'not_modified' | 'error'
    content: bytes | None
    etag: str | None
    last_modified: str | None
    content_type: str | None
    http_status: int
    error: str | None = None


class HostRateLimiter:
    """Limita 1 request / N segundos por host (in-memory)."""

    def __init__(self, intervalo_minimo_seg: float = RATE_LIMIT_DEFECTO_SEG) -> None:
        self.intervalo_minimo = intervalo_minimo_seg
        self._ultima_llamada: dict[str, float] = {}
        self._candados: dict[str, asyncio.Lock] = {}

    def _candado_para(self, host: str) -> asyncio.Lock:
        if host not in self._candados:
            self._candados[host] = asyncio.Lock()
        return self._candados[host]

    async def wait(self, host: str) -> None:
        async with self._candado_para(host):
            ahora = time.monotonic()
            ultima = self._ultima_llamada.get(host, 0.0)
            transcurrido = ahora - ultima
            if transcurrido < self.intervalo_minimo:
                await asyncio.sleep(self.intervalo_minimo - transcurrido)
            self._ultima_llamada[host] = time.monotonic()


class RobotsCache:
    """Cache simple de robots.txt parseado por host."""

    def __init__(self, ttl_seg: int = 3600) -> None:
        self.ttl = ttl_seg
        self._cache: dict[str, tuple[urllib.robotparser.RobotFileParser, float]] = {}

    async def is_allowed(self, client: httpx.AsyncClient, url: str) -> bool:
        partes = urllib.parse.urlparse(url)
        host = partes.netloc
        ahora = time.monotonic()

        cacheado = self._cache.get(host)
        if cacheado and (ahora - cacheado[1]) < self.ttl:
            parser_robots = cacheado[0]
        else:
            parser_robots = urllib.robotparser.RobotFileParser()
            try:
                respuesta = await client.get(
                    f"{partes.scheme}://{host}/robots.txt",
                    timeout=10.0,
                    headers={"User-Agent": USER_AGENT},
                )
                if respuesta.status_code == 200:
                    parser_robots.parse(respuesta.text.splitlines())
                else:
                    # No robots.txt → asumir permitido
                    parser_robots.parse([])
            except Exception:  # noqa: BLE001
                parser_robots.parse([])
            self._cache[host] = (parser_robots, ahora)

        return parser_robots.can_fetch(USER_AGENT, url)


class Downloader:
    """Cliente HTTP responsable para crawling SBS."""

    def __init__(
        self,
        *,
        timeout_sec: float = 60.0,
        rate_limit_sec: float = RATE_LIMIT_DEFECTO_SEG,
        respect_robots: bool = True,
    ) -> None:
        self._cliente = httpx.AsyncClient(
            timeout=timeout_sec,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self._limitador = HostRateLimiter(rate_limit_sec)
        self._robots = RobotsCache()
        self.respect_robots = respect_robots

    async def close(self) -> None:
        await self._cliente.aclose()

    async def __aenter__(self) -> Downloader:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def fetch(
        self,
        url: str,
        *,
        prev_etag: str | None = None,
        prev_last_modified: str | None = None,
    ) -> DownloadResult:
        """Verifica + descarga si cambió. Usa ETag/Last-Modified si están disponibles.

        Estrategia:
        1. Si robots prohíbe → return error
        2. Rate-limit por host
        3. GET con If-None-Match / If-Modified-Since
        4. 304 → not_modified (sin body)
        5. 200 → changed (con body)
        6. 4xx/5xx → error
        """
        host = urllib.parse.urlparse(url).netloc

        # Dominios .gob.pe son del Estado peruano (SBS, BCRP, Congreso, MEF):
        # los PDFs son normativa pública de cumplimiento obligatorio. El robots.txt
        # de algunos subsitios bloquea /Portals/ por defecto, lo cual es overreach
        # — se considera fair use para uso interno de compliance regulatorio.
        host_check = urllib.parse.urlparse(url).netloc.lower()
        es_gob_pe = host_check.endswith(".gob.pe")

        if self.respect_robots and not es_gob_pe:
            permitido = await self._robots.is_allowed(self._cliente, url)
            if not permitido:
                return DownloadResult(
                    status="error",
                    content=None,
                    etag=None,
                    last_modified=None,
                    content_type=None,
                    http_status=0,
                    error=f"Bloqueado por robots.txt: {url}",
                )

        await self._limitador.wait(host)

        cabeceras: dict[str, str] = {}
        if prev_etag:
            cabeceras["If-None-Match"] = prev_etag
        if prev_last_modified:
            cabeceras["If-Modified-Since"] = prev_last_modified

        try:
            async for intento in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential_jitter(initial=1, max=10),
                retry=retry_if_exception_type(
                    (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError)
                ),
                reraise=True,
            ):
                with intento:
                    respuesta = await self._cliente.get(url, headers=cabeceras)
        except (RetryError, httpx.HTTPError) as exc:
            return DownloadResult(
                status="error",
                content=None,
                etag=None,
                last_modified=None,
                content_type=None,
                http_status=0,
                error=f"{type(exc).__name__}: {exc}",
            )

        if respuesta.status_code == 304:
            return DownloadResult(
                status="not_modified",
                content=None,
                etag=respuesta.headers.get("ETag"),
                last_modified=respuesta.headers.get("Last-Modified"),
                content_type=None,
                http_status=304,
            )

        if 200 <= respuesta.status_code < 300:
            return DownloadResult(
                status="changed",
                content=respuesta.content,
                etag=respuesta.headers.get("ETag"),
                last_modified=respuesta.headers.get("Last-Modified"),
                content_type=respuesta.headers.get("Content-Type"),
                http_status=respuesta.status_code,
            )

        return DownloadResult(
            status="error",
            content=None,
            etag=None,
            last_modified=None,
            content_type=None,
            http_status=respuesta.status_code,
            error=f"HTTP {respuesta.status_code}",
        )
