# RAG SBS — Mesa Experta Regulatoria

> Sistema **RAG agéntico** sobre normativa financiera peruana (**SBS**, **BCRP**, **Congreso**, **MEF**, **SMV**, **SUNAT**, **INDECOPI**, **BIS/BID**). Respuestas con citación de fuente oficial verificable, cálculos deterministas, grafo navegable de citaciones, retrieval híbrido adaptativo y memoria por usuario.

**🌐 Demo en vivo**: [3.220.87.49.nip.io](https://3.220.87.49.nip.io)
**📖 Documentación**: [eurrutia.github.io/rag-sbs](https://eurrutia.github.io/rag-sbs)

---

## ¿Qué hace?

Responde preguntas técnicas de banca peruana citando la **fuente oficial PDF** y para cálculos numéricos invoca **funciones deterministas** (nunca alucina porcentajes).

### Capacidades clave (v0.4)

| Capacidad | Implementación |
|---|---|
| **Búsqueda híbrida adaptativa** | Vector + BM25 con pesos ajustados según perfil de query (lexical/semantic/balanced) |
| **Re-ranker LLM** | El LLM re-puntúa 18 candidatos y mantiene los 7 más relevantes |
| **OCR fallback** | Tesseract español para PDFs escaneados (auto-detectado por densidad de texto) |
| **Topic router determinista** | Separa Provisiones ↔ Patrimonio Efectivo ↔ LAFT para evitar mezcla |
| **Calculator agent** | Funciones Python deterministas para clasificación/provisiones (cero alucinación numérica) |
| **Graph-augmented retrieval** | Knowledge graph L1 (citas) + L2 (tópicos K-means) navegable |
| **Asistente de consulta** | Wizard que arma queries estructuradas a partir de rol+caso+objetivo |
| **Memoria persistente** | Recupera últimas 6 conversaciones por alias entre sesiones |
| **Analytics por usuario** | Log de consultas con confianza, fuentes, latencia, opciones |
| **Self-healing** | Cron `*/15` limpia runs zombies + cleanup al startup |
| **Caps de costo** | Worker se autoapaga si supera $9.50 total o $1.50/día |

### Ejemplo 1: Caso multidimensional

> **Usuario** (vía wizard): *Compliance officer · Caso: titulización de cartera + fideicomiso · Objetivo: informe regulatorio integral*

El sistema genera un informe estructurado de 7 secciones con citas a:
- Res SBS 1308-2013 (Transferencia de Cartera) — score 0.90
- Res SBS 3780-2011 (Riesgo de Crédito) — score 0.85
- Res SBS 14354-2009 (Patrimonio Efectivo) — score 0.80
- Res SBS 1010-99 (Reglamento Fideicomiso) — score 0.75
- Res SBS 3986-2024 (Cuenta 8406 Cartera Transferida) — score 0.70

### Ejemplo 2: Cálculo determinista

> **Usuario**: "Hipotecario S/ 200,000, atraso 100 días, garantía S/ 180,000. ¿Qué hago?"

Sistema:
1. `clasificar_deudor("hipotecario", 100)` → **Deficiente** (Cap. II num. 4.3)
2. `calcular_provision(200k, "Deficiente", "preferida", 180k)` → **S/ 38,750**
3. UI muestra paso a paso, tabla regulatoria, cita PDF.

### Ejemplo 3: Anti-alucinación

> **Usuario**: "¿Cuál es la tasa de provisión hipotecaria para CPP?"

| Sistema | Respuesta |
|---|---|
| Gemini directo | "0.63%" ❌ inventado |
| **RAG SBS** | "2.50% con garantía preferida / 5.00% sin garantía" ✓ Res. 11356-2008 Cap. III |

---

## Estado del corpus (mayo 2026)

| Métrica | Valor |
|---|---|
| **Documentos indexados** | ~900 PDFs |
| **Chunks vectorizados** | ~29,000 |
| **Instituciones cubiertas** | 9 (SBS, BCRP, Congreso, MEF, SMV, SUNAT, INDECOPI, BIS, BID) |
| **Capítulos del Manual de Contabilidad SBS** | I, II, III, IV completos (vigencias 2024-2026) |
| **Knowledge graph** | ~1,100 nodos / ~12,000 aristas |
| **Tópicos descubiertos** | 15 áreas temáticas (K-means + LLM naming) |

---

## Stack

- **Backend**: FastAPI + Python 3.11
- **UI**: Streamlit (estilo conversacional)
- **LLM**: Gemini 2.5 Flash (Google AI Studio)
- **Embeddings**: `gemini-embedding-001` (768d)
- **Vector store**: PostgreSQL + pgvector
- **Cache semántico**: Redis
- **OCR**: Tesseract español
- **Object storage**: S3 / GCS / local (abstracción cloud-agnóstica)
- **Reverse proxy**: Caddy con HTTPS automático (Let's Encrypt)
- **Containerización**: Docker
- **Scheduling**: APScheduler (cron jobs in-process)

---

## Características técnicas destacadas

### Retrieval
- **Hybrid search adaptativo**: pesos vector vs BM25 ajustados automáticamente por perfil de query
  - Lexical fuerte (2+ entidades): w_vector=0.6, w_texto=1.4
  - Lexical simple: 0.8 / 1.2
  - Semantic: 1.3 / 0.7
  - Balanced: 1.0 / 1.0
- **Reciprocal Rank Fusion** (k=60, ponderado)
- **Re-ranker LLM** con prompt de 5 niveles de discriminación (0-10):
  - 10: respuesta literal
  - 8-9: regla aplicable con entidad clave
  - 5-7: contexto relacionado
  - 2-4: mismo cuerpo, otro capítulo
  - 0-1: ruido
- **Graph-augmented retrieval** opcional (multi-hop)

### Generación
- SYSTEM_PROMPT con 3 niveles de evidencia:
  - **A**: sin info → "no tengo evidencia"
  - **B**: info parcial → describe lo encontrado + formula 2-3 preguntas de clarificación
  - **C**: info suficiente → respuesta con citas
- Español peruano neutro/formal (sin voseo)
- Anti-mezcla regulatoria (provisiones ≠ patrimonio efectivo)

### Ingestion
- **Parser de 3 niveles**: PyMuPDF → pypdf → **OCR Tesseract** si chars_promedio < 50
- **Chunker estructural**: detecta `Capítulo > Sección > Artículo > Anexo`
- **Worker background** con cron `*/10` + caps de costo automáticos
- **Scrapers** SBS / BCRP con verificación HTTP HEAD
- **Catálogo curado** versionado (v1 → v5 = 413 fuentes verificadas)

### Operación
- **Self-healing**: cron `*/15` limpia runs zombies (>30 min sin actualizar)
- **Memoria persistente** por alias de usuario (recupera últimas 6 conversaciones)
- **Query log** con metadata completa para analytics
- **Modo usuario vs modo técnico**: usuario final ve UI limpia, admin ve dashboard

---

## Quickstart desarrollo local

```bash
# 1. Prerrequisitos
brew install docker
docker compose --version

# 2. Configurar
cp .env.example .env
# Editar .env: GOOGLE_API_KEY=tu_api_key

# 3. Levantar stack
docker compose up -d

# 4. Migrar BD (incluye 005_query_log.sql)
docker exec rag-sbs-postgres psql -U rag -d ragdb -f /sql/migrations/001_init.sql
# ... aplicar 002-005

# 5. Seedear catálogo
curl -X POST http://localhost:8000/v1/ingest/seed

# 6. Disparar ingesta
curl -X POST http://localhost:8000/v1/ingest/scan -d '{}' -H 'Content-Type: application/json'

# 7. UI en http://localhost:8501
```

## Quickstart producción

```bash
# AWS Lightsail (Ubuntu 22.04 LTS, 2GB RAM mínimo)
ssh ubuntu@<IP> "bash <(curl -fsSL https://raw.githubusercontent.com/eurrutia/rag-sbs/main/scripts/lightsail/bootstrap.sh)"

# Configurar .env.prod con:
# - GOOGLE_API_KEY
# - POSTGRES_PASSWORD
# - DOMAIN=tu-vm.nip.io

# Lanzar stack productivo
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

---

## Estructura del repo

```
rag-sbs/
├── src/
│   ├── api/
│   │   ├── routes_query.py        ← /v1/query, /v1/query/stream
│   │   ├── routes_ingest.py       ← /v1/ingest/scan, /v1/ingest/seed
│   │   ├── routes_graph.py        ← /v1/graph/*, viz interactiva
│   │   ├── routes_background.py   ← /v1/background/* (worker control)
│   │   ├── routes_analytics.py    ← /v1/analytics/* (queries por usuario)
│   │   └── routes_health.py
│   ├── agents/
│   │   ├── calculator_agent.py    ← function calling
│   │   ├── planner.py             ← decide responder vs clarificar
│   │   ├── topic_router.py        ← separación regulatoria
│   │   └── query_rewriter.py      ← reescritura con historial
│   ├── rag/
│   │   ├── parser.py              ← PyMuPDF + pypdf + OCR Tesseract
│   │   ├── chunker_estructural.py ← detecta jerarquía SBS
│   │   ├── reranker.py            ← dispatcher (llm/cross-encoder/cohere)
│   │   ├── reranker_llm.py        ← re-ranking con prompt de 5 niveles
│   │   └── query_profile.py       ← perfilador para hybrid tuning
│   ├── llm/
│   │   ├── base.py                ← interfaz LLMProvider
│   │   └── gemini.py              ← implementación Google AI Studio
│   ├── storage/
│   │   ├── pgvector_store.py      ← hybrid_search con pesos adaptativos
│   │   ├── query_log.py           ← persistencia consultas + memoria
│   │   └── object_store.py        ← abstracción S3/GCS/local
│   ├── tools/
│   │   ├── clasificacion.py       ← clasificar_deudor()
│   │   └── provisiones.py         ← calcular_provision()
│   ├── graph/
│   │   ├── builder.py             ← construir L1 (citas)
│   │   └── topics.py              ← K-means L2 + LLM naming
│   ├── ingestion/
│   │   ├── pipeline.py            ← process_source + run_scan
│   │   ├── background_worker.py   ← tick con caps de costo
│   │   ├── scheduler.py           ← APScheduler + zombie cleanup
│   │   ├── downloader.py          ← fetch con respeto a robots.txt
│   │   ├── scrapers/              ← SBS, BCRP, HTML
│   │   └── seed_catalog.py        ← 413 fuentes verificadas
│   └── ui/
│       ├── streamlit_app.py       ← tabs Consultar/Tópicos/Mapa/A-B/Admin
│       ├── api_client.py
│       └── styles.py              ← CSS + chat bubbles
├── sql/migrations/
│   ├── 001_init.sql
│   ├── 002_doc_sources.sql
│   ├── 003_graph.sql
│   ├── 004_background.sql         ← worker + cost tracker
│   └── 005_query_log.sql          ← user_sessions + query_log
├── docs/                          ← GitHub Pages site
├── deploy/                        ← Caddyfile + docker-compose.prod.yml
├── scripts/
│   └── lightsail/bootstrap.sh
├── data/sample/                   ← PDFs de muestra
├── docker-compose.prod.yml
└── Dockerfile                     ← multi-stage con Tesseract
```

---

## Roadmap

✅ **Fase 0 — Demo técnica completada**
✅ **Fase 1 — Deploy AWS Lightsail con HTTPS**
✅ **Fase 2 — Corpus regulatorio multiinstitucional (9 emisores)**
✅ **Fase 3 — Manual de Contabilidad SBS completo (Cap I-IV)**
✅ **Fase 4 — Retrieval avanzado (hybrid tuning + LLM reranker + OCR)**
✅ **Fase 5 — Analytics + memoria persistente por usuario**
⏳ **Fase 6 — Migración GCP Cloud Run con vector store gestionado**
⏳ **Fase 7 — Multi-tenant + RBAC + agentes especializados por área**

Ver [`docs/roadmap.md`](docs/roadmap.md) para detalle.

---

## Costos operativos

| Concepto | Costo mensual estimado |
|---|---|
| AWS Lightsail VM 2GB | USD 12 |
| Gemini 2.5 Flash (embeddings + generación, 1000 queries/día) | ~USD 5-10 |
| Dominio nip.io (gratuito) | $0 |
| **Total** | **~USD 20/mes** |

Cap de seguridad configurado: **USD 9.50 total** (worker se autoapaga).

---

## Licencia

Propietario — Erik Urrutia (mayo 2026).
Código de referencia abierto bajo solicitud para portafolio.

## Contacto

**Erik Urrutia** — eurrutia489@gmail.com
