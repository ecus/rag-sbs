---
title: Arquitectura
---

# Arquitectura técnica (v0.4 — mayo 2026)

## Diagrama de componentes

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Cliente (Browser)                            │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ HTTPS · Let's Encrypt
                  ┌──────────▼──────────┐
                  │       Caddy         │ (reverse proxy + auto TLS)
                  │       :443          │
                  └──────────┬──────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
       ┌──────▼──────┐               ┌──────▼──────┐
       │  Streamlit  │ ◄── REST ───► │   FastAPI   │
       │      UI     │               │   /v1/*     │
       │    :8501    │               │   :8000     │
       └─────────────┘               └──┬──────┬───┘
                                        │      │
                          ┌─────────────┘      └──────────────┐
                          │                                   │
                  ┌───────▼──────────┐               ┌────────▼──────┐
                  │   PostgreSQL     │               │     Redis     │
                  │   + pgvector     │               │  (sem cache)  │
                  │   :5432          │               │    :6379      │
                  └──┬───────────────┘               └───────────────┘
                     │
                     ├── documents, chunks, embeddings
                     ├── doc_sources, ingestion_runs, change_events
                     ├── graph_nodes, graph_edges
                     ├── pending_sources, cost_tracker, background_config
                     └── user_sessions, query_log
                          ▲
                          │
                  ┌───────┴────────┐
                  │  APScheduler   │ in-process: */10 worker, */15 zombies,
                  │                │ HH:05 graph+topics rebuild
                  └────────────────┘
                          │
                  ┌───────▼────────┐         ┌────────────────┐
                  │   Gemini API   │         │   Object Store │
                  │  (LLM + embed) │         │   S3/GCS/local │
                  └────────────────┘         └────────────────┘
```

## Pipeline de query (v0.4)

### Fase 1 — Preprocesamiento

1. **Recepción**: `POST /v1/query` o `/v1/query/stream`. Incluye `alias`, `history`, `options`.
2. **Query rewriter** (LLM corto): si hay historial conversacional, reescribe la consulta para que sea autocontenida.
   *Ejemplo*: "¿y para consumo?" → "¿cuál es el % de provisión para consumo no revolvente?"
3. **Embedding**: `gemini-embedding-001` (768d).

### Fase 2 — Retrieval híbrido adaptativo

4. **Query profiler** detecta el tipo de consulta:

| Perfil | Patrón detectado | Pesos RRF |
|---|---|---|
| Lexical fuerte | 2+ entidades específicas | w_v=0.6 / w_t=1.4 |
| Lexical simple | 1 entidad (#res, art°, cuenta) | w_v=0.8 / w_t=1.2 |
| Semantic | "¿qué/cómo/por qué?" sin entidad | w_v=1.3 / w_t=0.7 |
| Balanced | sin señal clara | w_v=1.0 / w_t=1.0 |

5. **Hybrid search**:
   - Vectorial: cosine sobre pgvector index ivfflat/hnsw
   - Lexical: BM25 vía PostgreSQL `tsvector` + `ts_rank`
   - **Fusión RRF ponderada**: `score = w_v·1/(k+rank_v) + w_t·1/(k+rank_t)` con k=60

6. **Graph-augmented retrieval** (opcional, flag `expansion_enabled`):
   - Expande chunks iniciales siguiendo aristas del grafo
   - Multi-hop configurable (1 o 2 saltos)
   - Útil para cross-regulación

### Fase 3 — Re-ranking y filtrado

7. **LLM Re-ranker** (default ON):
   - Toma 18 candidatos del hybrid search
   - El LLM les asigna scores 0.0–10.0 con 5 niveles de discriminación
   - Retorna top 7 más relevantes
   - Telemetría: cuenta chunks que cambiaron de orden

8. **Topic router determinista**:
   - Detecta keywords → clasifica en `{provisiones, patrimonio_efectivo, tasas_intereses, plaft, ciberseguridad, ...}`
   - Filtra chunks del tema opuesto (anti-mezcla)
   - **Re-fetch dirigido**: si el filtro deja vacío, consulta directa filtrando por título

### Fase 4 — Cálculo y generación

9. **Calculator agent** (function calling):
   - Detecta intención de cálculo (clasificación de deudor, provisiones)
   - Inyecta valores demo si pide "ejemplo sencillo"
   - Ejecuta funciones Python deterministas: `clasificar_deudor()`, `calcular_provision()`
   - NO usa el LLM para los números

10. **Generación final** con SYSTEM_PROMPT estricto + 3 niveles de evidencia:

| Nivel | Cuándo | Output |
|---|---|---|
| **A** | Contexto totalmente vacío | "No tengo evidencia suficiente para responder con certeza." |
| **B** | Contexto parcial relacionado | Describe lo encontrado + 2-3 preguntas de clarificación |
| **C** | Contexto suficiente | Respuesta directa con `[Fuente N]` y `[Cálculo N]` |

11. **Logging persistente**: query, respuesta, confianza, fuentes top-8, opciones, latencia → `query_log` (si vino con alias).

---

## Ingestion pipeline

### Catálogo curado (manual)
- `seed_catalog.py`: 413 URLs verificadas en 5 rondas (v1-v5)
- POST `/v1/ingest/seed` registra en `doc_sources`
- POST `/v1/ingest/scan` dispara `run_scan(source_filter=...)`

### Worker background (scrapers + queue)
- `pending_sources` table: cola de URLs descubiertas por scrapers
- Cron `*/10`: worker tick procesa N URLs, respeta caps:
  - Cap total: $9.50
  - Cap diario: $1.50
  - Max docs total: 2000
  - Schedule until: 2026-06-01
- Self-apagado si supera cualquier cap

### Parser (cadena de 3 niveles)

```
PyMuPDF → texto extraído?
   ├─ Sí (>50 chars/pág)  → chunker estructural
   ├─ No                   → pypdf fallback
   │                        └─ Sigue vacío?
   │                              ├─ Sí  → OCR Tesseract español (DPI 200, max 30 pág)
   │                              └─ No  → chunker
   └─ Error                → pypdf fallback
```

### Chunker estructural
- Detecta jerarquía: `Capítulo > Sección > Artículo > Anexo`
- Crea metadata `section_path`
- Si cobertura estructural <60% del texto → fallback a chunker recursivo
- Embedding por chunk + almacenamiento en `chunks` con `tsvector` para BM25

### Self-healing
- Cron `*/15`: `UPDATE ingestion_runs SET status='aborted' WHERE status='running' AND started_at < NOW() - INTERVAL '30 minutes'`
- También al startup del API
- Previene acumulación de zombies (visto 321 en un día sin esto)

---

## Knowledge Graph

### Nivel 1 — Citaciones explícitas

Extracción por regex de patrones en chunks:
- `Res. SBS N° XXX-YYYY`
- `Ley XXXXX, Art. N`
- `Anexo N de la Resolución...`
- `Circular BCRP N°...`

Genera:
- **Nodos**: `document`, `resolution`, `ley`, `articulo`, `anexo`, `circular`, `topic`
- **Aristas**: `cites`, `modifies`, `derogates`, `canonical_form`, `topic_member`

### Nivel 2 — Tópicos semánticos

K-means sobre embeddings de chunks (k=15) + naming con LLM. Ejemplos detectados:
- Tasas de interés de referencia
- Prevención lavado activos
- Provisiones de créditos procíclicas
- Operaciones de reporte BCRP
- Gobierno corporativo y compliance
- Auditoría interna
- TI y ciberseguridad
- Riesgo de modelo

### Rebuild
- Cron horario `HH:05`: `reconstruir_completo(pool)` trunca y rearma
- Tras rebuild, automáticamente `descubrir_topicos()` para mantener consistencia

### Visualización
- Endpoint `/v1/graph` retorna HTML interactivo (vis-network desde CDN)
- Parámetros físicos ajustables: espaciado (60-500), repulsión (500-20000), gravedad (0-1)
- Coloreo por institución emisora (SBS azul, BCRP rojo, Congreso morado, MEF verde, etc.)

---

## Capa de analytics y memoria

### Tablas
- `user_sessions`: alias + created_at + last_seen_at
- `query_log`: query, answer, confidence, n_sources, latency_ms, options (JSONB), sources_summary (JSONB)

### Endpoints
- `POST /v1/analytics/session` — registrar alias
- `GET /v1/analytics/users` — top usuarios con métricas
- `GET /v1/analytics/user/{alias}/queries` — historial completo
- `GET /v1/analytics/user/{alias}/memory` — últimas 6 conversaciones (para reconstruir memoria al login)

### Flow
1. Usuario ingresa alias en la app
2. UI recupera memoria histórica → la inyecta en `st.session_state.historial_chat`
3. Cada query incluye el alias en el payload
4. API loguea en `query_log` con todos los metadatos
5. Modo técnico expone dashboard de analytics con drill-down por usuario

---

## Stack containerizado

`docker-compose.prod.yml`:

| Service | Imagen | Volumen | Puerto |
|---|---|---|---|
| `postgres` | pgvector/pgvector:pg16 | pgdata | 5432 |
| `redis` | redis:7-alpine | - | 6379 |
| `api` | local Dockerfile (Python 3.11 + Tesseract) | - | 8000 |
| `ui` | local Dockerfile | - | 8501 |
| `caddy` | caddy:2-alpine | caddy_data | 80, 443 |

Dockerfile multi-stage:
- Stage 1 builder: instala todas las deps en `/opt/venv`
- Stage 2 runtime: copia venv + agrega Tesseract español (~100MB)
- Imagen final ~350MB

---

## Estado actual del corpus (mayo 2026)

| Métrica | Valor |
|---|---|
| Documentos en BD | ~900 |
| Chunks vectorizados | ~29,000 |
| Catálogo curado | 413 URLs verificadas |
| Instituciones | SBS, BCRP, Congreso, MEF, SMV, SUNAT, INDECOPI, BIS, BID |
| Manual de Contabilidad SBS | Cap I-IV (vigencias 2024-2026) + Res 895-98 |
| Knowledge graph | ~1,100 nodos / ~12,000 aristas |
| Tópicos | 15 áreas temáticas |
| Costo acumulado Gemini | ~USD 2.50 |
| Cap restante | USD 7.00 (de USD 9.50) |

---

## Decisiones arquitectónicas registradas (ADRs)

- **ADR-001** — Gemini sobre Ollama: latencia + calidad >> costo en escala portafolio
- **ADR-002** — pgvector sobre Pinecone/Weaviate: simplicidad, una sola BD
- **ADR-003** — APScheduler in-process sobre Celery: stack 5x más simple para 1 worker
- **ADR-004** — RRF ponderado sobre concatenación simple: documentado en literatura
- **ADR-005** — LLM reranker sobre cross-encoder local: evita +3GB de sentence-transformers
- **ADR-006** — Topic router determinista (no agente LLM): zero falsos positivos críticos en separación regulatoria
- **ADR-007** — Caps de costo hard-coded al worker: presupuesto portafolio limitado
- **ADR-008** — Self-healing cron sobre supervisión manual: experiencia: 321 zombies/día sin esto
