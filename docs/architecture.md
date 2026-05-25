---
title: Arquitectura
---

# Arquitectura

## Diagrama de componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                         Cliente (Browser)                        │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTPS (Caddy + Let's Encrypt)
                         │
        ┌────────────────┴─────────────────┐
        │                                  │
   ┌────▼───────┐                  ┌──────▼──────┐
   │  Streamlit │                  │   FastAPI   │
   │     UI     │ ◄──── API ────►  │   /v1/*     │
   │   :8501    │                  │    :8000    │
   └────────────┘                  └──┬──────┬───┘
                                      │      │
                          ┌───────────┘      └────────────┐
                          │                               │
                  ┌───────▼──────┐               ┌────────▼──────┐
                  │   PostgreSQL │               │     Redis     │
                  │  + pgvector  │               │ (sem. cache)  │
                  │   :5432      │               │    :6379      │
                  └──────────────┘               └───────────────┘
                          ▲
                          │
                  ┌───────┴───────┐
                  │ Object Store  │
                  │ S3 / GCS /    │
                  │   local       │
                  └───────────────┘
```

## Pipeline de query

1. **Query rewriter** (LLM corto) — convierte una consulta dependiente del historial en una standalone.
   *Ejemplo*: "¿y para consumo?" → "¿cuál es el % de provisión para consumo no revolvente?"

2. **Embedding** del query con `gemini-embedding-001` (768d).

3. **Hybrid search** en pgvector:
   - Búsqueda vectorial (cosine similarity)
   - BM25 textual
   - Fusión con **Reciprocal Rank Fusion** (k=60)

4. **Graph-augmented retrieval** (opcional, feature flag):
   - Expande los chunks iniciales siguiendo aristas del grafo (citaciones a otras resoluciones).
   - Aporta contexto cruzado (ej. consultar provisiones trae automáticamente el chunk de la modificatoria 2368-2023).

5. **Topic router** determinista:
   - Detecta keywords del query → clasifica en `{provisiones, patrimonio_efectivo, tasas_intereses, plaft, ciberseguridad...}`.
   - Filtra chunks que pertenecen al tema opuesto (ej. removeve chunks de Patrimonio Efectivo si la query es sobre provisiones).
   - **Re-fetch dirigido**: si el filtro removió todo, consulta directamente la DB filtrando por title.

6. **LLM reranker** — el LLM puntúa los chunks en una sola llamada y mantiene los top-N.

7. **Calculator agent** (function calling):
   - Detecta si la query requiere cálculo (clasificación, provisión).
   - Si pide "ejemplo sencillo" sin datos, inyecta valores demo.
   - Ejecuta funciones Python deterministas (NO inferencia LLM): `clasificar_deudor()`, `calcular_provision()`.

8. **Generación final** con SYSTEM_PROMPT estricto:
   - Cita explícita `[Cálculo N]` para números y `[Fuente N]` para citaciones textuales.
   - Reglas anti-mezcla de regulaciones.
   - Si el contexto no es suficiente: "No tengo evidencia suficiente para responder con certeza."

## Knowledge Graph

### Nivel 1 — Citaciones explícitas (L1)

Extracción por regex de patrones como:
- `Res. SBS N° XXX-YYYY`
- `Ley XXXXX, Art. N`
- `Anexo N de la Resolución...`
- `Circular BCRP N°...`

Generan nodos (`document`, `resolution`, `ley`, `articulo`, `anexo`, `circular`) y aristas (`cites`, `modifies`, `derogates`, `canonical_form`).

Estado actual: **317 nodos, 1969 aristas, 47 modificatorias detectadas**.

### Nivel 2 — Tópicos semánticos (L2)

K-means sobre embeddings de chunks + naming con LLM:

| # | Tópico | Miembros |
|---|---|---|
| 0 | Supervisión regulatoria | 205 |
| 1 | Prevención lavado fondos | 98 |
| 2 | Reglamento Auditoría Interna | 130 |
| 3 | Riesgo crediticio evaluación | 192 |
| 4 | Riesgo crediticio | 100 |
| 5 | Métodos IRB crediticio | 94 |
| 6 | Vigencia normativa | 105 |
| 7 | Fiduciario y regulación | 39 |

## Parser de PDFs

PyMuPDF como parser principal con fallback a pypdf. Bug crítico resuelto: pypdf perdía las tablas de la Res. 11356-2008 — solo extraía ~10 chunks de un PDF de 47 páginas. PyMuPDF preserva la estructura → **67 chunks bien formados**.

Chunker estructural detecta jerarquía SBS (Capítulo > Sección > Artículo > Anexo) y crea metadata `section_path`. Si la cobertura estructural cae bajo 60% del texto, fallback automático a chunker recursivo.

## Validación de fuentes

Pipeline determinista de auditoría:
1. Descarga el PDF vigente del portal SBS.
2. Extrae con PyMuPDF.
3. Compara contra las tablas hardcoded en el código (`src/tools/clasificacion.py`).
4. Reporta cualquier discrepancia.

Esto previene el anti-patrón clásico: "trustear una imagen sin validar contra fuente oficial".
