"""Agente calculador — detecta si la query pide cálculos y los ejecuta.

Patrón function-calling sin SDK exclusivo:
  1. LLM emite plan estructurado JSON: ¿qué herramienta(s) llamar, con qué args?
  2. Validamos el JSON contra los schemas (Pydantic).
  3. Ejecutamos las funciones deterministas.
  4. Retornamos los resultados al pipeline RAG para que la respuesta los cite.

Las herramientas disponibles:
  - clasificar_deudor(tipo_credito, dias_atraso)
  - calcular_provision(saldo, clasificacion, tipo_garantia?, valor_garantia?)

Si el LLM no detecta intent de cálculo o falla parseando, retornamos lista
vacía — el flujo RAG continúa normal.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError

from src.llm.base import LLMProvider
from src.tools import (
    CalculoResult,
    ClasificacionInput,
    CronogramaInput,
    ProvisionInput,
    calcular_provision,
    clasificar_deudor,
    generar_cronograma,
)

logger = logging.getLogger(__name__)


PROMPT_PLANIFICADOR_CALCULO = """\
Eres un detector de intenciones de cálculo regulatorio para banca peruana.

Te paso una consulta del usuario. Determina si requiere CÁLCULO determinista
(no solo explicación) sobre:
  A) Clasificación de un deudor según días de atraso
  B) Cálculo de provisión de un crédito
  C) Cronograma de amortización de un crédito (cuotas, intereses, plazo),
     incluyendo reprogramaciones (postergar una cuota N días)

Si NO hay cálculo pedido (solo explicación general), retorna `{"calls": []}`.

Si SÍ hay cálculo, retorna una lista de llamadas con el formato:

{
  "calls": [
    {
      "tool": "clasificar_deudor",
      "args": {
        "tipo_credito": "consumo_no_revolvente",
        "dias_atraso": 45
      }
    },
    {
      "tool": "calcular_provision",
      "args": {
        "saldo": 50000,
        "clasificacion": "Deficiente",
        "tipo_garantia": "ninguna",
        "valor_garantia": 0
      }
    }
  ]
}

VALORES ACEPTADOS:
  tipo_credito: corporativo, gran_empresa, mediana_empresa, pequena_empresa,
                microempresa, consumo_revolvente, consumo_no_revolvente, hipotecario
  clasificacion: Normal, CPP, Deficiente, Dudoso, Pérdida
  tipo_garantia: ninguna, preferida, preferida_muy_rapida, preferida_autoliquidable
  tipo_tasa (cronograma): TEA (anual, default), TEM (mensual), TED (diaria)
  metodo (cronograma): frances (cuota fija, default), aleman (amort. constante)

HERRAMIENTA cronograma_amortizacion — args:
  monto (capital), tasa (ej 0.38 o 38), tipo_tasa, plazo_meses, metodo,
  reprogramacion: {"cuota_numero": N, "dias_extra": D}  (opcional)

REGLAS:
- Solo llama clasificar_deudor si el usuario menciona días de atraso explícitos.
- Solo llama calcular_provision si el usuario menciona un saldo Y una categoría
  (o si la clasificación se puede inferir del paso anterior).
- Llama cronograma_amortizacion cuando el usuario pida un cronograma, tabla de
  cuotas, plan de pagos o amortización CON monto, tasa y plazo. Si pide además
  simular una reprogramación/postergación, agrega el bloque reprogramacion.
  Si pide el cronograma normal Y el reprogramado, emite DOS llamadas.
- Si faltan datos numéricos para hacer el cálculo, retorna {"calls": []} y la
  capa RAG explicará el concepto sin números.
- Output SOLO JSON, sin texto adicional, sin markdown.

EJEMPLOS:

Q: "Tengo un cliente con 45 días de atraso en un crédito de consumo. ¿Cuál es su categoría?"
→ {"calls":[{"tool":"clasificar_deudor","args":{"tipo_credito":"consumo_no_revolvente","dias_atraso":45}}]}

Q: "Calcula la provisión para un crédito Deficiente de S/50,000 sin garantía"
→ {"calls":[{"tool":"calcular_provision","args":{"saldo":50000,"clasificacion":"Deficiente","tipo_garantia":"ninguna","valor_garantia":0}}]}

Q: "Tengo un hipotecario con 100 días de atraso y saldo 200000 con garantía inmobiliaria de 180000. Provisión?"
→ {"calls":[
    {"tool":"clasificar_deudor","args":{"tipo_credito":"hipotecario","dias_atraso":100}},
    {"tool":"calcular_provision","args":{"saldo":200000,"clasificacion":"Deficiente","tipo_garantia":"preferida","valor_garantia":180000}}
  ]}

Q: "Explícame el sistema de provisiones procíclicas"
→ {"calls":[]}

Q: "¿Qué establece la SBS sobre titularización?"
→ {"calls":[]}

Q: "dame un cronograma de un crédito de consumo de 1000 soles con 38% de tasa a 12 meses"
→ {"calls":[{"tool":"cronograma_amortizacion","args":{"monto":1000,"tasa":0.38,"tipo_tasa":"TEA","plazo_meses":12,"metodo":"frances"}}]}

Q: "cronograma de S/1000 al 38% a 12 meses, y otro simulando que en la 3ra cuota se reprograma 15 días"
→ {"calls":[
    {"tool":"cronograma_amortizacion","args":{"monto":1000,"tasa":0.38,"tipo_tasa":"TEA","plazo_meses":12,"metodo":"frances"}},
    {"tool":"cronograma_amortizacion","args":{"monto":1000,"tasa":0.38,"tipo_tasa":"TEA","plazo_meses":12,"metodo":"frances","reprogramacion":{"cuota_numero":3,"dias_extra":15}}}
  ]}

CASOS ESPECIALES — "ejemplo" / "ejemplo sencillo" / "muéstrame un ejemplo":
Si el usuario pide explícitamente un "ejemplo" o "ejemplo sencillo" SIN dar
números concretos, INVENTA valores razonables de demostración y dispara las
tools. Inputs sugeridos según contexto:

  - "ejemplo de provisión genérica + específica para hipotecario":
    {"calls":[
      {"tool":"clasificar_deudor","args":{"tipo_credito":"hipotecario","dias_atraso":0}},
      {"tool":"calcular_provision","args":{"saldo":100000,"clasificacion":"Normal","tipo_garantia":"preferida","valor_garantia":120000}},
      {"tool":"clasificar_deudor","args":{"tipo_credito":"hipotecario","dias_atraso":75}},
      {"tool":"calcular_provision","args":{"saldo":100000,"clasificacion":"Deficiente","tipo_garantia":"preferida","valor_garantia":120000}}
    ]}

  - "ejemplo de provisión para consumo":
    {"calls":[
      {"tool":"clasificar_deudor","args":{"tipo_credito":"consumo_no_revolvente","dias_atraso":45}},
      {"tool":"calcular_provision","args":{"saldo":50000,"clasificacion":"Deficiente","tipo_garantia":"ninguna","valor_garantia":0}}
    ]}

Q: "para un crédito hipotecario, cuál es el % de provisión genérica y específica, muéstrame un ejemplo sencillo"
→ {"calls":[
    {"tool":"clasificar_deudor","args":{"tipo_credito":"hipotecario","dias_atraso":0}},
    {"tool":"calcular_provision","args":{"saldo":100000,"clasificacion":"Normal","tipo_garantia":"preferida","valor_garantia":120000}},
    {"tool":"clasificar_deudor","args":{"tipo_credito":"hipotecario","dias_atraso":75}},
    {"tool":"calcular_provision","args":{"saldo":100000,"clasificacion":"Deficiente","tipo_garantia":"preferida","valor_garantia":120000}}
  ]}

CONSULTA: {consulta}

JSON:"""


def _extraer_json(texto: str) -> dict | None:
    """Extrae JSON del output, tolerando ruido y code fences (Gemini)."""
    texto = texto.strip()
    # Limpieza de markdown fences ```json ... ```
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*", "", texto)
        texto = re.sub(r"\s*```\s*$", "", texto)
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", texto)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _ejecutar_llamada(call: dict) -> CalculoResult:
    """Ejecuta UNA llamada a herramienta y retorna su resultado."""
    tool = call.get("tool", "")
    args = call.get("args", {}) or {}

    try:
        if tool == "clasificar_deudor":
            inp = ClasificacionInput(**args)
            out = clasificar_deudor(inp)
            return CalculoResult(
                tool=tool,
                inputs=inp.model_dump(),
                output=out.model_dump(),
                fuente_normativa=out.fuente_normativa,
            )
        if tool == "calcular_provision":
            inp = ProvisionInput(**args)
            out = calcular_provision(inp)
            return CalculoResult(
                tool=tool,
                inputs=inp.model_dump(),
                output=out.model_dump(),
                fuente_normativa=out.fuente_normativa,
            )
        if tool == "cronograma_amortizacion":
            inp = CronogramaInput(**args)
            out = generar_cronograma(inp)
            return CalculoResult(
                tool=tool,
                inputs=inp.model_dump(),
                output=out.model_dump(),
                fuente_normativa=out.fuente_normativa,
            )
    except ValidationError as exc:
        return CalculoResult(
            tool=tool, inputs=args, output={}, fuente_normativa="",
            error=f"Validación: {exc}",
        )
    except Exception as exc:  # noqa: BLE001
        return CalculoResult(
            tool=tool, inputs=args, output={}, fuente_normativa="",
            error=f"Ejecución: {exc}",
        )
    return CalculoResult(
        tool=tool, inputs=args, output={}, fuente_normativa="",
        error=f"Herramienta desconocida: {tool}",
    )


async def detectar_y_calcular(query: str, llm: LLMProvider) -> list[CalculoResult]:
    """Pipeline completo: detect → extract → execute. Retorna lista de resultados.

    Devuelve [] si:
      - El LLM no detecta intent de cálculo
      - El LLM no produce JSON parseable (fallback seguro)
    """
    if not query or not query.strip():
        return []

    prompt = PROMPT_PLANIFICADOR_CALCULO.replace("{consulta}", query.strip())
    try:
        resultado = await llm.generate(
            prompt, system=None, temperature=0.0, max_tokens=512
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Calculator agent LLM falló: %s", exc)
        return []

    data = _extraer_json(resultado.text)
    if not data or "calls" not in data:
        return []

    calls = data.get("calls") or []
    if not isinstance(calls, list):
        return []

    resultados: list[CalculoResult] = []
    for call in calls[:5]:  # cap defensivo
        if not isinstance(call, dict):
            continue
        resultados.append(_ejecutar_llamada(call))

    if resultados:
        logger.info(
            "Calculator agent: %d cálculo(s) ejecutado(s)",
            sum(1 for r in resultados if not r.error),
        )
    return resultados


def detectar_dependencias(calculos: list[CalculoResult]) -> dict[int, list[str]]:
    """Detecta cuando un cálculo posterior usa el output de uno anterior.

    Heurística: si un input del cálculo i coincide en valor con un output clave
    de un cálculo anterior j (i > j), entonces i depende de j por ese campo.

    Retorna mapping {indice_calculo: [textos_dependencia, ...]}.
    Indices son 1-based para alinearse con la numeración visible al usuario.
    """
    dependencias: dict[int, list[str]] = {}
    # Campos de output de cada tool que son "exportables" hacia inputs siguientes
    campos_output_clave = {
        "clasificar_deudor": ["categoria"],
        "calcular_provision": ["monto_provision"],
    }
    # Campos de input que típicamente reciben outputs de otra herramienta
    campos_input_que_reciben = {
        "calcular_provision": {"clasificacion": "categoria"},
    }

    for i, c_i in enumerate(calculos, 1):
        if c_i.error or c_i.tool not in campos_input_que_reciben:
            continue
        mapeo = campos_input_que_reciben[c_i.tool]
        for input_clave, output_clave in mapeo.items():
            valor_input = c_i.inputs.get(input_clave)
            if valor_input is None:
                continue
            # Busca en cálculos anteriores un output con ese valor
            for j, c_j in enumerate(calculos[:i - 1], 1):
                if c_j.error:
                    continue
                if c_j.tool not in campos_output_clave:
                    continue
                if output_clave not in campos_output_clave[c_j.tool]:
                    continue
                valor_output = c_j.output.get(output_clave)
                if valor_output is not None and valor_output == valor_input:
                    dependencias.setdefault(i, []).append(
                        f"{input_clave}='{valor_input}' derivado del Cálculo {j} ({c_j.tool})"
                    )
                    break
    return dependencias


def _formatear_cronograma(output: dict) -> str:
    """Renderiza el cronograma como tabla de texto para el prompt del LLM."""
    filas = output.get("cronograma", []) or []
    lineas = [
        f"  TEM={output.get('tasa_mensual_efectiva')}%  "
        f"TED={output.get('tasa_diaria_efectiva')}%  "
        f"Cuota fija=S/{output.get('cuota_fija')}",
        "  Cuota | Días | Saldo ini | Interés | Amortiz. | Cuota | Saldo fin",
    ]
    for f in filas:
        lineas.append(
            f"  {f['cuota']:>5} | {f['dias']:>4} | {f['saldo_inicial']:>9.2f} | "
            f"{f['interes']:>7.2f} | {f['amortizacion']:>8.2f} | "
            f"{f['cuota_total']:>7.2f} | {f['saldo_final']:>9.2f}"
        )
    lineas.append(
        f"  Total intereses=S/{output.get('total_intereses')}  "
        f"Total pagado=S/{output.get('total_pagado')}"
    )
    if output.get("interes_adicional_reprogramacion"):
        lineas.append(
            f"  Interés adicional por reprogramación: "
            f"S/{output['interes_adicional_reprogramacion']}"
        )
    if output.get("nota_reprogramacion"):
        lineas.append(f"  Nota: {output['nota_reprogramacion']}")
    return "\n".join(lineas)


def formatear_calculos_para_prompt(calculos: list[CalculoResult]) -> str:
    """Renderiza los cálculos como bloque para incluir en el user prompt.

    Incluye explícitamente las dependencias entre cálculos para que el LLM
    pueda narrar la cadena de inferencia.
    """
    if not calculos:
        return ""

    deps = detectar_dependencias(calculos)

    lineas = ["\n=== CÁLCULOS DETERMINISTAS VERIFICADOS ==="]
    lineas.append(
        "Estos números fueron calculados por código aplicando las reglas "
        "exactas de la normativa SBS. NO los modifiques. Cítalos en tu respuesta "
        "indicando [Cálculo N] y la fuente normativa."
    )
    lineas.append(
        "IMPORTANTE: si dos cálculos están encadenados (uno usa el output del "
        "otro), NÁRRALO EXPLÍCITAMENTE en tu respuesta. Ej: 'Como el Cálculo 1 "
        "determinó que la categoría es X, el Cálculo 2 aplica X para...'."
    )
    for i, c in enumerate(calculos, 1):
        if c.error:
            lineas.append(f"\n[Cálculo {i}] herramienta: {c.tool}  — ERROR: {c.error}")
            continue
        lineas.append(f"\n[Cálculo {i}] {c.tool}")
        lineas.append(f"  Fuente: {c.fuente_normativa}")
        lineas.append(f"  Inputs: {c.inputs}")
        if c.tool == "cronograma_amortizacion":
            lineas.append(_formatear_cronograma(c.output))
        else:
            lineas.append(f"  Output: {c.output}")
        if i in deps:
            for texto_dep in deps[i]:
                lineas.append(f"  ⛓ DEPENDENCIA: {texto_dep}")
    lineas.append("=== FIN CÁLCULOS ===\n")
    return "\n".join(lineas)
