---
title: Arquitectura
description: Diseño técnico del sistema RAG SBS — componentes, pipeline y decisiones
---

# 🏗️ Arquitectura técnica · v0.5

> Visión de ingeniería del sistema RAG SBS — qué corre dónde, cómo fluye una query, y por qué se diseñó así.

---

## 🎯 Objetivos de diseño

| Objetivo | Cómo se logra |
|---|---|
| **Zero alucinación numérica** | Calculator agent con funciones Python deterministas |
| **Citas verificables** | Hybrid search + reranker + cada fuente vinculada a PDF original |
| **Anti-mezcla regulatoria** | Topic router determinista basado en keywords |
| **Bajo costo operativo** | Stack en una VM 2GB · cap de gasto Gemini · scale-to-zero futuro |
| **Auto-mantenimiento** | Crons que limpian zombies, descubren docs nuevos y rebuildean grafo |
| **Memoria sin sesgo** | Filtro semántico de turnos relevantes vía embeddings |

---

## 🗺️ Vista de despliegue

```mermaid
graph TB
    subgraph CLIENT[🌐 Cliente]
        BR[Browser]
    end

    subgraph VM["☁️ AWS Lightsail · Ubuntu 22.04 · 2GB RAM"]
        subgraph EDGE[🔒 Edge]
            CAD[Caddy<br/>HTTPS · Let's Encrypt]
        end

        subgraph FE[📱 Frontend]
            UI[Streamlit UI<br/>:8501<br/>400MB RAM]
        end

        subgraph BE[⚙️ Backend]
            API[FastAPI<br/>:8000<br/>700MB RAM]
            SCH[APScheduler<br/>in-process]
        end

        subgraph DATA[🗄️ Persistencia]
            PG[(PostgreSQL 16<br/>+ pgvector<br/>600MB RAM)]
            RD[(Redis 7<br/>150MB)]
        end
    end

    subgraph CLOUD[☁️ Externos]
        GEM[Gemini API<br/>2.5 Flash + embedding-001]
        S3[(S3 / GCS<br/>PDFs + backups)]
        GH[GitHub<br/>código + CI/CD]
    end

    BR -->|HTTPS| CAD
    CAD --> UI
    CAD --> API
    UI <-->|REST + SSE| API
    API <--> PG
    API <--> RD
    API <--> GEM
    API <--> S3
    SCH -.->|cron */10| API
    GH -.->|git pull| VM

    style BR fill:#f97316,color:#fff
    style CAD fill:#10b981,color:#fff
    style UI fill:#ff4b4b,color:#fff
    style API fill:#003d7a,color:#fff
    style PG fill:#336791,color:#fff
    style RD fill:#dc382d,color:#fff
    style GEM fill:#4285f4,color:#fff
```

---

## 🔬 Pipeline de query — 8 fases detalladas

```mermaid
flowchart TB
    Q[💬 Query usuario]:::input --> H{¿historial?}

    H -->|sí| MF[🧠 Fase 0.5<br/>Filtro semántico de turnos]:::new
    H -->|no| EMB
    MF -->|turnos relevantes| RW[✏️ Fase 1<br/>Rewriter standalone]

    RW --> EMB[🔢 Fase 2<br/>Embedding consulta]
    EMB --> QP[🎯 Fase 3<br/>Query Profiler]:::new

    QP -->|lexical fuerte| WP1[w_v=0.6 · w_t=1.4]
    QP -->|semantic| WP2[w_v=1.3 · w_t=0.7]
    QP -->|balanced| WP3[w_v=1.0 · w_t=1.0]

    WP1 --> HS[🔍 Fase 4<br/>Hybrid Search + RRF ponderado<br/>25 candidatos]
    WP2 --> HS
    WP3 --> HS

    HS --> GR{¿Graph-aug?}
    GR -->|sí| GE[🕸️ Expansión multi-hop<br/>siguiendo KG]
    GR -->|no| RK
    GE --> RK[🏆 Fase 5<br/>LLM Re-ranker<br/>25 → top 10]

    RK --> TR[🚦 Fase 6<br/>Topic Router determinista<br/>anti-mezcla]
    TR --> CALC[🧮 Fase 7<br/>Calculator Agent<br/>function calling]

    CALC --> SP[💬 Fase 8<br/>Generación LLM<br/>3 niveles de evidencia]
    SP -->|NIVEL A| OUT_A[Sin evidencia 🟡]
    SP -->|NIVEL B| OUT_B[Evidencia parcial + clarificación 🔵]
    SP -->|NIVEL C| OUT_C[Respuesta con citas 🟢]

    OUT_A --> LOG
    OUT_B --> LOG
    OUT_C --> LOG[📝 query_log + analytics]

    classDef input fill:#fde68a,color:#92400e
    classDef new fill:#dbeafe,color:#1e40af,stroke:#3b82f6,stroke-width:2px
```

### 🆕 Fase 0.5 — Filtro semántico de contexto

```mermaid
flowchart LR
    H[Historial<br/>10 turnos] --> E1[Embed cada par<br/>user+assistant]
    Q[Query actual] --> E2[Embed query]

    E1 --> COS[Cosine similarity<br/>por turno]
    E2 --> COS

    COS --> F{score ≥ 0.55?}
    F -->|sí| KEEP[✅ Incluir]
    F -->|no| DROP[❌ Descartar]
    KEEP --> LAST[+ Forzar último turno<br/>siempre]
    DROP --> LAST
    LAST --> OUT[Top 6 turnos<br/>al rewriter]

    style F fill:#fef3c7,color:#92400e
    style KEEP fill:#10b981,color:#fff
    style DROP fill:#ef4444,color:#fff
```

**Razón**: usuarios cambian de tema en conversaciones largas. Pasar siempre los últimos N turnos provoca contaminación de contexto (ej. RCD bajo lente de titulización). El filtro semántico solo pasa turnos relacionados con la nueva pregunta.

### 🎯 Fase 3 — Query Profiler

```mermaid
flowchart TB
    Q[Query] --> P{Patrón detectado}

    P -->|"Res SBS 11356-2008<br/>Art 5"| L2[Lexical fuerte<br/>2+ entidades]
    P -->|"Resolución 11356"| L1[Lexical simple<br/>1 entidad]
    P -->|"¿qué es...?"<br/>"¿cómo...?"| S[Semantic]
    P -->|sin señal clara| B[Balanced]

    L2 --> W2[w_vector=0.6<br/>w_texto=1.4]
    L1 --> W1[w_vector=0.8<br/>w_texto=1.2]
    S --> WS[w_vector=1.3<br/>w_texto=0.7]
    B --> WB[w_vector=1.0<br/>w_texto=1.0]
```

---

## 🕸️ Knowledge Graph

```mermaid
classDiagram
    class Document {
        +UUID id
        +string title
        +string issuer
        +string source_url
        +date publication_date
    }

    class Resolution {
        +string number
        +int year
        +string status
    }

    class Topic {
        +int cluster_id
        +string label
        +int members
    }

    class Article {
        +int number
        +string chapter
    }

    Document "1" --> "*" Article : cites
    Document "1" --> "*" Resolution : cites
    Resolution "1" --> "*" Resolution : modifies
    Resolution "1" --> "*" Resolution : derogates
    Document "*" --> "*" Topic : topic_member

    class GraphEdge {
        +UUID src_node
        +UUID dst_node
        +string kind
    }
```

### Niveles del KG

| Nivel | Qué representa | Cómo se construye |
|---|---|---|
| **L1** Citas explícitas | Referencias entre normas | Regex sobre chunks: `Res. SBS N° XXXX-YYYY` |
| **L2** Tópicos semánticos | Agrupaciones temáticas | K-means sobre embeddings + LLM naming |

**Estado actual**: ~1,100 nodos `document` + 252 nodos `resolution` + 15 nodos `topic` + ~12,000 aristas `cites`.

---

## 📥 Pipeline de ingesta

```mermaid
flowchart LR
    SRC[Fuente PDF<br/>URL del catálogo] --> DL[📥 Downloader<br/>respeta robots.txt<br/>excepto .gob.pe]

    DL --> HASH[#️⃣ Hash<br/>SHA-256 contenido]
    HASH --> CACHE{¿hash cambió?}
    CACHE -->|no| SKIP[⏭️ Skip<br/>last_status=unchanged]
    CACHE -->|sí| PARSE

    PARSE[📄 Parser cadena 3 niveles]
    PARSE --> P1[1. PyMuPDF<br/>preserva tablas]
    P1 --> CHK1{¿texto ≥ 50 char/pág?}
    CHK1 -->|sí| OK
    CHK1 -->|no| P2[2. pypdf fallback]
    P2 --> CHK2{¿texto suficiente?}
    CHK2 -->|sí| OK
    CHK2 -->|no| P3[3. OCR Tesseract<br/>español · DPI 200]
    P3 --> OK[✅ Texto extraído]

    OK --> CHUNK[✂️ Chunker estructural<br/>detecta Cap → Sec → Art → Anexo]
    CHUNK --> EMB[🧠 Embedding<br/>768d por chunk]
    EMB --> STORE[(💾 chunks table<br/>+ tsvector BM25)]

    STORE --> KG[🕸️ Update KG<br/>extrae citas y enlaza]

    style P3 fill:#fef3c7,color:#92400e
    style CHUNK fill:#dbeafe,color:#1e40af
    style EMB fill:#4285f4,color:#fff
```

---

## ⏰ Crons automáticos

```mermaid
gantt
    title Cronograma de tareas automáticas (UTC)
    dateFormat HH:mm
    axisFormat %H:%M

    section Cada 10 min
    Worker tick (pending_sources) :crit, w1, 00:00, 10m
    Worker tick :crit, w2, 00:10, 10m
    Worker tick :crit, w3, 00:20, 10m

    section Cada 15 min
    Zombie cleanup :z1, 00:00, 15m
    Zombie cleanup :z2, 00:15, 15m

    section Cada hora
    Rebuild grafo + tópicos :g1, 00:05, 5m

    section Diario 03:00
    Discovery scrapers SBS+BCRP :d1, 03:00, 30m

    section Diario 04:00
    Backup pg_dump → S3 :b1, 04:00, 15m
```

---

## 💾 Capa de datos

```mermaid
erDiagram
    documents ||--o{ chunks : "1:N"
    documents ||--o{ change_events : "1:N"
    doc_sources ||--o{ documents : "1:N"
    ingestion_runs ||--o{ change_events : "1:N"
    user_sessions ||--o{ query_log : "1:N"
    graph_nodes ||--o{ graph_edges : "1:N"
    documents ||--o{ pending_sources : "scraper"

    documents {
        uuid id PK
        text document_id
        int version_id
        text title
        text source_url
        text content_hash
        jsonb metadata
        timestamp indexed_at
    }

    chunks {
        uuid id PK
        uuid document_id FK
        text content
        vector embedding
        tsvector content_tsv
        jsonb metadata
    }

    query_log {
        uuid id PK
        text alias
        text query_text
        text answer_text
        text confidence
        int n_sources
        int latency_ms
        jsonb options
        jsonb sources_summary
        timestamp created_at
    }

    graph_nodes {
        uuid id PK
        text label
        text kind
        uuid document_id FK
        jsonb metadata
    }

    graph_edges {
        uuid id PK
        uuid src_node FK
        uuid dst_node FK
        text kind
    }
```

---

## 🤖 Arquitectura de memoria conversacional

```mermaid
flowchart TB
    LOGIN[👤 Login con alias] --> Q1{¿tiene historial<br/>en BD?}

    Q1 -->|sí| ASK[📚 Mostrar opción:<br/>'Cargar N conversaciones?']
    Q1 -->|no| EMPTY[🆕 Empezar limpio]

    ASK -->|usuario: sí| LOAD[Cargar últimos 20<br/>mensajes de query_log]
    ASK -->|usuario: no| EMPTY

    LOAD --> SESS[(session_state<br/>historial_chat)]
    EMPTY --> SESS

    SESS --> CONV[💬 Usuario conversa]
    CONV --> APPEND[Append turno al historial]
    APPEND --> SAVE[Persistir en query_log]
    SAVE --> CONV

    CONV -.->|nueva consulta| FILT[🧠 Filtro semántico<br/>solo turnos relevantes]
    FILT -.->|contexto limpio| LLM[LLM responde]
```

**Diferencia clave con sistemas tradicionales**:
- ❌ Tradicional: pasa últimos N turnos siempre → contamina contexto
- ✅ RAG SBS: filtra por similitud semántica → solo turnos relevantes

---

## 🎚️ Self-healing

```mermaid
stateDiagram-v2
    [*] --> Running: cron tick dispara
    Running --> Completed: success
    Running --> Failed: error<br/>process_source
    Running --> Zombie: crash del proceso<br/>sin actualizar

    Zombie --> Aborted: cron */15 detecta<br/>> 30min sin update
    Failed --> [*]
    Completed --> [*]
    Aborted --> [*]

    note right of Zombie
        Sin este flujo,
        zombies se acumulaban
        (321 en un día observado)
    end note
```

---

## 🚀 Decisiones arquitectónicas (ADRs)

| ID | Decisión | Razón |
|---|---|---|
| **ADR-001** | Gemini sobre Ollama | Latencia + calidad >> costo en escala portafolio |
| **ADR-002** | pgvector sobre Pinecone/Weaviate | Simplicidad: una sola BD relacional |
| **ADR-003** | APScheduler in-process sobre Celery | Stack 5x más simple para 1 worker |
| **ADR-004** | RRF ponderado sobre concatenación | Documentado en literatura, mejor ranking |
| **ADR-005** | LLM reranker sobre cross-encoder local | Evita +3GB de sentence-transformers |
| **ADR-006** | Topic router determinista | Zero falsos positivos en separación regulatoria |
| **ADR-007** | Caps de costo hard-coded al worker | Presupuesto portafolio limitado |
| **ADR-008** | Self-healing cron sobre supervisión manual | Experiencia: 321 zombies/día sin esto |
| **ADR-009** | Filtro semántico de contexto memoria | Resolver contaminación en cambios de tema |
| **ADR-010** | Plan C: max_tokens 6K-8K, chunks 10 | Aprovechar context window Gemini (1M) |

---

## 📊 Métricas operativas

| Métrica | Valor actual | Meta v1.0 |
|---|---|---|
| Latencia query P50 | 4-8s | <5s |
| Latencia query P95 | 15s | <10s |
| Confianza ALTA real | ~70% | >85% |
| Costo por query | ~$0.005 | <$0.003 |
| Uptime | 99.5% | 99.9% |
| Corpus | 1,100 docs | 2,000+ |
| Instituciones | 12 | 15+ |
