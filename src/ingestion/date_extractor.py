"""Extracción de fecha de publicación (sin LLM), reutilizable por la ingesta y
el backfill. Cascada de señales, de más a menos confiable; la primera acierta:

  1. Dateline en el cuerpo: "Lima, DD de <mes> de AAAA"  → precisión 'dia'
  2. Fecha ISO en la URL/slug: ".../…-AAAA-MM-DD.pdf"     → precisión 'dia'
  3. Año en la ruta de la URL:  ".../Circulares/AAAA/…"    → precisión 'anio'
  4. Año en resolution_number:  "NNNN-AAAA"                → precisión 'anio'
  5. metadata.year                                          → precisión 'anio'
  6. Fecha suelta en el cuerpo: "DD de <mes> de AAAA"       → precisión 'dia' (último recurso)
"""

from __future__ import annotations

import datetime as dt
import re

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

RX_DATELINE = re.compile(
    r"Lima[,\.]?\s+(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s+de\s+((?:19|20)\d{2})",
    re.IGNORECASE,
)
RX_FECHA_TEXTO = re.compile(
    r"\b(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s+de\s+((?:19|20)\d{2})\b",
    re.IGNORECASE,
)
RX_ISO = re.compile(r"((?:19|20)\d{2})[-_/](\d{2})[-_/](\d{2})")
RX_ANIO_RUTA = re.compile(r"[/\-_]((?:19|20)\d{2})[/\-_]")
RX_ANIO_RESNUM = re.compile(r"-((?:19|20)\d{2})\b")


def _mes_a_num(nombre: str) -> int | None:
    return MESES.get(nombre.strip().lower())


def _fecha_valida(a: int, m: int, d: int) -> dt.date | None:
    try:
        return dt.date(a, m, d)
    except ValueError:
        return None


def detectar_fecha(
    texto: str | None,
    source_url: str | None,
    document_id: str | None,
    resolution_number: str | None,
    meta_year: int | None,
) -> tuple[dt.date, str] | None:
    """Devuelve (fecha, precision) o None. precision ∈ {'dia','anio'}."""
    texto = texto or ""
    url_slug = f"{source_url or ''} {document_id or ''}"

    m = RX_DATELINE.search(texto)
    if m:
        mes = _mes_a_num(m.group(2))
        if mes:
            f = _fecha_valida(int(m.group(3)), mes, int(m.group(1)))
            if f:
                return f, "dia"

    m = RX_ISO.search(url_slug)
    if m:
        f = _fecha_valida(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if f:
            return f, "dia"

    m = RX_ANIO_RUTA.search(source_url or "")
    if m:
        return dt.date(int(m.group(1)), 1, 1), "anio"
    if resolution_number:
        m = RX_ANIO_RESNUM.search(resolution_number)
        if m:
            return dt.date(int(m.group(1)), 1, 1), "anio"

    if meta_year and 1900 <= int(meta_year) <= 2100:
        return dt.date(int(meta_year), 1, 1), "anio"

    m = RX_FECHA_TEXTO.search(texto)
    if m:
        mes = _mes_a_num(m.group(2))
        if mes:
            f = _fecha_valida(int(m.group(3)), mes, int(m.group(1)))
            if f:
                return f, "dia"

    return None
