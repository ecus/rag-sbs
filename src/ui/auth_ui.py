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
        "recovery_code_pendiente": None,    # código a mostrar UNA vez
        "conversation_id": None,            # hilo activo
        "conversaciones": None,             # cache de la lista (None = recargar)
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


def _render_codigo_recuperacion() -> None:
    """Muestra el recovery code UNA vez y exige confirmación para seguir."""
    codigo = st.session_state.get("recovery_code_pendiente")
    if not codigo:
        return
    st.markdown(
        '<div style="background:linear-gradient(135deg,#fefce8,#fef9c3);'
        'border:2px solid #eab308;border-radius:12px;padding:20px;margin:12px 0;">'
        '<div style="font-size:20px;font-weight:700;color:#713f12;'
        'margin-bottom:8px;">🔑 Guarde su código de recuperación</div>'
        '<div style="color:#854d0e;font-size:13px;line-height:1.6;">'
        'Si olvida su PIN, este código es la <b>única</b> forma de recuperar '
        'el acceso. Anótelo en un lugar seguro — <b>no volverá a mostrarse</b>.'
        '</div>'
        f'<div style="font-family:monospace;font-size:28px;font-weight:700;'
        f'letter-spacing:3px;color:#1e3a8a;background:#fff;border-radius:8px;'
        f'padding:14px;text-align:center;margin-top:12px;">{codigo}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button("✅ Lo anoté, continuar", type="primary",
                 use_container_width=True, key="ack_recovery"):
        st.session_state.recovery_code_pendiente = None
        st.rerun()
    st.stop()


def render_auth(api_base: str) -> None:
    """Renderiza el formulario de login o registro. Llama st.stop() si no auth."""
    _init_state()

    # Si hay un recovery code pendiente de mostrar, bloquea todo hasta
    # que el usuario confirme que lo guardó (aplica logueado o no).
    _render_codigo_recuperacion()

    if esta_logueado():
        return

    # Diseño de la pantalla de acceso: una sola tarjeta centrada, sobria.
    # (render_auth llama a st.stop() si no hay sesión, así que este CSS no
    # afecta al chat.)
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] { background: #eef2f6; }
        section[data-testid="stMain"] {
            align-items: flex-start !important;
            justify-content: flex-start !important;
        }
        /* Alta especificidad para ganarle al padding-bottom:220px global
           (que existe para el chat input y estiraba la tarjeta de login). */
        html body [data-testid="stApp"] section[data-testid="stMain"]
        div[data-testid="stMainBlockContainer"] {
            max-width: 420px !important;
            margin: 1.5rem auto 1.5rem !important;
            padding: 1.6rem 1.8rem 1.4rem !important;
            padding-bottom: 1.4rem !important;
            background: #ffffff !important;
            border: 1px solid #e5e9f0 !important;
            border-radius: 16px !important;
            box-shadow: 0 10px 34px rgba(15,23,42,0.08) !important;
            height: fit-content !important;
            min-height: 0 !important;
        }
        html body [data-testid="stApp"] section[data-testid="stMain"]
        div[data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"] {
            padding-bottom: 0 !important;
        }
        [data-testid="stForm"] {
            border: none !important; padding: 0 !important; box-shadow: none !important;
        }
        [data-baseweb="tab-list"] {
            justify-content: center; gap: 8px;
            border-bottom: 1px solid #eef1f5 !important; margin-bottom: 4px;
        }
        [data-baseweb="tab"] { font-size: 14px; }
        [data-testid="stExpander"] details {
            border: none !important; box-shadow: none !important; background: transparent !important;
        }
        [data-testid="stExpander"] summary {
            font-size: 12.5px !important; color: #64748b !important; padding: 6px 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div style="text-align:center;margin:0 0 1.4rem;">'
        '<div style="display:inline-flex;align-items:center;justify-content:center;'
        'width:52px;height:52px;background:#0d2b5c;color:#fff;border-radius:12px;'
        'font-weight:700;font-size:16px;letter-spacing:1px;margin-bottom:12px;">SBS</div>'
        '<div style="font-size:20px;font-weight:600;color:#0f172a;line-height:1.2;">'
        'Mesa Experta Regulatoria</div>'
        '<div style="font-size:12.5px;color:#64748b;margin-top:4px;">'
        'Consultas sobre normativa financiera peruana</div>'
        '<div style="font-size:11px;color:#94a3b8;margin-top:2px;">'
        'Herramienta independiente, no oficial</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    tab_login, tab_reg = st.tabs(["Iniciar sesión", "Crear cuenta"])

    # ---- LOGIN ----
    with tab_login:
        with st.form("form_login", clear_on_submit=False):
            email_in = st.text_input(
                "Email",
                placeholder="usuario@empresa.com",
                key="login_email",
            )
            pin_in = st.text_input(
                "PIN (4-8 dígitos)",
                type="password",
                max_chars=8,
                key="login_pin",
            )
            submitted = st.form_submit_button(
                "Iniciar sesión", type="primary", use_container_width=True
            )
            if submitted:
                if not _email_valido(email_in):
                    st.error("Por favor ingrese un email válido.")
                elif not (pin_in or "").strip().isdigit() or not (4 <= len(pin_in.strip()) <= 8):
                    st.error("El PIN debe tener entre 4 y 8 dígitos.")
                else:
                    try:
                        r = httpx.post(
                            f"{api_base}/v1/users/login",
                            json={"email": email_in.strip(), "pin": pin_in.strip()},
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
                            # Memoria viene en el login (autenticada por PIN)
                            st.session_state.memoria_disponible = data.get("memory") or []
                            # Bootstrap (definió PIN ahora): mostrar recovery code
                            rc = data["user"].pop("recovery_code", None)
                            if rc:
                                st.session_state.recovery_code_pendiente = rc
                            st.toast(f"Bienvenido/a {data['user']['name']}", icon="👋")
                            st.rerun()
                        elif r.status_code == 401:
                            st.error("Email o PIN incorrectos.")
                        elif r.status_code == 429:
                            st.warning("Demasiados intentos. Espere un minuto y reintente.")
                        else:
                            st.error(f"Error: {r.text}")
                    except Exception as e:  # noqa: BLE001
                        st.error(f"No se pudo conectar al servidor: {e}")

        with st.expander("¿Olvidaste tu PIN?"):
            st.caption(
                "Use el **código de recuperación** que se le mostró al crear "
                "la cuenta (formato `XXXX-XXXX`). Al usarlo se genera un "
                "código nuevo. Si tampoco tiene el código, contacte al "
                "administrador para resetear su acceso."
            )
            with st.form("form_recover"):
                rec_email = st.text_input("Email", key="rec_email")
                rec_code = st.text_input(
                    "Código de recuperación",
                    placeholder="XXXX-XXXX",
                    max_chars=12,
                    key="rec_code",
                )
                col_rp1, col_rp2 = st.columns(2)
                with col_rp1:
                    rec_pin1 = st.text_input(
                        "Nuevo PIN (4-8 dígitos)", type="password",
                        max_chars=8, key="rec_pin1",
                    )
                with col_rp2:
                    rec_pin2 = st.text_input(
                        "Repetir nuevo PIN", type="password",
                        max_chars=8, key="rec_pin2",
                    )
                rec_ok = st.form_submit_button(
                    "Restablecer PIN", type="primary", use_container_width=True
                )
            if rec_ok:
                if not _email_valido(rec_email):
                    st.error("Ingrese un email válido.")
                elif not (rec_pin1 or "").strip().isdigit() or not (4 <= len(rec_pin1.strip()) <= 8):
                    st.error("El nuevo PIN debe tener entre 4 y 8 dígitos.")
                elif rec_pin1.strip() != (rec_pin2 or "").strip():
                    st.error("Los PIN no coinciden.")
                elif not (rec_code or "").strip():
                    st.error("Ingrese el código de recuperación.")
                else:
                    try:
                        r = httpx.post(
                            f"{api_base}/v1/users/recover",
                            json={
                                "email": rec_email.strip(),
                                "recovery_code": rec_code.strip(),
                                "new_pin": rec_pin1.strip(),
                            },
                            timeout=8,
                        )
                        if r.status_code == 200:
                            st.success(
                                "PIN restablecido ✓ — inicie sesión con su nuevo PIN."
                            )
                            nuevo_rc = r.json().get("recovery_code")
                            if nuevo_rc:
                                st.session_state.recovery_code_pendiente = nuevo_rc
                                st.rerun()
                        elif r.status_code == 401:
                            st.error("Email o código de recuperación incorrectos.")
                        elif r.status_code == 429:
                            st.warning("Demasiados intentos. Espere un minuto.")
                        else:
                            st.error("No se pudo restablecer el PIN. Reintente.")
                    except Exception as e:  # noqa: BLE001
                        st.error(f"No se pudo conectar al servidor: {e}")

    # ---- REGISTRO ----
    with tab_reg:
        with st.form("form_register", clear_on_submit=False):
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
            pin_reg = st.text_input(
                "PIN (4-8 dígitos) *",
                type="password",
                max_chars=8,
                help="Lo usará para iniciar sesión. Solo números.",
                key="reg_pin",
            )
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
                "Crear cuenta y solicitar acceso",
                type="primary",
                use_container_width=True,
            )
            if submitted:
                if not _email_valido(email_in):
                    st.error("Por favor ingrese un email válido.")
                elif not (name_in or "").strip():
                    st.error("Por favor ingrese su nombre.")
                elif not (pin_reg or "").strip().isdigit() or not (4 <= len(pin_reg.strip()) <= 8):
                    st.error("El PIN debe tener entre 4 y 8 dígitos (solo números).")
                else:
                    try:
                        r = httpx.post(
                            f"{api_base}/v1/users/register",
                            json={
                                "email": email_in.strip(),
                                "name": name_in.strip(),
                                "pin": pin_reg.strip(),
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
                            st.session_state.memoria_disponible = []
                            # Mostrar el recovery code una única vez
                            if data.get("recovery_code"):
                                st.session_state.recovery_code_pendiente = data["recovery_code"]
                            st.toast("Solicitud de acceso enviada ✓", icon="📨")
                            st.rerun()
                        elif r.status_code == 409:
                            st.warning(
                                "Este email ya está registrado. Use la pestaña "
                                "**Iniciar sesión**."
                            )
                        elif r.status_code == 429:
                            st.warning("Demasiados intentos. Espere un minuto y reintente.")
                        else:
                            try:
                                detail = r.json().get("detail", r.text)
                            except Exception:  # noqa: BLE001
                                detail = r.text
                            st.error(f"Error: {detail}")
                    except Exception as e:  # noqa: BLE001
                        st.error(f"No se pudo conectar al servidor: {e}")

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    with st.expander("Política de datos y privacidad"):
        st.caption(
            "Su email y sus consultas se usan únicamente para identificarlo y "
            "medir la calidad del servicio. Registramos datos técnicos (IP, "
            "latencia, endpoint) con fines de seguridad y monitoreo. No "
            "compartimos sus datos con fines comerciales ni los usamos para "
            "comunicaciones; para operar el servicio podemos usar proveedores de "
            "infraestructura y monitoreo que procesan datos técnicos con "
            "retención limitada. "
            f"La sesión se cierra tras **{INACTIVITY_LIMIT_SEC // 60} min** de "
            "inactividad. Puede eliminar sus datos cuando quiera (abajo)."
        )

    with st.expander("Eliminar mi cuenta y todos mis datos"):
        st.caption(
            "Borra su usuario, su historial de consultas, sus conversaciones y "
            "su feedback. Las encuestas de satisfacción se conservan "
            "**anonimizadas** (sin email). Los logs técnicos de monitoreo se "
            "eliminan automáticamente al expirar su retención."
        )
        with st.form("form_delete_me"):
            del_email = st.text_input("Email", key="del_email")
            del_pin = st.text_input("PIN", type="password", max_chars=8, key="del_pin")
            del_ok = st.form_submit_button("Eliminar definitivamente", type="secondary")
        if del_ok:
            try:
                r = httpx.post(
                    f"{api_base}/v1/users/me/delete",
                    json={"email": (del_email or "").strip(), "pin": (del_pin or "").strip()},
                    timeout=8,
                )
                if r.status_code == 200:
                    st.success("Sus datos fueron eliminados. Gracias por usar la herramienta.")
                elif r.status_code == 401:
                    st.error("Email o PIN incorrectos.")
                else:
                    st.error("No se pudo completar la eliminación. Reintente más tarde.")
            except Exception as e:  # noqa: BLE001
                st.error(f"No se pudo conectar al servidor: {e}")

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
        "admin_key",
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
        "conversation_id",
        "conversaciones",
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
