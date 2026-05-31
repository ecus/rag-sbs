"""Detección del perfil de la consulta para ajustar pesos vector vs BM25.

Tres perfiles:
- **lexical**: la consulta menciona entidades específicas (número de
  resolución, artículo, cuenta contable, número de circular). BM25 es muy
  efectivo aquí porque el match literal es lo que importa.
- **semantic**: pregunta abierta, conceptual ("¿qué se requiere para X?",
  "¿cómo se gestiona Y?"). Vector embeddings capturan mejor el significado.
- **balanced**: queries mixtas o sin señales claras.

Los pesos se aplican como coeficientes a las contribuciones RRF de cada
sub-ranking:

    score_final = w_vec * (1/(k+rank_vec)) + w_txt * (1/(k+rank_txt))

con w_vec + w_txt = 2.0 para preservar la escala de RRF estándar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

PerfilQuery = Literal["lexical", "semantic", "balanced"]


@dataclass
class PerfilDetectado:
    tipo: PerfilQuery
    w_vector: float
    w_texto: float
    razon: str


# Patrones lexicales (entidades específicas peruano-regulatorias)
_PATRONES_LEXICALES = [
    (re.compile(r"\b\d{1,5}\s*[-–]\s*\d{4}\b"), "número de resolución/ley NNNN-YYYY"),
    (re.compile(r"\bres(?:oluci[oó]n)?\.?\s*sbs\b", re.IGNORECASE), "menciona Resolución SBS"),
    (re.compile(r"\bcircular\s*[a-z]?\s*-?\s*\d{2,4}\b", re.IGNORECASE), "menciona Circular"),
    (re.compile(r"\bart[ií]culo\s+\d+", re.IGNORECASE), "menciona Artículo N°"),
    (re.compile(r"\bley\s+\d{4,5}\b", re.IGNORECASE), "menciona Ley N°"),
    (re.compile(r"\bdecreto\s+(?:legislativo|supremo|urgencia)\s+\d+", re.IGNORECASE),
     "menciona Decreto"),
    (re.compile(r"\bcuenta\s+\d{4,6}(?:\.\d+)?\b", re.IGNORECASE), "menciona cuenta contable"),
    (re.compile(r"\banexo\s+\d+", re.IGNORECASE), "menciona Anexo"),
    (re.compile(r"\bcap[ií]tulo\s+[IVX\d]+", re.IGNORECASE), "menciona Capítulo"),
    (re.compile(r"\b(?:G|G-)\d{3}\b"), "código de circular G-NNN"),
]

# Señales semánticas (preguntas abiertas conceptuales)
_PATRONES_SEMANTICOS = [
    re.compile(r"^¿?(qué|cómo|por qué|cuándo|cuáles?|para qué|en qué)\s",
               re.IGNORECASE),
    re.compile(r"^(explica|describe|define|compara|analiza|sintetiza)\s",
               re.IGNORECASE),
    re.compile(r"\b(diferencia|similitud|implicancia|consecuencia|relación)\s",
               re.IGNORECASE),
]


def detectar(query: str) -> PerfilDetectado:
    """Analiza la consulta y devuelve perfil + pesos sugeridos."""
    if not query or len(query) < 5:
        return PerfilDetectado("balanced", 1.0, 1.0, "query muy corta")

    q = query.strip()

    # Cuántas señales lexicales encontró
    senales_lex: list[str] = []
    for patron, etiqueta in _PATRONES_LEXICALES:
        if patron.search(q):
            senales_lex.append(etiqueta)
            if len(senales_lex) >= 2:
                break

    senales_sem = [
        p.pattern[:30] for p in _PATRONES_SEMANTICOS if p.search(q)
    ]

    if len(senales_lex) >= 2:
        # Múltiples entidades específicas → priorizar BM25 fuertemente
        return PerfilDetectado(
            "lexical", w_vector=0.6, w_texto=1.4,
            razon=f"lexical fuerte: {', '.join(senales_lex)}",
        )
    if len(senales_lex) == 1 and not senales_sem:
        return PerfilDetectado(
            "lexical", w_vector=0.8, w_texto=1.2,
            razon=f"lexical: {senales_lex[0]}",
        )
    if senales_sem and not senales_lex:
        return PerfilDetectado(
            "semantic", w_vector=1.3, w_texto=0.7,
            razon=f"semántico: {senales_sem[0]}",
        )
    return PerfilDetectado(
        "balanced", w_vector=1.0, w_texto=1.0,
        razon="balanced (sin señales fuertes)",
    )
