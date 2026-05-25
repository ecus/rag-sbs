---
title: Casos de uso
---

# Casos de uso

Queries reales probadas en el sistema. Todas devuelven respuestas verificables contra fuente oficial.

## Caso 1 — Cálculo de provisión hipotecaria con datos concretos

### Pregunta del usuario

> *"Hipotecario S/ 200,000, atraso 100 días, garantía S/ 180,000. ¿Qué hago?"*

### Lo que hace el sistema

1. Calculator agent detecta intent de cálculo, extrae parámetros.
2. Dispara **2 funciones deterministas**:

```python
clasificar_deudor(tipo_credito="hipotecario", dias_atraso=100)
→ {"categoria": "Deficiente", "rango_dias": "61-120 días"}

calcular_provision(
    saldo=200000,
    clasificacion="Deficiente",
    tipo_garantia="preferida",
    valor_garantia=180000
)
→ {
    "monto_provision": 38750.0,
    "saldo_cubierto_por_garantia": 90000,
    "saldo_no_cubierto": 110000,
    "tasa_aplicada_no_cubierto": 0.25,
    "tasa_aplicada_cubierto": 0.125
}
```

3. UI muestra card didáctica con:
   - **Inputs** del problema
   - **Narrativa paso a paso**: "El haircut del 50% deja la garantía en S/ 90,000. Cubre S/ 90k del saldo, restan S/ 110k sin garantía..."
   - **Tabla de origen** colapsable con la tabla regulatoria completa, fila usada resaltada
   - **Desglose aritmético**: `S/ 110,000 × 25% = S/ 27,500`
   - **Resultado**: S/ 38,750 (% provisión efectivo 19.38%)
   - **Fuentes citadas**: Res. SBS 11356-2008 Cap. II num. 4.3 + Cap. III + Anexo II

### Calidad de la respuesta

| | Antes del topic router | Después |
|---|---|---|
| Fuentes citadas | Patrimonio Efectivo, SGSI (irrelevantes) | Res. 11356-2008 ✓ |
| Cálculos disparados | 2 | 2 |
| Cita correcta | ❌ Mezclaba Res. 14354 | ✓ Solo 11356 + 2368 |

---

## Caso 2 — Pregunta conceptual con solicitud de ejemplo

### Pregunta del usuario

> *"Para un crédito hipotecario, ¿cuál es el % de provisión genérica y específica? Muéstrame un ejemplo sencillo."*

### Cómo lo resuelve

El planner detecta la frase **"ejemplo sencillo"** sin valores numéricos en la query → inyecta valores demo automáticamente:

```python
# Escenario A: caso Normal (para mostrar la provisión genérica)
clasificar_deudor("hipotecario", 0)  → Normal
calcular_provision(100000, "Normal", "preferida", 120000)  → S/ 1,000

# Escenario B: caso Deficiente (para mostrar la específica)
clasificar_deudor("hipotecario", 75)  → Deficiente
calcular_provision(100000, "Deficiente", "preferida", 120000)  → S/ 17,500
```

### Respuesta generada

Estructura:
1. **Marco normativo**: Res. SBS 11356-2008 Cap. III + Anexo II
2. **Escenario A — Normal**: saldo 100k, atraso 0 días → provisión **genérica 1%** = S/ 1,000
3. **Escenario B — Deficiente**: mismo saldo, atraso 75 días → **provisión específica** = S/ 17,500
4. **Tabla** por categoría con tasas (5 filas × 2 columnas: sin garantía / con preferida)
5. Citas `[Cálculo N]` y `[Fuente N]` con snippet del PDF oficial.

---

## Caso 3 — Cross-regulación (SBS + BCRP)

### Pregunta del usuario

> *"En mi empresa de crédito uso tasa moratoria de 13%, ¿puedo subirla a 15%?"*

### Cómo lo resuelve

Topic router detecta keyword `tasa moratoria` → activa tema `tasas_intereses`.

Re-fetch dirigido trae chunks de **dos fuentes complementarias**:

1. **Res. SBS 8181-2012** (Reglamento de Transparencia):
   > "las empresas pueden determinar libremente las tasas de interés compensatorio y moratorio para sus operaciones, siempre que estas sean expresadas en forma efectiva anual y consideren la regulación emitida por el Banco Central de Reserva del Perú"

2. **Circular BCRP 0008-2021** (Tasa Máxima de Interés):
   > "la tasa máxima de interés convencional compensatorio es equivalente a 2 veces el promedio de las observaciones... la tasa moratoria máxima es 15% adicional sobre la compensatoria"

### Respuesta generada

El LLM combina ambas fuentes y explica:
- Marco legal de libertad de tasas (Ley 26702 Art. 9 + Res. SBS 8181-2012).
- Tope regulatorio del BCRP (Circular 0008-2021).
- Recomienda consultar la nota informativa BCRP vigente para la tasa máxima del trimestre actual.

---

## Caso 4 — Caso negativo (lo que pasa cuando NO hay evidencia)

### Pregunta del usuario

> *"¿Cuál es el tratamiento contable para criptoactivos en bancos peruanos?"*

### Comportamiento esperado

El corpus indexado no cubre criptoactivos (no hay aún normativa SBS específica). El sistema responde:

> "No tengo evidencia suficiente para responder con certeza."

**No alucina**. Es el comportamiento correcto — la regla está en el SYSTEM_PROMPT:

```
Si el contexto no es suficiente, responde literalmente:
"No tengo evidencia suficiente para responder con certeza."
NUNCA inventes resoluciones, artículos o números.
```

---

## Caso 5 — Detección de mezcla regulatoria

### Pregunta del usuario

> *"¿Qué factor de ponderación aplica a un crédito hipotecario para patrimonio efectivo?"*

### Cómo lo resuelve

Topic router detecta `patrimonio efectivo` → activa tema `patrimonio_efectivo` (no provisiones).

Re-fetch trae **solo chunks de Res. 14354-2009** (Patrimonio Efectivo por Riesgo de Crédito). El SYSTEM_PROMPT prohíbe citar Res. 11356 (provisiones) en este contexto.

Resultado: respuesta sobre factor de ponderación (50%, 75%, 100% según LTV e indicador prudencial), **sin contaminación con conceptos de provisión**.

Este caso valida que el sistema **mantiene separadas las dos regulaciones distintas** que comparten vocabulario superficial ("hipotecario", "%", "saldo").

---

## Stats del corpus

| Métrica | Valor |
|---|---|
| Documentos indexados | 18 |
| Chunks (con PyMuPDF) | ~790 |
| Resoluciones SBS | 14 |
| Documentos BCRP | 4 (Circular 0008-2021 + 3 notas informativas) |
| Nodos del grafo L1 | 317 |
| Aristas del grafo L1 | 1,969 |
| Modificatorias clasificadas | 47 |
| Tópicos L2 (K-means) | 8 |
