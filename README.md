# RAG SBS — Mesa Experta Regulatoria

> Sistema **RAG agéntico** sobre normativa de la **Superintendencia de Banca, Seguros y AFP del Perú (SBS)** y el **Banco Central de Reserva (BCRP)**. Respuestas con cálculos deterministas, citación de fuente oficial verificable y grafo navegable de citaciones entre resoluciones.

**📖 Documentación completa**: [eurrutia.github.io/rag-sbs](https://eurrutia.github.io/rag-sbs)

---

## ¿Qué hace?

Responde preguntas técnicas de banca peruana citando la **fuente oficial PDF** y para cálculos numéricos invoca **funciones deterministas** (nunca alucina porcentajes).

### Ejemplo 1: Cálculo concreto

> **Usuario**: "Hipotecario S/ 200,000, atraso 100 días, garantía S/ 180,000. ¿Qué hago?"

Sistema:
1. Dispara `clasificar_deudor("hipotecario", 100)` → **Deficiente** (rango 61-120 días, Cap. II num. 4.3)
2. Dispara `calcular_provision(200k, "Deficiente", "preferida", 180k)` → **S/ 38,750**
3. UI muestra desglose paso a paso, tabla regulatoria con fila resaltada, cita textual del PDF.

### Ejemplo 2: Cross-regulación (SBS + BCRP)

> **Usuario**: "¿Puedo subir mi tasa moratoria de 13% a 15%?"

Sistema recupera **Res. SBS 8181-2012** (Transparencia) + **Circular BCRP 0008-2021** (tope = 15% adicional sobre compensatoria) y responde con citas literales.

### Ejemplo 3: Anti-alucinación

> **Usuario**: "¿Cuál es la tasa de provisión hipotecaria para CPP?"

| Sistema | Respuesta |
|---|---|
| Gemini directo (sin RAG) | "0.63%" ❌ inventado |
| **RAG SBS** | "2.50% con garantía preferida / 5.00% sin garantía" ✓ Res. 11356-2008 Cap. III |

## Stack

- **Backend**: FastAPI + Python 3.11
- **UI**: Streamlit
- **LLM**: Gemini 2.5 Flash (Google AI Studio) — Ollama fallback en dev local
- **Embeddings**: `gemini-embedding-001` (768d)
- **Vector store**: PostgreSQL + pgvector
- **Cache semántico**: Redis
- **Object storage**: S3 / GCS / local (cloud-agnóstico)
- **Reverse proxy**: Caddy con HTTPS automático
- **Containerización**: Docker / Podman

## Características técnicas destacadas

- **Hybrid search** (vector + BM25 + Reciprocal Rank Fusion)
- **Graph-augmented retrieval** (317 nodos / 1,969 aristas de citaciones)
- **Topic router** determinista que separa Provisiones ↔ Patrimonio Efectivo ↔ PLAFT
- **Re-fetch dirigido**: si el filtro temático remueve chunks, consulta directo a la DB filtrando por título
- **Parser PyMuPDF** con fallback a pypdf (preserva tablas regulatorias)
- **Chunker estructural** que detecta Capítulo > Sección > Artículo > Anexo
- **Validación contra fuente oficial**: tablas hardcoded validadas vs PDF en línea SBS
- **Streaming SSE** + reconstrucción de query con historial conversacional
- **Backups automáticos** pg_dump → S3 con cron

## Quickstart local (Podman + Ollama)

```bash
# 1. Prerrequisitos
brew install podman ollama       # macOS
ollama pull qwen2.5:14b
ollama pull nomic-embed-text

# 2. Configurar
cp .env.example .env             # edita LLM_PROVIDER=ollama

# 3. Levantar stack
podman-compose up -d

# 4. Ingestar corpus
make local-ingest

# 5. UI en http://localhost:8501
```

## Quickstart producción (cloud)

```bash
# AWS Lightsail
ssh ubuntu@<IP> "bash <(curl -fsSL https://raw.githubusercontent.com/eurrutia/rag-sbs/main/scripts/lightsail/bootstrap.sh)"
# Editar .env.prod
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

Migración futura a GCP:

```bash
bash scripts/migrate/aws-to-gcp.sh
```

## Estructura del repo

```
rag-sbs/
├── src/                  ← Código fuente
│   ├── api/              ← FastAPI endpoints
│   ├── agents/           ← Calculator, topic router, query rewriter
│   ├── rag/              ← Parser, chunker, retriever, reranker
│   ├── llm/              ← Providers Ollama / Gemini (factory pattern)
│   ├── storage/          ← pgvector store + object_store abstracto
│   ├── tools/            ← Funciones deterministas (clasificación, provisiones)
│   ├── graph/            ← Knowledge graph L1 + L2 (K-means)
│   ├── ingestion/        ← Downloader + scheduler + diff
│   └── ui/               ← Streamlit app + componentes
├── docs/                 ← GitHub Pages site
├── deploy/               ← Caddyfile + manifests
├── scripts/              ← Bootstrap, backup, migración
├── sql/                  ← Migraciones Alembic
├── tests/                ← pytest suites
├── data/sample/          ← PDFs de muestra para dev local
├── docker-compose.prod.yml
└── podman-compose.yml    ← Stack dev local
```

## Estado del proyecto

✅ **Fase 0 — Demo técnica completada**
🟡 **Fase 1 — Deploy público (en curso, AWS Lightsail)**
⏳ Fase 2 — Migración GCP Cloud Run
⏳ Fase 3 — Multi-tenant + MCPs + agentes especializados

Ver [`docs/roadmap.md`](docs/roadmap.md) para detalle.

## Licencia

(pendiente decidir — propietario o MIT)

## Contacto

Erik Urrutia — eurrutia489@gmail.com
