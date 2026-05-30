"""Scraper del portal SBS — versión ampliada con verificación concurrente.

Estrategia:
1. Catálogo base de URLs conocidas (verificadas manualmente).
2. Barrido por patrones canónicos sobre rangos amplios de doc_id/num/año/versión.
3. Verificación HTTP HEAD concurrente con semáforo (30 paralelos).

Cobertura objetivo: doc_ids 700-2700, resoluciones 1-9999, años 2010-2026,
versiones v1-v3. Caps superiores para evitar barrer al infinito.
"""

from __future__ import annotations

import asyncio
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


_BASE_INTRANET = "https://intranet2.sbs.gob.pe"
_BASE_PORTAL = "https://www.sbs.gob.pe"


# URLs canónicas conocidas y verificadas manualmente
_CATALOGO_BASE_SBS: list[tuple[str, str]] = [
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
]


# Patrones URL canónicos (con extensión variable)
_PATRONES_VARIANTES = [
    "/dv_int_cn/{doc_id}/v{ver}.0/Adjuntos/{num}-{anio}.R.pdf",
    "/dv_int_cn/{doc_id}/v{ver}.0/Adjuntos/{num}-{anio}.r.pdf",
    "/dv_int_cn/{doc_id}/v{ver}.0/Adjuntos/{num}-{anio}.pdf",
]


def _slug_from_url(url: str) -> str:
    nombre = url.rsplit("/", 1)[-1]
    nombre = re.sub(r"\.[a-zA-Z]+$", "", nombre)
    nombre = re.sub(r"[^a-zA-Z0-9]+", "-", nombre).strip("-").lower()
    return nombre or "sbs-doc"


def _extraer_numero_resolucion(url: str) -> str | None:
    nombre = url.rsplit("/", 1)[-1]
    m = re.search(r"(\d{1,5})-(\d{4})", nombre)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None


def _generar_candidatos(max_candidatos: int) -> list[str]:
    """Genera URLs candidatas barriendo el espacio de patrones."""
    candidatas: set[str] = set()

    for sufijo, _dominio in _CATALOGO_BASE_SBS:
        candidatas.add(_BASE_INTRANET + sufijo)

    doc_ids = list(range(700, 2700, 3))
    nums = [
        1, 5, 10, 20, 30, 41, 50, 100, 150, 200, 250, 300, 400, 500, 600,
        700, 800, 877, 1000, 1049, 1500, 1754, 1928, 2000, 2220, 2286, 2500,
        2660, 2755, 3000, 3201, 3289, 3500, 3884, 3932, 4000, 4500, 5000,
        5570, 6000, 6285, 6328, 6523, 7000, 8000, 9000, 11699,
    ]
    anios = [
        "2010", "2011", "2012", "2013", "2014", "2015", "2016", "2017",
        "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025",
    ]
    versiones = [1, 2, 3]

    for doc_id in doc_ids:
        for num in nums:
            for anio in anios:
                for ver in versiones:
                    for patron in _PATRONES_VARIANTES:
                        url = _BASE_INTRANET + patron.format(
                            doc_id=doc_id, ver=ver, num=num, anio=anio
                        )
                        candidatas.add(url)
                        if len(candidatas) >= max_candidatos:
                            return list(candidatas)
    return list(candidatas)


async def _verificar_url(
    cliente: httpx.AsyncClient, semaforo: asyncio.Semaphore, url: str
) -> bool:
    async with semaforo:
        try:
            resp = await cliente.head(url)
            if resp.status_code != 200:
                return False
            ctype = resp.headers.get("content-type", "").lower()
            clen = int(resp.headers.get("content-length", "0") or 0)
            return "pdf" in ctype or clen > 10_000
        except Exception:  # noqa: BLE001
            return False


async def descubrir_sbs(
    *,
    max_urls: int = 800,
    verify_http: bool = True,
    timeout: float = 8.0,
    max_candidatos: int = 30000,
    concurrencia: int = 30,
) -> list[FuenteDescubierta]:
    """Descubre URLs de PDFs vigentes en el portal SBS."""
    candidatas = _generar_candidatos(max_candidatos)
    logger.info("SBS scraper: %d candidatas generadas", len(candidatas))

    if not verify_http:
        return [
            _construir_fuente(url, dominio=None)
            for url in candidatas[:max_urls]
        ]

    semaforo = asyncio.Semaphore(concurrencia)
    descubiertas: list[FuenteDescubierta] = []

    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True
    ) as cliente:
        lote_size = 500
        for inicio in range(0, len(candidatas), lote_size):
            if len(descubiertas) >= max_urls:
                break
            lote = candidatas[inicio : inicio + lote_size]
            resultados = await asyncio.gather(
                *(_verificar_url(cliente, semaforo, u) for u in lote)
            )
            for url, ok in zip(lote, resultados):
                if ok:
                    descubiertas.append(_construir_fuente(url, dominio=None))
                    if len(descubiertas) >= max_urls:
                        break
            logger.info(
                "SBS scraper: lote %d/%d → %d encontradas",
                inicio // lote_size + 1,
                (len(candidatas) + lote_size - 1) // lote_size,
                len(descubiertas),
            )

    logger.info(
        "Scraper SBS: %d URLs verificadas (de %d candidatas)",
        len(descubiertas), len(candidatas),
    )
    return descubiertas


def _construir_fuente(url: str, dominio: str | None) -> FuenteDescubierta:
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
