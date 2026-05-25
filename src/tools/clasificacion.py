"""Clasificación del deudor según días de atraso.

Fuente: Res. SBS Nº 11356-2008, Reglamento para la Evaluación y Clasificación
del Deudor — específicamente Capítulo II "Categorías de Clasificación Crediticia
del Deudor de la Cartera de Créditos Minoristas".

Para créditos NO minoristas (corporativos, grandes empresas, medianas empresas),
la clasificación es PRINCIPALMENTE cualitativa (capacidad de pago, flujo de
caja, situación financiera). Aquí solo aplicamos la regla de días de atraso
como un APROXIMADO — el resultado debe siempre validarse con análisis cualitativo.
"""

from __future__ import annotations

from src.tools.schemas import (
    CategoriaDeudor,
    ClasificacionInput,
    ClasificacionOutput,
    TipoCredito,
)

# Tabla de clasificación por días de atraso
# Cada entrada: lista de (dia_max, categoria, descripcion)
# El último cubre "más de N días".
# Fuente: Res. SBS 11356-2008, Anexo de Clasificación (tabla canónica SBS).

# MES (Microempresa) / Consumo no revolvente / pequeña-microempresa
_TABLA_MINORISTAS_NO_HIPOTECARIO: list[tuple[int, CategoriaDeudor, str]] = [
    (8, "Normal", "Cumple o atraso hasta 8 días"),
    (30, "CPP", "Atraso entre 9 y 30 días — Con Problemas Potenciales"),
    (60, "Deficiente", "Atraso entre 31 y 60 días"),
    (120, "Dudoso", "Atraso entre 61 y 120 días"),
    (10**9, "Pérdida", "Atraso mayor a 120 días"),
]

# HIPOTECARIO (vivienda)
# Fuente: Res. SBS 11356-2008, Cap. II, numeral 4 (págs. 21-22). Verificado contra
# el PDF oficial — citas literales:
#   4.1 Normal:     "atraso de hasta treinta (30) días calendario"
#   4.2 CPP:        "treinta y uno (31) a sesenta (60) días"
#   4.3 Deficiente: "sesenta y uno (61) a ciento veinte (120) días"
#   4.4 Dudoso:     "ciento veintiuno (121) a trescientos sesenta y cinco (365) días"
#   4.5 Pérdida:    "más de trescientos sesenta y cinco (365) días"
# Res. 2368-2023 NO modifica estos rangos (solo numeral 2.2 corporativo).
_TABLA_HIPOTECARIO: list[tuple[int, CategoriaDeudor, str]] = [
    (30, "Normal", "Cumple o atraso hasta 30 días"),
    (60, "CPP", "Atraso entre 31 y 60 días — Con Problemas Potenciales"),
    (120, "Deficiente", "Atraso entre 61 y 120 días"),
    (365, "Dudoso", "Atraso entre 121 días y 1 año"),
    (10**9, "Pérdida", "Atraso mayor a 1 año"),
]

# COMERCIAL / NO MINORISTA (corporativo, gran empresa, mediana empresa).
# Fuente: Res. SBS 11356-2008, Cap. II, numeral 2 (págs. 19-20). Verificado.
# La norma OFICIAL define la categoría principalmente por criterios CUALITATIVOS
# (situación financiera, flujo de caja, capacidad de pago). Los días de atraso
# son solo UNO de varios criterios (ítem b en cada numeral). Citas literales:
#   2.2 CPP b):        "Dos o más atrasos mayores a 15 días en los últimos 6
#                       meses siempre que no excedan los 60 días"
#   2.3 Deficiente b): "Atrasos mayores a 60 días y que no excedan 120 días"
#   2.4 Dudoso b):     "mayores a 120 días y no excedan 365 días"
#   2.5 Pérdida b):    "mayores a 365 días"
# Este proxy es CONSERVADOR (Normal solo si 0 días) — la categoría real puede
# ser Normal con atrasos cortos si la evaluación cualitativa es sólida.
# DEBE complementarse SIEMPRE con análisis cualitativo del oficial de crédito.
_TABLA_NO_MINORISTAS_PROXY: list[tuple[int, CategoriaDeudor, str]] = [
    (0, "Normal", "Cumple sin atraso (0 días) — sujeto a evaluación cualitativa"),
    (60, "CPP", "Atraso 1-60 días o problemas potenciales detectados"),
    (120, "Deficiente", "Atraso 61-120 días o capacidad de pago debilitada"),
    (365, "Dudoso", "Atraso 121 días - 1 año o capacidad de pago seriamente afectada"),
    (10**9, "Pérdida", "Atraso > 1 año o pérdida prácticamente segura"),
]


def _seleccionar_tabla(tipo_credito: TipoCredito) -> tuple[list, str]:
    """Retorna (tabla, fuente) según tipo de crédito."""
    if tipo_credito == "hipotecario":
        return _TABLA_HIPOTECARIO, "Res. SBS 11356-2008, Cap. II — Cartera Hipotecaria"
    if tipo_credito in ("corporativo", "gran_empresa", "mediana_empresa"):
        return (
            _TABLA_NO_MINORISTAS_PROXY,
            "Res. SBS 11356-2008, Cap. II — No minoristas (proxy cuantitativo; verificar cualitativo)",
        )
    # Minoristas no hipotecarios (pequeña, micro, consumo)
    return _TABLA_MINORISTAS_NO_HIPOTECARIO, "Res. SBS 11356-2008, Cap. II — Cartera Minorista"


def clasificar_deudor(inp: ClasificacionInput) -> ClasificacionOutput:
    """Clasifica un deudor según días de atraso + tipo de crédito.

    Determinista — basado en tablas de Res. SBS 11356-2008.
    """
    tabla, fuente = _seleccionar_tabla(inp.tipo_credito)

    dia_min = 0
    for dia_max, categoria, descripcion in tabla:
        if inp.dias_atraso <= dia_max:
            rango = (
                f"{dia_min}-{dia_max} días" if dia_max < 10**8 else f"más de {dia_min - 1} días"
            )
            return ClasificacionOutput(
                categoria=categoria,
                rango_dias=rango,
                fuente_normativa=fuente,
                descripcion=descripcion,
            )
        dia_min = dia_max + 1

    # Nunca debería llegar aquí, pero por safety
    return ClasificacionOutput(
        categoria="Pérdida",
        rango_dias="indefinido",
        fuente_normativa=fuente,
        descripcion="Días de atraso exceden todos los rangos definidos",
    )
