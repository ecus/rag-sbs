-- 009_conversations.sql
-- Conversaciones tipo ChatGPT: hilos separados por usuario.
-- Cada hilo es un contexto limpio (reduce contaminación entre temas) y
-- permite controlar cuánto historial se reinyecta al LLM (control de costo).

CREATE TABLE IF NOT EXISTS conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    email       TEXT,                       -- denormalizado (alias en query_log)
    title       TEXT NOT NULL DEFAULT 'Nueva conversación',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conv_email ON conversations (LOWER(email), updated_at DESC);

-- Vincular cada consulta a su conversación (NULL = consultas legacy)
ALTER TABLE query_log ADD COLUMN IF NOT EXISTS conversation_id UUID
    REFERENCES conversations(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_query_log_conv ON query_log (conversation_id, created_at);
