# =============================================================================
# Multi-stage Dockerfile — RAG SBS API
# =============================================================================
# Stage 1: builder (instala deps en venv aislada)
# Stage 2: runtime (imagen final, mínima, solo runtime)
#
# Beneficios: imagen final ~250MB en lugar de 1GB, sin compiladores ni caches.
# =============================================================================

# ----- Stage 1: builder -----
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps para psycopg, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Crear venv aislada — copiable a runtime stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Instalar deps. Copiamos solo pyproject para aprovechar cache de Docker.
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install ".[dev]" || \
    pip install \
        "fastapi>=0.115.0" "uvicorn[standard]>=0.32.0" "python-multipart>=0.0.12" \
        "pydantic>=2.9.0" "pydantic-settings>=2.6.0" \
        "sqlalchemy>=2.0.35" "psycopg[binary,pool]>=3.2.3" "psycopg-pool>=3.2.0" "pgvector>=0.3.6" "alembic>=1.13.0" \
        "httpx>=0.27.0" "tenacity>=9.0.0" \
        "pymupdf>=1.24.0" "pypdf>=5.0.0" "tiktoken>=0.8.0" \
        "redis>=5.1.0" "structlog>=24.4.0" \
        "apscheduler>=3.10.4" \
        "numpy>=1.26.0" "scikit-learn>=1.5.0" \
        "streamlit>=1.40.0" "altair>=5.5.0" "pandas>=2.2.0" \
        "google-genai>=1.0.0" "boto3>=1.34.0"

# ----- Stage 2: runtime -----
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Solo libs runtime necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar venv del builder
COPY --from=builder /opt/venv /opt/venv

# Usuario sin privilegios (defensa en profundidad)
RUN groupadd -r app && useradd --no-log-init -r -g app app

WORKDIR /app

# Copiar código (al final, capa más volátil)
COPY --chown=app:app src/ ./src/
COPY --chown=app:app sql/ ./sql/
COPY --chown=app:app .streamlit/ ./.streamlit/

USER app

EXPOSE 8000

# Healthcheck nativo del container
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
