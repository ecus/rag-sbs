-- =============================================================================
-- Migration 001 — Schema inicial RAG SBS
-- =============================================================================
-- Se ejecuta automáticamente al crear el container Postgres
-- (montado en /docker-entrypoint-initdb.d/)
-- =============================================================================

-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS vector;          -- pgvector
CREATE EXTENSION IF NOT EXISTS pg_trgm;         -- BM25-like text search

-- -----------------------------------------------------------------------------
-- documents — un registro por documento ingerido (versionado append-only)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     TEXT NOT NULL,                        -- ID estable cross-version
    version_id      INTEGER NOT NULL DEFAULT 1,
    title           TEXT NOT NULL,
    source_url      TEXT,
    document_type   TEXT,                                 -- manual|resolución|circular|...
    domain          TEXT,                                 -- contabilidad|riesgo_credito|...
    entity_type     TEXT,                                 -- banco|financiera|...
    validity_status TEXT DEFAULT 'vigente',               -- vigente|derogada|modificada|...
    resolution_number TEXT,
    publication_date DATE,
    effective_date  DATE,
    superseded_by   UUID REFERENCES documents(id),        -- versión que la reemplaza
    content_hash    TEXT NOT NULL,                        -- SHA-256 del contenido
    raw_storage_url TEXT,                                 -- GCS / filesystem
    metadata        JSONB DEFAULT '{}'::jsonb,
    indexed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, version_id)
);

CREATE INDEX idx_documents_domain      ON documents(domain);
CREATE INDEX idx_documents_validity    ON documents(validity_status);
CREATE INDEX idx_documents_doc_id      ON documents(document_id);

-- -----------------------------------------------------------------------------
-- chunks — fragmentos vectorizados
-- -----------------------------------------------------------------------------
-- 768 dim para nomic-embed-text (Ollama) y text-embedding-004 (Vertex)
-- Si cambias a otro modelo, ajusta EMBED_DIM en .env Y recrea esta tabla.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    content_tsv     tsvector GENERATED ALWAYS AS (to_tsvector('spanish', content)) STORED,
    embedding       vector(768),
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

-- Índice HNSW para búsqueda vectorial rápida (cosine distance)
CREATE INDEX idx_chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Índice GIN para BM25-like sobre content_tsv
CREATE INDEX idx_chunks_content_tsv ON chunks USING GIN (content_tsv);

-- -----------------------------------------------------------------------------
-- ingestion_runs — historial del scheduler (Sprint 2)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at         TIMESTAMPTZ,
    status              TEXT NOT NULL DEFAULT 'running',  -- running|completed|failed|partial
    sources_scanned     INTEGER DEFAULT 0,
    docs_new            INTEGER DEFAULT 0,
    docs_modified       INTEGER DEFAULT 0,
    docs_unchanged      INTEGER DEFAULT 0,
    errors              JSONB DEFAULT '[]'::jsonb,
    triggered_by        TEXT                              -- 'cron'|'manual:user_id'
);

-- -----------------------------------------------------------------------------
-- traces — trazabilidad de queries (Sprint 1, simplificado)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS traces (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             TEXT,                             -- por ahora null (auth en Sprint 2)
    question            TEXT NOT NULL,
    answer              TEXT,
    sources             JSONB DEFAULT '[]'::jsonb,
    confidence          TEXT,
    cache_hit           BOOLEAN DEFAULT false,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    latency_ms          DOUBLE PRECISION,
    estimated_cost_usd  DOUBLE PRECISION,
    warnings            JSONB DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_traces_created_at ON traces(created_at DESC);
CREATE INDEX idx_traces_user_id    ON traces(user_id);
