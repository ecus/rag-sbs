"""Implementación LLMProvider para Ollama local.

Ollama expone una API REST compatible con la SDK de OpenAI en algunos endpoints,
pero acá usamos los endpoints nativos para tener control fino.

Docs: https://github.com/ollama/ollama/blob/main/docs/api.md
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.llm.base import GenerationResult, LLMProvider


class OllamaProvider(LLMProvider):
    """Adapter para Ollama corriendo en host."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        embed_model: str,
        timeout_sec: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embed_model = embed_model
        self._cliente = httpx.AsyncClient(timeout=timeout_sec)

    async def close(self) -> None:
        await self._cliente.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings vía /api/embeddings.

        Ollama procesa de a uno; iteramos. En producción usar batch SDK.
        """
        vectores: list[list[float]] = []
        for texto in texts:
            respuesta = await self._cliente.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.embed_model, "prompt": texto},
            )
            respuesta.raise_for_status()
            vectores.append(respuesta.json()["embedding"])
        return vectores

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> GenerationResult:
        """Genera respuesta vía /api/generate (no streaming)."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        respuesta = await self._cliente.post(f"{self.base_url}/api/generate", json=payload)
        respuesta.raise_for_status()
        datos = respuesta.json()

        return GenerationResult(
            text=datos.get("response", "").strip(),
            # Ollama reporta `prompt_eval_count` y `eval_count` cuando el modelo
            # los provee; algunos modelos no los exponen → defaults a 0.
            input_tokens=datos.get("prompt_eval_count", 0),
            output_tokens=datos.get("eval_count", 0),
            model=self.model,
            extra={
                "total_duration_ns": datos.get("total_duration"),
                "eval_duration_ns": datos.get("eval_duration"),
            },
        )

    async def health(self) -> bool:
        """Ping a /api/tags (lista modelos). Si responde 200 → OK."""
        try:
            respuesta = await self._cliente.get(f"{self.base_url}/api/tags", timeout=5.0)
            return respuesta.status_code == 200
        except (httpx.HTTPError, httpx.ConnectError):
            return False

    async def generate_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Streaming nativo de Ollama: /api/generate con stream: true.

        Cada línea del response es un JSON con campos:
          { "response": "token", "done": false, ... }
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        async with self._cliente.stream(
            "POST", f"{self.base_url}/api/generate", json=payload
        ) as respuesta:
            respuesta.raise_for_status()
            async for linea in respuesta.aiter_lines():
                if not linea:
                    continue
                try:
                    datos = json.loads(linea)
                except json.JSONDecodeError:
                    continue
                texto = datos.get("response", "")
                if texto:
                    yield texto
                if datos.get("done"):
                    break
