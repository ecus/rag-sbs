"""Extracción de citas explícitas con regex.

Patrones canónicos en normativa SBS Perú:
- "Res. SBS Nº 11356-2008" / "Resolución S.B.S. N° 1802-2014" / "Resolución 504-2021"
- "Ley N° 28591" / "Ley Nº 26702"
- "Circular G-139" / "Circular B-2199-2010"
- "Artículo 6" / "Art. 12"
- "Anexo II" / "Anexo 1"

La extracción produce **menciones**: tuplas (kind, label, span) donde:
  kind  = 'resolution' | 'ley' | 'circular' | 'articulo' | 'anexo'
  label = forma canónica del nodo (ej. "Res-SBS-11356-2008")
  span  = (start, end) en el texto original (para evidencia visual futura)

Las menciones luego se materializan como nodos + aristas en el repositorio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

EntityKind = Literal["resolution", "ley", "circular", "articulo", "anexo"]


@dataclass(frozen=True)
class Mention:
    """Mención detectada de una entidad citada."""

    kind: EntityKind
    label: str        # forma canónica para deduplicar
    raw: str          # texto original tal cual aparece
    start: int
    end: int


# --- Patrones ---------------------------------------------------------------
# Resolución SBS:
#   "Res. SBS Nº 11356-2008", "Resolución SBS N° 504-2021",
#   "Resolución S.B.S. Nº 11356 - 2008", "Resolución S.B.S. N° 0011356-2008"
RX_RESOLUCION: Final = re.compile(
    r"""
    \b
    (?:Res(?:olución)?\.?\s+)              # Res / Resolución
    (?:S\.?B\.?S\.?\s+)?                    # SBS opcional
    N[°ºo]?\s*                              # N° / Nº / N
    0*(\d{1,6})\s*[-—–]\s*(\d{4})           # 11356-2008 (con leading zeros opcionales)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Ley:
#   "Ley N° 28591", "Ley Nº 26702", "la Ley 29733"
RX_LEY: Final = re.compile(
    r"\b[Ll]ey\s+(?:N[°ºo]?\.?\s*)?(\d{4,6})\b",
)

# Circular SBS:
#   "Circular G-139", "Circular B-2199-2010", "Circular Nº SBS-G-184"
RX_CIRCULAR: Final = re.compile(
    r"\b[Cc]ircular\s+(?:N[°ºo]?\s*)?([A-Z]{1,3}[-\s]\d{1,4}(?:[-\s]\d{4})?)\b",
)

# Artículo:
#   "Artículo 6", "Art. 12", "artículo 5°"
RX_ARTICULO: Final = re.compile(
    r"\b[Aa]rt(?:[íi]culo|\.)\s+(\d{1,4})(?:[°º])?\b",
)

# Anexo:
#   "Anexo II", "Anexo 1", "ANEXO N° 3"
RX_ANEXO: Final = re.compile(
    r"\b[Aa]nexo\s+(?:N[°ºo]?\s*)?([IVX]{1,5}|\d{1,3})\b",
)


def _label_resolucion(numero: str, anio: str) -> str:
    """Canoniza: '11356', '2008' → 'Res-SBS-11356-2008'."""
    return f"Res-SBS-{int(numero)}-{anio}"


def _label_ley(numero: str) -> str:
    return f"Ley-{int(numero)}"


def _label_circular(codigo: str) -> str:
    norm = re.sub(r"\s+", "-", codigo.strip()).upper()
    return f"Circular-{norm}"


def _label_articulo(numero: str) -> str:
    return f"Articulo-{int(numero)}"


def _label_articulo_calificado(numero: str, norma_padre: str) -> str:
    """Artículo calificado con su norma padre: 'Ley-26702' + '52' → 'Ley-26702 · Art. 52'.

    Un número de artículo suelto ("Articulo-52") no identifica la norma: el art. 52
    de la Ley 26702 y el art. 52 de otro reglamento son cosas distintas y no deben
    colapsar en el mismo nodo. Calificarlo con la norma padre elimina esos falsos
    puentes entre documentos que citan "artículo 52" de normas diferentes.
    """
    return f"{norma_padre} · Art. {int(numero)}"


# Conector norma-padre tras un artículo: "…artículo 52[°] de la Ley N° 26702".
# Captura el "de la / del / de" que precede a la norma.
RX_CONECTOR_PADRE: Final = re.compile(
    r"^\s*[°º]?\s*,?\s*(?:de\s+la|del|de)\s+",
    re.IGNORECASE,
)
# Norma padre "propia" del documento: "de la presente Ley/Resolución/Reglamento…".
RX_PADRE_PROPIO: Final = re.compile(
    r"^(?:la\s+|el\s+)?(?:present[ae]|mism[ao]|citad[ao]|referid[ao]|indicad[ao]|"
    r"acotad[ao]|antes\s+mencionad[ao])\s+"
    r"(?:[Ll]ey|[Rr]esoluci[oó]n|[Cc]ircular|[Rr]eglamento|norma)\b",
    re.IGNORECASE,
)
RX_PADRE_LEY: Final = re.compile(r"^[Ll]ey\s+(?:N[°ºo]?\.?\s*)?(\d{4,6})\b")


def _detectar_norma_padre(cola: str, self_label: str | None) -> str | None:
    """Dado el texto inmediatamente posterior a un 'artículo N', devuelve la
    etiqueta canónica de la norma que lo contiene, o None si no es explícita.

    Casos soportados (los dominantes en normativa peruana):
      - "… de la Ley N° 26702"           → 'Ley-26702'
      - "… de la Resolución SBS N° 504-2021" → 'Res-SBS-504-2021'
      - "… de la Circular G-139"          → 'Circular-G-139'
      - "… de la presente Ley/Resolución" → self_label (la propia norma del doc)
    Las referencias implícitas sin norma nombrada ("el artículo anterior") quedan
    sin calificar a propósito (no se puede saber la norma con regex).
    """
    m = RX_CONECTOR_PADRE.match(cola)
    if not m:
        return None
    resto = cola[m.end():]
    if RX_PADRE_PROPIO.match(resto):
        return self_label
    ml = RX_PADRE_LEY.match(resto)
    if ml:
        return _label_ley(ml.group(1))
    mr = RX_RESOLUCION.match(resto)
    if mr:
        return _label_resolucion(mr.group(1), mr.group(2))
    mc = RX_CIRCULAR.match(resto)
    if mc:
        return _label_circular(mc.group(1))
    return None


def _label_anexo(numero: str) -> str:
    return f"Anexo-{numero.upper()}"


def extraer_menciones(texto: str, self_label: str | None = None) -> list[Mention]:
    """Aplica todos los patrones y retorna lista de menciones únicas por (kind, label).

    Mantenemos múltiples menciones del mismo (kind,label) si están en spans distintos
    — cada una es evidencia adicional de la cita. La deduplicación a nivel de nodo
    la hace el repositorio.

    `self_label` (opcional) = etiqueta canónica de la norma que ES este documento
    (p.ej. 'Res-SBS-504-2021'). Se usa para calificar referencias del tipo
    "artículo N de la presente Resolución" con la norma propia del documento.
    """
    menciones: list[Mention] = []

    for match in RX_RESOLUCION.finditer(texto):
        numero, anio = match.group(1), match.group(2)
        menciones.append(
            Mention(
                kind="resolution",
                label=_label_resolucion(numero, anio),
                raw=match.group(0),
                start=match.start(),
                end=match.end(),
            )
        )

    for match in RX_LEY.finditer(texto):
        menciones.append(
            Mention(
                kind="ley",
                label=_label_ley(match.group(1)),
                raw=match.group(0),
                start=match.start(),
                end=match.end(),
            )
        )

    for match in RX_CIRCULAR.finditer(texto):
        menciones.append(
            Mention(
                kind="circular",
                label=_label_circular(match.group(1)),
                raw=match.group(0),
                start=match.start(),
                end=match.end(),
            )
        )

    for match in RX_ARTICULO.finditer(texto):
        numero = match.group(1)
        # Mirar el texto inmediatamente posterior para calificar el artículo con
        # su norma padre ("… de la Ley 26702"). Si no hay norma explícita, queda
        # como artículo suelto (que la UI trata como atributo, no como puente).
        cola = texto[match.end() : match.end() + 90]
        norma_padre = _detectar_norma_padre(cola, self_label)
        etiqueta = (
            _label_articulo_calificado(numero, norma_padre)
            if norma_padre
            else _label_articulo(numero)
        )
        menciones.append(
            Mention(
                kind="articulo",
                label=etiqueta,
                raw=match.group(0),
                start=match.start(),
                end=match.end(),
            )
        )

    for match in RX_ANEXO.finditer(texto):
        menciones.append(
            Mention(
                kind="anexo",
                label=_label_anexo(match.group(1)),
                raw=match.group(0),
                start=match.start(),
                end=match.end(),
            )
        )

    return menciones


def deduplicar_por_etiqueta(menciones: list[Mention]) -> list[Mention]:
    """Retorna primera mención por (kind, label). Útil para nodos únicos."""
    vistos: set[tuple[str, str]] = set()
    unicos: list[Mention] = []
    for m in menciones:
        clave = (m.kind, m.label)
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(m)
    return unicos
