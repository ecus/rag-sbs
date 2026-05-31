"""UI Streamlit del RAG SBS — Mesa Experta Regulatoria.

Run dentro del container:
    streamlit run src/ui/streamlit_app.py --server.port=8501 --server.address=0.0.0.0
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import altair as alt
import pandas as pd
import streamlit as st

from src.ui.api_client import APIClient
from src.ui.styles import (
    badge_confianza,
    badge_via,
    calcular_dependencias_ui,
    inyectar_estilos,
    panel_sin_evidencia,
    render_calculo_card,
    render_footer,
    render_fuente_card,
    render_header,
    resaltar_referencias_fuente,
)


def _es_respuesta_sin_evidencia(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return any(k in t for k in (
        "no tengo evidencia",
        "no encuentro evidencia",
        "no hay evidencia",
        "sin información suficiente",
        "no dispongo de información",
        "no se encontró información",
        "no encontré información",
    ))

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="RAG SBS · Mesa Experta",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inyectar_estilos()
render_header()


@st.cache_resource
def obtener_cliente() -> APIClient:
    return APIClient()


api = obtener_cliente()


# ---------------------------------------------------------------------------
# Helper: procesar query con streaming (SSE)
# ---------------------------------------------------------------------------

NOMBRE_PASO = {
    "rewrite": "🧠 Reescribiendo consulta con memoria",
    "embedding": "🔎 Vectorizando consulta",
    "retrieval": "📚 Buscando en pgvector",
    "graph_expansion": "🧠 Expandiendo con knowledge graph",
    "rerank": "⚖️ Reordenando con LLM-as-reranker",
    "calc": "🧮 Detectando cálculos deterministas",
    "generation": "✍️ Generando respuesta",
}


def _historial_para_backend(historial_streamlit: list[dict], max_turnos: int = 3) -> list[dict]:
    """Convierte el historial de Streamlit a {role, content} para el API.

    Solo toma los últimos N turnos completos (user+assistant) para no inflar.
    """
    if not historial_streamlit:
        return []
    salida = []
    for m in historial_streamlit[-(max_turnos * 2):]:
        rol = "user" if m.get("rol") == "user" else "assistant"
        contenido = m.get("texto", "") or ""
        if contenido.strip():
            salida.append({"role": rol, "content": contenido})
    return salida


def _procesar_streaming(
    api: APIClient,
    pregunta: str,
    usar_grafo: bool,
    max_hops: int,
    modo_informe: bool,
    es_input_directo: bool,
    state,
    historial: list[dict] | None = None,
) -> None:
    """Renderiza la respuesta con streaming en el chat_message del asistente."""
    fuentes_recibidas: list[dict] = []
    calculos_recibidos: list[dict] = []
    graph_info: dict | None = None
    metadata_final: dict | None = None
    rewrite_info: dict | None = None
    texto_acumulado: list[str] = []
    error: str | None = None

    with st.chat_message("assistant"):
        # Estado de progreso colapsable
        status = st.status("Iniciando…", expanded=True)
        placeholder_texto = st.empty()

        try:
            for evento, data in api.query_stream(
                pregunta,
                expansion=usar_grafo,
                max_hops=max_hops if usar_grafo else 0,
                report_mode=modo_informe,
                history=historial,
            ):
                if evento == "status":
                    paso = data.get("step", "")
                    status.update(label=NOMBRE_PASO.get(paso, paso))
                elif evento == "sources":
                    fuentes_recibidas = data
                    status.write(f"📚 {len(data)} fuentes recuperadas")
                elif evento == "calculations":
                    calculos_recibidos = data
                    status.write(f"🧮 {len(data)} cálculo(s) ejecutado(s)")
                elif evento == "graph":
                    graph_info = data
                    if data.get("added_chunks"):
                        status.write(
                            f"🧠 +{data['added_chunks']} chunks vía grafo "
                            f"({data.get('visited_nodes', 0)} nodos visitados)"
                        )
                elif evento == "rewrite":
                    rewrite_info = data
                    if data.get("was_rewritten"):
                        status.write(
                            f"🧠 Consulta reescrita por memoria:\n"
                            f"  `{data.get('rewritten', '')}`"
                        )
                    else:
                        status.write("🧠 Consulta ya autónoma — sin reescritura")
                elif evento == "token":
                    texto_acumulado.append(data.get("text", ""))
                    placeholder_texto.markdown("".join(texto_acumulado) + " ▌")
                elif evento == "metadata":
                    metadata_final = data
                elif evento == "error":
                    error = data.get("message", str(data))
                    break
                elif evento == "done":
                    break
        except Exception as exc:  # noqa: BLE001
            error = str(exc)

        if error:
            status.update(label="❌ Error", state="error", expanded=True)
            placeholder_texto.error(f"Falló el streaming: {error}")
            return

        # Texto final con resaltado de [Fuente N]
        respuesta_final = "".join(texto_acumulado)
        sin_evidencia = _es_respuesta_sin_evidencia(respuesta_final)

        if sin_evidencia:
            # Panel prominente en lugar del texto plano + ocultar contradicciones
            placeholder_texto.markdown(
                panel_sin_evidencia(n_fuentes=len(fuentes_recibidas or [])),
                unsafe_allow_html=True
            )
        else:
            placeholder_texto.markdown(
                resaltar_referencias_fuente(respuesta_final),
                unsafe_allow_html=True,
            )
        status.update(label="✓ Listo", state="complete", expanded=False)

        # Metricas top
        if metadata_final:
            cols = st.columns([1, 1, 1, 2])
            cols[0].markdown(
                f"**Confianza:** {badge_confianza(metadata_final['confidence'], respuesta_final)}",
                unsafe_allow_html=True,
            )
            cols[1].caption(f"⏱ {metadata_final['latency_ms']/1000:.1f}s")
            cols[2].caption(f"✨ streaming")
            if graph_info:
                cols[3].caption(
                    f"🧠 +{graph_info.get('added_chunks', 0)} chunks vía grafo"
                )

        # Cálculos
        if calculos_recibidos:
            deps_map = calcular_dependencias_ui(calculos_recibidos)
            st.markdown(f"##### 🧮 Cálculos verificados ({len(calculos_recibidos)})")
            html = "".join(
                render_calculo_card(i, c, deps_map.get(i))
                for i, c in enumerate(calculos_recibidos, 1)
            )
            st.markdown(html, unsafe_allow_html=True)

        # Fuentes
        if fuentes_recibidas:
            st.markdown(f"##### 📚 Fuentes citadas ({len(fuentes_recibidas)})")
            html = "".join(
                render_fuente_card(i, f) for i, f in enumerate(fuentes_recibidas, 1)
            )
            st.markdown(html, unsafe_allow_html=True)

        # Guardar en historial
        if es_input_directo:
            state.historial_chat.append({
                "rol": "assistant",
                "texto": respuesta_final,
                "metadatos": {
                    "confidence": metadata_final.get("confidence") if metadata_final else None,
                    "sources": fuentes_recibidas,
                    "calculations": calculos_recibidos,
                    "graph_expansion": graph_info,
                },
            })


# ---------------------------------------------------------------------------
# Sidebar — estado del sistema
# ---------------------------------------------------------------------------

# =========================================================================
# Sidebar amigable por defecto · modo técnico bajo toggle
# =========================================================================

# Toggle global: modo técnico (admin) ↔ modo usuario (default)
if "modo_tecnico" not in st.session_state:
    st.session_state.modo_tecnico = False

with st.sidebar:
    # Logo + claim siempre
    st.markdown(
        '<div style="text-align:center;padding:8px 0 16px;">'
        '<div style="font-size:32px;line-height:1;">🏛️</div>'
        '<div style="font-weight:700;font-size:18px;color:#003d7a;'
        'margin-top:6px;">Mesa Experta</div>'
        '<div style="font-size:11px;color:#64748b;letter-spacing:0.5px;'
        'text-transform:uppercase;">Regulación Bancaria · Perú</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.modo_tecnico:
        # ----- MODO USUARIO: simple, amigable -----
        st.markdown("### 💡 ¿Cómo preguntar?")
        st.markdown(
            """
            <div style="background:#f1f5f9;padding:12px;border-radius:8px;
            font-size:13px;line-height:1.5;color:#334155;">
            <p style="margin:0 0 8px 0;"><b>✅ Buenas preguntas:</b></p>
            <ul style="margin:0 0 0 16px;padding:0;">
              <li>¿Qué dice la Resolución SBS 11356-2008 sobre clasificación del deudor?</li>
              <li>¿Cuáles son las provisiones procíclicas vigentes?</li>
              <li>¿Qué cuentas afecta una titulización según el Manual de Contabilidad?</li>
            </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("La mesa busca solo en normativa oficial publicada (SBS, BCRP, Congreso, MEF, SMV).")

        st.markdown("### 📚 Cobertura")
        try:
            by_issuer = api.stats_by_issuer()
            items = by_issuer.get("por_issuer", [])
            total_docs = sum(it.get("docs", 0) for it in items)
            st.metric("Documentos en mesa", f"{total_docs:,}")
            instituciones = ", ".join(it["issuer"] for it in items if it["issuer"] != "(s/d)")
            st.caption(f"Instituciones: {instituciones}")
        except Exception:  # noqa: BLE001
            pass

        st.markdown("---")
        if st.button("🔧 Modo técnico", use_container_width=True,
                     help="Ver detalles del sistema, ingesta, comparación A/B"):
            st.session_state.modo_tecnico = True
            st.rerun()
        st.caption(
            '<div style="font-size:10px;color:#94a3b8;text-align:center;'
            'margin-top:12px;">v0.3 · Portafolio personal</div>',
            unsafe_allow_html=True,
        )
    else:
        # ----- MODO TÉCNICO: dashboard admin -----
        if st.button("← Volver a modo usuario", use_container_width=True):
            st.session_state.modo_tecnico = False
            st.rerun()

        st.markdown("### 🔍 Estado del sistema")
        salud = api.health()
        if salud.get("status") == "healthy":
            st.success("Operativo")
        elif salud.get("status") == "degraded":
            st.warning("Degradado")
        else:
            st.error(f"No disponible: {salud.get('error', salud.get('status'))}")

        if salud.get("checks"):
            for componente, estado in salud["checks"].items():
                simbolo = "✓" if estado == "ok" else "✗"
                st.caption(f"{simbolo} **{componente}**: {estado}")

        st.markdown("### 📊 Corpus")
        try:
            stats = api.graph_stats()
            col1, col2 = st.columns(2)
            col1.metric("Documentos", stats["nodos_por_tipo"].get("document", 0))
            col2.metric("Resoluciones", stats["nodos_por_tipo"].get("resolution", 0))
            col1.metric("Aristas (citas)", stats["aristas_total"])
            col2.metric("Tópicos", stats["nodos_por_tipo"].get("topic", 0))
        except Exception:  # noqa: BLE001
            st.info("Esperando datos del grafo…")

        try:
            by_issuer = api.stats_by_issuer()
            items = by_issuer.get("por_issuer", [])
            if items:
                st.markdown("### 🏢 Por institución")
                colores_inst = {
                    "SBS": "#003d7a", "BCRP": "#b91c1c", "Congreso": "#7c3aed",
                    "MEF": "#15803d", "SMV": "#0891b2", "INDECOPI": "#ca8a04",
                    "SUNAT": "#be185d", "BIS": "#0f766e", "BID": "#9333ea",
                    "(s/d)": "#64748b",
                }
                for it in items:
                    issuer = it.get("issuer", "?")
                    docs = it.get("docs", 0)
                    chunks = it.get("chunks", 0)
                    color = colores_inst.get(issuer, "#475569")
                    st.markdown(
                        f'<div style="background:{color}11;border-left:3px solid {color};'
                        f'padding:6px 10px;border-radius:4px;margin-bottom:4px;font-size:12px;">'
                        f'<strong style="color:{color};">{issuer}</strong>'
                        f'<span style="float:right;color:#64748b;">{docs} docs · {chunks} chunks</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
        except Exception:  # noqa: BLE001
            pass

        st.markdown("### ⚡ Acciones")
        if st.button("Disparar scan", use_container_width=True):
            with st.spinner("Disparando scan..."):
                r = api.trigger_scan(force=False)
                st.toast(f"Scan disparado: {r.get('run_id', '?')[:8]}…", icon="⚡")

        st.markdown("---")
        st.caption(
            "Stack: FastAPI · pgvector · Gemini 2.5 Flash · NetworkX"
        )


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

if st.session_state.modo_tecnico:
    tab_chat, tab_stats, tab_grafo, tab_ab, tab_runs = st.tabs(
        ["💬 Consultar", "🧩 Tópicos", "🧠 Mapa regulatorio",
         "🔬 A/B (técnico)", "⚙️ Administración"]
    )
else:
    tab_chat, tab_stats, tab_grafo, tab_ab, tab_runs = st.tabs(
        ["💬 Consultar", "🧩 Tópicos", "🧠 Mapa regulatorio",
         "  ", "  "]  # tabs casi invisibles cuando modo usuario
    )


# ===========================================================================
# Tab 1 — Chat / Consulta
# ===========================================================================

with tab_chat:
    st.markdown("### 💬 Consulte a la mesa experta")
    st.caption(
        "Respuestas basadas **únicamente en normativa oficial publicada** "
        "(SBS, BCRP, Congreso, MEF, SMV, SUNAT, INDECOPI). Si no hay evidencia, lo decimos."
    )

    if "historial_chat" not in st.session_state:
        st.session_state.historial_chat = []

    # Opciones del pipeline (6 toggles)
    col_a, col_b, col_c, col_d, col_e, col_f, col_g = st.columns([2, 1, 1, 1, 1, 1, 1])
    with col_b:
        usar_grafo = st.toggle("Graph-aug", value=False, key="chat_graph",
                                help="Usa el knowledge graph para enriquecer el contexto")
    with col_c:
        max_hops = st.selectbox("Saltos", [1, 2], index=0, key="chat_hops",
                                disabled=not usar_grafo)
    with col_d:
        modo_informe = st.toggle("📋 Informe", value=False, key="chat_informe",
                                  help="Respuesta estructurada en 10 dimensiones")
    with col_e:
        usar_planner = st.toggle("🤖 Agente", value=False, key="chat_agente",
                                  help="Pide clarificaciones antes de buscar si la consulta "
                                       "es ambigua.")
    with col_f:
        usar_streaming = st.toggle("⚡ Stream", value=True, key="chat_stream",
                                    help="Token-por-token en vivo.")
    with col_g:
        usar_memoria = st.toggle("🧠 Memoria", value=True, key="chat_memoria",
                                  help="Pasa los últimos turnos al backend para resolver "
                                       "referencias anafóricas y mantener el hilo "
                                       "de la conversación.")

    # Indicador de memoria activa + botón limpiar
    n_turnos = len([m for m in st.session_state.get("historial_chat", [])
                     if m.get("rol") == "user"])
    if n_turnos > 0:
        col_info, col_clear = st.columns([5, 1])
        col_info.caption(
            f"🧠 Conversación con **{n_turnos} turno(s)** previos"
            + (" — memoria activa" if usar_memoria else " — memoria DESACTIVADA")
        )
        if col_clear.button("🗑 Limpiar", key="clear_chat", use_container_width=True):
            st.session_state.historial_chat = []
            st.session_state.plan_pendiente = None
            st.session_state.consulta_pendiente = None
            st.rerun()

    # Estado de la conversación con planner
    if "plan_pendiente" not in st.session_state:
        st.session_state.plan_pendiente = None    # {query, questions} o None
    if "consulta_pendiente" not in st.session_state:
        st.session_state.consulta_pendiente = None  # query enriquecido a procesar

    # Render history
    for mensaje in st.session_state.historial_chat:
        with st.chat_message(mensaje["rol"]):
            if mensaje["rol"] == "assistant":
                st.markdown(
                    resaltar_referencias_fuente(mensaje["texto"]),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(mensaje["texto"])
            md = mensaje.get("metadatos")
            if md and md.get("sources"):
                st.markdown(f"##### 📚 Fuentes ({len(md['sources'])})")
                fuentes_html = "".join(
                    render_fuente_card(i, f)
                    for i, f in enumerate(md["sources"], 1)
                )
                st.markdown(fuentes_html, unsafe_allow_html=True)

    # Si el agente está esperando respuestas a clarificaciones, las pintamos
    if st.session_state.plan_pendiente:
        pp = st.session_state.plan_pendiente
        with st.chat_message("assistant"):
            st.markdown(
                "🤖 **Necesito un poco más de contexto antes de buscar la respuesta.**"
                + (f"\n\n_{pp['reason']}_" if pp.get("reason") else "")
            )
            with st.form(key="clarif_form", clear_on_submit=False):
                respuestas: dict[str, object] = {}
                for q in pp["questions"]:
                    label = q["label"]
                    rationale = q.get("rationale")
                    full_label = label + (f"  \n_{rationale}_" if rationale else "")
                    if q["type"] == "select" and q.get("options"):
                        respuestas[label] = st.selectbox(
                            full_label, q["options"], key=f"clar_{q['id']}"
                        )
                    elif q["type"] == "multiselect" and q.get("options"):
                        respuestas[label] = st.multiselect(
                            full_label, q["options"], key=f"clar_{q['id']}"
                        )
                    else:
                        respuestas[label] = st.text_input(
                            full_label, key=f"clar_{q['id']}"
                        )
                col_s, col_x = st.columns([1, 1])
                enviar = col_s.form_submit_button("Continuar con esa info", type="primary",
                                                    use_container_width=True)
                cancelar = col_x.form_submit_button("Saltar clarificaciones",
                                                      use_container_width=True)
            if enviar:
                from src.agents.planner import enriquecer_consulta_con_respuestas
                consulta_enriquecida = enriquecer_consulta_con_respuestas(
                    pp["query"], respuestas
                )
                st.session_state.consulta_pendiente = consulta_enriquecida
                st.session_state.plan_pendiente = None
                st.rerun()
            elif cancelar:
                st.session_state.consulta_pendiente = pp["query"]
                st.session_state.plan_pendiente = None
                st.rerun()

    # Input
    consulta_a_procesar = st.session_state.consulta_pendiente
    if consulta_a_procesar:
        st.session_state.consulta_pendiente = None
        pregunta = consulta_a_procesar
        consulta_input = None
    else:
        pregunta = None
        consulta_input = st.chat_input("Escribe tu consulta regulatoria…")
        if consulta_input:
            pregunta = consulta_input

    if pregunta:
        # Si NO viene de un planner previo, registrar como turno user
        if consulta_input:
            st.session_state.historial_chat.append(
                {"rol": "user", "texto": consulta_input}
            )
            with st.chat_message("user"):
                st.markdown(consulta_input)

            # Rama 1: agente planner activo → consulta plan primero
            if usar_planner:
                with st.chat_message("assistant"):
                    with st.spinner("🤖 Analizando tu consulta…"):
                        try:
                            plan = api.plan(consulta_input)
                        except Exception as exc:  # noqa: BLE001
                            st.warning(f"Planner falló ({exc}); continuamos directo.")
                            plan = {"action": "answer_directly"}
                if plan["action"] == "ask_clarifications" and plan.get("questions"):
                    st.session_state.plan_pendiente = {
                        "query": consulta_input,
                        "questions": plan["questions"],
                        "reason": plan.get("reason"),
                    }
                    st.rerun()

        # Historial para el backend (excluyendo el turno actual recién agregado)
        historial_backend = _historial_para_backend(
            st.session_state.historial_chat[:-1] if consulta_input
            else st.session_state.historial_chat
        ) if usar_memoria else []

        # Procesamiento — streaming o bloqueante según toggle
        if usar_streaming:
            _procesar_streaming(
                api, pregunta, usar_grafo, max_hops, modo_informe,
                consulta_input, st.session_state,
                historial=historial_backend,
            )
            st.stop()   # cortar ejecución; streaming ya rendereó todo

        # Modo bloqueante (path original)
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("_Consultando el corpus…_")
            try:
                respuesta = api.query(
                    pregunta,
                    expansion=usar_grafo,
                    max_hops=max_hops if usar_grafo else 0,
                    report_mode=modo_informe,
                    history=historial_backend,
                )
                # Respuesta con [Fuente N] resaltados en amarillo
                sin_ev = _es_respuesta_sin_evidencia(respuesta["answer"])
                if sin_ev:
                    placeholder.markdown(
                        panel_sin_evidencia(
                            n_fuentes=len(respuesta.get("sources") or [])
                        ),
                        unsafe_allow_html=True,
                    )
                else:
                    placeholder.markdown(
                        resaltar_referencias_fuente(respuesta["answer"]),
                        unsafe_allow_html=True,
                    )

                # Confianza + métricas
                cols = st.columns([1, 1, 1, 2])
                cols[0].markdown(
                    f"**Confianza:** {badge_confianza(respuesta['confidence'], respuesta['answer'])}",
                    unsafe_allow_html=True,
                )
                cols[1].caption(f"⏱ {respuesta['latency_ms']/1000:.1f}s")
                cols[2].caption(f"🪙 {sum(respuesta['tokens_used'].values())} tokens")
                if respuesta.get("graph_expansion"):
                    ge = respuesta["graph_expansion"]
                    cols[3].caption(
                        f"🧠 +{ge.get('added_chunks', 0)} chunks vía grafo "
                        f"({ge.get('visited_nodes', 0)} nodos visitados)"
                    )

                # Cálculos deterministas (si los hubo) — con detección de
                # dependencias entre cálculos para mostrar la cadena
                calculos = respuesta.get("calculations") or []
                if calculos:
                    deps_map = calcular_dependencias_ui(calculos)
                    st.markdown(f"##### 🧮 Cálculos verificados ({len(calculos)})")
                    calculos_html = "".join(
                        render_calculo_card(i, c, deps_map.get(i))
                        for i, c in enumerate(calculos, 1)
                    )
                    st.markdown(calculos_html, unsafe_allow_html=True)

                # Fuentes VISIBLES por defecto (no en expander) — cards prominentes
                st.markdown(
                    f"##### 📚 Fuentes citadas ({len(respuesta['sources'])})",
                )
                fuentes_html = "".join(
                    render_fuente_card(i, f)
                    for i, f in enumerate(respuesta["sources"], 1)
                )
                st.markdown(fuentes_html, unsafe_allow_html=True)

                # Avisos
                if respuesta.get("warnings"):
                    for aviso in respuesta["warnings"]:
                        st.warning(aviso)

                st.session_state.historial_chat.append({
                    "rol": "assistant",
                    "texto": respuesta["answer"],
                    "metadatos": {
                        "trace_id": respuesta["trace_id"],
                        "confidence": respuesta["confidence"],
                        "graph_expansion": respuesta.get("graph_expansion"),
                        "sources": respuesta["sources"],
                    },
                })
            except Exception as exc:  # noqa: BLE001
                placeholder.error(f"Error: {exc}")


# ===========================================================================
# Tab 2 — Comparación A/B (vanilla vs graph-aug)
# ===========================================================================

with tab_ab:
    st.markdown("### Comparación A/B — Vanilla vs Graph-Augmented")
    st.caption(
        "Misma consulta corrida en paralelo con y sin expansión por el grafo. "
        "Compara fuentes, scores y respuestas lado a lado."
    )

    pregunta_ab = st.text_input(
        "Consulta a comparar",
        placeholder="Ej. responsabilidades del directorio en gestión de riesgos y ciberseguridad",
        key="ab_query",
    )

    col_btn, col_hops = st.columns([3, 1])
    with col_hops:
        hops_ab = st.selectbox("Max hops (B)", [1, 2], index=1, key="ab_hops")

    if col_btn.button("Ejecutar comparación", type="primary",
                       disabled=not pregunta_ab, use_container_width=True):
        col_a, col_b = st.columns(2, gap="medium")

        with col_a:
            st.markdown("#### A — Vanilla")
            st.caption("Solo retriever vectorial (top-k híbrido)")
            with st.spinner("Consultando vanilla…"):
                t0 = time.time()
                rA = api.query(pregunta_ab, expansion=False)
                dt_a = time.time() - t0

        with col_b:
            st.markdown("#### B — Graph-Augmented")
            st.caption(f"Vector + expansión por grafo ({hops_ab} salto(s))")
            with st.spinner("Consultando con grafo…"):
                t0 = time.time()
                rB = api.query(pregunta_ab, expansion=True, max_hops=hops_ab)
                dt_b = time.time() - t0

        # Métricas top
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Confianza A", rA["confidence"])
        m2.metric("Confianza B", rB["confidence"])
        m3.metric("Latencia A", f"{dt_a:.1f}s")
        m4.metric(
            "Δ docs nuevos (B)",
            rB.get("graph_expansion", {}).get("added_docs", 0),
        )

        # Lado a lado: respuestas + fuentes
        col_a2, col_b2 = st.columns(2, gap="medium")
        with col_a2:
            st.markdown("**Respuesta A (Vanilla)**")
            st.markdown(resaltar_referencias_fuente(rA["answer"]),
                        unsafe_allow_html=True)
            st.markdown(f"##### 📚 Fuentes A ({len(rA['sources'])})")
            st.markdown(
                "".join(render_fuente_card(i, f) for i, f in enumerate(rA["sources"], 1)),
                unsafe_allow_html=True,
            )

        with col_b2:
            st.markdown("**Respuesta B (Graph-Aug)**")
            st.markdown(resaltar_referencias_fuente(rB["answer"]),
                        unsafe_allow_html=True)
            st.markdown(f"##### 📚 Fuentes B ({len(rB['sources'])})")
            st.markdown(
                "".join(render_fuente_card(i, f) for i, f in enumerate(rB["sources"], 1)),
                unsafe_allow_html=True,
            )

        # Diff de fuentes
        ids_a = {f["doc_id"] for f in rA["sources"]}
        ids_b = {f["doc_id"] for f in rB["sources"]}
        solo_b = ids_b - ids_a
        if solo_b:
            st.success(
                f"✨ **B descubrió {len(solo_b)} documento(s) que A no incluyó** "
                f"— habilita el valor del grafo en queries cross-dominio."
            )


# ===========================================================================
# Tab 3 — Grafo navegable (iframe)
# ===========================================================================

with tab_grafo:
    st.markdown("### 🧠 Mapa interactivo de la regulación")
    st.caption(
        "Cada círculo es un documento o entidad legal citada. Las líneas son "
        "referencias entre normas. Click en cualquier nodo para explorarlo."
    )
    # Detectar el host con el que el navegador llegó a Streamlit
    try:
        request_host = st.context.headers.get("Host") or st.context.headers.get("host")
    except Exception:  # noqa: BLE001
        request_host = None
    grafo_url = api.graph_url(request_host=request_host)
    st.components.v1.iframe(grafo_url, height=900, scrolling=True)
    st.caption(
        f"También disponible directamente en [{grafo_url}]({grafo_url})"
    )


# ===========================================================================
# Tab 4 — Tópicos auto-descubiertos
# ===========================================================================

with tab_stats:
    st.markdown("### 🧭 Áreas temáticas de la regulación")
    st.caption(
        "Cada tarjeta agrupa partes del corpus regulatorio que tratan sobre el "
        "mismo tema. Útil para explorar qué cubre la mesa por área (ej. riesgo "
        "crediticio, LAFT, gobierno corporativo) antes de consultar."
    )

    # ---- Cards por tópico (vista principal) ----
    try:
        detalle = api.graph_topics_details(
            sample_chunks_per_topic=2, max_docs_per_topic=6
        )
        topicos_detallados = detalle.get("topicos", [])
        if not topicos_detallados:
            st.info(
                "🔄 Las áreas temáticas se están reconstruyendo. Volvé en unos minutos."
            )
        else:
            # Resumen
            total_chunks_topificados = sum(t.get("miembros", 0) for t in topicos_detallados)
            cols_s = st.columns(3)
            with cols_s[0]:
                st.metric("Áreas temáticas", len(topicos_detallados))
            with cols_s[1]:
                st.metric("Fragmentos analizados", f"{total_chunks_topificados:,}")
            with cols_s[2]:
                docs_unicos_total = sum(t.get("documentos_unicos", 0) for t in topicos_detallados)
                st.metric("Σ documentos por tópico", docs_unicos_total)

            st.markdown("---")

            # Render cards en grid de 2 columnas
            paleta = [
                "#003d7a", "#b91c1c", "#15803d", "#7c3aed",
                "#ca8a04", "#0891b2", "#be185d", "#1e40af",
                "#65a30d", "#9333ea",
            ]
            for i in range(0, len(topicos_detallados), 2):
                col_l, col_r = st.columns(2)
                for j, col in enumerate((col_l, col_r)):
                    idx = i + j
                    if idx >= len(topicos_detallados):
                        continue
                    t = topicos_detallados[idx]
                    color = paleta[t.get("indice", idx) % len(paleta)]
                    label = t.get("label", "Sin nombre")
                    miembros = t.get("miembros", 0)
                    docs_count = t.get("documentos_unicos", 0)

                    with col:
                        # Badges institucionales en el header (Mejora #1)
                        colores_inst = {
                            "SBS": "#003d7a", "BCRP": "#b91c1c",
                            "Congreso": "#7c3aed", "MEF": "#15803d",
                            "SMV": "#0891b2", "INDECOPI": "#ca8a04",
                            "SUNAT": "#be185d", "(s/d)": "#94a3b8",
                        }
                        por_iss = t.get("por_issuer", []) or []
                        badges_html = ""
                        for it_iss in por_iss[:5]:
                            iss_name = it_iss.get("issuer", "?")
                            iss_docs = it_iss.get("docs", 0)
                            if iss_name in ("(s/d)", "", None):
                                continue
                            iss_color = colores_inst.get(iss_name, "#475569")
                            badges_html += (
                                f'<span style="background:rgba(255,255,255,0.25);'
                                f'border:1px solid rgba(255,255,255,0.4);'
                                f'color:#fff;padding:2px 8px;border-radius:10px;'
                                f'font-size:10px;font-weight:600;margin-right:4px;'
                                f'letter-spacing:0.3px;">'
                                f'{iss_name} · {iss_docs}</span>'
                            )

                        # Card header con color de tópico
                        st.markdown(
                            f"""
                            <div style="
                                background: linear-gradient(135deg, {color}dd, {color}99);
                                color: white;
                                padding: 14px 18px;
                                border-radius: 8px 8px 0 0;
                                margin-top: 8px;
                            ">
                                <div style="font-size: 11px; opacity: 0.85;">
                                    TÓPICO #{t.get('indice', '?')}
                                </div>
                                <div style="font-size: 18px; font-weight: 600; margin-top: 2px;">
                                    {label}
                                </div>
                                <div style="font-size: 12px; margin-top: 6px; opacity: 0.92;">
                                    📊 {miembros} chunks · 📚 {docs_count} documentos
                                </div>
                                <div style="margin-top: 8px;">{badges_html}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        # Body de la card
                        body_html_parts = [
                            f'<div style="border: 1px solid {color}33; '
                            f'border-top: none; padding: 14px 18px; '
                            f'border-radius: 0 0 8px 8px; background: white;">'
                        ]

                        # Top docs
                        docs = t.get("docs_top", [])
                        if docs:
                            body_html_parts.append(
                                '<div style="font-size: 12px; font-weight: 600; '
                                'color: #475569; margin-bottom: 6px;">📚 Documentos:</div>'
                            )
                            body_html_parts.append('<ul style="margin: 0 0 12px 16px; padding: 0; font-size: 13px;">')
                            for d in docs[:5]:
                                title = (d.get("title") or "")[:75]
                                ch_t = d.get("chunks_del_topico", 0)
                                body_html_parts.append(
                                    f'<li style="margin: 2px 0;">{title} '
                                    f'<span style="color:#94a3b8;">({ch_t} chunks)</span></li>'
                                )
                            body_html_parts.append('</ul>')

                        # Sample chunks
                        samples = t.get("samples", [])
                        if samples:
                            body_html_parts.append(
                                '<div style="font-size: 12px; font-weight: 600; '
                                'color: #475569; margin-bottom: 6px;">💡 Fragmento representativo:</div>'
                            )
                            s = samples[0]
                            body_html_parts.append(
                                f'<div style="background: #f8fafc; padding: 10px 12px; '
                                f'border-left: 3px solid {color}; border-radius: 4px; '
                                f'font-size: 12px; color: #334155; line-height: 1.5;">'
                                f'<em>"{s.get("snippet","")}"</em><br>'
                                f'<span style="font-size: 10px; color: #94a3b8;">'
                                f'— {s.get("doc_title","")}</span></div>'
                            )

                        body_html_parts.append('</div>')
                        st.markdown("".join(body_html_parts), unsafe_allow_html=True)

            st.markdown("---")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"No se pudo cargar dashboard de tópicos: {exc}")

    # ---- Sección secundaria: entidades más citadas (la que ya teníamos) ----
    with st.expander("📈 Top entidades más citadas (vista por nodos)", expanded=False):
        st.caption(
            "Resoluciones, leyes y circulares ordenadas por número de citaciones recibidas "
            "desde el corpus indexado."
        )
        try:
            topicos = api.graph_topics(limit=20)
            if topicos:
                df = pd.DataFrame(topicos)
                chart = (
                    alt.Chart(df)
                    .mark_bar(color="#003d7a")
                    .encode(
                        x=alt.X("citaciones:Q", title="Citaciones recibidas"),
                        y=alt.Y("label:N", sort="-x", title=""),
                        tooltip=["label", "kind", "citaciones"],
                    )
                    .properties(height=520)
                )
                st.altair_chart(chart, use_container_width=True)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Aún no hay entidades citadas.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"No se pudo cargar tópicos clásicos: {exc}")


# ===========================================================================
# Tab 5 — Operación (sources + runs + events)
# ===========================================================================

with tab_runs:
    # ----------------------------------------------------------------------
    # Sección "Tarea de fondo" — ingesta automática con caps
    # ----------------------------------------------------------------------
    st.markdown("### 🤖 Tarea de ingesta en background")
    st.caption(
        "Worker autónomo que descubre PDFs en portales oficiales (SBS, BCRP) "
        "y los ingesta respetando topes de costo y plazo. Cron cada 10 min."
    )
    try:
        bg = api._get("/v1/background/status")
        bg_cfg = bg.get("config", {})
        bg_est = bg.get("estado", {})
        today = bg_est.get("today", {})
        total = bg_est.get("total", {})
        queue = bg_est.get("queue", {})

        cap_cost_total = float(bg_cfg.get("max_cost_total", 9.5) or 9.5)
        cap_cost_daily = float(bg_cfg.get("max_cost_daily", 1.5) or 1.5)
        cap_docs_total = int(bg_cfg.get("max_docs_total", 2000) or 2000)
        enabled = bool(bg_cfg.get("enabled", True))
        plazo = bg_cfg.get("schedule_until", "—")

        b1, b2, b3, b4 = st.columns(4)
        with b1:
            st.metric(
                "Estado",
                "🟢 Activo" if enabled else "⏸️ Pausado",
                help=f"Plazo: {plazo}",
            )
        with b2:
            cost_total = float(total.get("cost", 0))
            st.metric(
                "Costo total",
                f"${cost_total:.4f}",
                delta=f"de ${cap_cost_total:.2f}",
            )
            st.progress(min(1.0, cost_total / cap_cost_total))
        with b3:
            cost_today = float(today.get("cost", 0))
            st.metric(
                "Costo hoy",
                f"${cost_today:.4f}",
                delta=f"de ${cap_cost_daily:.2f}",
            )
            st.progress(min(1.0, cost_today / cap_cost_daily))
        with b4:
            docs_total = int(total.get("docs", 0))
            st.metric(
                "Docs procesados",
                docs_total,
                delta=f"de {cap_docs_total}",
            )
            st.progress(min(1.0, docs_total / max(1, cap_docs_total)))

        q1, q2, q3 = st.columns(3)
        with q1:
            st.metric("Cola pending", queue.get("pending", 0))
        with q2:
            st.metric("Completados", queue.get("completed", 0))
        with q3:
            st.metric("Fallidos", queue.get("failed", 0))

        ba, bb, bc, bd = st.columns(4)
        with ba:
            if st.button(
                "⏸️ Pausar" if enabled else "▶️ Activar",
                use_container_width=True,
            ):
                try:
                    api._post("/v1/background/pause" if enabled else "/v1/background/start")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"{exc}")
        with bb:
            if st.button("🔍 Descubrir URLs", use_container_width=True,
                         help="Corre scrapers SBS+BCRP y encola hallazgos"):
                with st.spinner("Descubriendo... (puede tardar ~1min)"):
                    try:
                        res = api._post("/v1/background/scrape", json={
                            "sbs": True, "bcrp": True,
                            "max_urls_sbs": 400, "max_urls_bcrp": 100,
                        })
                        st.success(f"Encoladas: {res.get('resumen')}")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"{exc}")
        with bc:
            if st.button("⚡ Tick ahora", use_container_width=True,
                         help="Ejecuta una iteración inmediata del worker"):
                with st.spinner("Procesando tick..."):
                    try:
                        res = api._post("/v1/background/tick")
                        st.success(f"action={res.get('action')} reason={res.get('reason', '—')}")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"{exc}")
        with bd:
            if st.button("🔄 Refrescar", use_container_width=True):
                st.rerun()
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Worker no disponible: {exc}")

    st.markdown("---")

    # ----------------------------------------------------------------------
    # Sección "Catálogo curado" — popular fuentes con un click
    # ----------------------------------------------------------------------
    st.markdown("### 📦 Catálogo curado de fuentes")
    st.caption(
        "Lista verificada de PDFs oficiales de SBS, BCRP, leyes y otras "
        "reguladoras. Al **Popular** se registran en el scheduler y se "
        "ingestan en el próximo scan (manual o automático diario)."
    )

    try:
        catalog = api.get_catalog()
        cat_stats = catalog.get("stats", {})
        col_st1, col_st2, col_st3 = st.columns(3)
        with col_st1:
            st.metric("Fuentes en catálogo", cat_stats.get("total_fuentes", 0))
        with col_st2:
            por_iss = cat_stats.get("por_institucion", {})
            st.metric(
                "Instituciones",
                len(por_iss),
                help=", ".join(f"{k}:{v}" for k, v in por_iss.items()),
            )
        with col_st3:
            por_dom = cat_stats.get("por_dominio", {})
            st.metric("Dominios", len(por_dom))

        # Tabla del catálogo
        items = catalog.get("items", [])
        if items:
            df_cat = pd.DataFrame([
                {
                    "Institución": (it.get("metadata") or {}).get("issuer", "—"),
                    "Tipo": it.get("document_type", "—"),
                    "Nombre": (it.get("metadata") or {}).get("title", it["name"])[:80],
                    "Dominio": it.get("domain", "—"),
                    "Año": (it.get("metadata") or {}).get("year", "—"),
                }
                for it in items
            ])
            st.dataframe(df_cat, use_container_width=True, hide_index=True, height=240)

        # Acciones
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button(
                "🌱 Popular catálogo completo",
                type="primary",
                use_container_width=True,
                help="Registra TODAS las fuentes del catálogo en doc_sources",
            ):
                with st.spinner("Registrando fuentes..."):
                    try:
                        res = api.seed_catalog()
                        st.success(
                            f"✓ {res.get('registradas', 0)} fuentes registradas. "
                            "Pulsa 'Disparar scan' para ingestarlas ahora."
                        )
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Error: {exc}")
        with col_b:
            issuer_filter = st.selectbox(
                "Solo institución",
                options=["(todas)"] + list((cat_stats.get("por_institucion") or {}).keys()),
                key="seed_issuer_filter",
            )
            if st.button("🎯 Popular solo esta", use_container_width=True):
                if issuer_filter == "(todas)":
                    st.warning("Elige una institución específica primero")
                else:
                    with st.spinner(f"Registrando fuentes de {issuer_filter}..."):
                        try:
                            res = api.seed_catalog(only_issuer=issuer_filter)
                            st.success(
                                f"✓ {res.get('registradas', 0)} fuentes de {issuer_filter}"
                            )
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Error: {exc}")
        with col_c:
            if st.button(
                "⚡ Disparar scan ahora",
                use_container_width=True,
                help="Procesa todas las fuentes habilitadas y las ingesta.",
            ):
                try:
                    res = api.trigger_scan(force=False, dry_run=False)
                    run_id = res.get("run_id")
                    if run_id:
                        st.session_state["active_scan_id"] = run_id
                        st.session_state["active_scan_started_at"] = time.time()
                        st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Error: {exc}")

    except Exception as exc:  # noqa: BLE001
        st.warning(f"No se pudo cargar el catálogo: {exc}")

    # -------------------------------------------------------------------
    # Sección "Progreso en vivo del scan" (solo visible si hay scan corriendo)
    # Está FUERA del try del catálogo — necesita correr aunque el catálogo falle.
    # -------------------------------------------------------------------
    active_run_id = st.session_state.get("active_scan_id")
    if active_run_id:
        st.markdown("---")
        st.markdown("### 📡 Progreso del scan en curso")

        # Total esperado (fuentes activas en BD)
        try:
            total_fuentes_activas = len([
                f for f in api.list_sources() if f.get("enabled", True)
            ])
        except Exception:  # noqa: BLE001
            total_fuentes_activas = 0

        bar_placeholder = st.empty()
        metrics_placeholder = st.empty()
        info_placeholder = st.empty()

        max_polls = 240  # ~8 minutos máximo de polling activo (2s * 240)
        for poll_n in range(max_polls):
            try:
                run = api.get_run(active_run_id)
            except Exception as exc:  # noqa: BLE001
                info_placeholder.error(f"Error obteniendo estado: {exc}")
                break

            estado = run.get("status", "?")
            scanned = run.get("sources_scanned", 0) or 0
            nuevos = run.get("docs_new", 0) or 0
            modif = run.get("docs_modified", 0) or 0
            sin_cambios = run.get("docs_unchanged", 0) or 0
            elapsed = int(
                time.time() - st.session_state.get("active_scan_started_at", time.time())
            )

            with metrics_placeholder.container():
                m1, m2, m3, m4, m5 = st.columns(5)
                with m1:
                    st.metric("Procesadas", f"{scanned}/{total_fuentes_activas or '?'}")
                with m2:
                    st.metric("Nuevos", nuevos)
                with m3:
                    st.metric("Modificados", modif)
                with m4:
                    st.metric("Sin cambios", sin_cambios)
                with m5:
                    st.metric("Tiempo", f"{elapsed}s")

            if estado in ("completed", "failed"):
                if estado == "completed":
                    bar_placeholder.progress(1.0, text=f"✓ Completado en {elapsed}s")
                    info_placeholder.success(
                        f"✅ Scan finalizado · {nuevos} nuevos · "
                        f"{modif} modificados · {sin_cambios} sin cambios"
                    )
                else:
                    bar_placeholder.empty()
                    info_placeholder.error(f"❌ Scan falló: {run.get('errors', '?')}")
                # Limpiar estado
                st.session_state.pop("active_scan_id", None)
                st.session_state.pop("active_scan_started_at", None)
                break

            # Running: pintar barra
            if total_fuentes_activas > 0:
                pct = min(scanned / total_fuentes_activas, 0.99)
                bar_placeholder.progress(
                    pct,
                    text=f"Procesando fuente {scanned} de {total_fuentes_activas}… "
                         f"({int(pct * 100)}%)",
                )
            else:
                bar_placeholder.progress(
                    min(scanned / max(scanned + 1, 1), 0.95),
                    text=f"Procesando… {scanned} fuentes hasta ahora",
                )
            info_placeholder.caption(
                f"Run ID: `{active_run_id[:8]}…` · refrescando cada 2s"
            )

            time.sleep(2)
        else:
            # Salió por timeout del loop
            info_placeholder.warning(
                "⏱ Polling detenido tras 8 min. El scan puede seguir en background — "
                "recarga la página o revisa 'Últimos runs' abajo."
            )

    st.markdown("---")

    # ----------------------------------------------------------------------
    # Sección "Fuentes registradas" (la que ya estaba)
    # ----------------------------------------------------------------------
    st.markdown("### 📋 Fuentes registradas en BD")
    try:
        fuentes = api.list_sources()
        if fuentes:
            df_fuentes = pd.DataFrame([
                {
                    "Fuente": f["name"],
                    "Dominio": f.get("domain") or "—",
                    "Cron": f.get("cron_expr"),
                    "Última verificación": f.get("last_checked_at") or "nunca",
                    "Estado": f.get("last_status") or "—",
                }
                for f in fuentes
            ])
            st.dataframe(df_fuentes, use_container_width=True, hide_index=True)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Error cargando fuentes: {exc}")

    st.markdown("### Últimos runs del scheduler")
    try:
        runs = api.list_runs(limit=20)
        if runs:
            df_runs = pd.DataFrame([
                {
                    "ID": r["id"][:8] + "…",
                    "Iniciado": r["started_at"][:19].replace("T", " "),
                    "Estado": r["status"],
                    "Fuentes": r.get("sources_scanned", 0),
                    "Nuevos": r.get("docs_new", 0),
                    "Modificados": r.get("docs_modified", 0),
                    "Sin cambios": r.get("docs_unchanged", 0),
                    "Disparado por": r.get("triggered_by", "—"),
                }
                for r in runs
            ])
            st.dataframe(df_runs, use_container_width=True, hide_index=True)
        else:
            st.info("Sin runs aún.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Error cargando runs: {exc}")

    st.markdown("### Eventos pendientes de notificar")
    try:
        eventos = api.list_events(limit=30)
        if eventos:
            df_ev = pd.DataFrame([
                {
                    "Tipo": e["event_type"],
                    "Resumen": e["summary"],
                    "Cuándo": e["created_at"][:19].replace("T", " "),
                }
                for e in eventos
            ])
            st.dataframe(df_ev, use_container_width=True, hide_index=True)
        else:
            st.success("Sin eventos pendientes.")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Error cargando eventos: {exc}")


render_footer()
