"""Clasificador de relaciones cites → modifies / derogates.

Estrategia: regex sobre ventana de contexto (±300 chars del span de la cita).
Reusa los patrones de `differ.py` que ya detectan vocabulario modificatorio
y derogatorio en sumarios SBS, ahora aplicados a chunks individuales.

Costo: cero LLM. Sprint posterior puede añadir LLM como fallback para
casos ambiguos donde regex acierta pero con baja confianza.
"""

from __future__ import annotations

import logging
from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.ingestion.differ import RX_DEROGATORIO, RX_MODIFICATORIO

logger = logging.getLogger(__name__)


def _clasificar_ventana(
    contenido_chunk: str, span: list[int] | None, radio: int = 300
) -> str:
    """Clasifica una cita en función del texto que la rodea."""
    if not span or len(span) < 2:
        ventana = contenido_chunk
    else:
        inicio = max(0, span[0] - radio)
        fin = min(len(contenido_chunk), span[1] + radio)
        ventana = contenido_chunk[inicio:fin]

    if RX_DEROGATORIO.search(ventana):
        return "derogates"
    if RX_MODIFICATORIO.search(ventana):
        return "modifies"
    return "cites"


async def reclasificar_aristas_cites(pool: AsyncConnectionPool) -> dict:
    """Itera todas las aristas con relation='cites' que tengan evidencia
    (evidence_chunk_id != NULL) y aplica el clasificador de ventana.

    Si la ventana sugiere modifies/derogates → UPDATE relation.
    """
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT e.id AS edge_id, e.relation, e.metadata,
                       c.content AS chunk_content
                FROM graph_edges e
                JOIN chunks c ON c.id = e.evidence_chunk_id
                WHERE e.relation = 'cites'
                """
            )
            filas = list(await cursor.fetchall())

    if not filas:
        return {"aristas_revisadas": 0, "modificadas": 0, "derogadas": 0}

    cambios_modifies: list[UUID] = []
    cambios_derogates: list[UUID] = []

    for fila in filas:
        edge_id = fila["edge_id"]
        contenido = fila["chunk_content"] or ""
        meta = fila["metadata"] or {}
        span = meta.get("span")
        nueva_relacion = _clasificar_ventana(contenido, span)
        if nueva_relacion == "modifies":
            cambios_modifies.append(edge_id)
        elif nueva_relacion == "derogates":
            cambios_derogates.append(edge_id)

    if cambios_modifies or cambios_derogates:
        async with pool.connection() as conn:
            async with conn.cursor() as cursor:
                if cambios_modifies:
                    await cursor.execute(
                        "UPDATE graph_edges SET relation = 'modifies' WHERE id = ANY(%s)",
                        (cambios_modifies,),
                    )
                if cambios_derogates:
                    await cursor.execute(
                        "UPDATE graph_edges SET relation = 'derogates' WHERE id = ANY(%s)",
                        (cambios_derogates,),
                    )

    logger.info(
        "Reclasificación: %d → modifies, %d → derogates de %d aristas cites",
        len(cambios_modifies), len(cambios_derogates), len(filas),
    )

    return {
        "aristas_revisadas": len(filas),
        "modificadas": len(cambios_modifies),
        "derogadas": len(cambios_derogates),
    }
