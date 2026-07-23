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
from psycopg_pool import AsyncConnectionPool

from src.config import get_settings
from src.ingestion.date_extractor import detectar_fecha


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
