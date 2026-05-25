"""Provider Gemini API (Google AI Studio).

Usa el SDK oficial google-genai. Compatible con:
- API key de Google AI Studio (free tier) — el flujo más simple.
- Vertex AI (requiere proyecto GCP) — cuando se active vía env vars.

Free tier de Gemini 2.5 Flash: ~10 RPM. Si se excede, el SDK levanta un
ClientError 429 con ``RetryInfo``. Este provider implementa retry exponencial
respetando el ``retryDelay`` sugerido por la API.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from collections.abc import AsyncIterator

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from src.llm.base import GenerationResult, LLMProvider

logger = logging.getLogger(__name__)


def _delay_de_429(exc: Exception) -> float | None:
    """Extrae ``retry_delay`` (segundos) de un ClientError 429 si lo sugiere."""
    try:
        msg = str(exc)
        m = re.search(r"retry[Dd]elay['\"]?\s*:\s*['\"](\d+(?:\.\d+)?)s?", msg)
        if m:
            return float(m.group(1))
        m = re.search(r"retry in (\d+(?:\.\d+)?)s", msg)
        if m:
            return float(m.group(1))
    except Exception:  # noqa: BLE001
        pass
    return None


async def _con_retry(fn, *, max_intentos: int = 4, base_delay: float = 2.0):
    """Ejecuta ``fn`` con retry exponencial para 429 RESOURCE_EXHAUSTED.

    Si detecta agotamiento del quota DIARIO (mensaje "embed_content_free_tier
    _requests" o "RequestsPerDayPerProjectPerModel-FreeTier"), aborta sin
    reintentar — esperar al reset diario es lo único que ayuda.
    """
    for intento in range(max_intentos):
        try:
            return await fn()
        except genai_errors.ClientError as exc:
            if getattr(exc, "code", None) != 429:
                raise
            msg = str(exc)
            # Si es quota DIARIO agotado, no hay caso reintentar
            if "RequestsPerDay" in msg or "free_tier_requests" in msg:
                logger.error(
                    "Gemini quota diario agotado — abortar (espera reset 24h o "
                    "activar Tier 1 pagado por $5)"
                )
                raise
            sugerido = _delay_de_429(exc)
            if sugerido is None:
                sugerido = base_delay * (2 ** intento)
            sugerido += random.uniform(0, 1)
            logger.warning(
                "Gemini 429 RPM (intento %d/%d) — esperando %.1fs",
                intento + 1, max_intentos, sugerido,
            )
            if intento == max_intentos - 1:
                raise
            await asyncio.sleep(sugerido)


class GeminiProvider(LLMProvider):
    """Provider para Gemini API (Google AI Studio) con free tier."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-2.5-flash",
        embed_model: str = "gemini-embedding-001",
        embed_dim: int = 768,
        thinking_budget: int = 0,
    ) -> None:
        """Inicializa cliente Gemini.

        Args:
            thinking_budget: tokens internos de "thinking" que el modelo puede
                gastar antes de emitir texto visible. ``0`` desactiva thinking
                (recomendado para Flash en tareas determinísticas como JSON
                planner, ahorra latencia y tokens). Para tareas de razonamiento
                profundo (modo informe), usar ``-1`` (dinámico) o un valor alto.
        """
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY no configurado. Obtenerla en "
                "https://aistudio.google.com/app/apikey"
            )
        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.embed_model = embed_model
        self.embed_dim = embed_dim
        self.thinking_budget = thinking_budget

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embeddings batch. Gemini embed_content acepta hasta 100 textos."""
        if not texts:
            return []
        # El SDK síncrono se ejecuta en thread para no bloquear el event loop
        import asyncio
        loop = asyncio.get_event_loop()

        def _call() -> list[list[float]]:
            # Procesa en lotes de 100 (límite del API)
            cfg = types.EmbedContentConfig(output_dimensionality=self.embed_dim)
            resultados: list[list[float]] = []
            for i in range(0, len(texts), 100):
                lote = texts[i : i + 100]
                resp = self._client.models.embed_content(
                    model=self.embed_model,
                    contents=lote,
                    config=cfg,
                )
                for emb in resp.embeddings:
                    resultados.append(list(emb.values))
            return resultados

        async def _ejecutar():
            return await loop.run_in_executor(None, _call)
        try:
            return await _con_retry(_ejecutar)
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini embed falló: %s", exc)
            raise

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> GenerationResult:
        """Generación bloqueante."""
        import asyncio
        loop = asyncio.get_event_loop()

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system if system else None,
            thinking_config=types.ThinkingConfig(
                thinking_budget=self.thinking_budget
            ),
        )

        def _call() -> GenerationResult:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            texto = (resp.text or "").strip()
            usage = getattr(resp, "usage_metadata", None)
            return GenerationResult(
                text=texto,
                input_tokens=getattr(usage, "prompt_token_count", 0) if usage else 0,
                output_tokens=getattr(usage, "candidates_token_count", 0) if usage else 0,
                model=self.model,
                extra={
                    "finish_reason": (
                        resp.candidates[0].finish_reason.name
                        if resp.candidates and resp.candidates[0].finish_reason
                        else None
                    )
                },
            )

        async def _ejecutar():
            return await loop.run_in_executor(None, _call)
        try:
            return await _con_retry(_ejecutar)
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini generate falló: %s", exc)
            raise

    async def generate_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Streaming nativo de Gemini (SSE chunks)."""
        import asyncio
        loop = asyncio.get_event_loop()

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system if system else None,
            thinking_config=types.ThinkingConfig(
                thinking_budget=self.thinking_budget
            ),
        )

        # El SDK ofrece un iterador síncrono. Lo materializamos a lista en thread
        # y luego yieldeamos. Para volúmenes pequeños (un solo response) es
        # adecuado; si en el futuro se requiere streaming real puede cambiarse
        # a una cola entre thread productor y loop consumidor.
        def _materializar() -> list[str]:
            stream = self._client.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config=config,
            )
            chunks: list[str] = []
            for chunk in stream:
                txt = getattr(chunk, "text", None)
                if txt:
                    chunks.append(txt)
            return chunks

        try:
            chunks = await loop.run_in_executor(None, _materializar)
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini generate_stream falló: %s", exc)
            raise
        for c in chunks:
            yield c

    async def health(self) -> bool:
        """Smoke test: NO consume quota.

        Solo valida que la API key esté configurada y que el endpoint de
        ``list_models`` responda. Importante: no hace embed ni generate
        para evitar agotar el quota free tier (1000 emb/día).

        Si el quota está agotado (429 RESOURCE_EXHAUSTED), retorna ``True``
        igualmente porque el SERVICIO sigue alcanzable — solo el quota
        terminará renovándose en 24h.
        """
        try:
            import asyncio
            loop = asyncio.get_event_loop()

            def _ping() -> bool:
                # list_models es gratis y no consume quota
                modelos = list(self._client.models.list())
                return len(modelos) > 0

            return await loop.run_in_executor(None, _ping)
        except genai_errors.ClientError as exc:
            if getattr(exc, "code", None) == 429:
                # Quota exhausted, pero servicio sigue vivo
                logger.warning(
                    "Gemini quota exhausted (sigue alcanzable, esperar reset diario)"
                )
                return True
            logger.warning("Gemini health check falló: %s", exc)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini health check falló: %s", exc)
            return False
