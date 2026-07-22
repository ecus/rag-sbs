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
from src.ui.auth_ui import (
    INACTIVITY_LIMIT_SEC,
    chequear_timeout,
    disparar_logout_con_encuesta,
    esta_logueado,
    render_auth,
    render_survey,
    tocar_actividad,
)
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
    """Detecta NIVEL A estricto: el LLM no encontró nada en el corpus.

    Si la respuesta empieza con 'Encontré información relacionada' (NIVEL B,
    clarificación), NO la consideramos sin evidencia — dejamos que el texto
    natural del LLM aparezca tal cual.
    """
    if not texto:
        return False
    t = texto.strip().lower()
    # NIVEL B (clarificación) → no es "sin evidencia"
    if t.startswith("encontré información") or t.startswith("encontre información"):
        return False
    if "¿podría especificar" in t or "¿podria especificar" in t:
        return False
    # NIVEL A estricto
    return any(k in t for k in (
        "no tengo evidencia suficiente",
        "no encuentro evidencia",
        "no hay evidencia",
        "sin información suficiente",
        "no dispongo de información",
        "no se encontró información",
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


# =========================================================================
# Cliente API (definido antes del auth para que render_auth pueda usarlo)
# =========================================================================

@st.cache_resource
def obtener_cliente() -> APIClient:
    return APIClient()


api = obtener_cliente()

# --- Administración por cuenta ---
# El panel admin es exclusivo de ADMIN_EMAIL. La clave admin vive en el
# servidor (ADMIN_API_KEY en el env del contenedor UI); cuando el usuario
# logueado ES el admin, el cliente la usa automáticamente. Así el admin no
# necesita conocer ninguna clave: alcanza con estar logueado con su cuenta.
import os as _os

ADMIN_EMAIL = _os.environ.get("ADMIN_EMAIL", "eurrutia489@gmail.com").strip().lower()
_ADMIN_KEY_ENV = _os.environ.get("ADMIN_API_KEY", "").strip()


def es_admin() -> bool:
    u = st.session_state.get("user") or {}
    return (u.get("email") or "").strip().lower() == ADMIN_EMAIL


# Si el usuario logueado es el admin, usar un cliente propio con la admin key
if es_admin() and _ADMIN_KEY_ENV:
    api = APIClient()
    api.set_admin_key(_ADMIN_KEY_ENV)


# =========================================================================
# Sesión: registro/login con email + timeout 5 min + encuesta de salida
# =========================================================================

# 1) Si hay encuesta pendiente, mostrarla y bloquear el resto de la UI
render_survey(api.base_url)

# 2) Si no hay usuario logueado, pedir login/registro y bloquear
render_auth(api.base_url)

# 2.5) Gate de aprobación: si el usuario no está aprobado, bloquear la app
if esta_logueado() and (st.session_state.user or {}).get("status") != "approved":
    _u = st.session_state.user
    st.markdown(
        '<div style="background:linear-gradient(135deg,#fef9c3,#fde68a);'
        'border:1px solid #f59e0b;border-radius:12px;padding:24px;'
        'margin:20px auto;max-width:640px;text-align:center;">'
        '<div style="font-size:26px;margin-bottom:10px;">⏳ Solicitud de acceso enviada</div>'
        f'<div style="color:#78350f;font-size:14px;line-height:1.6;">'
        f'Hola <b>{_u.get("name","")}</b>, tu registro con <b>{_u.get("email","")}</b> '
        f'quedó <b>pendiente de aprobación</b>.<br>'
        f'Un administrador revisará tu solicitud y podrás ingresar en cuanto sea '
        f'aprobada. Volvé a iniciar sesión más tarde.'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    if st.button("🔄 Ya me aprobaron — reintentar", type="primary"):
        # Re-login para refrescar el status
        st.session_state.user = None
        st.session_state.user_alias = None
        st.rerun()
    if st.button("🔚 Salir"):
        st.session_state.user = None
        st.session_state.user_alias = None
        st.rerun()
    st.stop()

# 3) Si la sesión expiró por inactividad → disparar encuesta
if esta_logueado() and chequear_timeout():
    disparar_logout_con_encuesta(reason="timeout")
    st.rerun()

# 4) La memoria persistente ahora se maneja por CONVERSACIONES (sidebar).
#    El historial activo es el de la conversación abierta; no se pide cargar
#    "memoria global" al entrar. Cada hilo es un contexto limpio.

# 5) Marcar actividad en cada rerun (resetea timeout)
if esta_logueado():
    tocar_actividad(api.base_url)


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


# Ventana de turnos del hilo que se REINYECTA al LLM en cada consulta.
# Es el control de costo: cuanto mayor, más tokens de entrada por consulta.
# Solo afecta cuánto contexto se manda, NO cuánto se guarda (se guarda todo).
MAX_TURNOS_CONTEXTO = 3


def _historial_para_backend(
    historial_streamlit: list[dict], max_turnos: int = MAX_TURNOS_CONTEXTO
) -> list[dict]:
    """Convierte el historial de Streamlit a {role, content} para el API.

    Solo toma los últimos N turnos completos (user+assistant) para no inflar
    el contexto (y por ende el costo del LLM).
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


def _pregunta_previa(idx: int) -> str:
    """Devuelve el texto del turno de usuario que precede a la respuesta idx."""
    hist = st.session_state.get("historial_chat", [])
    for j in range(idx - 1, -1, -1):
        if hist[j].get("rol") == "user":
            return hist[j].get("texto", "")
    return ""


def _render_feedback_botones(api: APIClient, idx: int, mensaje: dict) -> None:
    """👍 / 👎 bajo una respuesta; en 👎 abre caja de comentario."""
    votos = st.session_state.setdefault("votos_feedback", {})
    clave = f"{st.session_state.get('conversation_id','')}:{idx}"
    ya = votos.get(clave)

    if ya == "up":
        st.caption("👍 Gracias por tu feedback")
        return
    if ya == "down_done":
        st.caption("👎 Gracias, tomamos nota para mejorar")
        return

    pregunta = _pregunta_previa(idx)
    respuesta = mensaje.get("texto", "")

    if ya == "down_pending":
        # Mostrar caja de comentario
        with st.form(f"fbform_{clave}", clear_on_submit=True):
            st.caption("¿Qué estuvo mal o qué esperabas? (nos ayuda a mejorar)")
            comentario = st.text_area("Comentario", key=f"fbcom_{clave}",
                                      label_visibility="collapsed", height=70)
            c1, c2 = st.columns([1, 1])
            enviar = c1.form_submit_button("Enviar", type="primary",
                                           use_container_width=True)
            saltar = c2.form_submit_button("Omitir", use_container_width=True)
        if enviar or saltar:
            api.enviar_voto(
                email=(st.session_state.get("user") or {}).get("email"),
                conversation_id=st.session_state.get("conversation_id"),
                question=pregunta, answer=respuesta, vote="down",
                comment=(comentario if enviar else None),
            )
            votos[clave] = "down_done"
            st.rerun()
        return

    col1, col2, _ = st.columns([1, 1, 8])
    if col1.button("👍", key=f"up_{clave}", help="Respuesta útil"):
        api.enviar_voto(
            email=(st.session_state.get("user") or {}).get("email"),
            conversation_id=st.session_state.get("conversation_id"),
            question=pregunta, answer=respuesta, vote="up",
        )
        votos[clave] = "up"
        st.rerun()
    if col2.button("👎", key=f"down_{clave}", help="Respuesta a mejorar"):
        votos[clave] = "down_pending"
        st.rerun()


def _asegurar_conversacion(api: APIClient, user: dict) -> str | None:
    """Devuelve el conversation_id activo; crea uno si no hay."""
    cid = st.session_state.get("conversation_id")
    if cid:
        return cid
    conv = api.conv_crear(email=user.get("email"), user_id=user.get("id"))
    if conv:
        st.session_state.conversation_id = conv["id"]
        st.session_state.conversaciones = None  # invalidar cache de la lista
        return conv["id"]
    return None


def _render_conversaciones(api: APIClient, user: dict) -> None:
    """Sidebar estilo ChatGPT: nueva conversación + lista + renombrar/borrar."""
    email = user.get("email")

    if st.button("➕ Nueva conversación", use_container_width=True,
                 type="primary", key="conv_nueva"):
        conv = api.conv_crear(email=email, user_id=user.get("id"))
        if conv:
            st.session_state.conversation_id = conv["id"]
            st.session_state.historial_chat = []
            st.session_state.conversaciones = None
            st.toast("Nueva conversación", icon="✨")
            st.rerun()

    # Cargar lista (cacheada en session_state, refrescable)
    if st.session_state.get("conversaciones") is None:
        st.session_state.conversaciones = api.conv_listar(email, limit=40)
    convs = st.session_state.conversaciones or []

    if not convs:
        st.caption("Aún no tenés conversaciones guardadas.")
        return

    st.caption(f"💬 Tus conversaciones ({len(convs)})")
    activa = st.session_state.get("conversation_id")
    for c in convs:
        es_activa = c["id"] == activa
        etiqueta = ("🟢 " if es_activa else "") + (c["title"] or "Sin título")
        if st.button(etiqueta, use_container_width=True,
                     key=f"conv_{c['id']}",
                     type="secondary",
                     help=f"{c['n_mensajes']} mensaje(s)"):
            # Cambiar de conversación: cargar sus mensajes
            msgs = api.conv_mensajes(c["id"], limit=100)
            st.session_state.conversation_id = c["id"]
            st.session_state.historial_chat = msgs
            st.session_state.memoria_decidida = True
            st.rerun()

    # Controles de la conversación activa
    if activa:
        with st.expander("✏️ Renombrar / 🗑 borrar conversación activa"):
            nuevo = st.text_input("Nuevo título", key="conv_rename_input")
            col_r1, col_r2 = st.columns(2)
            if col_r1.button("Renombrar", use_container_width=True, key="conv_rename_go"):
                if nuevo.strip() and api.conv_renombrar(activa, email, nuevo.strip()):
                    st.session_state.conversaciones = None
                    st.toast("Renombrada", icon="✏️")
                    st.rerun()
            if col_r2.button("🗑 Borrar", use_container_width=True, key="conv_delete_go"):
                if api.conv_borrar(activa, email):
                    st.session_state.conversation_id = None
                    st.session_state.historial_chat = []
                    st.session_state.conversaciones = None
                    st.toast("Conversación borrada", icon="🗑")
                    st.rerun()


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
    error_tipo: str = ""

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
                alias=st.session_state.get("user_alias"),
                conversation_id=st.session_state.get("conversation_id"),
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
                    error_tipo = data.get("type", "") if isinstance(data, dict) else ""
                    break
                elif evento == "done":
                    break
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            error_tipo = ""

        if error:
            err_lower = error.lower()
            # Casos de control de acceso (no son errores del LLM)
            if error_tipo == "http_403" or "pendiente de aprobación" in err_lower:
                status.update(label="⏳ Acceso pendiente", state="error", expanded=True)
                placeholder_texto.warning(
                    "⏳ **Tu acceso está pendiente de aprobación.** "
                    "Un administrador debe habilitarte antes de poder consultar."
                )
                return
            if error_tipo == "http_429" and "por día" in err_lower:
                status.update(label="🚦 Límite diario alcanzado", state="error", expanded=True)
                placeholder_texto.warning(f"🚦 {error}")
                return

            status.update(label="❌ Error del LLM", state="error", expanded=True)
            is_503 = "503" in error or "unavailable" in err_lower or "high demand" in err_lower
            is_429 = "429" in error or "quota" in err_lower or "rate" in err_lower
            is_timeout = "timeout" in err_lower or "timed out" in err_lower

            if is_503:
                titulo = "🌐 El modelo (Gemini) está sobrecargado"
                explicacion = (
                    "Google reporta alta demanda en el LLM. **No es un problema de la app** "
                    "ni de tus datos — es del lado de Google y suele durar 1-5 minutos."
                )
                que_hacer = "Esperá ~2 min y reintentá la misma consulta."
            elif is_429:
                titulo = "🚦 Límite de cuota alcanzado"
                explicacion = (
                    "Se excedió la cuota gratuita por minuto del LLM."
                )
                que_hacer = "Esperá ~60 segundos y reintentá."
            elif is_timeout:
                titulo = "⏱ Timeout durante la generación"
                explicacion = "La generación tardó más del límite configurado."
                que_hacer = "Reintentá; si pasa seguido, desactivá modo Informe."
            else:
                titulo = "❌ Error durante la generación"
                explicacion = "El backend no pudo completar la respuesta."
                que_hacer = "Reintentá. Si persiste, contactá al admin."

            placeholder_texto.markdown(
                f'<div style="background:#fef2f2;border:2px solid #f87171;'
                f'border-radius:10px;padding:18px 20px;margin:12px 0;">'
                f'<div style="font-size:18px;font-weight:700;color:#991b1b;'
                f'margin-bottom:8px;">{titulo}</div>'
                f'<div style="color:#7f1d1d;font-size:14px;line-height:1.6;'
                f'margin-bottom:10px;">{explicacion}</div>'
                f'<div style="color:#1f2937;font-size:14px;background:#fff;'
                f'padding:10px 12px;border-radius:6px;border-left:4px solid #2563eb;">'
                f'<b>👉 Qué hacer:</b> {que_hacer}</div>'
                f'<details style="margin-top:10px;color:#6b7280;font-size:11px;">'
                f'<summary style="cursor:pointer;">Detalle técnico</summary>'
                f'<code style="font-size:11px;display:block;margin-top:6px;'
                f'background:#f3f4f6;padding:8px;border-radius:4px;'
                f'white-space:pre-wrap;word-break:break-all;">{error}</code>'
                f'</details>'
                f'</div>',
                unsafe_allow_html=True,
            )
            return

        # Texto final con resaltado de [Fuente N]
        respuesta_final = "".join(texto_acumulado)
        sin_evidencia = _es_respuesta_sin_evidencia(respuesta_final)

        # Detectar NIVEL B (clarificación) además de NIVEL A
        es_clarif_b = respuesta_final.strip().lower().startswith(
            ("encontré información", "encontre información")
        ) or "¿podría especificar" in respuesta_final.lower()

        if sin_evidencia:
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

        # Detector de respuesta truncada: termina sin signo de cierre claro
        # (sin punto final, sin '.', con ** abierto, o cortada en lista numerada)
        respuesta_trim = respuesta_final.rstrip()
        truncada = bool(respuesta_trim) and (
            respuesta_trim.endswith(("**", "1.", "2.", "3.", ":")) or
            (not respuesta_trim.endswith((".", "!", "?", ")", "**.")) and len(respuesta_trim) > 200)
        )
        if truncada and consulta_input:
            st.markdown(
                '<div style="background:#fff7ed;border:1px solid #fb923c;'
                'border-radius:8px;padding:10px 12px;margin:8px 0;'
                'font-size:13px;color:#9a3412;">'
                '✂️ La respuesta parece <b>cortada</b> por límite de tokens. '
                'Activá <b>📋 Informe</b> arriba para obtener respuestas extensas, '
                'o pedí <b>"continuar"</b> en el siguiente turno.'
                '</div>',
                unsafe_allow_html=True,
            )

        # Botón "Probar de otra forma" cuando la respuesta es SIN o B (parcial)
        if (sin_evidencia or es_clarif_b) and consulta_input:
            with st.container():
                st.markdown(
                    '<div style="background:#fef9c3;border:1px solid #facc15;'
                    'border-radius:8px;padding:10px 12px;margin:8px 0;'
                    'font-size:13px;color:#854d0e;">'
                    '🔄 ¿Quieres que intente <b>otra estrategia de búsqueda</b>? '
                    'Activamos Grafo + Saltos 2 + sinónimos regulatorios y '
                    'reformulamos la pregunta automáticamente.'
                    '</div>',
                    unsafe_allow_html=True,
                )
                if st.button("🔁 Probar de otra forma", type="primary",
                             use_container_width=False,
                             key=f"retry_{hash(consulta_input)}"):
                    sinonimos_map = {
                        "RCD": "Reporte Crediticio de Deudores Anexo 6",
                        "PDD": "Probabilidad de incumplimiento crediticio",
                        "patrimonio": "patrimonio efectivo capital regulatorio",
                        "provisión": "provisiones genéricas específicas categoría riesgo",
                        "fideicomiso": "fideicomiso patrimonio fideicometido SPV",
                        "registro": "asiento contable cuenta cuentas afectadas",
                    }
                    consulta_enriquecida = consulta_input
                    for term, syn in sinonimos_map.items():
                        if term.lower() in consulta_input.lower():
                            consulta_enriquecida = f"{consulta_input} (también: {syn})"
                            break
                    # Forzar toggles para esta consulta
                    st.session_state.chat_graph = True
                    st.session_state.chat_hops = 1  # Saltos=2 (index 1)
                    st.session_state.chat_agente = True
                    st.session_state.consulta_pendiente = consulta_enriquecida
                    st.toast("🔁 Reintentando con grafo + sinónimos", icon="✨")
                    st.rerun()

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

        # Guardar en historial siempre que haya respuesta válida (input directo
        # o consulta extendida desde acrónimo/planner). Solo no guardamos
        # cuando hubo error y no hay texto útil.
        if respuesta_final and not error:
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

    # Indicador de sesión activa (siempre visible)
    if esta_logueado():
        _u = st.session_state.user
        # Tiempo restante de inactividad
        _last = st.session_state.get("last_activity_at")
        _restante = ""
        if _last:
            _seg = max(0, int(INACTIVITY_LIMIT_SEC - (datetime.now() - _last).total_seconds()))
            _restante = f" · ⏳ {_seg//60}m {_seg%60:02d}s"
        st.markdown(
            f'<div style="background:#f0fdf4;border:1px solid #86efac;'
            f'border-radius:8px;padding:8px 12px;margin-bottom:12px;'
            f'font-size:12px;color:#166534;">'
            f'👤 <b>{_u.get("name","")}</b><br>'
            f'<span style="color:#475569;font-size:10px;">'
            f'{_u.get("email","")}{_restante}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("🔚 Salir", use_container_width=True, key="logout",
                     help="Cierra la sesión y abre la encuesta de salida"):
            disparar_logout_con_encuesta(reason="manual")
            st.rerun()

        # ----- Gestor de conversaciones (estilo ChatGPT) -----
        _render_conversaciones(api, _u)

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
        # El panel de administración es EXCLUSIVO de la cuenta admin.
        if es_admin():
            if st.button("🔧 Panel de administración", use_container_width=True,
                         help="Dashboard exclusivo de tu cuenta"):
                st.session_state.modo_tecnico = True
                st.rerun()
        st.caption(
            '<div style="font-size:10px;color:#94a3b8;text-align:center;'
            'margin-top:12px;">v0.3 · Portafolio personal</div>',
            unsafe_allow_html=True,
        )
    else:
        # ----- MODO TÉCNICO: dashboard admin (solo cuenta admin) -----
        if not es_admin():
            # Salvaguarda: si no es admin, forzar salida del modo técnico
            st.session_state.modo_tecnico = False
            st.rerun()
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

    # =====================================================================
    # 🪄 Asistente de consulta — wizard que estructura preguntas vagas
    # =====================================================================
    with st.expander(
        "🪄 Asistente para formular consulta (recomendado si tu pregunta es compleja)",
        expanded=False,
    ):
        st.caption(
            "Responda los campos y el asistente arma una consulta estructurada "
            "que activa el modo informe + grafo + clarificaciones."
        )

        wz_rol = st.selectbox(
            "Su rol",
            [
                "(seleccione)",
                "Compliance officer",
                "Auditor interno/externo",
                "Riesgos (crédito/operacional/mercado)",
                "Contabilidad / IFRS",
                "Tecnología / Ciberseguridad",
                "Legal / Jurídico",
                "Operaciones / Negocios",
                "Inversionista / Mercado de valores",
                "Asesor regulatorio externo",
            ],
            key="wz_rol",
        )
        wz_caso = st.text_area(
            "Describa el caso o situación",
            placeholder=(
                "Ej.: Una empresa de créditos está estructurando una operación "
                "de fondeo con una empresa de inversión, mediante titulización "
                "de cartera y vehículo de fideicomiso."
            ),
            key="wz_caso",
            height=90,
        )
        wz_objetivo = st.selectbox(
            "¿Qué necesita?",
            [
                "(seleccione)",
                "Informe regulatorio integral (todos los aspectos)",
                "Identificar normas SBS aplicables",
                "Calcular un requerimiento (provisión, patrimonio efectivo)",
                "Conocer el tratamiento contable específico",
                "Evaluar riesgos del caso (crédito/operacional/etc.)",
                "Saber qué documentos/reportes presentar",
                "Comparar dos escenarios",
            ],
            key="wz_objetivo",
        )
        wz_temas = st.multiselect(
            "Temas relevantes (opcional, ayuda al retrieval)",
            [
                "Riesgo de crédito",
                "Riesgo operacional",
                "LAFT (lavado de activos)",
                "Gobierno corporativo",
                "Ciberseguridad / TI",
                "Manual de Contabilidad",
                "Patrimonio efectivo / Basilea",
                "Titulización / Fideicomiso",
                "Pensiones / SPP",
                "Mercado de valores / SMV",
                "Protección al consumidor",
                "Tributario / SUNAT",
            ],
            key="wz_temas",
        )

        if st.button("✨ Generar consulta estructurada", use_container_width=True):
            if wz_rol == "(seleccione)" or not wz_caso.strip() or wz_objetivo == "(seleccione)":
                st.warning("Complete los 3 primeros campos para generar la consulta.")
            else:
                partes = [
                    f"**Rol:** Soy {wz_rol.lower()} en una empresa supervisada por la SBS Perú.",
                    "",
                    f"**Caso:** {wz_caso.strip()}",
                    "",
                    f"**Objetivo:** {wz_objetivo}.",
                ]
                if wz_temas:
                    partes.append("")
                    partes.append(
                        f"**Temas relevantes a considerar:** {', '.join(wz_temas)}."
                    )
                partes.append("")
                partes.append(
                    "Por favor cite todas las normas SBS/BCRP/Congreso/MEF "
                    "aplicables con número, año y artículo/sección. Si requiere "
                    "información adicional para responder con precisión, "
                    "formule las preguntas de clarificación necesarias."
                )
                consulta_armada = "\n".join(partes)
                st.session_state.consulta_pendiente = consulta_armada
                # Auto-activar toggles ideales para casos complejos
                st.session_state.chat_graph = True
                st.session_state.chat_hops = 1  # index 1 → valor 2
                st.session_state.chat_informe = True
                st.session_state.chat_agente = True
                st.success("Consulta lista. Se activaron Grafo + Saltos 2 + Informe + Agente.")
                st.rerun()

    # Opciones del pipeline. Para usuarios normales el chat es SIMPLE: se usan
    # defaults inteligentes y los toggles quedan escondidos en un expander
    # "Opciones avanzadas". En modo técnico se muestran directamente.
    def _toggles_avanzados() -> None:
        col_b, col_c, col_d, col_e, col_f, col_g = st.columns(6)
        with col_b:
            st.toggle("Graph-aug", value=st.session_state.get("chat_graph", False),
                      key="chat_graph",
                      help="Usa el knowledge graph para enriquecer el contexto")
        with col_c:
            st.selectbox("Saltos", [1, 2], index=0, key="chat_hops",
                         disabled=not st.session_state.get("chat_graph"))
        with col_d:
            st.toggle("📋 Informe", value=st.session_state.get("chat_informe", False),
                      key="chat_informe", help="Respuesta estructurada en 10 dimensiones")
        with col_e:
            st.toggle("🤖 Agente", value=st.session_state.get("chat_agente", False),
                      key="chat_agente",
                      help="Pide clarificaciones antes de buscar si la consulta es ambigua.")
        with col_f:
            st.toggle("⚡ Stream", value=st.session_state.get("chat_stream", True),
                      key="chat_stream", help="Token-por-token en vivo.")
        with col_g:
            st.toggle("🧠 Memoria", value=st.session_state.get("chat_memoria", True),
                      key="chat_memoria",
                      help="Mantiene el hilo de la conversación (últimos turnos).")

    # Defaults para usuarios normales (si nunca se setearon los toggles)
    st.session_state.setdefault("chat_graph", False)
    st.session_state.setdefault("chat_hops", 1)
    st.session_state.setdefault("chat_informe", False)
    st.session_state.setdefault("chat_agente", False)
    st.session_state.setdefault("chat_stream", True)
    st.session_state.setdefault("chat_memoria", True)

    if st.session_state.get("modo_tecnico"):
        _toggles_avanzados()
    else:
        with st.expander("⚙️ Opciones avanzadas"):
            st.caption(
                "Por defecto la mesa ya usa la mejor configuración. Estas opciones "
                "son para usuarios expertos."
            )
            _toggles_avanzados()

    usar_grafo = st.session_state.get("chat_graph", False)
    max_hops = st.session_state.get("chat_hops", 1)
    modo_informe = st.session_state.get("chat_informe", False)
    usar_planner = st.session_state.get("chat_agente", False)
    usar_streaming = st.session_state.get("chat_stream", True)
    usar_memoria = st.session_state.get("chat_memoria", True)

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
    for idx, mensaje in enumerate(st.session_state.historial_chat):
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
            # Botones like/dislike bajo cada respuesta del asistente
            if mensaje["rol"] == "assistant":
                _render_feedback_botones(api, idx, mensaje)

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

    # ===== Detector de acrónimos ambiguos (interceptor) =====
    # Paso 1: input nuevo con siglas ambiguas → marcar como pendiente.
    # NO renderizamos el form acá: si lo atáramos a consulta_input, el rerun
    # del click del form (donde chat_input devuelve None) no ejecutaría el
    # bloque y el click se perdería — ese era el bug original.
    if pregunta and consulta_input and not st.session_state.get("acronimo_resuelto"):
        try:
            from src.agents.acronyms import detectar as _detectar_acronimos
            _ambigs = _detectar_acronimos(pregunta)
        except Exception:  # noqa: BLE001
            _ambigs = []
        if _ambigs:
            st.session_state.pregunta_pendiente_acronimo = pregunta
            pregunta = None
            consulta_input = None

    # Paso 2: mientras haya pendiente sin resolver, renderizar el form en
    # CADA rerun (desde session_state) para que el submit siempre se capture.
    if (
        st.session_state.get("pregunta_pendiente_acronimo")
        and not st.session_state.get("acronimo_resuelto")
    ):
        pregunta_acro = st.session_state.pregunta_pendiente_acronimo
        try:
            from src.agents.acronyms import detectar as _detectar_acronimos
            ambiguedades = _detectar_acronimos(pregunta_acro)
        except Exception:  # noqa: BLE001
            ambiguedades = []

        if not ambiguedades:
            # Falsa alarma (no debería pasar): liberar y seguir normal
            st.session_state.pregunta_pendiente_acronimo = None
        else:
            st.warning(
                f"⚠️ Detecté **{len(ambiguedades)} acrónimo(s) ambiguo(s)** en tu pregunta. "
                f"¿A cuál te referís?"
            )
            with st.form("form_acronimos", clear_on_submit=False):
                selecciones: dict[str, str] = {}
                for amb in ambiguedades:
                    st.markdown(f"**`{amb['sigla']}` — elegí significado:**")
                    opciones_labels = []
                    opciones_map = {}
                    for op in amb["opciones"]:
                        label = f"{op['significado']} — {op['contexto']}"
                        if op.get("norma_principal"):
                            label += f" · {op['norma_principal']}"
                        opciones_labels.append(label)
                        opciones_map[label] = op["significado"]
                    opciones_labels.append(f"(no especificar, usar `{amb['sigla']}` tal cual)")
                    choice = st.radio(
                        f"Opciones para {amb['sigla']}",
                        opciones_labels,
                        index=0,
                        label_visibility="collapsed",
                        key=f"acro_radio_{amb['sigla']}",
                    )
                    selecciones[amb["sigla"]] = opciones_map.get(choice, "")

                submitted = st.form_submit_button(
                    "▶️ Continuar con la consulta",
                    type="primary",
                    use_container_width=True,
                )

            if submitted:
                pregunta_extendida = pregunta_acro
                for sigla, significado in selecciones.items():
                    if significado:
                        pregunta_extendida = pregunta_extendida.replace(
                            sigla, f"{sigla} ({significado})", 1
                        )
                st.session_state.consulta_pendiente = pregunta_extendida
                st.session_state.acronimo_resuelto = True
                st.rerun()
            st.stop()

    if pregunta:
        # Reset flag para próxima consulta (siempre que entremos a procesar)
        st.session_state.acronimo_resuelto = False

        # Renderizar bubble del usuario SIEMPRE — sea input directo,
        # consulta extendida desde acrónimo, o desde planner
        if consulta_input or st.session_state.get("pregunta_pendiente_acronimo"):
            texto_usuario = consulta_input or pregunta
            st.session_state.historial_chat.append(
                {"rol": "user", "texto": texto_usuario}
            )
            with st.chat_message("user"):
                st.markdown(texto_usuario)
            # Limpiar marcador de acrónimo pendiente
            st.session_state.pregunta_pendiente_acronimo = None

        # Si es input directo, opcionalmente correr planner
        if consulta_input:
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
        # El último mensaje siempre es la pregunta actual del usuario
        historial_backend = _historial_para_backend(
            st.session_state.historial_chat[:-1]
            if st.session_state.historial_chat
            and st.session_state.historial_chat[-1].get("rol") == "user"
            else st.session_state.historial_chat
        ) if usar_memoria else []

        # Incrementar contador de consultas de esta sesión
        st.session_state.queries_this_session = (
            st.session_state.get("queries_this_session", 0) + 1
        )

        # Asegurar conversación activa (crea una si es la primera consulta).
        # La lista se invalida para refrescar título/contador tras responder.
        if esta_logueado():
            _asegurar_conversacion(api, st.session_state.user)
            st.session_state.conversaciones = None

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
                    alias=st.session_state.get("user_alias"),
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
    # 📈 Dashboard de monitoreo (RF-015)
    # ----------------------------------------------------------------------
    st.markdown("### 📈 Monitoreo de uso")
    _dias = st.selectbox("Período", [7, 30, 90], index=1, key="dash_dias",
                         format_func=lambda d: f"Últimos {d} días")
    _m = api.dashboard_metricas(dias=_dias)
    if _m:
        m1, m2, m3 = st.columns(3)
        m1.metric("Consultas", _m.get("total_consultas", 0))
        m2.metric("Usuarios activos", _m.get("usuarios_activos", 0))
        m3.metric("Latencia media", f"{_m.get('latencia_avg_ms', 0)} ms")

        # Consultas por día
        pd_data = _m.get("consultas_por_dia", [])
        if pd_data:
            st.caption("Consultas por día")
            df_dia = pd.DataFrame(pd_data)
            st.bar_chart(df_dia.set_index("dia")["consultas"], height=180)

        cda, cdb = st.columns(2)
        with cda:
            st.caption("📄 Documentos más referenciados")
            td = _m.get("top_documentos", [])
            if td:
                st.dataframe(pd.DataFrame(td), hide_index=True,
                             use_container_width=True, height=280)
            else:
                st.info("Sin datos aún.")
        with cdb:
            st.caption("🔎 Consultas más frecuentes")
            tc = _m.get("top_consultas", [])
            if tc:
                st.dataframe(pd.DataFrame(tc), hide_index=True,
                             use_container_width=True, height=280)
            else:
                st.info("Sin datos aún.")

        # Distribución de confianza
        dc = _m.get("distribucion_confianza", [])
        if dc:
            st.caption("Distribución de confianza")
            st.dataframe(pd.DataFrame(dc), hide_index=True, use_container_width=True)
    else:
        st.info("Aún no hay datos de consultas.")

    # Export de logs por período (RNF-021)
    with st.expander("📥 Exportar consultas por período (CSV)"):
        ce1, ce2 = st.columns(2)
        _hoy = datetime.now().date()
        f_desde = ce1.date_input("Desde", value=_hoy.replace(day=1), key="exp_desde")
        f_hasta = ce2.date_input("Hasta", value=_hoy, key="exp_hasta")
        _csv = None
        if st.button("Generar CSV", type="primary", key="exp_go"):
            _csv = api.export_logs_csv(str(f_desde), str(f_hasta))
            if _csv:
                st.download_button(
                    "⬇️ Descargar CSV", data=_csv,
                    file_name=f"consultas_{f_desde}_a_{f_hasta}.csv",
                    mime="text/csv", key="exp_dl",
                )
            else:
                st.error("No se pudo generar el export.")

    st.markdown("---")

    # ----------------------------------------------------------------------
    # Solicitudes de acceso pendientes
    # ----------------------------------------------------------------------
    st.markdown("### 🔓 Solicitudes de acceso")
    pendientes = api.usuarios_pendientes()
    if not pendientes:
        st.success("No hay solicitudes pendientes. ✓")
    else:
        st.warning(f"⏳ {len(pendientes)} usuario(s) esperando aprobación:")
        for p in pendientes:
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.markdown(
                    f"**{p['name']}** · {p['email']}  \n"
                    f"<span style='color:#64748b;font-size:12px;'>"
                    f"{p.get('organization') or 's/org'} · {p.get('role') or 's/rol'}</span>",
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button("✅ Aprobar", key=f"apr_{p['email']}",
                             use_container_width=True, type="primary"):
                    if api.aprobar_usuario(p["email"]):
                        st.toast(f"Aprobado: {p['email']}", icon="✅")
                        st.rerun()
            with c3:
                if st.button("❌ Rechazar", key=f"rej_{p['email']}",
                             use_container_width=True):
                    if api.rechazar_usuario(p["email"]):
                        st.toast(f"Rechazado: {p['email']}", icon="🚫")
                        st.rerun()

    with st.expander("🎚️ Límite por usuario (consultas/día)"):
        st.caption("Default: 20 consultas/día. Poné 0 para dejarlo sin límite.")
        with st.form("form_limite"):
            lim_email = st.text_input("Email del usuario", key="lim_email")
            lim_valor = st.number_input("Límite diario", min_value=0, max_value=10000,
                                        value=20, step=5, key="lim_valor")
            if st.form_submit_button("Actualizar límite", type="primary"):
                if lim_email.strip() and api.set_limite_diario(lim_email.strip(), int(lim_valor)):
                    st.success(f"Límite de {lim_email.strip()} → {int(lim_valor)}/día")
                else:
                    st.error("No se pudo actualizar (¿email correcto?).")

    with st.expander("🌐 Límites GLOBALES (toda la mesa)"):
        st.caption(
            "Topes para el total de consultas de todos los usuarios juntos. "
            "Protegen tu cuota de Gemini. 0 = sin límite."
        )
        _s = api.get_settings()
        with st.form("form_limites_globales"):
            gc1, gc2 = st.columns(2)
            g_dia = gc1.number_input("Máx por día (global)", min_value=0, max_value=100000,
                                     value=int(_s.get("global_daily_limit", "0") or 0),
                                     step=10, key="g_dia")
            g_hora = gc2.number_input("Máx por hora (global)", min_value=0, max_value=100000,
                                      value=int(_s.get("global_hourly_limit", "0") or 0),
                                      step=5, key="g_hora")
            if st.form_submit_button("Guardar límites globales", type="primary"):
                if api.set_limites_globales(int(g_dia), int(g_hora)):
                    st.success(f"Global: {int(g_dia)}/día · {int(g_hora)}/hora")
                else:
                    st.error("No se pudo guardar.")

    st.markdown("---")

    # ----------------------------------------------------------------------
    # Feedback de respuestas (like/dislike + comentarios)
    # ----------------------------------------------------------------------
    st.markdown("### 👍👎 Feedback de respuestas")
    fb = api.feedback_summary(limit=50)
    if fb:
        fc1, fc2, fc3 = st.columns(3)
        fc1.metric("👍 Likes", fb.get("likes", 0))
        fc2.metric("👎 Dislikes", fb.get("dislikes", 0))
        total = fb.get("likes", 0) + fb.get("dislikes", 0)
        pct = round(100 * fb.get("likes", 0) / total) if total else 0
        fc3.metric("% satisfacción", f"{pct}%")
        detalle = fb.get("dislikes_detalle", [])
        if detalle:
            st.markdown("**Dislikes para revisar:**")
            for d in detalle:
                with st.expander(f"👎 {(d.get('question') or 's/pregunta')[:70]}"):
                    st.markdown(f"**Usuario:** {d.get('email') or '—'}")
                    if d.get("comment"):
                        st.markdown(f"**Comentario:** {d['comment']}")
                    st.caption(f"Pregunta: {d.get('question') or '—'}")
                    st.caption(f"Respuesta (extracto): {d.get('answer') or '—'}")
        else:
            st.info("No hay dislikes registrados. 🎉")
    else:
        st.info("Aún no hay feedback.")

    st.markdown("---")

    # ----------------------------------------------------------------------
    # Gestión de usuarios — reset de PIN
    # ----------------------------------------------------------------------
    with st.expander("🔑 Resetear PIN de un usuario"):
        st.caption(
            "Borra el PIN y el código de recuperación del email indicado. "
            "El próximo login de ese usuario definirá un PIN nuevo y "
            "recibirá un código de recuperación nuevo."
        )
        with st.form("form_admin_reset_pin"):
            reset_email = st.text_input("Email del usuario", key="admin_reset_email")
            reset_go = st.form_submit_button("Resetear PIN", type="primary")
        if reset_go and reset_email.strip():
            try:
                import httpx as _httpx
                _r = _httpx.post(
                    f"{api.base_url}/v1/users/admin/reset-pin",
                    json={"email": reset_email.strip()},
                    headers={"X-Admin-Key": st.session_state.get("admin_key", "")},
                    timeout=8,
                )
                if _r.status_code == 200:
                    st.success(
                        f"PIN de {reset_email.strip()} reseteado. Su próximo "
                        "login define el PIN nuevo."
                    )
                elif _r.status_code == 404:
                    st.warning("Ese email no está registrado.")
                else:
                    st.error(f"Error: {_r.text}")
            except Exception as _e:  # noqa: BLE001
                st.error(f"No se pudo conectar: {_e}")

    # ----------------------------------------------------------------------
    # Sección "Analytics de usuarios" — consultas registradas
    # ----------------------------------------------------------------------
    st.markdown("### 👥 Analytics de usuarios")
    st.caption(
        "Consultas registradas por alias. Solo se loguea si el usuario se "
        "identificó al entrar (lo cual hacemos siempre desde v0.4)."
    )
    try:
        users = api.analytics_users(limit=30)
        if not users:
            st.info("Aún no hay consultas registradas.")
        else:
            import pandas as _pd
            df_users = _pd.DataFrame(users)
            df_users.columns = [
                "Alias", "Consultas", "Última actividad",
                "Confianza ALTA", "Sin evidencia", "Latencia avg (ms)",
            ]
            st.dataframe(df_users, use_container_width=True, hide_index=True, height=240)

            sel = st.selectbox(
                "Ver consultas de:",
                options=["(elegir usuario)"] + [u["alias"] for u in users],
                key="analytics_user_sel",
            )
            if sel != "(elegir usuario)":
                qrs = api.analytics_user_queries(sel, limit=30)
                for q in qrs:
                    badge_conf = {
                        "alta": "🟢",
                        "media": "🟡",
                        "baja": "🟠",
                    }.get(q.get("confidence") or "", "⚪")
                    with st.expander(
                        f"{badge_conf} {(q.get('query') or '')[:90]}"
                        f"  · {q.get('created_at','')[:16]}"
                    ):
                        st.caption(
                            f"Confianza: {q.get('confidence') or 'n/a'} · "
                            f"Fuentes: {q.get('n_sources', 0)} · "
                            f"Latencia: {q.get('latency_ms', 0)} ms"
                        )
                        st.markdown(f"**Pregunta:** {q.get('query','')}")
                        if q.get("answer"):
                            st.markdown(f"**Respuesta:** {q['answer'][:1500]}…")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Analytics no disponible: {exc}")

    st.markdown("---")

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
                    "Año": str((it.get("metadata") or {}).get("year") or "—"),
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
