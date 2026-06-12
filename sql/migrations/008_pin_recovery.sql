-- 008_pin_recovery.sql
-- Código de recuperación de PIN (hasheado, un solo uso: se rota al usarse).

ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_code_hash TEXT;
