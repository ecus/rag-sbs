"""Diccionario y detector de acrónimos financieros peruanos ambiguos.

Cuando un usuario menciona un acrónimo sin contexto, el sistema puede
sufrir errores de interpretación. Este módulo provee:

1. Diccionario de acrónimos comunes con sus significados.
2. Función ``detectar(query)`` que devuelve los acrónimos ambiguos y
   sus posibles significados para que la UI pida desambiguación.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SignificadoAcronimo:
    sigla: str
    significado: str
    contexto: str  # tema regulatorio donde aplica
    norma_principal: str = ""


# Acrónimos peruano-financieros con múltiples significados conocidos.
# Si solo tiene 1 significado, NO se agrega aquí (no hay ambigüedad).
ACRONIMOS_AMBIGUOS: dict[str, list[SignificadoAcronimo]] = {
    "RCD": [
        SignificadoAcronimo(
            "RCD", "Reporte Crediticio de Deudores",
            "Reporte regulatorio mensual de cartera por deudor",
            "Res SBS 11356-2008 Anexo 6 / Manual Contabilidad",
        ),
        SignificadoAcronimo(
            "RCD", "Riesgo Cambiario Crediticio",
            "Gestión de riesgo cambiario en cartera",
            "Res SBS 774-2025",
        ),
        SignificadoAcronimo(
            "RCD", "Reglamento de Conducta de Mercado",
            "Reglas de transparencia y conducta con usuarios",
            "Res SBS 3274-2017",
        ),
    ],
    "PDD": [
        SignificadoAcronimo(
            "PDD", "Probabilidad de Default (Probability of Default)",
            "Métrica de riesgo de crédito (modelo IRB Basilea)",
            "Res SBS 14354-2009 / Basilea II-III",
        ),
        SignificadoAcronimo(
            "PDD", "Plan de Desarrollo Distrital",
            "Planificación municipal (no financiero)",
            "MEF / municipalidades",
        ),
    ],
    "RPC": [
        SignificadoAcronimo(
            "RPC", "Requerimiento de Patrimonio por Riesgo de Crédito",
            "Capital regulatorio por exposiciones crediticias",
            "Res SBS 14354-2009",
        ),
        SignificadoAcronimo(
            "RPC", "Registro Público del Mercado de Valores",
            "Registro SMV de emisiones públicas",
            "Ley Mercado de Valores DL 861",
        ),
    ],
    "SAR": [
        SignificadoAcronimo(
            "SAR", "Suspicious Activity Report",
            "Reporte de operación sospechosa (LAFT)",
            "Res SBS 2660-2015 / 789-2018",
        ),
    ],
    "GIR": [
        SignificadoAcronimo(
            "GIR", "Gestión Integral de Riesgos",
            "Marco corporativo de riesgos",
            "Res SBS 272-2017 / 37-2008",
        ),
    ],
    "ROS": [
        SignificadoAcronimo(
            "ROS", "Reporte de Operación Sospechosa",
            "LAFT — alertas a UIF",
            "Res SBS 2660-2015 Cap IV",
        ),
    ],
    "ROF": [
        SignificadoAcronimo(
            "ROF", "Reglamento de Organización y Funciones",
            "Estructura interna de la institución (gobierno)",
            "Aplicable a SBS, SMV, MEF",
        ),
    ],
    "TUO": [
        SignificadoAcronimo(
            "TUO", "Texto Único Ordenado",
            "Consolidación legal de una norma con sus modificatorias",
            "Aplicable a leyes y decretos varios",
        ),
    ],
    "LBTR": [
        SignificadoAcronimo(
            "LBTR", "Liquidación Bruta en Tiempo Real",
            "Sistema de pagos de alto valor del BCRP",
            "Circular BCRP 0029-2021",
        ),
    ],
    "ETF": [
        SignificadoAcronimo(
            "ETF", "Exchange Traded Fund (Fondo cotizado)",
            "Vehículo de inversión bursátil",
            "Reglamento SMV de fondos",
        ),
    ],
    "APP": [
        SignificadoAcronimo(
            "APP", "Asociación Público-Privada",
            "Modalidad de inversión MEF / PROINVERSIÓN",
            "DL 1362 / Reglamento MEF",
        ),
        SignificadoAcronimo(
            "APP", "Aplicación móvil (App)",
            "Software para dispositivos móviles (TI/ciberseguridad)",
            "Res SBS 504-2021 Ciberseguridad",
        ),
    ],
    "NIIF": [
        SignificadoAcronimo(
            "NIIF", "Normas Internacionales de Información Financiera",
            "Marco contable internacional",
            "Consejo Normativo de Contabilidad MEF",
        ),
    ],
}


# Patrón para detectar acrónimos en la query.
# Match: 2-5 letras mayúsculas (con o sin contexto numérico),
# aisladas por espacios/puntuación.
_PATRON_ACRONIMO = re.compile(r"\b([A-ZÁÉÍÓÚ]{2,5})\b")


def _esta_explicado(query: str, sigla: str) -> bool:
    """Detecta si la sigla aparece explicada en el mismo query.

    Ej. 'RCD (Reporte Crediticio de Deudores)' → explicado.
    Ej. 'Reporte Crediticio de Deudores (RCD)' → explicado.
    """
    q_lower = query.lower()
    sig_lower = sigla.lower()

    # Buscar el patrón "SIGLA (...)" o "(...SIGLA)"
    patron_inline = re.compile(
        rf"\b{sig_lower}\s*\([^)]+\)|\([^)]*{sig_lower}[^)]*\)",
        re.IGNORECASE,
    )
    if patron_inline.search(query):
        return True

    # Si en el query aparecen palabras clave de algún significado, lo
    # consideramos explicado (uso contextual claro).
    significados = ACRONIMOS_AMBIGUOS.get(sigla, [])
    for s in significados:
        # Tomamos las 2 palabras significativas del significado
        palabras = [
            w.lower() for w in re.findall(r"\b\w{4,}\b", s.significado)
            if w.lower() not in ("para", "como", "este", "esta", "para")
        ]
        if not palabras:
            continue
        # Si AL MENOS UNA palabra clave del significado aparece en el query,
        # se considera explicado por contexto.
        if any(p in q_lower for p in palabras[:3]):
            return True

    return False


def detectar(query: str) -> list[dict]:
    """Detecta acrónimos ambiguos en la query.

    Returns:
        Lista de dicts con `sigla`, `opciones` (lista de SignificadoAcronimo
        como dict). Vacía si no hay ambigüedad detectable.
    """
    if not query or len(query) < 3:
        return []

    siglas_encontradas: set[str] = set()
    for m in _PATRON_ACRONIMO.finditer(query):
        sigla = m.group(1).upper()
        if sigla in ACRONIMOS_AMBIGUOS:
            siglas_encontradas.add(sigla)

    resultado = []
    for sigla in siglas_encontradas:
        opciones = ACRONIMOS_AMBIGUOS[sigla]
        # Si solo hay un significado y NO está explicado, igual lo mostramos
        # como info contextual (no como ambigüedad bloqueante).
        if len(opciones) < 2:
            continue
        if _esta_explicado(query, sigla):
            continue
        resultado.append({
            "sigla": sigla,
            "opciones": [
                {
                    "sigla": op.sigla,
                    "significado": op.significado,
                    "contexto": op.contexto,
                    "norma_principal": op.norma_principal,
                }
                for op in opciones
            ],
        })
    return resultado
