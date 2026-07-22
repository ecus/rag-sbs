-- 011_feedback_limits.sql
-- Feedback por respuesta (like/dislike + comentario) y límites globales.

CREATE TABLE IF NOT EXISTS response_feedback (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email            TEXT,
    conversation_id  UUID,
    question         TEXT,
    answer           TEXT,
    vote             TEXT NOT NULL CHECK (vote IN ('up', 'down')),
    comment          TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_vote ON response_feedback (vote, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_email ON response_feedback (LOWER(email));

-- Configuración global (clave/valor) — límites generales, etc.
CREATE TABLE IF NOT EXISTS app_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO app_settings (key, value) VALUES
    ('global_daily_limit', '0'),    -- 0 = sin límite global por día
    ('global_hourly_limit', '0')    -- 0 = sin límite global por hora
ON CONFLICT (key) DO NOTHING;
