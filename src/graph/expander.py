"""Graph-augmented retrieval: expande el contexto del RAG usando el grafo.

Pipeline:
  1. Recibe los chunks que el retriever vectorial trajo en el top-k.
  2. Identifica los documentos a los que pertenecen.
  3. Camina N hops por el grafo siguiendo aristas configurables
     (`cites`, `same_topic`, `modifies` por defecto).
  4. Para cada documento alcanzado por la expansión, busca sus chunks más
     cercanos al query (por similitud vectorial), excluyendo duplicados.
  5. Retorna chunks adicionales con bonus/penalty según procedencia.

Ventaja: si el retriever vectorial no encontró el documento que cita
"Articulo-203" pero recuperó otro que SÍ lo cita, la expansión por
`cites` trae el documento puente. GraphRAG en versión simple.
"""

from __future__ import annotations

import logging
from typing import Iterable
from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.storage.pgvector_store import RetrievedChunk

logger = logging.getLogger(__name__)


# Pesos por tipo de relación: cuánto "vale" cada arista cuando expandimos.
# Mayor = más confianza de que el contenido al otro lado es relevante.
PESO_RELACION = {
    "cites":          1.00,
    "same_topic":     0.85,
    "modifies":       1.10,
    "derogates":      0.95,
    "self_reference": 0.30,   # poco valor — el mismo doc
    "canonical_form": 0.20,
}

RELACIONES_DEFECTO = ["cites", "same_topic", "modifies"]


async def expandir_por_grafo(
    pool: AsyncConnectionPool,
    *,
    chunks_iniciales: list[RetrievedChunk],
    query_embedding: list[float],
    max_hops: int = 1,
    relaciones: list[str] | None = None,
    max_chunks_agregados: int = 5,
) -> tuple[list[RetrievedChunk], dict]:
    """Expande el set de chunks recuperados navegando el grafo.

    Args:
        pool: pool de Postgres.
        chunks_iniciales: top-k del retriever vectorial.
        query_embedding: embedding de la consulta original (para puntuar
            chunks expandidos por similitud al query).
        max_hops: 1 (vecinos directos), 2 (vecinos de vecinos), etc.
        relaciones: tipos de aristas a seguir.
        max_chunks_agregados: tope de chunks NUEVOS a añadir.

    Returns:
        (chunks_nuevos, telemetria). `chunks_nuevos` excluye los iniciales.
    """
    relaciones = relaciones or RELACIONES_DEFECTO
    if not chunks_iniciales or max_hops <= 0:
        return [], {"expanded": False, "reason": "no_chunks_or_no_hops"}

    # 1. Documentos únicos que aportaron chunks en el top-k vectorial
    docs_iniciales: set[UUID] = {c.document_id for c in chunks_iniciales}

    async with pool.connection() as conn:
        # 2. Mapear documentos → graph nodes (kind='document')
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT id, document_id
                FROM graph_nodes
                WHERE kind = 'document' AND document_id = ANY(%s)
                """,
                (list(docs_iniciales),),
            )
            filas = await cursor.fetchall()
            nodos_iniciales: set[UUID] = {f[0] for f in filas}

        if not nodos_iniciales:
            return [], {"expanded": False, "reason": "no_graph_nodes_for_initial_docs"}

        # 3. BFS hasta max_hops (siguiendo aristas en ambas direcciones)
        visitados: set[UUID] = set(nodos_iniciales)
        frontera: set[UUID] = set(nodos_iniciales)
        for _ in range(max_hops):
            if not frontera:
                break
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT DISTINCT dst_node FROM graph_edges
                    WHERE src_node = ANY(%s) AND relation = ANY(%s)
                    UNION
                    SELECT DISTINCT src_node FROM graph_edges
                    WHERE dst_node = ANY(%s) AND relation = ANY(%s)
                    """,
                    (list(frontera), relaciones, list(frontera), relaciones),
                )
                vecinos = {f[0] for f in await cursor.fetchall()}
            nuevos = vecinos - visitados
            visitados |= nuevos
            frontera = nuevos

        # 4. Filtrar a nodos `document` que sean NUEVOS (no estaban en el top-k)
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT DISTINCT document_id
                FROM graph_nodes
                WHERE id = ANY(%s)
                  AND kind = 'document'
                  AND document_id IS NOT NULL
                  AND NOT (document_id = ANY(%s))
                """,
                (list(visitados), list(docs_iniciales)),
            )
            uuids_docs_nuevos = [f[0] for f in await cursor.fetchall()]

        if not uuids_docs_nuevos:
            return [], {
                "expanded": True,
                "added_docs": 0,
                "added_chunks": 0,
                "visited_nodes": len(visitados),
            }

        # 5. Top-N chunks de esos documentos nuevos, ordenados por similitud al query
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT c.id AS chunk_id,
                       c.content,
                       c.metadata,
                       d.id AS doc_uuid,
                       d.title,
                       d.source_url,
                       1 - (c.embedding <=> %s::vector) AS vector_score
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.document_id = ANY(%s)
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
                """,
                (query_embedding, uuids_docs_nuevos, query_embedding, max_chunks_agregados),
            )
            filas_chunks = list(await cursor.fetchall())

    chunks_expandidos = [
        RetrievedChunk(
            chunk_id=f["chunk_id"],
            document_id=f["doc_uuid"],
            document_title=f["title"],
            document_url=f["source_url"],
            content=f["content"],
            score=float(f["vector_score"]) * 0.80,
            vector_score=float(f["vector_score"]),
            text_score=0.0,
            metadata=f.get("metadata") or {},
        )
        for f in filas_chunks
    ]

    telemetria = {
        "expanded": True,
        "max_hops": max_hops,
        "relaciones_usadas": relaciones,
        "visited_nodes": len(visitados),
        "added_docs": len(uuids_docs_nuevos),
        "added_chunks": len(chunks_expandidos),
        "initial_docs": len(docs_iniciales),
    }
    logger.info("graph_expansion: %s", telemetria)
    return chunks_expandidos, telemetria


def fusionar_y_rankear(
    chunks_vector: Iterable[RetrievedChunk],
    chunks_expansion: Iterable[RetrievedChunk],
    *,
    top_k_final: int = 7,
    penalty_expansion: float = 0.15,
    bonus_ambos: float = 0.05,
) -> tuple[list[RetrievedChunk], list[str]]:
    """Combina ambos sets, deduplica por chunk_id, ordena por score normalizado.

    Score canónico = vector_score (cosine similarity 0..1):
      - chunks vector puros:    score = vector_score          (sin penalty)
      - chunks vía expansión:   score = vector_score × (1 − penalty_expansion)
      - chunks en ambos sets:   score = vector_score + bonus_ambos

    Esta normalización resuelve el bug donde RRF (~0.01) y cosine (~0.5) se
    mezclaban en escalas distintas y la expansión siempre dominaba.

    Returns:
        (chunks_finales, vias_por_chunk) — vias ∈ {'vector', 'graph_expansion', 'both'}
    """
    indice: dict[UUID, dict] = {}

    # 1. Vanilla: usa cosine puro como score canónico
    for c in chunks_vector:
        c.score = round(c.vector_score, 4)
        indice[c.chunk_id] = {"chunk": c, "via": "vector"}

    # 2. Expansión: cosine × (1 − penalty)
    factor_expansion = 1.0 - penalty_expansion
    for c in chunks_expansion:
        if c.chunk_id in indice:
            # Apareció en ambos: bonus sobre el score que ya tenía
            registro = indice[c.chunk_id]
            registro["via"] = "both"
            mejor = registro["chunk"]
            mejor.score = round(min(1.0, mejor.score + bonus_ambos), 4)
        else:
            c.score = round(c.vector_score * factor_expansion, 4)
            indice[c.chunk_id] = {"chunk": c, "via": "graph_expansion"}

    ordenados = sorted(indice.values(), key=lambda r: r["chunk"].score, reverse=True)
    ordenados = ordenados[:top_k_final]
    return (
        [r["chunk"] for r in ordenados],
        [r["via"] for r in ordenados],
    )
