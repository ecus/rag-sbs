#!/usr/bin/env bash
# backup-to-s3.sh — snapshot diario de Postgres a S3 (o GCS interop).
#
# Estrategia:
# 1. pg_dump comprimido del container postgres
# 2. Subir a s3://<bucket>/backups/YYYY-MM-DD-HH.sql.gz
# 3. Rotación local: solo último archivo
# 4. Rotación remota: lifecycle policy en S3 (configurar aparte)
#
# Variables requeridas (vienen de .env.prod):
#   OBJECT_STORE_BUCKET, OBJECT_STORE_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
#
# Para usar con GCS: agregar OBJECT_STORE_ENDPOINT_URL=https://storage.googleapis.com
# y usar HMAC keys de la consola GCP.

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/rag-sbs}"
cd "$INSTALL_DIR"

# Cargar variables del .env.prod (sin exponer secretos al log)
set -a
# shellcheck disable=SC1091
source .env.prod
set +a

if [[ -z "${OBJECT_STORE_BUCKET:-}" ]]; then
  echo "❌ OBJECT_STORE_BUCKET no configurado en .env.prod"
  exit 1
fi

TIMESTAMP="$(date -u +'%Y%m%dT%H%M%SZ')"
FILENAME="rag-sbs-pg-${TIMESTAMP}.sql.gz"
LOCAL_PATH="/tmp/${FILENAME}"

echo "[$(date -u +%FT%TZ)] ▶ pg_dump → ${LOCAL_PATH}"
docker compose -f docker-compose.prod.yml --env-file .env.prod \
  exec -T postgres pg_dump -U rag -d ragdb --no-owner --clean --if-exists \
  | gzip -9 > "${LOCAL_PATH}"

SIZE=$(stat -c%s "${LOCAL_PATH}" 2>/dev/null || stat -f%z "${LOCAL_PATH}")
echo "[$(date -u +%FT%TZ)] ▶ dump tamaño: $((SIZE/1024)) KB"

# Subir a object storage usando AWS CLI (compatible con S3 y GCS interop)
if [[ -n "${OBJECT_STORE_ENDPOINT_URL:-}" ]]; then
  ENDPOINT_FLAG=(--endpoint-url "${OBJECT_STORE_ENDPOINT_URL}")
else
  ENDPOINT_FLAG=()
fi

REMOTE_KEY="backups/${FILENAME}"
echo "[$(date -u +%FT%TZ)] ▶ s3 cp → s3://${OBJECT_STORE_BUCKET}/${REMOTE_KEY}"
AWS_DEFAULT_REGION="${OBJECT_STORE_REGION:-us-east-1}" \
  aws "${ENDPOINT_FLAG[@]}" s3 cp \
  "${LOCAL_PATH}" "s3://${OBJECT_STORE_BUCKET}/${REMOTE_KEY}" \
  --no-progress

echo "[$(date -u +%FT%TZ)] ▶ limpiando local"
rm -f "${LOCAL_PATH}"

echo "[$(date -u +%FT%TZ)] ✅ Backup completado: s3://${OBJECT_STORE_BUCKET}/${REMOTE_KEY}"
