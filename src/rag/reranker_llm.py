"""LLM-based reranker — usa el modelo de generación como juez de relevancia.

Por qué LLM en vez de cross-encoder dedicado:
  - Cero dependencias nuevas (Ollama ya está corriendo).
  - Se beneficia automáticamente del modelo más potente disponible (qwen2.5:14b
    en local, Gemini Flash/Pro en cloud).
  - Más interpretable (puede explicar el score si se le pide).
  - Trade-off: ~3-8s extra de latencia por una llamada extra al LLM.

Estrategia:
  1. Una SOLA llamada al LLM con todos los chunks numerados.
  2. Le pedimos un JSON con score 0-10 por chunk.
  3. Parseamos, ordenamos por score descendente.
  4. Si el LLM falla, fallback al ranking previo.

En producción, esto se reemplazaría por un cross-encoder real (BGE-reranker-v2-m3
con sentence-transformers). El interfaz es idéntico — solo cambia la
implementación interna.
"""

from __future__ import annotations

import json
import logging
import re

from src.llm.base import LLMProvider
from src.storage.pgvector_store import RetrievedChunk

logger = logging.getLogger(__name__)


PROMPT_RERANK = """\
Eres un experto en análisis de relevancia documental sobre normativa SBS Perú.

Te paso una CONSULTA y N FRAGMENTOS numerados. Tu tarea: asignar a cada fragmento
un score de relevancia entre 0.0 (irrelevante) y 10.0 (responde directamente la
consulta).

CRITERIOS:
- Score alto (8-10): el fragmento contiene la respuesta o gran parte de ella.
- Score medio (4-7): el fragmento aporta contexto útil pero no responde directo.
- Score bajo (0-3): el fragmento NO está relacionado con la consulta o solo la
  toca tangencialmente.

OUTPUT (estricto JSON, sin texto adicional):
[{{"id": 1, "score": 8.5}}, {{"id": 2, "score": 4.0}}, ...]

CONSULTA:
{consulta}

FRAGMENTOS:
{fragmentos}
"""


def _formatear_fragmentos(chunks: list[RetrievedChunk]) -> str:
    """Numera los chunks y trunca cada uno para no inflar el prompt."""
    bloques = []
    for i, c in enumerate(chunks, 1):
        # Cap a ~600 chars: suficiente para juzgar relevancia sin gastar tokens
        contenido = c.content.replace("\n", " ").strip()[:600]
        bloques.append(f"[{i}] {contenido}")
    return "\n\n".join(bloques)


def _parsear_scores(texto_llm: str, n_esperados: int) -> list[float] | None:
    """Intenta extraer JSON con scores. Tolera ruido y code fences."""
    # Limpieza de markdown code fences (Gemini suele envolver con ```json...```)
    limpio = texto_llm.strip()
    if limpio.startswith("```"):
        limpio = re.sub(r"^```(?:json)?\s*", "", limpio)
        limpio = re.sub(r"\s*```\s*$", "", limpio)

    # Primer intento: el output completo es JSON válido
    try:
        data = json.loads(limpio)
    except json.JSONDecodeError:
        # Segundo intento: extraer el primer array JSON del texto
        match = re.search(r"\[\s*\{.*?\}\s*\]", limpio, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(data, list):
        return None

    # Mapear id → score (los ids son 1-based)
    scores: dict[int, float] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("id"))
            sc = float(item.get("score", 0))
            scores[idx] = max(0.0, min(10.0, sc))
        except (TypeError, ValueError):
            continue

    if len(scores) < n_esperados // 2:
        # Si recuperamos < mitad de scores, el LLM se rompió
        return None

    return [scores.get(i, 0.0) for i in range(1, n_esperados + 1)]


async def rerank(
    llm: LLMProvider,
    query: str,
    chunks: list[RetrievedChunk],
    *,
    top_k: int = 7,
) -> list[RetrievedChunk]:
    """Reordena chunks por relevancia evaluada por LLM.

    Args:
        llm: LLMProvider (mismo que el de generación).
        query: texto del query original.
        chunks: candidatos a rerankear (típicamente 8-12).
        top_k: cantidad final retornada.

    Returns:
        Chunks ordenados por nuevo score; si el LLM falla, retorna los
        primeros top_k del input sin cambios.
    """
    if not chunks:
        return []
    if len(chunks) == 1:
        return chunks

    prompt = PROMPT_RERANK.format(
        consulta=query,
        fragmentos=_formatear_fragmentos(chunks),
    )

    try:
        resultado = await llm.generate(
            prompt, system=None, temperature=0.0, max_tokens=512
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM reranker falló (%s) — fallback a orden original", exc)
        return chunks[:top_k]

    scores = _parsear_scores(resultado.text, len(chunks))
    if scores is None:
        logger.warning(
            "LLM reranker output no parseable, primeras 200c: %r — fallback",
            resultado.text[:200],
        )
        return chunks[:top_k]

    # Asignar nuevo score normalizado a 0..1 (dividido por 10)
    for chunk, sc in zip(chunks, scores):
        chunk.score = round(sc / 10.0, 4)

    chunks_ordenados = sorted(chunks, key=lambda c: c.score, reverse=True)[:top_k]
    if chunks_ordenados:
        logger.info(
            "LLM rerank OK: top score=%.2f, último=%.2f, sobre %d candidatos",
            chunks_ordenados[0].score,
            chunks_ordenados[-1].score,
            len(chunks),
        )
    return chunks_ordenados


# Nota: rerank_con_vias se define en src/rag/reranker.py (dispatcher)
# para apuntar automáticamente al backend correcto según RERANKER_BACKEND.
