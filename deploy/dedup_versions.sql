-- Dedup de versiones duplicadas de documentos (deja solo max(version_id) por
-- document_id) y reconstrucción de índices pesados de chunks.
--
-- Contexto: hasta el fix de hash sobre texto (differ.hash_text), el scheduler
-- creaba una versión nueva en cada scrape porque hasheaba los bytes crudos del
-- PDF (que cambian por timestamps). Este script limpia el bloat resultante.
--
-- ORDEN IMPORTANTE (rendimiento): truncar el grafo y dropear HNSW/GIN ANTES de
-- borrar, si no el DELETE tarda >20 min por el mantenimiento del índice HNSW.
--
-- Uso:
--   docker exec -i rag-sbs-postgres psql -U rag -d ragdb -f - < deploy/dedup_versions.sql
-- DESPUÉS, reconstruir grafo y tópicos (usan el corpus ya limpio):
--   curl -X POST http://127.0.0.1:8000/v1/graph/rebuild
--   curl -X POST "http://127.0.0.1:8000/v1/graph/topics/build?n_topicos=8&max_chunks=20000"

\timing on

-- 1. El grafo se reconstruye después → truncarlo evita la cascada cara al borrar.
TRUNCATE graph_edges, graph_nodes CASCADE;

-- 2. Dropear los índices pesados (HNSW borra lentísimo fila por fila).
DROP INDEX IF EXISTS idx_chunks_embedding_hnsw;
DROP INDEX IF EXISTS idx_chunks_content_tsv;

-- 3. Borrar versiones no-últimas (los chunks caen por CASCADE).
DELETE FROM documents d
WHERE version_id < (SELECT max(version_id) FROM documents d2 WHERE d2.document_id = d.document_id);

-- 4. Recrear índices. HNSW en modo SERIAL: el build en paralelo satura el
--    /dev/shm de 64MB del contenedor ("No space left on device").
SET max_parallel_maintenance_workers = 0;
SET maintenance_work_mem = '256MB';
CREATE INDEX idx_chunks_embedding_hnsw ON public.chunks USING hnsw (embedding vector_cosine_ops) WITH (m = '16', ef_construction = '64');
CREATE INDEX idx_chunks_content_tsv ON public.chunks USING gin (content_tsv);

-- 5. Actualizar estadísticas del planner.
VACUUM ANALYZE chunks;
VACUUM ANALYZE documents;

SELECT
  (SELECT count(*) FROM documents) AS docs,
  (SELECT count(DISTINCT document_id) FROM documents) AS docs_unicos,
  (SELECT count(*) FROM chunks) AS chunks;
