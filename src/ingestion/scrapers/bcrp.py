"""Scraper del portal BCRP — Circulares y Notas Informativas."""

from __future__ import annotations

import logging
import re

import httpx

from src.ingestion.scrapers.sbs import FuenteDescubierta

logger = logging.getLogger(__name__)


_BASE_BCRP = "https://www.bcrp.gob.pe"

# Patrones canónicos:
#   Circulares: /docs/Transparencia/Normas-Legales/Circulares/{año}/circular-{NNNN}-{año}-bcrp.pdf
#   Notas:      /docs/Transparencia/Notas-Informativas/{año}/nota-informativa-{año}-{MM}-{DD}.pdf


async def descubrir_bcrp(
    *,
    max_urls: int = 150,
    verify_http: bool = True,
    timeout: float = 8.0,
) -> list[FuenteDescubierta]:
    """Descubre URLs de circulares y notas informativas BCRP vigentes."""
    candidatas: set[tuple[str, str]] = set()  # (url, tipo)

    # Circulares: probamos N=1..30 cada año desde 2018
    for anio in range(2018, 2027):
        for num in range(1, 25):
            url = (
                f"{_BASE_BCRP}/docs/Transparencia/Normas-Legales/Circulares/"
                f"{anio}/circular-{num:04d}-{anio}-bcrp.pdf"
            )
            candidatas.add((url, "circular"))

    # Notas: probamos algunos meses-días representativos por semestre
    for anio in range(2022, 2027):
        for mes in [1, 4, 7, 10]:
            for dia in [1, 7, 14, 21, 28]:
                url = (
                    f"{_BASE_BCRP}/docs/Transparencia/Notas-Informativas/"
                    f"{anio}/nota-informativa-{anio}-{mes:02d}-{dia:02d}.pdf"
                )
                candidatas.add((url, "nota_informativa"))

    descubiertas: list[FuenteDescubierta] = []
    if not verify_http:
        for url, tipo in list(candidatas)[:max_urls]:
            descubiertas.append(_construir_fuente_bcrp(url, tipo))
        return descubiertas

    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True
    ) as cliente:
        for url, tipo in list(candidatas):
            if len(descubiertas) >= max_urls:
                break
            try:
                resp = await cliente.head(url)
                if resp.status_code == 200:
                    descubiertas.append(_construir_fuente_bcrp(url, tipo))
                    logger.debug("✓ BCRP scraper found: %s", url)
            except (httpx.RequestError, httpx.HTTPStatusError):
                pass
            except Exception as exc:  # noqa: BLE001
                logger.debug("Error verificando %s: %s", url, exc)

    logger.info(
        "Scraper BCRP: descubiertas %d URLs (de %d candidatas)",
        len(descubiertas), len(candidatas),
    )
    return descubiertas


def _construir_fuente_bcrp(url: str, tipo: str) -> FuenteDescubierta:
    nombre = url.rsplit("/", 1)[-1].replace(".pdf", "")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", nombre).strip("-").lower()
    return FuenteDescubierta(
        url=url,
        name_hint=f"bcrp-{slug[:50]}",
        title_hint=f"BCRP {tipo} {nombre[:50]}",
        issuer="BCRP",
        document_type=tipo,
        domain="tasas_intereses",
        priority=40,
    )
