---
title: RAG SBS — Asesor Regulatorio
description: Sistema RAG sobre normativa de la SBS Perú
---

# RAG SBS — Mesa Experta Regulatoria

> Sistema **RAG agéntico** sobre normativa de la **Superintendencia de Banca, Seguros y AFP del Perú** (SBS) y el **Banco Central de Reserva** (BCRP). Responde consultas técnicas con cálculos deterministas, citación de fuente oficial verificable y un grafo navegable de citaciones entre resoluciones.

---

## El problema

Los asesores financieros, oficiales de cumplimiento y profesionales del sistema bancario peruano deben mantenerse actualizados sobre **cientos de resoluciones SBS**, sus modificatorias y la regulación complementaria del BCRP. Tradicionalmente esto se resuelve con:

- Búsqueda manual en PDFs oficiales (lento, propenso a citar normas derogadas).
- Consulta a chatbots genéricos (ChatGPT, Gemini directo): **alucinan porcentajes y categorías** porque no consultan la fuente real.

Demostración concreta del problema con un LLM crudo:

| Pregunta | Respuesta Gemini 3 4B (sin RAG) | Realidad (Res. SBS 11356-2008) |
|---|---|---|
| Tasa de provisión hipotecario CPP | "0.63%" | **2.50% con garantía preferida / 5.00% sin garantía** |
| Categorías SBS | "Buena (G), Media (E), Deficiente (D)" | **Normal, CPP, Deficiente, Dudoso, Pérdida** |
| Hipotecario 100 días atraso | "Calificación deficiente" sin contexto | Verificado: **Deficiente** (rango 61-120 días, Cap. II num. 4.3) |

## La solución

Pipeline completo de RAG que **siempre cita la fuente oficial** y para cálculos numéricos invoca **funciones deterministas** (no inferencia LLM):

```
Pregunta del usuario
  ↓
Query rewriter (resuelve anáforas con historial)
  ↓
Embedding + Hybrid Search (vector + BM25 + RRF)
  ↓
Graph-augmented retrieval (citaciones L1 + tópicos L2)
  ↓
Topic router (filtra Provisiones vs Patrimonio Efectivo vs PLAFT...)
  ↓
LLM reranker (cross-encoder o LLM)
  ↓
Function calling — clasificar_deudor, calcular_provision
  ↓
Generación con cita explícita [Cálculo N] + [Fuente N]
  ↓
Respuesta verificable
```

## Características destacadas

- **Cita textual** del PDF oficial en cada respuesta (snippet visible inline).
- **Cálculos deterministas** (no LLM) para clasificación y provisiones — los números nunca se alucinan.
- **Knowledge Graph navegable**: 317+ nodos, 1969+ aristas de citación entre resoluciones, modificatorias y derogaciones.
- **Tópicos auto-descubiertos** (K-means + naming por LLM) — visualiza qué clusters semánticos tiene el corpus.
- **Re-ingesta automática** vía scheduler con detección de cambios (ETag + hash).
- **Streaming SSE** de respuestas + tarjetas didácticas con desglose paso a paso.
- **Validación contra fuente oficial**: las tablas de clasificación se validaron extrayendo el texto literal del PDF de SBS Perú vigente al 2026-05.

## Casos de uso demostrables

### 1. Cálculo de provisión hipotecaria

> *"Hipotecario S/ 200,000, atraso 100 días, garantía S/ 180,000. ¿Qué hago?"*

→ Sistema dispara 2 cálculos deterministas:
- `clasificar_deudor(hipotecario, 100d) → Deficiente` (cita Cap. II num. 4.3)
- `calcular_provision(200k, Deficiente, preferida, 180k) → S/ 38,750` (Cap. III + Anexo II)

Card UI muestra: tabla de origen, fórmula aritmética paso a paso, narrativa didáctica.

### 2. Conceptual con ejemplo demo

> *"¿Cuál es el % de provisión genérica y específica hipotecario? Muéstrame un ejemplo sencillo."*

→ Detecta "ejemplo sencillo", inyecta valores demo automáticamente (saldo 100k, dos categorías Normal+Deficiente), dispara 4 cálculos y responde con tabla por categoría + fuente.

### 3. Consulta sobre tasas de interés (cross-regulación)

> *"En mi empresa de crédito uso tasa moratoria de 13%, ¿puedo subirla a 15%?"*

→ Recupera Res. SBS 8181-2012 (Reglamento de Transparencia) + Circular BCRP 0008-2021 (tasa máxima). Cita textualmente: "tasa moratoria máxima = 15% adicional sobre la compensatoria".

## Stack técnico

| Capa | Tecnología |
|---|---|
| Backend API | FastAPI + Python 3.11 |
| UI | Streamlit (paleta SBS) |
| LLM | Gemini 2.5 Flash (Google AI Studio) — Ollama fallback |
| Embeddings | `gemini-embedding-001` (768d) |
| Vector store | PostgreSQL + pgvector |
| Knowledge Graph | PostgreSQL nativo + extracción L1 (regex) + L2 (K-means) |
| Cache semántico | Redis |
| Container | Docker / Podman |
| Deploy | AWS Lightsail (fase 1) → GCP Cloud Run (fase 2) |
| Reverse proxy | Caddy con HTTPS automático |

## Validación regulatoria

Las tablas oficiales que el sistema usa para cálculos deterministas **fueron validadas contra el PDF en línea de la SBS Perú** (`intranet2.sbs.gob.pe/dv_int_cn/1097/v6.0/`). Se descartaron resoluciones que tienen el mismo número pero versión obsoleta. Se verificaron las modificatorias relevantes:

- ✓ Res. SBS 11356-2008 (vigente)
- ✓ Res. SBS 2368-2023 (modifica num. 2.2 corporativo)
- ✓ Res. SBS 4345-2023 (definiciones Cap. I, no toca rangos)
- ✓ Res. SBS 975-2025 (definiciones, no toca rangos)

Conclusión: **ningún cambio normativo posterior altera los rangos de días por categoría**.

## Páginas de documentación

- [Arquitectura](architecture.md) — diagramas y componentes
- [Casos de uso](casos-de-uso.md) — queries demostrables con resultado esperado
- [Fuentes regulatorias](regulatorio.md) — corpus SBS + BCRP indexado
- [Roadmap](roadmap.md) — fases del producto

## Código fuente

Disponible en [github.com/{{ site.github.owner_name }}/rag-sbs](https://github.com/ecus/rag-sbs).
