-- 005_query_log.sql
-- User aliases + log de consultas para analytics y memoria persistente.

CREATE TABLE IF NOT EXISTS user_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alias           TEXT NOT NULL,           -- nombre/identificador que el user da
    user_agent      TEXT,                    -- meta de browser
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_sessions_alias_lower
    ON user_sessions(LOWER(alias));

CREATE TABLE IF NOT EXISTS query_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alias           TEXT NOT NULL,                -- referencia simple al alias (no FK para no romper si user borra)
    query_text      TEXT NOT NULL,
    answer_text     TEXT,
    confidence      TEXT,                         -- 'alta' | 'media' | 'baja' | 'sin_evidencia'
    n_sources       INT NOT NULL DEFAULT 0,
    latency_ms      INT,
    tokens_in       INT,
    tokens_out      INT,
    options         JSONB DEFAULT '{}'::jsonb,    -- toggles usados (graph, hops, informe, agente, stream)
    sources_summary JSONB DEFAULT '[]'::jsonb,    -- [{issuer, title, score, doc_id}, ...]
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_query_log_alias_created
    ON query_log(alias, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_query_log_created
    ON query_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_query_log_confidence
    ON query_log(confidence);
