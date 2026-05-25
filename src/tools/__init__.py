"""Herramientas de cálculo regulatorio determinista (function calling).

Cada función implementa un cálculo NORMATIVO exacto (no LLM estimando).
Fuente: Res. SBS Nº 11356-2008 — Reglamento de Evaluación y Clasificación
del Deudor + Anexos.

Filosofía: el LLM puede explicar y contextualizar, pero los NÚMEROS los
calcula código determinista. Esto elimina alucinaciones numéricas.
"""

from src.tools.clasificacion import clasificar_deudor
from src.tools.provisiones import calcular_provision, descuento_garantia
from src.tools.schemas import (
    CalculoResult,
    ClasificacionInput,
    ClasificacionOutput,
    ProvisionInput,
    ProvisionOutput,
)

__all__ = [
    "clasificar_deudor",
    "calcular_provision",
    "descuento_garantia",
    "CalculoResult",
    "ClasificacionInput",
    "ClasificacionOutput",
    "ProvisionInput",
    "ProvisionOutput",
]
