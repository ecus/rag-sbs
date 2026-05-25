"""Agente planificador — decide si responder directo o pedir clarificaciones.

Patrón inspirado en ReAct + 'reflection': antes de gastar tokens en retrieval +
generation completos, un LLM-as-planner evalúa si el query es suficientemente
específico para producir una respuesta útil.

Decisiones del planner:
  - `answer_directly`: query claro, contexto suficiente → flujo normal RAG
  - `ask_clarifications`: query ambiguo o falta contexto crítico → pedir 2-4
    preguntas al usuario antes de retrievar

Heurísticas del prompt (no hard-coded; las decide el LLM):
  - Tipo de entidad supervisada (banco, financiera, caja, cooperativa, EDPYME)
  - Tamaño / segmento (corporativo, microfinanzas, retail)
  - Tipo específico de operación (no solo "operación")
  - Rol del consultante (cumplimiento, contabilidad, riesgo, gerencia)
  - Si la pregunta es factual cerrada vs. consultoría abierta

Devuelve JSON estricto; si el LLM se rompe parseando, fallback a "responder
directo" (más seguro que bloquear al usuario).
"""

from __future__ import annotations

import json
import logging
import re

from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)


PROMPT_PLANNER = """\
Eres un consultor regulatorio SBS Perú. Decides si una consulta puede responderse
directamente o si **clarificar produciría una respuesta sustancialmente diferente**.

⚠️ DEFAULT FUERTE = "answer_directly". Solo clarificas si NO clarificar produciría
una respuesta inútil o confusa. La mayoría de queries deben ir directo.

REGLAS:

→ "answer_directly" SIEMPRE cuando:
- El query pide info factual: "qué dice el artículo X", "qué es Y", "porcentaje de Z"
- El query pide definición / explicación general de un concepto
- El query es exploratorio ("explícame", "cómo funciona", "qué establece")
- El query menciona el tipo de entidad O el tipo de operación (al menos UNO)
- El query es sobre un tema regulatorio específico aunque el rol no esté claro

→ "ask_clarifications" SOLO cuando se cumplen TODAS:
1. Falta tipo de entidad Y tipo de operación
2. La respuesta cambiaría drásticamente según la respuesta
3. El query es muy genérico tipo "qué debo hacer" o "qué considerar" SIN tema

EJEMPLOS (estudiar y replicar):

Q: "qué porcentaje de provisión específica para categoría Dudoso"
→ {"action": "answer_directly", "reason": "factual cerrada, una respuesta normativa"}

Q: "soy una empresa de crédito y voy a hacer titularización, qué debo tener en cuenta"
→ {"action": "answer_directly", "reason": "menciona tipo entidad + operación específica"}

Q: "explícame el sistema de provisiones procíclicas"
→ {"action": "answer_directly", "reason": "pregunta exploratoria, no requiere contexto"}

Q: "qué establece la SBS sobre ciberseguridad"
→ {"action": "answer_directly", "reason": "tema regulatorio definido"}

Q: "qué debo tener en cuenta para mi operación"
→ {"action": "ask_clarifications", "reason": "falta tipo de operación Y tipo de entidad"}

Q: "qué tasa aplica"
→ {"action": "ask_clarifications", "reason": "falta producto, deudor, entidad"}

REGLAS DE PREGUNTAS (si decides clarificar):
- Mínimo 2, máximo 3 preguntas
- Que cada una cambie genuinamente la respuesta
- Preferir "select" con opciones concretas cuando aplique

OUTPUT: JSON estricto, SIN texto adicional, SIN markdown, SIN comentarios.

Schema:
{
  "action": "answer_directly" | "ask_clarifications",
  "reason": "1 línea breve",
  "questions": [
    {"id": "q1", "label": "...", "type": "text|select|multiselect",
     "options": [...]|null, "rationale": "..."}
  ]
}

CONSULTA: {consulta}

JSON:"""


def _extraer_json(texto: str) -> dict | None:
    """Intenta parsear JSON del output del LLM, tolerando ruido y code fences."""
    texto = texto.strip()
    # Limpieza de markdown fences ```json ... ```
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*", "", texto)
        texto = re.sub(r"\s*```\s*$", "", texto)
    # Caso 1: el texto completo es JSON
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    # Caso 2: extraer el primer objeto JSON con balanceo de llaves
    match = re.search(r"\{[\s\S]*\}", texto)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _validar_y_normalizar(data: dict) -> dict:
    """Asegura que el dict tenga la estructura esperada."""
    action = data.get("action", "answer_directly")
    if action not in ("answer_directly", "ask_clarifications"):
        action = "answer_directly"

    questions = []
    if action == "ask_clarifications":
        for q in data.get("questions") or []:
            if not isinstance(q, dict):
                continue
            qid = str(q.get("id", "")).strip()
            label = str(q.get("label", "")).strip()
            if not qid or not label:
                continue
            qtype = q.get("type", "text")
            if qtype not in ("text", "select", "multiselect"):
                qtype = "text"
            options = q.get("options")
            if qtype in ("select", "multiselect"):
                if not isinstance(options, list) or not options:
                    qtype = "text"
                    options = None
                else:
                    options = [str(o) for o in options][:8]
            else:
                options = None
            questions.append({
                "id": qid,
                "label": label,
                "type": qtype,
                "options": options,
                "rationale": str(q.get("rationale", "")).strip() or None,
            })
        # Si decidió clarificar pero no hay preguntas válidas, cambia a directo
        if not questions:
            action = "answer_directly"

    return {
        "action": action,
        "reason": str(data.get("reason", "")).strip()[:300] or None,
        "questions": questions[:4],
    }


async def decidir_plan(query: str, llm: LLMProvider) -> dict:
    """Llama al planner y retorna decisión normalizada.

    Si el LLM falla o el output no es parseable, retorna fallback seguro
    ("answer_directly") — preferimos responder algo a bloquear al usuario.
    """
    if not query or not query.strip():
        return {"action": "answer_directly", "reason": "query vacía", "questions": []}

    prompt = PROMPT_PLANNER.replace("{consulta}", query.strip())
    try:
        resultado = await llm.generate(
            prompt, system=None, temperature=0.0, max_tokens=512
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Planner LLM falló: %s — fallback directo", exc)
        return {"action": "answer_directly", "reason": "planner_error", "questions": []}

    data = _extraer_json(resultado.text)
    if not data:
        logger.warning("Planner output no parseable, primeras 200c: %r", resultado.text[:200])
        return {"action": "answer_directly", "reason": "parse_error", "questions": []}

    return _validar_y_normalizar(data)


def enriquecer_consulta_con_respuestas(
    query_original: str, respuestas: dict[str, str | list[str]]
) -> str:
    """Combina la consulta original con las respuestas a las clarificaciones.

    Formato resultante es un prompt enriquecido que el retriever puede usar
    directamente y que el LLM verá como contexto explícito.
    """
    if not respuestas:
        return query_original
    bloques = [f"Consulta original: {query_original.strip()}"]
    bloques.append("\nContexto adicional aportado por el usuario:")
    for clave, valor in respuestas.items():
        if isinstance(valor, list):
            valor_txt = ", ".join(str(v) for v in valor)
        else:
            valor_txt = str(valor)
        bloques.append(f"- {clave}: {valor_txt}")
    return "\n".join(bloques)
