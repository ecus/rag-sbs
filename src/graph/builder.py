"""Constructor del grafo: itera chunks → extrae menciones → upsert nodos+aristas.

Uso típico:
  - Reconstrucción completa: `await rebuild_full(pool)` después de re-ingesta masiva
  - Incremental: `await build_for_document(pool, doc_uuid)` tras ingerir un doc

Tipos de nodos y aristas creados (L1):
  Nodos:
    - kind='document', label=document_id (slug), metadata={title, domain}
    - kind='resolution', label='Res-SBS-NNNNN-AAAA'
    - kind='ley', label='Ley-NNNNN'
    - kind='circular', label='Circular-X-NNN'
    - kind='articulo', label='Articulo-N'
    - kind='anexo', label='Anexo-X'

  Aristas:
    - relation='cites': document → (resolution|ley|circular|anexo|articulo)
    - relation='self_reference': para self-citations (Res citando un Art. propio)

  Auto-vinculación documento↔resolución:
    Si un nodo `document` tiene metadata.resolution_number == X-Y y existe nodo
    `resolution` con label `Res-SBS-X-Y`, se crea arista `relation='canonical_form'`
    para conectarlos.
"""

from __future__ import annotations

import logging
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from src.graph.extractor import Mention, extraer_menciones
from src.graph.repository import GraphRepository

logger = logging.getLogger(__name__)


async def _obtener_o_crear_nodo_documento(
    repo: GraphRepository,
    *,
    document_uuid: UUID,
    document_slug: str,
    title: str,
    domain: str | None,
) -> UUID:
    """Crea/retorna nodo `kind='document'`.

    Usa el slug humano (ej. 'res-sbs-11356-2008-clasificacion-deudor') como label
    en lugar del UUID de Postgres — más legible al inspeccionar la BD por SQL
    o ver la primera carga del grafo antes de los overrides de la UI.
    """
    return await repo.upsert_node(
        kind="document",
        label=document_slug,
        document_id=document_uuid,
        metadata={"title": title, "domain": domain},
    )


async def _materializar_mencion_como_nodo(
    repo: GraphRepository, mencion: Mention
) -> UUID:
    """Convierte una mención en nodo (kind = mencion.kind)."""
    return await repo.upsert_node(
        kind=mencion.kind,
        label=mencion.label,
        metadata={"raw_examples": [mencion.raw]},
    )


async def _enlazar_documento_canonico(
    repo: GraphRepository, document_node: UUID, resolution_label: str
) -> None:
    """Si la fuente de un documento ES una resolución conocida, vincula su nodo
    'document' al nodo 'resolution' canónico. Usamos relation='canonical_form'.
    """
    res_node = await repo.upsert_node(
        kind="resolution",
        label=resolution_label,
        metadata={"is_canonical_target": True},
    )
    await repo.insert_edge(
        src_node=document_node,
        dst_node=res_node,
        relation="canonical_form",
        score=1.0,
        metadata={"reason": "document_id corresponde a esta resolución"},
    )


async def construir_para_documento(
    pool: AsyncConnectionPool,
    *,
    document_id: UUID,
) -> dict:
    """Construye el subgrafo de UN documento desde sus chunks.

    Retorna conteos para reporting.
    """
    nodos_creados = 0
    aristas_creadas = 0

    async with pool.connection() as conn:
        repo = GraphRepository(conn)

        # 1. Cargar metadata del documento + chunks
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT title, domain, metadata, document_id
                FROM documents WHERE id = %s
                """,
                (document_id,),
            )
            fila_doc = await cursor.fetchone()
            if not fila_doc:
                return {"error": "documento no existe"}
            titulo, dominio, meta_doc, doc_slug = fila_doc

            await cursor.execute(
                "SELECT id, content FROM chunks WHERE document_id = %s ORDER BY chunk_index",
                (document_id,),
            )
            chunks_filas = await cursor.fetchall()

        # 2. Crear nodo del documento (label = slug humano)
        nodo_doc = await _obtener_o_crear_nodo_documento(
            repo,
            document_uuid=document_id,
            document_slug=doc_slug,
            title=titulo,
            domain=dominio,
        )
        nodos_creados += 1

        # 3. Vinculación canónica si metadata tiene resolution_number
        numero_res = (meta_doc or {}).get("resolution_number")
        if numero_res:
            etiqueta = f"Res-SBS-{numero_res.replace('-', '-')}"
            # numero_res viene como "11356-2008"
            await _enlazar_documento_canonico(repo, nodo_doc, etiqueta)
            aristas_creadas += 1

        # 4. Iterar chunks → extraer menciones → crear nodos+aristas
        # self_label = norma canónica de ESTE documento, para calificar los
        # "artículo N de la presente Resolución" con la norma propia.
        self_label = f"Res-SBS-{numero_res}" if numero_res else None
        for chunk_id, contenido in chunks_filas:
            menciones = extraer_menciones(contenido, self_label=self_label)
            for mencion in menciones:
                # Evitar self-citation explícita (la canónica ya la creamos arriba)
                if (
                    mencion.kind == "resolution"
                    and numero_res
                    and mencion.label == f"Res-SBS-{numero_res}"
                ):
                    relacion = "self_reference"
                else:
                    relacion = "cites"

                nodo_destino = await _materializar_mencion_como_nodo(repo, mencion)
                nodos_creados += 1
                await repo.insert_edge(
                    src_node=nodo_doc,
                    dst_node=nodo_destino,
                    relation=relacion,
                    score=1.0,
                    evidence_chunk_id=chunk_id,
                    metadata={"raw": mencion.raw, "span": [mencion.start, mencion.end]},
                )
                aristas_creadas += 1

    logger.info(
        "Grafo construido para %s: ~%d nodos, ~%d aristas",
        document_id, nodos_creados, aristas_creadas,
    )
    return {"nodos_intentados": nodos_creados, "aristas_intentadas": aristas_creadas}


async def reconstruir_completo(pool: AsyncConnectionPool) -> dict:
    """Trunca y rearma el grafo desde cero a partir de TODOS los documentos."""
    async with pool.connection() as conn:
        repo = GraphRepository(conn)
        await repo.truncate_all()

        async with conn.cursor() as cursor:
            await cursor.execute("SELECT id FROM documents")
            ids_docs = [fila[0] for fila in await cursor.fetchall()]

    totales_nodos = 0
    totales_aristas = 0
    for doc_id in ids_docs:
        resultado = await construir_para_documento(pool, document_id=doc_id)
        totales_nodos += resultado.get("nodos_intentados", 0)
        totales_aristas += resultado.get("aristas_intentadas", 0)

    async with pool.connection() as conn:
        repo = GraphRepository(conn)
        stats = await repo.estadisticas()

    return {
        "documentos_procesados": len(ids_docs),
        "operaciones_nodo": totales_nodos,
        "operaciones_arista": totales_aristas,
        "estado_final": stats,
    }
