"""Componentes UI: registro/login con email, timeout, encuesta de salida."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

import httpx
import streamlit as st

# Timeout de inactividad por defecto (5 minutos)
INACTIVITY_LIMIT_SEC = 5 * 60

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


# -----------------------------------------------------------------------------
# State helpers
# -----------------------------------------------------------------------------

def _init_state() -> None:
    """Inicializa keys de sesión relacionadas a auth/timeout/survey."""
    defaults = {
        "user": None,                       # dict {id, email, name, ...}
        "auth_mode": "login",               # "login" | "register"
        "session_started_at": None,         # datetime
        "last_activity_at": None,           # datetime
        "queries_this_session": 0,
        "show_survey": False,
        "survey_closed_reason": "manual",   # "manual" | "timeout" | "browser"
        "survey_submitted": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def esta_logueado() -> bool:
    return bool(st.session_state.get("user"))


def user_id() -> str | None:
    u = st.session_state.get("user")
    return u.get("id") if u else None


def user_email() -> str | None:
    u = st.session_state.get("user")
    return u.get("email") if u else None


# -----------------------------------------------------------------------------
# Inactivity / timeout
# -----------------------------------------------------------------------------

def tocar_actividad(api_base: str) -> None:
    """Marca actividad reciente. Llamar en cada interacción."""
    st.session_state.last_activity_at = datetime.now()
    uid = user_id()
    if uid:
        try:
            httpx.post(
                f"{api_base}/v1/users/activity",
                json={"user_id": uid},
                timeout=3,
            )
        except Exception:  # noqa: BLE001
            pass


def chequear_timeout() -> bool:
    """Retorna True si la sesión expiró por inactividad."""
    last = st.session_state.get("last_activity_at")
    if not last:
        return False
    delta = (datetime.now() - last).total_seconds()
    return delta > INACTIVITY_LIMIT_SEC


def disparar_logout_con_encuesta(reason: str = "manual") -> None:
    """Marca la sesión para mostrar la encuesta de salida."""
    st.session_state.show_survey = True
    st.session_state.survey_closed_reason = reason


# -----------------------------------------------------------------------------
# Login / Registro
# -----------------------------------------------------------------------------

def _email_valido(email: str) -> bool:
    return bool(EMAIL_RE.match((email or "").strip()))


def render_auth(api_base: str) -> None:
    """Renderiza el formulario de login o registro. Llama st.stop() si no auth."""
    _init_state()

    if esta_logueado():
        return

    st.markdown(
        '<div style="background:linear-gradient(135deg,#eff6ff,#dbeafe);'
        'border:1px solid #93c5fd;border-radius:12px;padding:20px;'
        'margin:8px 0 16px;">'
        '<div style="font-size:24px;margin-bottom:8px;">👤 Acceso a la Mesa Experta</div>'
        '<div style="color:#1e3a8a;font-size:13px;line-height:1.5;">'
        'Regístrese con su email para identificar sus consultas y poder '
        'analizar la calidad del servicio. Su email no se comparte ni se usa '
        'para enviar comunicaciones.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    tab_login, tab_reg = st.tabs(["🔑 Iniciar sesión", "🆕 Registrarse"])

    # ---- LOGIN ----
    with tab_login:
        with st.form("form_login", clear_on_submit=False):
            email_in = st.text_input(
                "Email",
                placeholder="usuario@empresa.com",
                key="login_email",
            )
            submitted = st.form_submit_button(
                "Iniciar sesión", type="primary", use_container_width=True
            )
            if submitted:
                if not _email_valido(email_in):
                    st.error("Por favor ingrese un email válido.")
                else:
                    try:
                        r = httpx.post(
                            f"{api_base}/v1/users/login",
                            json={"email": email_in.strip()},
                            timeout=8,
                        )
                        if r.status_code == 200:
                            data = r.json()
                            st.session_state.user = data["user"]
                            # Compat con código existente que usa user_alias
                            st.session_state.user_alias = data["user"]["email"]
                            st.session_state.session_started_at = datetime.now()
                            st.session_state.last_activity_at = datetime.now()
                            st.session_state.queries_this_session = 0
                            st.session_state.historial_chat = []
                            st.session_state.memoria_disponible = None
                            st.toast(f"Bienvenido/a {data['user']['name']}", icon="👋")
                            st.rerun()
                        elif r.status_code == 404:
                            st.warning(
                                "Email no registrado. Use la pestaña **Registrarse**."
                            )
                        else:
                            st.error(f"Error: {r.text}")
                    except Exception as e:  # noqa: BLE001
                        st.error(f"No se pudo conectar al servidor: {e}")

    # ---- REGISTRO ----
    with tab_reg:
        with st.form("form_register", clear_on_submit=False):
            col1, col2 = st.columns(2)
            with col1:
                email_in = st.text_input(
                    "Email *",
                    placeholder="usuario@empresa.com",
                    key="reg_email",
                )
                name_in = st.text_input(
                    "Nombre y apellido *",
                    placeholder="ej. Juan Pérez",
                    key="reg_name",
                )
            with col2:
                org_in = st.text_input(
                    "Organización (opcional)",
                    placeholder="ej. Banco XYZ",
                    key="reg_org",
                )
                role_in = st.selectbox(
                    "Rol (opcional)",
                    [
                        "",
                        "Compliance / Cumplimiento",
                        "Auditoría",
                        "Riesgos",
                        "Contabilidad",
                        "Legal",
                        "Operaciones",
                        "Tecnología",
                        "Académico / Investigación",
                        "Otro",
                    ],
                    key="reg_role",
                )

            submitted = st.form_submit_button(
                "Crear cuenta y comenzar",
                type="primary",
                use_container_width=True,
            )
            if submitted:
                if not _email_valido(email_in):
                    st.error("Por favor ingrese un email válido.")
                elif not (name_in or "").strip():
                    st.error("Por favor ingrese su nombre.")
                else:
                    try:
                        r = httpx.post(
                            f"{api_base}/v1/users/register",
                            json={
                                "email": email_in.strip(),
                                "name": name_in.strip(),
                                "organization": (org_in or "").strip() or None,
                                "role": role_in or None,
                            },
                            timeout=8,
                        )
                        if r.status_code == 200:
                            data = r.json()
                            st.session_state.user = data["user"]
                            # Compat con código existente que usa user_alias
                            st.session_state.user_alias = data["user"]["email"]
                            st.session_state.session_started_at = datetime.now()
                            st.session_state.last_activity_at = datetime.now()
                            st.session_state.queries_this_session = 0
                            st.session_state.historial_chat = []
                            st.session_state.memoria_disponible = None
                            st.toast("Cuenta creada ✓", icon="✅")
                            st.rerun()
                        elif r.status_code == 409:
                            st.warning(
                                "Este email ya está registrado. Use la pestaña "
                                "**Iniciar sesión**."
                            )
                        else:
                            try:
                                detail = r.json().get("detail", r.text)
                            except Exception:  # noqa: BLE001
                                detail = r.text
                            st.error(f"Error: {detail}")
                    except Exception as e:  # noqa: BLE001
                        st.error(f"No se pudo conectar al servidor: {e}")

    st.caption(
        "🔒 Política: el email se usa solo para identificar consultas y métricas "
        "de calidad. La sesión se cierra automáticamente tras "
        f"**{INACTIVITY_LIMIT_SEC // 60} min** de inactividad."
    )
    st.stop()


# -----------------------------------------------------------------------------
# Encuesta de salida
# -----------------------------------------------------------------------------

def _stars_widget(label: str, key: str) -> int | None:
    """Renderiza selector de estrellas 1-5. Retorna None si el usuario no eligió."""
    val = st.radio(
        label,
        options=[1, 2, 3, 4, 5],
        format_func=lambda n: "★" * n + "☆" * (5 - n),
        index=None,
        horizontal=True,
        key=key,
    )
    return val


def render_survey(api_base: str) -> None:
    """Renderiza el modal de encuesta y al enviarla cierra la sesión."""
    if not st.session_state.get("show_survey"):
        return
    if st.session_state.get("survey_submitted"):
        # Ya envió → cerrar sesión limpia
        _logout_final()
        return

    closed_reason = st.session_state.get("survey_closed_reason", "manual")

    st.markdown(
        '<div style="background:linear-gradient(135deg,#fef3c7,#fde68a);'
        'border:1px solid #f59e0b;border-radius:12px;padding:20px;'
        'margin:8px 0 16px;">'
        '<div style="font-size:22px;margin-bottom:4px;">📝 Encuesta de salida</div>'
        '<div style="color:#78350f;font-size:13px;line-height:1.5;">'
        + (
            "Su sesión cerró por <b>inactividad de "
            f"{INACTIVITY_LIMIT_SEC // 60} minutos</b>. "
            if closed_reason == "timeout"
            else "Antes de cerrar, ayúdenos a mejorar la herramienta. "
        )
        + "Toma menos de un minuto."
        '</div></div>',
        unsafe_allow_html=True,
    )

    with st.form("form_survey"):
        st.markdown("### Calificación general")
        rating_overall = _stars_widget(
            "¿Qué tan satisfecho/a quedaste con la herramienta?",
            key="srv_overall",
        )

        col1, col2 = st.columns(2)
        with col1:
            rating_accuracy = _stars_widget(
                "Precisión / calidad de las respuestas",
                key="srv_accuracy",
            )
            rating_ux = _stars_widget(
                "Facilidad de uso de la interfaz",
                key="srv_ux",
            )
        with col2:
            rating_speed = _stars_widget(
                "Velocidad de las respuestas",
                key="srv_speed",
            )
            would_rec = st.radio(
                "¿Recomendarías esta herramienta a un/a colega?",
                options=["si", "tal_vez", "no"],
                format_func=lambda v: {"si": "✅ Sí", "tal_vez": "🤔 Tal vez", "no": "❌ No"}[v],
                index=None,
                key="srv_rec",
            )

        st.markdown("### Tu experiencia")
        use_case = st.text_input(
            "¿Para qué la usaste hoy? (opcional)",
            placeholder="ej. Buscar criterios de provisiones procíclicas",
            key="srv_usecase",
        )
        favorite = st.text_input(
            "¿Qué fue lo más útil? (opcional)",
            placeholder="ej. Las citas con páginas exactas",
            key="srv_fav",
        )
        missing = st.text_input(
            "¿Qué le faltó o qué mejorarías? (opcional)",
            placeholder="ej. Más fuentes del MEF, o mejor manejo de tablas",
            key="srv_miss",
        )
        comments = st.text_area(
            "Comentarios adicionales (opcional)",
            placeholder="Cualquier feedback es bienvenido.",
            key="srv_comments",
            height=80,
        )

        col_send, col_skip = st.columns([2, 1])
        with col_send:
            submitted = st.form_submit_button(
                "📤 Enviar y cerrar sesión",
                type="primary",
                use_container_width=True,
            )
        with col_skip:
            skipped = st.form_submit_button(
                "Omitir",
                use_container_width=True,
            )

    if submitted or skipped:
        if submitted:
            # Calcular métricas automáticas
            started = st.session_state.get("session_started_at")
            dur_min = (
                int((datetime.now() - started).total_seconds() / 60) if started else None
            )
            payload = {
                "user_id": user_id(),
                "email": user_email(),
                "rating_overall": rating_overall,
                "rating_accuracy": rating_accuracy,
                "rating_speed": rating_speed,
                "rating_ux": rating_ux,
                "use_case": use_case or None,
                "would_recommend": would_rec,
                "favorite_feature": favorite or None,
                "missing_feature": missing or None,
                "comments": comments or None,
                "session_duration_min": dur_min,
                "n_queries_session": st.session_state.get("queries_this_session", 0),
                "closed_reason": closed_reason,
            }
            try:
                r = httpx.post(
                    f"{api_base}/v1/users/survey",
                    json=payload,
                    timeout=8,
                )
                if r.status_code == 200:
                    st.success("¡Gracias por tu feedback! 🙌")
                else:
                    st.warning("Tu feedback no pudo guardarse, pero igual cerramos la sesión.")
            except Exception:  # noqa: BLE001
                st.warning("Tu feedback no pudo guardarse, pero igual cerramos la sesión.")

        st.session_state.survey_submitted = True
        _logout_final()
        st.rerun()

    st.stop()


def _logout_final() -> None:
    """Limpia el estado de sesión tras enviar/saltar la encuesta."""
    for k in [
        "user",
        "user_alias",
        "session_started_at",
        "last_activity_at",
        "queries_this_session",
        "show_survey",
        "survey_submitted",
        "historial_chat",
        "memoria_disponible",
        "memoria_decidida",
        "consulta_pendiente",
        "plan_pendiente",
        "pregunta_pendiente_acronimo",
        "acronimo_resuelto",
    ]:
        if k in st.session_state:
            st.session_state[k] = (
                None if k in ("user", "user_alias", "session_started_at",
                              "last_activity_at") else
                [] if k == "historial_chat" else
                False if k in ("show_survey", "survey_submitted",
                               "memoria_decidida", "acronimo_resuelto") else
                0 if k == "queries_this_session" else None
            )
