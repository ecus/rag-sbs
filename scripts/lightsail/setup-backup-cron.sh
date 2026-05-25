#!/usr/bin/env bash
# setup-backup-cron.sh — registra cron diario que dispara backup-to-s3.sh.
# Idempotente: se puede correr varias veces sin duplicar líneas.

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/rag-sbs}"
LOG_FILE="/var/log/rag-sbs-backup.log"
CRON_LINE="0 3 * * * cd ${INSTALL_DIR} && bash scripts/lightsail/backup-to-s3.sh >> ${LOG_FILE} 2>&1"

sudo touch "${LOG_FILE}"
sudo chown ubuntu:ubuntu "${LOG_FILE}"

# Quita líneas previas referidas a backup-to-s3 y agrega la nueva
(crontab -l 2>/dev/null | grep -v "backup-to-s3.sh" || true; echo "${CRON_LINE}") | crontab -

echo "✅ Cron registrado:"
crontab -l | grep backup-to-s3 || true
echo ""
echo "Logs en: ${LOG_FILE}"
echo "Para probar manualmente AHORA:"
echo "  bash ${INSTALL_DIR}/scripts/lightsail/backup-to-s3.sh"
