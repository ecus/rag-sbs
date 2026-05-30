"""Scraper HTML genérico para portales regulatorios.

Estrategia: fetch de páginas índice → extraer URLs PDF con regex → verificar
HEAD opcional → construir FuenteDescubierta.

Compatible con portales que tengan listados HTML estáticos (SBS, MEF, SMV,
INDECOPI, Congreso). Maneja Cloudflare/Incapsula con User-Agent realista
y backoff.
"""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx

from src.ingestion.scrapers.sbs import FuenteDescubierta

logger = logging.getLogger(__name__)


_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Regex para <a href="...pdf"> (case-insensitive, encoded o no)
_RE_PDF_LINK = re.compile(
    r"""href\s*=\s*["']([^"']+\.pdf(?:\?[^"']*)?)["']""",
    re.IGNORECASE,
)


async def _fetch_html(
    cliente: httpx.AsyncClient, url: str, timeout: float = 15.0
) -> str | None:
    try:
        resp = await cliente.get(
            url,
            timeout=timeout,
            headers={"User-Agent": _UA, "Accept-Language": "es-PE,es;q=0.9"},
        )
        if resp.status_code != 200:
            logger.warning("HTML fetch %s → HTTP %d", url, resp.status_code)
            return None
        return resp.text
    except Exception as exc:  # noqa: BLE001
        logger.warning("HTML fetch %s falló: %s", url, exc)
        return None


def _extraer_pdfs(html: str, base_url: str) -> set[str]:
    """Extrae URLs absolutas de PDFs del HTML."""
    urls: set[str] = set()
    for m in _RE_PDF_LINK.finditer(html):
        href = m.group(1).strip()
        if not href:
            continue
        # Saltar mailto:, javascript:, etc.
        if href.startswith(("mailto:", "javascript:", "#")):
            continue
        absoluta = urljoin(base_url, href)
        # Solo http(s)
        parsed = urlparse(absoluta)
        if parsed.scheme not in ("http", "https"):
            continue
        urls.add(absoluta)
    return urls


async def _verificar_head(
    cliente: httpx.AsyncClient,
    semaforo: asyncio.Semaphore,
    url: str,
    timeout: float = 8.0,
) -> bool:
    async with semaforo:
        try:
            resp = await cliente.head(
                url, timeout=timeout, headers={"User-Agent": _UA}
            )
            if resp.status_code != 200:
                # Algunos servers no aceptan HEAD, intentar GET con stream
                if resp.status_code in (405, 403):
                    resp = await cliente.get(
                        url,
                        timeout=timeout,
                        headers={"User-Agent": _UA, "Range": "bytes=0-1024"},
                    )
                    return resp.status_code in (200, 206)
                return False
            return True
        except Exception:  # noqa: BLE001
            return False


# -----------------------------------------------------------------------------
# Configuración por portal
# -----------------------------------------------------------------------------

# (issuer, índices, document_type, domain por defecto, priority)
_PORTALES: list[dict] = [
    {
        "issuer": "SBS",
        "document_type": "resolucion",
        "domain": None,
        "priority": 30,
        "indices": [
            "https://www.sbs.gob.pe/normativa-funciones/marco-normativo",
            "https://www.sbs.gob.pe/normativa-funciones/marco-normativo/sistema-financiero",
            "https://www.sbs.gob.pe/normativa-funciones/normativa-conducta-mercado",
            "https://www.sbs.gob.pe/usuarios/normativa-vigente",
            "https://www.sbs.gob.pe/normativa-funciones/marco-normativo/sistema-de-seguros",
            "https://www.sbs.gob.pe/normativa-funciones/marco-normativo/sistema-privado-de-pensiones",
        ],
    },
    {
        "issuer": "MEF",
        "document_type": "norma",
        "domain": "politica_fiscal",
        "priority": 50,
        "indices": [
            "https://www.mef.gob.pe/es/normatividad",
            "https://www.mef.gob.pe/es/normatividad-sp-9867/por-instrumento/decretos-supremos",
            "https://www.mef.gob.pe/es/normatividad-sp-9867/por-instrumento/resoluciones-ministeriales",
        ],
    },
    {
        "issuer": "SMV",
        "document_type": "resolucion",
        "domain": "mercado_valores",
        "priority": 45,
        "indices": [
            "https://www.smv.gob.pe/Frm_NormatividadMarco.aspx?data=A526A26841F65EE0B6034FE52CD3C3A57E70B4FCA8",
            "https://www.smv.gob.pe/Frm_SIL_Resoluciones.aspx",
        ],
    },
    {
        "issuer": "Congreso",
        "document_type": "ley",
        "domain": None,
        "priority": 35,
        "indices": [
            # Páginas de leyes orgánicas y modificaciones del sector financiero
            "https://www.leyes.congreso.gob.pe/leyes_normas.aspx",
        ],
    },
]


async def descubrir_html(
    *,
    max_urls_por_portal: int = 200,
    verify_http: bool = True,
    timeout: float = 15.0,
    concurrencia: int = 20,
    portales: list[str] | None = None,
) -> dict[str, list[FuenteDescubierta]]:
    """Descubre PDFs scrapeando portales HTML.

    Args:
        max_urls_por_portal: tope por portal
        verify_http: si True, verifica HEAD antes de encolar
        timeout: timeout HTTP
        concurrencia: HEADs paralelos
        portales: filtro de issuers (None = todos)

    Returns:
        dict {issuer: [FuenteDescubierta, ...]}
    """
    resultado: dict[str, list[FuenteDescubierta]] = {}
    semaforo = asyncio.Semaphore(concurrencia)

    async with httpx.AsyncClient(
        follow_redirects=True,
        verify=False,  # algunos portales tienen certs viejos
    ) as cliente:
        for cfg in _PORTALES:
            issuer = cfg["issuer"]
            if portales and issuer not in portales:
                continue

            urls_brutas: set[str] = set()
            for indice in cfg["indices"]:
                html = await _fetch_html(cliente, indice, timeout=timeout)
                if not html:
                    continue
                encontradas = _extraer_pdfs(html, indice)
                urls_brutas.update(encontradas)
                logger.info(
                    "[%s] índice %s → %d PDFs",
                    issuer, indice, len(encontradas),
                )

            urls_brutas_lista = list(urls_brutas)[: max_urls_por_portal * 3]

            if verify_http and urls_brutas_lista:
                verificaciones = await asyncio.gather(
                    *(
                        _verificar_head(cliente, semaforo, u, timeout=timeout)
                        for u in urls_brutas_lista
                    )
                )
                urls_ok = [
                    u for u, ok in zip(urls_brutas_lista, verificaciones) if ok
                ]
            else:
                urls_ok = urls_brutas_lista

            urls_ok = urls_ok[:max_urls_por_portal]

            fuentes = [
                _construir_fuente_portal(url, cfg) for url in urls_ok
            ]
            resultado[issuer] = fuentes
            logger.info(
                "[%s] %d PDFs verificados (de %d candidatos)",
                issuer, len(fuentes), len(urls_brutas),
            )

    return resultado


def _construir_fuente_portal(url: str, cfg: dict) -> FuenteDescubierta:
    nombre_archivo = url.rsplit("/", 1)[-1].split("?")[0].replace(".pdf", "")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", nombre_archivo).strip("-").lower()[:50]
    issuer = cfg["issuer"]
    return FuenteDescubierta(
        url=url,
        name_hint=f"{issuer.lower()}-{slug}",
        title_hint=f"{issuer} {nombre_archivo[:60]}",
        issuer=issuer,
        document_type=cfg["document_type"],
        domain=cfg["domain"],
        priority=cfg["priority"],
    )
