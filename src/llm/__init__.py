"""Factory de proveedores LLM.

Selección vía env var ``LLM_PROVIDER``:
- ``ollama``       → local dev (Ollama qwen/nomic).
- ``gemini``       → Google AI Studio API (free tier, solo API key).
- ``vertex_flash`` → Vertex AI Gemini Flash (Sprint 3, requiere GCP project).
- ``vertex_pro``   → Vertex AI Gemini Pro (Sprint 3).

ADR-001: la interfaz ``LLMProvider`` permite cambiar de proveedor sin tocar
el resto del código.
"""

from src.config import get_settings
from src.llm.base import LLMProvider
from src.llm.ollama import OllamaProvider


def get_llm_provider() -> LLMProvider:
    """Factory: retorna implementación según ``LLM_PROVIDER`` en config."""
    settings = get_settings()
    provider = settings.llm_provider

    if provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            embed_model=settings.ollama_embed_model,
        )

    if provider == "gemini":
        # Import lazy: solo carga el SDK si efectivamente se va a usar
        from src.llm.gemini import GeminiProvider
        return GeminiProvider(
            api_key=settings.google_api_key,
            model=settings.gemini_model,
            embed_model=settings.gemini_embed_model,
            embed_dim=settings.gemini_embed_dim,
        )

    raise NotImplementedError(
        f"Provider '{provider}' aún no implementado. "
        f"Opciones válidas: ollama, gemini."
    )


__all__ = ["LLMProvider", "OllamaProvider", "get_llm_provider"]
