"""Interfaz abstracta de proveedores LLM (Adapter pattern).

Separar interfaz de implementación nos permite:
- Testear con mocks sin tocar Ollama/Vertex reales
- Cambiar de proveedor con un cambio de config (cumple ADR-001)
- Documentar el contrato esperado
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class GenerationResult:
    """Resultado de una generación LLM con metadatos para tracing."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    extra: dict = field(default_factory=dict)


class LLMProvider(ABC):
    """Contrato común para todos los proveedores LLM (Ollama, Vertex, etc.)."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para una lista de textos.

        Args:
            texts: textos a embeber.
        Returns:
            Lista de vectores (floats). Dimensión depende del modelo.
        """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> GenerationResult:
        """Genera una respuesta.

        Args:
            prompt: user prompt.
            system: system prompt (opcional).
            temperature: 0-1, baja = deterministic.
            max_tokens: límite de tokens de salida.
        """

    @abstractmethod
    async def health(self) -> bool:
        """True si el proveedor está disponible (para /v1/health)."""

    async def generate_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Variante streaming — yields tokens conforme el LLM los emite.

        Default fallback: una sola llamada bloqueante a `generate` y yield del
        texto completo. Las implementaciones que soporten streaming nativo
        (Ollama, Vertex, OpenAI) deben sobrescribir esto.
        """
        result = await self.generate(
            prompt, system=system, temperature=temperature, max_tokens=max_tokens
        )
        yield result.text
