#!/usr/bin/env bash
# aws-to-gcp.sh — migra el RAG SBS desde Lightsail/S3 a Cloud Run + GCS + Cloud SQL.
#
# PREREQUISITOS:
# - gcloud CLI autenticado (gcloud auth login)
# - aws CLI autenticado (aws configure)
# - El proyecto GCP creado con APIs habilitadas:
#     gcloud services enable \
#       run.googleapis.com \
#       sqladmin.googleapis.com \
#       artifactregistry.googleapis.com \
#       storage.googleapis.com \
#       cloudbuild.googleapis.com
#
# Pasos automatizados:
#   1. Snapshot final de Postgres en Lightsail → S3
#   2. Copia el dump S3 → GCS
#   3. Restaura en Cloud SQL Postgres
#   4. Sincroniza PDFs S3 → GCS
#   5. Construye y empuja imágenes a Artifact Registry
#   6. Despliega API y UI en Cloud Run
#   7. Smoke test de las URLs nuevas
#
# Para configurar antes de correr:
set -euo pipefail

# ────────── PARÁMETROS ──────────
GCP_PROJECT="${GCP_PROJECT:-CHANGEME-proyecto}"
GCP_REGION="${GCP_REGION:-us-central1}"
GCS_BUCKET="${GCS_BUCKET:-rag-sbs-${GCP_PROJECT}}"
S3_BUCKET="${S3_BUCKET:-CHANGEME-aws-bucket}"
AR_REPO="rag-sbs"
CLOUDSQL_INSTANCE="rag-sbs-pg"
CLOUDSQL_TIER="db-f1-micro"   # ~$9/mes, suficiente para arrancar
LIGHTSAIL_IP="${LIGHTSAIL_IP:-CHANGEME_ip}"

# ────────── 1. Snapshot final desde Lightsail ──────────
echo "▶ [1/7] Snapshot final del Postgres de Lightsail..."
ssh "ubuntu@${LIGHTSAIL_IP}" "cd /opt/rag-sbs && bash scripts/lightsail/backup-to-s3.sh"
LATEST_DUMP=$(aws s3 ls "s3://${S3_BUCKET}/backups/" | sort | tail -1 | awk '{print $4}')
echo "    Último dump: s3://${S3_BUCKET}/backups/${LATEST_DUMP}"

# ────────── 2. Copia S3 → GCS ──────────
echo "▶ [2/7] Copiando dump y PDFs S3 → GCS..."
gcloud storage buckets create "gs://${GCS_BUCKET}" \
  --project="${GCP_PROJECT}" --location="${GCP_REGION}" 2>/dev/null || true
aws s3 cp "s3://${S3_BUCKET}/backups/${LATEST_DUMP}" "/tmp/${LATEST_DUMP}"
gcloud storage cp "/tmp/${LATEST_DUMP}" "gs://${GCS_BUCKET}/backups/"
# PDFs originales
aws s3 sync "s3://${S3_BUCKET}/pdfs/" "/tmp/pdfs-migration/"
gcloud storage rsync -r "/tmp/pdfs-migration/" "gs://${GCS_BUCKET}/pdfs/"

# ────────── 3. Crear Cloud SQL con pgvector ──────────
echo "▶ [3/7] Provisionando Cloud SQL Postgres (db-f1-micro)..."
gcloud sql instances create "${CLOUDSQL_INSTANCE}" \
  --project="${GCP_PROJECT}" \
  --database-version=POSTGRES_16 \
  --tier="${CLOUDSQL_TIER}" \
  --region="${GCP_REGION}" \
  --database-flags=cloudsql.iam_authentication=on \
  2>/dev/null || echo "    Instancia ya existe, continuando"

gcloud sql databases create ragdb --instance="${CLOUDSQL_INSTANCE}" --project="${GCP_PROJECT}" 2>/dev/null || true

echo "    Habilitando pgvector..."
gcloud sql instances patch "${CLOUDSQL_INSTANCE}" \
  --project="${GCP_PROJECT}" \
  --database-flags=cloudsql.enable_pgvector=on

# ────────── 4. Restaurar dump ──────────
echo "▶ [4/7] Restaurando dump en Cloud SQL..."
gcloud sql import sql "${CLOUDSQL_INSTANCE}" \
  "gs://${GCS_BUCKET}/backups/${LATEST_DUMP}" \
  --database=ragdb --project="${GCP_PROJECT}"

# ────────── 5. Build y push de imágenes ──────────
echo "▶ [5/7] Build + push a Artifact Registry..."
gcloud artifacts repositories create "${AR_REPO}" \
  --project="${GCP_PROJECT}" \
  --repository-format=docker \
  --location="${GCP_REGION}" 2>/dev/null || true

gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev"
AR_HOST="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/${AR_REPO}"

docker build -t "${AR_HOST}/api:latest" .
docker push "${AR_HOST}/api:latest"
docker tag "${AR_HOST}/api:latest" "${AR_HOST}/ui:latest"
docker push "${AR_HOST}/ui:latest"

# ────────── 6. Deploy a Cloud Run ──────────
echo "▶ [6/7] Desplegando en Cloud Run..."
CLOUDSQL_CONN="${GCP_PROJECT}:${GCP_REGION}:${CLOUDSQL_INSTANCE}"

gcloud run deploy rag-sbs-api \
  --project="${GCP_PROJECT}" \
  --region="${GCP_REGION}" \
  --image="${AR_HOST}/api:latest" \
  --add-cloudsql-instances="${CLOUDSQL_CONN}" \
  --set-env-vars="LLM_PROVIDER=gemini,OBJECT_STORE_BACKEND=gcs,OBJECT_STORE_BUCKET=${GCS_BUCKET},DATABASE_URL=postgresql+psycopg://rag:CHANGEME@/ragdb?host=/cloudsql/${CLOUDSQL_CONN}" \
  --set-secrets="GOOGLE_API_KEY=gemini-api-key:latest,JWT_SECRET=jwt-secret:latest" \
  --allow-unauthenticated \
  --memory=1Gi --cpu=1 \
  --min-instances=0 --max-instances=3

gcloud run deploy rag-sbs-ui \
  --project="${GCP_PROJECT}" \
  --region="${GCP_REGION}" \
  --image="${AR_HOST}/ui:latest" \
  --command="streamlit" \
  --args="run,src/ui/streamlit_app.py,--server.port=8501,--server.address=0.0.0.0,--server.headless=true" \
  --port=8501 \
  --allow-unauthenticated \
  --memory=1Gi --cpu=1 \
  --min-instances=0 --max-instances=2

# ────────── 7. Smoke test ──────────
echo "▶ [7/7] Smoke test..."
API_URL=$(gcloud run services describe rag-sbs-api --project="${GCP_PROJECT}" --region="${GCP_REGION}" --format='value(status.url)')
UI_URL=$(gcloud run services describe rag-sbs-ui --project="${GCP_PROJECT}" --region="${GCP_REGION}" --format='value(status.url)')

echo ""
echo "✅ Migración completa. URLs:"
echo "    API:    ${API_URL}"
echo "    UI:     ${UI_URL}"
echo ""
echo "    Health: $(curl -sf ${API_URL}/v1/health || echo 'FAIL')"
echo ""
echo "📋 Pasos opcionales tras verificar:"
echo "    - Apagar Lightsail VM cuando confirmes que GCP funciona"
echo "    - Configurar dominio custom (Cloud Run domain mapping)"
echo "    - Setear backups periódicos automáticos en Cloud SQL"
