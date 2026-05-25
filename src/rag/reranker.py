"""Dispatcher de reranking — selecciona backend por config.

Backends disponibles:
  - llm           (default, sin deps extra)        → src/rag/reranker_llm.py
  - cross_encoder (requiere sentence-transformers) → src/rag/reranker_cross_encoder.py
  - cohere        (requiere COHERE_API_KEY)        → src/rag/reranker_cohere.py

Configuración:
  RERANKER_BACKEND=llm | cross_encoder | cohere

El interfaz `rerank(llm, query, chunks, top_k)` es idéntico entre todos los
backends; el primer argumento `llm` solo lo usa el backend `llm`, los otros
lo ignoran. Esto permite swap sin tocar el código que invoca al reranker.

Decisión arquitectónica (ADR-006, ver doc):
  - En dev local (VM podman 18 GB): backend `llm` para evitar instalación
    pesada de torch + sentence-transformers (~3 GB).
  - En cloud (Cloud Run / GKE sin restricción de disco): `cross_encoder`
    para mejor latencia y calidad.
  - En producción enterprise: `cohere` para latencia sub-100ms y SLA.
"""

from __future__ import annotations

from src.config import get_settings
from src.llm.base import LLMProvider
from src.storage.pgvector_store import RetrievedChunk


async def rerank(
    llm: LLMProvider,
    query: str,
    chunks: list[RetrievedChunk],
    *,
    top_k: int = 7,
) -> list[RetrievedChunk]:
    """Dispatcher — delega al backend configurado."""
    backend = get_settings().reranker_backend

    if backend == "cross_encoder":
        from src.rag.reranker_cross_encoder import rerank as _impl
    elif backend == "cohere":
        from src.rag.reranker_cohere import rerank as _impl
    else:  # default: llm
        from src.rag.reranker_llm import rerank as _impl

    return await _impl(llm, query, chunks, top_k=top_k)


async def rerank_con_vias(
    llm: LLMProvider,
    query: str,
    chunks: list[RetrievedChunk],
    vias: list[str],
    *,
    top_k: int = 7,
) -> tuple[list[RetrievedChunk], list[str]]:
    """Versión que preserva la correspondencia chunk → via."""
    if not chunks:
        return [], []
    via_por_id = {chunk.chunk_id: via for chunk, via in zip(chunks, vias)}
    chunks_ordenados = await rerank(llm, query, chunks, top_k=top_k)
    vias_ordenadas = [via_por_id.get(c.chunk_id, "vector") for c in chunks_ordenados]
    return chunks_ordenados, vias_ordenadas
