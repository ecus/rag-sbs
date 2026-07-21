-- 010_access_control.sql
-- Control de acceso: los usuarios se registran como 'pending' y un admin
-- los aprueba. Límite de consultas por día por usuario (cuida cuota LLM).

ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_query_limit INT NOT NULL DEFAULT 20;
ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;

-- Los usuarios que YA existían quedan aprobados (no se los bloquea de golpe).
UPDATE users SET status = 'approved', approved_at = NOW()
WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_users_status ON users (status);
