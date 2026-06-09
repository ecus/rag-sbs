"""Filtrado semántico de turnos relevantes del historial.

Problema: pasar siempre los últimos N turnos al LLM provoca contaminación
de contexto (ej. usuario hablaba de titulización, ahora pregunta sobre
RCD, pero el historial fuerza al LLM a interpretar RCD bajo titulización).

Solución: para cada turno del historial, calculamos su similitud semántica
con la query actual. Solo incluimos turnos cuya similitud supere un
umbral. Así el LLM ve:
- Si el usuario está continuando un tema → ve los turnos relacionados
- Si cambió de tema → ve solo turnos del nuevo tema (o ninguno)
"""

from __future__ import annotations

import logging
import math
from typing import Any

from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)


def _cosine(a: list[float], b: list[float]) -> float:
    """Similitud coseno entre dos vectores."""
    if not a or not b or len(a) != len(b):
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def _turno_a_texto(turno: dict) -> str:
    """Concatena texto de un turno (rol + contenido)."""
    rol = turno.get("role", turno.get("rol", ""))
    contenido = turno.get("content", turno.get("texto", ""))
    if not contenido:
        return ""
    return f"{rol}: {contenido}"


async def seleccionar_turnos_relevantes(
    query: str,
    historial: list[dict],
    llm: LLMProvider,
    *,
    umbral_relevancia: float = 0.55,
    max_turnos_relevantes: int = 6,
    siempre_incluir_ultimos: int = 1,
) -> tuple[list[dict], dict[str, Any]]:
    """Selecciona del historial solo los turnos semánticamente relevantes
    a la query actual.

    Args:
        query: consulta del usuario actual.
        historial: lista completa de turnos {role, content}.
        llm: provider para embeddings.
        umbral_relevancia: similitud mínima para considerar relevante (0..1).
        max_turnos_relevantes: tope superior de turnos a devolver.
        siempre_incluir_ultimos: # de turnos finales que siempre se incluyen
            (asume follow-up: ej. "dame un ejemplo" se entiende solo con
            el último turno aunque la similitud sea baja).

    Returns:
        (turnos_filtrados, telemetria)
    """
    if not historial:
        return [], {"total": 0, "relevantes": 0, "razon": "vacio"}

    # Si hay muy pocos turnos, devolvemos todos
    if len(historial) <= siempre_incluir_ultimos:
        return historial, {"total": len(historial), "relevantes": len(historial),
                            "razon": "muy_pocos_para_filtrar"}

    # Generar embedding de la query
    try:
        vec_query = (await llm.embed([query]))[0]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Memory relevance: embed query falló (%s) — fallback a últimos N", exc)
        return historial[-max_turnos_relevantes:], {
            "total": len(historial), "relevantes": min(len(historial), max_turnos_relevantes),
            "razon": "embed_fail",
        }

    # Pares user+assistant juntos para puntuar
    pares = []
    i = 0
    while i < len(historial):
        if i + 1 < len(historial) and \
           historial[i].get("role", historial[i].get("rol")) == "user" and \
           historial[i + 1].get("role", historial[i + 1].get("rol")) == "assistant":
            pares.append((i, [historial[i], historial[i + 1]]))
            i += 2
        else:
            pares.append((i, [historial[i]]))
            i += 1

    if not pares:
        return [], {"total": 0, "relevantes": 0, "razon": "sin_pares"}

    # Texto representativo de cada par
    textos_pares = [
        " | ".join(_turno_a_texto(t) for t in p[1])[:2000]
        for p in pares
    ]

    try:
        embeddings_pares = await llm.embed(textos_pares)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Memory relevance: embed pares falló (%s)", exc)
        return historial[-max_turnos_relevantes:], {
            "total": len(historial), "relevantes": min(len(historial), max_turnos_relevantes),
            "razon": "embed_pares_fail",
        }

    # Puntuar cada par
    scores: list[tuple[int, float, list[dict]]] = []
    for (idx, turnos_par), emb in zip(pares, embeddings_pares):
        score = _cosine(vec_query, emb)
        scores.append((idx, score, turnos_par))

    # Siempre incluir los últimos N independiente del score
    indices_forzados = set(
        s[0] for s in scores[-siempre_incluir_ultimos:]
    )

    # Filtrar por umbral + agregar forzados
    seleccionados = [
        s for s in scores
        if s[1] >= umbral_relevancia or s[0] in indices_forzados
    ]

    # Aplicar cap superior — preferimos los más recientes empate-en-score
    if len(seleccionados) > max_turnos_relevantes:
        # Ordenar por score desc, romper empates por orden cronológico (más nuevo primero)
        seleccionados.sort(key=lambda s: (s[1], s[0]), reverse=True)
        seleccionados = seleccionados[:max_turnos_relevantes]

    # Reordenar cronológicamente para mantener flujo conversacional
    seleccionados.sort(key=lambda s: s[0])

    historial_filtrado = []
    for _, _, turnos_par in seleccionados:
        historial_filtrado.extend(turnos_par)

    telemetria = {
        "total": len(historial),
        "relevantes": len(historial_filtrado),
        "umbral": umbral_relevancia,
        "scores": [round(s[1], 3) for s in scores],
        "razon": "embedding_filter",
    }

    logger.info(
        "Memory relevance: %d/%d turnos relevantes (umbral=%.2f, scores=%s)",
        len(historial_filtrado), len(historial), umbral_relevancia,
        telemetria["scores"],
    )

    return historial_filtrado, telemetria
