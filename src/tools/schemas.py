"""Pydantic schemas para las herramientas de cálculo regulatorio."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CategoriaDeudor = Literal["Normal", "CPP", "Deficiente", "Dudoso", "Pérdida"]
TipoCredito = Literal[
    "corporativo", "gran_empresa", "mediana_empresa", "pequena_empresa",
    "microempresa", "consumo_revolvente", "consumo_no_revolvente", "hipotecario",
]
TipoGarantia = Literal[
    "ninguna",
    "preferida",            # hipoteca, prendaria, fianza solidaria
    "preferida_autoliquidable",  # depósitos efectivo SBS, etc.
    "preferida_muy_rapida",      # joyas, oro
]


class ClasificacionInput(BaseModel):
    """Input para clasificar_deudor."""

    tipo_credito: TipoCredito
    dias_atraso: int = Field(..., ge=0)


class ClasificacionOutput(BaseModel):
    """Output de clasificar_deudor."""

    categoria: CategoriaDeudor
    rango_dias: str             # ej. "0-8 días"
    fuente_normativa: str
    descripcion: str


class ProvisionInput(BaseModel):
    """Input para calcular_provision."""

    saldo: float = Field(..., gt=0, description="Saldo de la deuda directa en moneda")
    clasificacion: CategoriaDeudor
    tipo_garantia: TipoGarantia = "ninguna"
    valor_garantia: float = Field(default=0.0, ge=0)


class ProvisionOutput(BaseModel):
    """Output detallado del cálculo de provisión."""

    monto_provision: float
    tasa_aplicada: float           # 0..1
    saldo_no_cubierto: float       # saldo - valor_garantia (ajustada por descuentos)
    saldo_cubierto: float          # parte que la garantía cubre
    tasa_provision_generica: float = 0.0
    monto_provision_generica: float = 0.0
    fuente_normativa: str
    desglose: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Cronograma de amortización
# ---------------------------------------------------------------------------

TipoTasa = Literal["TEA", "TEM", "TED"]
MetodoAmortizacion = Literal["frances", "aleman"]


class ReprogramacionInput(BaseModel):
    """Postergación de una cuota por N días."""

    cuota_numero: int = Field(..., ge=1, description="Nº de cuota que se reprograma")
    dias_extra: int = Field(..., ge=1, le=365, description="Días de postergación")


class CronogramaInput(BaseModel):
    """Input para generar_cronograma."""

    monto: float = Field(..., gt=0, description="Capital del crédito")
    tasa: float = Field(..., gt=0, description="Valor de la tasa (0.38 o 38)")
    tipo_tasa: TipoTasa = "TEA"
    plazo_meses: int = Field(..., ge=1, le=600)
    metodo: MetodoAmortizacion = "frances"
    reprogramacion: ReprogramacionInput | None = None


class CuotaCronograma(BaseModel):
    """Una fila del cronograma."""

    cuota: int
    dias: int
    saldo_inicial: float
    interes: float
    amortizacion: float
    cuota_total: float
    saldo_final: float


class CronogramaOutput(BaseModel):
    """Output de generar_cronograma."""

    tasa_mensual_efectiva: float       # %
    tasa_diaria_efectiva: float        # %
    cuota_fija: float
    cronograma: list[CuotaCronograma]
    total_intereses: float
    total_pagado: float
    interes_adicional_reprogramacion: float = 0.0
    fuente_normativa: str
    nota_reprogramacion: str | None = None


class CalculoResult(BaseModel):
    """Resultado genérico devuelto por el calculator agent."""

    tool: str                  # 'clasificar_deudor' | 'calcular_provision' | 'cronograma_amortizacion'
    inputs: dict
    output: dict
    fuente_normativa: str
    error: str | None = None
