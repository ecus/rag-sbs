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


class CalculoResult(BaseModel):
    """Resultado genérico devuelto por el calculator agent."""

    tool: str                  # 'clasificar_deudor' | 'calcular_provision'
    inputs: dict
    output: dict
    fuente_normativa: str
    error: str | None = None
