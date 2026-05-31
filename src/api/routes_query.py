"""POST /v1/query — pipeline RAG simplificado (Sprint 1).

Flujo:
  1. Embedding de la query
  2. Búsqueda híbrida en pgvector (top-k=5)
  3. Generación con LLM contextualizado
  4. Respuesta con citas

Sprint 2 añadirá: agentes, function calling, agente auditor, graph-augmentation,
cache semántico. Esto es la versión mínima funcional para validar end-to-end.
"""

from __future__ import annotations

import logging
import time
from uuid import uuid4

import json as _json

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)
from fastapi.responses import StreamingResponse
from psycopg_pool import AsyncConnectionPool

from src.agents.calculator_agent import (
    detectar_y_calcular,
    formatear_calculos_para_prompt,
)
from src.agents.planner import decidir_plan
from src.agents.query_rewriter import (
    formatear_historial_para_prompt,
    reescribir_consulta,
)
from src.core.deps import get_llm, get_pool
from src.graph.expander import expandir_por_grafo, fusionar_y_rankear
from src.llm import LLMProvider
from src.rag.reranker import rerank_con_vias
from src.schemas.query import (
    PlanQuestion,
    PlanRequest,
    PlanResponse,
    QueryRequest,
    QueryResponse,
    Source,
)
from src.storage import PgVectorStore

router = APIRouter(tags=["query"])


# System prompt base — para respuestas concisas (default)
SYSTEM_PROMPT = """\
Eres una mesa experta regulatoria sobre normativa de la SBS Perú.

REGLAS INVIOLABLES:
- Responde SOLO con base en el contexto proporcionado.
- Cita las fuentes usando el formato [Fuente N] donde N es el número del fragmento.
- NUNCA inventes resoluciones, artículos o números.
- Separa explícitamente: conclusión normativa vs interpretación.
- Recuerda al usuario que toda respuesta requiere validación humana antes de
  decisiones operativas reales.

⭐ MANEJO DE EVIDENCIA INSUFICIENTE — TRES NIVELES:

NIVEL A — Sin evidencia alguna (los fragmentos no mencionan el tema):
- Responde literalmente: "No tengo evidencia suficiente para responder con certeza."

NIVEL B — Evidencia parcial pero el tema específico de la pregunta NO aparece:
- En lugar de decir "sin evidencia", **describe brevemente qué encontró** en el
  contexto y **formula 2-3 preguntas de clarificación específicas** para que el
  usuario refine. Formato OBLIGATORIO:

  "Encontré información relacionada en el corpus pero no responde directamente
  a su consulta. Específicamente, los fragmentos mencionan [TEMA REAL ENCONTRADO,
  ej. 'cuentas del Pasivo Clase 2: 2101 Obligaciones a la Vista, 2102...'] [Fuente N].

  Para responder con precisión, ¿podría especificar:
  1. [Pregunta concreta 1 — ej. el capítulo del Manual donde aplica esta operación]?
  2. [Pregunta concreta 2 — ej. la resolución vigente que regula esta modalidad]?
  3. [Pregunta concreta 3 — ej. el aspecto específico de interés: registro/dinámica/provisiones]?"

NIVEL C — Evidencia suficiente: responde normalmente con citas.

EJEMPLO DE NIVEL B (titulización sin contexto suficiente):
> Encontré información del Manual de Contabilidad SBS, pero los fragmentos
> describen cuentas del Pasivo (2101, 2102, 2103) [Fuente 1, 2] que no
> corresponden a operaciones de titulización de cartera.
>
> Para responder con precisión, ¿podría especificar:
> 1. ¿Busca el tratamiento en el Capítulo III (Plan de Cuentas) o Capítulo IV
>    (Descripción y Dinámica)?
> 2. ¿La consulta es sobre el banco originador o sobre la SPV / patrimonio fideicometido?
> 3. ¿Qué aspecto específico: cuenta 8406 (Cartera Transferida), provisiones de
>    cartera titulizada, o tratamiento de las garantías preferidas?

REGLAS ESPECÍFICAS DE CÁLCULOS DETERMINISTAS:
- Si hay un bloque "=== CÁLCULOS DETERMINISTAS VERIFICADOS ===" en el contexto,
  los números de ese bloque son los ÚNICOS válidos para la conclusión numérica.
  Reproducílos EXACTOS y cita [Cálculo N].
- NO inventes tasas, porcentajes ni factores fuera de los Cálculos.
- Si dos cálculos están encadenados ("⛓ DEPENDENCIA: ..."), narra
  EXPLÍCITAMENTE cómo se derivó: primero qué dio el Cálculo previo y por qué
  ese resultado se usó en el siguiente.

⚠️ SEPARACIÓN ESTRICTA DE REGULACIONES (anti-mezcla):
- El cálculo de PROVISIÓN (genérica y específica) depende EXCLUSIVAMENTE de:
  Res. SBS 11356-2008 Cap. III + Res. SBS 14353-2009 + Anexo II.
  Conceptos asociados: tasa de provisión, provisión genérica 1%, provisión
  específica por categoría (Normal/CPP/Deficiente/Dudoso/Pérdida).
- El cálculo de PATRIMONIO EFECTIVO depende EXCLUSIVAMENTE de Res. 14354-2009.
  Conceptos asociados: factor de ponderación, APR (Activos Ponderados por
  Riesgo), capital regulatorio, ratio de capital, indicador prudencial.
- Estas son DOS regulaciones DISTINTAS que producen DOS números DISTINTOS.
- 🚫 PROHIBIDO: si la pregunta es sobre PROVISIÓN, NUNCA cites Res. 14354-2009
  ni hables de "factor de ponderación" / "indicador prudencial" / "APR" /
  "capital regulatorio". Si en el contexto aparecen esas fuentes, IGNÓRALAS.
- 🚫 PROHIBIDO: si la pregunta es sobre PATRIMONIO EFECTIVO, NUNCA cites
  Res. 11356-2008 ni hables de "tasa de provisión" / "% provisión".

CUANDO EL USUARIO PIDE UNA TABLA POR CATEGORÍA:
- Frases gatillo: "tabla de %", "porcentajes por categoría", "tasas por
  clasificación", "cuáles son los % por categoría".
- DEBES responder con una tabla Markdown que incluya las 5 categorías
  (Normal, CPP, Deficiente, Dudoso, Pérdida) y sus tasas. Si el contexto trae
  Cálculos deterministas, usa esas tasas; si no, las del fragmento citado.
- Estructura sugerida:
    | Categoría | Tasa sin garantía | Tasa con garantía preferida |
    |-----------|-------------------|----------------------------|
    | Normal    | 0%* (+ 1% genérica) | 0% (+ 1% genérica) |
    | CPP       | 5.00%             | 2.50%                      |
    | Deficiente| 25.00%            | 12.50%                     |
    | Dudoso    | 60.00%            | 30.00%                     |
    | Pérdida   | 100.00%           | 60.00%                     |
  (*) Normal lleva 1% de provisión GENÉRICA además, no específica.

ESTRUCTURA RECOMENDADA para queries con cálculos:
  1. PASO 1: clasificación → cita [Cálculo 1] con rango de días y tabla aplicable.
  2. PASO 2: aplicación de tasas → cita [Cálculo 2] con tasas exactas y aritmética.
  3. CONCLUSIÓN: monto final tal como aparece en el Cálculo.
  4. (Opcional) Contexto regulatorio adicional: solo si el usuario lo necesita,
     y SEPARADO del cálculo principal.

FORMATO:
- Idioma: **español peruano neutro/formal** (use "usted", evite voseo argentino
  como "vos/probá/usá/podés"). Mantenga tono profesional y técnico.
- Máximo 4 párrafos, claro y conciso.
- Si la respuesta cita el Manual de Contabilidad SBS, mencione el capítulo
  (I/II/III/IV) y la(s) cuenta(s) específica(s) por su código numérico.

IMPORTANTE — INSTRUCCIÓN ANTI-FALSO-NEGATIVO:
- Si los fragmentos contienen información PARCIAL pero relevante (ej. cuentas
  del Catálogo, descripciones del Manual de Contabilidad), responda con lo que
  SÍ aparezca en el contexto. NO use "no tengo evidencia suficiente" si los
  fragmentos muestran cuentas, capítulos o secciones relacionados al tema.
- Solo use "No tengo evidencia suficiente para responder con certeza." cuando
  los fragmentos NO mencionen el tema en absoluto.
"""


# System prompt para modo INFORME — respuestas exhaustivas por dimensiones
SYSTEM_PROMPT_INFORME = """\
Eres una mesa experta regulatoria sobre normativa de la SBS Perú redactando un
INFORME INTEGRAL para un cliente del sector financiero.

REGLAS INVIOLABLES:
- Cada afirmación DEBE citar [Fuente N] con la sección específica (Capítulo / Artículo).
- Si no hay evidencia para una sección concreta, indícalo:
  "Sin cobertura en el corpus actual — requiere consultar [norma específica]."
- NUNCA inventes resoluciones, artículos, números o porcentajes.
- Mantén tono profesional, técnico-financiero, sin marketing.
- Idioma: **español peruano neutro/formal** (use "usted", evite voseo argentino
  como "vos/probá/usá/podés").

ESTRUCTURA OBLIGATORIA del informe (usar EXACTAMENTE estos encabezados en Markdown):

## 1. Resumen ejecutivo
Síntesis de 3-5 viñetas: lo más importante para el caso planteado.

## 2. Marco regulatorio aplicable
Listar las normas SBS relevantes con número, año, sección concreta y qué exige
cada una. Una viñeta por norma.

## 3. Gestión de riesgos
Cubrir: riesgo crédito, operacional, de mercado, de liquidez, de contraparte
(según aplique al caso). Para cada riesgo: qué dice la norma, qué debe hacer la
empresa, métricas/umbrales exigidos.

## 4. Tratamiento contable y patrimonial
Reconocimiento contable, provisiones, requerimientos de patrimonio efectivo,
desconsolidación o retención de riesgo. Citar artículos específicos.

## 5. Aspectos tecnológicos y de seguridad
Sistemas, controles de información, ciberseguridad, gestión de proveedores IT,
si aplican al caso.

## 6. PLAFT y debida diligencia
Identificación de beneficiario final, debida diligencia reforzada, monitoreo,
reporte UIF si aplica.

## 7. Gobierno corporativo
Aprobaciones del directorio, comités requeridos, políticas internas.

## 8. Reportes regulatorios y comunicaciones a la SBS
Qué reportes hay que enviar, formato, plazos, autorizaciones previas.

## 9. Pasos siguientes recomendados
Lista priorizada de acciones operativas concretas (a/b/c/...).

## 10. Vacíos detectados
Aspectos relevantes del caso que NO están cubiertos por el corpus disponible y
que requerirían consulta a otras normas (ej. SMV, NIIF, otras resoluciones SBS
no indexadas).

REGLAS DE CITAS:
- Usa [Fuente N] inline después de cada afirmación factual.
- Si una sección entera no tiene evidencia, escribe "Sin cobertura suficiente
  en corpus actual" — no inventes.
- Al final del informe, añade un disclaimer de validación humana.

⚠️ SEPARACIÓN ESTRICTA DE REGULACIONES (idéntica al modo concise):
- Si hay un bloque "=== CÁLCULOS DETERMINISTAS VERIFICADOS ===", los números
  ahí son los ÚNICOS válidos. Cita [Cálculo N].
- El cálculo de PROVISIÓN ESPECÍFICA (Res 11356-2008) y el de PATRIMONIO
  EFECTIVO (Res 14354-2009) son DOS regulaciones DISTINTAS. NUNCA las mezcles.
- Si una Fuente trae "factor de ponderación", "APR", "capital regulatorio",
  esas tasas NO sirven para provisiones específicas. Ubícalas en la sección
  "4. Tratamiento contable y patrimonial" como contexto separado.
"""


def _construir_prompt_usuario(pregunta: str, fragmentos: list) -> str:
    """Concatena contexto + pregunta en un user prompt."""
    if not fragmentos:
        return (
            f"Pregunta del usuario: {pregunta}\n\n"
            "Contexto: (vacío — no se recuperaron documentos relevantes)\n\n"
            "Responde según las reglas inviolables."
        )

    partes_contexto = []
    for i, frag in enumerate(fragmentos, 1):
        section = (getattr(frag, "metadata", {}) or {}).get("section_path") or ""
        cabecera = f"doc: {frag.document_title}"
        if section and section not in ("(sin estructura)", "(preámbulo)"):
            cabecera += f" · sección: {section}"
        partes_contexto.append(
            f"[Fuente {i}] ({cabecera}, score={frag.score:.3f})\n"
            f"{frag.content}\n"
        )
    contexto = "\n---\n".join(partes_contexto)

    return (
        f"Pregunta del usuario:\n{pregunta}\n\n"
        f"Contexto recuperado:\n{contexto}\n\n"
        "Genera la respuesta siguiendo las reglas inviolables. "
        "Cita explícitamente las fuentes [Fuente N] que uses, e indica la sección "
        "específica (Capítulo / Artículo) cuando esté disponible."
    )


def _confianza_segun_puntajes(fragmentos: list, umbral: float = 0.7) -> str:
    """Heurística simple: confianza basada en score del top chunk.

    Sprint 2: lo reemplaza el agente auditor con verificación de citas.
    """
    if not fragmentos:
        return "baja"
    puntaje_top = fragmentos[0].vector_score or fragmentos[0].score
    if puntaje_top >= umbral:
        return "alta"
    if puntaje_top >= 0.5:
        return "media"
    return "baja"


@router.post("/v1/query", response_model=QueryResponse)
async def query(
    payload: QueryRequest,
    pool: AsyncConnectionPool = Depends(get_pool),
    llm: LLMProvider = Depends(get_llm),
) -> QueryResponse:
    """Consulta RAG vanilla — Sprint 1."""
    inicio = time.perf_counter()
    trace_id = uuid4()

    # 0. Reescritura de query usando historial (si hay)
    historial_dicts = [m.model_dump() for m in payload.history]
    rewrite_info: dict | None = None
    consulta_efectiva = payload.query
    if historial_dicts:
        rewrite_info = await reescribir_consulta(payload.query, historial_dicts, llm)
        if rewrite_info["was_rewritten"]:
            consulta_efectiva = rewrite_info["rewritten"]

    # 1. Embedding (usa consulta reescrita para mejor recall)
    try:
        vectores = await llm.embed([consulta_efectiva])
        vector_consulta = vectores[0]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"LLM provider unreachable for embedding: {exc}",
        ) from exc

    # 2. Hybrid search en pgvector con pesos adaptativos (Phase 3)
    from src.rag.query_profile import detectar as _detectar_perfil
    _perfil = _detectar_perfil(consulta_efectiva)
    logger.info(
        "Query profile: %s (w_vec=%.2f w_txt=%.2f) - %s",
        _perfil.tipo, _perfil.w_vector, _perfil.w_texto, _perfil.razon,
    )

    async with pool.connection() as conn:
        store = PgVectorStore(conn)
        fragmentos_vec = await store.hybrid_search(
            query_embedding=vector_consulta,
            query_text=consulta_efectiva,
            top_k=5,
            domain=payload.filters.domain,
            validity_status=payload.filters.validity_status or "vigente",
            w_vector=_perfil.w_vector,
            w_texto=_perfil.w_texto,
        )

    # 2.5 Graph-augmented retrieval (feature flag)
    telemetria_grafo: dict | None = None
    vias_por_fragmento: list[str]
    if payload.options.expansion_enabled and payload.options.max_hops > 0:
        fragmentos_exp, telemetria_grafo = await expandir_por_grafo(
            pool,
            chunks_iniciales=fragmentos_vec,
            query_embedding=vector_consulta,
            max_hops=payload.options.max_hops,
        )
        # Pre-fusión: traemos hasta 12 candidatos (7 + ~5 expansiones) para
        # darle más material al reranker. Si rerank=false usamos top 7 directo.
        candidatos, vias_candidatos = fusionar_y_rankear(
            fragmentos_vec, fragmentos_exp,
            top_k_final=18 if payload.options.rerank_enabled else 7,
        )
        fragmentos, vias_por_fragmento = candidatos, vias_candidatos
    else:
        # Vanilla: normaliza score a cosine para comparabilidad
        fragmentos = fragmentos_vec
        for f in fragmentos:
            f.score = round(f.vector_score, 4)
        vias_por_fragmento = ["vector"] * len(fragmentos)

    # 2.6 LLM-based reranking (feature flag, default ON)
    if payload.options.rerank_enabled and len(fragmentos) > 1:
        fragmentos, vias_por_fragmento = await rerank_con_vias(
            llm, payload.query, fragmentos, vias_por_fragmento, top_k=7
        )

    # 2.65 Filtro temático determinista — evita que chunks de Patrimonio Efectivo
    # contaminen una respuesta sobre provisiones (o viceversa).
    from src.agents.topic_router import (
        filtrar_fragmentos_por_tema,
        titulos_permitidos_para_query,
    )
    fragmentos_pre = fragmentos
    fragmentos, telemetria_router = filtrar_fragmentos_por_tema(
        fragmentos, consulta_efectiva
    )
    if len(fragmentos) != len(fragmentos_pre):
        ids_validos = {id(f) for f in fragmentos}
        vias_por_fragmento = [
            v for v, f in zip(vias_por_fragmento, fragmentos_pre) if id(f) in ids_validos
        ]

    # 2.66 Re-fetch dirigido por tema: si el filtro removió chunks Y no hay
    # ningún fragmento sobreviviente de los docs "permitidos" del tema,
    # consultamos directamente la DB filtrando por title — así garantizamos que
    # el contexto tenga al menos UN chunk de la regulación correcta.
    titulos_relevantes = titulos_permitidos_para_query(consulta_efectiva)
    if titulos_relevantes:
        # Determinar qué patrones permitidos NO están aún representados en los fragmentos.
        titles_presentes = " ".join(
            (getattr(f, "document_title", "") or "").lower() for f in fragmentos
        )
        faltantes = [p for p in titulos_relevantes if p.lower() not in titles_presentes]
        if faltantes:
            async with pool.connection() as conn:
                store_extra = PgVectorStore(conn)
                fragmentos_extra = await store_extra.hybrid_search(
                    query_embedding=vector_consulta,
                    query_text=consulta_efectiva,
                    top_k=6,
                    validity_status=payload.filters.validity_status or "vigente",
                    titles_like=faltantes,
                )
            if fragmentos_extra:
                for fx in fragmentos_extra:
                    try:
                        fx.score = float(getattr(fx, "score", 0) or 0) + 0.50
                    except Exception:  # noqa: BLE001
                        pass
                ids_existentes = {getattr(f, "chunk_id", id(f)) for f in fragmentos}
                for fx in fragmentos_extra:
                    if getattr(fx, "chunk_id", id(fx)) not in ids_existentes:
                        fragmentos.append(fx)
                        vias_por_fragmento.append("vector")
                pares = sorted(
                    zip(fragmentos, vias_por_fragmento),
                    key=lambda p: float(getattr(p[0], "score", 0) or 0),
                    reverse=True,
                )
                fragmentos = [p[0] for p in pares][:7]
                vias_por_fragmento = [p[1] for p in pares][:7]
                telemetria_router["refetch_chunks_added"] = len(fragmentos_extra)
                telemetria_router["refetch_patrones_buscados"] = faltantes

    # 2.7 Function calling — calculadora (sobre consulta efectiva para extraer datos)
    calculos = await detectar_y_calcular(consulta_efectiva, llm)
    bloque_calculos = formatear_calculos_para_prompt(calculos)

    # 3. Generación — historial + contexto + cálculos
    prompt_usuario = _construir_prompt_usuario(payload.query, fragmentos)
    bloque_historial = formatear_historial_para_prompt(historial_dicts)
    if bloque_historial:
        prompt_usuario = bloque_historial + "\n" + prompt_usuario
    if bloque_calculos:
        prompt_usuario += "\n" + bloque_calculos
    es_informe = payload.options.report_mode
    sys_prompt = SYSTEM_PROMPT_INFORME if es_informe else SYSTEM_PROMPT
    max_tokens = 3500 if es_informe else 1024
    try:
        resultado = await llm.generate(
            prompt_usuario,
            system=sys_prompt,
            temperature=0.2,
            max_tokens=max_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"LLM provider error during generation: {exc}",
        ) from exc

    # 4. Construir respuesta — incluye `via`, `section_path` y `content_snippet`
    fuentes = []
    for frag, via in zip(fragmentos, vias_por_fragmento):
        contenido = (frag.content or "").strip()
        # Snippet: primeros ~700 chars del chunk para que el usuario vea
        # exactamente qué texto del PDF se citó (transparencia + auditoría)
        snippet = contenido[:700]
        if len(contenido) > 700:
            snippet += "…"
        fuentes.append(
            Source(
                doc_id=str(frag.document_id),
                title=frag.document_title,
                url=frag.document_url,
                score=round(frag.score, 4),
                via=via,  # type: ignore[arg-type]
                section_path=(frag.metadata or {}).get("section_path"),
                content_snippet=snippet,
                issuer=getattr(frag, "document_issuer", None),
            )
        )

    confianza = _confianza_segun_puntajes(fragmentos)
    avisos: list[str] = []
    if not fragmentos:
        avisos.append("No se recuperó ningún chunk con la query.")
    if confianza == "baja":
        avisos.append("Confianza baja — recomendable validación humana.")

    latencia_ms = (time.perf_counter() - inicio) * 1000

    # Log a query_log si vino con alias (no-bloqueante)
    if payload.alias:
        try:
            from src.storage import query_log as _qlog
            await _qlog.log_query(
                pool=pool,
                alias=payload.alias.strip(),
                query_text=payload.query,
                answer_text=resultado.text,
                confidence=confianza,
                n_sources=len(fuentes),
                latency_ms=int(latencia_ms),
                tokens_in=resultado.input_tokens,
                tokens_out=resultado.output_tokens,
                options=payload.options.model_dump(),
                sources_summary=[
                    {
                        "issuer": f.issuer,
                        "title": (f.title or "")[:120],
                        "score": f.score,
                        "doc_id": f.doc_id,
                    }
                    for f in fuentes[:8]
                ],
            )
        except Exception:  # noqa: BLE001
            pass

    return QueryResponse(
        trace_id=trace_id,
        answer=resultado.text,
        sources=fuentes,
        confidence=confianza,  # type: ignore[arg-type]
        cache_hit=False,
        tokens_used={"input": resultado.input_tokens, "output": resultado.output_tokens},
        latency_ms=round(latencia_ms, 2),
        warnings=avisos,
        graph_expansion=telemetria_grafo,
        calculations=[c.model_dump() for c in calculos],
        query_rewrite=rewrite_info,
    )


# ---------------------------------------------------------------------------
# Plan agente — decide si responder directo o pedir clarificaciones
# ---------------------------------------------------------------------------

@router.post("/v1/plan", response_model=PlanResponse)
async def planear(
    payload: PlanRequest,
    llm: LLMProvider = Depends(get_llm),
) -> PlanResponse:
    """LLM-as-planner: evalúa si el query tiene contexto suficiente.

    Si NO: retorna 2-4 preguntas de clarificación para que el usuario las
    responda antes de proceder al retrieval + generación normales.

    El flujo en la UI:
      1. POST /v1/plan {query}
      2. Si action == 'ask_clarifications': mostrar formulario al usuario
      3. User responde → enriquecer query con las respuestas
      4. POST /v1/query {query enriquecido}
    """
    decision = await decidir_plan(payload.query, llm)
    return PlanResponse(
        action=decision["action"],
        reason=decision.get("reason"),
        questions=[PlanQuestion(**q) for q in decision.get("questions", [])],
    )


# ---------------------------------------------------------------------------
# /v1/query/stream — Server-Sent Events streaming
# ---------------------------------------------------------------------------

def _sse(event: str, data: dict | str) -> str:
    """Formatea un evento SSE estándar.

    Formato:
      event: <event>
      data: <json-or-text>
      \n
    """
    payload = _json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("/v1/query/stream")
async def query_stream(
    payload: QueryRequest,
    pool: AsyncConnectionPool = Depends(get_pool),
    llm: LLMProvider = Depends(get_llm),
) -> StreamingResponse:
    """Versión streaming de /v1/query.

    Emite eventos SSE en este orden:
      - status:        {"step": "embedding"|"retrieval"|"rerank"|"calc"|"generation"}
      - sources:       lista de Source completa
      - calculations:  cálculos deterministas detectados
      - graph:         telemetría de expansión (si aplica)
      - token:         {"text": "..."} por cada chunk del LLM
      - metadata:      {trace_id, confidence, latency_ms, tokens_used}
      - done:          {}

    El cliente puede ir pintando la respuesta token-por-token y al final
    aplicar el formateo de fuentes.
    """
    async def generador():
        import time
        from uuid import uuid4
        inicio = time.perf_counter()
        trace_id = uuid4()

        try:
            # 0. Reescritura por memoria conversacional (si hay historial)
            historial_dicts = [m.model_dump() for m in payload.history]
            consulta_efectiva = payload.query
            if historial_dicts:
                yield _sse("status", {"step": "rewrite"})
                rewrite_info = await reescribir_consulta(payload.query, historial_dicts, llm)
                if rewrite_info["was_rewritten"]:
                    consulta_efectiva = rewrite_info["rewritten"]
                yield _sse("rewrite", rewrite_info)

            yield _sse("status", {"step": "embedding"})
            vectores = await llm.embed([consulta_efectiva])
            vector_consulta = vectores[0]

            yield _sse("status", {"step": "retrieval"})
            from src.rag.query_profile import detectar as _detectar_perfil_s
            _perfil_s = _detectar_perfil_s(consulta_efectiva)
            logger.info(
                "Stream query profile: %s (w_vec=%.2f w_txt=%.2f) - %s",
                _perfil_s.tipo, _perfil_s.w_vector, _perfil_s.w_texto, _perfil_s.razon,
            )
            async with pool.connection() as conn:
                store = PgVectorStore(conn)
                fragmentos_vec = await store.hybrid_search(
                    query_embedding=vector_consulta,
                    query_text=consulta_efectiva,
                    top_k=5,
                    w_vector=_perfil_s.w_vector,
                    w_texto=_perfil_s.w_texto,
                    domain=payload.filters.domain,
                    validity_status=payload.filters.validity_status or "vigente",
                )

            telemetria_grafo = None
            vias_por_fragmento: list[str]
            if payload.options.expansion_enabled and payload.options.max_hops > 0:
                yield _sse("status", {"step": "graph_expansion"})
                fragmentos_exp, telemetria_grafo = await expandir_por_grafo(
                    pool,
                    chunks_iniciales=fragmentos_vec,
                    query_embedding=vector_consulta,
                    max_hops=payload.options.max_hops,
                )
                fragmentos, vias_por_fragmento = fusionar_y_rankear(
                    fragmentos_vec, fragmentos_exp,
                    top_k_final=18 if payload.options.rerank_enabled else 7,
                )
                if telemetria_grafo:
                    yield _sse("graph", telemetria_grafo)
            else:
                fragmentos = fragmentos_vec
                for f in fragmentos:
                    f.score = round(f.vector_score, 4)
                vias_por_fragmento = ["vector"] * len(fragmentos)

            if payload.options.rerank_enabled and len(fragmentos) > 1:
                yield _sse("status", {"step": "rerank"})
                fragmentos, vias_por_fragmento = await rerank_con_vias(
                    llm, consulta_efectiva, fragmentos, vias_por_fragmento, top_k=7
                )

            # Filtro temático determinista (anti-contaminación entre regulaciones)
            from src.agents.topic_router import (
                filtrar_fragmentos_por_tema,
                titulos_permitidos_para_query,
            )
            fragmentos_pre = fragmentos
            fragmentos, telemetria_router = filtrar_fragmentos_por_tema(
                fragmentos, consulta_efectiva
            )
            if len(fragmentos) != len(fragmentos_pre):
                ids_validos = {id(f) for f in fragmentos}
                vias_por_fragmento = [
                    v for v, f in zip(vias_por_fragmento, fragmentos_pre) if id(f) in ids_validos
                ]

            # Re-fetch dirigido (asegura que haya al menos un chunk de la regulación correcta)
            titulos_relevantes = titulos_permitidos_para_query(consulta_efectiva)
            if titulos_relevantes:
                ya_tiene_relevante = any(
                    any(p.lower() in (getattr(f, "document_title", "") or "").lower()
                        for p in titulos_relevantes)
                    for f in fragmentos
                )
                if not ya_tiene_relevante:
                    async with pool.connection() as conn:
                        store_extra = PgVectorStore(conn)
                        fragmentos_extra = await store_extra.hybrid_search(
                            query_embedding=vector_consulta,
                            query_text=consulta_efectiva,
                            top_k=4,
                            validity_status=payload.filters.validity_status or "vigente",
                            titles_like=titulos_relevantes,
                        )
                    if fragmentos_extra:
                        for fx in fragmentos_extra:
                            try:
                                fx.score = float(getattr(fx, "score", 0) or 0) + 0.50
                            except Exception:  # noqa: BLE001
                                pass
                        ids_existentes = {getattr(f, "chunk_id", id(f)) for f in fragmentos}
                        for fx in fragmentos_extra:
                            if getattr(fx, "chunk_id", id(fx)) not in ids_existentes:
                                fragmentos.append(fx)
                                vias_por_fragmento.append("vector")  # refetch dirigido (cuenta como vector)
                        pares = sorted(
                            zip(fragmentos, vias_por_fragmento),
                            key=lambda p: float(getattr(p[0], "score", 0) or 0),
                            reverse=True,
                        )
                        fragmentos = [p[0] for p in pares][:7]
                        vias_por_fragmento = [p[1] for p in pares][:7]
                        telemetria_router["refetch_chunks_added"] = len(fragmentos_extra)

            if telemetria_router.get("temas_detectados"):
                yield _sse("topic_filter", telemetria_router)

            # Calculator agent (sobre consulta efectiva, mejor extracción de params)
            yield _sse("status", {"step": "calc"})
            calculos = await detectar_y_calcular(consulta_efectiva, llm)
            if calculos:
                yield _sse("calculations", [c.model_dump() for c in calculos])

            # Emitir fuentes (antes del streaming de tokens)
            fuentes_data = []
            for frag, via in zip(fragmentos, vias_por_fragmento):
                contenido = (frag.content or "").strip()
                snippet = contenido[:700] + ("…" if len(contenido) > 700 else "")
                fuentes_data.append({
                    "doc_id": str(frag.document_id),
                    "title": frag.document_title,
                    "url": frag.document_url,
                    "score": round(frag.score, 4),
                    "via": via,
                    "section_path": (frag.metadata or {}).get("section_path"),
                    "content_snippet": snippet,
                    "issuer": getattr(frag, "document_issuer", None),
                })
            yield _sse("sources", fuentes_data)

            # Generación streaming — prompt enriquecido con historial + cálculos
            yield _sse("status", {"step": "generation"})
            prompt_usuario = _construir_prompt_usuario(payload.query, fragmentos)
            bloque_historial = formatear_historial_para_prompt(historial_dicts)
            if bloque_historial:
                prompt_usuario = bloque_historial + "\n" + prompt_usuario
            bloque_calculos = formatear_calculos_para_prompt(calculos)
            if bloque_calculos:
                prompt_usuario += "\n" + bloque_calculos
            es_informe = payload.options.report_mode
            sys_prompt = SYSTEM_PROMPT_INFORME if es_informe else SYSTEM_PROMPT
            max_tokens = 3500 if es_informe else 1024

            texto_completo = []
            async for chunk in llm.generate_stream(
                prompt_usuario,
                system=sys_prompt,
                temperature=0.2,
                max_tokens=max_tokens,
            ):
                texto_completo.append(chunk)
                yield _sse("token", {"text": chunk})

            # Metadata final
            respuesta_final = "".join(texto_completo)
            confianza = _confianza_segun_puntajes(fragmentos)
            latencia_ms = (time.perf_counter() - inicio) * 1000
            yield _sse("metadata", {
                "trace_id": str(trace_id),
                "confidence": confianza,
                "latency_ms": round(latencia_ms, 2),
                "answer_length": len(respuesta_final),
            })

            # Log a query_log si vino con alias (no-bloqueante)
            if payload.alias:
                try:
                    from src.storage import query_log as _qlog
                    await _qlog.log_query(
                        pool=pool,
                        alias=payload.alias.strip(),
                        query_text=payload.query,
                        answer_text=respuesta_final,
                        confidence=confianza,
                        n_sources=len(fragmentos),
                        latency_ms=int(latencia_ms),
                        options=payload.options.model_dump(),
                        sources_summary=[
                            {
                                "issuer": getattr(f, "document_issuer", None),
                                "title": (f.document_title or "")[:120],
                                "score": float(f.score),
                                "doc_id": str(f.document_id),
                            }
                            for f in fragmentos[:8]
                        ],
                    )
                except Exception:  # noqa: BLE001
                    pass

            yield _sse("done", {})
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"message": str(exc), "type": type(exc).__name__})

    return StreamingResponse(
        generador(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
