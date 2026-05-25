"""Chunking de documentos.

MVP: chunker recursivo por caracteres con overlap. Sprint 2 evaluará semantic
chunking de LlamaIndex (`SemanticSplitterNodeParser`).

Decisión: 768 tokens / overlap 12% según sec 3.6 del documento de arquitectura.
Aproximación: 1 token ≈ 4 chars en español → 3000 chars / 360 overlap.
"""

from __future__ import annotations

import re

# Aproximación pragmática para MVP. Sprint 2: usar tiktoken para precisión.
CHARS_POR_TOKEN_ES = 4


def chunk_text(
    text: str,
    *,
    chunk_size_tokens: int = 768,
    overlap_tokens: int = 96,
) -> list[str]:
    """Divide texto en chunks con overlap, respetando saltos de párrafo.

    Estrategia:
    1. Separa en párrafos (split por doble newline)
    2. Acumula párrafos hasta llegar al tamaño objetivo
    3. Si un párrafo es más grande que chunk_size, lo parte por oraciones
    """
    if not text or not text.strip():
        return []

    tamano_chars = chunk_size_tokens * CHARS_POR_TOKEN_ES
    overlap_chars = overlap_tokens * CHARS_POR_TOKEN_ES

    # Normalizar whitespace
    texto = re.sub(r"\r\n", "\n", text)
    parrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]

    fragmentos: list[str] = []
    actual: list[str] = []
    largo_actual = 0

    for parrafo in parrafos:
        if len(parrafo) > tamano_chars:
            # Párrafo gigante: partir por oración
            oraciones = re.split(r"(?<=[.!?])\s+", parrafo)
            for oracion in oraciones:
                if largo_actual + len(oracion) > tamano_chars and actual:
                    fragmentos.append(" ".join(actual))
                    # Overlap: arrastra últimas N chars
                    cola = " ".join(actual)[-overlap_chars:] if overlap_chars > 0 else ""
                    actual = [cola, oracion] if cola else [oracion]
                    largo_actual = sum(len(s) for s in actual)
                else:
                    actual.append(oracion)
                    largo_actual += len(oracion)
        else:
            if largo_actual + len(parrafo) > tamano_chars and actual:
                fragmentos.append("\n\n".join(actual))
                cola = "\n\n".join(actual)[-overlap_chars:] if overlap_chars > 0 else ""
                actual = [cola, parrafo] if cola else [parrafo]
                largo_actual = sum(len(s) for s in actual)
            else:
                actual.append(parrafo)
                largo_actual += len(parrafo)

    if actual:
        fragmentos.append("\n\n".join(actual))

    return [f for f in fragmentos if len(f.strip()) > 50]  # filtra fragmentos triviales
