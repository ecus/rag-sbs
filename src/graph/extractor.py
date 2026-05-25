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


def _label_anexo(numero: str) -> str:
    return f"Anexo-{numero.upper()}"


def extraer_menciones(texto: str) -> list[Mention]:
    """Aplica todos los patrones y retorna lista de menciones únicas por (kind, label).

    Mantenemos múltiples menciones del mismo (kind,label) si están en spans distintos
    — cada una es evidencia adicional de la cita. La deduplicación a nivel de nodo
    la hace el repositorio.
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
        menciones.append(
            Mention(
                kind="articulo",
                label=_label_articulo(match.group(1)),
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
