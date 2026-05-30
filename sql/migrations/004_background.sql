-- 004_background.sql
-- Soporte para ingesta automática en background con queue + cost tracking.
-- Permite ejecutar scrapers que descubren URLs masivas, encolarlas y
-- procesarlas con un worker rate-limited por costo + volumen.

-- =============================================================================
-- pending_sources — cola de URLs candidatas a ingestar
-- =============================================================================

CREATE TABLE IF NOT EXISTS pending_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url             TEXT NOT NULL UNIQUE,
    name_hint       TEXT,                  -- nombre tentativo del slug
    title_hint      TEXT,                  -- título legible si se obtuvo
    issuer          TEXT NOT NULL,         -- SBS / BCRP / SMV / etc.
    document_type   TEXT,                  -- resolucion / circular / ley / etc.
    domain          TEXT,                  -- riesgo_credito / tasas_intereses / etc.
    discovered_at   TIMESTAMPTZ DEFAULT NOW(),
    discovered_by   TEXT,                  -- scraper:sbs / scraper:bcrp / manual
    status          TEXT NOT NULL DEFAULT 'pending',
                    -- pending | processing | completed | failed | skipped
    error_msg       TEXT,
    chunks_count    INT,                   -- # chunks tras ingestar (si OK)
    processed_at    TIMESTAMPTZ,
    estimated_cost  NUMERIC(10, 6),        -- USD estimado consumido
    priority        INT NOT NULL DEFAULT 50,
                    -- 0 (alta) ... 100 (baja). scraper SBS = 30, BCRP = 40, manual = 10
    metadata        JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_pending_sources_status
    ON pending_sources(status, priority, discovered_at);
CREATE INDEX IF NOT EXISTS idx_pending_sources_issuer
    ON pending_sources(issuer, status);


-- =============================================================================
-- cost_tracker — control de costo Gemini por día
-- =============================================================================

CREATE TABLE IF NOT EXISTS cost_tracker (
    day             DATE PRIMARY KEY,
    docs_processed  INT NOT NULL DEFAULT 0,
    chunks_processed INT NOT NULL DEFAULT 0,
    estimated_cost  NUMERIC(10, 6) NOT NULL DEFAULT 0,
    last_doc_at     TIMESTAMPTZ
);


-- =============================================================================
-- background_config — singleton para configuración runtime
-- =============================================================================

CREATE TABLE IF NOT EXISTS background_config (
    key             TEXT PRIMARY KEY,
    value           JSONB NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Configuración por defecto: límites del task autorizado por el usuario
INSERT INTO background_config (key, value) VALUES
  ('enabled',          'true'::jsonb),
  ('max_docs_total',   '2000'::jsonb),
  ('max_cost_total',   '9.50'::jsonb),
  ('max_cost_daily',   '1.50'::jsonb),
  ('docs_per_tick',    '3'::jsonb),
  ('schedule_until',   '"2026-06-01T23:59:00Z"'::jsonb)
ON CONFLICT (key) DO NOTHING;
