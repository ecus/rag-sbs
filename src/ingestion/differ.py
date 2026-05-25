"""Detección de cambios y clasificación de eventos.

L1 del problema: ¿este contenido es nuevo, igual o cambió?
L2: si cambió, ¿es modificatorio, derogatorio o solo edición menor?

La clasificación L2 (modificatorio/derogatorio) usa regex sobre el título y
las primeras 1000 chars del texto. Sprint 2 evolución: LLM classifier de
fallback cuando regex no es concluyente (RF-012).
"""

from __future__ import annotations

import hashlib
import re
from typing import Final, Literal

# Patrones canónicos en sumarios de resoluciones SBS
RX_DEROGATORIO: Final = re.compile(
    r"\b(derog[aáú](?:n|cion|toria)|d[eé]jase\s+sin\s+efecto|abrog[aá])\b",
    re.IGNORECASE,
)
RX_MODIFICATORIO: Final = re.compile(
    r"\b(modif[ií](?:ca|caci[oó]n|catoria)|sustit[uú](?:ye|cion|tase|y[oóe])|"
    r"incorpor[aá](?:n|se|ci[oó]n)|adici[oó]n[a]?se|incl[uú][yi][aae]se)\b",
    re.IGNORECASE,
)


def hash_bytes(data: bytes) -> str:
    """SHA-256 hex de bytes crudos (binarios o utf-8)."""
    return hashlib.sha256(data).hexdigest()


def has_changed(prev_hash: str | None, new_hash: str) -> bool:
    """True si el contenido es distinto del último indexado."""
    return prev_hash != new_hash


ChangeKind = Literal["new", "modified", "derogatorio"]


def classify_change(
    *,
    is_new: bool,
    title: str,
    text_head: str,
) -> ChangeKind:
    """Clasifica el evento de cambio.

    Args:
        is_new: True si es la primera versión que vemos.
        title: título del documento.
        text_head: primeras ~1000-2000 chars del texto extraído.
    """
    texto_a_escanear = f"{title}\n{text_head}"

    if is_new:
        # Aun siendo "nuevo" para nosotros, puede ser una norma derogatoria
        # publicada hoy. Detectamos de todos modos.
        if RX_DEROGATORIO.search(texto_a_escanear):
            return "derogatorio"
        return "new"

    # Versión que ya conocíamos pero cambió
    if RX_DEROGATORIO.search(texto_a_escanear):
        return "derogatorio"
    if RX_MODIFICATORIO.search(texto_a_escanear):
        return "modified"
    return "modified"  # default conservador
