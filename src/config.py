"""Configuración centralizada — lee .env vía pydantic-settings.

Toda variable de entorno usada por la app pasa por aquí. Esto permite:
- Validación de tipos al arrancar (falla rápido si .env está mal)
- Auto-completado en IDEs
- Single source of truth para tests (sobreescribibles)
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del sistema. Cada campo se mapea a una env var."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----- App -----
    app_env: Literal["local", "staging", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    app_version: str = "0.1.0"

    # ----- Database -----
    database_url: str = Field(
        default="postgresql+psycopg://rag:rag@localhost:5432/ragdb",
        description="DSN SQLAlchemy para Postgres con pgvector",
    )

    # ----- LLM Provider -----
    # ollama  → local dev (Ollama + qwen/nomic)
    # gemini  → Google AI Studio (free tier, solo API key, sin GCP project)
    # vertex_flash / vertex_pro → Vertex AI (requiere GCP project — Sprint 3)
    llm_provider: Literal["ollama", "gemini", "vertex_flash", "vertex_pro"] = "ollama"

    # Ollama (local dev)
    ollama_base_url: str = "http://host.containers.internal:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"
    embed_dim: int = 768

    # Google AI Studio (Gemini API directo, free tier disponible)
    # Modelos vigentes en AI Studio (mayo 2026):
    #   - gemini-2.5-flash  → caballo de batalla (free tier 1500 req/día)
    #   - gemini-2.5-pro    → razonamiento premium (free tier 50 req/día)
    #   - gemini-embedding-001 → embeddings GA (dim configurable 768/1536/3072)
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_pro_model: str = "gemini-2.5-pro"
    gemini_embed_model: str = "gemini-embedding-001"
    gemini_embed_dim: int = 768

    # Vertex AI (cloud — Sprint 3, requiere GCP project)
    google_cloud_project: str = ""
    vertex_location: str = "us-central1"
    vertex_flash_model: str = "gemini-2.5-flash"
    vertex_pro_model: str = "gemini-2.5-pro"
    vertex_embed_model: str = "text-embedding-005"

    # ----- RAG -----
    chunk_size: int = 768
    chunk_overlap: int = 96
    top_k: int = 5
    similarity_threshold: float = 0.78

    # Reranker backend: llm | cross_encoder | cohere
    # - llm (default local): usa LLMProvider, cero deps extra
    # - cross_encoder: requiere sentence-transformers + torch (~3GB)
    # - cohere: requiere COHERE_API_KEY, cobra por uso
    reranker_backend: Literal["llm", "cross_encoder", "cohere"] = "llm"
    cohere_api_key: str = ""
    cross_encoder_model: str = "BAAI/bge-reranker-base"

    # ----- Cache -----
    redis_url: str = "redis://localhost:6379/0"
    semantic_cache_ttl_sec: int = 86400
    semantic_cache_sim: float = 0.95

    # ----- Auth (Sprint 2) -----
    jwt_secret: str = "dev-only-not-secure"
    jwt_algorithm: str = "HS256"
    jwt_ttl_hours: int = 8


@lru_cache
def get_settings() -> Settings:
    """Singleton de configuración. Sobreescribible en tests con dependency_overrides."""
    return Settings()
