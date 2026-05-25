"""Cálculo de provisiones por riesgo de crédito.

Fuente principal: Res. SBS Nº 11356-2008 — Capítulo III "Exigencia de Provisiones".
Garantías preferidas y descuentos: Anexo II.

Lógica determinista:
  1. Parte del saldo cubierta por garantía (con descuento del Anexo II)
     usa tasa de "garantía preferida" / "muy rápida realización".
  2. Parte NO cubierta usa tasa específica sin garantía.
  3. Sobre cartera Normal, se aplica además la provisión genérica (1%).

⚠️ Las tasas implementadas corresponden a la tabla canónica de la Res. 11356-2008
en su versión original. Modificatorias posteriores (Res. 14353-2009 sobre
provisiones procíclicas, Res. 2368-2023, etc.) pueden alterar valores.
El sistema cita la fuente y el usuario debe validar.
"""

from __future__ import annotations

from src.tools.schemas import (
    CategoriaDeudor,
    ProvisionInput,
    ProvisionOutput,
    TipoGarantia,
)

# Tabla 1 (sin garantía preferida)
_TASA_SIN_GARANTIA: dict[CategoriaDeudor, float] = {
    "Normal": 0.0,        # cubierta por genérica (1%)
    "CPP": 0.05,
    "Deficiente": 0.25,
    "Dudoso": 0.60,
    "Pérdida": 1.00,
}

# Tabla 2 (garantía preferida — ej. hipotecaria estándar)
_TASA_PREFERIDA: dict[CategoriaDeudor, float] = {
    "Normal": 0.0,
    "CPP": 0.025,
    "Deficiente": 0.125,
    "Dudoso": 0.30,
    "Pérdida": 0.60,
}

# Tabla 3 (garantía preferida de muy rápida realización — joyas, oro)
_TASA_MUY_RAPIDA: dict[CategoriaDeudor, float] = {
    "Normal": 0.0,
    "CPP": 0.0125,
    "Deficiente": 0.0625,
    "Dudoso": 0.15,
    "Pérdida": 0.30,
}

# Tabla 4 (garantía preferida autoliquidable — depósitos efectivo en la misma empresa)
_TASA_AUTOLIQUIDABLE: dict[CategoriaDeudor, float] = {
    "Normal": 0.0,
    "CPP": 0.01,
    "Deficiente": 0.01,
    "Dudoso": 0.01,
    "Pérdida": 0.01,
}

# Tasa de provisión genérica (sobre cartera Normal)
PROVISION_GENERICA_NORMAL = 0.01     # 1% — Res 11356-2008 Cap. III

# Descuentos del Anexo II (haircuts sobre el valor de tasación de la garantía)
_DESCUENTOS_GARANTIA: dict[TipoGarantia, float] = {
    "ninguna": 1.00,                   # no aplica (se ignora valor_garantia)
    "preferida": 0.50,                 # típicamente inmuebles tasación → 50%
    "preferida_muy_rapida": 0.30,      # joyas, oro
    "preferida_autoliquidable": 0.00,  # depósitos efectivo → no se descuenta (vale 100%)
}


def descuento_garantia(tipo: TipoGarantia, valor: float) -> float:
    """Aplica el descuento (haircut) del Anexo II sobre el valor de la garantía.

    El descuento es la PORCIÓN que se RESTA del valor pericial.
    Ej. inmueble tasado en 100 con descuento 50% → valor ajustado = 50.
    """
    if valor <= 0 or tipo == "ninguna":
        return 0.0
    descuento = _DESCUENTOS_GARANTIA.get(tipo, 0.50)
    return round(valor * (1.0 - descuento), 2)


def _tabla_por_garantia(tipo: TipoGarantia) -> dict[CategoriaDeudor, float]:
    """Retorna la tabla de tasas según tipo de garantía."""
    if tipo == "preferida":
        return _TASA_PREFERIDA
    if tipo == "preferida_muy_rapida":
        return _TASA_MUY_RAPIDA
    if tipo == "preferida_autoliquidable":
        return _TASA_AUTOLIQUIDABLE
    return _TASA_SIN_GARANTIA


# ── API pública para introspección desde la UI / agentes ─────────────
# Nombres legibles para mostrar al usuario.
NOMBRES_TABLAS: dict[str, str] = {
    "sin_garantia": "Tabla 1 — Sin garantía preferida",
    "preferida": "Tabla 2 — Garantía preferida",
    "preferida_muy_rapida": "Tabla 3 — Garantía de muy rápida realización",
    "preferida_autoliquidable": "Tabla 4 — Garantía autoliquidable",
}


def obtener_tabla_provision(tipo: TipoGarantia | str) -> tuple[str, str, dict[CategoriaDeudor, float]]:
    """Devuelve ``(clave, nombre_legible, tabla)`` para una garantía dada.

    Usado por la UI para mostrar la tabla regulatoria de la que sale la tasa.
    """
    if tipo == "preferida":
        return "preferida", NOMBRES_TABLAS["preferida"], dict(_TASA_PREFERIDA)
    if tipo == "preferida_muy_rapida":
        return "preferida_muy_rapida", NOMBRES_TABLAS["preferida_muy_rapida"], dict(_TASA_MUY_RAPIDA)
    if tipo == "preferida_autoliquidable":
        return "preferida_autoliquidable", NOMBRES_TABLAS["preferida_autoliquidable"], dict(_TASA_AUTOLIQUIDABLE)
    return "sin_garantia", NOMBRES_TABLAS["sin_garantia"], dict(_TASA_SIN_GARANTIA)


def obtener_descuento_garantia(tipo: TipoGarantia | str) -> float:
    """Devuelve el porcentaje de descuento (haircut) del Anexo II para una garantía.

    Retorna el % a aplicar (ej. 0.50 = 50% se descuenta del valor de tasación).
    """
    return _DESCUENTOS_GARANTIA.get(tipo, 0.50) if tipo != "ninguna" else 0.0


def calcular_provision(inp: ProvisionInput) -> ProvisionOutput:
    """Calcula la provisión específica + genérica de un crédito.

    Lógica (Res. SBS 11356-2008, Cap. III + Anexo II):
      1. Valor cubierto = descuento_garantia(tipo, valor_garantia)
      2. Saldo no cubierto = max(0, saldo - valor_cubierto)
      3. Provisión específica:
         - Parte cubierta × tasa(tabla_garantia, categoria)
         - Parte no cubierta × tasa(sin_garantia, categoria)
      4. Si categoría == Normal: añade genérica 1% sobre saldo total
    """
    # Paso 1: valor ajustado de la garantía
    valor_cubierto = descuento_garantia(inp.tipo_garantia, inp.valor_garantia)
    valor_cubierto = min(valor_cubierto, inp.saldo)
    saldo_no_cubierto = round(inp.saldo - valor_cubierto, 2)

    # Paso 2: tasas según tabla
    tasa_no_cubierto = _TASA_SIN_GARANTIA[inp.clasificacion]
    tasa_cubierto = _tabla_por_garantia(inp.tipo_garantia)[inp.clasificacion]

    # Paso 3: provisión específica (combinada)
    prov_no_cubierto = saldo_no_cubierto * tasa_no_cubierto
    prov_cubierto = valor_cubierto * tasa_cubierto
    prov_especifica = round(prov_no_cubierto + prov_cubierto, 2)

    # Paso 4: provisión genérica solo aplica a Normal
    prov_generica = 0.0
    if inp.clasificacion == "Normal":
        prov_generica = round(inp.saldo * PROVISION_GENERICA_NORMAL, 2)

    # Tasa efectiva combinada (para reporting)
    tasa_efectiva = round(prov_especifica / inp.saldo, 4) if inp.saldo else 0.0

    return ProvisionOutput(
        monto_provision=round(prov_especifica + prov_generica, 2),
        tasa_aplicada=tasa_efectiva,
        saldo_no_cubierto=saldo_no_cubierto,
        saldo_cubierto=valor_cubierto,
        tasa_provision_generica=PROVISION_GENERICA_NORMAL if inp.clasificacion == "Normal" else 0.0,
        monto_provision_generica=prov_generica,
        fuente_normativa="Res. SBS 11356-2008, Cap. III + Anexo II",
        desglose={
            "valor_garantia_original": inp.valor_garantia,
            "descuento_garantia_pct": _DESCUENTOS_GARANTIA.get(inp.tipo_garantia, 0.0),
            "valor_garantia_ajustado": valor_cubierto,
            "saldo_total": inp.saldo,
            "saldo_no_cubierto": saldo_no_cubierto,
            "saldo_cubierto_por_garantia": valor_cubierto,
            "tasa_aplicada_no_cubierto": tasa_no_cubierto,
            "tasa_aplicada_cubierto": tasa_cubierto,
            "provision_no_cubierto": round(prov_no_cubierto, 2),
            "provision_cubierto": round(prov_cubierto, 2),
            "provision_especifica_total": prov_especifica,
            "provision_generica": prov_generica,
            "provision_total": round(prov_especifica + prov_generica, 2),
        },
    )
