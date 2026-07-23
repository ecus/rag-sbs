"""Backfill de `publication_date` (+ `date_precision` en metadata) sobre documents.

Cascada de señales, de más a menos confiable. La primera que acierta gana:
  1. Dateline en el cuerpo: "Lima, DD de <mes> de AAAA"  → precisión 'dia'
  2. Fecha ISO en la URL/slug: ".../…-AAAA-MM-DD.pdf"     → precisión 'dia'
  3. Año en la ruta de la URL:  ".../Circulares/AAAA/…"    → precisión 'anio'
  4. Año en resolution_number:  "NNNN-AAAA"                → precisión 'anio'
  5. metadata.year                                          → precisión 'anio'
  6. Fecha suelta en el cuerpo: "DD de <mes> de AAAA"       → precisión 'dia' (último recurso)

Sin LLM. Idempotente: se puede correr las veces que haga falta.
Uso (dentro del contenedor api):  python -m src.scripts.backfill_dates
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re

from psycopg_pool import AsyncConnectionPool

from src.config import get_settings

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# "Lima, 07 de Marzo de 2025" (permite espacios/saltos raros y mayúsculas)
RX_DATELINE = re.compile(
    r"Lima[,\.]?\s+(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s+de\s+((?:19|20)\d{2})",
    re.IGNORECASE,
)
# "10 de diciembre de 2010" en cualquier parte
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

    # 1. Dateline en el cuerpo
    m = RX_DATELINE.search(texto)
    if m:
        mes = _mes_a_num(m.group(2))
        if mes:
            f = _fecha_valida(int(m.group(3)), mes, int(m.group(1)))
            if f:
                return f, "dia"

    # 2. Fecha ISO en URL/slug
    m = RX_ISO.search(url_slug)
    if m:
        f = _fecha_valida(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if f:
            return f, "dia"

    # 3/4. Año en la ruta de URL o en resolution_number
    m = RX_ANIO_RUTA.search(source_url or "")
    if m:
        return dt.date(int(m.group(1)), 1, 1), "anio"
    if resolution_number:
        m = RX_ANIO_RESNUM.search(resolution_number)
        if m:
            return dt.date(int(m.group(1)), 1, 1), "anio"

    # 5. metadata.year
    if meta_year and 1900 <= int(meta_year) <= 2100:
        return dt.date(int(meta_year), 1, 1), "anio"

    # 6. Fecha suelta en el cuerpo (último recurso)
    m = RX_FECHA_TEXTO.search(texto)
    if m:
        mes = _mes_a_num(m.group(2))
        if mes:
            f = _fecha_valida(int(m.group(3)), mes, int(m.group(1)))
            if f:
                return f, "dia"

    return None


async def backfill(pool: AsyncConnectionPool, *, solo_vacios: bool = True) -> dict:
    cond = "WHERE publication_date IS NULL" if solo_vacios else ""
    actualizados = 0
    por_precision = {"dia": 0, "anio": 0}
    sin_fecha: list[str] = []

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT d.id, d.document_id, d.source_url, d.resolution_number,
                       d.metadata, c.content
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id AND c.chunk_index = 0
                {cond}
                """
            )
            filas = await cur.fetchall()

        for doc_uuid, doc_slug, url, resnum, meta, contenido in filas:
            meta = meta or {}
            res = detectar_fecha(
                (contenido or "")[:1200], url, doc_slug, resnum, meta.get("year")
            )
            if not res:
                sin_fecha.append(doc_slug)
                continue
            fecha, precision = res
            nueva_meta = {**meta, "date_precision": precision}
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE documents SET publication_date = %s, metadata = %s WHERE id = %s",
                    (fecha, __import__("json").dumps(nueva_meta), doc_uuid),
                )
            actualizados += 1
            por_precision[precision] += 1
        await conn.commit()

    return {
        "actualizados": actualizados,
        "por_precision": por_precision,
        "sin_fecha": len(sin_fecha),
        "ejemplos_sin_fecha": sin_fecha[:10],
    }


async def _main() -> None:
    dsn = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")
    pool = AsyncConnectionPool(conninfo=dsn, min_size=1, max_size=4, open=False)
    await pool.open()
    resultado = await backfill(pool, solo_vacios=False)
    print(resultado)
    await pool.close()


if __name__ == "__main__":
    asyncio.run(_main())
