-- 007_security.sql
-- PIN de acceso por usuario + IP de cliente en query_log (auditoría).

-- PIN hasheado (pbkdf2). NULL = usuario legacy que aún no definió PIN;
-- en el primer login se le exige definir uno.
ALTER TABLE users ADD COLUMN IF NOT EXISTS pin_hash TEXT;

-- IP del cliente para auditoría y análisis de abuso
ALTER TABLE query_log ADD COLUMN IF NOT EXISTS client_ip TEXT;
