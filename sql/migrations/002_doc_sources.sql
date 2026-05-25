-- =============================================================================
-- Migration 002 — Ingesta automática (scheduler + diff + change events)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- doc_sources — fuentes registradas para el scheduler
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS doc_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,                 -- ID legible
    url             TEXT NOT NULL,                        -- URL directa al PDF/HTML
    source_type     TEXT NOT NULL DEFAULT 'direct_pdf',   -- direct_pdf | listing_html | sitemap
    domain          TEXT,                                 -- riesgo_credito | ti_seguridad | ...
    document_type   TEXT,                                 -- resolución | circular | ...
    cron_expr       TEXT NOT NULL DEFAULT '0 2 * * *',    -- daily 02:00
    timezone        TEXT NOT NULL DEFAULT 'America/Lima',
    enabled         BOOLEAN NOT NULL DEFAULT true,

    -- Cache de detección de cambios
    last_etag       TEXT,
    last_modified   TEXT,
    last_hash       TEXT,
    last_status     TEXT,                                 -- 'no_change' | 'changed' | 'error'
    last_checked_at TIMESTAMPTZ,
    last_changed_at TIMESTAMPTZ,

    -- Metadatos extra
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_doc_sources_enabled ON doc_sources(enabled) WHERE enabled = true;
CREATE INDEX idx_doc_sources_domain  ON doc_sources(domain);

-- -----------------------------------------------------------------------------
-- change_events — eventos de cambio detectados (para alertas y auditoría)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS change_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       UUID NOT NULL REFERENCES doc_sources(id) ON DELETE CASCADE,
    run_id          UUID REFERENCES ingestion_runs(id) ON DELETE SET NULL,
    event_type      TEXT NOT NULL,                        -- new | modified | derogatorio | parse_failed
    document_id     UUID REFERENCES documents(id) ON DELETE SET NULL,
    summary         TEXT,                                 -- mensaje legible
    details         JSONB DEFAULT '{}'::jsonb,
    notified        BOOLEAN NOT NULL DEFAULT false,       -- ¿webhook/email enviado?
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_change_events_source     ON change_events(source_id);
CREATE INDEX idx_change_events_unnotified ON change_events(notified) WHERE notified = false;
CREATE INDEX idx_change_events_type       ON change_events(event_type);
CREATE INDEX idx_change_events_created    ON change_events(created_at DESC);

-- -----------------------------------------------------------------------------
-- Extend ingestion_runs (existing table) con campos de detalle
-- -----------------------------------------------------------------------------
ALTER TABLE ingestion_runs
    ADD COLUMN IF NOT EXISTS source_filter JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS dry_run        BOOLEAN NOT NULL DEFAULT false;
