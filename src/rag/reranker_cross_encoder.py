"""Reranker basado en cross-encoder dedicado (BAAI/bge-reranker-base por default).

Requisitos:
  pip install sentence-transformers torch --index-url https://download.pytorch.org/whl/cpu

NO está activo en dev local por restricción de disco en la VM podman (18 GB).
En Cloud Run / Kubernetes con disco ilimitado:
  1. Descomentar las deps en pyproject.toml + Dockerfile
  2. Pre-descargar modelo en Dockerfile
  3. RERANKER_BACKEND=cross_encoder en env

Ventaja vs LLM-as-reranker:
  - Latencia: ~200-500 ms vs 3-10 s (CPU)
  - Calidad: ligeramente mejor en queries con mucho ruido semántico
  - Sin coste de tokens LLM
"""

from __future__ import annotations

import logging
from threading import Lock

from src.config import get_settings
from src.storage.pgvector_store import RetrievedChunk

logger = logging.getLogger(__name__)

_modelo_singleton = None
_lock = Lock()


def _obtener_modelo():
    """Carga lazy + thread-safe. Falla con mensaje claro si las deps no están."""
    global _modelo_singleton
    if _modelo_singleton is not None:
        return _modelo_singleton
    with _lock:
        if _modelo_singleton is not None:
            return _modelo_singleton
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers no instalado. Para usar este backend:\n"
                "  pip install sentence-transformers torch --index-url "
                "https://download.pytorch.org/whl/cpu\n"
                "O cambiar RERANKER_BACKEND a 'llm' o 'cohere'."
            ) from exc

        nombre = get_settings().cross_encoder_model
        logger.info("Cargando cross-encoder %s (singleton)…", nombre)
        _modelo_singleton = CrossEncoder(nombre, max_length=512)
        return _modelo_singleton


async def rerank(
    llm,  # noqa: ARG001  — firma compartida con LLM backend
    query: str,
    chunks: list[RetrievedChunk],
    *,
    top_k: int = 7,
) -> list[RetrievedChunk]:
    if not chunks:
        return []
    if len(chunks) == 1:
        return chunks
    modelo = _obtener_modelo()
    pares = [[query, c.content] for c in chunks]
    scores = modelo.predict(pares, batch_size=8, show_progress_bar=False)
    for chunk, score in zip(chunks, scores):
        chunk.score = round(float(score), 4)
    ordenados = sorted(chunks, key=lambda c: c.score, reverse=True)[:top_k]
    logger.info("cross-encoder rerank: %d → top %d", len(chunks), len(ordenados))
    return ordenados
