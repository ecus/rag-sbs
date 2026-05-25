"""Reranker via Cohere Rerank API — latencia sub-100 ms, calidad SOTA.

Requisitos:
  pip install cohere
  export COHERE_API_KEY=...

Modelo recomendado: `rerank-multilingual-v3.0` (soporta español nativo).
Costo: ~$1 por 1K búsquedas (búsqueda = 1 query × N docs).

NO está activo por default — requiere API key. Habilitar:
  RERANKER_BACKEND=cohere
  COHERE_API_KEY=tu_key
"""

from __future__ import annotations

import logging

from src.config import get_settings
from src.storage.pgvector_store import RetrievedChunk

logger = logging.getLogger(__name__)


async def rerank(
    llm,  # noqa: ARG001
    query: str,
    chunks: list[RetrievedChunk],
    *,
    top_k: int = 7,
) -> list[RetrievedChunk]:
    if not chunks:
        return []
    if len(chunks) == 1:
        return chunks

    cfg = get_settings()
    if not cfg.cohere_api_key:
        logger.warning(
            "COHERE_API_KEY no configurada — fallback al orden original"
        )
        return chunks[:top_k]

    try:
        import cohere
    except ImportError as exc:
        raise RuntimeError(
            "cohere SDK no instalado. Para este backend: pip install cohere"
        ) from exc

    cliente = cohere.Client(cfg.cohere_api_key)
    documentos = [c.content for c in chunks]
    try:
        resultado = cliente.rerank(
            query=query,
            documents=documentos,
            top_n=top_k,
            model="rerank-multilingual-v3.0",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cohere falló (%s) — fallback al orden original", exc)
        return chunks[:top_k]

    # Cohere retorna índices + scores normalizados 0..1
    ordenados: list[RetrievedChunk] = []
    for item in resultado.results:
        chunk = chunks[item.index]
        chunk.score = round(float(item.relevance_score), 4)
        ordenados.append(chunk)

    logger.info("cohere rerank: %d → top %d", len(chunks), len(ordenados))
    return ordenados
