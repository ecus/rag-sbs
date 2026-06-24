"""Cronograma de amortización determinista (francés / alemán).

Genera la tabla de cuotas de un crédito sin que el LLM invente números.
Soporta reprogramación: postergar una cuota N días, calculando el interés
compensatorio adicional que se devenga sobre el saldo en ese periodo.

Convenciones (estándar Perú):
  - TEA → TEM = (1+TEA)^(1/12) − 1 ; TED = (1+TEA)^(1/360) − 1
  - Meses de 30 días; año de 360 días para la tasa diaria.
  - Método francés: cuota fija. Método alemán: amortización constante.
"""

from __future__ import annotations

from src.tools.schemas import (
    CronogramaInput,
    CronogramaOutput,
    CuotaCronograma,
)


def _tasas_efectivas(tasa: float, tipo_tasa: str) -> tuple[float, float]:
    """Normaliza la tasa y devuelve (TEM, TED) como fracciones."""
    # Normalizar: si viene como 38 en vez de 0.38
    t = tasa / 100.0 if tasa > 1 else tasa
    if tipo_tasa == "TEM":
        tem = t
        tea = (1 + tem) ** 12 - 1
    elif tipo_tasa == "TED":
        ted = t
        tea = (1 + ted) ** 360 - 1
        tem = (1 + tea) ** (1 / 12) - 1
    else:  # TEA (default)
        tea = t
        tem = (1 + tea) ** (1 / 12) - 1
    ted = (1 + tea) ** (1 / 360) - 1
    return tem, ted


def generar_cronograma(inp: CronogramaInput) -> CronogramaOutput:
    """Construye el cronograma de amortización."""
    tem, ted = _tasas_efectivas(inp.tasa, inp.tipo_tasa)
    P = inp.monto
    n = inp.plazo_meses

    # Cuota fija (francés)
    if tem > 0:
        cuota_fija = P * tem / (1 - (1 + tem) ** -n)
    else:
        cuota_fija = P / n

    reprog_cuota = inp.reprogramacion.cuota_numero if inp.reprogramacion else None
    reprog_dias = inp.reprogramacion.dias_extra if inp.reprogramacion else 0

    filas: list[CuotaCronograma] = []
    saldo = P
    total_intereses = 0.0
    extra_reprog = 0.0
    amort_constante = P / n

    for k in range(1, n + 1):
        dias = 30
        # Interés normal del periodo (30 días) sobre el saldo
        interes = saldo * tem

        if inp.metodo == "aleman":
            amort = amort_constante if k < n else saldo
        else:  # frances
            amort = cuota_fija - interes
            if k == n:
                amort = saldo  # ajuste de redondeo en la última

        # Reprogramación: este periodo dura 30 + dias_extra
        if reprog_cuota == k and reprog_dias > 0:
            dias = 30 + reprog_dias
            interes_reprog = saldo * ((1 + ted) ** dias - 1)
            extra_reprog = interes_reprog - interes
            interes = interes_reprog
            # La amortización (reducción de capital) se mantiene; el interés
            # adicional sube la cuota de ese periodo.

        cuota_total = interes + amort
        saldo_fin = saldo - amort
        if abs(saldo_fin) < 0.005:
            saldo_fin = 0.0
        total_intereses += interes

        filas.append(CuotaCronograma(
            cuota=k,
            dias=dias,
            saldo_inicial=round(saldo, 2),
            interes=round(interes, 2),
            amortizacion=round(amort, 2),
            cuota_total=round(cuota_total, 2),
            saldo_final=round(saldo_fin, 2),
        ))
        saldo = saldo_fin

    nota = None
    if reprog_cuota and reprog_dias:
        nota = (
            f"En la cuota {reprog_cuota} se postergó el pago {reprog_dias} días "
            f"(periodo de {30 + reprog_dias} días en vez de 30). El interés "
            f"compensatorio se devenga día a día sobre el saldo de capital, por "
            f"lo que esa cuota acumula S/ {extra_reprog:.2f} de interés adicional. "
            f"Ese excedente eleva la cuota del periodo (o, según la política de la "
            f"entidad, se capitaliza y se redistribuye en el nuevo cronograma)."
        )

    return CronogramaOutput(
        tasa_mensual_efectiva=round(tem * 100, 4),
        tasa_diaria_efectiva=round(ted * 100, 5),
        cuota_fija=round(cuota_fija, 2),
        cronograma=filas,
        total_intereses=round(total_intereses, 2),
        total_pagado=round(P + total_intereses, 2),
        interes_adicional_reprogramacion=round(extra_reprog, 2) if extra_reprog else 0.0,
        fuente_normativa=(
            "Cálculo financiero estándar (método francés/alemán). El tratamiento "
            "contable de la reprogramación sigue el Manual de Contabilidad SBS "
            "(intereses diferidos y provisiones de créditos reprogramados)."
        ),
        nota_reprogramacion=nota,
    )
