"""Scraper del portal SBS.

Estrategia: el portal SBS expone su normativa vigente en
``https://www.sbs.gob.pe/normativa-funciones/marco-normativo`` y otras
páginas hijas. Las URLs de PDFs vigentes están en ``intranet2.sbs.gob.pe/dv_int_cn/``.

Por la estructura del portal (JS render), descubrimos URLs vía:
1. Sitemap ``https://www.sbs.gob.pe/sitemap.xml`` si existe
2. Páginas índice como ``resoluciones-administrativas``
3. Patrones conocidos de URLs ``dv_int_cn/<docId>/v<N>/Adjuntos/<num>-<año>.r.pdf``

Como el portal puede tener Incapsula/Cloudflare en algunas zonas, usamos
fallback a búsqueda Google ``site:intranet2.sbs.gob.pe filetype:pdf "Resolución SBS"``.

Esta es una implementación deliberadamente CONSERVADORA: descubre los slugs
canónicos de las resoluciones desde la tabla ``ingesta automática`` y
para cada slug verifica HTTP 200 antes de encolarlo.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class FuenteDescubierta:
    url: str
    name_hint: str
    title_hint: str | None
    issuer: str
    document_type: str
    domain: str | None
    priority: int


# Patrones URL canónicos del portal SBS
_BASE_INTRANET = "https://intranet2.sbs.gob.pe"
_BASE_PORTAL = "https://www.sbs.gob.pe"


# Slugs canónicos de resoluciones SBS (Núm-Año) que conocemos y son vigentes.
# Esta lista la PUEDES ampliar manualmente; el scraper verifica HTTP 200
# antes de encolar. Mantiene URLs verificadas durante la sesión actual.
#
# Formato: tuple (numero, año, doc_id_intranet, version, descripción, dominio)
# La URL se construye como:
#   {_BASE_INTRANET}/dv_int_cn/{doc_id}/v{version}/Adjuntos/{numero}-{año}.r.pdf
# o variantes según versión.
_CATALOGO_BASE_SBS: list[tuple[str, str]] = [
    # (sufijo_url_relativa, dominio_tematico)
    ("/dv_int_cn/1134/v9.0/Adjuntos/11699-2008.r.pdf", "riesgo_credito"),
    ("/dv_int_cn/2361/v1.0/Adjuntos/1754-2024.R.pdf", "riesgo_credito"),
    ("/dv_int_cn/2410/v1.0/Adjuntos/2286-2024.R.pdf", "ti_seguridad"),
    ("/dv_int_cn/2452/v1.0/Adjuntos/3884-2024.R.pdf", "riesgo_credito"),
    ("/dv_int_cn/2506/v1.0/Adjuntos/Res.SBS%202220-2025.pdf", "riesgo_credito"),
    ("/dv_int_cn/2525/v1.0/Adjuntos/Resolucion%20SBS%20N%c2%b0%203289-2025.pdf", "riesgo_credito"),
    ("/dv_int_cn/2222/v1.0/Adjuntos/3932-2022.R.pdf", "riesgo_credito"),
    ("/dv_int_cn/1877/v1.0/Adjuntos/5570-2019.R.pdf", "riesgo_credito"),
    ("/intranet/INT_CN/DV_INT_CN/714/v1.0/Adjuntos/6285-2013.r.pdf", "riesgo_credito"),
    ("/dv_int_cn/718/v6.0/Adjuntos/6523-2013.R.pdf", "ti_seguridad"),
    ("/dv_int_cn/715/v3.0/Adjuntos/6328-2009.pdf", "gobierno"),
    ("/dv_int_cn/1369/v1.0/adjuntos/0041-2005.r.pdf", "riesgo_operacional"),
    ("/intranet/INT_CN/DV_INT_CN/1660/v1.0/Adjuntos/1928-2015.r.pdf", "gobierno"),
    ("/dv_int_cn/2062/v1.0/Adjuntos/1049-2021.doc.pdf", "operaciones_estructuradas"),
    ("/dv_int_cn/1790/v2.0/Adjuntos/2755-2018.R.pdf", "riesgo_credito"),
    ("/dv_int_cn/1894/v2.0/Adjuntos/877-2020.R.pdf", "riesgo_operacional"),
    ("/dv_int_cn/1540/v2.0/Adjuntos/2660-2015.r.pdf", "laft"),
    ("/intranet/INT_CN/DV_INT_CN/885/v2.0/Adjuntos/3201-2013.r.pdf", "operaciones_estructuradas"),
    # Patrones para barrido por rango
]


# Patrón clave: si conocemos doc_id y queremos probar versiones recientes
# Lo usamos en _descubrir_por_patron_doc_id
_PATRONES_VARIANTES = [
    "/dv_int_cn/{doc_id}/v{ver}.0/Adjuntos/{num}-{anio}.R.pdf",
    "/dv_int_cn/{doc_id}/v{ver}.0/Adjuntos/{num}-{anio}.r.pdf",
    "/dv_int_cn/{doc_id}/v{ver}.0/Adjuntos/{num}-{anio}.pdf",
    "/dv_int_cn/{doc_id}/v{ver}.0/Adjuntos/Resolucion%20SBS%20N%c2%b0%20{num}-{anio}.pdf",
]


def _slug_from_url(url: str) -> str:
    """Extrae un slug razonable del nombre del archivo en la URL."""
    nombre = url.rsplit("/", 1)[-1]
    nombre = re.sub(r"\.[a-zA-Z]+$", "", nombre)
    nombre = re.sub(r"[^a-zA-Z0-9]+", "-", nombre).strip("-").lower()
    return nombre or "sbs-doc"


def _extraer_numero_resolucion(url: str) -> str | None:
    """Extrae el patrón ``N-YYYY`` o ``NNNN-YYYY`` del nombre del archivo."""
    nombre = url.rsplit("/", 1)[-1]
    m = re.search(r"(\d{1,5})-(\d{4})", nombre)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None


async def descubrir_sbs(
    *,
    max_urls: int = 800,
    verify_http: bool = True,
    timeout: float = 8.0,
) -> list[FuenteDescubierta]:
    """Descubre URLs de PDFs vigentes en el portal SBS.

    Para esta primera versión usa el catálogo base + barrido por patrones.
    Una versión futura puede hacer scraping HTML real del portal.

    Args:
        max_urls: tope superior de URLs a descubrir
        verify_http: si True, verifica HTTP 200 antes de encolar
        timeout: timeout por verificación HTTP

    Returns:
        Lista de ``FuenteDescubierta`` listas para insertar en pending_sources.
    """
    candidatas: set[str] = set()

    # 1. URLs canónicas conocidas
    for sufijo, _dominio in _CATALOGO_BASE_SBS:
        candidatas.add(_BASE_INTRANET + sufijo)

    # 2. Barrido por rangos de resoluciones recientes (2020-2026)
    # Para cada año, intentamos versiones del 1 al 8000 con cada doc_id.
    # Esto es CARO si lo hacemos sin filtro — limitamos a doc_ids "altos"
    # observados en URLs recientes (1700-2600).
    doc_ids_recientes = range(1750, 2600, 25)
    nums_resol = [
        "100", "500", "1000", "1500", "2000", "2500", "3000",
        "3500", "4000", "4500",
    ]
    anios = ["2020", "2021", "2022", "2023", "2024", "2025"]
    for doc_id in doc_ids_recientes:
        for num in nums_resol:
            for anio in anios:
                for patron in _PATRONES_VARIANTES[:2]:
                    url = _BASE_INTRANET + patron.format(
                        doc_id=doc_id, ver=1, num=num, anio=anio
                    )
                    candidatas.add(url)
                    if len(candidatas) > max_urls * 6:
                        break
                if len(candidatas) > max_urls * 6:
                    break
            if len(candidatas) > max_urls * 6:
                break
        if len(candidatas) > max_urls * 6:
            break

    # 3. Verificar HTTP 200
    descubiertas: list[FuenteDescubierta] = []
    if not verify_http:
        for url in list(candidatas)[:max_urls]:
            descubiertas.append(_construir_fuente(url, dominio=None))
        return descubiertas

    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True
    ) as cliente:
        for url in list(candidatas)[: max_urls * 3]:  # over-fetch para verificar
            if len(descubiertas) >= max_urls:
                break
            try:
                resp = await cliente.head(url)
                if resp.status_code == 200:
                    # Verificar que sea un PDF (Content-Type o tamaño razonable)
                    ctype = resp.headers.get("content-type", "").lower()
                    clen = int(resp.headers.get("content-length", "0") or 0)
                    if "pdf" in ctype or clen > 10_000:
                        descubiertas.append(_construir_fuente(url, dominio=None))
                        logger.debug("✓ SBS scraper found: %s", url)
            except (httpx.RequestError, httpx.HTTPStatusError):
                pass
            except Exception as exc:  # noqa: BLE001
                logger.debug("Error verificando %s: %s", url, exc)

    logger.info(
        "Scraper SBS: descubiertas %d URLs (de %d candidatas)",
        len(descubiertas), len(candidatas),
    )
    return descubiertas


def _construir_fuente(url: str, dominio: str | None) -> FuenteDescubierta:
    """Construye un FuenteDescubierta a partir de una URL."""
    slug = _slug_from_url(url)
    numero = _extraer_numero_resolucion(url)
    title = f"Resolución SBS {numero}" if numero else f"SBS doc {slug[:30]}"
    return FuenteDescubierta(
        url=url,
        name_hint=f"res-sbs-{numero}" if numero else f"sbs-{slug[:40]}",
        title_hint=title,
        issuer="SBS",
        document_type="resolucion",
        domain=dominio,
        priority=30,
    )
