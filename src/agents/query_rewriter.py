"""Query rewriter — convierte una consulta dependiente del historial en standalone.

Problema: "y para cooperativas?" no matchea bien en retrieval vectorial porque
le falta el sujeto/tema. Si arriba en el historial hubo "qué considerar para
titulización", la query enriquecida debería ser "qué considerar para
titulización en cooperativas".

Estrategia: LLM con prompt few-shot que:
  - Detecta referencias anafóricas / elípticas (pronombres, "y para X?", "ese tema")
  - Reescribe usando los últimos N turnos como contexto
  - Si la query YA es autónoma, la retorna tal cual (no inventa contenido)

Output: dict con `rewritten` (string) y `was_rewritten` (bool) para telemetría.
"""

from __future__ import annotations

import json
import logging
import re

from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)


PROMPT_REWRITER = """\
Convertís consultas que dependen del historial conversacional en consultas
AUTÓNOMAS. Si la consulta ya es autónoma (no tiene pronombres anafóricos, sí
menciona el tema), la devolvés tal cual.

REGLAS:
- NUNCA inventes información que no está en el historial.
- Si hay pronombres como "ese", "eso", "el caso anterior", "ellos", reescríbelos.
- Si hay elipsis ("y para X?", "qué pasa si Y", "ahora con Z"), expándelos
  reincorporando el sujeto/tema del último turno asistente.
- Mantén el tono y el idioma del usuario.
- Solo JSON, sin texto adicional, sin markdown.

OUTPUT:
{
  "rewritten": "consulta autónoma",
  "was_rewritten": true | false,
  "reason": "breve justificación"
}

EJEMPLOS:

HISTORIAL:
user: qué consideraciones para titulización en empresa de crédito?
assistant: [respuesta sobre titulización, transferencia de cartera, etc.]

CONSULTA: y para cooperativas?
→ {"rewritten": "qué consideraciones para titulización en cooperativas", "was_rewritten": true, "reason": "elipsis del tema 'titulización' del turno previo"}

---

HISTORIAL: (vacío)
CONSULTA: qué dice el artículo 5
→ {"rewritten": "qué dice el artículo 5", "was_rewritten": false, "reason": "ya autónoma"}

---

HISTORIAL:
user: explícame las provisiones procíclicas
assistant: [explica el régimen de provisiones]

CONSULTA: y cuándo se activa?
→ {"rewritten": "cuándo se activa el régimen de provisiones procíclicas", "was_rewritten": true, "reason": "pronombre 'se activa' refiere a provisiones procíclicas"}

---

HISTORIAL:
user: clasificación del deudor según días de atraso
assistant: [tabla de categorías Normal/CPP/Deficiente/Dudoso/Pérdida]

CONSULTA: clasificación del deudor según días de atraso
→ {"rewritten": "clasificación del deudor según días de atraso", "was_rewritten": false, "reason": "consulta autónoma, sin referencias"}

---

HISTORIAL (últimos turnos):
{historial}

CONSULTA ACTUAL: {consulta}

JSON:"""


def _formatear_historial(historial: list[dict], max_turnos: int = 3) -> str:
    """Renderiza los últimos N turnos en formato user/assistant."""
    if not historial:
        return "(vacío)"
    # Tomamos los últimos max_turnos pares (user+assistant)
    ultimos = historial[-(max_turnos * 2):]
    lineas = []
    for m in ultimos:
        rol = "user" if m.get("role") == "user" else "assistant"
        contenido = (m.get("content") or "").strip()
        # Truncar respuestas largas para no inflar el prompt
        if len(contenido) > 400:
            contenido = contenido[:400] + "…"
        lineas.append(f"{rol}: {contenido}")
    return "\n".join(lineas)


def _extraer_json(texto: str) -> dict | None:
    texto = texto.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*", "", texto)
        texto = re.sub(r"\s*```\s*$", "", texto)
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", texto)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


async def reescribir_consulta(
    consulta: str,
    historial: list[dict],
    llm: LLMProvider,
) -> dict:
    """Reescribe consulta para que sea standalone.

    Args:
        consulta: query original del usuario.
        historial: lista de {role, content}. Idealmente últimos N turnos.
        llm: provider.

    Returns:
        dict con keys: rewritten (str), was_rewritten (bool), reason (str).
    """
    if not historial:
        # Sin historial no hay nada que reescribir
        return {"rewritten": consulta, "was_rewritten": False, "reason": "sin_historial"}

    prompt = (
        PROMPT_REWRITER
        .replace("{historial}", _formatear_historial(historial))
        .replace("{consulta}", consulta.strip())
    )
    try:
        resultado = await llm.generate(
            prompt, system=None, temperature=0.0, max_tokens=300
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Query rewriter LLM falló: %s — usar consulta original", exc)
        return {"rewritten": consulta, "was_rewritten": False, "reason": "llm_error"}

    data = _extraer_json(resultado.text)
    if not data or "rewritten" not in data:
        logger.warning("Rewriter output no parseable, primeros 200c: %r",
                       resultado.text[:200])
        return {"rewritten": consulta, "was_rewritten": False, "reason": "parse_error"}

    rewritten = str(data.get("rewritten", consulta)).strip() or consulta
    was_rewritten = bool(data.get("was_rewritten", False))
    reason = str(data.get("reason", "")).strip()[:200]
    return {
        "rewritten": rewritten,
        "was_rewritten": was_rewritten,
        "reason": reason,
    }


def formatear_historial_para_prompt(historial: list[dict], max_turnos: int = 3) -> str:
    """Renderiza el historial como bloque para incluir en el user prompt
    durante la GENERACIÓN (no para retrieval).
    """
    if not historial:
        return ""
    ultimos = historial[-(max_turnos * 2):]
    bloques = ["\n=== HISTORIAL DE LA CONVERSACIÓN ==="]
    for m in ultimos:
        rol = "Usuario" if m.get("role") == "user" else "Asistente"
        contenido = (m.get("content") or "").strip()
        if len(contenido) > 600:
            contenido = contenido[:600] + "…"
        bloques.append(f"\n{rol}: {contenido}")
    bloques.append("\n=== FIN HISTORIAL ===\n")
    return "\n".join(bloques)
