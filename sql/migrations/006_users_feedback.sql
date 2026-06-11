-- 006_users_feedback.sql
-- Registro de usuarios con email único + encuesta de satisfacción al cerrar sesión.

-- =============================================================================
-- users — registro básico con email único
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL,
    name            TEXT NOT NULL,
    organization    TEXT,
    role            TEXT,                -- compliance/auditor/riesgos/contab/legal/etc
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    n_sessions      INT NOT NULL DEFAULT 1,
    n_queries_total INT NOT NULL DEFAULT 0
);

-- Email único case-insensitive (un mismo email = un solo registro)
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower ON users (LOWER(email));
CREATE INDEX IF NOT EXISTS idx_users_last_activity ON users (last_activity_at DESC);


-- =============================================================================
-- feedback_surveys — encuestas de satisfacción al cerrar sesión
-- =============================================================================

CREATE TABLE IF NOT EXISTS feedback_surveys (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID REFERENCES users(id) ON DELETE SET NULL,
    email              TEXT,                     -- denormalizado
    -- Ratings 1-5 (NULL si no respondió)
    rating_overall     INT CHECK (rating_overall BETWEEN 1 AND 5),
    rating_accuracy    INT CHECK (rating_accuracy BETWEEN 1 AND 5),
    rating_speed       INT CHECK (rating_speed BETWEEN 1 AND 5),
    rating_ux          INT CHECK (rating_ux BETWEEN 1 AND 5),
    -- Multi-choice / texto libre
    use_case           TEXT,                     -- "compliance regulatorio"
    would_recommend    TEXT,                     -- "si"/"no"/"tal_vez"
    favorite_feature   TEXT,                     -- texto libre o JSON
    missing_feature    TEXT,                     -- texto libre
    comments           TEXT,                     -- texto libre
    -- Métricas automáticas
    session_duration_min INT,
    n_queries_session    INT,
    closed_reason      TEXT,                     -- "manual"/"timeout"/"browser"
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback_surveys (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_overall ON feedback_surveys (rating_overall);


-- =============================================================================
-- Migración suave: backfill desde user_sessions a users (los aliases viejos)
-- =============================================================================

INSERT INTO users (email, name, created_at, last_login_at, last_activity_at, n_sessions)
SELECT
    alias || '@legacy.local' AS email,
    alias AS name,
    created_at,
    last_seen_at,
    last_seen_at,
    1
FROM user_sessions s
WHERE NOT EXISTS (
    SELECT 1 FROM users u
    WHERE LOWER(u.email) = LOWER(s.alias || '@legacy.local')
);
