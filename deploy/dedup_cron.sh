#!/usr/bin/env bash
# Dedup automático de versiones duplicadas de documentos.
#
# Pensado para correr por cron. Es SELF-SKIP: primero cuenta cuántas versiones
# no-últimas hay; si son 0, no hace nada (barato y seguro de correr seguido).
# Solo cuando hay duplicados ejecuta el procedimiento pesado (deploy/dedup_versions.sql)
# y reconstruye grafo + tópicos.
#
# Contexto: tras el fix de hash sobre texto (differ.hash_text), el primer re-scrape
# de cada fuente crea 1 versión de transición (byte-hash → text-hash) y luego se
# estabiliza. Este cron limpia esas versiones cuando aparecen.
#
# Instalar (crontab del usuario ubuntu, domingos 04:10 UTC):
#   (crontab -l 2>/dev/null; echo "10 4 * * 0 /opt/rag-sbs/deploy/dedup_cron.sh") | crontab -

set -uo pipefail

LOG="${HOME}/rag-dedup.log"
DIR="$(cd "$(dirname "$0")" && pwd)"
exec >>"$LOG" 2>&1

echo "=== $(date -u +%FT%TZ) dedup check ==="

DUP="$(docker exec -i rag-sbs-postgres psql -U rag -d ragdb -tAc \
  "SELECT count(*) FROM documents d WHERE version_id < (SELECT max(version_id) FROM documents d2 WHERE d2.document_id = d.document_id);" 2>/dev/null | tr -d '[:space:]')"

echo "versiones duplicadas: ${DUP:-?}"

if [ "${DUP:-0}" = "0" ]; then
  echo "nada que dedupear; skip"
  exit 0
fi

echo "dedupeando ${DUP} versiones..."
if ! docker exec -i rag-sbs-postgres psql -U rag -d ragdb -f - < "${DIR}/dedup_versions.sql"; then
  echo "ERROR en dedup_versions.sql; aborta"
  exit 1
fi

echo "reconstruyendo grafo..."
curl -s --max-time 800 -X POST http://127.0.0.1:8000/v1/graph/rebuild >/dev/null \
  || echo "WARN: fallo el rebuild del grafo"

echo "reconstruyendo tópicos..."
curl -s --max-time 800 -X POST "http://127.0.0.1:8000/v1/graph/topics/build?n_topicos=8&max_chunks=20000" >/dev/null \
  || echo "WARN: fallo el rebuild de tópicos"

echo "dedup completo."
