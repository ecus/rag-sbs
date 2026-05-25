#!/usr/bin/env bash
# bootstrap.sh — provisiona una VM Lightsail Ubuntu 22.04 desde cero.
#
# Se ejecuta UNA SOLA VEZ por VM. Asume que ya conectaste por SSH como ubuntu.
#
# Uso desde tu Mac:
#   scp scripts/lightsail/bootstrap.sh ubuntu@<IP>:~/
#   ssh ubuntu@<IP> "bash bootstrap.sh"

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/CHANGEME/rag-sbs.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/rag-sbs}"

echo "▶ 1/6 Actualizando sistema..."
sudo apt-get update -y
sudo apt-get upgrade -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold

echo "▶ 2/6 Instalando Docker + docker compose plugin..."
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker ubuntu
fi
sudo apt-get install -y docker-compose-plugin awscli git ufw fail2ban

echo "▶ 3/6 Configurando firewall (UFW)..."
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP (Caddy)'
sudo ufw allow 443/tcp comment 'HTTPS (Caddy)'
sudo ufw --force enable

echo "▶ 4/6 Clonando repo a $INSTALL_DIR..."
sudo mkdir -p "$INSTALL_DIR"
sudo chown ubuntu:ubuntu "$INSTALL_DIR"
if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  git clone "$REPO_URL" "$INSTALL_DIR"
else
  cd "$INSTALL_DIR" && git pull
fi

echo "▶ 5/6 Generando .env.prod template..."
if [[ ! -f "$INSTALL_DIR/.env.prod" ]]; then
  cat > "$INSTALL_DIR/.env.prod" <<'ENVEOF'
# Provider LLM
LLM_PROVIDER=gemini
GOOGLE_API_KEY=CHANGEME_aizasy...
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBED_MODEL=gemini-embedding-001
GEMINI_EMBED_DIM=768
EMBED_DIM=768

# Postgres
POSTGRES_PASSWORD=CHANGEME_random_password

# JWT
JWT_SECRET=CHANGEME_random_secret

# Object storage (PDFs + backups)
OBJECT_STORE_BACKEND=s3
OBJECT_STORE_BUCKET=CHANGEME-rag-sbs
OBJECT_STORE_REGION=us-east-1
AWS_ACCESS_KEY_ID=CHANGEME
AWS_SECRET_ACCESS_KEY=CHANGEME

# Caddy / dominio
DOMAIN=_                 # cambia a tu-dominio.com si tienes uno
API_URL_PUBLIC=http://_  # cambia cuando tengas dominio
ENVEOF
  echo "⚠  .env.prod creado con placeholders. EDÍTALO antes de levantar el stack:"
  echo "    nano $INSTALL_DIR/.env.prod"
fi

echo "▶ 6/6 Verificación..."
docker --version
docker compose version
aws --version || true

cat <<'NEXT'

✅ Bootstrap completo.

PRÓXIMOS PASOS (en orden):

1. Editar credenciales en .env.prod:
   nano /opt/rag-sbs/.env.prod

2. Cerrar sesión y volver a conectar (para que tome el grupo docker):
   exit && ssh ubuntu@<IP>

3. Levantar el stack:
   cd /opt/rag-sbs
   docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

4. Inicializar la DB (correr migraciones):
   docker compose -f docker-compose.prod.yml --env-file .env.prod \
     exec api alembic upgrade head

5. Verificar:
   curl http://localhost:8000/v1/health

6. Configurar backups automáticos:
   bash scripts/lightsail/setup-backup-cron.sh

NEXT
